# Handheld Atlas 0.4 – automatische Entdeckung, optional KI & Vision

## Version 0.4.1 – automatische HTML-Schnappschüsse und Quellenbilder

- **Eine heruntergeladene `Handheld-Atlas.html` aktualisiert sich nicht selbst.** Der Quellenworkflow speichert aber jetzt den neu gebauten HTML-Schnappschuss mit den aktualisierten Daten im privaten Repository. Danach die Datei erneut herunterladen.
- **Gehostete PWA:** Die Schaltfläche „Veröffentlichte Release-Daten laden“ lädt nun die Projektliste und Release-Informationen vom selben Server. Für echte automatische Updates benötigt Atlas eine HTTPS-Website; die Offline-Datei genügt dafür nicht.
- **Mehr Quellbilder:** `scripts/enrich_media.py` durchsucht offizielle Modrinth-Galerien, GitHub-README-Bilder und Screenshot-Verzeichnisse mit begrenztem Abfragebudget; die Modrinth-Suche nimmt ihre Originalgalerie direkt mit.
- Neue Bilder bleiben **ungeprüfte Projektbilder mit Quellenverweis**. Keine Behauptung von Thor-Kompatibilität, exaktem Spiel-Build oder Nutzungsfreigabe. Sie werden nicht in dieses Repository gespiegelt.
- **Privater Test:** GitHub → Actions → erfolgreichen Checks-/Discovery-Lauf → Artefakt `handheld-atlas-preview` herunterladen oder `Handheld-Atlas.html` aus dem Repository herunterladen. GitHub Pages ist ohne gesonderte Zugriffskontrolle nicht als private Website geeignet.


**Spielzentrierte Discovery für AYN Thor, Android- und offene Handheld-Plattformen. 8. November 2026.**


## Version 0.4 – automatisierter, quellenbelegter Projekt-Radar

- Projektzentrierter Index `data/projects.json`: ein Projekt kann mit mehreren Spielen und Spielwegen verbunden sein. Automatische Funde erscheinen im Reiter **Aktuelles** mit explizitem Status **nicht getestet**, nicht als bestätigte Installationswege.
- Neue Kandidaten erhalten Quellenangaben und soweit vorhanden direkt zugehörige Bildkandidaten. **KI-Visionsprüfung ist nur Plausibilität; Bildrechte und genaue Version sind damit nicht geklärt.** Bestehende 77 dokumentierte Eden-Duo-Fotos bleiben den konkreten Varianten zugeordnet.
- `scripts/deep_research.py --batch` rotiert auch durch die Titel des breiteren Watchlist-Indexes. Minecraft ist im Workflow kein hart codierter Sonderlauf mehr. Suchabdeckung kann trotzdem nicht als vollständig gelten.
- `scripts/ai_agents.py --research` und `--vision` nutzen optional die OpenAI Responses API mit Websuche und Bild-Eingaben. **Ohne `OPENAI_API_KEY` werden keine API-Aufrufe ausgeführt**. Die Recherche ist begrenzt auf einen Titel pro Durchlauf, Vision auf höchstens zwei Bilder im Standardworkflow. `docs/V4-OPERATIONS.md` erklärt Kosten-, Datenschutz- und Sicherheitsgrenzen.
- `.github/workflows/update-sources.yml` aktualisiert nur strukturierte Daten automatisch auf dem Hauptbranch; du musst keine inhaltlichen PRs freigeben. Im privaten Repository gibt es außerdem ein herunterladbares ZIP des Browser-Builds als GitHub-Actions-Artefakt.

**Erster Start:** GitHub Actions → **Checks** → Run workflow. Wenn der Build grün ist, kannst du die ZIP-Datei `handheld-atlas-preview` herunterladen und lokal per `python3 -m http.server` ausprobieren. Danach **Automated Atlas discovery** → Run workflow. **Pages-Deploy ist standardmäßig deaktiviert**, solange die Actions-Variable `ATLAS_ENABLE_PAGES=true` nicht gesetzt ist. Für kostenpflichtige Recherche die Option `run_ai` nur nach eigener API-Freigabe aktivieren. Einrichtung: [docs/V4-OPERATIONS.md](docs/V4-OPERATIONS.md).

**Wichtige Grenze:** Live-APIs und Modellabrechnung konnten in der lokalen Entwicklungsumgebung mangels Netzwerk/API-Schlüssel noch nicht end-to-end geprüft werden. Veröffentlichte Spielwege sind nicht automatisch Geräte-Benchmarks; die KI führt keine Installation und kein Debugging auf deinem Thor durch.

---

## Schnellstart

- **Browser ohne Installation:** `Handheld-Atlas.html` öffnen. Externe Originalscreenshots benötigen eine Internetverbindung.
- **PWA-Entwicklung:** `python3 scripts/serve.py` starten, `http://localhost:8765` öffnen. Die PWA wird erst nach HTTPS-Hosting auf einem Android-Handheld installierbar.
- **Recherche lesen:** Minecraft öffnen → Reiter **Recherche-Stand**. Dort sind die Funde als **Offline-Demo**, nicht als Live-Befunde, markiert.
- **Vollständiger technischer Plan:** [`docs/DEEP-RESEARCH.md`](docs/DEEP-RESEARCH.md).

## Was neu ist

- Minecraft **DroidBridge Launcher** und **DroidBridge + Dual Screen HUD** als zwei separate dokumentierte Spielwege, neben Bedrock, ExoJosh, Abacus, Zalith und Amethyst. Versions- und Modloader-Konflikte sind explizit beschrieben; keine Hardware-Benchmarks erfunden.
- Datenmodell bleibt getrennt: **374 suchbare Spiele** (41 kuratierte Spiele + 333 Index-/Watchlist-Titel) und **60 dokumentierte Spielwege**. Eine Suchindex-Karte ist kein Kompatibilitätsnachweis.
- **Screenshot-Verknüpfung unverändert:** 77 bereits in v0.2 zugeordnete Quellbilder von Eden-Duo-Companions. Bei neuen DroidBridge-Spielwegen sind noch keine sicher zugeordneten Bilder eingebunden; originaler CurseForge-Galerielink statt falscher Screenshots.
- GitHub-, Modrinth- und optional CurseForge-Recherche pro Spiel in `scripts/deep_research.py`; mit URL-Deduplikation, Quellenverweisen, Versions-/Loader-Hinweisen und Reviewstatus.
- `data/research_queue.json` enthält zur Demonstration nur **synthetische Test-API-Antworten auf Grundlage bekannter Projekte**. **Kein Live-Abgleich**. Recherchequeue und veröffentlichte Spielwege sind getrennt.
- `scripts/quality_audit.py` zeigt Datenlücken, `scripts/triage_media.py` führt unbestätigte Bildkandidaten zusammen, `scripts/validate_agent_findings.py` validiert optionales KI-JSON, ohne selbst ein Modell aufzurufen.
- `.github/workflows/update-sources.yml` schlägt wöchentlich Deep-Research-Ergebnisse und zweimal täglich andere Quelländerungen per Pull Request vor; startet erst nach Hosting in einem Repository. Ein aktiv laufender Agent, echte KI-Vision oder Push-Benachrichtigungen sind **nicht** enthalten.

## Recherche lokal reproduzieren

```sh
python3 scripts/deep_research.py --game minecraft --fixture fixtures/minecraft_research.json --leads fixtures/minecraft_leads.json --budget 8
python3 scripts/triage_media.py
python3 scripts/quality_audit.py
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/core.test.cjs
python3 scripts/build.py
```

## Eigene echte API-Recherche

```sh
# GITHUB_TOKEN ist sinnvoll (optional), CURSEFORGE_API_KEY nur mit API-Genehmigung.
python3 scripts/deep_research.py --game minecraft --live --budget 9
python3 scripts/deep_research.py --batch 3 --live --budget 4
```

Diese Befehle setzen erreichbares Internet voraus und wurden in dieser Umgebung **nicht erfolgreich live ausgeführt** (externe DNS-Auflösung nicht verfügbar). Die vorhandenen Test-API-Antworten sind als Fixture gekennzeichnet; ein Live-Lauf entfernt die Demo-Kandidaten aus der Recherchequeue.

Keine ROMs, APKs, privaten Spieldaten oder Screenshots werden kopiert oder installiert. Bilder müssen gesondert nach Spielweg, tatsächlicher Darstellung und Rechten geprüft werden. Allgemeine Projekt-READMEs oder KI-Ausgaben sind kein Beleg für reale Thor-Kompatibilität.

Quellcode MIT (`LICENSE`); bei fremden Metadaten, Medien, Markenzeichen und Projektdateien gelten die Rechte der jeweiligen Urheber. Für das rechtssichere Einbinden von Reddit-, CurseForge- und anderen Community-Daten müssen deren Nutzungsbedingungen eingehalten werden.
