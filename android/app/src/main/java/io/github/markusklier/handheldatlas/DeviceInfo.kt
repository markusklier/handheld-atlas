package io.github.markusklier.handheldatlas

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.os.Environment
import android.os.StatFs
import androidx.core.app.NotificationManagerCompat
import androidx.webkit.WebViewCompat
import org.json.JSONArray
import org.json.JSONObject

object DeviceInfo {
    fun device(ctx: Context): JSONObject {
        val mem = ActivityManager.MemoryInfo().also { ctx.getSystemService(ActivityManager::class.java).getMemoryInfo(it) }
        val stat = StatFs(Environment.getDataDirectory().path)
        return JSONObject()
            .put("manufacturer", Build.MANUFACTURER).put("brand", Build.BRAND).put("model", Build.MODEL)
            .put("device", Build.DEVICE).put("product", Build.PRODUCT).put("hardware", Build.HARDWARE).put("board", Build.BOARD)
            .put("soc", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else "")
            .put("socMaker", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MANUFACTURER else "")
            .put("ramGb", Math.round(mem.totalMem / 1e9 * 10) / 10.0)
            .put("storageGb", Math.round(stat.totalBytes / 1e9))
            .put("storageFreeGb", Math.round(stat.availableBytes / 1e9))
            .put("android", Build.VERSION.RELEASE).put("sdk", Build.VERSION.SDK_INT)
            .put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
            .put("build", Build.DISPLAY)
    }

    fun info(act: AtlasWebActivity): JSONObject = JSONObject()
        .put("app", JSONObject().put("version", BuildConfig.VERSION_NAME).put("code", BuildConfig.VERSION_CODE)
            .put("package", BuildConfig.APPLICATION_ID)
            .put("webview", WebViewCompat.getCurrentWebViewPackage(act)?.versionName ?: ""))
        .put("role", act.role)
        .put("displayId", Screens.displayIdOf(act))
        .put("dual", Screens.displays(act).size >= 2)
        .put("second", Screens.hasSecond())
        .put("device", device(act))
        .put("displays", Screens.describe(act))
        .put("shizuku", Shell.state(act))
        .put("canInstall", act.packageManager.canRequestPackageInstalls())
        .put("notifications", NotificationManagerCompat.from(act).areNotificationsEnabled())
        .put("measuring", MeasureService.running)
}
