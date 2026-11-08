"""One-time audited media correction from Eden Duo Companions README, 2026-11-08.
Each URL below was seen literally as an `img src` path in the upstream README.
Do not rerun this as a blind updater; use discover_media.py for future review diffs.
"""
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'data/catalog.json'
c=json.loads(p.read_text(encoding='utf-8'))
repo='https://raw.githubusercontent.com/igawa6/eden-duo-companions/main/screenshots/'
ref='https://github.com/igawa6/eden-duo-companions/blob/main/README.md'
verified={
 'persona-5-royal':('persona5royal',['field','menu','battle']),
 'metroid-dread':('metroid-dread',['map','emmi','water']),
 'the-legend-of-zelda-link-s-awakening':('links-awakening',['map','gear','items']),
 'mario-kart-8-deluxe':('mario-kart-8-deluxe',['map_long_light','horn_short_dark','waiting']),
 'super-mario-bros-wonder':('super-mario-bros-wonder',['title','map','course']),
 'animal-crossing-new-horizons':('animal-crossing-new-horizons',['map','pockets','critterpedia']),
 'fire-emblem-three-houses':('fire-emblem-three-houses',['monastery','academy','battle']),
 'the-binding-of-isaac-afterbirth':('the-binding-of-isaac',['map','items','room']),
 'pokemon-brilliant-diamond':('pokemon-luminescent-platinum',['map','party','battle']),
 'pokemon-shining-pearl':('pokemon-shining-pearl',['map','party','poketch']),
 'crash-team-racing-nitro-fueled':('crash-team-racing-nitro-fueled',['race','settings','hud']),
 'dragon-quest-iii-hd-2d-remake':('dragon-quest-iii-hd-2d-remake',['map','party','battle']),
 'chained-echoes':('chained-echoes',['field','battle','crystals']),
 'yoru-tomosu':('yoru-tomosu',['log','option','cg']),
 'diablo-iii-eternal-collection':('diablo-iii-eternal-collection',['map','hero','gear']),
 'farming-simulator-nintendo-switch-edition':('farming-simulator',['map','garage','prices']),
 'the-legend-of-zelda-breath-of-the-wild':('breath-of-the-wild',['ready','inventory','map']),
 'castlevania-belmont-s-curse':('castlevania-belmont',['map','equipment','pins']),
 'super-mario-odyssey':('mario-odyssey',['map','stats','warp-here']),
 'the-legend-of-zelda-echoes-of-wisdom':('echoes-of-wisdom',['map','notebooks','equipment']),
 'persona-3-portable':('persona3portable',['talk','persona','social_links']),
 'fire-emblem-engage':('fire-emblem-engage',['war','unit-details','somniel']),
 'octopath-traveler-0':('octopath-traveler-0',['map','party','battle']),
 'pokemon-sword':('pokemon-sword',['town-map','battle','pokedex']),
 'pokemon-shield':('pokemon-shield',['town-map','battle','pokedex']),
 'cult-of-the-lamb':('cult-of-the-lamb',['cult','dungeon'])
}
# Identify route by Eden-duo provenance and title slug; avoid guessing other screenshots.
seen=[]
for game in c['games']:
    for route in game['routes']:
        if 'eden-companions' not in route.get('sources',[]):continue
        key=game['id']
        if key not in verified:
            route.pop('media',None)
            continue
        folder,files=verified[key]
        route['media']=[{'url':repo+folder+'/'+fn+'.png', 'caption':fn.replace('_',' ').replace('-',' ').capitalize(),
                        'sourceUrl':ref,'sourceLabel':'Original-Screenshot: Eden Duo Companions',
                        'review':'exact-path-verified-in-readme', 'rights':'Originalprojekt; keine eigenstaendige kommerzielle Lizenz zur Wiedergabe geprueft'} for fn in files]
        seen.append((key,len(files)))
# Give a warning for every not yet matched expected ID.
print('Known verified shots:',len(seen),'routes;',sum(n for _,n in seen),'image links; unmatched expected IDs',set(verified)-set(k for k,_ in seen))
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
