"""Per-game multi-source discovery and evidence queue, NOT an auto-publisher.

Python 3.10+, standard library. Only curated API endpoints are fetched. External
project documents are untrusted text, never executable instructions. Use
--fixture for reproducible offline research. Optional CurseForge API key and
GitHub token live in environment variables, never in the built PWA.

Examples:
  python scripts/deep_research.py --game minecraft --fixture fixtures/minecraft_research.json
  python scripts/deep_research.py --game minecraft --live
  python scripts/deep_research.py --batch 3 --live
  python scripts/deep_research.py --game minecraft --fixture fixtures/minecraft_research.json --leads fixtures/example_leads.json
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'data/research_queue.json'
TARGETS=ROOT/'data/research_targets.json'
GAME_VERSION=re.compile(r'(?<![\d.])(?:1\.(?:[0-9]{1,2})\.(?:[0-9]{1,2})|26\.[0-9]{1,2}(?:\.[0-9]{1,2})?)(?!\d)')
LOADER=re.compile(r'\b(fabric|neoforge|forge|quilt|smapi|tmodloader)\b',re.I)
REPO=re.compile(r'^[A-Za-z\d_.-]{1,70}/[A-Za-z\d_.-]{1,100}$')
IMAGES=re.compile(r'!\[([^\]]{0,120})\]\(([^)\s]+\.(?:png|jpe?g|webp))(?:\s+[^)]*)?\)|<img\b[^>]*?src=[\"\']([^\"\']+\.(?:png|jpe?g|webp))[\"\'][^>]*>',re.I)
KEYWORDS=('dual screen','dual-screen','second screen','companion','android','handheld','native port','recomp','decomp','touchscreen','secondary display','second display','two screens','hud','ayn thor','split screen')
MAX_SOURCE=500_000
UA='HandheldAtlasResearch/0.3 (+https://github.com; user-initiated catalog metadata checks)'


def now():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def digest(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()[:20]
def load_json(p,default=None):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else (default if default is not None else {})
def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    temporary.replace(path)

def canonical_url(raw):
    try:
        u=urllib.parse.urlsplit(str(raw).strip())
        if u.scheme!='https' or not u.hostname or u.username or u.password:return None
        host=u.hostname.lower()
        if host not in ('github.com','www.github.com','modrinth.com','www.curseforge.com','curseforge.com','play.google.com','andreyvelsk.github.io','www.reddit.com','reddit.com'):
            return None
        path=re.sub(r'/+$','',u.path) or '/'
        if host=='www.github.com':host='github.com'
        if host=='curseforge.com':host='www.curseforge.com'
        # Do not use tracking query strings to define identities. For Google Play keep id.
        query=''
        if host=='play.google.com':
            q=urllib.parse.parse_qs(u.query);query=urllib.parse.urlencode({'id':q.get('id',[''])[0]}) if q.get('id') else ''
        return urllib.parse.urlunsplit(('https',host,path,query,''))
    except (ValueError,TypeError):return None

def safe_project_image(url,repo=None):
    """Resolve relative images only inside the *same* official repository.
    No automatic scraping, download, hotlink publication or 'AI approved' claims.
    """
    if not url or url.startswith(('#','data:','javascript:')):return None
    raw=html.unescape(url.strip())
    if repo and not urllib.parse.urlsplit(raw).scheme:
        if raw.startswith('/') or '..' in Path(raw).parts:return None
        raw='https://raw.githubusercontent.com/'+repo+'/HEAD/'+raw.lstrip('./')
    try:
        u=urllib.parse.urlsplit(raw)
        if u.scheme!='https' or not u.hostname or u.username or u.password:return None
        if u.hostname.lower() not in ('raw.githubusercontent.com','github.com','cdn.modrinth.com','media.forgecdn.net','mediafilez.forgecdn.net'):return None
        if not re.search(r'\.(?:png|jpe?g|webp)$',u.path,re.I):return None
        return urllib.parse.urlunsplit(('https',u.hostname.lower(),u.path,'',''))
    except ValueError:return None

def image_candidates(markdown,repo,source_url,limit=10):
    output=[]
    for m in IMAGES.finditer(markdown[:MAX_SOURCE]):
        caption=(m.group(1) or 'Originalprojekt-Bild').strip()[:140]
        url=safe_project_image(m.group(2) or m.group(3),repo)
        if url and url not in {x['url'] for x in output}:
            output.append({'url':url,'caption':caption,'sourceUrl':source_url,'reviewStatus':'needs-context-and-rights-review'})
        if len(output)>=limit:break
    return output

def evidence_lines(markdown,terms=KEYWORDS,max_lines=4):
    result=[]
    for line in markdown[:MAX_SOURCE].splitlines():
        simple=re.sub(r'[#*_`>|]+',' ',line).strip()
        if not 20<=len(simple)<=500:continue
        if any(t in simple.lower() for t in terms) or (GAME_VERSION.search(simple) and 'minecraft' in simple.lower()):
            clean=re.sub(r'\s+',' ',simple)[:320]
            if clean not in result:result.append(clean)
            if len(result)>=max_lines:break
    return result

def research_queries(game,target):
    aliases=target.get('aliases') or [game['title']]
    main=aliases[0]
    github=[f'"{main}" "dual screen" in:name,description,readme',
            f'"{main}" "android" "mod" in:name,description,readme',
            f'"{main}" "port" in:name,description,readme']
    github=target.get('githubQueries',github)
    modrinth=target.get('modrinthQueries',[]) if game['id']=='minecraft' else []
    curseforge=target.get('curseforgeQueries',[]) if game['id']=='minecraft' else []
    return {'github':github[:6],'modrinth':modrinth[:4],'curseforge':curseforge[:3]}

def request_json(url,headers,cap=MAX_SOURCE):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json',**headers})
    with urllib.request.urlopen(req,timeout=22) as response:
        data=response.read(cap+1)
        if len(data)>cap:raise ValueError('Oversize provider response')
        return json.loads(data.decode('utf-8'))

def request_gh_readme(repo,token):
    if not REPO.fullmatch(repo):return None
    url='https://api.github.com/repos/'+repo+'/readme'
    headers={'Accept':'application/vnd.github.raw+json','X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,headers={'User-Agent':UA,**headers})
    with urllib.request.urlopen(req,timeout=22) as response:
        blob=response.read(120001)
        if len(blob)>120000:return None
        ct=response.headers.get('Content-Type','')
        if 'json' in ct:
            obj=json.loads(blob);import base64
            return base64.b64decode(obj['content']).decode('utf-8','replace')
        return blob.decode('utf-8','replace')

def github_search(q,token):
    params=urllib.parse.urlencode({'q':q,'sort':'updated','order':'desc','per_page':30})
    hdr={'X-GitHub-Api-Version':'2022-11-28'}
    if token:hdr['Authorization']='Bearer '+token
    return request_json('https://api.github.com/search/repositories?'+params,hdr,1_500_000).get('items',[])

def modrinth_search(q):
    params=urllib.parse.urlencode({'query':q,'limit':30,'index':'updated','facets':json.dumps([['project_type:mod']])})
    return request_json('https://api.modrinth.com/v2/search?'+params,{},1_500_000).get('hits',[])

def curseforge_search(q,key):
    params=urllib.parse.urlencode({'gameId':432,'searchFilter':q,'pageSize':30})
    return request_json('https://api.curseforge.com/v1/mods/search?'+params,{'x-api-key':key},1_500_000).get('data',[])

def relevant(game,target,title,summary,readme='',strict=True):
    joined=' '.join([title,summary,readme[:10000]]).lower()
    aliases=[a.lower() for a in (target.get('aliases') or [game['title']])]
    game_mention=any(a in joined for a in aliases if len(a)>=4)
    speciality=any(x in joined for x in KEYWORDS)
    # Minecraft mod listings are already tied to Minecraft by their provider; require relevant topic.
    return speciality and (game_mention or (game['id']=='minecraft' and not strict))

def from_github(game,target,hit,query,readme=''):
    repo=hit.get('full_name','')
    if not isinstance(repo,str) or not REPO.fullmatch(repo):return None
    label=hit.get('name') or repo.split('/')[-1]
    description=str(hit.get('description') or '')[:400]
    if not relevant(game,target,label+' '+repo,description,readme):return None
    url='https://github.com/'+repo
    score=1+int(bool(readme))+int('dual' in (label+' '+description+' '+readme[:500]).lower())
    excerpts=evidence_lines(readme)
    versions=sorted(set(GAME_VERSION.findall(readme[:30000])))[:25]
    loaders=sorted(set(s.lower() for s in LOADER.findall(readme[:30000])))
    return {'id':digest(game['id']+'|'+url),'gameId':game['id'],'provider':'github','project':label,'url':url,
            'label':description or label,'status':'pending-review','score':score,'matchedQueries':[query],
            'versionsMentioned':versions,'loadersMentioned':loaders,
            'evidence':[{'sourceUrl':url+'/blob/HEAD/README.md','excerpt':s} for s in excerpts],
            'mediaCandidates':image_candidates(readme,repo,url+'/blob/HEAD/README.md'),
            'notTested':True,'rights':'External project: check licence, media permissions and publisher terms.'}

def from_modrinth(game,target,hit,query):
    title=str(hit.get('title') or '')[:140]
    summary=str(hit.get('description') or '')[:450]
    if not relevant(game,target,title,summary,strict=False):return None
    # The word 'companion' often means a pet/NPC, not a secondary screen.
    # Require explicit platform/display wording before entering the handheld queue.
    device_terms = re.compile(r'\b(?:dual[ -]?screens?|second[ -]?screens?|secondary[ -]?displays?|two[ -]?screens?|multi[ -]?screens?|second[ -]?monitors?|ayn[ -]?thor|android[ -]?handhelds?|droidbridge|pojavlauncher|zalithlauncher)\b', re.I)
    if not device_terms.search(title+' '+summary):return None
    slug=str(hit.get('slug') or '').strip()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{2,90}',slug):return None
    url='https://modrinth.com/mod/'+slug
    # Modrinth's 'versions' are platform metadata, not tested on the Thor.
    versions=[v for v in hit.get('versions',[]) if isinstance(v,str)][:35]
    cats=[v for v in hit.get('categories',[]) if isinstance(v,str)][:20]
    # The official Modrinth search API supplies original project-gallery URLs.
    gallery=[]
    for picture in (hit.get('gallery') or [])[:8]:
        url_img=safe_project_image(picture)
        if url_img and url_img not in {m['url'] for m in gallery}:
            gallery.append({'url':url_img,'caption':'Modrinth-Projektgalerie',
              'sourceUrl':url,'reviewStatus':'needs-context-and-rights-review'})
    return {'id':digest(game['id']+'|'+url),'gameId':game['id'],'provider':'modrinth','project':title,'url':url,
            'label':summary,'status':'pending-review','score':2,'matchedQueries':[query],
            'versionsMentioned':versions,'loadersMentioned':[c for c in cats if c in ('fabric','forge','neoforge','quilt')],
            'evidence':[{'sourceUrl':url,'excerpt':summary}] if summary else [],
            'mediaCandidates':gallery, 'notTested':True,
            'rights':'Project metadata only; Modrinth gallery URLs require review before public use.'}

def from_curseforge(game,target,hit,query):
    title=str(hit.get('name') or '')[:140]; summary=str(hit.get('summary') or '')[:450]
    if not relevant(game,target,title,summary,strict=False):return None
    url=canonical_url((hit.get('links') or {}).get('websiteUrl'))
    if not url or not url.startswith('https://www.curseforge.com/minecraft/'):return None
    screenshot_candidates=[]
    for m in (hit.get('screenshots') or [])[:8]:
        image=safe_project_image(m.get('url') or m.get('thumbnailUrl'))
        if image:screenshot_candidates.append({'url':image,'caption':str(m.get('title') or title)[:140],
              'sourceUrl':url,'reviewStatus':'needs-context-and-rights-review'})
    return {'id':digest(game['id']+'|'+url),'gameId':game['id'],'provider':'curseforge',
            'project':title,'url':url,'label':summary,'status':'pending-review','score':2,
            'matchedQueries':[query],'versionsMentioned':[], 'loadersMentioned':[],
            'evidence':[{'sourceUrl':url,'excerpt':summary}] if summary else [],
            'mediaCandidates':screenshot_candidates,'notTested':True,
            'rights':'CurseForge assets may only be used in accordance with developer API and media terms.'}

def from_lead(game,lead):
    if lead.get('gameId')!=game['id']:return None
    url=canonical_url(lead.get('url'))
    if not url:return None
    label=str(lead.get('title') or '')[:160]
    summary=str(lead.get('excerpt') or '')[:420]
    return {'id':digest(game['id']+'|'+url),'gameId':game['id'],'provider':'community-lead','project':label,
            'url':url,'label':summary,'status':'pending-review','score':1,'matchedQueries':['external-research-lead'],
            'versionsMentioned':sorted(set(GAME_VERSION.findall(summary))),
            'loadersMentioned':sorted(set(s.lower() for s in LOADER.findall(summary))),
            'evidence':[{'sourceUrl':url,'excerpt':summary}] if summary else [], 'mediaCandidates':[],
            'notTested':True,'rights':'Imported lead: verify firsthand and check media rights.'}

def merge(existing,added,stamp):
    old={c['id']:c for c in existing}
    new=0
    for c in added:
        if c['id'] not in old:
            c['firstSeenAt']=stamp;c['lastSeenAt']=stamp;old[c['id']]=c;new+=1
            continue
        x=old[c['id']];x['lastSeenAt']=stamp
        x['matchedQueries']=sorted(set(x.get('matchedQueries',[])+c['matchedQueries']))
        x['versionsMentioned']=sorted(set(x.get('versionsMentioned',[])+c['versionsMentioned']))[:60]
        x['loadersMentioned']=sorted(set(x.get('loadersMentioned',[])+c['loadersMentioned']))
        x['score']=max(x.get('score',0),c.get('score',0))
        for field,key in (('evidence','excerpt'),('mediaCandidates','url')):
            seen={v.get(key) for v in x.get(field,[])}
            for val in c.get(field,[]):
                if val.get(key) not in seen:x.setdefault(field,[]).append(val);seen.add(val.get(key))
        # A reviewer may set a status; searches never reset it to pending.
    return sorted(old.values(),key=lambda x:(x.get('status')!='pending-review',-x.get('score',0),x['project'].lower())),new

def run(games,targets,fixture=None,live=False,leads=None,queue=None,budget=6):
    stamp=now()
    history=queue or {'schemaVersion':1,'researchedAt':None,'candidates':[],'runs':[]}
    existing=history.get('candidates',[])
    if live: existing=[c for c in existing if c.get('discoveryMode')!='fixture']
    discovered=[];reports=[]
    token=os.getenv('GITHUB_TOKEN');cf_key=os.getenv('CURSEFORGE_API_KEY')
    for game in games:
        target=targets.get(game['id'],{})
        qs=research_queries(game,target);seen=0;count={'github':0,'modrinth':0,'curseforge':0,'community-lead':0};errors=[];skipped=[]
        for provider in ('github','modrinth','curseforge'):
            for q in qs[provider]:
                if seen>=budget:skipped.append(provider+': budget reached');break
                if provider=='curseforge' and live and not cf_key:skipped.append('CurseForge: API key missing');break
                if not live and fixture is None:skipped.append('offline: use --fixture or --live');continue
                try:
                    if fixture is not None:
                        hits=fixture.get(provider,{}).get(q,[])
                    else:
                        hits={'github':lambda:github_search(q,token),'modrinth':lambda:modrinth_search(q),
                              'curseforge':lambda:curseforge_search(q,cf_key)}[provider]()
                    if isinstance(hits,dict):hits=hits.get('items',hits.get('hits',hits.get('data',[])))
                    if not isinstance(hits,list):raise ValueError('Provider shape mismatch')
                    for hit in hits[:35]:
                        if not isinstance(hit,dict):continue
                        if provider=='github':
                            repo=hit.get('full_name','')
                            if not isinstance(repo,str) or not REPO.fullmatch(repo):continue
                            md=(fixture.get('readmes',{}).get(repo,'') if fixture is not None else '')
                            if live and relevant(game,target,repo,str(hit.get('description') or '')):
                                try:md=request_gh_readme(repo,token) or ''
                                except (urllib.error.HTTPError,urllib.error.URLError,ValueError):md=''
                            c=from_github(game,target,hit,q,md)
                        elif provider=='modrinth':c=from_modrinth(game,target,hit,q)
                        else:c=from_curseforge(game,target,hit,q)
                        if c:discovered.append(c);count[provider]+=1
                    seen+=1
                    if live:time.sleep(1.0)
                except (urllib.error.HTTPError,urllib.error.URLError,ValueError,KeyError) as ex:
                    status=getattr(ex,'code',None)
                    errors.append(provider+': '+('rate limited' if status in (403,429) else type(ex).__name__))
                    if status in (403,429):break
        for lead in leads or []:
            c=from_lead(game,lead)
            if c:discovered.append(c);count['community-lead']+=1
        reports.append({'gameId':game['id'],'title':game['title'],'checkedAt':stamp,'providerHits':count,
                        'errors':errors,'skipped':list(dict.fromkeys(skipped)),
                        'result':'fixture-only' if fixture is not None else ('partial' if errors or skipped else 'completed'),
                        'mode':'fixture' if fixture is not None else ('live' if live else 'disabled'),
                        'note':'Search coverage is bounded, not proof of absence or compatibility. Fixture results are synthetic tests, not live findings.'})
    discovery_mode='fixture' if fixture is not None else ('live' if live else 'disabled')
    for candidate in discovered:candidate['discoveryMode']=discovery_mode
    merged,added=merge(existing,discovered,stamp)
    history.update({'schemaVersion':1,'researchedAt':stamp,'candidates':merged,'runs':(history.get('runs',[])+reports)[-60:],
                    'warning':'Automated discovery is incomplete. Every route, version claim, screenshot and compatibility conclusion requires original-source review.',
                    'lastMode':'fixture' if fixture is not None else ('live' if live else 'disabled')})
    return history,added

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game',help='Exactly one known catalog game ID, e.g. minecraft')
    p.add_argument('--batch',type=int,default=0,help='Number of games with documented routes to scan, max 10')
    p.add_argument('--fixture',type=Path,help='Local fixture for offline/reproducible tests')
    p.add_argument('--leads',type=Path,help='Optional JSON list of external discovery leads')
    p.add_argument('--live',action='store_true',help='Actually call provider APIs')
    p.add_argument('--dry-run',action='store_true',help='Report, never write queue')
    p.add_argument('--budget',type=int,default=6,help='Max API searches per game, 1..12')
    args=p.parse_args()
    if args.live and args.fixture:p.error('Choose either --fixture or --live')
    if not args.game and not args.batch:p.error('Pass --game ID or --batch 1..10')
    if not 1<=args.budget<=12 or not 0<=args.batch<=10:p.error('Invalid budget/batch')
    catalog=load_json(ROOT/'data/catalog.json')
    games_by_id={g['id']:g for g in catalog['games']}
    for entry in catalog.get('gameIndex',[]):
        games_by_id.setdefault(entry['id'],{'id':entry['id'],'title':entry['title'],'routes':[]})
    queue=load_json(QUEUE,{'schemaVersion':1,'candidates':[],'runs':[]})
    if args.game:
        if args.game not in games_by_id:p.error('Unknown game ID: '+args.game)
        games=[games_by_id[args.game]]
    else:
        # The weekly batch rotates via the oldest successful LIVE scan, never by a fixed list.
        latest={}
        for entry in queue.get('runs',[]):
            if entry.get('mode')=='live' and entry.get('result')=='completed':
                latest[entry['gameId']]=entry['checkedAt']
        games=sorted(games_by_id.values(),key=lambda g:(latest.get(g['id'],'0000'),
             not any('dual-screen' in r['features'] for r in g['routes']),g['id']))[:args.batch]
    registry=load_json(TARGETS,{}).get('targets',{})
    fixture=load_json(args.fixture,{}) if args.fixture else None
    leads=load_json(args.leads,[]) if args.leads else []
    if not isinstance(leads,list):p.error('Leads file must contain an array')
    result,new=run(games,registry,fixture,args.live,leads,queue,args.budget)
    if not args.dry_run:write_json(QUEUE,result)
    print(json.dumps({'games':[g['id'] for g in games],'newPending':new,'totalPending':sum(c['status']=='pending-review' for c in result['candidates']),
                      'reports':result['runs'][-len(games):], 'written':not args.dry_run},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
