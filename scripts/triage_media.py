"""Combine variant media candidates into a deduplicated human-review queue.
No image download, automatic visual verification, hotlink publication, or licence assumption.
Pass a separate explicit game+route approval in editorial JSON before publishing.
"""
import hashlib
import json
from pathlib import Path
from sync_sources import ROOT, atomic_json, utcnow


def triage(research,eden,catalog):
    valid_games={g['id'] for g in catalog['games']}
    out={}
    for item in research.get('candidates',[]):
        gid=item.get('gameId')
        if gid not in valid_games:continue
        for m in item.get('mediaCandidates',[]):
            url=m.get('url')
            if not url or not url.startswith('https://'):continue
            key=hashlib.sha256((gid+'|'+url).encode()).hexdigest()[:20]
            out[key]={
              'id':key,'gameId':gid,'routeId':None,'url':url,'caption':m.get('caption',''),
              'sourceUrl':m.get('sourceUrl') or item['url'],'discoveredVia':item.get('provider','unknown'),
              'project':item.get('project',''), 'reviewStatus':'needs-game-route-visual-and-rights-review',
              'questions':['Is this an actual screenshot from THIS mod/variant?',
                           'Does the image show both displays or the claimed feature?',
                           'Is the version/edition of this picture correct?',
                           'Can the image be hotlinked or rehosted under its licence?']}
    for item in eden.get('candidates',[]):
        gid=item.get('gameId')
        if gid not in valid_games:continue
        url=item.get('url')
        if not url or not url.startswith('https://'):continue
        key=hashlib.sha256((gid+'|'+url).encode()).hexdigest()[:20]
        if key in out:continue
        out[key]={'id':key,'gameId':gid,'routeId':None,'url':url,'caption':item.get('caption',''),
          'sourceUrl':item.get('sourceUrl',''),'discoveredVia':'eden-duo-companions',
          'project':'Eden Duo Companions','reviewStatus':'needs-game-route-visual-and-rights-review',
          'questions':['Confirm this is for the correct companion route and game version.',
                       'Confirm usage/hotlink permission and attribution.']}
    return {'schemaVersion':1,'generatedAt':utcnow(),'items':sorted(out.values(),key=lambda x:(x['gameId'],x['project'],x['url'])),
      'notice':'These are only source URLs and metadata. No screenshot has been visually reviewed by this tool.'}


def main():
    research=json.loads((ROOT/'data/research_queue.json').read_text(encoding='utf-8'))
    eden=json.loads((ROOT/'data/media_candidates.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    output=triage(research,eden,catalog)
    atomic_json(ROOT/'data/media_review.json',output)
    print('Media candidates needing review:',len(output['items']))

if __name__=='__main__':main()
