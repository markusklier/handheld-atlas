# Wo recherchiert Atlas? API oder Abo

Atlas hat zwei KI-Arbeiter. Welcher Anfragen aus der App erledigt, steht in `data/research.json` und lässt sich in der
App unter **Info → „Wo wird recherchiert?“** mit einem Tipp umschalten.

| | **API** (Standard) | **Abo** |
|---|---|---|
| Wer | GitHub Action „KI-Recherche“ mit OpenAI | geplante Claude-Aufgabe „Handheld Atlas Pflege“ (dein Claude-Abo) |
| Wann | sofort, 3–5 Minuten nach der Anfrage | beim nächsten Pflegelauf (montags und donnerstags um 20:38) |
| Kosten | OpenAI-Guthaben (Verbrauch unter Info) | keine zusätzlichen, zählt zum Abo-Kontingent |
| Automatisch | Warteschlange alle 2 h, wöchentliche Recherche, Dual-Screen-Suchlauf, KI-Bildprüfung | pausiert – der Pflegelauf übernimmt Warteschlange (3–5 Spiele) und Bildprüfung |

**Ausfall der API:** Ist kein OpenAI-Schlüssel hinterlegt, das Monatsbudget erreicht oder das Guthaben leer, geht eine
Anfrage automatisch an die Abo-Aufgabe (`"fallback": "abo"`): Die Action kommentiert das Issue, setzt das Label
**`abo`** und lässt es offen. Die App zeigt dann „wartet auf die Abo-Aufgabe (montags und donnerstags um 20:38)“.

**Immer ohne KI und kostenlos:** Watcher (Releases, Funde), Wikidata-Basisprofile, EmuReady-Berichte, Bilder aus
libretro/Steam/Wikipedia/READMEs, Rückmeldungen vom Gerät (`setup-report:`, `reddit-images:`), Übernahme einer
Sofortanalyse (JSON im Issue) und das Umschalten selbst (`research-backend: api|abo`).

## Anfragen aus der App

- **Tiefenrecherche** – alles neu: Fassungen, Spielwege, Emulatoren, Mods, Berichte. Gibt es immer, auch wenn das Spiel
  schon recherchiert ist („Neue Tiefenrecherche“).
- **Aktualisieren** – nur, was sich seit der letzten Recherche geändert hat (neue Versionen, eingestellte Projekte,
  neue Wege). Günstiger, sucht aber nicht gezielt nach Fehlendem.
- **„Was fehlt dir?“** – freier Text am Datenstand-Kasten (z. B. „DroidDeck und GameHub fehlen“). Er geht als Auftrag mit
  und wird in der Recherche gezielt gesucht (`WUNSCH DES NUTZERS` im Prompt).
- Mit einem **GitHub-Schlüssel** (Info, Berechtigung „Issues: Lesen und Schreiben“) schickt die App Anfragen direkt
  ab; ohne öffnet sich GitHub mit allem ausgefüllt und du tippst auf „Create“.

## Technik

- `data/research.json`: `backend` (`api`|`abo`), `fallback` (`abo`|`none`), `aboSchedule` (Text für die App),
  `status` (letzter bekannter Zustand der API), `handovers` (zuletzt übergebene Anfragen).
- `scripts/ai_research.py`: `api_ready()` entscheidet vor jeder KI-Arbeit; `ApiUnavailable` (401/403, 429
  `insufficient_quota`) mitten im Lauf → Übergabe, angefangene Warteschlangen-Einträge kommen zurück nach vorn.
- `.github/workflows/research.yml`: findet es die Datei `report.md.handover`, setzt es das Label `abo` und schließt nicht.
- Die Claude-Aufgabe liest `CLAUDE.md` → Pflegelauf Schritt 2: offene Issues mit Label `abo` zuerst.
