# Handheld Atlas 0.3 – Recherche- und Qualitätspipeline

Stand: 2026-11-08 · Status: **funktionierender Offline-Test und vorbereitete Live-API-Adapter**, nicht dauerhaft betriebener öffentlicher Dienst.

## Zielbild

Atlas beantwortet **pro Spiel**: Welche Editionen gibt es, welche Spielwege und Zusatzfunktionen (Dual-Screen, native Ports, ROM-Hacks, Recomp, PC-Gaming), welche Hardware-/Software- und Dateiversion ist erforderlich, wo sind die belegten Bilder, und ist die Aussage auf Thor-Hardware geprüft? Ein großer **Spieleindex** ist getrennt von **quellenbasierten Spielwegen**. Unbekannte Spiele sind watchlistfähig, auch wenn kein Mod bekannt ist.

Die Pipeline kann **neue Projekte** suchen (GitHub-Suche, Modrinth-Suche, optional CurseForge-Suche) und **bekannte Projekte** überwachen (bestehender `sync_sources.py`), ohne jedes Repository vorher zu kennen. Das ist ausdrücklich **keine Vollständigkeitsgarantie**. Suchmaschinen, Foren und Discord brauchen ergänzende, freigegebene Zugänge/Community-Meldungen.

## Datenmodell: Titel → Edition → Ausführungsweg → Mod → verifizierte Kombination

Beispiel Minecraft:

- **Werk**: `Minecraft`.
- **Edition**: Java oder Bedrock (nicht austauschbar).
- **Minecraft-Datei/Build**: exakt unterstützte Version, z. B. `1.21.11` oder `26.x`.
- **Android-Laufzeit/Launcher**: DroidBridge, Zalith, Amethyst etc.; kein Ersatz für einen Emulator.
- **Mod/Companion**: ExoJosh-Fabric-Companion, Abacus-Forge-Companion, DroidBridge Dual Screen HUD etc.
- **Dateibindung**: Mod-Datei mit Modloader, Version, Hash/Release-URL, externen Abhängigkeiten.
- **Funktion**: Dual-Screen mit HUD, Karte, Touch-Eingabe. Nicht aus dem Namen eines Mods abgeleitet.
- **Hardwaretest**: separat; genaue Thor-Version/Firmware, Laufzeit, Datum, Leistungsprofil und Messbedingungen.

Die jetzige UI hat die Felder überwiegend noch **innerhalb der bestehenden `route`-Objekte**, um v0.2 nicht zu brechen. Ein späteres relationales Backend sollte `works`, `editions`, `builds`, `execution_routes`, `modifications`, `compatibility_claims`, `evidence`, `media_assets`, `device_tests`, `subscriptions` getrennt modellieren.

## Automatisierte Stufen

```text
   Spieleindex / Watchlist / Community-Vorschläge
                       |
            pro-Spiel-Suchaufträge
                       |
  +--------------------+---------------------+
  |                    |                     |
 bekannte Repos    GitHub-Reposuche    Modrinth/CurseForge*
  |                    |                     |
 Releases +       Neue Forks, Ports,   Minecraft-Moddateien,
 README-Diffs      Emulator-Varianten   Loader- und Versionsdaten
  +--------------------+---------------------+
                       |
        Normalisieren + URL-Deduplikation
                       |
          README / Release / Datei-Beleg
                       |
       Version, Edition, Features extrahieren
                       |
              Konflikte erkennen
                       |
          getrennte Screenshot-Vorschläge
                       |
              REVIEW-WARTESCHLANGE
                       |
    Redaktion / hardwarebasierter Community-Test
                       |
             KATALOG + WATCH-EVENT
```

*CurseForge nur mit genehmigtem Core-API-Zugang. Andere Quellen dürfen nur im erlaubten Nutzungsumfang eingebunden werden.*

### Implementiert

| Aufgabe | Datei | Status |
| --- | --- | --- |
| Bekannte Quellen, Releases und Linklisten | `scripts/sync_sources.py` | API-basiert, schon in v0.2; nicht dauerhaft betrieben |
| Breite, spielunabhängige GitHub-Repo-Suche | `scripts/discover_repositories.py` | Suchadapter, review-only |
| **Neue spielbezogene Recherche** | `scripts/deep_research.py` | GitHub- und Modrinth-Suche; optional CurseForge mit Key; Testfixture enthalten |
| Rechercheziele und Editionen | `data/research_targets.json` | Minecraft und Super Metroid gezielt, alle anderen mit Basisqueries |
| Quellenhinweise, Versions-/Loader-Erkennung | `scripts/deep_research.py` | Regelauswertung, keine unabhängige Aussage über Hardwarefunktion |
| Recherche-Kandidaten | `data/research_queue.json` | **Aktueller Beispielinhalt stammt aus einer Offline-Fixture**, im Browser klar als Demo markiert |
| Bild-URL-Vorschläge aus READMEs | `scripts/discover_media.py`, `scripts/deep_research.py` | Nur URLs/Alt-Texte, keine visuelle Validierung |
| Kandidaten in Bild-Review-Liste überführen | `scripts/triage_media.py` | Quell-/Spiel-Zuordnung, niemals automatische Veröffentlichung |
| Audit für fehlende Bilder und Versionsinfos | `scripts/quality_audit.py` | Läuft, keine Prozentzahl für angebliche Vollständigkeit |
| Optionales KI-Ausgabeformat | `schemas/agent_findings.schema.json`, `scripts/validate_agent_findings.py` | Validierung implementiert; **kein Modell und keine Vision-API angebunden** |
| GitHub Actions Scheduler und PR-Review | `.github/workflows/update-sources.yml` | Konfiguriert, muss im eigenen Repository aktiviert werden |

## Schnell ausprobieren

Python 3.10+, Node 20+ für die Javascript-Tests.

```sh
# Reproduzierbarer lokaler Recherchetest (KEIN Live-Abgleich)
python3 scripts/deep_research.py --game minecraft \
  --fixture fixtures/minecraft_research.json \
  --leads fixtures/minecraft_leads.json --budget 8

# Qualitätsbericht + Medienvorschläge aktualisieren
python3 scripts/triage_media.py
python3 scripts/quality_audit.py

# Browser-Datei und PWA neu bauen
python3 scripts/validate.py
python3 scripts/build.py
python3 scripts/serve.py
```

Dann `http://localhost:8765` öffnen → **Minecraft → Recherche-Stand**. `Handheld-Atlas.html` kann alternativ offline geöffnet werden. Es ist **kein Live-API-Frontend**.

Bei aktivem Internetzugang mit serverseitigen Credentials:

```sh
# Mac / Linux:
export GITHUB_TOKEN='your-github-token'          # optional, für höhere Limits
export CURSEFORGE_API_KEY='your-approved-api-key' # optional, nur bei genehmigtem Zugang
python3 scripts/deep_research.py --game minecraft --live --budget 9
python3 scripts/deep_research.py --batch 3 --live --budget 4
python3 scripts/triage_media.py
python3 scripts/quality_audit.py
python3 scripts/build.py
```

**Wichtig:** Der erste Live-Lauf entfernt Demo-Kandidaten aus der Recherchequeue, bevor echte API-Treffer gemischt werden. Keine Anmeldedaten in `dist/`, `catalog.json` oder PWA ablegen. Ein GitHub Action-Lauf wurde hier mangels eines verbundenen Repositories und verfügbarem API-Netzwerk noch nicht ausgeführt.

`--batch` untersucht anhand der **ältesten erfolgreich abgeschlossenen Live-Recherche** die nächsten Spiele; damit läuft nicht jede Woche dieselbe Auswahl. Ein Lauf ist absichtlich pro Spiel und Anzahl API-Suchen begrenzt. Nicht recherchiert heißt niemals „für dieses Spiel existiert nichts“.

## Die fehlenden Quellen – wie wir sie sinnvoll ergänzen

1. **GitHub-Suche**: Repos, Forks, README, Release-Notes, issues/discussions nur soweit per API zulässig; ergänzend vorhandene Indexlisten.
2. **Mod-Portale**: Modrinth API ist technisch dokumentiert. CurseForge benötigt eine genehmigte API-Anbindung und entsprechende Nutzungsrechte. Direkte Webscraper durch offizielle APIs ersetzen.
3. **Community-Kanäle**: Reddit-Posts/Threads können die Erstentdeckung liefern, **aber nur mit passender Freigabe**. Reddit verlangt für kommerzielle Verwendung der Data API eine separate Genehmigung; keine automatische nicht genehmigte Scraping-Lösung implementieren. Discord ebenfalls nur über zulässige Bots/Community-Partnerschaften.
4. **Recherchedienst/Agent**: Für ein bisher schlecht abgedecktes Spiel zusätzliche Web-/Forensuche über einen rechtmäßig nutzbaren Suchdienst starten. Ergebnisse werden als `--leads` JSON importiert – nie automatisch als belegte Spielwege ausgewiesen.
5. **Meldungen durch Nutzer und Mod-Autoren**: Formular `Spiel → Projektlink → Edition → Kurzbeschreibung → Quelle → Screenshots` mit Review-Queue. Die echte serverseitige Meldeschnittstelle fehlt noch.

## Wo KI tatsächlich hilft

**Agent A – Discovery & Extraktion:** Neue Kandidaten inhaltlich zuordnen; aus offiziellen Anleitungen streng strukturierte Claims (Edition, Versionsrange, Modloader, Runtime, Sicherheitsbedingungen) vorschlagen. Das Modell erhält ausschließlich isolierte Texte als **nicht vertrauenswürdige Quellen**, keinerlei Shell-/GitHub-Rechte. Die Ausgaben müssen `schemas/agent_findings.schema.json` entsprechen und eine präzise Quellenstelle enthalten.

**Agent B – Widerspruchsprüfung:** Meldet Konflikte zwischen README, Release-Datei und Tests. Beispiel DroidBridge: Dokumentation nennt Fabric; eine Dateiliste zeigt auch Loader-Bezeichnungen, die *pro Datei* zu prüfen sind. Nicht automatisch „Forge unterstützt“ behaupten.

**Agent C – Medienprüfung:** Zunächst nur Kandidatenquellen und Bildmetadaten sammeln. Danach ein Vision-Modell fragen, ob der Screenshot zur konkreten Spielversion gehört, ob zwei Bildschirme und das behauptete Feature sichtbar sind, und ob es ein Mockup oder Titelbild ist. **Ein Modell kann weder Nutzungsrechte noch Game-Builds zuverlässig allein validieren.** Bei Unsicherheit bleibt ein Quellenlink statt eines Bildes. Bilder aus fremden Threads dürfen nur entsprechend der jeweiligen Nutzungsrechte eingebettet oder gespeichert werden.

Dafür ist n8n **optional**: hilfreich für Fehlerbenachrichtigungen, Review-Formulare und zeitgesteuerte KI-Läufe. GitHub Actions + Python reichen für den Start. Ein kostenpflichtiger KI-Job sollte nur auf Treffer mit neuer/unklarer Evidenz ausgelöst werden, nicht auf jede Polling-Antwort.

## Qualitätssicherung und Freigaberegeln

- Ein **Katalogeintrag** braucht belegte Edition, Runtime, Installationsvoraussetzungen, Quelle und den Status `documented`, `experimental` oder `archived`.
- Eine **Kompatibilitätsbestätigung** braucht echten Gerätebericht, Gerät/Firmware/Version/Datum und reproduzierbare Schritte. Ein README allein ist nicht gleich „Thor-getestet“.
- Ein **Versionsintervall** wird nicht aus einer einzelnen Moddatei hochgerechnet. Herstellerseitige Versionen, Release-Dateien und Community-Tests werden auseinandergehalten.
- **Screenshots** brauchen Projekt-/Variante-Zuordnung, Quell-Link, Lizenz-/Nutzungsrecht und idealerweise eine visuelle Prüfung. Kein blindes Bilderscraping.
- **Watch-Events**: `release_detected` ist etwas anderes als `feature_added`. Nur ein separat redaktionell geprüfter Feature-Claim darf eine Feature-Watchlist-Benachrichtigung auslösen.
- Neue KI-Vorschläge dürfen weder fremde APKs ausführen, noch Nutzer-ROMs hochladen, noch bekannte Dateien überschreiben, noch unüberprüft in `catalog.json` landen.

## Offene Produktfragen

- **Großer Grundkatalog**: Wikidata kann eine Basis sein, aber für möglichst alle Editions- und Franchise-Metadaten braucht es wahrscheinlich eine passende lizenzierte Spiele-API. Das v0.3-Paket enthält weiterhin 374 suchbare Titel, davon 333 reine Indexeinträge.
- **Watchlist-Benachrichtigungen**: Der lokale Browser kennt deine Interessen, aber das Backend kennt sie nicht. Für echte Push-Events benötigt Atlas Opt-in-Synchronisierung, Geräte-Token/Push-Abonnements, Datenschutzregeln und eine passende Event-Datenbank.
- **Menschliche Review-Kapazität**: Langfristig sind Mod-Autoren und Geräte-Community-Meldungen der Schlüssel zur Vollständigkeit; KI allein kann unbekannte private Discord-Funde oder reine Video-Demos nicht zuverlässig erfassen.
- **Rechte**: Keine geschützten ROMs, Minecraft-Dateien, fremde Artwork-Pakete oder exklusive Mod-Dateien spiegeln. Lizenz- und Markenhinweise pro Quelle berücksichtigen.

## Offizielle Quellen zur technischen API-Nutzung

- GitHub REST API: https://docs.github.com/en/rest
- Modrinth Search API: https://docs.modrinth.com/api/operations/searchprojects/
- CurseForge API-Genehmigung: https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key
- Reddit Data API / commercial permissions: https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data
