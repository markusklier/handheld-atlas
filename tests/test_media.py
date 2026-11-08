import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402
import media  # noqa: E402

README = '''
# Chrono Duo
[![build](https://img.shields.io/badge/build-passing-green.svg)](x)
<img src="docs/logo.png" alt="logo">
![Battle with the menu on the bottom screen](docs/screenshots/battle.webp)
<img alt="Overworld map" src="https://github.com/me/chrono-duo/blob/main/docs/overworld.png" width="400">
![Powered by libultraship](docs/poweredbylus.lightmode.png)
![](https://github.com/user-attachments/assets/1234-abcd)
'''


class ReadmeImagesTest(unittest.TestCase):
    def test_extracts_screenshots_and_skips_badges_and_logos(self):
        imgs = media.readme_images(README, 'https://raw.githubusercontent.com/me/chrono-duo/HEAD/README.md', 'me/chrono-duo')
        urls = [i['url'] for i in imgs]
        self.assertIn('https://raw.githubusercontent.com/me/chrono-duo/HEAD/docs/screenshots/battle.webp', urls)
        self.assertIn('https://raw.githubusercontent.com/me/chrono-duo/main/docs/overworld.png', urls)
        self.assertIn('https://github.com/user-attachments/assets/1234-abcd', urls)
        self.assertFalse(any('shields.io' in u or 'logo' in u or 'poweredby' in u for u in urls))
        self.assertEqual(imgs[0]['alt'], 'Battle with the menu on the bottom screen')


class FillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self._orig = media.DATA
        media.DATA = self.tmp / 'data'
        (media.DATA / 'media_state.json').unlink(missing_ok=True)  # tests must not depend on earlier runs

    def tearDown(self):
        media.DATA = self._orig
        shutil.rmtree(self.tmp)

    def game(self, gid):
        return atlas.read(media.DATA / 'games' / f'{gid}.json')

    def test_route_shots_only_from_game_specific_projects(self):
        def fetch(url, as_json=False):
            if url.endswith('/README.md'):
                return README
            raise OSError('404')
        media.fill_route_shots(fetch)
        chrono = self.game('chrono-trigger')
        duo = next(r for r in chrono['routes'] if 'chrono' in r.get('projects', []))
        self.assertTrue(duo['screenshots'])
        self.assertTrue(all(s['check'] == 'readme' for s in duo['screenshots']))
        # generic emulators (Snes9x, RetroArch, Eden …) never receive README images
        sm = self.game('super-metroid')
        self.assertFalse(any(s.get('check') == 'readme' for r in sm['routes'] if r['projects'] == ['snes9x']
                             for s in r.get('screenshots', [])))

    def test_steam_cover_for_pc_games(self):
        target = next(g for g in (atlas.read(f) for f in (media.DATA / 'games').glob('*.json'))
                      if 'PC' in g.get('platforms', []) and not g.get('cover'))

        def fetch(url, as_json=False):
            if 'storesearch' in url:
                return {'items': [{'id': 4242, 'name': target['title'] + '™'}]}
            if 'appdetails' in url:
                return {'4242': {'success': True, 'data': {'header_image': 'https://cdn/header.jpg',
                        'screenshots': [{'path_full': 'https://cdn/ss1.jpg'}]}}}
            return {'items': []}
        original = media.urllib.request.urlopen
        media.urllib.request.urlopen = lambda *a, **k: None  # library art exists
        try:
            media.fill_steam(fetch, pause=0)
        finally:
            media.urllib.request.urlopen = original
        g = self.game(target['id'])
        self.assertIn('/apps/4242/library_600x900_2x.jpg', g['cover']['url'])
        self.assertEqual(g['cover']['source'], 'https://store.steampowered.com/app/4242/')

    def test_wikipedia_only_accepts_video_game_articles(self):
        def fetch(url, as_json=False):
            if 'Metroid+Dread' in url:
                return {'query': {'pages': [{'title': 'Metroid Dread', 'description': '2021 video game',
                                             'thumbnail': {'source': 'https://upload.wikimedia.org/dread.jpg'}}]}}
            return {'query': {'pages': [{'title': 'Something', 'description': 'River in Europe',
                                         'thumbnail': {'source': 'https://upload.wikimedia.org/river.jpg'}}]}}
        dread = self.game('metroid-dread')
        dread.pop('cover', None)
        atlas.write(media.DATA / 'games' / 'metroid-dread.json', dread)
        media.fill_wikipedia(fetch, pause=0, limit=1000)
        self.assertEqual(self.game('metroid-dread')['cover']['url'], 'https://upload.wikimedia.org/dread.jpg')
        self.assertNotIn('river', json.dumps([atlas.read(f).get('cover') for f in (media.DATA / 'games').glob('*.json')]))


if __name__ == '__main__':
    unittest.main()


class HttpImagesTest(unittest.TestCase):
    def test_http_images_are_skipped(self):
        text = '![shot](http://xproger.info/shots/a.jpg) ![ok](https://example.org/b.png)'
        urls = [i['url'] for i in media.readme_images(text, 'https://raw.githubusercontent.com/a/b/HEAD/README.md', 'a/b')]
        self.assertEqual(urls, ['https://example.org/b.png'])
