package io.github.markusklier.handheldatlas

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

/**
 * One Atlas window: the web app in a WebView plus the native bridge ("AtlasBridge").
 * The bridge is only injected into pages of the Atlas origin; everything else opens in the browser.
 */
abstract class AtlasWebActivity : Activity() {
    lateinit var web: WebView
        private set
    private var bridge: Bridge? = null
    var role: String = Screens.MAIN
        private set

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        role = Screens.roleOf(this)
        web = WebView(this)
        web.setBackgroundColor(Color.parseColor("#0A0D0C"))
        setContentView(web, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        hideBars()

        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            setSupportMultipleWindows(false)
            userAgentString = "$userAgentString AtlasApp/${BuildConfig.VERSION_NAME}"
        }
        CookieManager.getInstance().setAcceptCookie(true)
        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return false
                val u = request.url
                if (isAtlas(u)) return false
                openExternal(u)
                return true
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                // only when the app shell itself cannot be loaded (first start without network)
                if (request.isForMainFrame && isAtlas(request.url)) view.loadUrl("file:///android_asset/offline.html#" + query())
            }
        }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            val b = Bridge(this)
            bridge = b
            WebViewCompat.addWebMessageListener(web, "AtlasBridge", setOf(BuildConfig.WEB_ORIGIN), b)
        }
        Screens.register(this)
        Shell.init()
        web.loadUrl(BuildConfig.WEB_URL + "?" + query())
    }

    private fun query(): String = "app=${BuildConfig.VERSION_CODE}" + if (role == Screens.COMPANION) "&screen=companion" else ""

    private fun isAtlas(u: Uri): Boolean =
        u.scheme == "https" && u.host == Uri.parse(BuildConfig.WEB_URL).host && (u.path ?: "").startsWith(Uri.parse(BuildConfig.WEB_URL).path ?: "/")

    fun openExternal(u: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, u).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: ActivityNotFoundException) {
            // no app for this link
        }
    }

    fun emit(event: String, data: Any?) {
        bridge?.emit(event, data)
    }

    private fun hideBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideBars()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        // moved to the other display: the window changes its role
        val now = Screens.roleOf(this)
        if (now != role) {
            role = now
            web.loadUrl(BuildConfig.WEB_URL + "?" + query())
        }
    }

    override fun onResume() {
        super.onResume()
        web.onResume()
        emit("resume", null)
    }

    override fun onPause() {
        web.onPause()
        super.onPause()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else moveTaskToBack(true)
    }

    override fun onDestroy() {
        Screens.unregister(this)
        web.destroy()
        super.onDestroy()
    }
}

/** Launcher window. Opens the second window on the other display when the device has two. */
class MainActivity : AtlasWebActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("atlas", MODE_PRIVATE)
        if (prefs.getBoolean("dual", true) && !Screens.hasSecond()) web.post { Screens.openSecond(this) }
    }

    override fun onDestroy() {
        Screens.closeSecond()
        super.onDestroy()
    }
}

/** Second window on the other display of a dual-screen handheld. */
class SecondActivity : AtlasWebActivity()
