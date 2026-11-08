"""Deterministic offline tests. No network calls or credentials needed."""
import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sync_sources import extract_links, canonical_project_url, metadata_events, add_candidates, sync, ApiError, RateLimited
from validate import validate

ROOT=Path(__file__).resolve().parents[1]

class FakeAPI:
    def __init__(self, release='v1', fail=False, limited=False):
        self.release,self.fail,self.limited=release,fail,limited
        self.calls=[]
    def get(self,path,allow_404=False):
        self.calls.append(path)
        if self.limited: raise RateLimited('HTTP 429')
        if self.fail: raise ApiError('Network unavailable')
        if path.endswith('/releases/latest'):
            return {'id':self.release,'tag_name':self.release,'published_at':'2026-01-02T00:00:00Z'}
        if path.endswith('/readme'):
            body='[Port](https://github.com/example/port?utm_source=test)\n[Other](https://github.com/example/port)'
            return {'sha':'abc','encoding':'base64','content':base64.b64encode(body.encode()).decode()}
        return {'default_branch':'main','archived':False,'license':{'spdx_id':'MIT'}}
    def save_cache(self): pass

class PipelineTests(unittest.TestCase):
    def test_catalog(self):
        self.assertEqual(validate(json.loads((ROOT/'data/catalog.json').read_text())),(41,60,41))
    def test_unsupported_fps_claim_rejected(self):
        d=json.loads((ROOT/'data/catalog.json').read_text())
        d['games'][0]['routes'][0]['features'].append('fps60-tested')
        with self.assertRaises(AssertionError): validate(d)
    def test_extract_dedup_and_reject_unsafe_links(self):
        text='[A](https://github.com/a/b?utm_source=chatgpt.com) [Again](https://github.com/a/b) https://github.com/sponsors/a https://github.com/a/b/issues/2 https://evil.example/x/y'
        links=extract_links(text)
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]['url'],'https://github.com/a/b')
        self.assertIsNone(canonical_project_url('https://token@github.com/a/b'))
        self.assertIsNone(canonical_project_url('http://github.com/a/b'))
    def test_documents_in_same_repo_remain_separate_review_candidates(self):
        links=extract_links('https://github.com/a/b/blob/main/games/one.md https://github.com/a/b/blob/main/games/two.md')
        self.assertEqual(len(links),2)
    def test_baseline_is_not_news(self):
        current={'repo':'a/b','url':'https://github.com/a/b','archived':False,'latestRelease':{'id':'1','tag':'v1','url':'https://github.com/a/b/releases/tag/v1','publishedAt':'2026-01-01'}}
        self.assertEqual(metadata_events(None,current,'2026-01-02'),[])
        updated=copy.deepcopy(current);updated['latestRelease']['id']='2';updated['latestRelease']['tag']='v2'
        events=metadata_events(current,updated,'2026-01-03')
        self.assertEqual(len(events),1);self.assertFalse(events[0]['reviewed'])
    def test_candidates_never_auto_approved_and_dedup_preserves_provenance(self):
        state={'candidates':[]}; links=[{'url':'https://github.com/a/b','repo':'a/b','label':'B'}]
        self.assertEqual(add_candidates(state,links,'list1','https://github.com/x/list1',set(),'2026-01-01'),1)
        self.assertEqual(add_candidates(state,links,'list2','https://github.com/x/list2',set(),'2026-01-02'),0)
        self.assertEqual(state['candidates'][0]['status'],'pending')
        self.assertEqual(len(state['candidates'][0]['sourceIds']),2)
    def fixture(self,root):
        (root/'data').mkdir()
        catalog={'sources':[{'id':'project','repo':'a/b','role':'primary','url':'https://github.com/a/b','name':'B'},{'id':'dual-list','repo':'x/list','role':'discovery','url':'https://github.com/x/list','name':'List'}]}
        (root/'data/catalog.json').write_text(json.dumps(catalog))
        return (root/'data/catalog.json').read_bytes()
    def test_sync_integration_with_fake_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); original=self.fixture(root)
            self.assertEqual(sync(root,FakeAPI()),0)
            first=json.loads((root/'data/updates.json').read_text())
            self.assertEqual(first['events'],[])
            self.assertEqual(len(json.loads((root/'data/candidates.json').read_text())['candidates']),1)
            self.assertEqual(sync(root,FakeAPI(release='v2')),0)
            state=json.loads((root/'data/updates.json').read_text())
            self.assertEqual(len(state['events']),1)
            self.assertEqual((root/'data/catalog.json').read_bytes(),original)
    def test_network_failure_preserves_existing_success_and_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);sync(root,FakeAPI())
            before=json.loads((root/'data/updates.json').read_text())
            self.assertEqual(sync(root,FakeAPI(fail=True)),1)
            after=json.loads((root/'data/updates.json').read_text())
            self.assertEqual(after['projects'],before['projects'])
            self.assertEqual(after['lastSuccessAt'],before['lastSuccessAt'])
            self.assertTrue(after['errors'])
    def test_rate_limit_stops_future_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);api=FakeAPI(limited=True)
            self.assertEqual(sync(root,api),1)
            self.assertEqual(len(api.calls),1)
    def test_partial_run_not_full_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);sync(root,FakeAPI(),selected=['project'])
            self.assertIsNone(json.loads((root/'data/updates.json').read_text())['lastSuccessAt'])

if __name__=='__main__': unittest.main()
