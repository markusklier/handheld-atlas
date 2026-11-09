import json
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ai_research  # noqa: E402
import atlas  # noqa: E402
import wikidata  # noqa: E402


def claim(prop_id, quals=None, time=None):
    snak = {'datavalue': {'value': {'time': time} if time else {'id': prop_id}}}
    c = {'mainsnak': snak}
    if quals:
        c['qualifiers'] = {'P400': [{'datavalue': {'value': {'id': q}}} for q in quals]}
    return c


def item(q, label, year_by_platform, series=None, kinds=('Q7889',), based=None, parts=None, wiki=None):
    claims = {'P31': [claim(k) for k in kinds], 'P400': [claim(p) for p in year_by_platform],
              'P577': [claim(None, [p], f'+{y}-06-01T00:00:00Z') for p, y in year_by_platform.items()],
              'P136': [claim('Q_FPS')]}
    if series:
        claims['P179'] = [claim(series)]
    if based:
        claims['P144'] = [claim(b) for b in based]
    if parts:
        claims['P527'] = [claim(x) for x in parts]
    return {'id': q, 'labels': {'en': {'value': label}}, 'claims': claims,
            'sitelinks': {'enwiki': {'title': wiki or label}} if wiki is not False else {}}


LABELS = {'Q_PC': 'Microsoft Windows', 'Q_DOS': 'MS-DOS', 'Q_PS1': 'PlayStation', 'Q_AND': 'Android', 'Q_IOS': 'iOS',
          'Q_SW': 'Nintendo Switch', 'Q_FPS': 'first-person shooter', 'Q7889': 'video game',
          'Q_EXP': 'expansion pack', 'Q_COMP': 'video game compilation'}


class FakeWikidata:
    def __init__(self, items, search, series_members):
        self.items, self.search, self.members = items, search, series_members

    def __call__(self, url, data=None):
        if data is not None:                                # SPARQL
            q = urllib.parse.parse_qs(data.decode())['query'][0]
            if 'VALUES ?label' in q:
                rows = [{'label': {'value': t}, 'item': {'value': f'http://www.wikidata.org/entity/{qid}'},
                         'y': {'value': str(y)}} for t, hits in self.search.items() if f'"{t}"@en' in q for qid, y in hits]
                return {'results': {'bindings': rows}}
            if 'wdt:P179|wdt:P361' in q:
                return {'results': {'bindings': [{'item': {'value': f'http://www.wikidata.org/entity/{m}'}} for m in self.members]}}
            return {'results': {'bindings': []}}
        ids = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['ids'][0].split('|')
        out = {}
        for i in ids:
            if i in self.items:
                out[i] = self.items[i]
            elif i in LABELS:
                out[i] = {'id': i, 'labels': {'en': {'value': LABELS[i]}}}
        return {'entities': out}


class WikidataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = (atlas.DATA, wikidata.DATA, wikidata.STATE, ai_research.DATA)
        atlas.DATA = wikidata.DATA = ai_research.DATA = self.tmp / 'data'
        wikidata.STATE = self.tmp / 'data' / 'wikidata_state.json'
        wikidata.STATE.unlink(missing_ok=True)
        q = lambda *a, **k: None
        ai_research.create_game('ZZ Quake', ['PC'], 'ZZ Quake', 1996, log=q)
        g = atlas.read(atlas.DATA / 'games' / 'zz-quake.json')
        g['versions'][0].pop('year', None)           # year unknown so far
        atlas.write(atlas.DATA / 'games' / 'zz-quake.json', g)
        self.items = {
            'Q1': item('Q1', 'ZZ Quake', {'Q_DOS': 1996, 'Q_SW': 2021, 'Q_AND': 2023}, series='QS'),
            'Q2': item('Q2', 'ZZ Quake II', {'Q_PC': 1997, 'Q_PS1': 1999}, series='QS'),
            'Q3': item('Q3', 'ZZ Quake Mission Pack', {'Q_PC': 1997}, series='QS', kinds=('Q_EXP',)),
            'Q4': item('Q4', 'ZZ Quake Remastered', {'Q_PC': 2021}, series='QS', based=['Q1']),
            'Q5': item('Q5', 'ZZ Quake Collection', {'Q_PC': 2001}, series='QS', kinds=('Q_COMP',), parts=['Q1', 'Q2']),
        }
        self.fake = FakeWikidata(self.items, {'ZZ Quake': [('Q1', 1996)]}, ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])

    def tearDown(self):
        atlas.DATA, wikidata.DATA, wikidata.STATE, ai_research.DATA = self.orig
        shutil.rmtree(self.tmp)

    def test_enrich_fills_years_versions_and_android(self):
        wikidata.enrich(10, self.fake, log=lambda *a: None, only={'zz-quake'})
        g = atlas.read(atlas.DATA / 'games' / 'zz-quake.json')
        self.assertEqual(g['wikidata'], 'Q1')
        self.assertEqual(g['versions'][0]['year'], 1996)                     # PC original got its year
        rows = {(v['type'], v['year'], tuple(v['platforms'])) for v in g['versions']}
        self.assertIn(('port', 2021, ('Nintendo Switch',)), rows)
        self.assertIn(('android', 2023, ('Android',)), rows)                  # → "Offizielle Android-App" in the app
        self.assertEqual(g['genre'], 'first-person shooter')
        self.assertEqual(g['wikipedia'], 'https://en.wikipedia.org/wiki/ZZ_Quake')
        self.assertEqual(atlas.validate(), [])

    def test_series_adds_games_versions_and_skips_expansions(self):
        g = atlas.read(atlas.DATA / 'games' / 'zz-quake.json')
        g['wikidata'] = 'Q1'
        atlas.write(atlas.DATA / 'games' / 'zz-quake.json', g)
        rep = wikidata.complete_series('ZZ Quake', self.fake, log=lambda *a: None)
        self.assertEqual(rep['added'], ['zz-quake-ii'])
        self.assertEqual([x['title'] for x in rep['skipped']], ['ZZ Quake Mission Pack'])
        q1 = atlas.read(atlas.DATA / 'games' / 'zz-quake.json')
        q2 = atlas.read(atlas.DATA / 'games' / 'zz-quake-ii.json')
        self.assertIn(('remaster', 'ZZ Quake Remastered (2021)'), [(v['type'], v['name']) for v in q1['versions']])
        self.assertIn('ZZ Quake Collection (2001)', [v['name'] for v in q1['versions']])     # compilation → both games
        self.assertIn('ZZ Quake Collection (2001)', [v['name'] for v in q2['versions']])
        self.assertEqual((q2['franchise'], q2['tier'], q2['platforms']), ('ZZ Quake', 'basis', ['PC']))
        self.assertEqual(atlas.validate(), [])
        again = wikidata.complete_series('ZZ Quake', self.fake, log=lambda *a: None)      # idempotent
        self.assertEqual((again['added'], again['versions']), ([], []))


if __name__ == '__main__':
    unittest.main()
