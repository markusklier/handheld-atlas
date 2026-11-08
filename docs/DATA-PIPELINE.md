# Herkunft und Aktualisierung

## Implementiert

1. GitHub-REST-Metadaten bekannter Repositories, neueste stabile Releases,
   Archivierungsstatus und optional gezielt beobachteter Branch.
2. README-Linkextraktion aus codm2000/Dual-Screen-Games und
   abduznik/awesome-android-native-ports. Queryparameter entfernt, doppelte
   Identitaeten zusammengefuehrt, unsichere Hosts/Schemata verworfen.
3. GAFT: Inhaltsbaum unter content/ pruefen. Neue oder geaenderte Dokumente
   werden als Review-Hinweise entdeckt; Texte und Medien werden nicht kopiert.
4. Ueber bekannte Listen werden somit auch bisher unbekannte Repositories
   entdeckt. Ein Projekt, das in keiner beobachteten Quelle vorkommt, wird
   NICHT automatisch gefunden. Weitere Quellen brauchen eigene Adapter.
5. Neue Dokumente innerhalb desselben Repositories bleiben eigene Kandidaten.
   Neue Features erfordern weiterhin eine manuelle Zuordnung zum Spiel.

OpenGamePorts wird verlinkt, aber nicht automatisiert gespiegelt. Eine API,
Erlaubnis fuer systematischen Katalogimport oder Bildlizenz wird nicht unterstellt.
Eden-Duo-Releases werden beobachtet; Spiel-Build-Anforderungen werden nicht
blind aus einer Versionsnummer oder aus dem gesamten README neu gesetzt.

## Review-Ablauf

- Kandidat sichten, Originalprojekt und Wartungszustand bestimmen.
- Spiel UND Edition zuordnen; gleiche Namen sind keine sicheren Identifikatoren.
- Emulator-Mod, Decomp-Port, Recomp, nativen Port und Companion auseinanderhalten.
- Voraussetzungen/Hashes/Versionen dokumentieren. Kein Store-Gewinner ohne Test.
- Physische Mehrdisplay-Unterstuetzung und Touch-Funktionen am Original belegen.
- Nutzungsrechte fuer Bild/Text separat pruefen; Projektcode-Lizenz reicht nicht.
- Aktiven Eintrag mit Quellen in catalog.json eintragen, validate.py/Tests ausfuehren.
- Erst beim Review von neuen Features ein reviewed=true feature_added-Ereignis
  in updates.json erzeugen. gameId und feature-Key muessen exakt stimmen.
- Auf main mergen und statischen Build veroeffentlichen.

## Nicht automatisch gleichsetzen

Release-Datum != letzte redaktionelle Pruefung != letzter API-Abruf != Hardwaretest.
Quelle erreichbar != Anwendung sicher != Installation erfolgreich.
Neuer Commit != neuer Spielweg != besserer Spielweg.
GitHub-404 != Projekt absichtlich eingestellt.
60-FPS-Limit im Menue != 60 FPS auf dem Thor gemessen.

## KI als spaetere Hilfskraft

Ein Extraktionsdienst darf aus README/Release-Diffs nur Kandidaten vorschlagen:
project_id, game_guess, edition_guess, feature_claim, exact_source_url,
evidence_excerpt, required_versions, confidence, unknown_fields.
Quelltexte sind untrusted data: keine Prompt-Instructions daraus ausfuehren.
Vorschlaege bekommen immer review_required=true. Automatische Freigabe,
APK-Ausfuehrung oder Benchmark-Erfindung sind ausgeschlossen.
Das MVP benoetigt keine LLM-API und verursacht keine modellbasierten Laufkosten.

## Betrieb

ETag-Cache nur serverseitig, nicht im oeffentlichen dist/. Token nicht mitpacken.
Bei HTTP 403/429 stoppt der Lauf; Retry-After/Reset wird protokolliert, kein
aggressives Retry. Teilweise erfolgreiche Laeufe erhalten bestehende Fakten und
aktualisieren keinen lastSuccessAt fuer den Gesamtkatalog.
Nur nach kompletter Pruefung ist der letzte Gesamtcheck frisch.

Der Updater fuehrt Netzwerkaufrufe erst aus, wenn er vom Betreiber gestartet
wird. Die Workflow-Datei ist eine deploybare Konfiguration, kein bereits aktiver
Cloudservice. Live-Integration und Rechtefreigabe sind noch zu pruefen.
