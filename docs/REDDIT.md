# Reddit-Quelle: Bilder vom Gerät laden

Ziel: bessere und mehr Bilder für Spielwege, vor allem **Dual Screen**. Die besten Fotos stammen oft aus Reddit-Beiträgen
der Autoren selbst (Beispiel: ExoJoshs Minecraft-Dual-Screen-Mod in r/AynThor). Genau diese Beiträge kann Atlas auf dem
Server nicht lesen. Deshalb lädt sie **der Handheld** (die Web-App, später die native Atlas-App) und meldet die Bilder
automatisch zurück in die Datenbank.

## Warum auf dem Gerät?

Stand November 2026 (siehe Quellen unten):

- **Ende Mai 2026** hat Reddit die nicht angemeldeten `.json`-Abrufe abgeschaltet. Ohne Anmeldung gibt es 403,
  auch von privaten Anschlüssen; mit Anmeldung (Browser-Cookie) funktioniert es weiter.
- **GitHub Actions** werden ohnehin gesperrt (403).
- **API-Zugang:** Seit dem **31.10.2026** nimmt Reddit keine neuen Anträge mehr an; nicht registrierte Apps verlieren
  ab dem 12.01.2027 den Zugang, der restliche öffentliche Zugang endet im März 2027. Der Weg über
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` in `images.py` bleibt im Code, ist aber praktisch tot.
- **RSS** endet am 13.11.2026 – darauf bauen wir nicht.

Was bleibt: **angemeldete Abrufe vom eigenen Gerät**, in geringem Umfang (ein Beitrag alle 1,5 Sekunden, höchstens
12 pro App-Start). Bilder werden nur verlinkt, nie kopiert.

## Ablauf

```
 Server (GitHub)                                  Handheld (Atlas)
 ───────────────                                  ────────────────
 Spieldateien: Reddit-Links, Berichte,
 Bildquellen  ─┐
 KI-Bildersuche: Reddit-Seiten, die nicht   ──►  data.json → "reddit": Abholliste
 lesbar waren (media_state → reddit.found) ─┘     (Dual Screen zuerst)
                                                    │  1. native App (Reddit-Anmeldung)   oder
                                                    │  2. direkt aus dem Browser (falls Reddit antwortet)
                                                    ▼
                                                 Bilder sofort in der Galerie („Reddit · vom Gerät“),
                                                 nur Bilder, die auf dem Gerät wirklich laden (mit Größe)
                                                    │
 Action „KI-Recherche“  ◄── Issue „reddit-images:“ + JSON (automatisch mit GitHub-Schlüssel)
   reddit.apply(): neue Bilder check "reddit",
   Vorschau → Original ersetzen, Beitrag erledigt
   ai_vision.py: prüft "reddit"-Bilder (passt / unklar / raus)
   Commit + Deploy → alle Geräte haben die Bilder
```

### 1. Abholliste (Server)

`scripts/reddit.py` sammelt alle Reddit-Beiträge, auf die ein Spiel verweist:

| Fundstelle | Ziel der Bilder |
|---|---|
| `routes[].links`, `routes[].reports`, `routes[].screenshots[].source` | dieser Spielweg |
| `mods[].url`, `mods[].screenshots[].source` | dieser Mod |
| `screenshots[].source` des Spiels | Originalbilder des Spiels |
| KI-Bildersuche fand den Beitrag, GitHub konnte ihn nicht öffnen (`remember`) | der gesuchte Spielweg |

Der Build schreibt die noch offenen Beiträge als `reddit` in `data.json`
(`{id, url, targets: ["spiel/weg" | "spiel" | "spiel/mod:id"], dual}`), Dual-Screen-Wege und Wege mit wenigen Bildern zuerst.
Erledigt ist ein Beitrag, wenn das Gerät Bilder, „keine Bilder“ oder „gelöscht“ gemeldet hat, oder nach drei
fehlgeschlagenen Abrufen. Der Stand liegt in `data/media_state.json` → `reddit` (`found`, `done`).

```sh
python3 scripts/reddit.py               # Abholliste ansehen (DS = Dual Screen)
python3 scripts/reddit.py apply x.json  # eine Rückmeldung lokal übernehmen
```

### 2. Abruf auf dem Gerät (`app/app.js`, Abschnitt „Reddit-Quelle“)

- Beim Start (nach 5 s) arbeitet Atlas bis zu 12 Beiträge der Abholliste ab; beim Öffnen eines Spiels zuerst dessen Beiträge.
- Abrufwege, in dieser Reihenfolge:
  1. **Atlas-App** – über die Brücke `redditFetch` (Abschnitt „In der Atlas-App“). Die App nutzt die
     Reddit-Anmeldung des Nutzers; das ist der Weg, der dauerhaft funktioniert.
  2. **Direkt aus dem Browser** – `https://www.reddit.com/comments/<id>/.json?raw_json=1`, erst ohne, dann mit
     Cookies. Das Ergebnis wird gemerkt (`atlas.redditProbe`). Ist der Abruf gesperrt, versucht Atlas es erst nach
     24 Stunden wieder (oder per „Erneut testen“ unter Info), damit Reddit nicht mit Fehlversuchen belastet wird.
- Aus dem Beitrags-JSON nimmt Atlas: Galerie in Originalreihenfolge (als Original `i.redd.it/<id>.jpg|png`, die
  Vorschau in voller Größe als Ersatz), das Bild eines Bildbeitrags, bei Videos das Vorschaubild, Crossposts vom
  Ursprungsbeitrag. Jedes Bild wird auf dem Gerät geladen; gemeldet werden nur Bilder, die wirklich laden (mit Breite/Höhe).
- Geladene Bilder erscheinen sofort in der Galerie des Spielwegs mit dem Hinweis **„Reddit · vom Gerät“**
  (Cache `atlas.redditCache`), bis die Datenbank sie übernommen hat.
- **Kann der Browser Reddit nicht lesen**, zeigt der Spielweg „Reddit-Beitrag hier anzeigen“: die offizielle
  Reddit-Einbettung (`embed.reddit.com`) direkt in Atlas, dazu „Auf Reddit“. So sieht man die Bilder trotzdem auf
  dem Gerät – sie landen dann nur nicht automatisch in der Datenbank.
- **Bildqualität allgemein:** Alle gespeicherten Reddit-Vorschaubilder (`preview.redd.it/…?width=640`) zeigt die App
  als Original von `i.redd.it`; lädt das nicht, fällt sie auf die Vorschau zurück.

### 3. Rückmeldung (automatisch)

Einmalig unter **Info → Reddit-Bilder vom Gerät** einen GitHub-Schlüssel eintragen:

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → *Generate new token*.
2. *Repository access*: **Only select repositories** → `markusklier/handheld-atlas`.
3. *Permissions → Repository permissions → Issues*: **Read and write**. Sonst nichts.
4. Ablaufdatum nach Wunsch (z. B. 1 Jahr), Schlüssel in Atlas einfügen, **Speichern**.

Der Schlüssel bleibt im Browser des Geräts und geht nur an `api.github.com`. Danach schickt Atlas die Ergebnisse
nach jedem Abgleich selbst als Issue (Label `recherche`, höchstens 25 Beiträge pro Issue). Ohne Schlüssel sammelt
Atlas sie und bietet „Als Issue senden“ an (vorbereitetes Issue, ein Tipp auf *Create*).

Format des Issues:

````
reddit-images: 2

```json
{"kind": "reddit-images", "device": "AYN Thor", "method": "direct|direct-cred|native", "at": "2026-11-09T18:52:14Z",
 "posts": [
   {"post": "https://www.reddit.com/r/AynThor/comments/1vjvo8t/", "status": "ok", "title": "…", "author": "exojosh",
    "images": [{"url": "https://i.redd.it/xp1sgpm1sdih1.jpg", "w": 1920, "h": 1080}]},
   {"post": "https://www.reddit.com/r/Doom/comments/1vim9bm/", "status": "gone", "images": []}
 ]}
```
````

`status`: `ok` · `no-images` · `gone` (gelöscht/entfernt) · `failed` (wird bis zu dreimal erneut versucht).

### 4. Übernahme (Action „KI-Recherche“, ohne KI)

`ai_research.py` erkennt `reddit-images:` und ruft `reddit.apply()` auf. Regeln:

- nur Beiträge, die auf der Abholliste stehen; nur Bilder von `i.redd.it`, `preview.redd.it`,
  `external-preview.redd.it`, `i.imgur.com`; nichts aus `rejectedImages`; höchstens 6 Bilder pro Spielweg;
- dieselbe Aufnahme (gleiche Reddit-Medien-ID) wird nicht doppelt angelegt; liegt sie bisher nur als verkleinerte
  Vorschau vor, wird die Adresse durch das Original ersetzt (Bildunterschrift und Prüfstufe bleiben);
- neue Bilder: `check: "reddit"`, `credit: "Reddit · u/<autor>"`, `source` = Beitrag. Die anschließende
  **KI-Bildprüfung** (`ai_vision.py`) behandelt `reddit` wie `ai`/`readme`: passt → `ai-verified` mit deutscher
  Bildunterschrift und Dual-Screen-Bilder nach vorn, unklar → `ai-unclear` (Pflege-Agent), passt nicht → entfernt;
- Changelog `screenshot-added` mit `"by": "device"`.

## In der Atlas-App

Seit dem 10.11.2026 gibt es die App (`android/`, siehe [`docs/SETUP.md`](SETUP.md)). Dort läuft Reddit so:

- **Anmelden:** Info → „Reddit-Bilder vom Gerät“ → „Bei Reddit anmelden“ öffnet `reddit.com/login` in einem Fenster
  der App. Benutzername und Passwort verwenden – die Google-Anmeldung funktioniert in App-Fenstern nicht. Atlas
  sieht das Passwort nicht; in der App bleiben nur Reddits Cookies.
- **Abruf:** Die Seite ruft `native.call('redditFetch', {url})`. Die App öffnet die `.json`-Adresse des Beitrags in
  einem unsichtbaren Browserfenster – also genau so, wie es dein Browser mit deiner Anmeldung täte – und gibt
  `{status, body}` zurück (`android/…/Reddit.kt`). Erlaubt ist nur
  `https://www.reddit.com/comments/<id>/.json?raw_json=1&limit=1`.
- Antwortet Reddit mit einer Anmelde- oder Sperrseite statt JSON, gilt das als 403: Atlas hört auf, meldet den
  Beitrag **nicht** als Fehlversuch und bittet um erneute Anmeldung.
- Ohne Anmeldung fragt die App Reddit gar nicht erst an (Info zeigt „noch nicht bei Reddit angemeldet“).

## Regeln

- Nur Beiträge, auf die Atlas ohnehin verweist; kein Durchsuchen von Subreddits, keine Kommentare, keine Nutzerprofile.
- Sanfte Taktung (1,5 s Abstand, max. 12 Beiträge pro Start), gesperrte Abrufe erst nach 24 h erneut.
- Bilder werden verlinkt, nie kopiert; `credit` nennt den Autor, `source` den Beitrag.
- Für den privaten Gebrauch gebaut (siehe `docs/KONTEXT.md`). Vor einer Veröffentlichung von Atlas Reddits
  Nutzungsbedingungen für automatisierte Abrufe erneut prüfen.

## Stand und offene Punkte

- Geprüft im Test-Browser mit nachgebildetem Reddit (Abruf erlaubt, gesperrt, native Brücke) und mit Unit-Tests
  (`tests/test_reddit.py`). **Noch nicht auf dem Thor getestet**: ob Reddit dem Browser den Abruf erlaubt, zeigt
  Info → „Reddit-Bilder vom Gerät“ nach dem ersten Start. Erwartung nach der Sperre vom Mai 2026: im Browser
  gesperrt → volle Automatik erst mit der nativen App, bis dahin Einbettung zum Ansehen.
- Ob `embed.reddit.com` ohne Anmeldung weiter funktioniert, ist ungeprüft (bei Fehlern bleibt „Auf Reddit“).
- Ob `i.redd.it/<id>.jpg` für jede Vorschau existiert, ist nicht garantiert – deshalb immer mit Rückfall auf die Vorschau.

Quellen: [Reddit-JSON-403 (Test vom 18.10.2026)](https://bigideasdb.com/reddit-json-403-forbidden) ·
[Reddit API-, RSS- und JSON-Änderungen](https://redmantu.com/blog/reddit-api-rss-json-shutdown/)
