# Atlas-App und Setup-Assistent

Ziel: Ein neuer Handheld kommt an → Atlas zeigt, was es gibt → du entscheidest dich für einen Spielweg → Atlas
richtet ihn ein und sorgt dafür, dass er **gut läuft**, nicht nur, dass er installiert ist. Du stellst nur die ROM
bereit bzw. kaufst das Spiel.

Erste Fassung (10.11.2026): **nur AYN Thor Max (16 GB / 1 TB)**. Alles hier ist im Test-Browser mit nachgebildeter
App und mit Unit-Tests geprüft, die APK baut in GitHub Actions – **auf dem Thor selbst ist noch nichts getestet**.
Der eingebaute Selbsttest (unten) ist dafür da, genau das beim ersten Start herauszufinden und zurückzumelden.

## Was die erste Fassung kann – und was noch nicht

| Schritt | Stand |
|---|---|
| Atlas als App, auf beiden Bildschirmen (Hauptbildschirm bedient, der andere zeigt Vorschau, Bilder, Live-Werte) | fertig, im Simulator geprüft, ungetestet auf dem Gerät |
| Gerät erkennen (Chip, RAM, Bildschirme), installierte Apps und Versionen | fertig |
| Apps installieren: GitHub-Release laden und installieren, mit Shizuku ohne Android-Nachfrage | fertig |
| Play-Store-Apps, Download-Seiten | Atlas öffnet die richtige Seite, installieren musst du dort |
| Startkonfiguration je Spiel aus Berichten (Thor Max zuerst, dann gleicher Chip) | fertig |
| App starten (auf dem großen Bildschirm) | fertig; **direkt ins Spiel** (ROM-Start) kommt als Nächstes |
| Messfahrt: Bildrate, 1 %-Low, Bildzeiten, Ruckler, Temperatur, Verbrauch | fertig, braucht Shizuku |
| Auswertung mit festen Abbruchregeln („nicht verrennen“) | fertig |
| KI-Feintuning: schlägt die eine nächste Änderung vor (mit Websuche, eigener OpenAI-Schlüssel) | fertig |
| Einstellungen **automatisch** in die App schreiben | noch nicht – du stellst sie von Hand ein, die Liste bleibt unten stehen |
| ROM/BIOS erkennen (Ordner wählen, Prüfsummen) | noch nicht – Abhaken von Hand |
| Atlas probiert Konfigurationen ganz allein (Testszene, virtuelles Gamepad) | noch nicht – hängt am Selbsttest |
| Rückmeldung der Messfahrten in die Datenbank | fertig (Issue `setup-report:`) |

## Installieren

1. Auf dem Thor im Browser öffnen: `https://github.com/markusklier/handheld-atlas/releases/latest/download/handheld-atlas.apk`
   (oder in Atlas: Info → „Atlas-App mit Setup-Assistent“ → APK laden). Datei öffnen; Android fragt einmal, ob der
   Browser Apps installieren darf.
2. Updates: in **Obtainium** „App hinzufügen“ → `https://github.com/markusklier/handheld-atlas`. Die App meldet neue
   Versionen außerdem selbst (Info → Atlas-App) und kann sich selbst aktualisieren.
3. **Shizuku** (empfohlen, für Messen und lautloses Installieren): Info → Atlas-App → „Shizuku installieren“, dann
   der Anleitung dort folgen (WLAN-Debugging koppeln, „Starten“, „Atlas freigeben“). Nach jedem Neustart des Geräts
   muss Shizuku einmal neu gestartet werden; Atlas zeigt das an.
4. Info → Atlas-App → **Selbsttest starten**. Das Ergebnis geht automatisch an die Datenbank (wenn der
   GitHub-Schlüssel unter Info eingetragen ist, sonst „als Issue senden“).

**Signatur:** Die APK ist mit einem Vorab-Schlüssel signiert, der offen im Repository liegt
(`android/atlas-dev.keystore`), weil die Sitzung, die die App gebaut hat, keine Repository-Secrets anlegen konnte.
Folge: Jeder könnte eine APK bauen, die Android als Update von Atlas annimmt – gefährlich nur, wenn man eine
Atlas-APK aus fremder Quelle installiert. Für einen eigenen Schlüssel: Keystore als Base64 in das Secret
`ATLAS_KEYSTORE_B64` und das Passwort in `ATLAS_KEYSTORE_PASSWORD` legen (Alias `atlas`); der Workflow nimmt ihn
dann automatisch. Danach muss die App einmal neu installiert werden (andere Signatur).

## So läuft „Einrichten“

Jeder Spielweg hat auf der Spielseite den Knopf **Einrichten** – auch allgemeine Emulatoren und Wege, die Atlas
nicht empfiehlt. Der Nutzer entscheidet; der Assistent sagt nur ehrlich, was die Berichte erwarten lassen.

1. **Gerät** – erkannt oder von dir bestätigt; Hinweis, wenn Shizuku fehlt.
2. **App(s) installieren** – aus `data/setup/apps.json` oder direkt aus dem GitHub-Release des Projekts. Gibt es
   mehrere passende Apps (z. B. Eden und Eden Duo), wählst du.
3. **Deine Dateien** – was du selbst besitzen musst (`requires` des Wegs). Atlas lädt nie Spieldateien.
4. **Einstellungen** – Startpunkt: zuerst eigene Messfahrten vom Thor Max, dann Berichte vom Thor Max, dann vom
   Thor Pro/Base, dann von anderen Geräten mit demselben Chip; jeweils die der gewählten App. Unterschiede zur
   vorigen Runde sind markiert.
5. **Spielen und messen** – „Messfahrt starten“: Atlas öffnet die App, du lädst das Spiel und spielst 2,5 Minuten
   an einer typischen Stelle. Unten laufen Bildrate, Restzeit und Temperatur mit.
6. **Ergebnis und Feintuning** – Kennzahlen, dein Urteil (Ton und Steuerung kann keine Messung beurteilen), dann:
   KI-Feintuning, eine andere Konfiguration aus den Berichten, oder „Fertig – so lasse ich es“.

### Regeln fürs Feintuning (`data/setup/policy.json`)

- Ziel ist das Originaltempo des Spiels (30 oder 60), nicht „so viel wie möglich“.
- Erst Abstürze/Grafikfehler, dann gleichmäßige Bildzeiten, dann Auflösung und Extras.
- Pro Runde eine Änderung, danach neu messen.
- **Aufhören**, wenn das Ziel erreicht ist (Ø ≥ 97 %, 1 %-Low ≥ 85 % der Zielrate), wenn zwei Runden in Folge
  weniger als 3 FPS bzw. 5 % bringen, spätestens nach 6 Runden.
- **Hardware-Grenze:** bleibt es deutlich unter dem Ziel, lieber ein festes niedrigeres Limit (z. B. 30 bei
  gemessenen 35) als weiter optimieren – und einen besseren Weg nennen.
- Hitze zählt (Drosselung, Gehäuse über 45 °C).
- **Kosten:** keine feste Obergrenze je Spielweg; Hinweis ab 5 €, Halt bei 10 €, bis du ausdrücklich weitermachst.
  Dafür unter Info → Atlas-App den Preis deines Modells je 1 Mio. Tokens eintragen; ohne Preis zeigt Atlas nur Tokens.

Das KI-Feintuning läuft auf dem Gerät mit deinem OpenAI-Schlüssel (wie die Sofortanalyse). Es bekommt Gerät, Spiel,
Weg, App-Version, alle bisherigen Runden mit Messwerten, die Berichte anderer Nutzer, die anderen Wege und die
Regeln – und antwortet mit genau einem nächsten Schritt (`change`, `done`, `lower-target`, `other-way`).

## Zwei Bildschirme (`app/dual.js`, `InputRouter.kt`)

Dritte Fassung (12.11.2026). Grundsatz: **ein Hauptbildschirm, ein Begleiter** – nie zwei gleichberechtigte Fenster.

- **Hauptbildschirm** (standardmäßig oben, größerer Bildschirm): die ganze App, genau wie auf einem Bildschirm.
  **Nur hier wird bedient** – Controller, Fokus, Verlauf, Scroll-Position. Listen, Spielseite, Einrichten: alles hier.
- **Begleiter** (standardmäßig unten): zeigt, was zum Hauptbildschirm passt, und sonst nichts.
  - Liste oben, Spiel markiert (Controller-Fokus oder Finger auf der Karte) → **Vorschau**: Bilder groß zum Durchwischen
    (Dual-Screen-Bilder zuerst), kleine Bilder zum Antippen, Cover, Reihe und Jahr, Plattformen, Dual-Screen-Art,
    Empfehlung und **„Spiel ansehen“** (öffnet die Spielseite auf dem Hauptbildschirm).
  - Spielseite oben → **Bilder**: Galerie des Spiels; der Spielweg, der oben gerade offen oder im Fokus ist, kommt
    zuerst. Darunter die Wege als Knöpfe – antippen öffnet den Weg oben.
  - Einrichten oben → Bilder des Weges; während einer **Messfahrt** die Live-Werte groß (FPS, Restzeit, Temperatur).
  - Noch nichts markiert → Begrüßung mit Dual-Screen-Spielen zum Antippen.
  - Der Begleiter hat keinen eigenen Verlauf, keinen Fokus und bekommt keine Controller-Taste. Antippen wirkt als
    Fernbedienung. Dadurch kann es weder zwei offene Spiele noch zwei bediente Bildschirme geben.
- **Controller:** alles wie gewohnt auf dem Hauptbildschirm; **L2/R2** blättern die Bilder des Begleiters,
  **Select** tauscht die Bildschirme. Bilder auf dem Begleiter per Finger: wischen, aufs Bild tippen (linkes Drittel
  zurück, sonst weiter), Pfeile, kleine Bilder. Die Bilder wechseln alle 6 s von selbst, nach dem Anfassen 25 s Pause.
- **Tauschen** und **Dual Screen an/aus** stehen auf beiden Bildschirmen (Kopfzeile bzw. Leiste des Begleiters).
  Getauscht ist der kleine Bildschirm der Hauptbildschirm, der große zeigt Vorschau/Bilder im Querformat (Bilder links,
  Spiel rechts). Der neue Hauptbildschirm übernimmt Verlauf (B führt weiter zurück), Filter, Scroll-Position und Fokus.
  Aus = ein Bildschirm wie auf jedem anderen Handheld, an derselben Stelle.
- Geräte mit einem Bildschirm (z. B. Odin) sehen keinen Schalter; alles läuft in einem Fenster.

Technik:
- **Rollen:** `single` (ein Bildschirm), `primary`, `companion`. Die App vergibt `screen=companion` an das Fenster auf dem
  kleinsten Display; getauscht (`dualSwap`) ist es umgekehrt. `route()` fragt zuerst `dualCompanion()` – der Begleiter
  rendert nie eine Seite der App, sondern `cpHTML(D.show)`.
- **Ein Zustand, eine Richtung:** Der Hauptbildschirm leitet aus Seite und Fokus ab, was der Begleiter zeigen soll
  (`dualWant()` → `{v: 'preview'|'game'|'setup', game, way}`), und schickt es bei jeder Änderung vollständig
  (`dualPublish`). Der Begleiter meldet sich nach dem Laden mit `hello` und bekommt den aktuellen Stand.
- **Nachrichten** gehen doppelt (Brücke `relay` und `BroadcastChannel`, mit Kennung gegen Doppelte). Wichtig: Was das
  andere Fenster sofort wissen muss (getauscht?, Stand des Hauptbildschirms), reist **in der Nachricht** mit –
  `localStorage` kommt im anderen WebView verzögert an (das war ein echter Fehler beim Tauschen).
- **Übergabe** (`savePrimary` → `takeOver`): Verlauf (`trail`, wird per `history.pushState` nachgebaut), Filter, Scroll,
  Fokus. Bei Dual an/aus zusätzlich mit Zeitstempel (`handoff`), damit auch ein frisch geladenes Fenster übernimmt.
- **Controller** (`InputRouter.kt`): Android schickt Tasten an das zuletzt berührte Fenster, und die Gamepad-API beider
  WebViews sieht jeden Knopf – deshalb reagierten früher beide Bildschirme. Die App fängt alle Controller-Tasten ab
  (`dispatchKeyEvent`/`dispatchGenericMotionEvent`: Steuerkreuz, Stick mit Wiederholung, L2/R2 auch als Analog-Trigger)
  und schickt sie als Ereignis `input` an das Fenster, dessen Seite sich mit `input {role: 'primary'}` angemeldet hat.
  Die Zurück-Geste kommt als Taste `back` beim Hauptbildschirm an (auf der Startseite: `leave`).
  Ältere Apps: 0.1.10 kennt `inputReady`/`setInput` (wird weiter bedient), noch ältere haben keine Verteilung – dann
  liest **nur der Hauptbildschirm** die Gamepad-API (`padsAllowed`), und Tasten, die im Begleiter-Fenster landen, reicht
  dieser weiter. In der Seite verarbeitet `padInput(key)` (app.js) alles.
- `second {open}` öffnet/schließt das zweite Fenster und merkt sich die Wahl; `focusSelf` holt das eigene Fenster nach vorn
  (Tastatur für die Suche). Thor: oben 1920×1080, unten 1240×1080; die CSS-Größe hängt von der Bildschirmdichte ab
  (unbekannt, solange kein Selbsttest zurückkam) – das Layout ist für 413×360 bis 620×540 (unten) geprüft.
- **Simulator** (`scripts/dualsim.mjs`): zwei Browser-Seiten in einem Profil mit nachgebauter Brücke – so lässt sich
  Dual Screen ohne Gerät durchspielen und ansehen. `node scripts/dualsim.mjs tour|vorschau|einrichten|stress`
  (`--density=2.25`, `--apk=7|10|11` für ältere Apps, `--seed`, `--steps`). **Vor jeder Änderung an dual.js den
  Stresstest laufen lassen** – er prüft nach jedem Schritt: genau ein Hauptbildschirm, der Begleiter zeigt keine eigene
  Seite und passt zum Spiel oben.
- **Update der App:** Die Prüfung nimmt das Release mit der höchsten Nummer (GitHub listet nicht in Versionsreihenfolge;
  bis 11.11. wurde deshalb 0.1.10 nie angeboten) und zeigt „Installieren“ direkt im Hinweis.

## Emulator wählen

Jeder Emulator einer Fassung ist ein eigener Weg (z. B. für PC: GameNative, Winlator, GameHub, DroidDeck). Atlas sortiert
sie nach Berichten von Geräten mit dem Thor-Chip, eigenen Messfahrten und dem, was schon installiert ist, und markiert
den besten als „beste Wahl“. Atlas merkt sich keinen Favoriten. Im Setup-Assistenten steht oben die Emulator-Wahl:
Empfehlung markiert, ein Tipp auf einen anderen richtet diesen ein.

## Messfahrt: was gemessen wird

Über Shizuku (Shell-Rechte, kein Root) liest die App zweimal pro Sekunde die Bildzeitpunkte der Spieloberfläche:
`dumpsys SurfaceFlinger --list` (Ebene des Spiels finden) und `dumpsys SurfaceFlinger --latency <Ebene>`.
Daraus: Ø Bilder pro Sekunde, 1 %-Low (Mittel der langsamsten 1 % der Bilder), Bildzeiten (50/95/99 %, Maximum),
Ruckler (Bilder, die mehr als 2,5-mal so lange dauern wie üblich und über 25 ms), Verlauf je Sekunde.
Dazu alle 5 Sekunden Temperaturen (`dumpsys thermalservice`: CPU, GPU, Gehäuse, Drosselstufe) und der Verbrauch
aus der Akku-Anzeige (nur ohne Netzteil aussagekräftig). Die Messung läuft als Vordergrunddienst mit
Benachrichtigung („Messung beenden“) und endet von selbst nach der Messzeit oder wenn das Spiel 30 s keine Bilder liefert.

## Aufbau

```
android/                      Kotlin-App (eine APK): WebView + native Brücke
  Screens.kt                  Fenster und Bildschirme, Rollen main/companion, Spielbildschirm
  AtlasWebActivity.kt         Fenster mit der Atlas-Seite; MainActivity (Start), SecondActivity (zweiter Bildschirm)
  Bridge.kt                   „AtlasBridge“: feste Funktionen für die Seite, Ereignisse zurück
  Shell.kt                    Shizuku: Shell-Dienst (IShellService.aidl), Rechte, Zustand
  Installer.kt                APK aus GitHub-Release laden, bestätigen lassen, installieren
  Measure.kt                  Bildzeiten, Temperaturen, Verbrauch; Vordergrunddienst der Messfahrt
  SelfTest.kt                 prüft auf dem Gerät, was wirklich geht
  Reddit.kt                   Reddit-Beitrag mit der Anmeldung des Nutzers lesen (docs/REDDIT.md)
app/setup.js                  der Assistent in der Atlas-Oberfläche (Checkliste, Messfahrt, Feintuning, zwei Bildschirme)
app/app.js → native           Brücken-Client (native.call / native.on); im Browser ist native.available false
scripts/setup.py              Setup-Daten prüfen, bündeln, Rückmeldungen übernehmen
data/setup/                   devices.json, apps.json, policy.json, runs/<spiel>.json, selftest.json, learned.json
.github/workflows/android.yml baut die APK bei Änderungen an android/ und veröffentlicht sie als Release app-v0.1.<n>
```

Die App lädt die Oberfläche von `https://markusklier.github.io/handheld-atlas/` – neue Daten und Verbesserungen am
Assistenten kommen also ohne App-Update. Offline zeigt sie den zuletzt geladenen Stand (Service Worker).

### Brücke (`AtlasBridge`)

Die Seite schickt `{"id","method","params"}`, die App antwortet `{"id","ok","result"|"error"}`; Ereignisse kommen als
`{"event","data"}`. Die Brücke gibt es nur für Seiten von `https://markusklier.github.io/handheld-atlas/`.

| Funktion | Zweck |
|---|---|
| `info` | App-Version, Rolle, Gerät (Modell, Chip, RAM, Android), Bildschirme, Shizuku-Zustand |
| `packages {ids}` | welche Pakete installiert sind (Version) |
| `install {repo, url, name}` | APK aus `github.com/<repo>/releases/download/…` laden und installieren (nach Bestätigung) |
| `launch {package}` | App auf dem großen Bildschirm starten |
| `openUrl {url}` | https- oder Store-Link im Browser/Play Store öffnen |
| `shizuku {action}` | Zustand, Freigabe anfragen, Shizuku öffnen |
| `second {open}` | zweites Fenster ein/aus |
| `relay {…}` | Nachricht an das andere Fenster (z. B. „öffne dieses Spiel“) |
| `measureStart {package, label, seconds, meta}` / `measureStop` / `measureState` | Messfahrt |
| `selftest` | Selbsttest |
| `redditFetch {url}` / `redditLogin` / `redditState` | Reddit mit eigener Anmeldung |

Ereignisse: `measure` (waiting/running/done), `install` (download/installing/done/error/cancelled), `shizuku`,
`reddit`, `relay`, `resume`, `error`.

### Sicherheit

- Die Seite kann **keine Befehle** an die Shell schicken. Jede Funktion tut genau eine feste Sache; Befehle baut nur
  der Kotlin-Code.
- Installiert wird nur aus den GitHub-Releases des genannten Repositories, und **jede** Installation bestätigst du
  in einem Dialog der App (nicht der Seite) – auch mit Shizuku. Ungeprüfte KI-Funde sind im Dialog gekennzeichnet.
- `data/setup/apps.json` ist handverlesen. Die KI-Recherche schreibt dort nicht hinein. Projekte aus
  `projects.json` (auch KI-Funde) können installiert werden, aber immer mit Quelle im Dialog.
- Vertrauensanker ist dieses Repository: Wer hier schreiben darf, bestimmt, was die App anbietet.
- Keine ROMs, kein BIOS, keine Keys, keine Käufe.

## Daten

- `devices.json` – Gerät mit Chip-Klasse (`sd8gen2`), Bildschirmen, Erkennungsregel (`match`) und den Gerätenamen,
  unter denen Berichte zählen (`reportNames`, `familyReportNames`).
- `apps.json` – App mit Paketnamen (aus dem gemeinfreien Obtainium Emulation Pack), Quelle (`github`/`play`/`page`),
  zugehörigen Atlas-Projekten und den Emulatornamen aus Berichten (`reportNames`).
- `runs/<spiel>.json` – Messfahrten vom Gerät, neueste zuerst (höchstens 40): Weg, App und Version, Konfiguration
  (Einstellungen, Änderungen, Quelle), Kennzahlen, Urteil. Das sind Atlas' eigene Performance-Daten; die App zeigt
  sie am Spielweg („Ø 58 FPS“) und nimmt gute Runden als ersten Startpunkt.
- `selftest.json` – letzter Selbsttest je Gerät. **Der Pflege-Agent liest ihn**, bevor er an Messung, virtuellem
  Gamepad oder Konfigurationsdateien weiterbaut (`python3 scripts/setup.py`).
- `learned.json` – Paketnamen, die beim Installieren erkannt wurden (Projekt → Paket).

Rückmeldung vom Gerät (Issue mit Label `recherche`, übernimmt die Action „KI-Recherche“ ohne KI):

````
setup-report: 1

```json
{"kind": "setup-report", "device": "ayn-thor-max", "app": {"version": "0.1.7"}, "at": "2026-11-10T20:27:00Z",
 "runs": [{"game": "kirby-and-the-forgotten-land", "way": "g:nintendo-switch:eden", "wayName": "Eden",
           "version": "nintendo-switch", "app": "Eden", "package": "dev.eden.eden_emulator", "appVersion": "0.0.4",
           "round": 1, "target": 60, "verdict": "good", "note": "",
           "variant": {"label": "AYN Thor Max · Eden 0.2.0-rc2 · Perfekt", "source": "https://www.emuready.com/listings/…",
                       "settings": {"Resolution": "1"}, "changes": []},
           "result": {"seconds": 150.2, "fps": {"avg": 59.6, "low1": 53.1}, "frameMs": {"p50": 16.7, "p95": 19.4, "p99": 22.9, "max": 84.1},
                      "stutters": 4, "refreshHz": 120, "temp": {"skinMax": 41.2, "throttleStatus": 1}, "power": {"avgW": 9.6}}}],
 "packages": {"azahar": "org.azahar_emu.azahar"},
 "selftest": {"at": "…", "info": {…}, "checks": [{"id": "frames", "name": "Bildzeiten messen", "ok": true, "detail": "…"}]}}
```
````

`verdict`: `good` · `ok` · `bad` · `broken` (startet nicht/stürzt ab; dann ohne Messwerte). Messfahrten werden nur
für das unterstützte Gerät gemeldet.

## Entscheidungen von Markus (10.11.2026)

- Eine App, kein separates Setup-Programm; zwei Bildschirme gehören dazu. WebView oder nativ durfte der Agent
  entscheiden → Hybrid (eine Oberfläche für Browser und App).
- Shizuku ja, wenn das Ergebnis besser wird. ADB vom Mac nur für Notfälle, nie als normaler Weg.
- Einzelrezepte je Spiel sind wichtig (dieselbe App läuft mit anderer Konfiguration deutlich besser).
- Der Nutzer wählt den Weg; der Assistent versucht auch nicht empfohlene Wege.
- KI darf für das beste Ergebnis Geld kosten; über 5–10 € je Spielinstallation ist nicht mehr im Verhältnis.
- Nicht verrennen: nicht wegen 3 FPS optimieren und nicht 60 erzwingen, wenn die Hardware 35 hergibt.
- Zuerst nur AYN Thor Max 16 GB / 1 TB.

## Nächste Schritte

1. **Selbsttest vom Thor auswerten** (`data/setup/selftest.json`): Stimmen Erkennung (Modell, Chip-Name), Rollen der
   Bildschirme, Bildzeit-Messung, Temperaturen? Danach die Messung härten.
2. **Direkt ins Spiel:** Ordner mit eigenen Spielen wählen, Datei zum Spiel finden (Name, später Prüfsumme),
   Emulator mit dieser Datei starten (Startbefehle je Emulator wie bei ES-DE).
3. **Einstellungen automatisch schreiben:** je Emulator ein Adapter (Konfigurationsdatei, pro Spiel wo möglich),
   mit Sicherung der alten Datei. Zuerst die Emulatoren mit den meisten Berichten (Eden, GameNative, PPSSPP, Dolphin).
4. **Allein ausprobieren:** Testszene (Speicherstand), virtuelles Gamepad (`uinput`, laut Selbsttest), Screenshot an
   die KI für Grafikfehler – dann fährt Atlas mehrere Konfigurationen ohne dich durch.
5. **Rezepte auf Vorrat:** Die Pflegeaufgabe (Claude, über das Abo) schreibt je Spiel und Chip-Klasse Profile mit
   Quellen; die Messfahrten bestätigen oder korrigieren sie.
6. Weitere Geräte: Thor Pro/Base (gleicher Chip), dann Odin 2, Retroid Pocket 6.

## Für Entwickler

```sh
python3 scripts/setup.py                         # Überblick über Setup-Daten, letzter Selbsttest
python3 -m unittest tests.test_setup             # Daten, Übernahme der Rückmeldung
cd android && ./gradlew :app:assembleRelease     # APK lokal bauen (braucht Android SDK, JDK 17+)
```

Die Oberfläche lässt sich ohne Gerät testen: vor dem Laden ein Objekt `window.AtlasBridge` mit `postMessage(json)`
und `onmessage` bereitstellen, das die Funktionen oben nachbildet.

Quellen: [AYN Thor: Varianten und Specs (Notebookcheck)](https://www.notebookcheck.net/AYN-Thor-dual-screen-handheld-begins-shipping-but-only-the-Snapdragon-8-Gen-2-version.1138344.0.html) ·
[Bildschirme des Thor aus App-Sicht (Kenneth Reitz, Cannoli)](https://kennethreitz.org/essays/2026-07-18-teaching_cannoli_which_screen_is_home) ·
[Obtainium Emulation Pack: Paketnamen](https://github.com/RJNY/Obtainium-Emulation-Pack) ·
[TakoStats: Messen über Shizuku ohne Root](https://androplus.jp/en/entry/takostats-android-fps-app/) ·
[Android: Start auf einem bestimmten Bildschirm](https://source.android.com/docs/core/display/multi_display/activity-launch)
