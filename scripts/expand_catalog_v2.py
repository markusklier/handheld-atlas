"""One-time v0.2 editorial expansion based on confirmed Eden Duo README (2026-11-08).
Not an unattended sync tool. Existing hand-reviewed routes are retained.
"""
import json, re, unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'data/catalog.json'
c=json.loads(PATH.read_text())
if c.get('version')=='0.2.0':
 print('Already expanded'); raise SystemExit()
c['version']='0.2.0'
c['notice']='Grosser Watchlist-Spielindex + redaktionell dokumentierte Spielwege. Spielindex ist KEIN Geraete-Kompatibilitaetstest. Externe Projektbilder mit Quellenangaben.'
c['features'].pop('live-map',None) if False else None
c['sources'] += [
 {'id':'eden-companions','name':'Eden Duo Companions','url':'https://github.com/igawa6/eden-duo-companions','repo':'igawa6/eden-duo-companions','role':'primary','checkedAt':'2026-11-08','note':'Projektkatalog mit exakten Spielversionen und Quell-Screenshots. Projekte dokumentiert, keine Atlas-Messungen.'},
 {'id':'abacus-dual','name':'Abacus Ayn Dual Screen','url':'https://github.com/Abacus1829/ayn-dual-screen','repo':'Abacus1829/ayn-dual-screen','role':'primary','checkedAt':'2026-11-08','note':'Minecraft Java Forge, Stardew, Terraria und weitere Companion-Mods. Source-available, Weiterverwendung pruefen.'},
 {'id':'zalith','name':'Zalith Launcher 2','url':'https://github.com/ZalithLauncher/ZalithLauncher2','repo':'ZalithLauncher/ZalithLauncher2','role':'primary','checkedAt':'2026-11-08','note':'Minecraft Java Android Launcher; Version und Renderer passend konfigurieren.'},
 {'id':'wikidata','name':'Wikidata','url':'https://www.wikidata.org/wiki/Wikidata:Introduction','role':'planned','checkedAt':'2026-11-08','note':'CC0-Spielestammdaten fuer grossen Index. Ein periodischer Plattformimport ist vorbereitet, live noch nicht ausgefuehrt.'}
]
by_title={g['title'].casefold():g for g in c['games']}
by_id={g['id']:g for g in c['games']}
def slug(s):
 s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower().replace('&','and')
 return re.sub('-+','-',re.sub('[^a-z0-9]+','-',s)).strip('-')
# (game title, version, screenshot directory, filenames, franchise, theme, screenshot captions, benefit)
data=[
 ('Persona 5 Royal','1.0.2','persona5royal','field menu battle','Persona','signal','Feld Menue Kampf','Menues, Gebietskarte und Kampfdetails auf dem zweiten Bildschirm.'),
 ('Metroid Dread','2.1.0','metroid-dread','map emmi water','Metroid','signal','Karte EMMI Wasser','Live-Gebietskarte und Status auf dem unteren Display.'),
 ("The Legend of Zelda: Link’s Awakening",'1.0.1','links-awakening','map gear items','The Legend of Zelda','forest','Karte Ausruestung Gegenstaende','Karten, Ausruestung und Gegenstaende auf dem zweiten Display.'),
 ('Mario Kart 8 Deluxe','4.0.1 / 4.0.0 / 3.0.3','mario-kart-8-deluxe','map_long_light horn_short_dark waiting','Mario Kart','wild','Streckenkarte Hupe Naechstes Rennen','Kurskarte, Positionen und Touch-Hupe auf einem zweiten Display.'),
 ('Super Mario Bros. Wonder','1.2.1','super-mario-bros-wonder','title map course','Super Mario','forest','Startbildschirm Weltkarte Level','Weltkarte, Level-Fortschritt und Sammelstatus auf dem unteren Bildschirm.'),
 ('Animal Crossing: New Horizons','3.0.3','animal-crossing-new-horizons','map pockets critterpedia','Animal Crossing','forest','Inselkarte Taschen Lexikon','Inselkarte, Inventar und Sammlungen separat bedienen.'),
 ('Fire Emblem: Three Houses','1.2.0','fire-emblem-three-houses','monastery academy battle','Fire Emblem','signal','Kloster Akademie Kampf','Taktikkarte, Einheiten und Klosterinformationen auf dem zweiten Bildschirm.'),
 ('The Binding of Isaac: Afterbirth+','1.7.9b','the-binding-of-isaac','map items room','The Binding of Isaac','moon','Karte Items Raum','Raumkarte, Gegenstaende und Effekte auf dem zweiten Display.'),
 ('Pokémon Brilliant Diamond','1.3.0','pokemon-luminescent-platinum','map party battle','Pokémon','wild','Karte Team Kampf','Sinnoh-Karte und Teamansicht; auch Luminescent Platinum 2.2F genannt.'),
 ('Pokémon Shining Pearl','1.3.0','pokemon-shining-pearl','map party poketch','Pokémon','wild','Karte Team Poketch','Sinnoh-Karte, Teamdetails und Poketch; eigenes Paket fuer Shining Pearl.'),
 ('Crash Team Racing Nitro-Fueled','1.0.15','crash-team-racing-nitro-fueled','race settings hud','Crash Bandicoot','wild','Rennen HUD Einstellungen','Kurskarte, Positionen und einstellbares HUD auf dem zweiten Bildschirm.'),
 ('Dragon Quest III HD-2D Remake','1.1.0.0','dragon-quest-iii-hd-2d-remake','map party battle','Dragon Quest','ruins','Karte Team Kampf','Karte, Charaktermenues und Kampfinformationen auf dem unteren Bildschirm.'),
 ('Chained Echoes','1.41','chained-echoes','field battle crystals','Chained Echoes','forest','Feld Kampf Kristalle','Feldkarte, Kampfinformation und Kristallplanung.'),
 ('Yoru Tomosu','1.0.0','yoru-tomosu','log option cg','Yoru Tomosu','moon','Dialoglog Optionen Galerie','Dialogverlauf, Optionen und freigeschaltete Szenen als Companion.'),
 ('Diablo III: Eternal Collection','2.7.7 / 2.7.6','diablo-iii-eternal-collection','map hero gear','Diablo','ruins','Karte Held Ausruestung','Karte, Charakteruebersicht und Ausruestung auf dem unteren Bildschirm.'),
 ('Farming Simulator: Nintendo Switch Edition','1.5.0.1','farming-simulator','map garage prices','Farming Simulator','forest','Karte Garage Preise','Feldkarte, Fahrzeugverwaltung und Marktpreise auf dem zweiten Display.'),
 ('VA-11 Hall-A: Cyberpunk Bartender Action','1.0.0','', '', 'VA-11 Hall-A','city','','Touch-Cocktailsteuerung auf dem zweiten Display.'),
 ('The Legend of Zelda: Breath of the Wild','1.6.0','', '', 'The Legend of Zelda','forest','','Companion fuer Karte und Spielinformationen; siehe Originalprojekt.'),
 ("Castlevania: Belmont's Curse",'1.1.0','','','Castlevania','ruins','','Companion fuer die dokumentierte Spielversion.'),
 ('Super Mario Odyssey','1.4.1','','','Super Mario','forest','','Separate Companion-Anzeige auf dem unteren Display.'),
 ('The Legend of Zelda: Echoes of Wisdom','1.1.0','','','The Legend of Zelda','forest','','Separate Companion-Anzeige auf dem unteren Display.'),
 ('Dave the Diver','1.0.6.1267','','','Dave the Diver','wild','','Karte, Missions- und Ausruestungsinformationen auf dem unteren Display.'),
 ('Persona 3 Portable','1.0.0 (Basis)','persona3portable','hub battle map','Persona','signal','Menue Kampf Tartarus','Karten-, Dialog- und Kampfmenues auf dem zweiten Bildschirm.'),
 ('Fire Emblem Engage','2.0.0','fire-emblem-engage','war unit-details somniel','Fire Emblem','signal','Taktikkarte Einheit Somniel','Taktikkarte und Einheitsinformationen auf dem zweiten Display.'),
 ('Octopath Traveler 0','1.0.5','octopath-traveler-0','map party battle','Octopath Traveler','ruins','Karte Team Kampf','Karte, Team und Kampfstatus auf dem unteren Bildschirm.'),
 ('Pokémon Sword','1.3.2','pokemon-sword','town-map battle pokedex','Pokémon','wild','Karte Kampf Pokedex','Galar-Karte, Team, Pokedex und Kampfeingaben auf dem zweiten Bildschirm.'),
 ('Pokémon Shield','1.3.2','pokemon-shield','town-map battle pokedex','Pokémon','wild','Karte Kampf Pokedex','Galar-Karte, Team, Pokedex und Kampfeingaben auf dem zweiten Bildschirm.'),
 ('Cult of the Lamb','1.5.27 / 1.5.28','','','Cult of the Lamb','moon','','Kultstatus, Gefolgsleute und Dungeoninfos auf dem zweiten Display.')
]
for title,version,directory,files,franchise,theme,captions,benefit in data:
 # Map source's stylized title to existing title
 existing=by_id.get('metroid-dread') if title=='Metroid Dread' else None
 if title=='The Legend of Zelda: Link’s Awakening': title="The Legend of Zelda: Link's Awakening"
 g=existing or by_title.get(title.casefold())
 if not g:
  g={'id':slug(title),'title':title,'franchise':franchise,'original':'Nintendo Switch',
    'genre':'Verschiedenes','theme':theme,'blurb':'Dokumentierter Dual-Screen-Companion fuer Eden Duo. Erfordert eine exakt passende Spielversion.','reviewedAt':'2026-11-08','routes':[]}
  c['games'].append(g);by_title[title.casefold()]=g;by_id[g['id']]=g
 route=g['routes'][0] if title=='Metroid Dread' and g['routes'] else None
 if not route:
  route={'id':'eden-'+g['id'],'name':'Eden Duo + Spiel-Companion','kind':'emulator-mod','edition':'Nintendo Switch',
    'runtime':'Eden Duo','targets':['android'],'features':['dual-screen'],
    'requires':['Eigener rechtmaessig erworbener Spieldump mit passender Versionskennung','Spielversion '+version,
                'Eden Duo und zum Titel passendes .dsmod.zip aus dem Originalprojekt'],
    'benefit':benefit,
    'caveat':'Nur die dokumentierten Builds werden akzeptiert. Keine Atlas-Benchmarkdaten oder eigene Geraetetests.',
    'sources':['eden-companions','eden'], 'effort':'advanced','status':'documented',
    'dual':'Companion-Ansicht auf zweitem Bildschirm',
    'steps':['Originalprojekt und genaue Version abgleichen.',
             'Eigene Spielstaende und Einstellungen vorher sichern.',
             'Passende Eden-Duo-Version verwenden und Companion ueber Add-ons installieren.',
             'Mit einem eigenen Spieltest die Funktion pruefen.'],
    'stores':[], 'requiredVersion':version,'reviewedAt':'2026-11-08', 'testedOn':[], 'performance':None}
  g['routes'].append(route)
 else:
  route['sources']=['eden-companions','eden'];route['benefit']=benefit
 if directory:
  shots=[]
  parts=files.split(); captions_list=captions.split()
  for idx,path in enumerate(parts):
   img=f'https://raw.githubusercontent.com/igawa6/eden-duo-companions/main/screenshots/{directory}/{path}.png'
   shots.append({'url':img,'caption':captions_list[idx] if idx<len(captions_list) else path,
                 'sourceUrl':'https://github.com/igawa6/eden-duo-companions/blob/main/README.md',
                 'sourceLabel':'Eden Duo Companions / Projekt-Screenshot', 'review':'source-matched','rights':'Projektbild; Rechte der enthaltenen Spielgrafiken beim Rechteinhaber.'})
  route['media']=shots
# Minecraft specific update
mc=by_id['minecraft']
mc['blurb']='Java und Bedrock sind verschiedene Editionen. Fuer Java gibt es mehrere Launcher und voneinander unabhaengige Dual-Screen-Companions mit konkreten Versionsbindungen.'
for r in mc['routes']:
 if r['id']=='mc-exojosh':
  r['name']='ExoJosh / Fabric + Android Companion'
  r['requires'][1]='Fabric Loader mindestens 0.19.3 und Fabric API fuer Java 1.21.11'
  r['benefit']='Versetzt HUD, Karte, Inventar und Chat auf das zweite Display; beide Komponenten kommunizieren lokal.'
  r['requiredVersion']='Java 1.21.11, Fabric >= 0.19.3, passende Fabric API'
  r['sources']=['exojosh','exojosh-app','zalith']
mc['routes'].append({
 'id':'mc-zalith','name':'Minecraft Java via Zalith Launcher 2','kind':'java','edition':'Java Edition (versionabhaengig)',
 'runtime':'Zalith Launcher 2','targets':['android'],'features':['mods'],
 'requires':['Rechtmaessig erworbene Minecraft Java Edition','Zum gewuenschten Mod passende Java-, Loader- und Renderer-Version'],
 'benefit':'Java-Edition mit Modloadern auf Android, Basis fuer ausgewaehlte Dual-Screen-Mods.',
 'caveat':'Ohne zusaetzlichen Companion kein automatischer Dual-Screen-Mod. Keine Benchmark-Aussage.','sources':['zalith'],
 'effort':'guided','status':'documented','dual':None,
 'steps':['Launcher von der Projektquelle beziehen','Java-Profil und passende Runtime konfigurieren','Funktion ohne Mods pruefen'],
 'stores':[],'requiredVersion':None,'reviewedAt':'2026-11-08','testedOn':[],'performance':None})
mc['routes'].append({
 'id':'mc-abacus','name':'Abacus Dual Screen / Forge-Web-Companion','kind':'companion','edition':'Java Edition 1.21.1',
 'runtime':'Minecraft Forge + Web/Android Companion',
 'targets':['android','linux-x86_64','windows-x86_64'],
 'features':['dual-screen','mods'],
 'requires':['Minecraft Java 1.21.1','MinecraftForge 52.x, Java 21','Passender Server-Mod und Companion-Browser auf zweitem Bildschirm','Ggf. Rechner im lokalen Netzwerk; lokaler Android-Betrieb nicht von Atlas getestet'],
 'benefit':'Stellt Karte, Inventar und Status als interaktive Webansicht bereit. Unterer Bildschirm kann Browser anzeigen.',
 'caveat':'Anderer Mod als ExoJosh. Quellcode ist source-available, nicht frei zum Spiegeln. Webserver ohne Standard-Authentifizierung: nur in vertrauenswuerdigem Netz einsetzen.','sources':['abacus-dual'],
 'effort':'advanced','status':'documented','dual':'Web Companion fuer die zweite Anzeige',
 'steps':['Exakte Java-, Forge- und Java-Laufzeitversion abgleichen.','Mod von Originalquelle laden und lokalen Netzwerkzugriff absichern.','Companion im Browser des zweiten Bildschirms oeffnen.'],
 'stores':[],'requiredVersion':'Minecraft Java 1.21.1; Forge 52.x','reviewedAt':'2026-11-08','testedOn':[],'performance':None})
# Additional variants, source-backed: Stardew and Terraria
for title,fran,original,ver in [('Stardew Valley','Stardew Valley','PC / Android','SMAPI'),('Terraria','Terraria','PC / Android','tModLoader')]:
 g={'id':slug(title),'title':title,'franchise':fran,'original':original,'genre':'Simulation / Sandbox',
 'theme':'forest' if title.startswith('Stardew') else 'ruins','blurb':'Quellprojekt dokumentiert Web-Companion fuer einen zweiten Bildschirm. Kein Atlas-Geraetetest.','reviewedAt':'2026-11-08','routes':[]}
 g['routes'].append({'id':f'{g["id"]}-abacus','name':f'{title} + Abacus Companion', 'kind':'companion',
   'edition':'PC-Mod-Edition','runtime':ver+' + Browser/Android Companion','targets':['android','linux-x86_64','windows-x86_64'],
   'features':['dual-screen','mods'], 'requires':['Eigene PC-Spieldateien und Installation','Passende Mod-Umgebung '+ver,'Zweiter Bildschirm mit Browser/Companion'],
   'benefit':'Interaktives Zusatzdisplay fuer Status und Spielinformationen.',
   'caveat':'Mod laeuft in einer passenden PC-Umgebung; Start auf Android in einem Windows-Container nicht belegt.',
   'sources':['abacus-dual'],'effort':'advanced','status':'documented','dual':'Web Companion',
   'steps':['Originalprojekt und konkrete Mod-Version pruefen','Eigene Spielstaende sichern','Server-Mod und Browser-Companion nach Dokumentation einrichten'],
   'stores':[],'requiredVersion':ver,'reviewedAt':'2026-11-08','testedOn':[],'performance':None})
 c['games'].append(g)
# coarse look-up list for discovery and watchlists. Manual seed, not evidence of compatibility.
platforms={
'Nintendo 64':'''Super Mario 64|Mario Kart 64|Mario Party|Mario Party 2|Mario Party 3|The Legend of Zelda: Ocarina of Time|The Legend of Zelda: Majora's Mask|Banjo-Kazooie|Banjo-Tooie|Donkey Kong 64|GoldenEye 007|Perfect Dark|Star Fox 64|F-Zero X|Pilotwings 64|Paper Mario|Yoshi's Story|Kirby 64: The Crystal Shards|Pokémon Stadium|Pokémon Stadium 2|Pokémon Snap|Diddy Kong Racing|Conker's Bad Fur Day|Wave Race 64|1080° Snowboarding|Excitebike 64|Bomberman 64|Turok: Dinosaur Hunter|Turok 2: Seeds of Evil|Rayman 2: The Great Escape|Jet Force Gemini|Blast Corps|Ogre Battle 64|Harvest Moon 64|Mystical Ninja Starring Goemon|Super Smash Bros.|Resident Evil 2''',
'SNES':'''Super Mario World|Super Mario World 2: Yoshi's Island|Super Mario All-Stars|Super Mario Kart|Super Metroid|The Legend of Zelda: A Link to the Past|Chrono Trigger|EarthBound|Final Fantasy IV|Final Fantasy V|Final Fantasy VI|Secret of Mana|Trials of Mana|Terranigma|Illusion of Gaia|ActRaiser|Soul Blazer|Super Castlevania IV|Castlevania: Dracula X|Mega Man X|Mega Man X2|Mega Man X3|Donkey Kong Country|Donkey Kong Country 2|Donkey Kong Country 3|Super Mario RPG|Star Fox|F-Zero|Kirby's Dream Land 3|Kirby Super Star|Super Ghouls 'n Ghosts|Super Punch-Out!!|Contra III: The Alien Wars|Street Fighter II|Street Fighter II Turbo|Super Bomberman|Super Bomberman 2|Breath of Fire|Breath of Fire II|Lufia II: Rise of the Sinistrals|Harvest Moon|Super R-Type|Gradius III|Super Turrican|The Legend of the Mystical Ninja''',
'Game Boy / Game Boy Color':'''Tetris|Super Mario Land|Super Mario Land 2: 6 Golden Coins|Wario Land: Super Mario Land 3|Wario Land II|Wario Land 3|The Legend of Zelda: Link's Awakening DX|The Legend of Zelda: Oracle of Ages|The Legend of Zelda: Oracle of Seasons|Pokémon Red|Pokémon Blue|Pokémon Yellow|Pokémon Gold|Pokémon Silver|Pokémon Crystal|Pokémon Trading Card Game|Kirby's Dream Land|Kirby's Dream Land 2|Donkey Kong (1994)|Donkey Kong Land|Metroid II: Return of Samus|Mario Tennis|Mario Golf|Dragon Warrior Monsters|Dragon Warrior Monsters 2|Shantae|Mole Mania|Wario Blast|Bomberman Quest|Mega Man V|The Final Fantasy Legend|The Final Fantasy Legend II''',
'Game Boy Advance':'''Metroid Fusion|Metroid: Zero Mission|The Legend of Zelda: The Minish Cap|The Legend of Zelda: A Link to the Past & Four Swords|Pokémon Ruby|Pokémon Sapphire|Pokémon Emerald|Pokémon FireRed|Pokémon LeafGreen|Pokémon Mystery Dungeon: Red Rescue Team|Mario & Luigi: Superstar Saga|Mario Kart: Super Circuit|Super Mario Advance|Super Mario Advance 2|Super Mario Advance 3|Super Mario Advance 4|Wario Land 4|WarioWare, Inc.: Mega Microgames!|WarioWare: Twisted!|Golden Sun|Golden Sun: The Lost Age|Advance Wars|Advance Wars 2: Black Hole Rising|Fire Emblem|Fire Emblem: The Sacred Stones|Final Fantasy Tactics Advance|Castlevania: Circle of the Moon|Castlevania: Harmony of Dissonance|Castlevania: Aria of Sorrow|Kirby: Nightmare in Dream Land|Kirby & the Amazing Mirror|Mother 3|Astro Boy: Omega Factor|Sonic Advance|Sonic Advance 2|Sonic Advance 3|Drill Dozer|Boktai: The Sun Is in Your Hand|Mega Man Battle Network''',
'Nintendo DS':'''New Super Mario Bros.|Mario Kart DS|Super Mario 64 DS|Mario & Luigi: Partners in Time|Mario & Luigi: Bowser's Inside Story|The Legend of Zelda: Phantom Hourglass|The Legend of Zelda: Spirit Tracks|Pokémon Diamond|Pokémon Pearl|Pokémon Platinum|Pokémon HeartGold|Pokémon SoulSilver|Pokémon Black|Pokémon White|Pokémon Black 2|Pokémon White 2|Pokémon Mystery Dungeon: Explorers of Sky|Animal Crossing: Wild World|Chrono Trigger|Castlevania: Dawn of Sorrow|Castlevania: Portrait of Ruin|Castlevania: Order of Ecclesia|Metroid Prime Hunters|Kirby: Canvas Curse|Kirby: Squeak Squad|Kirby: Mass Attack|The World Ends with You|Professor Layton and the Curious Village|Professor Layton and the Diabolical Box|Phoenix Wright: Ace Attorney|Hotel Dusk: Room 215|Ghost Trick: Phantom Detective|Elite Beat Agents|Rhythm Heaven|Advance Wars: Dual Strike|Advance Wars: Days of Ruin|Golden Sun: Dark Dawn|Dragon Quest IX|Fire Emblem: Shadow Dragon|Nintendogs''',
'Nintendo 3DS':'''Super Mario 3D Land|Mario Kart 7|New Super Mario Bros. 2|Mario & Luigi: Dream Team|Mario & Luigi: Paper Jam|The Legend of Zelda: Ocarina of Time 3D|The Legend of Zelda: Majora's Mask 3D|The Legend of Zelda: A Link Between Worlds|The Legend of Zelda: Tri Force Heroes|Metroid: Samus Returns|Pokémon X|Pokémon Y|Pokémon Omega Ruby|Pokémon Alpha Sapphire|Pokémon Sun|Pokémon Moon|Pokémon Ultra Sun|Pokémon Ultra Moon|Animal Crossing: New Leaf|Monster Hunter 4 Ultimate|Monster Hunter Generations|Fire Emblem: Awakening|Fire Emblem Fates|Fire Emblem Echoes: Shadows of Valentia|Kid Icarus: Uprising|Luigi's Mansion: Dark Moon|Kirby: Planet Robobot|Kirby: Triple Deluxe|Bravely Default|Bravely Second: End Layer|Fantasy Life|Tomodachi Life|Resident Evil: Revelations|Minecraft: New Nintendo 3DS Edition''',
'PlayStation':'''Final Fantasy VII|Final Fantasy VIII|Final Fantasy IX|Metal Gear Solid|Resident Evil|Resident Evil 2|Resident Evil 3: Nemesis|Silent Hill|Castlevania: Symphony of the Night|Crash Bandicoot|Crash Bandicoot 2|Crash Bandicoot: Warped|Spyro the Dragon|Spyro 2: Ripto's Rage!|Spyro: Year of the Dragon|Gran Turismo|Gran Turismo 2|Tekken 3|Ridge Racer Type 4|Vagrant Story|Parasite Eve|Parasite Eve II|Xenogears|Chrono Cross|Suikoden II|Tony Hawk's Pro Skater 2|Tomb Raider|Tomb Raider II|Ape Escape|Final Fantasy Tactics|Oddworld: Abe's Oddysee|Harvest Moon: Back to Nature''',
'PlayStation 2':'''Grand Theft Auto III|Grand Theft Auto: Vice City|Grand Theft Auto: San Andreas|Metal Gear Solid 2: Sons of Liberty|Metal Gear Solid 3: Snake Eater|Final Fantasy X|Final Fantasy X-2|Final Fantasy XII|Kingdom Hearts|Kingdom Hearts II|Shadow of the Colossus|Ico|God of War|God of War II|Ratchet & Clank|Ratchet & Clank: Going Commando|Ratchet & Clank: Up Your Arsenal|Jak and Daxter|Jak II|Jak 3|Sly Cooper and the Thievius Raccoonus|Sly 2: Band of Thieves|Sly 3: Honor Among Thieves|Persona 3 FES|Persona 4|Okami|Devil May Cry|Devil May Cry 3|Burnout 3: Takedown|Gran Turismo 4|Silent Hill 2|Silent Hill 3|Resident Evil 4|Dragon Quest VIII|Bully|The Simpsons: Hit & Run''',
'Nintendo Switch':'''The Legend of Zelda: Breath of the Wild|The Legend of Zelda: Tears of the Kingdom|The Legend of Zelda: Link's Awakening|The Legend of Zelda: Echoes of Wisdom|Super Mario Odyssey|Super Mario Bros. Wonder|Super Mario 3D World + Bowser's Fury|Mario Kart 8 Deluxe|Super Smash Bros. Ultimate|Metroid Dread|Metroid Prime Remastered|Animal Crossing: New Horizons|Pokémon Sword|Pokémon Shield|Pokémon Legends: Arceus|Pokémon Scarlet|Pokémon Violet|Fire Emblem: Three Houses|Fire Emblem Engage|Persona 5 Royal|Pikmin 4|Xenoblade Chronicles 2|Xenoblade Chronicles 3|Luigi's Mansion 3|Kirby and the Forgotten Land|Hades|Hollow Knight|Stardew Valley|Dave the Diver|Minecraft''',
'PC':'''Minecraft|Minecraft Dungeons|The Elder Scrolls III: Morrowind|The Elder Scrolls IV: Oblivion|The Elder Scrolls V: Skyrim|Fallout 3|Fallout: New Vegas|Fallout 4|Cyberpunk 2077|The Witcher 3: Wild Hunt|Baldur's Gate 3|Hollow Knight|Celeste|Hades|Stardew Valley|Terraria|Balatro|Slay the Spire|Portal|Portal 2|Half-Life|Half-Life 2|DOOM (1993)|DOOM II|DOOM 3|Quake|Quake II|Quake III Arena|Return to Castle Wolfenstein|Deus Ex|System Shock 2|Diablo II|Diablo III|The Binding of Isaac: Rebirth|Factorio|RimWorld|Project Zomboid|Cuphead|Undertale|Risk of Rain 2'''
}
# Provide separate display-accurate names where old catalog has localized titles.
aliases={'Pokemon Emerald':'pokemon-emerald','Pokémon Emerald':'pokemon-emerald','The Legend of Zelda: Majora\'s Mask':'majoras-mask','The Legend of Zelda: The Minish Cap':'minish-cap'}
lookup={g['title'].casefold():g for g in c['games']}
index=[];ids=set(g['id'] for g in c['games']);unique={}
for platform,raw in platforms.items():
 for title in [x.strip() for x in raw.split('|') if x.strip()]:
  key=title.casefold()
  if key in lookup:
   g=lookup[key]; g.setdefault('knownPlatforms',[])
   if platform not in g['knownPlatforms']:g['knownPlatforms'].append(platform)
   continue
  if key not in unique:
   id=slug(title)
   if id in ids:
    id+='-'+slug(platform)
   ids.add(id)
   if title.startswith('The Legend of Zelda') or title.startswith('Zelda') :franchise='The Legend of Zelda'
   elif title.startswith('Pokémon') or title.startswith('Pokemon'):franchise='Pokémon'
   elif title.startswith('Mario Kart'):franchise='Mario Kart'
   elif title.startswith('Super Mario') or title.startswith('Mario ') or title.startswith('Mario & Luigi') :franchise='Super Mario'
   elif title.startswith('Donkey Kong'):franchise='Donkey Kong'
   elif title.startswith('Final Fantasy'):franchise='Final Fantasy'
   elif title.startswith('Resident Evil'):franchise='Resident Evil'
   elif title.startswith('Castlevania'):franchise='Castlevania'
   elif title.startswith('The Elder Scrolls'):franchise='The Elder Scrolls'
   elif title.startswith('Mega Man'):franchise='Mega Man'
   elif title.startswith('Metroid'):franchise='Metroid'
   elif title.startswith('Fire Emblem'):franchise='Fire Emblem'
   elif title.startswith('Animal Crossing'):franchise='Animal Crossing'
   elif title.startswith('Kirby'):franchise='Kirby'
   elif title.startswith('Star Fox'):franchise='Star Fox'
   elif title.startswith('Sonic'):franchise='Sonic'
   elif title.startswith('Wario'):franchise='Wario'
   elif title.startswith('Minecraft'):franchise='Minecraft'
   elif title.startswith('Crash Bandicoot'):franchise='Crash Bandicoot'
   else:franchise=title
   unique[key]={'id':id,'title':title,'franchise':franchise,'platforms':[platform]}
  else:
   if platform not in unique[key]['platforms']:unique[key]['platforms'].append(platform)
index=list(unique.values())
c['gameIndex']=index
PATH.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
print('Expanded routes:',len(c['games']),sum(len(g['routes']) for g in c['games']),'index:',len(index),'total games:',len(c['games'])+len(index))
