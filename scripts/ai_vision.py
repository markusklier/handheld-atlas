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


def ask(game, item, shot, kind, token, model):
    variant = (f"Spielweg „{item['name']}“ ({item.get('kind')}, {item.get('runtime') or ''})"
               + (f"; zweiter Bildschirm soll zeigen: {item.get('dualScreen')}" if 'dual-screen' in item.get('features', []) else '')
               if kind == 'route' else f"Mod „{item['name']}“ ({item.get('category')})")
    text = (f"Prüfe dieses Bild für den Spielekatalog „Handheld Atlas“. Spiel: „{game['title']}“. Erwartet: {variant}. "
            f"Bisherige Bildunterschrift: „{shot.get('caption', '')}“. Beantworte: zeigt es dieses Spiel, zeigt es genau diese "
            "Variante/diesen Mod, welche Art Bild ist es, sind zwei Bildschirme (Dual Screen) zu sehen? captionDe: kurze, "
            "sachliche deutsche Bildunterschrift (max. 60 Zeichen), was zu sehen ist.")
    resp = call_openai({'model': model, 'text': {'format': FORMAT}, 'max_output_tokens': 800, 'reasoning': {'effort': 'low'},
                        'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': text},
                                                               {'type': 'input_image', 'image_url': shot['url']}]}]}, token)
    return output_json(resp)


def decide(verdict, shot):
    """Mutates shot; returns 'keep', 'drop' or 'unclear'."""
    if verdict['kind'] in ('logo', 'promo', 'diagram') or verdict['showsGame'] == 'no' or verdict['showsVariant'] == 'no':
        return 'drop'
    if verdict['showsGame'] == 'yes' and verdict['showsVariant'] in ('yes', 'unclear'):
        shot['check'] = 'ai-verified'
        if verdict.get('captionDe'):
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
    model = os.environ.get('OPENAI_VISION_MODEL') or os.environ.get('OPENAI_MODEL') or 'gpt-6.1-sol'
    stats = {'keep': 0, 'drop': 0, 'unclear': 0, 'error': 0}
    touched = {}
    for f, g, item, shot, kind in candidates():
        if sum(stats.values()) >= args.limit:
            break
        g = touched.get(f, g)
        # re-resolve item/shot inside the (possibly already modified) game object
        coll = g['routes'] if kind == 'route' else g['mods']
        item = next(x for x in coll if x['id'] == item['id'])
        shot = next((s for s in item.get('screenshots', []) if s['url'] == shot['url']), None)
        if not shot:
            continue
        try:
            result = decide(ask(g, item, shot, kind, token, model), shot)
        except Exception as e:  # noqa: BLE001 – unreachable image etc.
            print(f"! {g['id']}/{item['id']}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            shot['check'] = 'ai-unclear'
            stats['error'] += 1
            touched[f] = g
            continue
        stats[result] += 1
        if result == 'drop':
            item['screenshots'] = [s for s in item['screenshots'] if s['url'] != shot['url']]
        # dual-screen pictures first, then verified ones
        item['screenshots'].sort(key=lambda s: (not s.get('dual'), s.get('check') != 'ai-verified'))
        touched[f] = g
    for f, g in touched.items():
        write(f, g)
    problems = atlas.validate()
    if problems:
        print('Validierung fehlgeschlagen:', problems[:3])
        return 1
    print(f"ai_vision.py: {stats['keep']} bestätigt, {stats['drop']} entfernt, {stats['unclear']} unklar, {stats['error']} nicht ladbar")
    if touched:
        cl = read(DATA / 'changelog.json')
        cl['entries'].insert(0, {'date': date.today().isoformat(), 'type': 'screenshot-added', 'by': 'ai-research',
                                 'text': f"KI-Bildprüfung: {stats['keep']} Screenshots bestätigt, {stats['drop']} unpassende entfernt"})
        write(DATA / 'changelog.json', cl)
    return 0


if __name__ == '__main__':
    sys.exit(main())
