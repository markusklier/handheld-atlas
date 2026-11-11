# Handheld Atlas – Kontext, Entscheidungen, nächste Schritte

Übergabe für neue Chats/Sessions. Technische Regeln für die Datenpflege stehen in `CLAUDE.md`, die Bedienung in
`README.md`. Hier steht, **was Markus entschieden hat und warum** – damit niemand es neu erfragen muss.

## Ziel und Rahmen

- Atlas ist **privat** (für Markus, AYN Thor). Grund: Nutzungsbedingungen der Quellen (v. a. EmuReady) und Kosten.
  Öffentlich erst, wenn sich Atlas inkl. Setup-Assistent im Alltag bewährt („vom leeren Handheld schnell ins Spiel“).
- Name: Es gibt bereits **HandheldAtlas.com** (x86-PC-Handhelds, Einstellungen/Benchmarks). Vor einer Veröffentlichung umbenennen.
- Anspruch: verlässlich aktuell, jedes Spiel auffindbar, Fassungen vollständig (Archiv), viele Bilder – Dual Screen zuerst.
- **Möglichst wenig Handarbeit.** Manuelle Schritte (z. B. Bild-Links einfügen) werden nicht genutzt →
  Lösungen müssen automatisch laufen. Qualität hat trotzdem Vorrang: Lücken werden zurückgestellt, nicht hingenommen.
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

## Bekannte Grenzen und zurückgestellte Themen

- **Reddit-Bilder: Stufe 1 umgesetzt (9.11.) – Laden auf dem Gerät.** Details, Datenformat und Vertrag für die native
  App: [`docs/REDDIT.md`](REDDIT.md). Kurz: Der Build schreibt eine Abholliste (Reddit-Beiträge aus den Spieldaten und
  solche, die die KI-Bildersuche fand, aber nicht öffnen konnte; Dual Screen zuerst) in `data.json`. Die App lädt sie auf
  dem Handheld, zeigt die Bilder sofort und meldet sie mit einem GitHub-Schlüssel (Info, nur „Issues“) automatisch als
  Issue `reddit-images:` zurück; die Action übernimmt sie ohne KI (`scripts/reddit.py`), die KI-Bildprüfung folgt.
  Gespeicherte Reddit-Vorschaubilder zeigt die App als Original (`i.redd.it`) mit Rückfall.
  Lage bei Reddit (Stand 9.11.2026): nicht angemeldete `.json`-Abrufe seit Ende Mai 2026 abgeschaltet, auch privat;
  neue API-Anträge seit 31.10.2026 geschlossen (Option „API-Zugang beantragen“ entfällt); RSS endet 13.11.2026.
  Folge: Im Browser wird der direkte Abruf sehr wahrscheinlich gesperrt sein (die Web-App darf die Reddit-Anmeldung
  nicht mitbenutzen) – das zeigt Info → „Reddit-Bilder vom Gerät“ nach dem ersten Start. Dann gilt:
  1. **Atlas-App** (seit 10.11., `docs/SETUP.md`): einmal in der App bei Reddit anmelden, dann liest sie die Beiträge
     mit dieser Anmeldung – die dauerhafte Lösung. Auf dem Thor noch ungetestet.
  2. Im Browser: Reddit-Einbettung am Spielweg („hier anzeigen“) zum Ansehen; KI-Websuche liest weiter Bildadressen,
     soweit sie kann.
  3. Eigener Runner zu Hause bleibt Plan B (bräuchte ebenfalls eine Reddit-Anmeldung).
- MobyGames, GameFAQs, minecraft.net u. ä. blocken Server-Abrufe. CurseForge braucht einen genehmigten Schlüssel.
- KI findet Seiten zuverlässig, Bild-URLs kaum → Bilder werden aus gefundenen Seiten extrahiert (`scripts/images.py`).

## Atlas-App mit Setup-Assistent (erste Fassung 10.11.2026)

Alles Wichtige steht in [`docs/SETUP.md`](SETUP.md): was die App kann und was noch nicht, Installation, Aufbau,
Brücke, Datenformate, Sicherheit, nächste Schritte. Kurzfassung:

- **Eine App** (`android/`, Kotlin): zeigt die Atlas-Oberfläche in einem WebView und gibt ihr über die Brücke
  `AtlasBridge` die Fähigkeiten, die eine Webseite nicht hat. Der Assistent selbst ist `app/setup.js` – eine
  Oberfläche für Browser (Checkliste) und App (installieren, starten, messen).
- **Zwei Bildschirme:** großes Display = Spielseite, kleines = Listen, Wege, Checkliste, Live-Werte.
- **Ablauf je Spielweg:** Gerät → App(s) installieren → eigene Dateien → Startkonfiguration aus Berichten →
  Messfahrt → Auswertung → Feintuning (KI oder nächste Konfiguration) → Rückmeldung in `data/setup/runs/`.
- **Nur AYN Thor Max** in der ersten Fassung. APK-Build und Release per GitHub Action; Vorab-Schlüssel im Repo.
- **Auf dem Thor ungetestet.** Der Selbsttest der App meldet zurück, was auf dem Gerät wirklich geht
  (`data/setup/selftest.json`) – den zuerst lesen, bevor an Messung, Start ins Spiel oder Konfigurationsdateien
  weitergebaut wird.

Entscheidungen von Markus (10.11.): Einzelrezepte je Spiel sind wichtig; der Nutzer wählt den Weg, der Assistent
versucht auch nicht empfohlene Wege; Shizuku ja, ADB vom Mac nur für Notfälle; KI darf für das beste Ergebnis Geld
kosten, über 5–10 € je Spielinstallation ist nicht mehr im Verhältnis; nicht verrennen (nicht wegen 3 FPS optimieren,
nicht 60 erzwingen, wenn die Hardware 35 hergibt). Die frühere Festlegung „keine KI, die selbstständig installiert“
gilt nicht mehr: Die KI soll so viel wie möglich selbst erledigen – innerhalb fester Werkzeuge (docs/SETUP.md →
Sicherheit), nie ROMs besorgen, nie kaufen.

Marktbild (Recherche 9.11.): EmuDeck für Android (Beta, nur Patreon, emulatorzentriert, Thor unterstützt) richtet
Emulatoren ein; GameNative sammelt Bewertungen und wendet bekannte Konfigurationen an; niemand verbindet
Spiel → Fassung → Weg → Gerät → gemessenes Setup.

## Offene Punkte

- Watcher-Funde: ~700 alte Leads werden pro Warteschlangen-Lauf zu 30 vorsortiert; Werkzeuge/Verzeichnisse bleiben
  für die Claude-Pflegeaufgabe.
- 22 Spiele ohne Cover (Nischentitel); Cover mit `fallback: true` sind Notlösungen und werden bei besserer Quelle ersetzt.
- Viele Spielwege noch ohne Bild; Originalbilder vor allem bei modernen Konsolenspielen dünn.

## Entscheidungen vom 11.11.2026

- **Recherche:** Standard ist die API (sofort); zentral umschaltbar auf das Abo (Info → „Wo wird recherchiert?“).
  Ist die API nicht nutzbar, übernimmt die Abo-Aufgabe automatisch. Details: [`docs/RECHERCHE.md`](RECHERCHE.md).
  Tiefenrecherche bleibt immer anforderbar, auch neben „Aktualisieren“; ein Wunschtext („Was fehlt dir?“) geht mit.
- **Remakes sind eigene Spiele** mit `remakeOf`; das Original zeigt sie unten aufklappbar, der Vergleich enthält ihre
  Wege eingeklappt. Remaster, Ports, Neuauflagen und Sammlungen bleiben Fassungen.
- **Emulator-Wahl:** Atlas empfiehlt je Fassung den besten Emulator (Berichte vom Thor-Chip, eigene Messfahrten, schon
  installiert) und markiert ihn. Atlas merkt sich **keinen** Favoriten; im Setup-Assistenten kann man jederzeit einen
  anderen wählen. PC: GameNative, Winlator, GameHub (Lite), DroidDeck.
- **Zwei Bildschirme:** oben stöbern, unten die „Bühne“ (große Vorschau → Spielseite → Einrichten); Tauschen per Knopf,
  Select wechselt den Bildschirm. Details in [`docs/SETUP.md`](SETUP.md).
