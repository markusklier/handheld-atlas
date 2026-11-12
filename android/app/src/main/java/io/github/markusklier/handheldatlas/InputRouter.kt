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
 * One controller, two screens: every button press goes to exactly one Atlas window – the main screen.
 *
 * Android delivers key events to the window that has focus (usually the one touched last) and the Gamepad API of
 * both WebViews sees every button – that made both screens react at once. So the activities consume controller keys
 * here and send them as "input" events to the window whose page registered as "primary" (bridge method `input`).
 * The companion window never gets a key. Pages that never registered keep the normal behaviour.
 * (Roles "browse"/"stage" and `target` are the contract of web app versions before the main-screen/companion model.)
 */
object InputRouter {
    private val roles = WeakHashMap<AtlasWebActivity, String>()      // "primary" | "companion" | "single" (old: "browse" | "stage")
    private val ready = WeakHashMap<AtlasWebActivity, Boolean>()
    @Volatile var target = "browse"
        private set
    private val main = Handler(Looper.getMainLooper())

    @Synchronized fun setRole(a: AtlasWebActivity, role: String) { roles[a] = role }
    @Synchronized fun roleOf(a: AtlasWebActivity): String = roles[a] ?: "single"
    @Synchronized fun setReady(a: AtlasWebActivity) { ready[a] = true }
    @Synchronized fun isReady(a: AtlasWebActivity) = ready[a] == true
    @Synchronized fun forget(a: AtlasWebActivity) { roles.remove(a); ready.remove(a) }

    /** [pad]: the switch came from the controller – the new window shows its focus ring right away. */
    fun setTarget(role: String, pad: Boolean = false) {
        target = role
        Screens.emitAll("inputTarget", JSONObject().put("role", role).put("pad", pad))
    }

    @Synchronized private fun windowFor(role: String): AtlasWebActivity? =
        Screens.all().firstOrNull { roles[it] == role && ready[it] == true }

    private val lastSent = HashMap<String, Long>()

    fun send(from: AtlasWebActivity, key: String, repeat: Boolean) {
        // triggers arrive as a key event and as an axis on many controllers: one press, one event
        if (key == "l2" || key == "r2") {
            val now = android.os.SystemClock.uptimeMillis()
            synchronized(lastSent) {
                if (now - (lastSent[key] ?: 0L) < 180) return
                lastSent[key] = now
            }
        }
        val win = windowFor("primary") ?: windowFor(target) ?: from
        win.emit("input", JSONObject().put("key", key).put("repeat", repeat))
    }

    /** Back gesture or back button of the system on any Atlas window. false = the page does not take keys. */
    fun back(from: AtlasWebActivity): Boolean {
        if (!isReady(from)) return false
        send(from, "back", false)
        return true
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
    private var triggerL = false
    private var triggerR = false
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
        // analog triggers (L2/R2) flip the pictures on the companion screen
        val l = maxOf(ev.getAxisValue(MotionEvent.AXIS_LTRIGGER), ev.getAxisValue(MotionEvent.AXIS_BRAKE)) > 0.5f
        val r = maxOf(ev.getAxisValue(MotionEvent.AXIS_RTRIGGER), ev.getAxisValue(MotionEvent.AXIS_GAS)) > 0.5f
        if (l && !triggerL) send(from, "l2", false)
        if (r && !triggerR) send(from, "r2", false)
        triggerL = l
        triggerR = r
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
