import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import atlas  # noqa: E402
import ai_vision  # noqa: E402


class VisionTest(unittest.TestCase):
    def test_decide(self):
        shot = {'url': 'https://x/a.png', 'caption': 'a', 'check': 'readme'}
        self.assertEqual(ai_vision.decide({'showsGame': 'yes', 'showsVariant': 'yes', 'kind': 'second-screen-ui',
                                           'dualScreenVisible': True, 'captionDe': 'Karte unten'}, shot), 'keep')
        self.assertEqual((shot['check'], shot['caption'], shot['dual']), ('ai-verified', 'Karte unten', True))
        self.assertEqual(ai_vision.decide({'showsGame': 'unclear', 'showsVariant': 'yes', 'kind': 'logo',
                                           'dualScreenVisible': False, 'captionDe': ''}, {}), 'drop')
        s2 = {}
        self.assertEqual(ai_vision.decide({'showsGame': 'unclear', 'showsVariant': 'unclear', 'kind': 'gameplay',
                                           'dualScreenVisible': False, 'captionDe': ''}, s2), 'unclear')
        self.assertEqual(s2['check'], 'ai-unclear')

    def test_run_updates_files_and_stays_valid(self):
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, tmp / 'data')
        orig = (atlas.DATA, ai_vision.DATA)
        atlas.DATA = ai_vision.DATA = tmp / 'data'
        orig_ask = ai_vision.ask
        calls = []

        def fake_ask(game, item, shot, kind, token, model):
            calls.append(shot['url'])
            bad = len(calls) % 2 == 0
            return {'showsGame': 'no' if bad else 'yes', 'showsVariant': 'yes', 'kind': 'gameplay',
                    'dualScreenVisible': False, 'captionDe': 'Im Spiel'}
        ai_vision.ask = fake_ask
        ai_vision.check_link = lambda url: True
        import os
        os.environ['OPENAI_API_KEY'] = 'test'
        sys.argv = ['ai_vision.py', '--limit', '6']
        try:
            before = sum(1 for _ in ai_vision.candidates())
            self.assertEqual(ai_vision.main(), 0)
            after = sum(1 for _ in ai_vision.candidates())
            self.assertEqual(len(calls), min(6, before))
            self.assertEqual(after, before - len(calls))
            self.assertEqual(atlas.validate(), [])
        finally:
            ai_vision.ask = orig_ask
            ai_vision.check_link = None
            os.environ.pop('OPENAI_API_KEY', None)
            atlas.DATA, ai_vision.DATA = orig
            shutil.rmtree(tmp)


if __name__ == '__main__':
    unittest.main()
