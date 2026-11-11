package io.github.markusklier.handheldatlas

import android.Manifest
import android.app.ActivityOptions
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.webkit.WebView
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * The native side of the web app: `AtlasBridge.postMessage('{"id":"1","method":"info","params":{}}')`
 * answers with `{"id":"1","ok":true,"result":…}`; events arrive as `{"event":"measure","data":…}`.
 * Every method does one fixed thing; nothing here runs a command or opens a file chosen by the page.
 */
class Bridge(private val act: AtlasWebActivity) : WebViewCompat.WebMessageListener {
    @Volatile
    private var proxy: JavaScriptReplyProxy? = null
    private val main = Handler(Looper.getMainLooper())

    override fun onPostMessage(view: WebView, message: WebMessageCompat, sourceOrigin: Uri, isMainFrame: Boolean, replyProxy: JavaScriptReplyProxy) {
        // only the Atlas page itself (the listener is already limited to its origin)
        val page = try { view.url ?: "" } catch (e: Throwable) { BuildConfig.WEB_URL }
        if (!isMainFrame || sourceOrigin.toString().trimEnd('/') != BuildConfig.WEB_ORIGIN || !page.startsWith(BuildConfig.WEB_URL)) return
        proxy = replyProxy
        val request = try {
            JSONObject(message.data ?: return)
        } catch (e: JSONException) {
            return
        }
        val id = request.optString("id")
        val method = request.optString("method")
        val params = request.optJSONObject("params") ?: JSONObject()
        worker.execute {
            val answer = JSONObject().put("id", id)
            try {
                answer.put("ok", true).put("result", call(method, params) ?: JSONObject.NULL)
            } catch (e: Throwable) {
                answer.put("ok", false).put("error", e.message ?: e.javaClass.simpleName)
            }
            post(answer)
        }
    }

    fun emit(event: String, data: Any?) {
        post(JSONObject().put("event", event).put("data", data ?: JSONObject.NULL))
    }

    private fun post(o: JSONObject) {
        val p = proxy ?: return
        main.post {
            try {
                p.postMessage(o.toString())
            } catch (e: Throwable) {
                // page is gone
            }
        }
    }

    private fun call(method: String, p: JSONObject): Any? = when (method) {
        "info" -> DeviceInfo.info(act)
        "packages" -> Installer.packages(act, p.optJSONArray("ids") ?: JSONArray())
        "install" -> Installer.install(act, p)
        "launch" -> launch(p.getString("package"))
        "openUrl" -> openUrl(p.getString("url"))
        "shizuku" -> shizuku(p.optString("action", "state"))
        "second" -> second(p.optBoolean("open", true))
        "relay" -> { Screens.emitOthers(act, "relay", p); true }
        "focusOther" -> focusOther()
        "inputReady" -> { InputRouter.setReady(act); InputRouter.setRole(act, p.optString("role", "single")); JSONObject().put("target", InputRouter.target) }
        "setRole" -> { InputRouter.setRole(act, p.optString("role", "single")); JSONObject().put("target", InputRouter.target) }
        "setInput" -> { InputRouter.setTarget(p.optString("role", "browse")); JSONObject().put("target", InputRouter.target) }
        "measureStart" -> {
            if (Build.VERSION.SDK_INT >= 33) act.runOnUiThread { act.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7) }
            MeasureService.start(act, p.getString("package"), p.optString("label", p.getString("package")), p.optInt("seconds", 180),
                p.optJSONObject("meta") ?: JSONObject())
            if (p.optBoolean("launch", true)) launch(p.getString("package"))
            true
        }
        "measureStop" -> { MeasureService.stop(); true }
        "measureState" -> JSONObject().put("running", MeasureService.running).put("live", MeasureService.live ?: JSONObject.NULL)
            .put("last", MeasureService.last(act) ?: JSONObject.NULL)
        "selftest" -> SelfTest.run(act)
        "redditFetch" -> RedditFetcher.fetch(act, p.getString("url"))
        "redditLogin" -> { act.runOnUiThread { act.startActivity(Intent(act, RedditLoginActivity::class.java)) }; true }
        "redditState" -> JSONObject().put("loggedIn", RedditFetcher.loggedIn())
        else -> throw IllegalArgumentException("Unbekannte Funktion: $method")
    }

    private fun launch(pkg: String): Boolean {
        val intent = act.packageManager.getLaunchIntentForPackage(pkg) ?: throw IllegalStateException("App ist nicht installiert: $pkg")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val display = Screens.gameDisplay(act)
        act.runOnUiThread {
            try {
                if (display != null) act.startActivity(intent, ActivityOptions.makeBasic().setLaunchDisplayId(display.displayId).toBundle())
                else act.startActivity(intent)
            } catch (e: Exception) {
                try { act.startActivity(intent) } catch (e2: Exception) { emit("error", "Start fehlgeschlagen: ${e2.message}") }
            }
        }
        return true
    }

    /** Moves input focus (controller) to the Atlas window on the other display. */
    private fun focusOther(): Boolean {
        val other = Screens.all().firstOrNull { it !== act } ?: return false
        act.runOnUiThread {
            try {
                val i = Intent(other, other.javaClass).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_NEW_TASK)
                other.startActivity(i, ActivityOptions.makeBasic().setLaunchDisplayId(Screens.displayIdOf(other)).toBundle())
            } catch (e: Exception) {
                // the system refused; the window still exists and can be touched
            }
            other.web.requestFocus()
        }
        return true
    }

    private fun openUrl(url: String): Boolean {
        val u = Uri.parse(url)
        require(u.scheme == "https" || u.scheme == "market") { "Nur https- und Store-Links" }
        act.runOnUiThread { act.openExternal(u) }
        return true
    }

    private fun shizuku(action: String): JSONObject {
        when (action) {
            "request" -> Shell.request()
            "open" -> {
                val launch = act.packageManager.getLaunchIntentForPackage(Shell.SHIZUKU_PACKAGE)
                act.runOnUiThread {
                    if (launch != null) act.startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    else act.openExternal(Uri.parse("https://github.com/RikkaApps/Shizuku/releases/latest"))
                }
            }
        }
        return Shell.state(act)
    }

    private fun second(open: Boolean): JSONObject {
        act.getSharedPreferences("atlas", android.content.Context.MODE_PRIVATE).edit().putBoolean("dual", open).apply()
        var ok = false
        if (open) {
            val latch = java.util.concurrent.CountDownLatch(1)
            act.runOnUiThread { ok = Screens.hasSecond() || Screens.openSecond(act); latch.countDown() }
            latch.await()
        } else {
            Screens.closeSecond()
        }
        return JSONObject().put("open", open && ok).put("dual", Screens.displays(act).size >= 2)
    }

    companion object {
        private val worker = Executors.newCachedThreadPool()
    }
}
