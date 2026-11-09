import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402
import reddit  # noqa: E402

POST = 'https://www.reddit.com/r/AynThor/comments/zz9abc/zz_dual_screen_mod_on_the_thor/'


class RedditUrlTest(unittest.TestCase):
    def test_post_ids(self):
        self.assertEqual(reddit.post_id(POST), 'zz9abc')
        self.assertEqual(reddit.post_id('https://old.reddit.com/comments/zz9abc'), 'zz9abc')
        self.assertEqual(reddit.post_id('https://redd.it/zz9abc'), 'zz9abc')
        self.assertIsNone(reddit.post_id('https://i.redd.it/abcdefgh1234.jpg'))
        self.assertIsNone(reddit.post_id('https://www.reddit.com/r/AynThor/'))
        self.assertEqual(reddit.canonical(POST + '?utm_source=share'), 'https://www.reddit.com/r/AynThor/comments/zz9abc/')

    def test_media_ids_and_better_address(self):
        prev = 'https://preview.redd.it/some-title-v0-xp1sgpm1sdih1.jpeg?auto=webp&s=d8&width=640'
        self.assertEqual(reddit.media_id(prev), 'xp1sgpm1sdih1')
        self.assertEqual(reddit.media_id('https://i.redd.it/xp1sgpm1sdih1.jpg'), 'xp1sgpm1sdih1')
        self.assertTrue(reddit.better('https://i.redd.it/xp1sgpm1sdih1.jpg', prev))
        self.assertTrue(reddit.better('https://preview.redd.it/xp1sgpm1sdih1.jpeg?s=1', prev))
        self.assertFalse(reddit.better(prev, 'https://i.redd.it/xp1sgpm1sdih1.jpg'))


class RedditApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = atlas.DATA
        atlas.DATA = self.tmp / 'data'
        atlas.write(atlas.DATA / 'games' / 'zz-dual-test.json', {
            'id': 'zz-dual-test', 'title': 'ZZ Dual Test', 'franchise': 'ZZ Test', 'platforms': ['PC'],
            'versions': [{'id': 'pc', 'name': 'PC (2020)', 'type': 'original', 'platforms': ['PC']}],
            'routes': [
                {'id': 'ds', 'name': 'ZZ Dual Screen', 'release': 'pc', 'kind': 'companion', 'features': ['dual-screen'],
                 'targets': ['android'], 'verification': 'ai-unverified', 'links': [{'label': 'Beitrag', 'url': POST}],
                 'screenshots': [{'url': 'https://preview.redd.it/zz-title-v0-aaaabbbbcccc1.jpeg?width=640&s=1', 'caption': 'alt',
                                  'source': POST, 'check': 'ai-verified'}]},
                {'id': 'plain', 'name': 'ZZ Plain', 'release': 'pc', 'kind': 'native', 'targets': ['android'],
                 'verification': 'ai-unverified', 'reports': [{'url': 'https://www.reddit.com/r/SBCGaming/comments/zz9def/x/',
                                                              'device': 'AYN Thor', 'summary': 'Läuft.'}], 'projects': [],
                 'links': [{'label': 'Projekt', 'url': 'https://github.com/example/zz'}]}],
            'mods': [], 'updatedAt': '2026-01-01'})

    def tearDown(self):
        atlas.DATA = self.orig
        shutil.rmtree(self.tmp)

    def test_pending_lists_dual_screen_first(self):
        pend = [p for p in reddit.pending() if p['id'] in ('zz9abc', 'zz9def')]
        self.assertEqual([p['id'] for p in pend], ['zz9abc', 'zz9def'])
        self.assertTrue(pend[0]['dual'])
        self.assertEqual(pend[0]['targets'], ['zz-dual-test/ds'])

    def test_blocked_posts_from_the_image_search_are_remembered(self):
        reddit.remember(['https://www.reddit.com/r/AM2R/comments/zz9ghi/foo/'], 'zz-dual-test/plain')
        p = next(p for p in reddit.pending() if p['id'] == 'zz9ghi')
        self.assertEqual(p['targets'], ['zz-dual-test/plain'])

    def test_device_report_adds_and_upgrades_pictures(self):
        payload = {'kind': 'reddit-images', 'device': 'AYN Thor', 'posts': [
            {'post': POST, 'status': 'ok', 'title': 'Dual screen mod on the Thor', 'author': 'zzauthor', 'images': [
                {'url': 'https://i.redd.it/aaaabbbbcccc1.jpg', 'w': 1920, 'h': 1080},
                {'url': 'https://i.redd.it/aaaabbbbcccc2.png', 'w': 1280, 'h': 720},
                {'url': 'https://evil.example/x.jpg'}]},
            {'post': 'https://www.reddit.com/r/SBCGaming/comments/zz9def/', 'status': 'gone'},
            {'post': 'https://www.reddit.com/r/Other/comments/unknown1/', 'status': 'ok', 'images': [{'url': 'https://i.redd.it/zzzzzzzzzzzz.jpg'}]}]}
        reddit.apply(json.dumps(payload), log=lambda *a: None)
        g = atlas.read(atlas.DATA / 'games' / 'zz-dual-test.json')
        shots = g['routes'][0]['screenshots']
        self.assertEqual([s['url'] for s in shots], ['https://i.redd.it/aaaabbbbcccc1.jpg', 'https://i.redd.it/aaaabbbbcccc2.png'])
        self.assertEqual(shots[0]['check'], 'ai-verified')            # upgraded in place, check kept
        self.assertEqual(shots[1]['check'], 'reddit')                 # new → KI-Bildprüfung
        self.assertEqual(shots[1]['credit'], 'Reddit · u/zzauthor')
        self.assertEqual(g['routes'][1].get('screenshots', []), [])
        ids = [p['id'] for p in reddit.pending()]
        self.assertNotIn('zz9abc', ids)
        self.assertNotIn('zz9def', ids)
        self.assertFalse(atlas.validate())
        cl = atlas.read(atlas.DATA / 'changelog.json')['entries'][0]
        self.assertEqual((cl['game'], cl['by'], cl['type']), ('zz-dual-test', 'device', 'screenshot-added'))

    def test_failed_fetches_are_retried_then_given_up(self):
        for _ in range(reddit.MAX_TRIES - 1):
            reddit.apply({'posts': [{'post': POST, 'status': 'failed'}]}, log=lambda *a: None)
            self.assertIn('zz9abc', [p['id'] for p in reddit.pending()])
        reddit.apply({'posts': [{'post': POST, 'status': 'failed'}]}, log=lambda *a: None)
        self.assertNotIn('zz9abc', [p['id'] for p in reddit.pending()])

    def test_issue_body_from_the_app_is_applied_without_ai(self):
        import ai_research
        old = ai_research.DATA
        ai_research.DATA = atlas.DATA
        try:
            payload = {'posts': [{'post': POST, 'status': 'ok', 'title': 't', 'images': [{'url': 'https://i.redd.it/aaaabbbbcccc3.jpg'}]}]}
            body = 'reddit-images: 1\n\nAutomatische Rückmeldung\n\n```json\n' + json.dumps(payload) + '\n```\n'
            env = dict(__import__('os').environ)
            __import__('os').environ.pop('OPENAI_API_KEY', None)
            argv, sys.argv = sys.argv, ['ai_research.py', '--issue-body', body, '--issue-title', 'Reddit-Bilder vom Gerät']
            report = self.tmp / 'report.md'
            __import__('os').environ['RESEARCH_REPORT'] = str(report)
            try:
                from contextlib import redirect_stdout
                import io
                with redirect_stdout(io.StringIO()):
                    ai_research.main()
            finally:
                sys.argv = argv
                __import__('os').environ.clear()
                __import__('os').environ.update(env)
            urls = [s['url'] for s in atlas.read(atlas.DATA / 'games' / 'zz-dual-test.json')['routes'][0]['screenshots']]
            self.assertIn('https://i.redd.it/aaaabbbbcccc3.jpg', urls)
            self.assertIn('Reddit-Bilder vom Gerät übernommen', report.read_text(encoding='utf-8'))
        finally:
            ai_research.DATA = old


if __name__ == '__main__':
    unittest.main()
