#!/usr/bin/env python3
"""KI-Bildprüfung für Spielweg- und Mod-Screenshots (OpenAI, Bild-Eingabe).

Prüft Bilder mit check "readme" (vom Watcher aus Projekt-READMEs) oder "ai" (von der KI-Recherche gefunden):
  - zeigt es dieses Spiel?  - zeigt es diese Variante (z. B. zweiter Bildschirm bei Dual-Screen-Wegen)?
  - ist es Logo / Werbegrafik / Menü eines anderen Spiels?
Ergebnis: passt → check "ai-verified" + deutsche Bildunterschrift; passt nicht → Bild entfernt;
unklar → check "ai-unclear" (der Pflege-Agent sieht es sich an). Dual-Screen-Bilder rücken nach vorn.

    python3 scripts/ai_vision.py [--limit 20]
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402
from atlas import DATA, read, write  # noqa: E402
from ai_research import call_openai, output_json  # noqa: E402

FORMAT = {'type': 'json_schema', 'name': 'atlas_image_check', 'strict': True, 'schema': {
    'type': 'object', 'additionalProperties': False,
    'required': ['showsGame', 'showsVariant', 'kind', 'dualScreenVisible', 'captionDe'],
    'properties': {
        'showsGame': {'type': 'string', 'enum': ['yes', 'no', 'unclear']},
        'showsVariant': {'type': 'string', 'enum': ['yes', 'no', 'unclear']},
        'kind': {'type': 'string', 'enum': ['gameplay', 'second-screen-ui', 'device-photo', 'menu', 'logo', 'promo', 'diagram', 'other']},
        'dualScreenVisible': {'type': 'boolean'},
        'captionDe': {'type': 'string'},
    }}}
TO_CHECK = {'readme', 'ai'}
check_link = None   # set in main(); tests replace it


def candidates():
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        for r in g.get('routes', []):
            for s in r.get('screenshots', []):
                if s.get('check') in TO_CHECK:
                    yield f, g, r, s, 'route'
        for m in g.get('mods', []):
            for s in m.get('screenshots', []):
                if s.get('check') in TO_CHECK:
                    yield f, g, m, s, 'mod'
        for s in g.get('screenshots', []):          # original-game pictures found by the AI image search
            if s.get('check') in TO_CHECK:
                yield f, g, g, s, 'game'
        if (g.get('cover') or {}).get('check') in TO_CHECK:
            yield f, g, g, g['cover'], 'cover'


def ask(game, item, shot, kind, token, model):
    if kind == 'route':
        variant = (f"Spielweg „{item['name']}“ ({item.get('kind')}, {item.get('runtime') or ''})"
                   + (f"; zweiter Bildschirm soll zeigen: {item.get('dualScreen')}" if 'dual-screen' in item.get('features', []) else ''))
    elif kind == 'mod':
        variant = f"Mod „{item['name']}“ ({item.get('category')})"
    elif kind == 'cover':
        variant = "Packungsgrafik/Cover oder offizielles Key-Art des Spiels (showsVariant = yes, wenn es ein Cover ist; kind dann 'promo' nur bei Werbebannern mit Preis/Text)"
    else:
        variant = (f"Spielszene aus „{game['title']}“ – egal welche Fassung (Original, Remaster, Portierung); "
                   "captionDe nennt bei erkennbar neuer Grafik die Fassung, z. B. „Remaster: …“")
    text =(f"Prüfe dieses Bild für den Spielekatalog „Handheld Atlas“. Spiel: „{game['title']}“. Erwartet: {variant}. "
            f"Bisherige Bildunterschrift: „{shot.get('caption', '')}“. Beantworte: zeigt es dieses Spiel, zeigt es genau diese "
            "Variante/diesen Mod, welche Art Bild ist es, sind zwei Bildschirme (Dual Screen) zu sehen? captionDe: kurze, "
            "sachliche deutsche Bildunterschrift (max. 60 Zeichen), was zu sehen ist.")
    resp = call_openai({'model': model, 'text': {'format': FORMAT}, 'max_output_tokens': 800, 'reasoning': {'effort': 'low'},
                        'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': text},
                                                               {'type': 'input_image', 'image_url': shot['url']}]}]}, token)
    return output_json(resp)


def reachable_image(url):
    """True if the URL really serves an image; dead or HTML links are dropped without asking the model."""
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'HandheldAtlas/1.2 (+https://github.com/markusklier/handheld-atlas)',
                                               'Range': 'bytes=0-2047'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.headers.get('Content-Type', '').startswith('image/')
    except Exception:  # noqa: BLE001
        return False


def decide(verdict, shot, kind='route'):
    """Mutates shot; returns 'keep', 'drop' or 'unclear'."""
    if kind == 'cover':   # box art is "promo"-like by nature; only the game match matters
        verdict = dict(verdict, kind='gameplay' if verdict['kind'] == 'promo' else verdict['kind'])
    if kind == 'game':    # original-game gallery: any edition of the game helps ("what is this game?")
        verdict = dict(verdict, showsVariant='yes' if verdict['showsGame'] == 'yes' else verdict['showsVariant'])
    if verdict['kind'] == 'promo' and verdict['showsGame'] == 'yes' and verdict['showsVariant'] == 'yes':
        verdict = dict(verdict, kind='gameplay')   # video thumbnails with title text still show the real thing
    if verdict['kind'] in ('logo', 'promo', 'diagram') or verdict['showsGame'] == 'no' or verdict['showsVariant'] == 'no':
        return 'drop'
    if verdict['showsGame'] == 'yes' and verdict['showsVariant'] in ('yes', 'unclear'):
        shot['check'] = 'ai-verified'
        if verdict.get('captionDe') and kind != 'cover':
            shot['caption'] = verdict['captionDe'][:80]
        if verdict.get('dualScreenVisible'):
            shot['dual'] = True
        return 'keep'
    shot['check'] = 'ai-unclear'
    return 'unclear'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=20)
    args = ap.parse_args()
    token = os.environ.get('OPENAI_API_KEY')
    if not token:
        print('OPENAI_API_KEY fehlt – keine Bildprüfung.')
        return 0
    global check_link
    check_link = check_link or reachable_image
    model = os.environ.get('OPENAI_VISION_MODEL') or os.environ.get('OPENAI_MODEL') or 'gpt-6.1-sol'
    stats = {'keep': 0, 'drop': 0, 'unclear': 0, 'error': 0}
    state_path = DATA / 'media_state.json'
    state = read(state_path) if state_path.exists() else {}
    rejected = set(state.get('rejectedImages', []))
    touched = {}
    for f, g, item, shot, kind in candidates():
        if sum(stats.values()) >= args.limit:
            break
        g = touched.get(f, g)
        # re-resolve item/shot inside the (possibly already modified) game object
        if kind in ('game', 'cover'):
            item = g
        else:
            coll = g['routes'] if kind == 'route' else g['mods']
            item = next(x for x in coll if x['id'] == item['id'])
        if kind == 'cover':
            shot = g.get('cover') if (g.get('cover') or {}).get('url') == shot['url'] else None
        else:
            shot = next((s for s in item.get('screenshots', []) if s['url'] == shot['url']), None)
        if not shot:
            continue

        def remove():
            if kind == 'cover':
                g.pop('cover', None)
            else:
                item['screenshots'] = [x for x in item['screenshots'] if x['url'] != shot['url']]
            rejected.add(shot['url'])   # media.py / the AI must not re-add it tomorrow
        if not check_link(shot['url']):
            stats['drop'] += 1
            remove()
            touched[f] = g
            continue
        try:
            verdict = ask(g, item, shot, kind, token, model)
            result = decide(verdict, shot, kind)
        except Exception as e:  # noqa: BLE001 – unreachable image etc.
            print(f"! {g['id']}/{item['id']}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            shot['check'] = 'ai-unclear'
            stats['error'] += 1
            touched[f] = g
            continue
        stats[result] += 1
        print(f"  {result:7} {g['id']}/{item.get('id') if kind in ('route', 'mod') else kind} "
              f"[Spiel {verdict['showsGame']}, Variante {verdict['showsVariant']}, {verdict['kind']}]: {shot['url'][:90]}", file=sys.stderr)
        if result == 'drop':
            remove()
        if kind in ('route', 'mod'):   # dual-screen pictures first, then verified ones
            item['screenshots'].sort(key=lambda s: (not s.get('dual'), s.get('check') != 'ai-verified'))
        touched[f] = g
    for f, g in touched.items():
        write(f, g)
    state['rejectedImages'] = sorted(rejected)
    write(state_path, state)
    problems = atlas.validate()
    if problems:
        print('Validierung fehlgeschlagen:', problems[:3])
        return 1
    from ai_research import USAGE
    print(f"ai_vision.py: {stats['keep']} bestätigt, {stats['drop']} entfernt, {stats['unclear']} unklar, {stats['error']} nicht ladbar"
          f" · OpenAI: {USAGE['calls']} Anfragen, {USAGE['input']:,} Eingabe-/{USAGE['output']:,} Ausgabe-Tokens ({model})")
    if touched:
        cl = read(DATA / 'changelog.json')
        cl['entries'].insert(0, {'date': date.today().isoformat(), 'type': 'screenshot-added', 'by': 'ai-research',
                                 'text': f"KI-Bildprüfung: {stats['keep']} Screenshots bestätigt, {stats['drop']} unpassende entfernt"})
        write(DATA / 'changelog.json', cl)
    return 0


if __name__ == '__main__':
    sys.exit(main())
