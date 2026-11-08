"""Strict intake for AI/n8n suggestion files; nothing is published to catalog.
No jsonschema dependency: intentionally narrow, auditable stdlib validation.
"""
import argparse
import json
import re
from pathlib import Path
from deep_research import ROOT, canonical_url
KINDS={'edition','version','loader','runtime','feature','device','media','limitation','security','unknown'}
STATUSES={'unreviewed','contradictory','needs-reproduction'}


def validate_findings(payload,game_ids):
    if not isinstance(payload,dict) or set(payload)!={'schemaVersion','gameId','findings'} or payload['schemaVersion']!=1:raise ValueError('Unknown root schema')
    if payload['gameId'] not in game_ids:raise ValueError('Unknown gameId')
    findings=payload['findings']
    if not isinstance(findings,list) or len(findings)>30:raise ValueError('Invalid findings')
    validated=[]
    for obj in findings:
        if not isinstance(obj,dict):raise ValueError('Finding is not an object')
        allowed={'claimType','claim','sourceUrl','sourceExcerpt','reviewRequired','verification','imageUrl','confidence'}
        if set(obj)-allowed:raise ValueError('Unknown finding keys')
        if obj.get('claimType') not in KINDS or obj.get('verification') not in STATUSES or obj.get('reviewRequired') is not True:raise ValueError('Cannot auto approve claims')
        for key,min_len,max_len in [('claim',3,240),('sourceExcerpt',12,350)]:
            v=obj.get(key)
            if not isinstance(v,str) or not min_len<=len(v.strip())<=max_len:raise ValueError('Bad text field '+key)
        url=canonical_url(obj.get('sourceUrl'))
        if not url:raise ValueError('Disallowed source URL')
        if 'imageUrl' in obj:
            # The agent may describe an image, but can never decide media permissions.
            raise ValueError('Image URLs belong to separate media review workflow')
        cf=obj.get('confidence',0)
        if isinstance(cf,bool) or not isinstance(cf,(int,float)) or not 0<=cf<=1:raise ValueError('Bad confidence')
        validated.append({**obj,'sourceUrl':url,'verification':obj['verification'],'reviewRequired':True})
    return {'gameId':payload['gameId'],'findings':validated,'allRequireHumanReview':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('jsonfile',type=Path)
    args=ap.parse_args()
    known={g['id'] for g in json.loads((ROOT/'data/catalog.json').read_text())['games']}
    result=validate_findings(json.loads(args.jsonfile.read_text(encoding='utf-8')),known)
    print('Valid unreviewed suggestions:',len(result['findings']),'for',result['gameId'])

if __name__=='__main__':main()
