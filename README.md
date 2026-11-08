# Handheld Atlas 0.3 – Datenqualität und Recherche

**Spielzentrierte Discovery für AYN Thor, Android- und offene Handheld-Plattformen. 8. November 2026.**

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
