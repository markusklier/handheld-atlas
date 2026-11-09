#!/usr/bin/env python3
"""Reddit-Quelle: Bilder aus Reddit-Beiträgen, abgerufen vom Handheld statt von GitHub.

Seit Ende Mai 2026 beantwortet Reddit Abrufe nur noch für angemeldete Nutzer; GitHub Actions bekommen 403, neue
API-Zugänge gibt es seit 31.10.2026 nicht mehr. Deshalb läuft der Abruf auf dem Gerät (Web-App bzw. später die native
App mit Reddit-Anmeldung) und dieses Modul ist nur noch die Server-Hälfte:

  1. Abholliste: welche Reddit-Beiträge Bilder für welche Spielwege liefern sollen. Quellen: Reddit-Links, Berichte
     und Bildquellen in den Spieldateien und Beiträge, die die KI-Bildersuche gefunden, aber nicht öffnen konnte
     (`remember`). Steht als `reddit` in data.json, Dual-Screen-Wege zuerst.
  2. Rückmeldung: Das Gerät schickt ein Issue mit `reddit-images:` und einem JSON-Block (Format in docs/REDDIT.md).
     `apply` übernimmt nur Bilder bekannter Beiträge von Reddit-Bildservern, ersetzt verkleinerte Vorschaubilder
     durch das Original (nur Adressen, die auf dem Gerät tatsächlich geladen haben) und markiert neue Bilder mit check "reddit" → die KI-Bildprüfung (ai_vision.py) sieht sie an.

    python3 scripts/reddit.py               # Abholliste anzeigen
    python3 scripts/reddit.py apply x.json  # Rückmeldung lokal übernehmen (sonst macht das die Action)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402  (atlas.DATA zur Laufzeit lesen – Tests biegen es um)
from atlas import read, write  # noqa: E402

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
MAX_SHOTS = 6                      # wie ai_research.MAX_SHOTS
MAX_PER_POST = 10
MAX_TRIES = 3                      # so oft darf ein Abruf fehlschlagen, dann gilt der Beitrag als erledigt
IMAGE_HOSTS = re.compile(r'^https://(i\.redd\.it|preview\.redd\.it|external-preview\.redd\.it|i\.imgur\.com)/[^\s"<>]+$')
POST_RE = re.compile(r'^https://(?:(?:www|old|new|np|m)\.)?reddit\.com/(?:r/([A-Za-z0-9_]+)/)?comments/([a-z0-9]{4,12})(?:[/?#]|$)'
                     r'|^https://redd\.it/([a-z0-9]{4,12})(?:[/?#]|$)', re.I)


def post_id(url):
    m = POST_RE.match((url or '').strip())
    return (m.group(2) or m.group(3)).lower() if m else None


def canonical(url):
    """https://www.reddit.com/r/<sub>/comments/<id>/ – ohne Slug, Parameter und Tracking."""
    m = POST_RE.match((url or '').strip())
    if not m:
        return None
    pid = (m.group(2) or m.group(3)).lower()
    return f'https://www.reddit.com/r/{m.group(1)}/comments/{pid}/' if m.group(1) else f'https://www.reddit.com/comments/{pid}/'


def media_id(url):
    """Reddit-Medien-ID eines Bildes: i.redd.it/<id>.jpg, preview.redd.it/<slug>-v0-<id>.jpeg?… → <id>."""
    m = re.match(r'^https://(?:i|preview)\.redd\.it/(?:[^/?]*-v0-)?([a-z0-9]{8,20})\.(?:jpe?g|png|webp|gif)', url or '', re.I)
    return m.group(1).lower() if m else None


def better(new, old):
    """Ist `new` eine bessere Adresse derselben Aufnahme als `old`? Original (i.redd.it) schlägt Vorschau,
    volle Größe schlägt verkleinerte Vorschau (…?width=640)."""
    if new == old:
        return False
    if new.startswith('https://i.redd.it/') and not old.startswith('https://i.redd.it/'):
        return True
    return 'width=' in old and 'width=' not in new and not old.startswith('https://i.redd.it/')


def _state():
    path = atlas.DATA / 'media_state.json'
    st = read(path) if path.exists() else {}
    rd = st.setdefault('reddit', {})
    rd.setdefault('found', {})     # id → {url, targets, since}: von der KI-Bildersuche gefunden, auf GitHub nicht lesbar
    rd.setdefault('done', {})      # id → {date, status, added, upgraded, tries}
    return path, st, rd


def remember(posts, target):
    """KI-Bildersuche fand Reddit-Beiträge für `target` ("spiel" oder "spiel/weg"), GitHub kann sie nicht öffnen."""
    path, st, rd = _state()
    changed = False
    for url in posts:
        pid, can = post_id(url), canonical(url)
        if not pid or pid in rd['done']:
            continue
        e = rd['found'].setdefault(pid, {'url': can, 'targets': [], 'since': TODAY})
        if target not in e['targets']:
            e['targets'].append(target)
            changed = True
    if changed:
        write(path, st)


def _refs(g):
    """(post-url, target, holder) für jeden Reddit-Beitrag, auf den ein Spiel verweist."""
    gid = g['id']
    for s in g.get('screenshots', []):
        yield s.get('source'), gid
    for r in g.get('routes', []):
        t = f"{gid}/{r['id']}"
        for x in r.get('links', []):
            yield x.get('url'), t
        for x in r.get('reports', []):
            yield x.get('url'), t
        for s in r.get('screenshots', []):
            yield s.get('source'), t
    for m in g.get('mods', []):
        t = f"{gid}/mod:{m['id']}"
        yield m.get('url'), t
        for s in m.get('screenshots', []):
            yield s.get('source'), t


def holder_of(g, target):
    """Spiel, Spielweg oder Mod zu einem Ziel ("spiel", "spiel/weg", "spiel/mod:id")."""
    _, _, rest = target.partition('/')
    if not rest:
        return g
    if rest.startswith('mod:'):
        return next((m for m in g.get('mods', []) if m['id'] == rest[4:]), None)
    return next((r for r in g.get('routes', []) if r['id'] == rest), None)


def known_posts(games=None):
    """Alle Reddit-Beiträge mit ihren Zielen: id → {url, targets}."""
    games = games if games is not None else [read(f) for f in sorted((atlas.DATA / 'games').glob('*.json'))]
    posts = {}
    for g in games:
        for url, target in _refs(g):
            pid = post_id(url)
            if pid:
                e = posts.setdefault(pid, {'url': canonical(url), 'targets': []})
                if target not in e['targets']:
                    e['targets'].append(target)
    _, _, rd = _state()
    ids = {g['id'] for g in games}
    for pid, f in rd['found'].items():
        e = posts.setdefault(pid, {'url': f['url'], 'targets': []})
        e['targets'] += [t for t in f['targets'] if t.split('/')[0] in ids and t not in e['targets']]
    return posts


def pending(games=None, limit=300):
    """Abholliste für die App: noch nicht erledigte Beiträge, Dual-Screen-Wege und Wege ohne Bild zuerst."""
    games = games if games is not None else [read(f) for f in sorted((atlas.DATA / 'games').glob('*.json'))]
    by_id = {g['id']: g for g in games}
    _, _, rd = _state()
    out = []
    for pid, e in known_posts(games).items():
        if pid in rd['done'] and rd['done'][pid].get('status') != 'failed-retry':
            continue
        dual, fewest = False, MAX_SHOTS
        for t in e['targets']:
            h = holder_of(by_id[t.split('/')[0]], t) if t.split('/')[0] in by_id else None
            if h is None:
                continue
            dual = dual or any(f in ('dual-screen', 'two-screens') for f in h.get('features', []))
            fewest = min(fewest, len(h.get('screenshots', [])))
        out.append({'id': pid, 'url': e['url'], 'targets': e['targets'], 'dual': dual, '_shots': fewest})
    out.sort(key=lambda p: (not p['dual'], p['_shots'], p['id']))
    return [{k: v for k, v in p.items() if not k.startswith('_')} for p in out[:limit]]


def _rejected():
    path = atlas.DATA / 'media_state.json'
    return set((read(path) if path.exists() else {}).get('rejectedImages', []))


def apply(payload, log=print):
    """Rückmeldung des Geräts übernehmen. Gibt Berichtszeilen zurück."""
    import images
    if isinstance(payload, str):
        payload = json.loads(payload)
    path, st, rd = _state()
    files = {f.stem: f for f in (atlas.DATA / 'games').glob('*.json')}
    games = {gid: read(f) for gid, f in files.items()}
    posts = known_posts(list(games.values()))
    rejected = _rejected()
    device = str(payload.get('device') or 'Handheld')[:40]
    lines, touched, changes = [], set(), {}
    for item in payload.get('posts', [])[:60]:
        pid = post_id(item.get('post') or '') or str(item.get('id') or '').lower()
        if pid not in posts:
            lines.append(f'- {pid or "?"}: unbekannter Beitrag, ignoriert')
            continue
        e, status = posts[pid], item.get('status')
        done = rd['done'].get(pid, {})
        if status == 'failed':
            tries = done.get('tries', 0) + 1
            rd['done'][pid] = {'date': TODAY, 'status': 'failed' if tries >= MAX_TRIES else 'failed-retry', 'tries': tries}
            lines.append(f"- {e['url']}: Abruf fehlgeschlagen ({tries}/{MAX_TRIES})")
            continue
        if status in ('gone', 'no-images'):
            rd['done'][pid] = {'date': TODAY, 'status': status, 'added': 0}
            lines.append(f"- {e['url']}: {'gelöscht/entfernt' if status == 'gone' else 'keine Bilder'}")
            continue
        imgs = []
        for im in (item.get('images') or [])[:MAX_PER_POST]:
            url = str(im.get('url') or '').strip()     # so, wie es auf dem Gerät geladen hat – nicht umschreiben
            if IMAGE_HOSTS.match(url) and url not in rejected and not any(images.same_image(url, x) for x in imgs):
                imgs.append(url)
        author = re.sub(r'[^A-Za-z0-9_-]', '', str(item.get('author') or ''))[:30]
        title = re.sub(r'\s+', ' ', str(item.get('title') or '')).strip()[:80]
        credit = f'Reddit · u/{author}' if author else 'reddit.com'
        added = upgraded = 0
        for target in e['targets']:
            gid = target.split('/')[0]
            g = games.get(gid)
            h = holder_of(g, target) if g else None
            if h is None:
                continue
            shots = h.setdefault('screenshots', [])
            for url in imgs:
                mid = media_id(url)
                same = next((s for s in shots if s.get('url') == url or (mid and media_id(s.get('url')) == mid)), None)
                if same:
                    if better(url, same['url']):    # gleiche Aufnahme, bisher nur als verkleinerte Vorschau
                        same['url'] = url
                        upgraded += 1
                        touched.add(gid)
                    continue
                if len(shots) >= MAX_SHOTS:
                    break
                cap = title or (h.get('name') if h is not g else 'Originalspiel') or 'Screenshot'
                shots.append({'url': url, 'caption': cap, 'source': e['url'], 'credit': credit, 'check': 'reddit'})
                added += 1
                touched.add(gid)
                changes.setdefault(gid, []).append((h.get('name') if h is not g else g['title'], e['url']))
        rd['done'][pid] = {'date': TODAY, 'status': 'ok' if imgs else 'no-images', 'added': added, 'upgraded': upgraded}
        rd['found'].pop(pid, None)
        lines.append(f"- {e['url']}: {len(imgs)} Bild(er) gelesen, {added} neu, {upgraded} in Originalgröße ersetzt")
    for gid in touched:
        games[gid]['updatedAt'] = TODAY
        write(files[gid], games[gid])
    if changes:
        cl = read(atlas.DATA / 'changelog.json')
        for gid, items in changes.items():
            names = ', '.join(dict.fromkeys(n for n, _ in items))
            cl['entries'].insert(0, {'date': TODAY, 'type': 'screenshot-added', 'by': 'device', 'game': gid,
                                     'text': f'{len(items)} Bilder aus Reddit für {names} (vom {device} geladen, Prüfung folgt)',
                                     'url': items[0][1]})
        write(atlas.DATA / 'changelog.json', cl)
    write(path, st)
    log('\n'.join(lines) or '- keine Beiträge in der Rückmeldung')
    return lines


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'apply':
        apply(Path(sys.argv[2]).read_text(encoding='utf-8'))
        return 0
    for p in pending():
        print(f"{'DS ' if p['dual'] else '   '}{p['url']}  →  {', '.join(p['targets'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
