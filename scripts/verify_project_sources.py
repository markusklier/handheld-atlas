"""Rotate project-source existence checks. Never mark games as working from existence alone."""
from __future__ import annotations
import argparse,json,os,re,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UA='HandheldAtlas/0.5 project source auditing'

def utcnow():return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def api_for_project(url):
    try:
        p=urllib.parse.urlsplit(str(url))
        if p.scheme!='https' or p.username or p.password or p.port:return None
        path=p.path.strip('/')
        if p.hostname=='github.com':
            m=re.fullmatch(r'([A-Za-z0-9_.-]{1,70})/([A-Za-z0-9_.-]{1,100})',path)
            return 'https://api.github.com/repos/'+m.group(1)+'/'+m.group(2) if m else None
        if p.hostname=='modrinth.com':
            m=re.fullmatch(r'mod/([A-Za-z0-9_-]{2,90})',path)
            return 'https://api.modrinth.com/v2/project/'+m.group(1) if m else None
    except (TypeError,ValueError):pass
    return None

def request(api):
    headers={'User-Agent':UA,'Accept':'application/vnd.github+json'}
    if api.startswith('https://api.github.com/') and os.getenv('GITHUB_TOKEN'):
        headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
    req=urllib.request.Request(api,headers=headers)
    with urllib.request.urlopen(req,timeout=18) as response:
        body=response.read(280000)
        return json.loads(body.decode('utf-8'))

def verify_one(url,fetch=request,when=None):
    api=api_for_project(url)
    if not api:return {'status':'unsupported','checkedAt':when or utcnow(),
                       'note':'Keine verfügbare projektbezogene API-Prüfung.'}
    try:
        item=fetch(api)
        if not isinstance(item,dict):return {'status':'unknown','checkedAt':when or utcnow()}
        title=item.get('full_name') or item.get('title') or item.get('slug')
        return {'status':'source-exists','checkedAt':when or utcnow(),'name':str(title or '')[:140],
                'source':url,'note':'Nur Projekt-Existenz geprüft; weder genaue Spiel-Version noch AYN-Thor-Kompatibilität.'}
    except Exception as ex:
        # Do not permanently label transient outages as missing projects.
        return {'status':'unavailable','checkedAt':when or utcnow(),'note':type(ex).__name__}

def select_projects(index,previous,limit):
    candidates=[p for p in index.get('projects',[]) if not p.get('curated') and api_for_project(p.get('url'))]
    ordered=sorted(candidates,key=lambda p:(previous.get('projects',{}).get(p['url'],{}).get('checkedAt',''),p['url']))
    return ordered[:limit]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--limit',type=int,default=8)
    args=p.parse_args()
    if not 1<=args.limit<=20:p.error('limit 1..20')
    previous=json.loads((ROOT/'data/project_checks.json').read_text())
    projects=json.loads((ROOT/'data/projects.json').read_text())
    for entry in select_projects(projects,previous,args.limit):
        previous['projects'][entry['url']]=verify_one(entry['url'])
    previous['checkedAt']=utcnow()
    (ROOT/'data/project_checks.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'visited':min(args.limit,len(projects.get('projects',[]))),
          'total':len(previous['projects']),'sourceExists':sum(v['status']=='source-exists' for v in previous['projects'].values())}))

if __name__=='__main__':main()
