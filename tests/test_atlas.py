import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402
import watch  # noqa: E402


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.db = atlas.load_db()

    def test_repository_data_is_valid(self):
        self.assertEqual(atlas.validate(self.db), [])

    def test_catches_unknown_feature_and_missing_project(self):
        db = copy.deepcopy(self.db)
        game = next(g for g in db['games'] if g.get('routes'))
        game['routes'][0]['features'] = ['teleport']
        game['routes'][0]['projects'] = ['does-not-exist']
        problems = '\n'.join(atlas.validate(db))
        self.assertIn("feature 'teleport'", problems)
        self.assertIn("'does-not-exist' fehlt", problems)

    def test_catches_duplicate_titles(self):
        db = copy.deepcopy(self.db)
        clone = copy.deepcopy(db['games'][0])
        clone['id'] = 'zz-clone'
        clone['_file'] = 'zz-clone.json'
        db['games'].append(clone)
        self.assertTrue(any('gleicher Titel' in p for p in atlas.validate(db)))

    def test_bundle_contains_everything_the_app_needs(self):
        data = atlas.bundle(self.db)
        for key in ('meta', 'games', 'projects', 'platforms', 'changelog', 'builtAt'):
            self.assertIn(key, data)
        self.assertFalse(any('_file' in g for g in data['games']))


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self._orig = watch.DATA
        watch.DATA = self.tmp / 'data'

    def tearDown(self):
        watch.DATA = self._orig
        shutil.rmtree(self.tmp)

    def fake_json(self, url, token=None):
        if '/search/repositories' in url:
            return {'items': [
                {'html_url': 'https://github.com/someone/new-dual-screen-port', 'full_name': 'someone/new-dual-screen-port',
                 'description': 'Dual screen port', 'fork': False},
                {'html_url': 'https://github.com/igawa6/eden-duo', 'full_name': 'igawa6/eden-duo', 'description': 'known'},
            ]}
        if url.endswith('/forks?sort=newest&per_page=30'):
            return [{'html_url': 'https://github.com/x/fork', 'full_name': 'x/fork', 'description': '',
                     'created_at': '2026-11-01T00:00:00Z', 'pushed_at': '2026-11-05T00:00:00Z'},
                    {'html_url': 'https://github.com/y/untouched', 'full_name': 'y/untouched',
                     'created_at': '2026-11-01T00:00:00Z', 'pushed_at': '2026-11-01T00:00:00Z'}]
        if 'modrinth' in url:
            return {'hits': [{'slug': 'second-screen-hud', 'title': 'HUD', 'project_type': 'mod'}]}
        if '/releases' in url:
            return [{'tag_name': 'v9.9.9', 'html_url': 'https://github.com/r/releases/v9.9.9',
                     'published_at': '2026-11-07T10:00:00Z', 'prerelease': False}]
        return {'archived': False, 'pushed_at': '2026-11-07T10:00:00Z'}

    def fake_text(self, url):
        return ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>New Thor dual screen mod</title>'
                '<link href="https://reddit.com/r/AYN/comments/abc"/></entry></feed>')

    def test_release_events_and_new_leads(self):
        w = watch.Watcher(fetch_json=self.fake_json, fetch_text=self.fake_text)
        w.check_projects()
        w.discover()
        w.save()
        inbox = atlas.read(watch.DATA / 'inbox.json')
        urls = [l['url'] for l in inbox['leads']]
        self.assertIn('https://github.com/someone/new-dual-screen-port', urls)
        self.assertIn('https://github.com/x/fork', urls)
        self.assertNotIn('https://github.com/y/untouched', urls)
        self.assertNotIn('https://github.com/igawa6/eden-duo', urls)  # already a known project
        self.assertIn('https://modrinth.com/mod/second-screen-hud', urls)
        self.assertIn('https://reddit.com/r/AYN/comments/abc', urls)
        changelog = atlas.read(watch.DATA / 'changelog.json')['entries']
        self.assertTrue(any('v9.9.9' in e['text'] for e in changelog))
        # second run: nothing new
        w2 = watch.Watcher(fetch_json=self.fake_json, fetch_text=self.fake_text)
        w2.check_projects()
        w2.discover()
        self.assertEqual((w2.new_leads, w2.new_events), (0, 0))

    def test_network_errors_are_not_fatal(self):
        def broken(*a, **k):
            raise OSError('offline')
        w = watch.Watcher(fetch_json=broken, fetch_text=broken)
        w.check_projects()
        w.discover()
        w.save()
        self.assertEqual(w.new_leads, 0)


if __name__ == '__main__':
    unittest.main()
