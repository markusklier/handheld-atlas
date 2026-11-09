#!/usr/bin/env python3
"""Resolve rebase conflicts in data/*.json by merging the JSON, not the text.

Several workflow runs (research requests, queue, watcher) may finish at the same time and all add entries to
changelog.json, inbox.json, queue.json … Git sees overlapping lines and gives up; here both sides are kept:

    python3 scripts/gitsync.py         # during a stopped rebase: merge every conflicted JSON file, stage it

Rules (3-way, base = common ancestor, theirs = what is on main already, mine = the commit being replayed):
- objects: keys merged recursively; a value changed on one side only wins; changed on both → mine
- lists of objects with "id" / "url" / "game": merged per item, items removed on one side stay removed,
  new items of mine come first (changelog: newest on top)
- other lists: same, items compared as a whole
"""
import json
import subprocess
import sys

KEYS = ('id', 'url', 'game')


def _key_fn(items):
    for k in KEYS:
        if items and all(isinstance(x, dict) and k in x for x in items):
            return lambda x, k=k: ('k', json.dumps(x[k], sort_keys=True))
    return lambda x: ('v', json.dumps(x, sort_keys=True, ensure_ascii=False))


def merge3(base, theirs, mine):
    if mine == base:
        return theirs
    if theirs == base or theirs == mine:
        return mine
    if isinstance(base, dict) and isinstance(theirs, dict) and isinstance(mine, dict):
        out = {}
        for k in list(theirs) + [k for k in mine if k not in theirs]:
            if k in theirs and k in mine:
                out[k] = merge3(base.get(k), theirs[k], mine[k])
            elif k in theirs:                     # mine deleted it?
                if k in base and base[k] == theirs[k]:
                    continue
                out[k] = theirs[k]
            else:
                if k in base and base[k] == mine[k]:
                    continue                      # theirs deleted it
                out[k] = mine[k]
        return out
    if isinstance(theirs, list) and isinstance(mine, list):
        base = base if isinstance(base, list) else []
        key = _key_fn(base + theirs + mine)
        b = {key(x): x for x in base}
        t = {key(x): x for x in theirs}
        m = {key(x): x for x in mine}
        new_mine = [x for x in mine if key(x) not in b and key(x) not in t]
        out = []
        for x in theirs:
            k = key(x)
            if k in b and k not in m and b[k] == x:
                continue                          # mine removed it (popped job, processed lead)
            out.append(merge3(b.get(k), x, m[k]) if k in m else x)
        return new_mine + out
    return mine


def conflicted():
    out = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=U'], capture_output=True, text=True, check=True).stdout
    return [p for p in out.split() if p]


def stage(n, path):
    r = subprocess.run(['git', 'show', f':{n}:{path}'], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def main():
    files = conflicted()
    if not files:
        print('gitsync: keine Konflikte')
        return 0
    for path in files:
        if not path.endswith('.json'):
            print(f'gitsync: {path} ist kein JSON – nicht automatisch lösbar')
            return 1
        base, theirs, mine = stage(1, path), stage(2, path), stage(3, path)
        if theirs is None or mine is None:      # deleted on one side: keep the surviving version
            merged = theirs if mine is None else mine
        else:
            merged = merge3(base if base is not None else {}, theirs, mine)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(merged, ensure_ascii=False, indent=2) + '\n')
        subprocess.run(['git', 'add', path], check=True)
        print(f'gitsync: {path} zusammengeführt')
    return 0


if __name__ == '__main__':
    sys.exit(main())
