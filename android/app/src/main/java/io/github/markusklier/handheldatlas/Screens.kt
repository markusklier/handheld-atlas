package io.github.markusklier.handheldatlas

import android.app.Activity
import android.app.ActivityManager
import android.app.ActivityOptions
import android.content.Context
import android.content.Intent
import android.hardware.display.DisplayManager
import android.util.DisplayMetrics
import android.view.Display
import org.json.JSONArray
import org.json.JSONObject
import java.lang.ref.WeakReference

/**
 * The windows of Atlas and the displays of the device.
 * On a dual-screen handheld the window on the largest display is "main" (game page, pictures) and the window
 * on the smallest display is "companion" (lists, setup checklist, live values). Games start on the largest display.
 */
object Screens {
    const val MAIN = "main"
    const val COMPANION = "companion"

    private val windows = LinkedHashMap<String, WeakReference<AtlasWebActivity>>()

    @Synchronized
    fun register(a: AtlasWebActivity) {
        windows[a.javaClass.name] = WeakReference(a)
    }

    @Synchronized
    fun unregister(a: AtlasWebActivity) {
        if (windows[a.javaClass.name]?.get() === a) windows.remove(a.javaClass.name)
    }

    @Synchronized
    fun all(): List<AtlasWebActivity> = windows.values.mapNotNull { it.get() }.filter { !it.isDestroyed }

    fun any(): AtlasWebActivity? = all().firstOrNull()

    fun emitAll(event: String, data: Any?) {
        for (a in all()) a.emit(event, data)
    }

    fun emitOthers(from: AtlasWebActivity, event: String, data: Any?) {
        for (a in all()) if (a !== from) a.emit(event, data)
    }

    fun displays(ctx: Context): List<Display> =
        ctx.getSystemService(DisplayManager::class.java).displays
            .filter { it.state != Display.STATE_OFF && (it.flags and Display.FLAG_PRIVATE) == 0 }

    @Suppress("DEPRECATION")
    private fun metrics(d: Display) = DisplayMetrics().also { d.getRealMetrics(it) }

    /** Physical area in square inches; falls back to a density-based estimate when the panel reports no real dpi. */
    fun area(d: Display): Double {
        val m = metrics(d)
        val xdpi = if (m.xdpi > 50f) m.xdpi else m.densityDpi.toFloat()
        val ydpi = if (m.ydpi > 50f) m.ydpi else m.densityDpi.toFloat()
        return (m.widthPixels / xdpi.toDouble()) * (m.heightPixels / ydpi.toDouble())
    }

    fun gameDisplay(ctx: Context): Display? = displays(ctx).maxByOrNull { area(it) }

    fun displayIdOf(a: Activity): Int = a.display?.displayId ?: Display.DEFAULT_DISPLAY

    fun roleOf(a: Activity): String {
        val ds = displays(a)
        if (ds.size < 2) return MAIN
        val smallest = ds.minByOrNull { area(it) } ?: return MAIN
        return if (smallest.displayId == displayIdOf(a)) COMPANION else MAIN
    }

    fun describe(ctx: Context): JSONArray {
        val out = JSONArray()
        val game = gameDisplay(ctx)?.displayId
        for (d in ctx.getSystemService(DisplayManager::class.java).displays) {
            val m = metrics(d)
            out.put(
                JSONObject()
                    .put("id", d.displayId).put("name", d.name)
                    .put("width", m.widthPixels).put("height", m.heightPixels)
                    .put("dpi", m.densityDpi).put("xdpi", m.xdpi.toDouble()).put("ydpi", m.ydpi.toDouble())
                    .put("hz", Math.round(d.refreshRate * 10) / 10.0)
                    .put("modes", JSONArray(d.supportedModes.map { Math.round(it.refreshRate).toInt() }.distinct().sorted()))
                    .put("areaSqIn", Math.round(area(d) * 10) / 10.0)
                    .put("default", d.displayId == Display.DEFAULT_DISPLAY)
                    .put("private", (d.flags and Display.FLAG_PRIVATE) != 0)
                    .put("on", d.state != Display.STATE_OFF)
                    .put("game", d.displayId == game)
            )
        }
        return out
    }

    /** Opens the second Atlas window on the other display. False when there is none or the system refuses. */
    fun openSecond(from: Activity): Boolean {
        val mine = displayIdOf(from)
        val other = displays(from).filter { it.displayId != mine }.minByOrNull { area(it) } ?: return false
        val intent = Intent(from, SecondActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            val am = from.getSystemService(ActivityManager::class.java)
            if (!am.isActivityStartAllowedOnDisplay(from, other.displayId, intent)) return false
            from.startActivity(intent, ActivityOptions.makeBasic().setLaunchDisplayId(other.displayId).toBundle())
            true
        } catch (e: Exception) {
            false
        }
    }

    fun closeSecond() {
        for (a in all()) if (a is SecondActivity) a.runOnUiThread { a.finish() }
    }

    fun hasSecond(): Boolean = all().any { it is SecondActivity }
}
