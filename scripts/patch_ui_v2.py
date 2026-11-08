from pathlib import Path
p=Path(__file__).resolve().parents[1]/'src/app.js'
s=p.read_text()
def subst(old,new,where=''):
 global s
 if old not in s: raise SystemExit('MISSING '+where+repr(old[:150]))
 s=s.replace(old,new,1)
subst("  const catalog = JSON.parse($('#catalog-data').textContent);", """  const catalog = JSON.parse($('#catalog-data').textContent);
  // Broad index entries are watchable but never treated as tested or installable.
  for (const item of (catalog.gameIndex || [])) {
    catalog.games.push({id:item.id,title:item.title,franchise:item.franchise,
      original:item.platforms.join(' · '),knownPlatforms:item.platforms,genre:'Spielindex',theme:'orbit',
      blurb:'Im allgemeinen Spieleindex erfasst. Noch keine einzeln geprüfte Variante in Atlas.',
      routes:[],indexOnly:true});
  }
""",'index')
subst("  const defaults = () => ({q:'',profile:prefs.profile,feature:'',kind:'',franchise:'',evidence:'',sort:'editorial',showOtherPlatforms:false,includeArchived:false});", """  let visibleLimit=48;
  const defaults = () => ({q:'',profile:prefs.profile,feature:'',kind:'',franchise:'',evidence:'',effort:'',original:'',sort:'editorial',showOtherPlatforms:false,includeArchived:false});""",'defaults')
# Add actual source-screenshot rendering helper before gameCard
needle="  function gameCard(game,routes) {"
insert="""  function primaryShot(routes) {return routes.flatMap(r=>r.media||[]).find(m=>C.safeURL(m.url));}
  function shotImage(m,css='') {
    const src=C.safeURL(m.url);
    if(!src)return '';
    return `<img class="${css}" src="${E(src)}" alt="${E(m.caption||'Screenshot der Spielvariante')}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
  }
  function routeScreens(r,limit=3) {
    const items=(r.media||[]).filter(m=>C.safeURL(m.url)).slice(0,limit);
    if(!items.length) return `<div class="media-unavailable">${icon('info')} Für diesen Spielweg fehlt noch ein zugeordneter, überprüfter Screenshot. ${link(sources.get(r.sources[0])?.url||'','Bilder im Originalprojekt suchen')}</div>`;
    return `<div class="route-screen-grid">${items.map(m=>`<figure class="route-shot"><a href="${E(C.safeURL(m.url))}" target="_blank" rel="noopener noreferrer" title="Originalbild öffnen">${shotImage(m)}</a><figcaption><span>${E(m.caption)}</span>${link(m.sourceUrl,'Quelle')}</figcaption></figure>`).join('')}</div>`;
  }
"""
subst(needle,insert+needle,'shot helper')
# gameCard replace entire function up to discover
start=s.index('  function gameCard(game,routes) {')
end=s.index('  function discover() {',start)
s=s[:start]+'''  function gameCard(game,routes) {
    const indexed=!game.routes.length;
    const dual=routes.some(r=>r.features.includes('dual-screen'));
    const kinds=[...new Set(routes.map(r=>catalog.kinds[r.kind]))];
    const media=primaryShot(routes);
    const artPart=media?`<div class="game-cover">${shotImage(media,'game-cover-img')}<span class="cover-credit">Screenshot: ${E(media.sourceLabel||'Originalprojekt')}</span></div>`:art(game,indexed?'Für Watchlist':dual?icon('dual')+'Dual-Screen':icon('box')+'Varianten');
    return `<article class="game-card ${indexed?'index-card':''}">
      <button type="button" class="save-btn ${prefs.watch[game.id]?'saved':''}" data-watch="${game.id}" aria-label="${prefs.watch[game.id]?'Aus Merkliste entfernen':'Merken'}: ${E(game.title)}" aria-pressed="${!!prefs.watch[game.id]}">${icon('bookmark')}</button>
      <button type="button" class="card-open" data-game="${game.id}" aria-label="${E(game.title)}: ${indexed?'Watchlist / Recherche':'Spielwege ansehen'}">${artPart}
       <div class="card-copy"><div class="card-meta">${E(game.original)}${indexed?' · nicht geprüft':' · '+E(game.genre)}</div><h3>${E(game.title)}</h3><div class="route-tags">${indexed?tag('Noch keine geprüften Wege','amber'):kinds.slice(0,2).map(k=>tag(k)).join('')}</div></div></button>
      <div class="card-bottom"><span>${indexed?'Spieleindex / Watchlist':routes.length+' von '+game.routes.length+' Spielwegen'}</span><button type="button" data-game="${game.id}"><strong>${indexed?'Ansehen':'Varianten'} ${icon('arrow')}</strong></button></div></article>`;
  }
''' + s[end:]
# replace whole discover function before franchisesView
start=s.index('  function discover() {')
end=s.index('  function franchisesView() {',start)
s=s[:start]+'''  function discover() {
    const results=C.filterGames(catalog,filters,prefs.watch);
    const franchises=[...new Set(catalog.games.map(g=>g.franchise))].sort((a,b)=>a.localeCompare(b,'de'));
    const platforms=[...new Set(catalog.games.flatMap(g=>g.knownPlatforms||[]))].sort((a,b)=>a.localeCompare(b,'de'));
    const routeCount=catalog.games.reduce((n,g)=>n+g.routes.length,0);
    const hero=`<section class="hero"><div><div class="eyebrow">THOR FIRST · ANDROID · OFFENE HANDHELDS</div><h1>Ein Spiel.<br><span>Alle Möglichkeiten.</span></h1><p>Entdecke Dual-Screen-Projekte, Ports und PC-Spielwege – oder merke dir ein beliebiges Spiel für zukünftige Mods. Dokumentierte Varianten und allgemeiner Spielindex bleiben getrennt.</p><div class="hero-actions"><button class="primary" type="button" data-feature="dual-screen">${icon('dual')} Dual-Screen entdecken</button><button class="secondary" type="button" data-nav="watchlist">Meine Merkliste ${icon('arrow')}</button></div></div><div class="hero-art" aria-hidden="true"><div class="handheld"><div class="screen top"><div class="hero-diamond"></div><span>DISCOVER EVERY WAY TO PLAY.</span></div><div class="screen bottom"><div class="mini-map"></div></div><div class="float-label">${icon('check')} Editionen und Mods verbinden</div><div class="float-label bottom">${icon('dual')} Bilder direkt an der Variante</div></div></div></section>`;
    const quick=[['','Alles','compass'],['dual-screen','Dual-Screen','dual'],['mods','Mods & Erweiterungen','spark'],['widescreen','Widescreen','settings'],['controller','Controller','box']];
    const cheapNotice=filters.effort?'<p class="footer-note">Einfach einzurichten meint wenige dokumentierte Setup-Schritte, nicht garantierte Performance oder Akkulaufzeit.</p>':'';
    return `${mobileProfile()}${hero}<div class="stat-strip"><span class="stat"><strong>${catalog.games.length}</strong> Spiele (inkl. Watchlist-Index)</span><span class="stat"><strong>${catalog.games.filter(g=>g.routes.length).length}</strong> mit dokumentierten Spielwegen</span><span class="stat"><strong>${routeCount}</strong> Varianten</span><span class="evidence-note">${icon('shield')} Index ≠ Kompatibilitätsnachweis.</span></div>
      <div class="section-heading" id="browse"><div><h2>${filters.franchise?E(filters.franchise):'Was willst du spielen?'}</h2><p>Spiele entdecken, Wege vergleichen oder für neue Mods beobachten.</p></div><span class="result-count" aria-live="polite">${results.length} Spiele</span></div>
      <div class="quick-filters">${quick.map(([f,t,i])=>`<button class="chip ${filters.feature===f?'active':''}" data-feature="${f}" type="button" aria-pressed="${filters.feature===f}">${icon(i)}${t}</button>`).join('')}
       <button class="chip ${filters.effort==='easy'?'active':''}" data-easy type="button">${icon('check')} Einfaches Setup</button>
       <button class="chip" type="button" data-info-battery>${icon('pulse')} Akkulaufzeit?</button></div>
      <div class="filters"><div class="filter-control"><label for="kind">Technischer Weg</label><select id="kind" data-filter="kind">${options([['','Alle Wege'],...Object.entries(catalog.kinds)],filters.kind)}</select></div>
      <div class="filter-control"><label for="original">Konsole / Plattform</label><select id="original" data-filter="original">${options([['','Alle Plattformen'],...platforms.map(p=>[p,p])],filters.original)}</select></div>
      <div class="filter-control"><label for="franchise">Franchise</label><select id="franchise" data-filter="franchise">${options([['','Alle Franchises'],...franchises.map(f=>[f,f])],filters.franchise)}</select></div>
      <div class="filter-control"><label for="evidence">Stand</label><select id="evidence" data-filter="evidence">${options([['','Mit Watchlist-Index'],['documented','Nur dokumentierte Varianten']],filters.evidence)}</select></div>
      <div class="filter-control"><label for="sort">Sortieren</label><select id="sort" data-filter="sort">${options([['editorial','Relevanz / dokumentiert zuerst'],['az','Alphabetisch']],filters.sort)}</select></div>
      <label class="filter-check"><input type="checkbox" data-filter="showOtherPlatforms" ${filters.showOtherPlatforms?'checked':''}> Auch andere Betriebssysteme</label><button class="reset-button" type="button" data-reset>Filter löschen</button></div>
      ${cheapNotice}<section class="game-grid" aria-label="Spielergebnisse">${results.length?results.slice(0,visibleLimit).map(x=>gameCard(x.game,x.routes)).join(''):`<div class="empty">${icon('search')}<h3>Keine passende, geprüfte Variante gefunden.</h3><p>Das ist kein Beweis, dass das Spiel nicht existiert. Für Akku- und FPS-Filter fehlen noch systematisch erhobene Messwerte.</p><button class="secondary" type="button" data-reset>Filter zurücksetzen</button></div>`}</section>
      ${results.length>visibleLimit?`<div class="load-more"><button class="secondary" type="button" data-more>Mehr Spiele anzeigen (${results.length-visibleLimit} weitere)</button></div>`:''}
      <p class="footer-note">Stand ${date(catalog.reviewedAt)}. Ohne eigene ROMs, keine Downloads von Spieldaten. Externe Projektbilder werden mit Ursprungsquelle eingeblendet; offline stehen sie nicht zur Verfügung.</p>`;
  }
''' +s[end:]
# franchise view adjustments
subst("Dies ist eine Franchise-Sicht auf den Startkatalog, keine vollst\\u00e4ndige Liste aller Ver\\u00f6ffentlichungen.", "Dies ist ein erweiterter, noch nicht vollst\\u00e4ndiger Franchise-Index. Nur Spielwege mit Quellen gelten als dokumentiert.",'fran note')
# modify watchlist game deref already games map updated
subst("    else {prefs.watch[id]={interests:['updates'],addedAt:new Date().toISOString()};", "    else {prefs.watch[id]={interests:['dual-screen','updates'],addedAt:new Date().toISOString()};",'watch defaults')
# render route with gallery
start=s.index('  function routeCard(r) {')
end=s.index('  function comparison() {',start)
s=s[:start]+'''  function routeCard(r) {
    const fit=C.platformMatch(r,selectedProfile());
    const features=r.features.filter(f=>!['live-map','touch-inventory'].includes(f));
    return `<article class="route-card ${fit?'':'incompatible'}"><div class="route-head"><div>${tag(catalog.kinds[r.kind])} ${tag(statusLabel(r.status),r.status==='documented'?'green':'amber')}${!fit?' '+tag('Anderes Plattformprofil','amber'):''}<h3>${E(r.name)}</h3><p class="route-sub">${E(r.edition)} / ${E(r.runtime)}</p></div><label class="select-compare"><input type="checkbox" data-compare="${r.id}" ${comparing.has(r.id)?'checked':''}>Vergleichen</label></div>
      <div class="route-tags">${features.map(f=>tag(catalog.features[f],f==='dual-screen'?'green':'')).join('')||tag('Keine Zusatzfunktion belegt')}</div>
      <p class="route-benefit">${E(r.benefit)}</p>${routeScreens(r)}
      <p class="route-caveat">${E(r.caveat)}</p><details class="requirements"><summary>Voraussetzungen / ${E(effort(r.effort))}</summary><ul>${r.requires.map(t=>`<li>${E(t)}</li>`).join('')}</ul></details>
      <div class="route-actions"><button type="button" class="primary" data-setup="${r.id}">Setup ansehen ${icon('arrow')}</button>${link(sources.get(r.sources[0])?.url||'','Originalprojekt','secondary')}${r.stores.map(st=>link(st.url,E(st.name),'secondary')).join('')}</div>
      <p class="route-source">Quellen: ${r.sources.map(id=>link(sources.get(id)?.url||'',E(sources.get(id)?.name||id))).join(' / ')}<br>Redaktion: ${date(r.reviewedAt)} / Keine eigenen Gerätemessungen.${r.requiredVersion?`<br>Versionsbindung: ${E(r.requiredVersion)}`:''}</p></article>`;
  }
''' +s[end:]
# gallery media tab, and indexed page
subst("    if(tab==='routes')content=selected.routes.map(routeCard).join('')+`<div class=\"compare-bar\">", "    if(tab==='routes')content=(selected.routes.length?selected.routes.map(routeCard).join(''):`<div class=\"empty\"><h3>Dieses Spiel kannst du schon beobachten.</h3><p>Es ist im allgemeinen Spieleindex erfasst. Noch kein einzeln geprüfter, gerätespezifischer Spielweg liegt in Atlas vor. Das bedeutet NICHT, dass keine Emulation oder Mod existiert.</p><div class=\"toolbar\"><button class=\"primary\" data-watch=\"${selected.id}\" type=\"button\">${icon('bookmark')} ${prefs.watch[selected.id]?'Aus Merkliste entfernen':'Für Dual-Screen-Mods merken'}</button><button class=\"secondary\" data-research=\"${selected.id}\" type=\"button\">GitHub-Projekte suchen ${icon('external')}</button></div></div>`) + (selected.routes.length?`<div class=\"compare-bar\">",'index content')
# close the conditional previously opening at end of routes template
subst("<button type=\"button\" class=\"primary\" data-tab=\"compare\" ${comparing.size<2?'disabled':''}>Vergleich \\u00f6ffnen ${icon('arrow')}</button></div>`;", "<button type=\"button\" class=\"primary\" data-tab=\"compare\" ${comparing.size<2?'disabled':''}>Vergleich \\u00f6ffnen ${icon('arrow')}</button></div>`:'');",'close index compare')
start=s.index("    if(tab==='media')content=")
end=s.index("    $('#detail-content').innerHTML=",start)
s=s[:start]+'''    if(tab==='media')content=selected.routes.length?selected.routes.map(r=>`<section class="gallery-section"><h3>${E(r.name)}</h3><p class="route-sub">${E(r.edition)} · ${E(r.runtime)}</p>${routeScreens(r,15)}</section>`).join(''):'<p class="info-banner neutral">Für dieses Spiel liegen noch keine zugeordneten Projektbilder vor.</p>';
''' +s[end:]
# detail tab count, index hero tag
subst("['media','Bilder & Quellen']", "['media','Galerie je Variante']",'media label')
# default changes in event listener
subst("    if('feature' in b.dataset){filters.feature=b.dataset.feature;", "    if('feature' in b.dataset){filters.feature=b.dataset.feature;filters.effort='';visibleLimit=48;",'feature')
subst("    if('reset' in b.dataset){filters=defaults();", "    if('reset' in b.dataset){visibleLimit=48;filters=defaults();",'reset')
subst("    if('refresh' in b.dataset)refresh();", """    if('refresh' in b.dataset)refresh();
    if('more' in b.dataset){visibleLimit+=48;render();}
    if('easy' in b.dataset){filters.effort=filters.effort==='easy'?'':'easy';filters.feature='';visibleLimit=48;render();}
    if('infoBattery' in b.dataset)info('Akkufilter ist noch nicht belastbar','<p>Ein einfach zu emulierendes Retrospiel kann weniger Leistung benötigen, aber Laufzeit hängt von Bildschirmhelligkeit, Emulator, Displayanzahl, Leistungsprofil und Spiel ab. Atlas behauptet ohne standardisierte Messungen keine verifizierten Batteriewerte. Als Zwischenlösung kannst du nach ursprünglicher Konsole oder einfachem Setup filtern.</p>');
    if(b.dataset.research){const g=games.get(b.dataset.research);if(g){const q=encodeURIComponent('"'+g.title+'" dual screen android handheld');const url='https://github.com/search?q='+q+'&type=repositories';window.open(url,'_blank','noopener,noreferrer');}}
""",'more')
subst("    if(el.dataset.filter){filters[el.dataset.filter]=el.type==='checkbox'?el.checked:el.value;render();}", "    if(el.dataset.filter){filters[el.dataset.filter]=el.type==='checkbox'?el.checked:el.value;visibleLimit=48;render();}",'filters')
# sources route image note
subst("Die Spielkarten verwenden eigene abstrakte Illustrationen, keine behaupteten Screenshots. Echte Projektbilder werden auf den jeweiligen Originalseiten verlinkt.","Die Spielkarten zeigen dort Original-Screenshots, wo sie einer konkreten Variante über das Quellen-README zugeordnet wurden. Andere Karten zeigen weiterhin abstrakte Illustrationen. Projektbilder werden extern eingebettet, nicht in diesem Paket gespiegelt; Bild- und Spielgrafikrechte sind separat zu klären.",'sources img')
# note source pipeline
subst("${catalog.sources.length}</strong> Quellen & Anbindungen", "${catalog.sources.length}</strong> Quellen & Anbindungen",'noop') if False else None
p.write_text(s)
print('Patched UI',len(s))
