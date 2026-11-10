package io.github.markusklier.handheldatlas

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import org.json.JSONObject
import org.json.JSONTokener
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit

/**
 * Reads one Reddit post as JSON the way the user's browser would: an off-screen WebView opens the .json address
 * with the cookies of the Reddit login made in [RedditLoginActivity] (docs/REDDIT.md).
 */
object RedditFetcher {
    private val ALLOWED = Regex("^https://www\\.reddit\\.com/comments/[a-z0-9]{4,12}/\\.json\\?raw_json=1&limit=1$")
    private val gate = Semaphore(1)

    @SuppressLint("SetJavaScriptEnabled")
    fun fetch(ctx: Context, url: String): JSONObject {
        require(ALLOWED.matches(url)) { "Nur einzelne Reddit-Beiträge" }
        gate.acquire()
        try {
            val main = Handler(Looper.getMainLooper())
            val latch = CountDownLatch(1)
            var status = 0
            var body = ""
            var view: WebView? = null
            main.post {
                val w = WebView(ctx.applicationContext)
                view = w
                w.settings.javaScriptEnabled = true
                w.webViewClient = object : WebViewClient() {
                    override fun onReceivedHttpError(v: WebView, request: WebResourceRequest, response: WebResourceResponse) {
                        if (request.isForMainFrame) status = response.statusCode
                    }

                    override fun onReceivedError(v: WebView, request: WebResourceRequest, error: WebResourceError) {
                        if (request.isForMainFrame && status == 0) status = -1
                    }

                    override fun onPageFinished(v: WebView, finishedUrl: String) {
                        v.evaluateJavascript("(document.body && document.body.innerText) || ''") { value ->
                            body = try { JSONTokener(value ?: "\"\"").nextValue() as? String ?: "" } catch (e: Exception) { "" }
                            if (status == 0) status = 200
                            latch.countDown()
                        }
                    }
                }
                w.loadUrl(url)
            }
            val done = latch.await(25, TimeUnit.SECONDS)
            main.post { view?.destroy() }
            if (!done) return JSONObject().put("status", 0).put("body", "")
            val text = body.trimStart()
            if (status == 200 && !(text.startsWith("[") || text.startsWith("{"))) status = 403   // login or block page instead of JSON
            return JSONObject().put("status", status).put("body", if (status == 200) body else "")
        } finally {
            gate.release()
        }
    }

    fun loggedIn(): Boolean {
        val cookies = CookieManager.getInstance().getCookie("https://www.reddit.com") ?: return false
        return cookies.contains("reddit_session") || cookies.contains("token_v2")
    }
}

/** Reddit login in a WebView of the app. Atlas never sees the password; only Reddit's cookies stay in the app. */
class RedditLoginActivity : Activity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0A0D0C"))
        }
        val done = Button(this).apply {
            text = "Fertig – zurück zu Atlas"
            setOnClickListener { finish() }
        }
        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.webViewClient = WebViewClient()
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)
        root.addView(done, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(web, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)
        web.loadUrl("https://www.reddit.com/login/")
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else finish()
    }

    override fun onDestroy() {
        CookieManager.getInstance().flush()
        Screens.emitAll("reddit", JSONObject().put("loggedIn", RedditFetcher.loggedIn()))
        web.destroy()
        super.onDestroy()
    }
}
