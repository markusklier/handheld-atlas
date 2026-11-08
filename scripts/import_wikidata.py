"""Extend the watchlist-only index using Wikidata video-game platform facts.

Wikidata CC0 labels/IDs != proof of game playability or availability.
Always review duplicate editions before merging the changes. Does not touch
curated routes. Live mode does a single bounded per-platform query and respects
Wikimedia limits. Input fixture mode is offline and deterministic.

Examples:
  python3 scripts/import_wikidata.py --fixture docs/wikidata-fixture.json
  python3 scripts/import_wikidata.py --platform n64 --live
"""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from sync_sources import ROOT, atomic_json, utcnow

# Checked identifiers: add platforms here after manual verification.
PLATFORMS={'n64':('Nintendo 64','Q184839')}
QID=re.compile(r'^Q[1-9][0-9]{0,15}$')

def slugify(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')[:100]

def query(platform_qid,limit=1200):
    if not QID.fullmatch(platform_qid):raise ValueError('Bad Wikidata QID')
    limit=max(1,min(int(limit),1500))
    # P400 means 'developed/released on', NOT 'emulates well on this handheld'.
    return f'''SELECT ?item ?itemLabel ?seriesLabel WHERE {{
      ?item wdt:P400 wd:{platform_qid} .
      ?item wdt:P31 wd:Q7889 .
      OPTIONAL {{ ?item wdt:P179 ?series . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,de". }}
    }} LIMIT {limit}'''

def fetch(platform_qid):
    params=urllib.parse.urlencode({'query':query(platform_qid),'format':'json'})
    req=urllib.request.Request('https://query.wikidata.org/sparql?'+params,
      headers={'User-Agent':'HandheldAtlasResearch/0.2 (research-only; see github.com/igawa6/eden-duo)',
       'Accept':'application/sparql-results+json','Accept-Encoding':'identity'})
    try:
        with urllib.request.urlopen(req,timeout=30) as res:
            buf=res.read(5_000_001)
            if len(buf)>5_000_000:raise RuntimeError('Size cap')
            return json.loads(buf)
    except urllib.error.HTTPError as error:
        if error.code in (429,503):raise RuntimeError('Wikidata rate limited or unavailable; do not retry in a tight loop') from error
        raise

def extract(payload,platform):
    records={}
    for binding in payload.get('results',{}).get('bindings',[]):
        uri=binding.get('item',{}).get('value','')
        m=re.fullmatch(r'https://www\.wikidata\.org/entity/(Q[1-9]\d{0,15})',uri)
        if not m:continue
        qid=m.group(1)
        title=str(binding.get('itemLabel',{}).get('value','')).strip()[:170]
        if not title or re.fullmatch(r'Q\d+',title) or len(title)<2:continue
        series=str(binding.get('seriesLabel',{}).get('value','')).strip()[:120]
        if not series or re.fullmatch(r'Q\d+',series):series='Weitere Spiele'
        key='wikidata-'+qid.lower()
        records[key]={'id':key,'title':title,'franchise':series,'platforms':[platform],
             'wikidataId':qid,'source':'Wikidata CC0 / P400', 'unverified':True}
    return sorted(records.values(),key=lambda x:x['title'].lower())

def update_catalog(root,items):
    path=root/'data/catalog.json'
    catalog=json.loads(path.read_text(encoding='utf-8'))
    catalog.setdefault('gameIndex',[])
    knownQ={str(x.get('wikidataId')) for x in catalog['gameIndex'] if x.get('wikidataId')}
    # Keep source IDs stable; fuzzy matches to existing curated games require review.
    new=[x for x in items if x['wikidataId'] not in knownQ]
    existingids={g['id'] for g in catalog['games']} | {g['id'] for g in catalog['gameIndex']}
    new=[x for x in new if x['id'] not in existingids]
    catalog['gameIndex'].extend(new)
    catalog['gameIndex'].sort(key=lambda x:x['title'].casefold())
    catalog['indexSources']=catalog.get('indexSources',[])
    if 'Wikidata P400 (watchlist-index only)' not in catalog['indexSources']:
        catalog['indexSources'].append('Wikidata P400 (watchlist-index only)')
    atomic_json(path,catalog)
    return len(new)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform',choices=sorted(PLATFORMS),default='n64')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fixture',type=Path)
    mode.add_argument('--live',action='store_true')
    args=parser.parse_args()
    label,qid=PLATFORMS[args.platform]
    payload=json.loads(args.fixture.read_text()) if args.fixture else fetch(qid)
    items=extract(payload,label)
    added=update_catalog(ROOT,items)
    print('Wikidata watchlist index:',len(items),'found,',added,'new; never considered compatible, verified or installable')

if __name__=='__main__':main()
