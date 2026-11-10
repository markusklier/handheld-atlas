#!/usr/bin/env python3
"""Setup-Assistent: Daten für „Einrichten“ in der Atlas-App (docs/SETUP.md).

  data/setup/devices.json   unterstützte Geräte (zuerst nur AYN Thor Max) mit Chip-Klasse und Bildschirmen
  data/setup/apps.json      Apps, die der Assistent installieren/erkennen kann (Paketname, Quelle) – handverlesen
  data/setup/policy.json    Regeln für das Feintuning (Ziel, Abbruch, Kosten)
  data/setup/runs/<spiel>.json   Messfahrten vom Gerät (Atlas' eigene Performance-Daten)
  data/setup/selftest.json  letzter Selbsttest je Gerät (was die App auf dem Gerät wirklich kann)
  data/setup/learned.json   beim Installieren erkannte Paketnamen von Projekten

Das Gerät schickt ein Issue mit `setup-report:` und einem JSON-Block; `apply` übernimmt es ohne KI.

    python3 scripts/setup.py               # Überblick
    python3 scripts/setup.py apply x.json  # Rückmeldung lokal übernehmen (sonst macht das die Action)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402  (atlas.DATA zur Laufzeit lesen – Tests biegen es um)
from atlas import read, write  # noqa: E402

PACKAGE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$')
REPO_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
VERDICTS = {'good', 'ok', 'bad', 'broken'}
SOURCE_TYPES = {'github', 'play', 'page'}
MAX_RUNS = 40


def _dir():
    return atlas.DATA / 'setup'


def _read(name, default):
    path = _dir() / name
    return read(path) if path.exists() else default


def load():
    runs = {}
    rd = _dir() / 'runs'
    if rd.exists():
        for f in sorted(rd.glob('*.json')):
            runs[f.stem] = read(f).get('runs', [])
    return {
        'devices': _read('devices.json', {'devices': []})['devices'],
        'apps': _read('apps.json', {'apps': []})['apps'],
        'policy': _read('policy.json', {}),
        'runs': runs,
        'selftest': _read('selftest.json', {}),
        'learned': _read('learned.json', {'packages': {}})['packages'],
    }


def validate(db):
    """Probleme der Setup-Daten als Liste (leer = in Ordnung). `db` ist atlas.load_db()."""
    s = load()
    errors = []
    err = errors.append
    project_ids = {p['id'] for p in db['projects']}
    game_ids = {g['id'] for g in db['games']}
    platforms = set(db['platforms']) | {p for g in db['games'] for p in g.get('platforms', [])}
    meta_devices = {d['id'] for d in db['meta'].get('devices', [])}
    seen = set()
    for d in s['devices']:
        w = f"setup/devices.json/{d.get('id')}"
        if not ID_RE.match(d.get('id', '')) or d['id'] in seen:
            err(f'{w}: id ungültig oder doppelt')
        seen.add(d.get('id'))
        if d.get('metaDevice') not in meta_devices:
            err(f"{w}: metaDevice {d.get('metaDevice')!r} fehlt in meta.json devices")
        for k in ('name', 'chipClass', 'soc', 'ramGb', 'displays', 'reportNames'):
            if not d.get(k):
                err(f'{w}: {k} fehlt')
    seen = set()
    for a in s['apps']:
        w = f"setup/apps.json/{a.get('id')}"
        if not ID_RE.match(a.get('id', '')) or a['id'] in seen:
            err(f'{w}: id ungültig oder doppelt')
        seen.add(a.get('id'))
        if not a.get('name'):
            err(f'{w}: name fehlt')
        for p in a.get('packages', []):
            if not PACKAGE_RE.match(p):
                err(f'{w}: Paketname {p!r} ungültig')
        for p in a.get('projects', []):
            if p not in project_ids:
                err(f'{w}: Projekt {p!r} fehlt in projects.json')
        for p in a.get('platforms', []):
            if p not in platforms:
                err(f'{w}: Plattform {p!r} unbekannt')
        src = a.get('source')
        if src:
            if src.get('type') not in SOURCE_TYPES:
                err(f"{w}: source.type {src.get('type')!r} nicht in {sorted(SOURCE_TYPES)}")
            if src.get('type') == 'github' and not REPO_RE.match(src.get('repo', '')):
                err(f'{w}: source.repo ungültig')
            if src.get('type') == 'play' and not PACKAGE_RE.match(src.get('id', '')):
                err(f'{w}: source.id ungültig')
            if src.get('type') == 'page' and not str(src.get('url', '')).startswith('https://'):
                err(f'{w}: source.url muss mit https:// beginnen')
        if not a.get('packages') and not src:
            err(f'{w}: weder Paketname noch Quelle')
    pol = s['policy']
    for path in ('measure.seconds', 'stop.maxRounds', 'budget.warnEur', 'budget.stopEur'):
        cur = pol
        for k in path.split('.'):
            cur = cur.get(k) if isinstance(cur, dict) else None
        if not isinstance(cur, (int, float)):
            err(f'setup/policy.json: {path} fehlt')
    for gid, runs in s['runs'].items():
        if gid not in game_ids:
            err(f'setup/runs/{gid}.json: Spiel existiert nicht')
        for r in runs:
            if not isinstance(r.get('fps', {}).get('avg'), (int, float)) and r.get('verdict') != 'broken':
                err(f'setup/runs/{gid}.json: Messung ohne fps.avg')
    return errors


def bundle():
    s = load()
    return {'devices': s['devices'], 'apps': s['apps'], 'policy': s['policy'], 'runs': s['runs'], 'learned': s['learned'],
            'selftest': {k: {'at': v.get('at'), 'appVersion': v.get('appVersion')} for k, v in s['selftest'].items()}}


def _num(v, lo, hi):
    return round(float(v), 1) if isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi else None


def _text(v, n):
    return re.sub(r'\s+', ' ', str(v or '')).strip()[:n]


def _clean_run(r, device_ids, today):
    """Eine Messfahrt auf die erlaubten Felder und plausible Werte beschränken; None = verwerfen."""
    res = r.get('result') or {}
    fps, frame = res.get('fps') or {}, res.get('frameMs') or {}
    verdict = r.get('verdict') if r.get('verdict') in VERDICTS else None
    avg = _num(fps.get('avg'), 1, 1000)
    seconds = _num(res.get('seconds'), 1, 7200)
    if avg is None and verdict != 'broken':
        return None
    if avg is not None and (seconds or 0) < 20:
        return None
    out = {
        'date': today, 'device': r.get('device') if r.get('device') in device_ids else None,
        'way': _text(r.get('way'), 120), 'wayName': _text(r.get('wayName'), 80), 'version': _text(r.get('version'), 60),
        'app': _text(r.get('app'), 60), 'package': r.get('package') if PACKAGE_RE.match(str(r.get('package') or '')) else None,
        'appVersion': _text(r.get('appVersion'), 40), 'round': int(r['round']) if isinstance(r.get('round'), int) and 0 < r['round'] < 50 else 1,
        'target': int(r['target']) if isinstance(r.get('target'), int) and 10 <= r['target'] <= 240 else None,
        'verdict': verdict, 'note': _text(r.get('note'), 300),
    }
    if avg is not None:
        out['seconds'] = seconds
        out['fps'] = {'avg': avg, 'low1': _num(fps.get('low1'), 0.1, 1000)}
        out['frameMs'] = {k: _num(frame.get(k), 0.1, 60000) for k in ('p50', 'p95', 'p99', 'max')}
        out['stutters'] = int(res['stutters']) if isinstance(res.get('stutters'), int) and 0 <= res['stutters'] < 10 ** 6 else None
        out['refreshHz'] = int(res['refreshHz']) if isinstance(res.get('refreshHz'), int) and 20 <= res['refreshHz'] <= 480 else None
        temp, power = res.get('temp') or {}, res.get('power') or {}
        out['temp'] = {k: _num(temp.get(k), -20, 150) for k in ('cpuMax', 'gpuMax', 'skinMax', 'skinStart', 'skinEnd') if temp.get(k) is not None}
        if isinstance(temp.get('throttleStatus'), int):
            out['temp']['throttleStatus'] = max(0, min(6, temp['throttleStatus']))
        if _num(power.get('avgW'), 0.1, 100) is not None:
            out['powerW'] = _num(power.get('avgW'), 0.1, 100)
    var = r.get('variant') or {}
    settings = var.get('settings') if isinstance(var.get('settings'), dict) else {}
    out['variant'] = {'label': _text(var.get('label'), 80),
                      'source': var.get('source') if str(var.get('source') or '').startswith('https://') else None,
                      'settings': {_text(k, 60): _text(v, 120) for k, v in list(settings.items())[:60]}}
    if isinstance(var.get('changes'), list):
        out['variant']['changes'] = [_text(c, 160) for c in var['changes'][:10]]
    return {k: v for k, v in out.items() if v not in (None, '', {})}


def apply(payload, log=print):
    """Rückmeldung des Geräts übernehmen (Messfahrten, Selbsttest, erkannte Paketnamen). Gibt Berichtszeilen zurück."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    s = load()
    device_ids = {d['id'] for d in s['devices']}
    device = payload.get('device') if payload.get('device') in device_ids else None
    dev_name = next((d['name'] for d in s['devices'] if d['id'] == device), 'Gerät')
    games = {f.stem for f in (atlas.DATA / 'games').glob('*.json')}
    projects = {p['id'] for p in read(atlas.DATA / 'projects.json')['projects']}
    lines, changes = [], []
    (_dir() / 'runs').mkdir(parents=True, exist_ok=True)
    by_game = {}
    for r in (payload.get('runs') or [])[:40]:
        gid = r.get('game')
        if gid not in games:
            lines.append(f'- Messfahrt für unbekanntes Spiel {gid!r} ignoriert')
            continue
        clean = _clean_run({**r, 'device': r.get('device') or device}, device_ids, today)
        if not clean:
            lines.append(f'- {gid}: Messfahrt unvollständig oder unplausibel, ignoriert')
            continue
        by_game.setdefault(gid, []).append(clean)
    for gid, new in by_game.items():
        path = _dir() / 'runs' / f'{gid}.json'
        old = read(path)['runs'] if path.exists() else []
        write(path, {'game': gid, 'runs': (new[::-1] + old)[:MAX_RUNS]})
        best = max(new, key=lambda x: x.get('fps', {}).get('avg', 0))
        if best.get('fps'):
            text = (f"Messfahrt auf dem {dev_name}: {best.get('wayName') or best['way']} mit Ø {best['fps']['avg']:g} Bildern pro Sekunde"
                    + (f" (1 %-Low {best['fps']['low1']:g})" if best['fps'].get('low1') else '') + (f", {len(new)} Runden" if len(new) > 1 else ''))
        else:
            text = f"Auf dem {dev_name} ausprobiert: {best.get('wayName') or best['way']} läuft nicht ({best.get('note') or 'ohne Notiz'})"
        changes.append({'date': today, 'type': 'verified', 'by': 'device', 'game': gid, 'text': text})
        lines.append(f'- {gid}: {len(new)} Messfahrt(en) übernommen')
    learned = dict(s['learned'])
    for pid, pkg in list((payload.get('packages') or {}).items())[:40]:
        if pid in projects and PACKAGE_RE.match(str(pkg)) and learned.get(pid, {}).get('package') != pkg:
            learned[pid] = {'package': pkg, 'date': today}
            lines.append(f'- Paketname erkannt: {pid} → {pkg}')
    if learned != s['learned']:
        write(_dir() / 'learned.json', {'packages': learned})
    st = payload.get('selftest')
    if isinstance(st, dict) and device and isinstance(st.get('checks'), list):
        tests = dict(s['selftest'])
        tests[device] = {'at': _text(st.get('at'), 40), 'appVersion': _text((payload.get('app') or {}).get('version'), 20),
                         'info': st.get('info') if isinstance(st.get('info'), dict) else {},
                         'checks': [{'id': _text(c.get('id'), 30), 'name': _text(c.get('name'), 80), 'ok': bool(c.get('ok')),
                                     'detail': str(c.get('detail') or '')[:600]} for c in st['checks'][:30] if isinstance(c, dict)]}
        write(_dir() / 'selftest.json', tests)
        ok = sum(1 for c in tests[device]['checks'] if c['ok'])
        lines.append(f"- Selbsttest vom {dev_name} gespeichert: {ok}/{len(tests[device]['checks'])} Punkte in Ordnung")
    if changes:
        cl = read(atlas.DATA / 'changelog.json')
        cl['entries'] = changes + cl['entries']
        write(atlas.DATA / 'changelog.json', cl)
    log('\n'.join(lines) or '- nichts zu übernehmen')
    return lines


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'apply':
        apply(Path(sys.argv[2]).read_text(encoding='utf-8'))
        return 0
    s = load()
    print(f"Geräte: {', '.join(d['name'] for d in s['devices'])}")
    print(f"Apps: {len(s['apps'])} ({sum(1 for a in s['apps'] if a.get('source', {}).get('type') == 'github')} mit GitHub-Quelle)")
    print(f"Messfahrten: {sum(len(v) for v in s['runs'].values())} für {len(s['runs'])} Spiele")
    for dev, t in s['selftest'].items():
        print(f"Selbsttest {dev} ({t.get('at')}): " + ', '.join(f"{c['id']}={'ok' if c['ok'] else 'FEHLT'}" for c in t.get('checks', [])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
