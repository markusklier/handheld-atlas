package io.github.markusklier.handheldatlas

import android.content.ComponentName
import android.content.Context
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.IBinder
import android.os.SystemClock
import org.json.JSONObject
import rikka.shizuku.Shizuku
import java.util.concurrent.TimeUnit
import kotlin.system.exitProcess

/**
 * Shell access through Shizuku (same rights as "adb shell", no root, no PC).
 * Only native code builds commands; the web app never passes a raw command line.
 * Never call [exec] on the main thread.
 */
object Shell {
    private const val REQUEST = 4711
    const val SHIZUKU_PACKAGE = "moe.shizuku.privileged.api"

    @Volatile
    private var service: IShellService? = null
    private var binding = false
    private var started = false
    private val lock = Object()

    private val args by lazy {
        Shizuku.UserServiceArgs(ComponentName(BuildConfig.APPLICATION_ID, ShellService::class.java.name))
            .daemon(false).processNameSuffix("shell").debuggable(false).version(BuildConfig.VERSION_CODE)
    }

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            synchronized(lock) {
                service = if (binder != null && binder.pingBinder()) IShellService.Stub.asInterface(binder) else null
                binding = false
                lock.notifyAll()
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            synchronized(lock) { service = null; binding = false }
        }
    }

    @Synchronized
    fun init() {
        if (started) return
        started = true
        try {
            Shizuku.addRequestPermissionResultListener { _, _ -> notifyState() }
            Shizuku.addBinderReceivedListenerSticky { notifyState() }
            Shizuku.addBinderDeadListener { service = null; notifyState() }
        } catch (e: Throwable) {
            // Shizuku library not usable on this device: state() reports it
        }
    }

    private fun notifyState() {
        val a = Screens.any() ?: return
        Screens.emitAll("shizuku", state(a))
    }

    fun installed(ctx: Context): Boolean = try {
        ctx.packageManager.getPackageInfo(SHIZUKU_PACKAGE, 0); true
    } catch (e: PackageManager.NameNotFoundException) {
        false
    }

    fun running(): Boolean = try { Shizuku.pingBinder() } catch (e: Throwable) { false }

    fun granted(): Boolean = try {
        running() && !Shizuku.isPreV11() && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
    } catch (e: Throwable) {
        false
    }

    fun request(): Boolean {
        if (!running()) return false
        if (granted()) return true
        return try { Shizuku.requestPermission(REQUEST); true } catch (e: Throwable) { false }
    }

    fun state(ctx: Context): JSONObject {
        val o = JSONObject().put("installed", installed(ctx)).put("running", running()).put("granted", granted())
        try {
            if (running()) o.put("version", Shizuku.getVersion()).put("uid", Shizuku.getUid())
        } catch (e: Throwable) {
            // binder died in between
        }
        return o
    }

    private fun connect(): IShellService? {
        service?.let { if (it.asBinder().pingBinder()) return it }
        if (!granted()) return null
        synchronized(lock) {
            service = null
            if (!binding) {
                binding = true
                try {
                    Shizuku.bindUserService(args, connection)
                } catch (e: Throwable) {
                    binding = false
                    return null
                }
            }
            val end = SystemClock.elapsedRealtime() + 10_000
            while (service == null) {
                val left = end - SystemClock.elapsedRealtime()
                if (left <= 0) break
                lock.wait(left)
            }
            if (service == null) binding = false
            return service
        }
    }

    /** Runs a command as shell user and returns stdout+stderr. Throws when Shizuku is not ready. */
    fun exec(command: String, timeoutMs: Int = 15_000): String {
        for (attempt in 0..1) {
            val s = connect() ?: throw IllegalStateException("Shizuku ist nicht bereit")
            try {
                return s.exec(command, timeoutMs) ?: ""
            } catch (e: Exception) {
                service = null   // service process died: bind again once
                if (attempt == 1) throw IllegalStateException("Shell-Dienst antwortet nicht: ${e.message}")
            }
        }
        return ""
    }

    fun quote(s: String): String = "'" + s.replace("'", "'\\''") + "'"
}

/** Lives in a separate process started by Shizuku with shell uid. */
class ShellService() : IShellService.Stub() {
    @Suppress("unused")
    constructor(context: Context) : this()

    override fun destroy() {
        exitProcess(0)
    }

    override fun exec(command: String, timeoutMs: Int): String {
        val process = ProcessBuilder("sh", "-c", command).redirectErrorStream(true).start()
        val out = StringBuffer()
        val reader = Thread {
            try {
                process.inputStream.bufferedReader().use { r ->
                    val buf = CharArray(8192)
                    while (true) {
                        val n = r.read(buf)
                        if (n < 0) break
                        if (out.length < MAX_OUTPUT) out.append(buf, 0, n)
                    }
                }
            } catch (e: Exception) {
                // stream closed
            }
        }
        reader.start()
        val finished = process.waitFor(timeoutMs.toLong().coerceIn(500L, 300_000L), TimeUnit.MILLISECONDS)
        if (!finished) process.destroyForcibly()
        reader.join(if (finished) 3000 else 500)
        return if (finished) out.toString() else "$out\n[Zeitüberschreitung]"
    }

    companion object {
        private const val MAX_OUTPUT = 400_000
    }
}
