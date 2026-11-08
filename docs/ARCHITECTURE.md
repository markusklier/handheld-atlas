# Technischer Zuschnitt

## 1. Browser zuerst

Die Discovery braucht Recherche, Filter, Beziehungen und nachvollziehbare
Quellen. Dafuer ist ein statischer, lokal-first PWA-Client ausreichend.
Kein Login, keine Datenbankinstallation, kein Framework-Build und keine
laufende KI-Abfrage sind fuer den ersten Nutzertest erforderlich.

Runtime: semantisches HTML, CSS, JavaScript. Build/Updater: Python-Standardbibliothek.
Tests: Node-Test-Runner, Python unittest; Playwright nur fuer optionale UI-QA.
Das Datenmodell ist unabhaengig vom Frontend und spaeter in Kotlin/Compose,
Capacitor oder einer anderen mobilen Umsetzung weiterverwendbar.

## 2. Fachliches Modell

Franchise -> Spiel -> mehrere Spielwege.
Jeder Spielweg hat Edition, technische Art, Runtime, Plattformarchitektur,
Features, Voraussetzungen, Versionsbindung, Aufwand und Provenienz.
Ein dokumentierter Weg ist NICHT gleichbedeutend mit einem Hardwaretest.
Ein DS-Spiel mit zwei emulierten Bildschirmen ist NICHT automatisch fuer
zwei physische Android-Displays eingerichtet.

Aktuell sind Editionen, Runtimes und Anforderungen noch eingebettete Felder,
kein vollstaendiger relationaler Abhaengigkeitsgraph. Fuer mehr als ca. einige
Hundert Varianten: eigene IDs fuer Edition, Projekt, Release, Runtime,
Requirement, DeviceProfile, TestReport und Asset einfuehren. Der Nutzer startet
weiter beim Spiel, nicht beim technischen Objekt.

Benchmarks brauchen mindestens:
Geraetemodell/RAM, OS/Firmware, Spiel-Build und Store-Ausgabe, Runtime/Version,
Treiber, Grafiksettings/Aufloesung, Leistungsprofil, Testszene, Dauer, thermischen
Zustand, Durchschnitts-FPS, Frametimes/Perzentile und Herkunft. Ohne Vergleichbarkeit
kein algorithmischer Gewinner und keine Kaufempfehlung.

## 3. Zustandsgrenzen

catalog.json: bewusst freigegebene redaktionelle Aussagen.
updates.json: beobachtete technische Fakten, keine Spielbarkeitserklaerung.
candidates.json: neue Links/Dokumente mit Status pending/rejected/reviewed;
keine Ausfuehrung, keine automatische Katalogaufnahme.
localStorage: nur Merkliste, Profil und Checklisten. Import ist begrenzt und
auf bekannte IDs und Feature-Keys reduziert. Kein ROM-/Spielstandupload.

Ein Feature-Watch reagiert nur auf ein feature_added-Ereignis mit reviewed=true
und passender gameId oder Projektbeziehung. Ein generischer Release erfuellt
kein Interesse wie 'Dual-Screen verfuegbar' oder '60 FPS gemessen'.

## 4. App-Pfad

Phase 1: HTTPS-PWA fuer Browser und Startbildschirm.
Phase 2: Backend fuer freigegebene Bilder, Konten optional, Testberichte und Push.
Phase 3: native Android-Integrationen fuer Intents, Datei-Auswahl und
gezielte Paketerkennung. Keine unbeschraenkte App-Inventarisierung versprechen.
Phase 4: Mac-/Windows-ADB-Companion fuer Diagnose und sichere Setup-Rezepte.

Die PWA ist keine Home-App und kein Android-Package-Installer. Ihre Aufnahme in
andere Launcher haengt vom jeweiligen Launcher und der PWA-Installation ab.

## 5. Spaeterer ADB-Companion (nicht implementiert)

Trenne den lesenden Discovery-Client strikt vom privilegierten Executor:

- Discovery exportiert eine versionsgebundene Plan-ID, keine Shellbefehle.
- Desktop-Companion prueft Geraet, Installationen und Dateihashes lokal.
- Vor jeder Mutation: lesbarer Plan, Rechteumfang, Backup und ausdrueckliche
  Bestaetigung. Kein Root, Unlock, Firmwareflash oder OS-Wechsel als Standard.
- Downloadquellen auf Allowlist; Hash und APK-Signatur pruefen, Paketnamen und
  Upgraderegeln abgleichen. Keine Ausfuehrung fremder README-Befehle durch ein LLM.
- Jeder Schritt ist idempotent, protokolliert und soweit moeglich ruecksetzbar.
  Android-App-Downgrades und private App-Daten sind nicht generell reversibel.
- Fehlerdiagnose redigiert Logs und verarbeitet lokal, solange kein ausdruecklicher
  Upload vereinbart ist. LLM-Ausgaben schlagen Schritte vor, autorisieren sie nicht.

Das hier exportierte JSON ist ausschliesslich eine readOnly-Vorbereitung.
Es ist absichtlich noch kein sicherheitsgeprueftes ausfuehrbares Rezeptformat.
