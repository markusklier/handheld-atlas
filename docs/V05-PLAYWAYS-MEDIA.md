# Handheld Atlas 0.5 – Cover, Originalbilder, Spielwege und private Tests

## Neues Modell

- **Franchise:** Serie; zeigt repräsentative Cover ihrer Spiele, nicht ein erfundenes „offizielles Franchise-Cover“.
- **Spiel:** eigener Indexeintrag mit normalisiertem Namen und Originalplattform; optional ein offizielles Spielcover und bis zu sechs Originalspiel-Screenshots (`data/game_media.json`).
- **Spielweg:** eine konkret dokumentierte Edition/Laufzeit/Mod-Kombination mit eigenen Screenshots in `catalog.json`. Route-Bilder werden nicht als allgemeine Spielcover ausgezeichnet.
- **Plattformoption:** ein bekannter Emulator oder PC-Layer für eine ursprüngliche Konsole (`data/platform_paths.json`). Diese Vorschläge sind nicht pro Spiel getestet und erhöhen keine „bestätigt spielbar“-Zähler.
- **Mod/Erweiterung:** separat, mit Version, Loader und Lizenz als später zu prüfende Anforderungen (`data/game_addons.json`). Das Minecraft-Beispiel markiert Sodium auf Android ausdrücklich als nicht offiziell unterstützt.
- **Quellenkontrolle:** `data/project_checks.json` vermerkt nur, ob eine Projektquelle über die API erreichbar ist. Das ist **keine** Community- oder Gerätevalidierung.

## Spielcovers und Quellen

1. **Sofort ohne Zugangsschlüssel:** `python scripts/enrich_game_media.py --live --provider steam --limit 12` nutzt nur redaktionell zugeordnete Steam-App-IDs in `data/media_targets.json`. Die API bestätigt den exakten Spieletitel; Portrait-Artwork wird nur nach echtem HTTP-Existenztest verwendet; sonst akzeptiertes Original-Headerbild. Original-Screenshots stammen aus den Metadaten des Steam Stores. Original-URL und Provider werden gespeichert. **Kein Bild wird in das Repo kopiert.**
2. **Optional IGDB:** Auf https://api-docs.igdb.com unter eigener nichtkommerzieller Twitch Developer App eine Client ID und Client Secret erzeugen. Als Actions-Secrets `TWITCH_CLIENT_ID` und `TWITCH_CLIENT_SECRET` hinzufügen. Workflow **Enrich game covers and original screenshots** mit `provider=igdb` ausführen. Nur exakt übereinstimmende, eindeutige Spiele werden automatisch übernommen. Ambiguität oder Edition-Abweichung führt zum Überspringen.
3. **Projektbilder:** `scripts/enrich_media.py` findet Bilder aus konkreten Mod-Galerien und GitHub-Projekten. Getrennt vom allgemeinen Cover, Quelle und Bildrechte unbestätigt.

Die Herkunft eines Bildes ist ein Beleg für die *Zuordnung*, keine Lizenz zur Weiterverbreitung. Steam-/IGDB-Publisher-Artwork bleibt geschützt; vor kommerziellem oder offiziellem Launch Nutzungsrechte und Bedingungen prüfen. Für private persönliche Tests ist die Nutzungsbeurteilung dennoch nicht automatisch geklärt.

## Aktualisieren

Der Bilder-Workflow läuft mittwochs und auf Wunsch manuell. Der Quellenprüfer montags. Beide schreiben nur JSON-Daten und eine neu generierte `Handheld-Atlas.html`, nie Quellcode oder Spieldateien. Auf einer gehosteten Version lassen sich frische Medien und Projektstände von derselben Domain abrufen. Ein lokal heruntergeladenes HTML bleibt immer ein eingefrorener Schnappschuss.

## Auf dem AYN Thor benutzen

1. **GitHub Pages** wird bei GitHub Free ausschließlich für **öffentliche Repositories** angeboten. Bei Pro/Team kann ein Repository privat bleiben, die öffentliche Website ist trotzdem allgemein erreichbar. Ein privates Pages-Site-Zugriffsmodell für echte Zugangsbeschränkung erfordert besondere Enterprise-Funktionen.
2. Wer ein persönliches GitHub-Konto und seine Commit-Historie nicht veröffentlichen will, sollte **nicht das bisherige Repository auf Public stellen**. Für einen Test ist ein getrenntes, neutral benanntes, öffentliches Repository sinnvoll, das ausschließlich die erzeugten `dist/`-Dateien enthält. Hierfür braucht es initial das Anlegen des Repos durch den Nutzer oder einen autorisierten Hosting-Connector. Keine API-Keys, Dateien aus `data/` mit persönlichen Tokens oder ROMs dort hochladen.
3. Wenn der aktuelle GitHub-Tarif eine Pages-Bereitstellung aus einem privaten Repository unterstützt: **Settings → Pages → Source: GitHub Actions** und unter **Settings → Secrets and variables → Actions → Variables** `ATLAS_ENABLE_PAGES=true` setzen. Den `Deploy PWA to GitHub Pages`-Workflow ausführen. Website ist **öffentlich**, auch wenn das Quellrepository privat bleibt. URI `https://<konto>.github.io/handheld-atlas/`.
4. Mit HTTPS im Chrome des Thor öffnen und über Browser-Menü **Zum Startbildschirm hinzufügen / Installieren**. Keine Android-APK nötig. Gemerkte Titel verbleiben lokal auf dem Thor, nicht synchron auf anderen Geräten.

**Keine Veröffentlichung als verifiziertes Thor-Profil:** bisher gibt es weder reale Laufzeit-/FPS-Messungen noch einen bestätigten gerätespezifischen Test des neuen Katalogs. Projekt- und Spielkompatibilität bleiben getrennte Aussagen.
