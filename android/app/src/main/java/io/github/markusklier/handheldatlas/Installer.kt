package io.github.markusklier.handheldatlas

import android.app.AlertDialog
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Installs apps for the setup assistant. Rules (docs/SETUP.md):
 * - only APK files from the GitHub releases of the named repository,
 * - the user confirms every install in a native dialog (the web page cannot skip it),
 * - with Shizuku the install runs without Android's own dialog, otherwise Android asks once more.
 */
object Installer {
    private val REPO = Regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

    fun packages(ctx: Context, ids: JSONArray): JSONObject {
        val out = JSONObject()
        for (i in 0 until ids.length()) {
            val id = ids.optString(i)
            if (id.isBlank()) continue
            out.put(id, try {
                val p = ctx.packageManager.getPackageInfo(id, 0)
                JSONObject().put("version", p.versionName ?: "").put("code", p.longVersionCode).put("updated", p.lastUpdateTime)
            } catch (e: PackageManager.NameNotFoundException) {
                JSONObject.NULL
            })
        }
        return out
    }

    private fun confirm(act: AtlasWebActivity, title: String, text: String): Boolean {
        val latch = CountDownLatch(1)
        var ok = false
        act.runOnUiThread {
            if (act.isFinishing || act.isDestroyed) { latch.countDown(); return@runOnUiThread }
            AlertDialog.Builder(act)
                .setTitle(title).setMessage(text)
                .setPositiveButton("Installieren") { _, _ -> ok = true; latch.countDown() }
                .setNegativeButton("Abbrechen") { _, _ -> latch.countDown() }
                .setOnCancelListener { latch.countDown() }
                .show()
        }
        latch.await(5, TimeUnit.MINUTES)
        return ok
    }

    fun install(act: AtlasWebActivity, p: JSONObject): JSONObject {
        val repo = p.getString("repo")
        val url = p.getString("url")
        val name = p.optString("name", repo)
        require(REPO.matches(repo)) { "Ungültiges Repository" }
        require(url.startsWith("https://github.com/$repo/releases/download/") && url.substringBefore('?').endsWith(".apk", ignoreCase = true)) {
            "Atlas installiert nur APK-Dateien aus den GitHub-Releases des Projekts"
        }
        val fileName = Uri.parse(url).lastPathSegment ?: "app.apk"
        val silent = Shell.granted()
        val text = "Quelle: github.com/$repo\nDatei: $fileName\n\n" +
            (if (p.optBoolean("unverified")) "Hinweis: Dieses Projekt ist ein ungeprüfter KI-Fund. Installiere nur, wenn du der Quelle vertraust.\n\n" else "") +
            (if (silent) "Die Installation läuft danach ohne weitere Nachfrage (Shizuku)." else "Android fragt danach noch einmal nach.")
        if (!confirm(act, "$name installieren?", text)) throw IllegalStateException("Abgebrochen")

        val dir = File(act.externalCacheDir ?: act.cacheDir, "apk").apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() }
        val file = File(dir, "install-${System.currentTimeMillis()}.apk")
        download(url, file) { done, total ->
            Screens.emitAll("install", JSONObject().put("phase", "download").put("repo", repo).put("done", done).put("total", total))
        }
        val info = act.packageManager.getPackageArchiveInfo(file.path, 0)
            ?: run { file.delete(); throw IllegalStateException("Die geladene Datei ist keine gültige APK") }
        val pkg = info.packageName
        val expected = p.optString("sha256")
        if (expected.isNotBlank() && !expected.equals(sha256(file), ignoreCase = true)) {
            file.delete()
            throw IllegalStateException("Prüfsumme stimmt nicht – Installation abgebrochen")
        }
        val result = JSONObject().put("package", pkg).put("version", info.versionName ?: "").put("repo", repo)
        Screens.emitAll("install", JSONObject().put("phase", "installing").put("repo", repo).put("package", pkg))

        if (silent) {
            val out = try {
                Shell.exec("cat ${Shell.quote(file.path)} | pm install -r -S ${file.length()}", 240_000)
            } catch (e: Exception) {
                e.message ?: ""
            }
            if (out.contains("Success")) {
                file.delete()
                Screens.emitAll("install", JSONObject().put("phase", "done").put("repo", repo).put("package", pkg))
                return result.put("mode", "shizuku").put("done", true)
            }
            result.put("shizukuError", out.take(300))
        }
        if (!act.packageManager.canRequestPackageInstalls()) {
            act.runOnUiThread {
                act.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${act.packageName}")))
            }
            throw IllegalStateException("Erlaube Atlas zuerst, Apps zu installieren, und tippe dann noch einmal auf „Installieren“.")
        }
        systemInstall(act, file, pkg, repo)
        return result.put("mode", "system").put("done", false)
    }

    private fun systemInstall(ctx: Context, file: File, pkg: String, repo: String) {
        val installer = ctx.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        params.setAppPackageName(pkg)
        if (Build.VERSION.SDK_INT >= 31) params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        val id = installer.createSession(params)
        installer.openSession(id).use { session ->
            session.openWrite("base.apk", 0, file.length()).use { out ->
                file.inputStream().use { it.copyTo(out, 1 shl 16) }
                session.fsync(out)
            }
            val intent = Intent(ctx, InstallReceiver::class.java).putExtra("repo", repo).putExtra("pkg", pkg)
            val pending = PendingIntent.getBroadcast(ctx, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
            session.commit(pending.intentSender)
        }
    }

    private fun download(url: String, file: File, progress: (Long, Long) -> Unit) {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 15_000
        conn.readTimeout = 30_000
        conn.setRequestProperty("User-Agent", "HandheldAtlas/${BuildConfig.VERSION_NAME}")
        try {
            if (conn.responseCode !in 200..299) throw IllegalStateException("Download fehlgeschlagen (HTTP ${conn.responseCode})")
            val total = conn.contentLengthLong
            var done = 0L
            var last = 0L
            conn.inputStream.use { input ->
                file.outputStream().use { out ->
                    val buf = ByteArray(1 shl 16)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        done += n
                        val now = System.currentTimeMillis()
                        if (now - last > 400) { last = now; progress(done, total) }
                    }
                }
            }
            progress(done, total)
        } catch (e: Exception) {
            file.delete()
            throw e
        } finally {
            conn.disconnect()
        }
    }

    private fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    fun cleanup(ctx: Context) {
        File(ctx.externalCacheDir ?: ctx.cacheDir, "apk").listFiles()?.forEach { it.delete() }
    }
}

/** Result of an install through Android's own installer. */
class InstallReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        val base = JSONObject().put("repo", intent.getStringExtra("repo") ?: "").put("package", intent.getStringExtra("pkg") ?: "")
        when (status) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                if (confirm != null) {
                    try {
                        context.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    } catch (e: Exception) {
                        Screens.emitAll("install", base.put("phase", "error").put("message", "Installationsdialog konnte nicht geöffnet werden"))
                    }
                }
            }
            PackageInstaller.STATUS_SUCCESS -> {
                Installer.cleanup(context)
                Screens.emitAll("install", base.put("phase", "done"))
            }
            else -> {
                Installer.cleanup(context)
                val msg = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "Status $status"
                Screens.emitAll("install", base.put("phase", if (status == PackageInstaller.STATUS_FAILURE_ABORTED) "cancelled" else "error").put("message", msg))
            }
        }
    }
}
