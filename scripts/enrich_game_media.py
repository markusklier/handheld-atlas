"""Source-backed *game-level* artwork, distinct from route screenshots.

Steam public store data (curated app IDs); optional IGDB noncommercial API
credentials via TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET. Both return external
images with provenance; not public-domain media or verified Thor screenshots.

Python standard library only. Do not crawl arbitrary image sites.
"""
from __future__ import annotations
import argparse
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/game_media.json'
MAX_BYTES = 2_500_000
USER_AGENT = 'HandheldAtlas/0.5 (personal non-commercial game metadata demo)'
HOSTS = {'shared.cloudflare.steamstatic.com', 'shared.fastly.steamstatic.com',
         'shared.akamai.steamstatic.com', 'shared.steamstatic.com',
         'cdn.akamai.steamstatic.com', 'cdn.cloudflare.steamstatic.com',
         'images.igdb.com'}


def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def get_json(url, headers=None, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': USER_AGENT, **(headers or {})},
                                 method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES: raise ValueError('Oversized metadata response')
        return json.loads(raw.decode('utf-8'))


def clean_image(value):
    try:
        u = urllib.parse.urlsplit(str(value or ''))
        if u.scheme != 'https' or u.hostname not in HOSTS or u.username or u.password or u.port: return None
        if not re.search(r'\.(?:jpg|jpeg|png|webp)$', u.path, re.I): return None
        return urllib.parse.urlunsplit(('https',u.hostname,u.path,'',''))
    except (TypeError,ValueError):return None


def same_game(name, title):
    norm=lambda s: re.sub(r'[^a-z0-9]+',' ',str(s).casefold()).strip()
    n,t=norm(name),norm(title)
    if not n or not t:return False
    return n==t or n.removeprefix('the ')==t.removeprefix('the ')


def steam_cover(appid, checker=None):
    """Use a verified original public Steam library capsule, no guessed image publication."""
    base=f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/'
    for filename in ('library_600x900_2x.jpg','library_600x900.jpg'):
        url=base+filename
        if checker and checker(url):return url
    return None


def image_exists(url):
    req=urllib.request.Request(url,method='HEAD',headers={'User-Agent':USER_AGENT})
    try:
        with urllib.request.urlopen(req,timeout=12) as r:
            ct=r.headers.get('Content-Type','').lower()
            return r.status==200 and ct.startswith('image/')
    except (OSError,ValueError):return False


def steam_metadata(game,appid,fetch=get_json,check=image_exists):
    appid=int(appid)
    obj=fetch('https://store.steampowered.com/api/appdetails?'+urllib.parse.urlencode(
        {'appids':appid,'cc':'US','l':'en'}))
    item=obj.get(str(appid),{})
    if not item.get('success') or not isinstance(item.get('data'),dict):return None
    details=item['data']
    if not same_game(details.get('name'),game['title']):return None
    page=f'https://store.steampowered.com/app/{appid}/'
    cover=steam_cover(appid,check)
    # Store-provided (not inferred) fallback artwork when a vertical library capsule is unavailable.
    art=clean_image(details.get('header_image'))
    if not cover and not art:return None
    screenshots=[]
    for entry in details.get('screenshots',[])[:6]:
        url=clean_image(entry.get('path_full'))
        if url and url not in {x['url'] for x in screenshots}:
            screenshots.append({'url':url,'caption':'Originalspiel · offizielles Steam-Store-Bild',
                'sourceUrl':page,'rights':'publisher-artwork','type':'original-game'})
    return {'title':game['title'],'cover':{
            'url':cover or art,'portrait':bool(cover),'caption':'Offizielle Steam-Bibliotheksgrafik' if cover else 'Steam-Store-Bild',
            'sourceUrl':page,'rights':'publisher-artwork','type':'game-cover'},
        'screenshots':screenshots,'provenance':'steam-store','verifiedName':details.get('name'),
        'reviewedAt':now(),'notice':'Spiel-Artwork ist nicht gemeinfrei; nur Verweis auf externen Anbieter.'}


def twitch_token(client_id,secret,fetch=get_json):
    url='https://id.twitch.tv/oauth2/token?'+urllib.parse.urlencode(
        {'client_id':client_id,'client_secret':secret,'grant_type':'client_credentials'})
    reply=fetch(url,data=b'')
    token=reply.get('access_token')
    if not token:raise ValueError('Twitch OAuth access token missing')
    return token


def igdb_image(image_id, size='t_cover_big'):
    if not re.fullmatch(r'[a-zA-Z0-9_]{3,60}',str(image_id)):return None
    return clean_image(f'https://images.igdb.com/igdb/image/upload/{size}/{image_id}.jpg')


def igdb_metadata(game,client_id,token,fetch=get_json):
    title=game['title']
    # Search is bound to title, with exact name match required; never trust fuzzy matches blindly.
    safe=title.replace('\\','\\\\').replace('"','\\"')
    query=f'search "{safe}"; fields name,cover.image_id,screenshots.image_id; limit 20;'.encode('utf-8')
    items=fetch('https://api.igdb.com/v4/games',
                {'Client-ID':client_id,'Authorization':'Bearer '+token,'Content-Type':'text/plain'},data=query)
    if not isinstance(items,list):return None
    exact=[x for x in items if same_game(x.get('name'),title)]
    if len(exact)!=1:return None  # Ambiguous edition / duplicate match -> no automatic artwork assignment.
    item=exact[0]
    cover=igdb_image((item.get('cover') or {}).get('image_id'))
    if not cover:return None
    url=f'https://www.igdb.com/games/{urllib.parse.quote(title.lower().replace(" ","-"))}'
    screenshots=[]
    for x in item.get('screenshots',[])[:5]:
        src=igdb_image(x.get('image_id'),'t_screenshot_med')
        if src:screenshots.append({'url':src,'caption':'Originalspiel · IGDB-Screenshot',
           'sourceUrl':url,'rights':'publisher-artwork','type':'original-game'})
    return {'title':title,'cover':{'url':cover,'portrait':True,'caption':'Spielcover laut IGDB',
        'sourceUrl':url,'rights':'publisher-artwork','type':'game-cover'},'screenshots':screenshots,
        'provenance':'igdb-noncommercial','verifiedName':item['name'],'reviewedAt':now(),
        'notice':'IGDB API nur mit gültiger Nutzungsberechtigung; Abbildungen bleiben Publisher-Artwork.'}


def run(catalog,targets,old,limit=10,provider='steam',game_id=None,fetch=get_json,check=image_exists,
        token=None,client_id=None):
    games={g['id']:g for g in catalog['games']+catalog.get('gameIndex',[])}
    result={**old,'schemaVersion':1,'games':dict(old.get('games',{}))}
    ordered=sorted(games,key=lambda gid:(bool(result['games'].get(gid,{}).get('cover')),gid))
    if game_id:ordered=[game_id] if game_id in games else []
    visited,added,failures=0,0,[]
    for gid in ordered:
        if visited>=limit:break
        g=games[gid]
        if not g.get('title'):continue
        if result['games'].get(gid,{}).get('cover') and not game_id:continue
        if provider=='steam' and gid not in targets.get('steam',{}):continue
        visited+=1
        try:
            if provider=='steam':m=steam_metadata(g,targets['steam'][gid],fetch,check)
            else:m=igdb_metadata(g,client_id,token,fetch)
            if m:
                result['games'][gid]=m
                added+=1
        except (ValueError,KeyError,OSError,TimeoutError) as exc:
            failures.append(f'{gid}: {type(exc).__name__}')
    result['updatedAt']=now()
    return result,{'checked':visited,'added':added,'totalWithCovers':sum(bool(v.get('cover')) for v in result['games'].values()),
                   'errors':failures[:20],'provider':provider}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true')
    p.add_argument('--provider',choices=['steam','igdb'],default='steam')
    p.add_argument('--limit',type=int,default=10)
    p.add_argument('--game')
    p.add_argument('--dry-run',action='store_true')
    args=p.parse_args()
    if not args.live:p.error('Run --live to use metadata APIs; no synthetic images are published.')
    if not 1<=args.limit<=20:p.error('--limit must be 1..20')
    cat=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    targets=json.loads((ROOT/'data/media_targets.json').read_text(encoding='utf-8'))
    old=json.loads(OUT.read_text(encoding='utf-8'))
    client=os.getenv('TWITCH_CLIENT_ID')
    token=None
    if args.provider=='igdb':
        secret=os.getenv('TWITCH_CLIENT_SECRET')
        if not client or not secret:
            print('SKIPPED: IGDB requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET');return 0
        token=twitch_token(client,secret)
    new,report=run(cat,targets,old,args.limit,args.provider,args.game,token=token,client_id=client)
    if not args.dry_run:OUT.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
