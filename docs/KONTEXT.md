# Handheld Atlas – Kontext, Entscheidungen, nächste Schritte

Übergabe für neue Chats/Sessions. Technische Regeln für die Datenpflege stehen in `CLAUDE.md`, die Bedienung in
`README.md`. Hier steht, **was Markus entschieden hat und warum** – damit niemand es neu erfragen muss.

## Ziel und Rahmen

- Atlas ist **privat** (für Markus, AYN Thor). Grund: Nutzungsbedingungen der Quellen (v. a. EmuReady) und Kosten.
  Öffentlich erst, wenn sich Atlas inkl. Setup-Assistent im Alltag bewährt („vom leeren Handheld schnell ins Spiel“).
- Name: Es gibt bereits **HandheldAtlas.com** (x86-PC-Handhelds, Einstellungen/Benchmarks). Vor einer Veröffentlichung umbenennen.
- Anspruch: verlässlich aktuell, jedes Spiel auffindbar, Fassungen vollständig (Archiv), viele Bilder – Dual Screen zuerst.
- **Möglichst wenig Handarbeit.** Manuelle Schritte (z. B. Bild-Links einfügen, Reddit-App) werden nicht genutzt →
  Lösungen müssen automatisch laufen.
- Alle Texte in der App Deutsch mit Umlauten. Keine Piraterie-Links, keine echten Hersteller-Logos.

## Kosten

- KI-Budget: **20 €/Monat** (OpenAI, Secret `OPENAI_API_KEY`), notfalls 50–100 €. Am 9.11. waren ~18 € verbraucht
  (viel davon Test- und Doppelläufe, inzwischen behoben).
- Stufenmodell: Breite kostenlos (Wikidata, Wikipedia, Steam, libretro, READMEs), Tiefe (KI) nur auf Anfrage oder
  wenn die Reihen-Auswahl ein Spiel für lohnend hält. Tageslimit Warteschlange `MAX_QUEUE_PER_DAY` (12).
- Verbrauch: `data/inbox.json` → `usage`, in der App unter Info. Optionale Repo-Variablen: `OPENAI_MODEL`,
  `OPENAI_IMAGES_MODEL`, `OPENAI_VISION_MODEL`, `OPENAI_TRIAGE_MODEL`, `OPENAI_PRICE_IN/OUT/SEARCH`, `OPENAI_MONTHLY_BUDGET`.

## Was automatisch läuft

| Was | Wann | Kosten |
|---|---|---|
| Watcher (`watch.yml`): Releases, Funde, Wikidata (150/Tag), Cover/Bilder, EmuReady, Reihen-Korrektur | täglich 05:16 UTC | 0 |
| KI-Recherche (`research.yml`): Anfragen aus der App (Issues mit Label `recherche`) | sofort | KI |
| Warteschlange + Nachprüfung bei neuen Releases + 30 Funde vorsortieren | alle 2 h zu :22 | KI |
| Wöchentlich: 3 Spiele + Bilder (Mi), Dual-Screen-Suchlauf (So), Bildprüfung | wöchentlich | KI |
| Claude-Pflegeaufgabe „Handheld Atlas Pflege“ (folgt `CLAUDE.md`) | Mo + Do 20:38 Berlin | Claude-Abo |

Hinweis: Die zeitgesteuerten GitHub-Läufe starteten erst verzögert; Markus hat die Cron-Zeilen selbst editiert
(Minute 22/16). Die Modusauswahl in `research.yml` vergleicht den Cron-String – bei Änderungen beide Stellen anpassen.

## Bewusst verworfen / bekannte Grenzen

- Reddit ist aus GitHub Actions gesperrt (403); eine Reddit-API-App ist mit normalem Konto praktisch nicht zu bekommen.
  Reddit-Bilder kommen nur, wenn die KI-Websuche die Bildadresse nennt. → später anders lösen (z. B. über die eigene App
  auf dem Gerät, die Reddit normal laden kann).
- MobyGames, GameFAQs, minecraft.net u. ä. blocken Server-Abrufe. CurseForge braucht einen genehmigten Schlüssel.
- KI findet Seiten zuverlässig, Bild-URLs kaum → Bilder werden aus gefundenen Seiten extrahiert (`scripts/images.py`).

## Nächstes großes Thema: Setup-Assistent als eigene Android-App

Entscheidung: **eigene native App** (Kotlin), damit möglichst viel automatisch bzw. KI-gestützt geht. Atlas (Web) bleibt
Entdecken + Datenbank; die App nutzt dieselbe `data.json`.

Konzept (aus der Planung vom 9.11.):
- **Setup-Rezept je Spielweg und Chip-Klasse** (nicht je Gerät: Thor, Odin 2, Retroid Pocket 5 teilen sich viel):
  Schritte vom Typ App installieren (Play/Obtainium/GitHub-Release), eigene Dateien bereitstellen (nur prüfen, nie
  besorgen; Prüfsummen), Einstellungen (Wert + Menüpfad + Quelle), Konfigurationsdatei, Mods, Android-/Geräteeinstellung,
  Starten (Intent). Jeder Schritt mit Quelle und Prüfstufe. Rezepte erzeugt/aktualisiert die KI im Hintergrund, einmal
  pro Weg, nicht pro Nutzer; EmuReady-Berichte liefern oft schon Einstellungen.
- **App kann:** installierte Apps/Versionen erkennen, APKs installieren/aktualisieren (Nutzer bestätigt), Ordner per SAF
  wählen, Spieldateien per Prüfsumme prüfen, Konfigs ablegen, wo Emulatoren aus Nutzerordnern lesen, Spiele per Intent
  starten; optional Shizuku. Grenzen: keine fremden `Android/data`-Ordner, keine Spieldateien, Play-Store-Richtlinien
  (Verteilung über GitHub/Obtainium).
- **KI in der App:** Fehlersuche mit Rezept + Geräteinfos als Kontext; fehlende Rezepte erzeugen (Ergebnis zurück in die DB).
  Keine KI, die selbstständig installiert.
- **Rückmeldung „Läuft es?“** nach jedem Setup → Erfahrungsberichte je Chip-Klasse → bessere Empfehlung (das ist der
  eigentliche Vorsprung gegenüber EmuReady/EmuDeck/ES-DE/Obtainium).
- Marktbild (Recherche 9.11.): EmuDeck für Android (Beta, nur Patreon, emulatorzentriert, Thor unterstützt) richtet
  Emulatoren ein; niemand verbindet Spiel → Fassung → Weg → Gerät → geprüftes Setup. Markt klein, aber zahlungsbereit
  (Patreon, Spenden, Affiliate).

Reihenfolge-Vorschlag: Rezept-Datenmodell + Beispielrezepte (CTR-DS, Skyrim über GameNative, ein DS-Spiel) →
KI füllt Rezepte für die bestempfohlenen Wege → App-Prototyp (Gerät/Apps erkennen, installieren, prüfen, starten).

## Offene Punkte

- Watcher-Funde: ~700 alte Leads werden pro Warteschlangen-Lauf zu 30 vorsortiert; Werkzeuge/Verzeichnisse bleiben
  für die Claude-Pflegeaufgabe.
- 22 Spiele ohne Cover (Nischentitel); Cover mit `fallback: true` sind Notlösungen und werden bei besserer Quelle ersetzt.
- Viele Spielwege noch ohne Bild; Originalbilder vor allem bei modernen Konsolenspielen dünn.
