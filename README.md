# Handheld Atlas

**Ein Spiel. Alle Wege, es zu spielen.** Spielzentrierte Discovery für Android-Handhelds, gebaut für den **AYN Thor**.

Du suchst ein Spiel, zum Beispiel *Super Metroid*, und siehst nebeneinander, wie es auf dem Handheld läuft:
klassische Emulation, RetroArch-Fork mit Karte auf dem zweiten Bildschirm, nativer Port, Mods, jeweils mit
Screenshots der Variante, Voraussetzungen, Projektlinks und dem neuesten Release.

- **701 Spiele** in Franchises sortiert, davon 41 mit 60 dokumentierten Spielwegen und 542 mit Cover und Originalscreenshots
- **Filter**: Dual Screen · Native Ports · Emulation · Mods · Thor-getestet · KI-Funde · Plattform
- **Für den Thor gemacht**: Querformat, Steuerkreuz/Gamepad-Navigation (A öffnen, B zurück, L1/R1 Bereiche), installierbar als App, offline nutzbar
- **Pflegt sich selbst**: täglicher Watcher plus KI-Agent, ohne manuelle Freigabe

## So hält sich die Datenbank aktuell

| Wer | Wann | Was |
|---|---|---|
| **Watcher** (`scripts/watch.py`, GitHub Action, ohne KI) | täglich | neue Releases/Archivierung aller bekannten Projekte → Reiter „Neu“; neue Kandidaten aus GitHub-Suche, aktiven Forks, Modrinth und Reddit → `data/inbox.json`; fehlende Cover/Screenshots (libretro-thumbnails, Steam, Wikipedia) und Screenshots je Spielweg aus den READMEs der Projekte |
| **Pflege-Agent** (Claude, geplante Aufgabe) | wöchentlich | sortiert die Inbox in Spiele ein, erweitert die Spieleliste um Spiele mit echten Wegen, prüft README-Bilder visuell, ergänzt fehlende Spielweg-Screenshots, korrigiert Franchises; Ablauf in [`CLAUDE.md`](CLAUDE.md) |
| **Du** | wann du willst | „Recherche anfordern“ im Spiel (legt ein GitHub-Issue an, der Agent arbeitet es zuerst ab) oder Claude sagen: „Spielweg X läuft auf dem Thor“ |

Alles landet direkt auf `main` und ist nach dem automatischen Deploy in der App. Jeder Spielweg trägt eine Prüfstufe:
**Auf dem AYN Thor getestet** · **Community-Erfahrung** · **Laut Projektdoku** · **KI-Fund, ungeprüft**.

## Einrichtung (einmalig)

1. **GitHub Pages aktivieren:** Repository → Settings → Pages → *Source: GitHub Actions*.
   Hinweis: Mit GitHub Free funktioniert Pages nur für **öffentliche** Repositories; für ein privates Repo braucht es GitHub Pro.
   Die Website selbst ist in beiden Fällen öffentlich erreichbar (sie enthält nur öffentliche Links).
2. Actions → **Deploy app** → *Run workflow*. Danach läuft die App unter `https://markusklier.github.io/handheld-atlas/`.
3. Auf dem Thor die Adresse in Chrome öffnen → Menü → **Zum Startbildschirm hinzufügen**.

Ohne Pages: `dist/Handheld-Atlas-offline.html` (aus dem Build oder in der App unter Info) enthält alle Daten in einer Datei.

## Aufbau

```
app/                 Web-App (HTML/CSS/JS, kein Framework)
data/games/*.json    ein Spiel pro Datei, inklusive Spielwege, Mods, Screenshots
data/projects.json   Emulatoren, Ports, Launcher, Mods – mit GitHub-Repo, damit der Watcher Releases findet
data/platforms.json  allgemeine Emulatoren je Plattform
data/inbox.json      unsortierte Funde für den Agenten
data/changelog.json  Reiter „Neu“
scripts/atlas.py     validate · build · stats · format
scripts/watch.py     Watcher
scripts/covers.py    Cover/Screenshots aus libretro-thumbnails
scripts/media.py     Spielweg-Screenshots (Projekt-READMEs), Steam, Wikipedia
```

```sh
python3 scripts/atlas.py validate      # Datenprüfung
python3 -m unittest discover -s tests  # Tests
python3 scripts/atlas.py build         # → dist/
python3 -m http.server -d dist 8000    # http://localhost:8000
```

Nur Python-Standardbibliothek, keine Abhängigkeiten.

## Grenzen

Atlas installiert nichts, startet keine Spiele und verlinkt keine ROMs, ISOs oder Spieldaten. „KI-Fund“ und
„Laut Projektdoku“ sind keine Gerätetests. Bilder werden verlinkt, nicht kopiert; Rechte liegen bei den jeweiligen Urhebern.
Quellcode: MIT (`LICENSE`).
