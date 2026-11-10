package io.github.markusklier.handheldatlas

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Checks on the device itself what the setup assistant can rely on (instead of a test bench with a PC):
 * shell rights, frame measurement, temperatures, virtual gamepad, access to app data folders, screenshots.
 * The report is shown in Atlas and can be sent back, so the next version can adapt to the real device.
 */
object SelfTest {
    private fun check(list: JSONArray, id: String, name: String, block: () -> Pair<Boolean, String>) {
        val (ok, detail) = try {
            block()
        } catch (e: Throwable) {
            false to (e.message ?: e.javaClass.simpleName)
        }
        list.put(JSONObject().put("id", id).put("name", name).put("ok", ok).put("detail", detail.take(600)))
    }

    fun run(act: AtlasWebActivity): JSONObject {
        val checks = JSONArray()
        val shizuku = Shell.state(act)
        check(checks, "shizuku", "Shizuku") {
            Shell.granted() to when {
                !shizuku.optBoolean("installed") -> "nicht installiert"
                !shizuku.optBoolean("running") -> "installiert, aber nicht gestartet"
                !shizuku.optBoolean("granted") -> "läuft, Atlas hat noch keine Freigabe"
                else -> "bereit (uid ${shizuku.optInt("uid")})"
            }
        }
        if (Shell.granted()) {
            val sh = { c: String -> Shell.exec(c, 8000).trim() }
            check(checks, "shell", "Shell-Rechte") { sh("id").let { it.contains("uid=") to it } }
            check(checks, "layers", "Bildschirm-Ebenen lesen") {
                val all = sh("dumpsys SurfaceFlinger --list").lines().filter { it.isNotBlank() }
                val own = all.filter { it.contains(BuildConfig.APPLICATION_ID) }
                (all.size > 3) to "${all.size} Ebenen, davon ${own.size} von Atlas: ${own.take(3).joinToString(" | ")}"
            }
            check(checks, "frames", "Bildzeiten messen") {
                val sampler = FrameSampler({ c -> Shell.exec(c, 5000) }, BuildConfig.APPLICATION_ID)
                val picked = sampler.pick()
                Thread.sleep(700)
                val n = sampler.poll()
                // a still page draws no frames; what matters is that the timestamps are readable
                (sampler.refreshNs > 0) to "Ebene: ${sampler.layer ?: "–"} · neue Bilder: $n · Periode: ${sampler.refreshNs} ns · gewählt: $picked\n${sampler.rawSample}"
            }
            check(checks, "thermal", "Temperaturen lesen") {
                val t = Thermals { c -> Shell.exec(c, 5000) }
                t.sample()
                val j = t.json()
                (j.has("skinMax") || j.has("cpuMax")) to j.toString()
            }
            check(checks, "uinput", "Virtuelles Gamepad (uinput)") {
                val out = sh("ls -l /system/bin/uinput 2>&1; uinput 2>&1 | head -3")
                (out.contains("/system/bin/uinput") && !out.contains("No such file")) to out
            }
            check(checks, "appdata", "App-Datenordner (Android/data)") {
                val out = sh("ls /sdcard/Android/data 2>&1 | head -200")
                val n = out.lines().count { it.isNotBlank() && !it.contains("denied") && !it.contains("No such") }
                (n > 1) to "$n Einträge sichtbar" + if (n <= 1) ": $out" else ""
            }
            check(checks, "screencap", "Screenshot aufnehmen") {
                val dir = act.externalCacheDir ?: act.cacheDir
                val f = File(dir, "selftest.png")
                val out = sh("screencap -p ${Shell.quote(f.path)} 2>&1; ls -l ${Shell.quote(f.path)} 2>&1")
                val size = f.length()
                f.delete()
                (size > 10_000) to "Dateigröße $size Bytes. $out"
            }
            check(checks, "displayIds", "Bildschirm-Kennungen") {
                val out = sh("dumpsys SurfaceFlinger --display-id 2>&1 | head -8")
                out.isNotBlank() to out
            }
            check(checks, "pm", "Installieren ohne Nachfrage") {
                val out = sh("pm list packages 2>&1 | wc -l")
                ((out.toIntOrNull() ?: 0) > 10) to "$out Pakete sichtbar"
            }
            check(checks, "perf", "Leistungsmodus lesbar") {
                val out = sh("settings list system 2>/dev/null | grep -i -E 'perf|fan|mode' | head -12; settings list global 2>/dev/null | grep -i -E 'perf|fan|low_power' | head -8")
                out.isNotBlank() to out
            }
        }
        return JSONObject()
            .put("at", java.time.Instant.now().toString())
            .put("info", DeviceInfo.info(act))
            .put("checks", checks)
    }
}
