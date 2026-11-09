import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import images  # noqa: E402


class PageImagesTest(unittest.TestCase):
    def test_youtube(self):
        for u in ('https://www.youtube.com/watch?v=XdkeiIj2R4c', 'https://youtu.be/XdkeiIj2R4c?t=3', 'https://www.youtube.com/shorts/XdkeiIj2R4c'):
            self.assertEqual(images.images_from_page(u)[0]['url'], 'https://i.ytimg.com/vi/XdkeiIj2R4c/maxresdefault.jpg')

    def test_reddit_post_and_gallery(self):
        post = [{'data': {'children': [{'data': {'title': 'CTR on the Thor, map below', 'url_overridden_by_dest': 'https://i.redd.it/a.jpg',
                 'media_metadata': {'x': {'s': {'u': 'https://preview.redd.it/b.jpg?width=1080&amp;s=1'}}}}}]}}]
        got = images.images_from_page('https://www.reddit.com/r/AYN/comments/abc/ctr/', fetch=lambda u, as_json=False: post)
        self.assertEqual([x['url'] for x in got], ['https://i.redd.it/a.jpg', 'https://preview.redd.it/b.jpg?width=1080&s=1'])

    def test_wikipedia_skips_logos_and_small_files(self):
        api = {'query': {'pages': [
            {'title': 'File:Final Doom Coverart.png', 'imageinfo': [{'url': 'https://upload.wikimedia.org/c.png', 'mime': 'image/png', 'width': 300}]},
            {'title': 'File:Final Doom screenshot.png', 'imageinfo': [{'url': 'https://upload.wikimedia.org/s.png', 'mime': 'image/png', 'width': 640}]},
            {'title': 'File:Id Software logo.svg', 'imageinfo': [{'url': 'https://upload.wikimedia.org/l.svg', 'mime': 'image/svg+xml', 'width': 800}]},
            {'title': 'File:Tiny.png', 'imageinfo': [{'url': 'https://upload.wikimedia.org/t.png', 'mime': 'image/png', 'width': 40}]}]}}
        got = images.images_from_page('https://en.wikipedia.org/wiki/Final_Doom', fetch=lambda u, as_json=False: api)
        self.assertEqual([x['url'] for x in got], ['https://upload.wikimedia.org/c.png', 'https://upload.wikimedia.org/s.png'])

    def test_html_og_image_and_large_imgs(self):
        page = ('<meta property="og:image" content="https://site.example/hero.jpg"><img src="/shots/1.png" width="800">'
                '<img src="/logo.png" width="900"><img src="/thumb.jpg" width="80">')
        got = images.images_from_page('https://site.example/article', fetch=lambda u, as_json=False: page)
        self.assertEqual([x['url'] for x in got], ['https://site.example/hero.jpg', 'https://site.example/shots/1.png'])

    def test_steam_and_play(self):
        steam = {'2290': {'data': {'screenshots': [{'path_full': 'https://shared.steamstatic.com/a.jpg'}]}}}
        got = images.images_from_page('https://store.steampowered.com/app/2290/Final_DOOM/', fetch=lambda u, as_json=False: steam)
        self.assertEqual(got[0]['url'], 'https://shared.steamstatic.com/a.jpg')
        ids = ['A' * 30, 'B' * 30, 'C' * 30, 'D' * 30]
        html = ' '.join(f'https://play-lh.googleusercontent.com/{i}' for i in ids)
        got = images.images_from_page('https://play.google.com/store/apps/details?id=x', fetch=lambda u, as_json=False: html)
        self.assertEqual([x['url'] for x in got], [f'https://play-lh.googleusercontent.com/{i}=w1280-h720' for i in ids[2:]])

    def test_article_only_and_same_image(self):
        page = ('<html><head><meta property="og:image" content="https://b.example/hero.jpg"></head><body>'
                '<aside><img src="https://b.example/other-game.jpg"></aside><article><img src="https://b.example/ctr-dual.webp"></article></body>')
        got = images.images_from_page('https://b.example/post', fetch=lambda u, as_json=False: page)
        self.assertEqual([x['url'] for x in got], ['https://b.example/hero.jpg', 'https://b.example/ctr-dual.webp'])
        self.assertTrue(images.same_image('https://raw.githubusercontent.com/a/b/HEAD/s/x.png', 'https://raw.githubusercontent.com/a/b/main/s/x.png'))
        self.assertTrue(images.same_image('https://upload.wikimedia.org/c.png?utm_source=x', 'https://upload.wikimedia.org/c.png'))

    def test_unreadable_page_yields_nothing(self):
        def boom(u, as_json=False):
            raise OSError('403')
        self.assertEqual(images.images_from_page('https://site.example/x', fetch=boom, log=lambda *a: None), [])


if __name__ == '__main__':
    unittest.main()
