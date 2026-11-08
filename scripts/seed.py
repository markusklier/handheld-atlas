"""Editorial seed. Factual summaries are original; linked projects retain their rights."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
D = '2026-11-08'
S = {}
def source(id, name, url, repo=None, role='primary', note='Projekt-Dokumentation; keine unabh\u00e4ngige Ger\u00e4tepr\u00fcfung.'):
    S[id] = dict(id=id, name=name, url=url, repo=repo, role=role, checkedAt=D, note=note)
source('metroidarch','MetroidArch / Projektumzug','https://github.com/Raekwon1603/super_metroid-android', 'Raekwon1603/super_metroid-android')
source('metroidarch-new','MetroidArch','https://github.com/Raekwon1603/RetroArch/tree/metroidarch-dual-screen','Raekwon1603/RetroArch', note='Nachfolger durch das archivierte Ursprungsprojekt belegt; Branch beachten.')
source('snes9x','Libretro: Snes9x','https://docs.libretro.com/library/snes9x/')
source('mgba','Libretro: mGBA','https://docs.libretro.com/library/mgba/')
source('n64','Libretro: Mupen64Plus-Next','https://docs.libretro.com/library/mupen64plus/')
source('eden','Eden Duo','https://github.com/igawa6/eden-duo','igawa6/eden-duo')
source('minish','Minish Cap Dual Screen','https://github.com/samyost1/tmc-android','samyost1/tmc-android')
source('alttp','Zelda3 Android','https://github.com/samyost1/zelda3-android','samyost1/zelda3-android')
source('openmw-ds','OpenMW-DS','https://github.com/Josh-Daniels/OpenMW-DS','Josh-Daniels/OpenMW-DS')
source('openmw','OpenMW','https://github.com/OpenMW/openmw','OpenMW/openmw')
source('minecraft','Minecraft: offizielle Downloads','https://www.minecraft.net/en-us/download')
source('amethyst','Amethyst Android','https://github.com/AngelAuraMC/Amethyst-Android','AngelAuraMC/Amethyst-Android')
source('exojosh','Minecraft Second Screen: Fabric-Mod','https://github.com/exojosh/AynThorSecondScreen','exojosh/AynThorSecondScreen')
source('exojosh-app','Minecraft Second Screen: Companion','https://github.com/exojosh/Android_AynThor_MinecraftSecondScreen','exojosh/Android_AynThor_MinecraftSecondScreen')
source('chrono','ChronoDuo','https://github.com/kalenjohnson/chrono-duo','kalenjohnson/chrono-duo')
source('melonds','melonDS Android','https://github.com/rafaelvcaetano/melonDS-android','rafaelvcaetano/melonDS-android')
source('balatro','Balatro Dual Screen','https://github.com/rosbean/balatro-dualscreen','rosbean/balatro-dualscreen')
source('balatro-official','Balatro: offizielle Spielseite','https://www.playbalatro.com/')
source('banjo','BanjoRecomp Android','https://github.com/AurelioB/BanjoRecomp-Android','AurelioB/BanjoRecomp-Android')
source('pokedaisy','PokeDaisy','https://github.com/lidor30/pokedaisy','lidor30/pokedaisy')
source('gamenative','GameNative','https://github.com/utkarshdalal/GameNative','utkarshdalal/GameNative',note='Belegt die Laufzeitumgebung, nicht die Spielbarkeit von Cyberpunk auf dem Thor.')
source('droiddeck','DroidDeck','https://github.com/Droid-Deck/DroidDeck','Droid-Deck/DroidDeck',note='Belegt die Laufzeitumgebung, nicht einen Cyberpunk-Benchmark. Hardwareanforderungen beachten.')
source('2ship','2 Ship 2 Harkinian Android','https://github.com/Waterdish/2ship2harkinian-Android','Waterdish/2ship2harkinian-Android')
source('zelda64','Zelda64Recomp','https://github.com/Zelda64Recomp/Zelda64Recomp','Zelda64Recomp/Zelda64Recomp')
source('gaft','GAFT','https://andreyvelsk.github.io/GAFT/', 'andreyvelsk/GAFT','discovery','Entdeckungsquelle. Kein vollst\u00e4ndiger Katalogimport; Rechte an Texten und Bildern separat kl\u00e4ren.')
source('dual-list','Dual-Screen-Games','https://github.com/codm2000/Dual-Screen-Games','codm2000/Dual-Screen-Games','discovery','Linkquelle, nicht als Beleg f\u00fcr gemessene Performance verwendet.')
source('native-ports','Awesome Android Native Ports','https://github.com/abduznik/awesome-android-native-ports','abduznik/awesome-android-native-ports','discovery','Liste unter CC0. Es werden Projektlinks als unbestaetigte Kandidaten erfasst, keine Projektdateien heruntergeladen.')
source('opengameports','OpenGamePorts','https://opengameports.com/',None,'discovery','Manuelle Entdeckungsquelle. Kein automatischer Vollimport und keine Bilduebernahme aktiviert; Datenrechte und Schnittstelle separat klaeren.')
source('recompa','Recompa','https://github.com/kalasyan/recompa',None,'planned','JSON-Katalog vorhanden; kein Import aktiviert. Katalogrechte separat vom Anwendungscode kl\u00e4ren.')
source('emuready','EmuReady API','https://www.emuready.com/docs/api/reference',None,'planned','API dokumentiert; noch keine Berichte importiert. Nutzungsbedingungen und Zuordnung pr\u00fcfen.')
source('igdb','IGDB API','https://api-docs.igdb.com/',None,'planned','F\u00fcr Stammdaten, Franchises und Bilder vorgesehen. Zugang und kommerzielle Partnerschaft noch nicht eingerichtet.')
source('portmaster','PortMaster','https://portmaster.games/',None,'planned','Linux-Handheld-Ports als n\u00e4chste Katalogerweiterung; noch kein Import.')

S['metroidarch-new']['watchBranch']='metroidarch-dual-screen'

ANDROID=['android']
MULTI=['android','linux-x86_64','linux-arm64','windows-x86_64']
G=[]
def game(id,title,franchise,original,genre,theme,blurb):
    g=dict(id=id,title=title,franchise=franchise,original=original,genre=genre,theme=theme,blurb=blurb,reviewedAt=D,routes=[])
    G.append(g); return g

def route(g,id,name,kind,edition,runtime,targets,features,requires,benefit,caveat,sources,effort='guided',status='documented',dual=None,steps=None,stores=None,version=None):
    g['routes'].append(dict(id=id,name=name,kind=kind,edition=edition,runtime=runtime,targets=targets,features=features,requires=requires,benefit=benefit,caveat=caveat,sources=sources,effort=effort,status=status,dual=dual,steps=steps or ['Projekt-Dokumentation und passende Version lesen.','Eigene Spieldateien und vorhandene Spielst\u00e4nde separat sichern.','Anleitung des Projekts befolgen; zuerst ohne zus\u00e4tzliche Mods testen.'],stores=stores or [],requiredVersion=version,reviewedAt=D,testedOn=[],performance=None))
def emu(g,id,platform,core,src):
    route(g,id,platform+' via RetroArch','emulation',platform,core,MULTI,[],['Eigene passende '+platform+'-ROM','RetroArch und verf\u00fcgbarer '+core+'-Core'], 'Originalfassung in einem gemeinsamen Emulator-Frontend.', 'Keine zus\u00e4tzliche Dual-Screen-Oberfl\u00e4che. Plattformweg dokumentiert; diese Kombination nicht auf einem Ger\u00e4t getestet.',[src],effort='guided')

g=game('super-metroid','Super Metroid','Metroid','SNES','Action-Adventure','orbit','Original-Emulation oder eine Karte auf dem zweiten Display? Hier werden die Unterschiede sichtbar.')
route(g,'sm-metroidarch','MetroidArch','emulator-mod','SNES','RetroArch-Fork / bsnes-hd',ANDROID,['dual-screen','live-map','widescreen'],['Eigene kompatible Super-Metroid-ROM','MetroidArch, Branch metroidarch-dual-screen'],'Dual-Screen-Ansicht und Widescreen in einem spezialisierten RetroArch-Fork.','Kein nativer Recomp. Der alte APK-Port wurde abgel\u00f6st; Spielst\u00e4nde vor einem Wechsel sichern.',['metroidarch','metroidarch-new'],dual='Interaktive Zusatzansicht',version='Branch metroidarch-dual-screen')
emu(g,'sm-snes9x','SNES','Snes9x','snes9x')
route(g,'sm-legacy','Super Metroid Android (alt)','emulator-mod','SNES','Eigenst\u00e4ndige Android-APK',ANDROID,['dual-screen','live-map'],['Super Metroid (Japan, USA) (En,Ja)-ROM'],'Fr\u00fcherer Dual-Screen-Ansatz bleibt als Vergleich sichtbar.','Archiviert; das Projekt verweist auf MetroidArch. Nicht als Neueinstieg empfohlen.',['metroidarch'],status='archived',dual='Karte und Ausr\u00fcstung')

g=game('minecraft','Minecraft','Minecraft','Java / Bedrock','Sandbox','blocks','Bedrock ist nicht Java. Mods, Spielversion und Launcher geh\u00f6ren zu unterschiedlichen Wegen.')
route(g,'mc-bedrock','Bedrock f\u00fcr Android','native','Bedrock Edition','Offizielle Android-App',ANDROID,[],['Android-Lizenz f\u00fcr Minecraft'],'Offizieller Android-Vertriebsweg.','Java-Mods wie Exojoshs Second-Screen-Mod passen nicht zu dieser Edition. Keine Dual-Screen-Erweiterung hier belegt.',['minecraft'],effort='easy',stores=[{'name':'Offizielle Bezugsquellen','url':'https://www.minecraft.net/en-us/download'}])
route(g,'mc-java','Java mit Amethyst','java','Java Edition','Amethyst Android',ANDROID,['mods'],['Minecraft-Java-Lizenz','Zur Spielversion passende Java- und Renderer-Einstellungen'],'Java-Edition auf Android; Zugang zum Java-Mod-\u00d6kosystem.','Nicht Bedrock. Modloader, Renderer und Controller-Konfiguration m\u00fcssen zusammenpassen.',['amethyst','minecraft'],effort='advanced')
route(g,'mc-exojosh','Java + Exojosh Second Screen','companion','Java Edition 1.21.11','Zalith Launcher 2 / Pojav-basierter Launcher',ANDROID,['dual-screen','live-map','touch-inventory','mods'],['Minecraft Java 1.21.11','Fabric Loader ab 0.19.3 und passende Fabric API','Fabric-Mod UND Android-Companion','Zweiter Android-Presentation-Bildschirm'],'HUD, Karte, Inventar und Chat auf dem unteren Display.','Exakte Kombination beider Projekte erforderlich; nicht auf Bedrock oder beliebige neue Java-Versionen \u00fcbertragbar.',['exojosh','exojosh-app'],effort='advanced',dual='HUD + interaktives Inventar',version='Minecraft 1.21.11; Fabric >= 0.19.3',steps=['Java-Lizenz und die Version 1.21.11 pr\u00fcfen.','Eigenes Spielprofil und Welten sichern.','Fabric und Fabric API passend zur Version einrichten.','Mod und Companion aus den Originalprojekten beziehen.','Welt starten und Verbindung zwischen beiden Komponenten pr\u00fcfen.'])

g=game('morrowind','The Elder Scrolls III: Morrowind','The Elder Scrolls','PC','Rollenspiel','ruins','Dieselben Spieldaten, unterschiedliche Engines: Dual-Screen auf Android oder OpenMW am Linux-Handheld.')
route(g,'mw-ds','OpenMW-DS','source-port','PC-Spieldaten','OpenMW-DS',ANDROID,['dual-screen','live-map','touch-inventory','mods'],['Eigene Morrowind-Spieldaten','Mod-Kompatibilit\u00e4t mit dem verwendeten OpenMW-Build'],'Karte, Journal und Charakteroberfl\u00e4che auf dem zweiten Display.','Ein OpenMW-Fork, keine Windows-Emulation. Nicht jeder klassische Engine-Mod ist kompatibel.',['openmw-ds'],dual='Karte, Journal, Inventar')
route(g,'mw-openmw','OpenMW Desktop','source-port','PC-Spieldaten','OpenMW',['linux-x86_64','windows-x86_64'],['mods'],['Eigene Morrowind-Spieldaten','Passender Desktop-Build'],'Alternative Engine f\u00fcr offene Desktop-Handhelds.','Keine Aussage zur Thor-Android-Kompatibilit\u00e4t dieses Desktop-Builds.',['openmw'])

g=game('minish-cap','The Legend of Zelda: The Minish Cap','The Legend of Zelda','Game Boy Advance','Action-Adventure','forest','Ein nativer Dual-Screen-Port neben klassischer GBA-Emulation; die ROM-Region macht einen Unterschied.')
route(g,'tmc-dual','Minish Cap Dual Screen','decomp','GBA / USA-Baseline','Project Picori / Android',ANDROID,['dual-screen','live-map','touch-inventory','widescreen'],['Eigene baserom.gba','USA-Baseline: SHA-1 b4bd50e4131b027c334547b4524e2dbbd4227130','Zur Region passender Build'],'Karte, Queststatus und Touch-Inventar; Widescreen als Portfunktion.','EU-ROM mit USA-Build ist laut Projekt ein Hybrid mit m\u00f6glichen Abweichungen. APK ist debug-signiert.',['minish'],dual='Karte + Touch-Inventar',version='ROM-Region muss zur Build-Baseline passen')
emu(g,'tmc-mgba','GBA','mGBA','mgba')

g=game('metroid-dread','Metroid Dread','Metroid','Nintendo Switch','Action-Adventure','signal','Eine zus\u00e4tzliche Live-Karte entsteht hier durch einen Emulator-Fork und ein versionsgebundenes Companion-Paket.')
route(g,'dread-eden','Eden Duo + Companion','emulator-mod','Nintendo Switch','Eden Duo',ANDROID,['dual-screen','live-map'],['Eigene Spieldaten und erforderliche Systemdateien','Spiel-Update 2.1.0','Zum Spiel passendes Companion-Paket'],'Separater Companion auf dem zweiten Display.','Versionsbindung ist strikt. Kein FPS- oder Stabilit\u00e4tsnachweis f\u00fcr deinen Thor im Katalog.',['eden'],effort='advanced',dual='Spielabh\u00e4ngiger Companion',version='Metroid Dread 2.1.0')

g=game('chrono-trigger','Chrono Trigger','Chrono','SNES / Nintendo DS / Android','Rollenspiel','clock','DS-Edition, SNES-Original und Android-Spiel mit Companion sind drei verschiedene Wege, kein gemeinsamer Mod.')
route(g,'chrono-duo','Android + ChronoDuo','companion','Android / Google Play','ChronoDuo',ANDROID,['dual-screen','live-map'],['Offizielle Android-Version','ChronoDuo; projektspezifische Berechtigungen','Optionale eigene DS-ROM f\u00fcr bestimmte Karten'],'Android-Spiel mit erg\u00e4nzender Zweitbildschirm-Oberfl\u00e4che.','Nicht mit der DS-Edition gleichsetzen; Versions- und Berechtigungsanforderungen im Projekt pr\u00fcfen.',['chrono'],effort='advanced',dual='Companion zur Android-Version')
route(g,'chrono-ds','Nintendo-DS-Edition','emulation','Nintendo DS','melonDS Android',ANDROID,['two-screens'],['Eigene DS-ROM','melonDS; passende Bildschirmkonfiguration'],'Die DS-Spielversion besitzt bereits zwei Spielbildschirme.','Zwei emulierte Bildschirme garantieren noch keine Ausgabe auf zwei physischen Thor-Displays. Diese Zuordnung hier nicht verifiziert.',['melonds'],dual='Zwei Spielbildschirme; physische Ausgabe ungepr\u00fcft')
emu(g,'chrono-snes','SNES','Snes9x','snes9x')

g=game('balatro','Balatro','Balatro','PC / Android','Kartenspiel','cards','Offizielle Mobilversion oder ein Dual-Screen-Umbau deiner PC-Kopie: die Lizenz und Dateiformate unterscheiden sich.')
route(g,'balatro-dual','Balatro Dual Screen','native-mod','PC-Dateien auf Android','L\u00d6VE + Android-Overlay',ANDROID,['dual-screen','controller','fps-cap'],['Eigene PC- oder Mac-Kopie','Dokumentiert: Steam 1.0.1o; EXE, gezippte APP oder LOVE','Kein iOS-/Mac-App-Store-Build'],'Handkarten und Shop unten, Tisch und Punkte oben; Controller und Touch.','60/120-FPS-Limit ist eine Option, kein gemessener Performancewert. Andere PC-Versionen sind nicht pauschal best\u00e4tigt.',['balatro'],dual='Handkarten + Shop',version='Steam 1.0.1o')
route(g,'balatro-native','Offizielle Mobilversion','native','Android','Offizielle Android-App',ANDROID,[],['Eigene Android-Lizenz'],'Direkter offizieller Bezugsweg ohne Umbau einer PC-Kopie.','Nicht die Datenquelle f\u00fcr den hier gelisteten Dual-Screen-Umbau.',['balatro-official'],effort='easy',stores=[{'name':'Offizielle Spielseite','url':'https://www.playbalatro.com/'}])

g=game('banjo-kazooie','Banjo-Kazooie','Banjo-Kazooie','Nintendo 64','Platformer','peak','N64 emulieren oder einen Android-Recomp verwenden: gleiche Spielvorlage, anderer technischer Weg.')
route(g,'banjo-recomp','BanjoRecomp Android','recomp','Nintendo 64','N64: Recompiled / Android',ANDROID,['dual-screen'],['Eigene kompatible Banjo-Kazooie-ROM','Passender Android-Recomp-Build'],'Recompilation mit einer zus\u00e4tzlichen Informationsansicht.','Passende ROM-Revision vorab im Projekt pr\u00fcfen. Hier kein unabh\u00e4ngiger Ger\u00e4tetest.',['banjo'],dual='Spielfortschritt und Informationen')
emu(g,'banjo-n64','N64','Mupen64Plus-Next','n64')

g=game('a-link-to-the-past','The Legend of Zelda: A Link to the Past','The Legend of Zelda','SNES','Action-Adventure','forest','Die SNES-ROM kann als Grundlage f\u00fcr Emulation oder einen Android-Port mit eigener Oberfl\u00e4che dienen.')
route(g,'alttp-port','Zelda3 Android','decomp','SNES','Zelda3 Android-Fork',ANDROID,['dual-screen'],['Eigene kompatible Zelda3-ROM','Zum ROM passender Projekt-Build'],'Android-Port mit Dual-Screen-Erweiterung.','Eigene Port-Konfiguration; ROM-Revision und Funktionsumfang am aktuellen Projektstand pr\u00fcfen.',['alttp'],dual='Port-eigene Zusatzansicht')
emu(g,'alttp-snes','SNES','Snes9x','snes9x')

g=game('pokemon-emerald','Pok\u00e9mon Smaragd','Pok\u00e9mon','Game Boy Advance','Rollenspiel','wild','Ein Pok\u00e9mon-spezifischer Companion kann mehr anzeigen als ein allgemeiner GBA-Emulator.')
route(g,'emerald-pokedaisy','PokeDaisy','emulator-mod','GBA / Pok\u00e9mon Emerald','PokeDaisy',ANDROID,['dual-screen','live-map'],['Eigene unterst\u00fctzte ROM','ROM-spezifische Funktionsliste beachten'],'Spielbezogene Informationen und Companion statt einer blo\u00dfen zweiten Kopie des Bilds.','Nicht jede ROM-Region oder jeder Hack besitzt denselben Funktionsumfang.',['pokedaisy'],dual='Pok\u00e9mon-Companion')
emu(g,'emerald-mgba','GBA','mGBA','mgba')

g=game('majoras-mask',"The Legend of Zelda: Majora's Mask",'The Legend of Zelda','Nintendo 64','Action-Adventure','moon','Decomp-Port f\u00fcr Android, Recomp f\u00fcr Desktop und klassischer N64-Emulator bleiben getrennte Optionen.')
route(g,'mm-2ship','2 Ship 2 Harkinian Android','decomp','Nintendo 64','2 Ship 2 Harkinian',ANDROID,[],['Eigene kompatible ROM bzw. daraus erzeugte Spieldaten','Projektanleitung f\u00fcr Android'],'Android-Port auf Basis der Decompilation.','Dual-Screen hier nicht belegt; nicht automatisch mit Desktop-Recomp-Funktionen gleichsetzen.',['2ship'])
route(g,'mm-recomp','Zelda64Recomp','recomp','Nintendo 64','Zelda64Recomp',['linux-x86_64','windows-x86_64'],['mods'],['Eigene kompatible Majora-ROM','Passender Linux- oder Windows-Build'],'Statische Recompilation f\u00fcr Desktop-Handhelds.','Dieser Eintrag ist kein Android-Port und kein Nachweis f\u00fcr Linux auf ARM.',['zelda64'])
emu(g,'mm-n64','N64','Mupen64Plus-Next','n64')

g=game('cyberpunk-2077','Cyberpunk 2077','Cyberpunk','PC','Action-Rollenspiel','city','Ein bewusst offener Vergleich: zwei PC-Laufzeitumgebungen, aber noch kein belastbarer Thor-Benchmark.')
route(g,'cp-gamenative','GameNative (Pr\u00fcfkandidat)','pc-runtime','PC / Store-Ausgabe pr\u00fcfen','GameNative',ANDROID,[],['Eigene PC-Lizenz','Passendes Ger\u00e4t, Runtime und Treiber','Konkreter Spieltest steht aus'],'Eine m\u00f6gliche PC-Laufzeitumgebung zur Untersuchung.','Nur die Runtime ist belegt. Startbarkeit, FPS und beste Store-Ausgabe von Cyberpunk sind hier UNGETESTET. Keine Kaufempfehlung.',['gamenative'],effort='advanced',status='experimental')
route(g,'cp-droiddeck','DroidDeck (Pr\u00fcfkandidat)','pc-runtime','PC / Store-Ausgabe pr\u00fcfen','DroidDeck',ANDROID,[],['Eigene PC-Lizenz','Unterst\u00fctzte Adreno-Hardware laut Projekt','Linux-Runtime und ausreichend Speicher','Konkreter Spieltest steht aus'],'Alternative PC-Umgebung auf Android; als Kandidat vergleichbar.','Keine Aussage, dass Cyberpunk auf deinem Ger\u00e4t l\u00e4uft. Keine belegte Performance-Rangfolge gegen\u00fcber GameNative.',['droiddeck'],effort='advanced',status='experimental')

features={'dual-screen':'Physisches Dual-Screen','two-screens':'DS-Spielbildschirme','live-map':'Live-Karte','touch-inventory':'Touch-Inventar','widescreen':'Widescreen','mods':'Mod-Unterst\u00fctzung','controller':'Controller dokumentiert','fps-cap':'FPS-Limit w\u00e4hlbar','fps60-tested':'60 FPS gemessen'}
kinds={'emulation':'Emulation','emulator-mod':'Emulator + Mod','native':'Native App','native-mod':'Native App + Mod','decomp':'Decomp-Port','recomp':'Recompilation','source-port':'Source Port / Engine','companion':'Companion + Spiel','java':'Java-Launcher','pc-runtime':'PC-Laufzeitumgebung'}
profiles=[{'id':'thor','name':'AYN Thor / Android','platform':'android','dual':True},{'id':'android','name':'Android / ein Display','platform':'android','dual':False},{'id':'android-dual','name':'Android / zwei Displays','platform':'android','dual':True},{'id':'linux-x86_64','name':'Linux-Handheld / x86-64','platform':'linux-x86_64','dual':False},{'id':'linux-arm64','name':'Linux-Handheld / ARM64','platform':'linux-arm64','dual':False},{'id':'windows-x86_64','name':'Windows-Handheld / x86-64','platform':'windows-x86_64','dual':False},{'id':'all','name':'Alle Plattformen','platform':'all','dual':True}]
catalog={'schemaVersion':1,'version':'0.1.0','reviewedAt':D,'notice':'Redaktioneller Startkatalog, kein vollst\u00e4ndiger Spieleindex. Keine eigenen Hardwaretests.','features':features,'kinds':kinds,'profiles':profiles,'sources':list(S.values()),'games':G}
(ROOT/'data/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'data/updates.json').write_text(json.dumps({'schemaVersion':1,'lastAttemptAt':None,'lastSuccessAt':None,'projects':{},'events':[],'errors':[]},indent=2)+'\n')
(ROOT/'data/candidates.json').write_text(json.dumps({'schemaVersion':1,'candidates':[]},indent=2)+'\n')
print(len(G),'games;',sum(len(g['routes']) for g in G),'routes;',len(S),'sources')
