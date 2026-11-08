"""Discovery of NEW GitHub repos via approved search queries; never auto-publish.
Use --fixture JSON for deterministic tests/no external access. A GitHub token is recommended on CI.
Search API rate limiting and abuse policies apply; requires review before making any claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from sync_sources import ROOT, atomic_json, utcnow, add_candidates, ApiError

QUERIES=[
 'topic:ayn-thor',
 '"dual-screen" android emulator in:name,description,readme',
 '"eden duo" companion in:name,description,readme',
 '"android port" game in:name,description',
 '"minecraft" "second screen" in:name,description,readme',
]


def candidates_from_search(results,now):
    output=[]
    for result in results:
        if not isinstance(result,dict):continue
        repo=result.get('full_name')
        if not isinstance(repo,str) or '/' not in repo or len(repo)>120:continue
        url='https://github.com/'+repo
        desc=str(result.get('description') or '')[:260]
        pushed=result.get('pushed_at') or ''
        text=(repo+' '+desc+' '+ ' '.join(result.get('topics') or [])).lower()
        terms=('dual','thor','handheld','emulat','retro','port','companion','recomp','android','minecraft')
        relevance=sum(t in text for t in terms)
        if relevance<1:continue
        output.append({'url':url,'repo':repo,'label':desc[:110] or repo,'score':relevance,'pushedAt':pushed})
    return output


def fetch_search(q,token=None):
    query=urllib.parse.urlencode({'q':q,'sort':'updated','order':'desc','per_page':30})
    url='https://api.github.com/search/repositories?'+query
    headers={'User-Agent':'HandheldAtlasResearch/0.2','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            payload=r.read(2_000_001)
            if len(payload)>2_000_000:raise ApiError('Response size exceeded')
            result=json.loads(payload)
            return result.get('items',[])
    except urllib.error.HTTPError as e:
        if e.code in (403,429):raise ApiError('GitHub search rate limited; stop and retry later') from e
        raise ApiError(f'GitHub HTTP {e.code}') from e


def update_state(payload,queries=QUERIES,root=ROOT):
    catalog=json.loads((root/'data/catalog.json').read_text(encoding='utf-8'))
    path=root/'data/candidates.json'
    state=json.loads(path.read_text(encoding='utf-8'))
    known={s['repo'].lower() for s in catalog['sources'] if s.get('repo')}
    now=utcnow()
    n=0
    for q in queries:
        page=payload.get(q,[])
        links=candidates_from_search(page,now)
        n+=add_candidates(state,links,'github-search','https://github.com/search?q='+urllib.parse.quote(q),known,now)
    # After dedup, keep a short triage hint, but never mark any finding as tested.
    state['candidates'].sort(key=lambda x:x.get('discoveredAt',''),reverse=True)
    state['lastRepositorySearchAt']=now
    atomic_json(path,state)
    return n


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fixture',type=Path,help='JSON object {search query:[GitHub API items]} for offline tests')
    args=ap.parse_args()
    if args.fixture:
        data=json.loads(args.fixture.read_text(encoding='utf-8'))
    else:
        data={}
        for q in QUERIES:
            try:
                data[q]=fetch_search(q,os.getenv('GITHUB_TOKEN'))
            except ApiError as e:
                print('STOP',str(e));return 1
            time.sleep(2.0)
    added=update_state(data)
    print('New discovery candidates:',added,'; no catalog entries auto-approved')
    return 0

if __name__=='__main__':raise SystemExit(main())
