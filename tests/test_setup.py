import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402
import setup  # noqa: E402


def run(game='minecraft', avg=58.4, **kw):
    r = {'game': game, 'way': 'r:mc-exojosh', 'wayName': 'ExoJosh Dual Screen', 'version': 'java', 'app': 'eden',
         'package': 'dev.eden.eden_emulator', 'appVersion': '0.0.4', 'round': 1, 'target': 60, 'verdict': 'good', 'note': ' läuft  rund ',
         'variant': {'label': 'Start: Bericht vom Thor Max', 'source': 'https://www.emuready.com/listings/abc',
                     'settings': {'Resolution': '1x', 'Driver': 'Turnip 25.1'}},
         'result': {'seconds': 151.2, 'fps': {'avg': avg, 'low1': 47.9}, 'frameMs': {'p50': 16.7, 'p95': 19.1, 'p99': 24.0, 'max': 88.0},
                    'stutters': 3, 'refreshHz': 120, 'temp': {'skinMax': 41.5, 'cpuMax': 78.0, 'throttleStatus': 1},
                    'power': {'avgW': 9.4, 'plugged': False}, 'series': [60] * 150, 'diag': {'layer': 'SurfaceView[x]'}}}
    r.update(kw)
    return r


class SetupDataTest(unittest.TestCase):
    def test_setup_data_is_valid_and_bundled(self):
        db = atlas.load_db()
        self.assertEqual(setup.validate(db), [])
        b = atlas.bundle(db)['setup']
        self.assertEqual(b['devices'][0]['id'], 'ayn-thor-max')
        self.assertTrue(any(a['id'] == 'shizuku' for a in b['apps']))
        self.assertGreaterEqual(b['policy']['budget']['stopEur'], b['policy']['budget']['warnEur'])

    def test_every_platform_emulator_with_reports_has_an_app(self):
        """Emulatoren, die in Berichten oft vorkommen, kann der Assistent erkennen (Paketname hinterlegt)."""
        names = {n.lower() for a in setup.load()['apps'] if a.get('packages') for n in a.get('reportNames', [])}
        for emu in ('Eden', 'GameNative', 'PPSSPP', 'Dolphin', 'Azahar', 'DuckStation', 'NethersX2', 'Winlator', 'Vita3K'):
            self.assertIn(emu.lower(), names)


class SetupApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = atlas.DATA
        atlas.DATA = self.tmp / 'data'

    def tearDown(self):
        atlas.DATA = self.orig
        shutil.rmtree(self.tmp)

    def test_runs_are_stored_cleaned_and_logged(self):
        payload = {'kind': 'setup-report', 'device': 'ayn-thor-max', 'app': {'version': '0.1.7'}, 'runs': [
            run(), run(avg=61.0, round=2), run(game='gibt-es-nicht'), run(avg=99999), run(avg=None, verdict='broken', note='stürzt beim Start ab'),
            {**run(), 'result': {'seconds': 5, 'fps': {'avg': 60}}}]}
        lines = setup.apply(json.dumps(payload), log=lambda *a: None)
        runs = atlas.read(atlas.DATA / 'setup' / 'runs' / 'minecraft.json')['runs']
        self.assertEqual(len(runs), 3)                                   # unknown game, absurd fps and 5-second run dropped
        self.assertEqual(runs[0]['verdict'], 'broken')                   # newest first
        self.assertEqual(runs[1]['fps'], {'avg': 61.0, 'low1': 47.9})
        self.assertEqual(runs[2]['note'], 'läuft rund')
        self.assertEqual(runs[2]['device'], 'ayn-thor-max')
        self.assertEqual(runs[2]['variant']['settings']['Driver'], 'Turnip 25.1')
        self.assertNotIn('series', runs[2])                              # raw series and diagnostics stay on the device
        self.assertNotIn('diag', runs[2])
        self.assertTrue(any('unbekanntes Spiel' in x for x in lines))
        cl = atlas.read(atlas.DATA / 'changelog.json')['entries'][0]
        self.assertEqual((cl['game'], cl['by'], cl['type']), ('minecraft', 'device', 'verified'))
        self.assertIn('61', cl['text'])
        self.assertFalse(atlas.validate())

    def test_selftest_and_learned_packages(self):
        payload = {'device': 'ayn-thor-max', 'app': {'version': '0.1.7'},
                   'packages': {'azahar': 'org.azahar_emu.azahar', 'gibt-es-nicht': 'a.b', 'winlator': 'kein paket'},
                   'selftest': {'at': '2026-11-10T20:00:00Z', 'info': {'device': {'model': 'Thor'}},
                                'checks': [{'id': 'shizuku', 'name': 'Shizuku', 'ok': True, 'detail': 'bereit'},
                                           {'id': 'uinput', 'name': 'Virtuelles Gamepad', 'ok': False, 'detail': 'No such file'}]}}
        setup.apply(payload, log=lambda *a: None)
        s = setup.load()
        self.assertEqual(s['learned'], {'azahar': {'package': 'org.azahar_emu.azahar', 'date': s['learned']['azahar']['date']}})
        self.assertEqual([c['ok'] for c in s['selftest']['ayn-thor-max']['checks']], [True, False])
        self.assertEqual(setup.bundle()['selftest']['ayn-thor-max']['appVersion'], '0.1.7')
        self.assertFalse(atlas.validate())

    def test_issue_body_from_the_app_is_applied_without_ai(self):
        import io
        import os
        from contextlib import redirect_stdout
        import ai_research
        old = ai_research.DATA
        ai_research.DATA = atlas.DATA
        env = dict(os.environ)
        argv = sys.argv
        try:
            os.environ.pop('OPENAI_API_KEY', None)
            report = self.tmp / 'report.md'
            os.environ['RESEARCH_REPORT'] = str(report)
            body = 'setup-report: 1\n\nRückmeldung\n\n```json\n' + json.dumps({'device': 'ayn-thor-max', 'runs': [run()]}) + '\n```\n'
            sys.argv = ['ai_research.py', '--issue-body', body, '--issue-title', 'Setup-Rückmeldung']
            with redirect_stdout(io.StringIO()):
                ai_research.main()
            self.assertEqual(len(atlas.read(atlas.DATA / 'setup' / 'runs' / 'minecraft.json')['runs']), 1)
            self.assertIn('Setup-Assistenten übernommen', report.read_text(encoding='utf-8'))
        finally:
            sys.argv = argv
            os.environ.clear()
            os.environ.update(env)
            ai_research.DATA = old


if __name__ == '__main__':
    unittest.main()
