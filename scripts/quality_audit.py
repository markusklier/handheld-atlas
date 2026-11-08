"""Generate honest per-game data-quality/coverage metadata (never a claim of catalog completeness)."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from sync_sources import ROOT, atomic_json, utcnow


def report(catalog, research):
    source_by_id={s['id']:s for s in catalog['sources']}
    candidates=research.get('candidates',[])
    recent={}
    for r in research.get('runs',[]):recent[r['gameId']]=r
    by_game=Counter(c.get('gameId') for c in candidates if c.get('status')=='pending-review')
    rows=[]
    for game in catalog.get('games',[]):
        routes=game['routes']
        missing=[r['id'] for r in routes if not r.get('media')]
        sources={sid for r in routes for sid in r.get('sources',[])}
        monitored=sum(1 for sid in sources if source_by_id.get(sid,{}).get('repo'))
        versioned=sum(1 for r in routes if r.get('requiredVersion'))
        run=recent.get(game['id'],{})
        rows.append({'gameId':game['id'],'title':game['title'],'cataloguedRoutes':len(routes),
          'dualScreenRoutes':sum('dual-screen' in r.get('features',[]) for r in routes),
          'routesWithPictures':len(routes)-len(missing),'missingPicturesRouteIds':missing,
          'routesWithVersionRequirements':versioned,'monitoredOriginalRepos':monitored,
          'pendingResearchCandidates':by_game[game['id']],
          'lastDeepResearchAt':run.get('checkedAt'),
          'researchMode':run.get('mode','not-run'),
          'coverageAssertion':'unknown; targeted searches cannot prove all variants were found'})
    return {'schemaVersion':1,'generatedAt':utcnow(),
       'catalogGames':len(catalog['games']),'watchlistOnlyGames':len(catalog.get('gameIndex',[])),
       'gamesWithPictures':sum(bool(any(r.get('media') for r in g['routes'])) for g in catalog['games']),
       'routesWithoutPictures':sum(len(x['missingPicturesRouteIds']) for x in rows),
       'pendingResearchCandidates':sum(by_game.values()),
       'notice':'Coverage is internal observation, not a proof that no other variants exist. Fixture-based research is NOT a live scan.',
       'games':rows}


def main():
    catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    research=json.loads((ROOT/'data/research_queue.json').read_text(encoding='utf-8'))
    output=report(catalog,research)
    atomic_json(ROOT/'data/quality_report.json',output)
    print('Quality report:',len(output['games']),'curated games;',output['routesWithoutPictures'],'routes without pictures')

if __name__=='__main__':main()
