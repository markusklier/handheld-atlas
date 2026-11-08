from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'src/app.js'
s=p.read_text(encoding='utf-8')
def change(old,new,label):
 global s
 if old not in s: raise ValueError('Anchor missing: '+label+' | '+old[:90])
 s=s.replace(old,new,1)

change("  const quality = JSON.parse($('#quality-data').textContent);",
"  const quality = JSON.parse($('#quality-data').textContent);\n  let mediaLibrary = JSON.parse($('#media-data').textContent);\n  const platformPaths = JSON.parse($('#platform-paths-data').textContent);\n  const gameAddons = JSON.parse($('#addons-data').textContent);",'initial embedded data')
change("  function primaryShot(routes) {return routes.flatMap(r=>r.media||[]).find(m=>C.safeURL(m.url));}","""  const artHosts = new Set(['images.igdb.com','shared.fastly.steamstatic.com',
    'shared.cloudflare.steamstatic.com','shared.akamai.steamstatic.com','shared.steamstatic.com',
    'cdn.cloudflare.steamstatic.com','cdn.akamai.steamstatic.com',
    'raw.githubusercontent.com','cdn.modrinth.com','media.forgecdn.net','mediafilez.forgecdn.net']);
  function safeArtwork(raw) {
    const url=C.safeURL(raw);
    if(!url)return null;
    try { const parsed=new URL(url);return artHosts.has(parsed.hostname) ? url : null; }
    catch(_){return null;}
  }
  function gameMedia(game) { return mediaLibrary.games?.[game.id] || {}; }
  function generalShot(game) {return (gameMedia(game).screenshots||[]).find(x=>safeArtwork(x.url));}
  function routeShot(game,routes) {
    return routes.flatMap(r=>(r.media||[]).map(m=>({...m,routeName:r.name,dual:r.features.includes('dual-screen')})))
      .find(m=>safeArtwork(m.url));
  }
  function primaryShot(routes) {return routes.flatMap(r=>r.media||[]).find(m=>safeArtwork(m.url));}
  function artworkImage(image,css='') {
    const url=safeArtwork(image?.url);
    if(!url)return '';
    return `<img class="${css}" src="${E(url)}" alt="${E(image.caption||'Spielmotiv')}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
  }
  function platformSuggestions(game) {
    const platforms=game.knownPlatforms||[];
    return (platformPaths.paths||[]).filter(path=>platforms.includes(path.platform));
  }
  function gameAddonsFor(game) {return gameAddons.games?.[game.id]||[];}
  function originalShots(game,limit=8) {
    const media=gameMedia(game);
    const shots=(media.screenshots||[]).filter(m=>safeArtwork(m.url)).slice(0,limit);
    if(!shots.length)return '<p class="media-unavailable">Noch keine allgemeinen Originalspiel-Screenshots mit bestätigter Zuordnung verfügbar.</p>';
    return `<div class="route-screen-grid">${shots.map(m=>`<figure class="route-shot"><a href="${E(safeArtwork(m.url))}" target="_blank" rel="noopener noreferrer">${artworkImage(m,'original-shot')}</a><figcaption>Originalspiel · kein Handheld-Test. ${link(m.sourceUrl,'Bildquelle')}</figcaption></figure>`).join('')}</div>`;
  }
  function platformOptions(game) {
    const paths=platformSuggestions(game);
    if(!paths.length)return '';
    return `<section class="platform-path-section"><div class="section-heading"><div><h3>Weitere mögliche Wege über die Originalplattform</h3><p>Plattformbasierte Ansätze – ausdrücklich keine Einzelspiel- oder Thor-Kompatibilitätstests</p></div></div><div class="platform-path-grid">${paths.map(p=>`<article class="platform-option"><div>${tag('Möglicher Emulatorweg','amber')} ${tag(p.platform)}</div><h3>${E(p.name)}</h3><p>${E(p.description)}</p><div class="route-actions">${link(p.projectUrl,'Offizielles Projekt')}</div></article>`).join('')}</div></section>`;
  }
  function addOnSection(game) {
    const addons=gameAddonsFor(game);
    if(!addons.length)return '<div class="media-unavailable">Für dieses Spiel liegen noch keine separat katalogisierten Performance- oder Erweiterungsmods vor.</div>';
    return `<div class="info-banner amber">Performance-Mods und Erweiterungen sind nicht automatisch auf Android oder dem Thor kompatibel. Die Versionen von Spiel, Launcher und Modloader müssen zusammenpassen.</div><div class="platform-path-grid">${addons.map(a=>`<article class="platform-option"><div>${tag(a.category.includes('performance')?'Performance-Mod':'Erweiterung','amber')} ${tag(a.edition||'Edition prüfen')}</div><h3>${E(a.name)}</h3><p>${E(a.description)}</p><p class="footer-note">Thor-Test: nicht vorhanden · Modversion/Loader separat prüfen</p><div class="route-actions">${link(a.projectUrl,'Mod-Projekt')}</div></article>`).join('')}</div>`;
  }
  function editionLinks(game) {
    const related=catalog.games.filter(g=>g.id!==game.id && g.franchise===game.franchise).slice(0,10);
    if(!related.length)return '';
    return `<section class="related-editions"><h3>Weitere Spiele und Editionen der Reihe</h3><div class="edition-chips">${related.map(g=>`<button type="button" class="chip" data-game="${g.id}">${E(g.title)} ${icon('arrow')}</button>`).join('')}</div></section>`;
  }""",'art and metadata helpers')
start=s.index('  function gameCard(game,routes) {');end=s.index('  function discover() {',start)
if not (start>=0 and end>start):raise ValueError('gamecard bounds')
s=s[:start]+"""  function gameCard(game,routes) {
    const indexed=!game.routes.length;
    const dual=routes.some(r=>r.features.includes('dual-screen'));
    const kinds=[...new Set(routes.map(r=>catalog.kinds[r.kind]))];
    const official=gameMedia(game).cover;
    const cover=safeArtwork(official?.url)?official:null;
    const original=generalShot(game);
    const route=routeShot(game,routes);
    const dualView=filters.feature==='dual-screen' && dual;
    const primary=dualView?(route||cover||original):(cover||route||original);
    const preview=dualView?(original||cover||route):(route||original||cover);
    const credit=primary===cover?'Spielcover / Originalgrafik':primary===route?'Bild des dokumentierten Spielwegs':'Originalspiel-Screenshot';
    const base=art(game,indexed?'Spieleindex':dual?icon('dual')+'Dual-Screen':icon('box')+'Spielwege');
    const showCover=safeArtwork(primary?.url);
    const hover=safeArtwork(preview?.url);
    const artPart=showCover?`<div class="game-cover cover-aspect ${primary?.portrait?'cover-portrait':''}">${base}${artworkImage(primary,'game-cover-img')}${hover&&hover!==showCover?`<img class="hover-preview" data-hover-src="${E(hover)}" alt="${E(preview?.caption||'Spielvorschau')}" decoding="async">`:''}${cover&&primary!==cover?`<div class="inset-cover">${artworkImage(cover)}</div>`:''}<span class="cover-credit">${E(credit)}</span></div>`:
      `<div class="game-cover cover-aspect">${base}<span class="cover-credit">Noch kein belegtes Spielcover</span></div>`;
    const pathCount=platformSuggestions(game).length;
    return `<article class="game-card ${indexed?'index-card':''}">
      <button type="button" class="save-btn ${prefs.watch[game.id]?'saved':''}" data-watch="${game.id}" aria-label="${prefs.watch[game.id]?'Aus Merkliste entfernen':'Merken'}: ${E(game.title)}" aria-pressed="${!!prefs.watch[game.id]}">${icon('bookmark')}</button>
      <button type="button" class="card-open" data-game="${game.id}" aria-label="${E(game.title)}: ${indexed?'Mögliche Spielwege und Recherche':'Spielwege ansehen'}">${artPart}
       <div class="card-copy"><div class="card-meta">${E(game.original)}${indexed?' · nicht getestet':' · '+E(game.genre)}</div><h3>${E(game.title)}</h3><div class="route-tags">${indexed?tag(pathCount?`${pathCount} Plattformoption${pathCount>1?'en':''}`:'Noch keine geprüften Wege','amber'):kinds.slice(0,2).map(k=>tag(k)).join('')}</div></div></button>
      <div class="card-bottom"><span>${indexed?'Spieleindex / mögliche Wege':routes.length+' von '+game.routes.length+' dokumentierten Wegen'}</span><button type="button" data-game="${game.id}"><strong>Ansehen ${icon('arrow')}</strong></button></div></article>`;
  }
"""+s[end:]
# updated discovery copy and status counts
change("<p>Spiele entdecken, Wege vergleichen oder für neue Mods beobachten.</p>","<p>Cover, Originalspiel-Screenshots und Variantenbilder entdecken – Spielwege getrennt von Kompatibilitätstests.</p>",'discover descriptor')
# redesign franchise imagery
start=s.index('  function franchisesView() {');end=s.index('  function watchlistView() {',start)
if start<0 or end<0:raise ValueError('franchises bounds')
s=s[:start]+"""  function franchisesView() {
    const groups=[...new Set(catalog.games.map(g=>g.franchise))].sort();
    return `${mobileProfile()}<div class="page-title"><div class="eyebrow">FRANCHISE → SPIEL → EDITION → SPIELWEG</div><h1>Franchises entdecken.</h1><p>Spielcover, Originalplattformen und Community-Spielwege gemeinsam durchstöbern.</p></div><div class="info-banner neutral">Eine Reihe hat oft mehrere Editionen; ihr Cover ist eine repräsentative Grafik eines konkreten Spiels, kein eigenes offizielles Franchise-Cover.</div><section class="franchise-grid">${groups.map(f=>{const gs=catalog.games.filter(g=>g.franchise===f);const covers=gs.map(g=>gameMedia(g).cover).filter(m=>safeArtwork(m?.url)).slice(0,3);
    return `<button type="button" class="franchise-card" data-franchise="${E(f)}"><span class="franchise-cover-strip">${covers.length?covers.map(m=>artworkImage(m,'franchise-cover-thumb')).join(''):`<span class="franchise-placeholder">${icon('library')}</span>`}</span><h3>${E(f)}</h3><p>${gs.length} Spiele · ${gs.reduce((n,g)=>n+g.routes.length,0)} dokumentierte Spielwege</p></button>`;
   }).join('')}</section>`;
  }
"""+s[end:]
# detail routes & other edition links
change("if(tab==='routes')content=(selected.routes.length?selected.routes.map(routeCard).join(''):","if(tab==='routes')content=(selected.routes.length?selected.routes.map(routeCard).join(''):",'routes anchor placeholder')
change(" +'',"," +'',",'noop') if False else None
# append platform options when routes tab (before next comparison)
change("    if(tab==='compare')content=comparison();","    if(tab==='routes')content += platformOptions(selected)+editionLinks(selected);\n    if(tab==='compare')content=comparison();",'routes append')
change("    if(tab==='media')content=selected.routes.length?selected.routes.map(r=>", "    if(tab==='media')content=selected.routes.length?selected.routes.map(r=>",'media anchor placeholder')
change("    if(tab==='media') content += unreviewedScreens(selected);",
"    if(tab==='media') content = `<section class=\"gallery-section\"><h3>Originalspiel · allgemeine Spielszenen</h3><p class=\"footer-note\">Screenshots des Originalspiels – nicht eines Mods oder Emulators.</p>${originalShots(selected)}</section>`+content+unreviewedScreens(selected);\n    if(tab==='mods')content=addOnSection(selected);",'original media')
change("<div class=\"detail-hero\">${art(selected)}<div>",
"<div class=\"detail-hero\">${safeArtwork(gameMedia(selected).cover?.url)?`<div class=\"detail-cover\">${artworkImage(gameMedia(selected).cover,'detail-game-cover')}<span>Original-Cover / ${E(gameMedia(selected).provenance||'Metadatenquelle')}</span></div>`:art(selected)}<div>",'detail cover')
change("['media','Galerie je Variante'],['research','Recherche-Stand']",
"['media','Bilder: Original & Varianten'],['mods',`Mods & Performance (${gameAddonsFor(selected).length})`],['research','Recherche-Stand']",'new mods tab')
# when detail open and new item hover updated
change("  document.addEventListener('click',async event=>{", """  // On desktop, lazily fetch game-specific preview screenshots on hover or keyboard focus.
  // No third-party script and no image fetch before actual card interaction.
  function loadPreview(card) {
    const image=card?.querySelector('img[data-hover-src]');
    const url=safeArtwork(image?.dataset.hoverSrc);
    if(image&&url&&!image.getAttribute('src'))image.setAttribute('src',url);
  }
  document.addEventListener('pointerover',event=>{
    if(window.matchMedia('(hover:hover)').matches)loadPreview(event.target.closest('.game-card'));
  });
  document.addEventListener('focusin',event=>loadPreview(event.target.closest('.game-card')));
  document.addEventListener('error',event=>{
    if(event.target?.tagName==='IMG' && event.target.classList.contains('game-cover-img'))event.target.hidden=true;
    if(event.target?.tagName==='IMG' && event.target.classList.contains('hover-preview'))event.target.hidden=true;
  },true);
  document.addEventListener('click',async event=>{""",'hover preview lazy')
# get safer game media refresh (only from same origin)
needle="      const [ru,rp]=await Promise.all([\n        fetch('data/updates.json',{cache:'no-store'}),\n        fetch('data/projects.json',{cache:'no-store'})\n      ]);"
if needle in s:
 s=s.replace(needle,"""      const [ru,rp,rm]=await Promise.all([
        fetch('data/updates.json',{cache:'no-store'}),
        fetch('data/projects.json',{cache:'no-store'}),
        fetch('data/game_media.json',{cache:'no-store'})
      ]);""")
 s=s.replace("const [next,nextProjects]=await Promise.all([ru.json(),rp.json()]);",
             "const [next,nextProjects,nextMedia]=await Promise.all([ru.json(),rp.json(),rm.json()]);")
 s=s.replace("      updates=next;projects=nextProjects;render();", "      updates=next;projects=nextProjects;if(nextMedia?.schemaVersion===1&&typeof nextMedia.games==='object')mediaLibrary=nextMedia;render();")
p.write_text(s,encoding='utf-8')
# UI and source HTML
p=ROOT/'src/template.html';s=p.read_text(encoding='utf-8')
s=s.replace('OPEN CATALOG <span>v0.4</span>','OPEN CATALOG <span>v0.5</span>') if False else s
needle='<script id="quality-data" type="application/json">/*__QUALITY__*/</script>'
assert needle in s
s=s.replace(needle,needle+'\n<script id="media-data" type="application/json">/*__MEDIA__*/</script>\n<script id="platform-paths-data" type="application/json">/*__PLATFORM_PATHS__*/</script>\n<script id="addons-data" type="application/json">/*__ADDONS__*/</script>')
p.write_text(s,encoding='utf-8')
p=ROOT/'scripts/build.py';s=p.read_text(encoding='utf-8')
s=s.replace("'QUALITY':json_embed(ROOT/'data/quality_report.json')}","'QUALITY':json_embed(ROOT/'data/quality_report.json'),\n             'MEDIA':json_embed(ROOT/'data/game_media.json'),\n             'PLATFORM_PATHS':json_embed(ROOT/'data/platform_paths.json'),\n             'ADDONS':json_embed(ROOT/'data/game_addons.json')}")
s=s.replace("https://mediafilez.forgecdn.net; manifest-src", "https://mediafilez.forgecdn.net https://shared.fastly.steamstatic.com https://shared.cloudflare.steamstatic.com https://shared.akamai.steamstatic.com https://shared.steamstatic.com https://cdn.cloudflare.steamstatic.com https://cdn.akamai.steamstatic.com https://images.igdb.com; manifest-src")
s=s.replace("'projects.json']:","'projects.json','game_media.json','platform_paths.json','game_addons.json']:")
s=s.replace("'data/projects.json'];", "'data/projects.json','data/game_media.json','data/platform_paths.json','data/game_addons.json'];")
p.write_text(s,encoding='utf-8')
# card styles appended to existing style
p=ROOT/'src/style.css';s=p.read_text(encoding='utf-8');s+='''
/* 0.5 – Launcher-style cover browser. Original game artwork and variant screenshots stay separate. */
@media(min-width:1150px){.game-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:17px}}
@media(min-width:1750px){.game-grid{grid-template-columns:repeat(5,minmax(0,1fr))}}
.game-cover.cover-aspect{position:relative;aspect-ratio:3/4;overflow:hidden;min-height:0;height:auto;background:#151d1a}
.game-cover.cover-aspect .game-art{height:100%;min-height:0;position:absolute;inset:0}
.game-cover.cover-aspect .game-cover-img{display:block;position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1}
.game-cover.cover-portrait .game-cover-img{object-position:center}
.game-cover .hover-preview{position:absolute;inset:0;z-index:2;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .25s;pointer-events:none}
@media(hover:hover){.game-card:hover .hover-preview[src],.game-card:focus-within .hover-preview[src]{opacity:1}}
.game-cover.cover-aspect .cover-credit{z-index:4;font-size:9px;letter-spacing:.015em;background:#111d18d9;color:#dfebe3;bottom:8px;left:8px;border-radius:6px;padding:6px 8px;max-width:calc(100% - 16px)}
.game-cover .inset-cover{position:absolute;z-index:3;right:8px;top:8px;width:53px;height:76px;border:2px solid #edf6eb;box-shadow:0 4px 14px #000a;border-radius:4px;overflow:hidden;background:#151d1a}
.game-cover .inset-cover img{width:100%;height:100%;object-fit:cover}
.game-cover img[hidden]{display:none!important}
.card-copy{min-height:117px}.card-copy h3{font-size:15px;line-height:1.3}
.franchise-cover-strip{display:flex;align-items:stretch;justify-content:center;height:126px;gap:6px;margin-bottom:16px}
.franchise-cover-thumb{max-width:31%;width:80px;height:125px;object-fit:cover;border-radius:6px;box-shadow:0 7px 15px #0008}
.franchise-placeholder{display:flex;align-items:center;justify-content:center;width:100%;min-height:104px;background:linear-gradient(125deg,#33443b,#1c2926);border-radius:8px;color:#b2f4cb}
.detail-hero>.detail-cover{width:132px;height:189px;flex:0 0 132px;border-radius:10px;background:#151f19;overflow:hidden;position:relative}
.detail-game-cover{height:100%;width:100%;object-fit:cover}
.detail-cover>span{position:absolute;left:0;right:0;bottom:0;padding:7px;background:#14231ddc;font-size:8px;color:#d8f0dd}
.platform-path-section,.related-editions{padding:16px 0 20px;border-top:1px solid var(--line);margin-top:20px}
.platform-path-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.platform-option{border:1px solid var(--line);background:var(--panel);padding:16px;border-radius:12px;display:flex;flex-direction:column;gap:10px}
.platform-option h3{font-size:15px;letter-spacing:-.02em}.platform-option p{font-size:12px;color:var(--muted)}
.platform-option .route-actions{margin-top:auto}.edition-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}
.original-shot{width:100%;height:100%;object-fit:cover}
@media(max-width:800px){.game-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.card-copy{padding:11px;min-height:118px}.card-copy h3{font-size:12px}.platform-path-grid{grid-template-columns:1fr}.detail-hero>.detail-cover{width:100px;height:148px;flex:0 0 100px}}
@media(max-width:430px){.game-grid{gap:8px}.game-cover .inset-cover{width:40px;height:58px}.game-cover.cover-aspect .cover-credit{font-size:8px;padding:4px 6px}.franchise-cover-strip{height:104px}.franchise-cover-thumb{height:102px}}
'''
p.write_text(s,encoding='utf-8')
print('Patch 0.5 UI completed')
