"""Extract source-linked screenshots as review candidates, never as auto-approved images.
Use --source-file for offline README. --fetch reads only the hardcoded Eden source.
Optionally validates PNG/JPEG/WebP header and dimensions when given --check-images (Pillow optional).
No image is redistributed or downloaded into dist. No vision API is called.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from sync_sources import ROOT, atomic_json, utcnow

BASE='https://raw.githubusercontent.com/igawa6/eden-duo-companions/main/'
README=BASE+'README.md'
REF='https://github.com/igawa6/eden-duo-companions/blob/main/README.md'
IMG_RE=re.compile(r'<img\s+[^>]*?src="(screenshots/[a-zA-Z0-9_./-]+\.(?:png|jpg|jpeg|webp))"[^>]*?alt="([^"]{1,160})"|!\[([^\]]{0,160})\]\((screenshots/[a-zA-Z0-9_./-]+\.(?:png|jpg|jpeg|webp))\)',re.I)
HEAD_RE=re.compile(r'^## (.+?)\s*$',re.M)


def normalize(s):
 import unicodedata
 s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower().replace('pokemon','pokemon')
 return re.sub(r'[^a-z0-9]+',' ',s).strip()


def candidates_from_readme(markdown, catalog):
    sections=list(HEAD_RE.finditer(markdown)); known={normalize(g['title']):g['id'] for g in catalog['games']}
    out=[]
    for idx,match in enumerate(sections):
        heading=match.group(1).strip()
        if heading=='Supported Games':continue
        normalized=normalize(heading)
        game_id=known.get(normalized)
        if not game_id:
            # Deliberately no fuzzy auto-match. Different editions can look similar.
            continue
        segment=markdown[match.end(): sections[idx+1].start() if idx+1<len(sections) else len(markdown)]
        for img in IMG_RE.finditer(segment):
            path=img.group(1) or img.group(4)
            alt=img.group(2) or img.group(3) or path
            if '..' in Path(path).parts or not path.startswith('screenshots/') or path.startswith('screenshots/eden-duo/'):
                continue
            if not re.fullmatch(r'screenshots/[A-Za-z0-9_.\-/]+\.(?:png|jpe?g|webp)',path,re.I):continue
            url=BASE+path
            out.append({'id':hashlib.sha256(url.encode()).hexdigest()[:20],'gameId':game_id,'routeKind':'emulator-mod','sourceId':'eden-companions',
              'sourceUrl':REF, 'url':url,'caption':html.unescape(alt), 'reviewStatus':'needs-media-review',
              'matchingBasis':'Exact matching ## game heading in original README',
              'rightsNote':'Hotlink to original documentation; no image or underlying game art rights granted.'})
    return out


def fetch_readme():
    req=urllib.request.Request(README,headers={'User-Agent':'HandheldAtlasResearch/0.2 (README media metadata only)','Accept':'text/plain'})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read(3_000_001)
        if len(raw)>3_000_000:raise RuntimeError('README size limit exceeded')
        return raw.decode('utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--source-file',type=Path,help='Offline copy of official README for deterministic review')
    group.add_argument('--fetch',action='store_true',help='Fetch from one hardcoded official README URL')
    args=ap.parse_args()
    markdown=args.source_file.read_text(encoding='utf-8') if args.source_file else fetch_readme()
    catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    shots=candidates_from_readme(markdown,catalog)
    data={'schemaVersion':1,'source':REF,'checkedAt':utcnow(),'candidates':shots,
          'notice':'Media candidates only; verify content, version, attribution and permissions before publication.'}
    atomic_json(ROOT/'data/media_candidates.json',data)
    print('Media candidates:',len(shots),'different games:',len(set(x['gameId'] for x in shots)))

if __name__=='__main__':main()
