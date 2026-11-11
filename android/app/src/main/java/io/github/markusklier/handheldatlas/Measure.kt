package io.github.markusklier.handheldatlas

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.Instant
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * Reads the frame timestamps of a game's surface from SurfaceFlinger (shell rights through Shizuku):
 *   dumpsys SurfaceFlinger --list              → layer names
 *   dumpsys SurfaceFlinger --latency <layer>   → refresh period, then up to 127 rows "desired actual ready" (ns)
 * Polled twice a second, so no frame is lost up to ~250 fps.
 */
class FrameSampler(private val sh: (String) -> String, private val pkg: String) {
    var layer: String? = null
        private set
    var refreshNs = 0L
        private set
    var emptyPolls = 0
        private set
    var candidates: List<String> = emptyList()
        private set
    var rawSample = ""
        private set
    var picks = 0
        private set

    private var lastTs = 0L
    private var data = LongArray(1 shl 14)
    var count = 0
        private set

    fun intervals(): LongArray = data.copyOf(count)

    private fun add(v: Long) {
        if (count == data.size) {
            if (data.size >= MAX_FRAMES) return
            data = data.copyOf(data.size * 2)
        }
        data[count++] = v
    }

    private fun read(name: String): List<Long> {
        val out = sh("dumpsys SurfaceFlinger --latency ${Shell.quote(name)}")
        val lines = out.lines()
        if (lines.isEmpty()) return emptyList()
        lines[0].trim().toLongOrNull()?.let { if (it > 0) refreshNs = it }
        if (rawSample.isEmpty() && lines.size > 3) rawSample = lines.take(6).joinToString("\n").take(400)
        val ts = ArrayList<Long>(128)
        for (i in 1 until lines.size) {
            val parts = lines[i].trim().split(WS)
            if (parts.size < 3) continue
            val actual = parts[1].toLongOrNull() ?: continue
            if (actual <= 0L || actual == Long.MAX_VALUE) continue   // empty slot or frame still pending
            ts.add(actual)
        }
        return ts
    }

    /** Chooses the layer of the package that is currently producing frames. */
    fun pick(): Boolean {
        picks++
        val all = sh("dumpsys SurfaceFlinger --list").lineSequence().map { it.trim() }
            .filter { it.contains(pkg) && !it.startsWith("Background for") }.distinct().toList()
        // game surfaces first: SurfaceView / BLAST buffer layers
        candidates = all.sortedBy { if (it.startsWith("SurfaceView[") && it.contains("BLAST")) 0 else if (it.contains("SurfaceView")) 1 else 2 }
        val now = System.nanoTime()
        var best: String? = null
        var bestFrames = 0
        var bestLast = 0L
        for (c in candidates.take(12)) {
            val ts = read(c)
            val recent = ts.count { now - it < 2_000_000_000L }
            if (recent > bestFrames) {
                best = c; bestFrames = recent; bestLast = ts.maxOrNull() ?: 0L
            }
        }
        if (best == null) return false
        if (best != layer) {
            layer = best
            lastTs = bestLast   // frames before this moment do not count
        }
        emptyPolls = 0
        return true
    }

    /** Returns the number of new frames since the last call. */
    fun poll(): Int {
        val name = layer ?: return 0
        val ts = read(name).filter { it > lastTs }.sorted()
        if (ts.isEmpty()) {
            emptyPolls++
            return 0
        }
        emptyPolls = 0
        var prev = lastTs
        for (t in ts) {
            if (prev != 0L) {
                val d = t - prev
                if (d in 1..2_000_000_000L) add(d)
            }
            prev = t
        }
        lastTs = prev
        return ts.size
    }

    companion object {
        private val WS = Regex("\\s+")
        private const val MAX_FRAMES = 1 shl 19   // ~70 minutes at 120 fps
    }
}

object FrameStats {
    private fun r1(v: Double) = (v * 10).roundToInt() / 10.0

    /** avg fps, "1 % low" (mean of the slowest 1 % of frames), frame-time percentiles and stutter count. */
    fun of(intervalsNs: LongArray): JSONObject {
        val o = JSONObject().put("frames", intervalsNs.size)
        if (intervalsNs.size < 10) return o
        val sorted = intervalsNs.copyOf().also { it.sort() }
        val total = intervalsNs.sum().toDouble()
        val ms = { ns: Long -> ns / 1e6 }
        val pct = { p: Double -> sorted[((sorted.size - 1) * p).toInt()] }
        val median = pct(0.5)
        val slowest = sorted.copyOfRange((sorted.size * 0.99).toInt().coerceAtMost(sorted.size - 1), sorted.size)
        val low1 = 1e9 / (slowest.sum().toDouble() / slowest.size)
        val stutterLimit = max(median * 2.5, 25e6)
        o.put("seconds", r1(total / 1e9))
        o.put("fps", JSONObject().put("avg", r1(intervalsNs.size / (total / 1e9))).put("low1", r1(low1)))
        o.put("frameMs", JSONObject().put("p50", r1(ms(median))).put("p95", r1(ms(pct(0.95)))).put("p99", r1(ms(pct(0.99))))
            .put("max", r1(ms(sorted.last()))))
        o.put("stutters", intervalsNs.count { it > stutterLimit })
        return o
    }
}

/**
 * Temperatures. First "dumpsys thermalservice" (type 0 CPU, 1 GPU, 2 battery, 3 skin); devices that report nothing
 * useful there (the AYN Thor in the first self-test) are read from the kernel's thermal zones instead
 * (/sys/class/thermal/thermal_zone*/type + temp, readable with shell rights).
 */
class Thermals(private val sh: (String) -> String) {
    private val maxBy = HashMap<String, Double>()
    private var skinFirst: Double? = null
    private var skinLast: Double? = null
    private var maxStatus = 0
    var samples = 0
        private set
    var source = ""
        private set
    var raw = ""
        private set

    private fun put(kind: String, v: Double) {
        if (v < -30 || v > 150) return
        maxBy[kind] = max(maxBy[kind] ?: v, v)
    }

    fun sample() {
        val out = try { sh(CMD) } catch (e: Exception) { return }
        if (raw.isEmpty()) raw = out.take(1500)
        val (hal, zones) = out.split(SPLIT).let { it[0] to it.getOrElse(1) { "" } }
        var skin: Double? = null
        var found = 0
        for (blk in BLOCK.findAll(hal)) {
            val b = blk.value
            val value = VALUE.find(b)?.groupValues?.get(1)?.toDoubleOrNull() ?: continue
            val type = TYPE.find(b)?.groupValues?.get(1)?.toIntOrNull() ?: continue
            if (value.isNaN() || value > 1000) continue
            STATUS.find(b)?.groupValues?.get(1)?.toIntOrNull()?.let { maxStatus = max(maxStatus, it) }
            val kind = when (type) { 0 -> "cpu"; 1 -> "gpu"; 2 -> "battery"; 3 -> "skin"; else -> null } ?: continue
            put(kind, value)
            found++
            if (kind == "skin") skin = max(skin ?: value, value)
        }
        if (found > 0) source = "thermalservice"
        if (found == 0 || maxBy["cpu"] == null) {
            for (line in zones.lines()) {
                val parts = line.trim().split(WS)
                if (parts.size < 2) continue
                val name = parts[0].lowercase()
                var v = parts[1].toDoubleOrNull() ?: continue
                if (v > 1000) v /= 1000.0
                if (v <= 0) continue
                val kind = when {
                    CPU.containsMatchIn(name) -> "cpu"
                    GPU.containsMatchIn(name) -> "gpu"
                    SKIN.containsMatchIn(name) -> "skin"
                    BAT.containsMatchIn(name) -> "battery"
                    else -> null
                } ?: continue
                put(kind, v)
                if (kind == "skin") skin = max(skin ?: v, v)
                found++
            }
            if (found > 0 && source.isEmpty()) source = "sysfs"
        }
        if (skin != null) {
            if (skinFirst == null) skinFirst = skin
            skinLast = skin
        }
        samples++
    }

    fun json(): JSONObject {
        val o = JSONObject()
        maxBy["cpu"]?.let { o.put("cpuMax", it) }
        maxBy["gpu"]?.let { o.put("gpuMax", it) }
        maxBy["battery"]?.let { o.put("batteryMax", it) }
        maxBy["skin"]?.let { o.put("skinMax", it) }
        skinFirst?.let { o.put("skinStart", it) }
        skinLast?.let { o.put("skinEnd", it) }
        o.put("throttleStatus", maxStatus)   // 0 none … 3 severe and above
        if (source.isNotEmpty()) o.put("source", source)
        return o
    }

    companion object {
        private const val SPLIT = "===ATLAS-SYSFS==="
        private val CMD = "dumpsys thermalservice 2>&1 | head -120; echo $SPLIT; " +
            "for z in /sys/class/thermal/thermal_zone*; do echo \"$(cat \$z/type 2>/dev/null) $(cat \$z/temp 2>/dev/null)\"; done 2>/dev/null"
        private val BLOCK = Regex("Temperature\\{[^}]*\\}")
        private val VALUE = Regex("mValue=([-\\d.]+)")
        private val TYPE = Regex("mType=(-?\\d+)")
        private val STATUS = Regex("mStatus=(\\d+)")
        private val WS = Regex("\\s+")
        private val CPU = Regex("^(cpu|cpuss|apc|cpu-\\d|cpullc|cpu\\d)")
        private val GPU = Regex("gpu")
        private val SKIN = Regex("skin|xo-therm|quiet|sys-therm|shell|board|case|surface")
        private val BAT = Regex("battery|bms|batt")
    }
}

/** Power draw from the battery gauge (only meaningful while not charging). */
class Power(private val ctx: Context) {
    private val bm = ctx.getSystemService(BatteryManager::class.java)
    private var sumW = 0.0
    private var n = 0
    private var levelStart = -1
    private var levelEnd = -1
    private var plugged = false

    fun sample() {
        val st = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return
        val level = st.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        if (levelStart < 0) levelStart = level
        levelEnd = level
        if (st.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0) plugged = true
        val mv = st.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0)
        var ua = abs(bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW).toDouble())
        if (ua == 0.0 || mv == 0) return
        if (ua < 20_000) ua *= 1000   // some gauges report mA instead of µA
        sumW += ua / 1e6 * mv / 1e3
        n++
    }

    fun json(): JSONObject {
        val o = JSONObject().put("plugged", plugged).put("levelStart", levelStart).put("levelEnd", levelEnd)
        if (n > 0 && !plugged) o.put("avgW", (sumW / n * 10).roundToInt() / 10.0)
        return o
    }
}

/**
 * "Messfahrt": measures the running game while the user plays. Foreground service, so it survives Atlas being in
 * the background. Sends live values to the Atlas windows (the companion screen stays visible on a dual-screen device).
 */
class MeasureService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopFlag = true
            if (!running) stopSelf()
            return START_NOT_STICKY
        }
        val request = intent
        val pkg = request?.getStringExtra("package")
        if (request == null || pkg == null || running) {
            if (!running) stopSelf()
            return START_NOT_STICKY
        }
        val label = request.getStringExtra("label") ?: pkg
        val seconds = request.getIntExtra("seconds", 180).coerceIn(20, 1800)
        val meta = request.getStringExtra("meta") ?: "{}"
        running = true
        stopFlag = false
        val n = notification("Messfahrt läuft: $label", "Spiel einfach weiter – Atlas misst Bildrate und Temperatur.", true)
        if (Build.VERSION.SDK_INT >= 34) startForeground(NOTIFICATION, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        else startForeground(NOTIFICATION, n)
        Thread { measure(pkg, label, seconds, meta) }.start()
        return START_NOT_STICKY
    }

    private fun channel() {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, getString(R.string.measure_channel), NotificationManager.IMPORTANCE_LOW))
        }
    }

    private fun notification(title: String, text: String, ongoing: Boolean): Notification {
        channel()
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val b = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_recent_history)
            .setContentTitle(title).setContentText(text).setOngoing(ongoing).setContentIntent(open).setAutoCancel(!ongoing)
        if (ongoing) {
            val stop = PendingIntent.getService(this, 1, Intent(this, MeasureService::class.java).setAction(ACTION_STOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            b.addAction(0, "Messung beenden", stop)
        }
        return b.build()
    }

    private fun measure(pkg: String, label: String, seconds: Int, meta: String) {
        val sh = { c: String -> Shell.exec(c, 5000) }
        val sampler = FrameSampler(sh, pkg)
        val thermals = Thermals(sh)
        val power = Power(this)
        val series = JSONArray()
        val startedAt = Instant.now().toString()
        val t0 = SystemClock.elapsedRealtime()
        var firstFrame = 0L
        var lastFrame = 0L
        var bucketStart = t0
        var bucketFrames = 0
        var lastPick = 0L
        var lastSlow = 0L
        var error: String? = null
        try {
            while (!stopFlag) {
                val now = SystemClock.elapsedRealtime()
                if ((sampler.layer == null || sampler.emptyPolls >= 6) && now - lastPick > 3000) {
                    lastPick = now
                    sampler.pick()
                }
                val n = sampler.poll()
                if (n > 0) {
                    if (firstFrame == 0L) { firstFrame = now; bucketStart = now; bucketFrames = 0 }
                    lastFrame = now
                    bucketFrames += n
                }
                if (now - lastSlow >= 5000) {
                    lastSlow = now
                    thermals.sample()
                    power.sample()
                }
                if (firstFrame != 0L && now - bucketStart >= 1000) {
                    val fps = bucketFrames * 1000.0 / (now - bucketStart)
                    if (series.length() < 3600) series.put(fps.roundToInt())
                    bucketFrames = 0
                    bucketStart = now
                    val elapsed = ((now - firstFrame) / 1000).toInt()
                    val l = JSONObject().put("state", "running").put("package", pkg).put("label", label)
                        .put("fps", (fps * 10).roundToInt() / 10.0).put("elapsed", elapsed).put("seconds", seconds)
                        .put("temp", thermals.json())
                    live = l
                    Screens.emitAll("measure", l)
                } else if (firstFrame == 0L && (now - t0) % 2000 < 450) {
                    val l = JSONObject().put("state", "waiting").put("package", pkg).put("label", label)
                        .put("waited", ((now - t0) / 1000).toInt()).put("layers", sampler.candidates.size)
                    live = l
                    Screens.emitAll("measure", l)
                }
                if (firstFrame == 0L && now - t0 > 180_000) { error = "no-frames"; break }
                if (firstFrame != 0L && now - firstFrame >= seconds * 1000L) break
                if (firstFrame != 0L && now - lastFrame > 30_000) break   // game closed or paused for good
                Thread.sleep(400)
            }
        } catch (e: Throwable) {
            error = e.message ?: e.javaClass.simpleName
        }
        thermals.sample()
        power.sample()
        val result = FrameStats.of(sampler.intervals())
            .put("package", pkg).put("label", label).put("startedAt", startedAt).put("wanted", seconds)
            .put("stopped", if (error != null) "error" else if (stopFlag) "user" else "auto")
            .put("refreshHz", if (sampler.refreshNs > 0) (1e9 / sampler.refreshNs).roundToInt() else 0)
            .put("series", series).put("temp", thermals.json()).put("power", power.json())
            .put("appVersion", try { packageManager.getPackageInfo(pkg, 0).versionName ?: "" } catch (e: Exception) { "" })
            .put("meta", try { JSONObject(meta) } catch (e: Exception) { JSONObject() })
            .put("diag", JSONObject().put("layer", sampler.layer ?: "").put("candidates", JSONArray(sampler.candidates.take(12)))
                .put("raw", sampler.rawSample).put("picks", sampler.picks))
        if (error != null) result.put("error", error)
        try {
            File(filesDir, LAST).writeText(result.toString())
        } catch (e: Exception) {
            // result still goes to the windows
        }
        live = null
        running = false
        Screens.emitAll("measure", JSONObject().put("state", "done").put("result", result))
        @Suppress("DEPRECATION")
        stopForeground(true)
        val fps = result.optJSONObject("fps")
        val text = if (fps != null) "Ø ${fps.optDouble("avg")} FPS · 1 % Low ${fps.optDouble("low1")} FPS – in Atlas ansehen" else "Keine Bilder gemessen – in Atlas ansehen"
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION + 1, notification("Messfahrt fertig: $label", text, false))
        stopSelf()
    }

    companion object {
        private const val CHANNEL = "measure"
        private const val NOTIFICATION = 41
        private const val LAST = "measure-last.json"
        const val ACTION_STOP = "io.github.markusklier.handheldatlas.STOP_MEASURE"

        @Volatile var running = false
        @Volatile var stopFlag = false
        @Volatile var live: JSONObject? = null

        fun start(ctx: Context, pkg: String, label: String, seconds: Int, meta: JSONObject) {
            if (!Shell.granted()) throw IllegalStateException("Zum Messen braucht Atlas Shizuku")
            if (running) throw IllegalStateException("Es läuft schon eine Messfahrt")
            ctx.startForegroundService(Intent(ctx, MeasureService::class.java)
                .putExtra("package", pkg).putExtra("label", label).putExtra("seconds", seconds).putExtra("meta", meta.toString()))
        }

        fun stop() {
            stopFlag = true
        }

        fun last(ctx: Context): JSONObject? = try {
            JSONObject(File(ctx.filesDir, LAST).readText())
        } catch (e: Exception) {
            null
        }
    }
}
