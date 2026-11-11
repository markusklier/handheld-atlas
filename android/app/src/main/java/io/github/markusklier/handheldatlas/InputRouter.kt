package io.github.markusklier.handheldatlas

import android.os.Handler
import android.os.Looper
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import org.json.JSONObject
import java.util.WeakHashMap
import kotlin.math.abs

/**
 * One controller, two screens: every button press goes to exactly one Atlas window.
 *
 * Android delivers key events to the window that has focus (usually the one touched last) and the Gamepad API of
 * both WebViews sees every button – that made both screens react at once. So the activities consume controller keys
 * here and send them as "input" events to the window the page chose (`setInput`): the browse window by default,
 * the stage while you look at a game. Pages that never called `inputReady` keep the normal behaviour.
 */
object InputRouter {
    private val roles = WeakHashMap<AtlasWebActivity, String>()      // "browse" | "stage" | "single"
    private val ready = WeakHashMap<AtlasWebActivity, Boolean>()
    @Volatile var target = "browse"
        private set
    private val main = Handler(Looper.getMainLooper())

    @Synchronized fun setRole(a: AtlasWebActivity, role: String) { roles[a] = role }
    @Synchronized fun roleOf(a: AtlasWebActivity): String = roles[a] ?: "single"
    @Synchronized fun setReady(a: AtlasWebActivity) { ready[a] = true }
    @Synchronized fun isReady(a: AtlasWebActivity) = ready[a] == true
    @Synchronized fun forget(a: AtlasWebActivity) { roles.remove(a); ready.remove(a) }

    fun setTarget(role: String) {
        target = role
        Screens.emitAll("inputTarget", JSONObject().put("role", role))
    }

    @Synchronized private fun windowFor(role: String): AtlasWebActivity? =
        Screens.all().firstOrNull { roles[it] == role && ready[it] == true }

    fun send(from: AtlasWebActivity, key: String, repeat: Boolean) {
        val win = windowFor(target) ?: from
        win.emit("input", JSONObject().put("key", key).put("repeat", repeat))
    }

    fun keyName(code: Int): String? = when (code) {
        KeyEvent.KEYCODE_DPAD_UP -> "up"
        KeyEvent.KEYCODE_DPAD_DOWN -> "down"
        KeyEvent.KEYCODE_DPAD_LEFT -> "left"
        KeyEvent.KEYCODE_DPAD_RIGHT -> "right"
        KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_BUTTON_A -> "a"
        KeyEvent.KEYCODE_BUTTON_B, KeyEvent.KEYCODE_BACK -> "b"
        KeyEvent.KEYCODE_BUTTON_X -> "x"
        KeyEvent.KEYCODE_BUTTON_Y -> "y"
        KeyEvent.KEYCODE_BUTTON_L1 -> "l"
        KeyEvent.KEYCODE_BUTTON_R1 -> "r"
        KeyEvent.KEYCODE_BUTTON_L2 -> "l2"
        KeyEvent.KEYCODE_BUTTON_R2 -> "r2"
        KeyEvent.KEYCODE_BUTTON_SELECT -> "select"
        KeyEvent.KEYCODE_BUTTON_START -> "start"
        else -> null
    }

    /** true = consumed. */
    fun onKey(from: AtlasWebActivity, event: KeyEvent): Boolean {
        if (!isReady(from)) return false
        val key = keyName(event.keyCode) ?: return false
        // the back key of the system bar / gesture is not a controller: only take it from a game controller
        if (event.keyCode == KeyEvent.KEYCODE_BACK && (event.source and InputDevice.SOURCE_GAMEPAD) != InputDevice.SOURCE_GAMEPAD
            && (event.source and InputDevice.SOURCE_JOYSTICK) != InputDevice.SOURCE_JOYSTICK) return false
        if (event.action == KeyEvent.ACTION_DOWN) send(from, key, event.repeatCount > 0)
        return true
    }

    // analog stick and hat switch: edge + repeat (380 ms, then every 110 ms)
    private var stickDir: String? = null
    private var stickFrom: AtlasWebActivity? = null
    private val repeat = object : Runnable {
        override fun run() {
            val d = stickDir ?: return
            stickFrom?.let { send(it, d, true) }
            main.postDelayed(this, 110)
        }
    }

    fun onMotion(from: AtlasWebActivity, ev: MotionEvent): Boolean {
        if (!isReady(from)) return false
        if ((ev.source and InputDevice.SOURCE_JOYSTICK) != InputDevice.SOURCE_JOYSTICK || ev.action != MotionEvent.ACTION_MOVE) return false
        val hx = ev.getAxisValue(MotionEvent.AXIS_HAT_X)
        val hy = ev.getAxisValue(MotionEvent.AXIS_HAT_Y)
        val x = if (abs(hx) > 0.5f) hx else ev.getAxisValue(MotionEvent.AXIS_X)
        val y = if (abs(hy) > 0.5f) hy else ev.getAxisValue(MotionEvent.AXIS_Y)
        val dir = when {
            abs(y) >= abs(x) && y < -0.6f -> "up"
            abs(y) >= abs(x) && y > 0.6f -> "down"
            x < -0.6f -> "left"
            x > 0.6f -> "right"
            else -> null
        }
        if (dir != stickDir) {
            main.removeCallbacks(repeat)
            stickDir = dir
            stickFrom = from
            if (dir != null) {
                send(from, dir, false)
                main.postDelayed(repeat, 380)
            }
        }
        return true
    }
}
