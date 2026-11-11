import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ai_research  # noqa: E402
import atlas  # noqa: E402


class ResearchModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = (atlas.DATA, ai_research.DATA)
        atlas.DATA = ai_research.DATA = self.tmp / 'data'
        self.env = dict(os.environ)
        self.argv = sys.argv
        for k in ('OPENAI_API_KEY', 'OPENAI_MONTHLY_BUDGET'):
            os.environ.pop(k, None)
        self.report = self.tmp / 'report.md'
        os.environ['RESEARCH_REPORT'] = str(self.report)

    def tearDown(self):
        atlas.DATA, ai_research.DATA = self.orig
        sys.argv = self.argv
        os.environ.clear()
        os.environ.update(self.env)
        shutil.rmtree(self.tmp)

    def run_issue(self, body, title='x'):
        sys.argv = ['ai_research.py', '--issue-body', body, '--issue-title', title]
        with redirect_stdout(io.StringIO()):
            ai_research.main()
        return self.report.read_text(encoding='utf-8')

    def test_without_key_a_research_request_is_handed_over(self):
        out = self.run_issue('game: doom-1993\n\nWas soll recherchiert werden? (optional)\nDroidDeck und GameHub fehlen', 'Recherche: DOOM')
        self.assertIn('An die Abo-Aufgabe übergeben', out)
        self.assertTrue(Path(str(self.report) + '.handover').exists())
        rm = atlas.read(atlas.DATA / 'research.json')
        self.assertEqual(rm['handovers'][0]['title'], 'Recherche: DOOM')

    def test_switch_backend_needs_no_ai(self):
        out = self.run_issue('research-backend: abo', 'Recherche-Modus: Abo')
        self.assertIn('Abo', out)
        self.assertEqual(atlas.read(atlas.DATA / 'research.json')['backend'], 'abo')
        self.assertFalse(Path(str(self.report) + '.handover').exists())
        self.assertFalse(atlas.validate())

    def test_abo_mode_hands_over_even_with_key(self):
        os.environ['OPENAI_API_KEY'] = 'sk-test'
        data = atlas.read(atlas.DATA / 'research.json')
        data['backend'] = 'abo'
        atlas.write(atlas.DATA / 'research.json', data)
        out = self.run_issue('update: doom-1993', 'Aktualisieren: DOOM')
        self.assertIn('Recherche-Modus „Abo“', out)

    def test_request_note(self):
        self.assertEqual(ai_research.request_note('game: doom-1993\n\nWas soll recherchiert werden? (optional)\nDroidDeck fehlt\n'), 'DroidDeck fehlt')
        self.assertEqual(ai_research.request_note('game: x\nversion: pc\n```json\n{}\n```'), '')


if __name__ == '__main__':
    unittest.main()
