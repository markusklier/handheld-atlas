"""Merge carefully named title-only platform seeds; never invent playable routes.

These are basic discovery index entries, *not* verified compatibility records.
The merge is idempotent and does not replace curated games or edition-specific data.
"""
import json
import re
import unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def normalize(name):
    normalized=unicodedata.normalize('NFKD',str(name)).casefold()
    return re.sub(r'[^a-z0-9]+','',normalized.encode('ascii','ignore').decode('ascii'))

def slug(name):
    normalized=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'^-|-$','',re.sub(r'[^a-z0-9]+','-',normalized))[:78]

PREFIXES=[
 ('The Legend of Zelda', 'The Legend of Zelda'),('Mario Kart','Mario Kart'),('Super Mario','Super Mario'),
 ('Paper Mario','Super Mario'),('Mario ','Super Mario'),('Luigi\'s Mansion','Super Mario'),
 ('The Legend of Heroes','The Legend of Heroes'),('Trails of Cold Steel','The Legend of Heroes'),
 ('Metroid','Metroid'),('Fire Emblem','Fire Emblem'),('Pokémon','Pokémon'),('Pokemon','Pokémon'),
 ('Final Fantasy','Final Fantasy'),('Shin Megami Tensei','Shin Megami Tensei'),
 ('Persona','Persona'),('God of War','God of War'),('Grand Theft Auto','Grand Theft Auto'),
 ('Monster Hunter','Monster Hunter'),('Resident Evil','Resident Evil'),('Devil May Cry','Devil May Cry'),
 ('Sonic','Sonic'),('Star Wars','Star Wars'),('Wario','Wario'),('Kirby','Kirby'),
 ('Ratchet & Clank','Ratchet & Clank'),('Jak ','Jak and Daxter'),('Soulcalibur','Soulcalibur'),
 ('Tekken','Tekken'),('Ys ','Ys'),('Burnout','Burnout'),('Street Fighter','Street Fighter'),
 ('Metal Gear Solid','Metal Gear'),('Kingdom Hearts','Kingdom Hearts'),('Castlevania','Castlevania'),
 ('Star Ocean','Star Ocean'),('Phantasy Star','Phantasy Star'),('Danganronpa','Danganronpa'),
 ('Yakuza','Yakuza'),('Sly ','Sly Cooper'),('Ace Combat','Ace Combat'),('Ecco','Ecco the Dolphin'),
 ('Shining ','Shining'),('Streets of Rage','Streets of Rage'),('Wii ','Wii'),('Valkyria Chronicles','Valkyria Chronicles')]

def franchise(title):
    for prefix,label in PREFIXES:
        if title.casefold().startswith(prefix.casefold()):return label
    return title

def merge(catalog,seeds):
    out=json.loads(json.dumps(catalog))
    current=out['gameIndex']
    curated_titles={normalize(g['title']) for g in out['games']}
    keyed={normalize(g['title']):g for g in current}
    ids={g['id'] for g in out['games']+current}
    added=0; platforms_extended=0
    for platform,titles in seeds['platforms'].items():
        if not isinstance(platform,str) or not isinstance(titles,list):continue
        for title in titles:
            if not isinstance(title,str) or len(title)<3 or len(title)>140:continue
            name=normalize(title)
            if name in curated_titles:continue
            if name in keyed:
                if platform not in keyed[name]['platforms']:
                    keyed[name]['platforms'].append(platform);platforms_extended+=1
                continue
            id=slug(title)
            if not id:continue
            if id in ids:
                k=2
                while f'{id}-{k}' in ids:k+=1
                id=f'{id}-{k}'
            ids.add(id)
            game={'id':id,'title':title,'franchise':franchise(title),'platforms':[platform],
                  'indexSource':'editorial-name-only-v051','verification':'title-platform-lead',
                  'note':'Kein Spielweg, keine Performance- oder Gerätevalidierung.'}
            current.append(game);keyed[name]=game;added+=1
    out['gameIndex']=current
    return out,{'added':added,'platformLinksExtended':platforms_extended,'indexGames':len(current),
                'totalGames':len(out['games'])+len(current)}

def main():
    cat=ROOT/'data/catalog.json';p=ROOT/'data/index_seeds_v051.json'
    output,stats=merge(json.loads(cat.read_text()),json.loads(p.read_text()))
    cat.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(stats))

if __name__=='__main__':main()
