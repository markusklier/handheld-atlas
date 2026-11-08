/* Handheld Atlas - local-first discovery, no remote execution. */
(() => {
  'use strict';
  const C = window.AtlasCore;
  const $ = s => document.querySelector(s);
  const E = C.escapeHTML;
  const catalog = JSON.parse($('#catalog-data').textContent);
  // Broad index entries are watchable but never treated as tested or installable.
  for (const item of (catalog.gameIndex || [])) {
    catalog.games.push({id:item.id,title:item.title,franchise:item.franchise,
      original:item.platforms.join(' · '),knownPlatforms:item.platforms,genre:'Spielindex',theme:'orbit',
      blurb:'Im allgemeinen Spieleindex erfasst. Noch keine einzeln geprüfte Variante in Atlas.',
      routes:[],indexOnly:true});
  }

  let updates = JSON.parse($('#updates-data').textContent);
  let candidates = JSON.parse($('#candidates-data').textContent);
  const research = JSON.parse($('#research-data').textContent);
  let projects = JSON.parse($('#projects-data').textContent);
  const quality = JSON.parse($('#quality-data').textContent);
  const auditByGame = new Map((quality.games || []).map(x=>[x.gameId,x]));
  const sources = new Map(catalog.sources.map(s => [s.id, s]));
  const games = new Map(catalog.games.map(g => [g.id, g]));
  const KEY = 'handheld-atlas.preferences.v1';
  let storageAvailable = true;
  let prefs = {schemaVersion:1, watch:{}, customGames:{}, checks:{}, profile:'thor', lastSeen:null};
  try { const raw = localStorage.getItem(KEY); if(raw) prefs = C.sanitizePreferences(JSON.parse(raw), catalog); }
  catch (_) { storageAvailable = false; }
  // User-provided titles are local placeholders, never compatibility claims.
  function restoreCustomGames() {
    for(const [id,c] of Object.entries(prefs.customGames || {})) {
      if(games.has(id))continue;
      const game={id,title:c.title,franchise:'Eigene Suchliste',original:c.platform,
        knownPlatforms:c.platform && c.platform!=='Plattform unbekannt'?[c.platform]:[],
        genre:'Eigener Spieleintrag',theme:'orbit',blurb:'Von dir als Erinnerung angelegt. Noch nicht in Atlas redaktionell zugeordnet; keine automatische Projektbenachrichtigung.',routes:[],indexOnly:true,customOnly:true};
      catalog.games.push(game); games.set(id,game);
    }
  }
  restoreCustomGames();
  let view = 'discover', selected = null, tab = 'routes', comparing = new Set(), deferredInstall = null;
  let lastFocus = null;
  let visibleLimit=48;
  const defaults = () => ({q:'',profile:prefs.profile,feature:'',kind:'',franchise:'',evidence:'',effort:'',original:'',sort:'editorial',showOtherPlatforms:false,includeArchived:false});
  let filters = defaults();
  const icons = {
    compass:'<circle cx="12" cy="12" r="9"/><path d="m15.7 8.3-2.3 5.1-5.1 2.3 2.3-5.1z"/>',
    library:'<path d="M4 4h4v16H4zM10 4h4v16h-4zM16 5l3-1 4 15-3 1z"/>',
    bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
    pulse:'<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    search:'<circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/>',
    dual:'<rect x="4" y="2" width="16" height="9" rx="2"/><rect x="4" y="13" width="16" height="9" rx="2"/><path d="M9 17h6"/>',
    arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    external:'<path d="M14 3h7v7M21 3 10 14M10 4H4v16h16v-6"/>',
    shield:'<path d="m12 2 8 3v6c0 5-8 11-8 11S4 16 4 11V5zM8 12l3 3 5-6"/>',
    check:'<path d="m5 12 4 4L20 5"/>',
    close:'<path d="m5 5 14 14M19 5 5 19"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    settings:'<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
    spark:'<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3z"/>',
    box:'<path d="m12 2 9 5v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>'
  };
  const icon = n => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[n] || icons.box}</svg>`;
  const link = (url,text,cls='') => {const safe=C.safeURL(url);return safe?`<a class="${cls}" href="${E(safe)}" target="_blank" rel="noopener noreferrer">${text} ${icon('external')}</a>`:`<span>${text}</span>`;};
  const date = s => s && Number.isFinite(Date.parse(s)) ? new Date(s).toLocaleDateString('de-DE') : 'Noch nicht ausgef\u00fchrt';
  const statusLabel = s => ({documented:'Projekt dokumentiert',experimental:'Ungetesteter Kandidat',archived:'Archiviert / ersetzt'}[s] || 'Unbekannt');
  const effort = s => ({easy:'Einfach',guided:'Mit Anleitung',advanced:'Fortgeschritten'}[s] || s);
  const tag = (text,kind='') => `<span class="tag ${kind}">${E(text)}</span>`;
  const selectedProfile = () => catalog.profiles.find(p => p.id === prefs.profile);
  const platformName = s => ({android:'Android','linux-x86_64':'Linux x86-64','linux-arm64':'Linux ARM64','windows-x86_64':'Windows x86-64'}[s] || s);
  const options = (entries,value) => entries.map(([key,label]) => `<option value="${E(key)}"${key===value?' selected':''}>${E(label)}</option>`).join('');
  const profileOptions = () => options(catalog.profiles.map(p=>[p.id,p.name]),prefs.profile);
  const mobileProfile = () => `<div class="mobile-profile"><label for="mobile-device">Profil</label><select id="mobile-device" data-profile>${profileOptions()}</select></div>`;
  function toast(message) { $('#toast').textContent=message; $('#toast').classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('visible'),4300); }
  function persist() { try {localStorage.setItem(KEY, JSON.stringify(prefs));} catch (_) {storageAvailable=false;toast('Speichern ist blockiert. Nutze den JSON-Export zur Sicherung.');} renderNav(); }
  function download(name,value,type='application/json') {const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000);}
  function renderNav() {
    const items=[['discover','Entdecken','compass'],['franchises','Franchises','library'],['watchlist','Merkliste','bookmark'],['updates','Aktuelles','pulse'],['sources','Daten & Quellen','database']];
    $('#nav').innerHTML=items.map(([id,label,i])=>`<button type="button" class="nav-item ${view===id?'active':''}" data-nav="${id}" ${view===id?'aria-current="page"':''}>${icon(i)}${label}${id==='watchlist'&&Object.keys(prefs.watch).length?`<span class="nav-number">${Object.keys(prefs.watch).length}</span>`:''}</button>`).join('');
    $('#watch-count').textContent=Object.keys(prefs.watch).length;
    $('#device').innerHTML=profileOptions();
  }
  const themes={orbit:['#152432','#3a738c','#a1d6de'],blocks:['#243429','#597947','#c9d9a2'],ruins:['#30252b','#815856','#e0c3a7'],forest:['#1d302b','#46735b','#bdddb6'],signal:['#292535','#5e4c86','#d4c5e9'],clock:['#332c22','#8b6c3a','#f0d49e'],cards:['#34252a','#914e56','#edbbb0'],peak:['#1f3040','#477a9a','#c5e3df'],wild:['#23362c','#408c62','#c3e4b6'],moon:['#2c253b','#74528b','#e3d2f3'],city:['#303122','#7c7932','#e6e39b']};
  function art(game,chip='') {
    const [base,glow,ink]=themes[game.theme] || themes.orbit;
    const paths={
      orbit:'<circle cx="170" cy="100" r="49" fill="none" stroke="currentColor" stroke-width="1"/><circle cx="170" cy="100" r="70" fill="none" stroke="currentColor" opacity=".25"/><path d="M82 124h47V79h42v45h45V61h42" fill="none" stroke="currentColor" stroke-width="7"/><circle cx="129" cy="123" r="8" fill="currentColor"/>',
      blocks:'<path d="m85 92 40-21 40 21-40 23zM125 115v44l40-22V92M85 92v45l40 22m43-67 40-21 40 21-40 23zM208 115v44l40-22V92M168 92v45l40 22m-82-89 40-21 40 21-40 23zM166 71v43l40-22V48M126 48v43l40 23" fill="none" stroke="currentColor" stroke-width="2"/>',
      ruins:'<path d="M75 151h190M96 150V85h34v65m-39-68 22-20 22 20M157 150V62h34v88m-39-91 22-30 22 30M218 150v-49h25v49" fill="none" stroke="currentColor" stroke-width="3"/><circle cx="255" cy="46" r="17" fill="currentColor" opacity=".25"/>',
      forest:'<path d="m168 40-66 110h132z" fill="none" stroke="currentColor" stroke-width="2"/><path d="m168 71-34 58h68zM168 40v31M102 150l32-21m100 21-32-21" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="168" cy="109" r="61" fill="none" stroke="currentColor" opacity=".2"/>',
      signal:'<path d="M95 144V86h48V48h51v66h48v30z" fill="none" stroke="currentColor" stroke-width="3"/><path d="M112 125h17V99h31V66h18v65h46" fill="none" stroke="currentColor" stroke-width="2" opacity=".5"/><circle cx="194" cy="114" r="9" fill="currentColor"/>',
      clock:'<circle cx="170" cy="98" r="59" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="170" cy="98" r="48" fill="none" stroke="currentColor" opacity=".4"/><path d="M170 53v45l30 19M170 38v11M170 148v11M111 98h11M217 98h11" fill="none" stroke="currentColor" stroke-width="3"/>',
      cards:'<g transform="rotate(-13 165 100)"><rect x="109" y="40" width="80" height="113" rx="8" fill="none" stroke="currentColor" stroke-width="2"/></g><g transform="rotate(10 184 100)"><rect x="150" y="40" width="80" height="113" rx="8" fill="var(--base)" stroke="currentColor" stroke-width="2"/><path d="m190 69 19 27-19 27-19-27z" fill="currentColor" opacity=".7"/></g>',
      peak:'<path d="m77 150 59-88 36 47 27-69 65 110z" fill="none" stroke="currentColor" stroke-width="2"/><path d="m136 62 17 47-18-8-16 19m80-80 17 51-17-10-15 15" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="102" cy="50" r="12" fill="currentColor" opacity=".4"/>',
      wild:'<circle cx="170" cy="98" r="54" fill="none" stroke="currentColor" stroke-width="2"/><path d="M116 98h37m34 0h37M170 44v25m0 58v25" fill="none" stroke="currentColor" stroke-width="2"/><path d="m170 77 21 21-21 21-21-21z" fill="none" stroke="currentColor" stroke-width="2"/>',
      moon:'<path d="M181 42c-48 0-79 44-55 83 24 39 80 33 99-6-43 11-70-37-44-77z" fill="none" stroke="currentColor" stroke-width="2"/><path d="m240 53 3 9 9 3-9 3-3 9-3-9-9-3 9-3zM99 88l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" fill="currentColor"/>',
      city:'<path d="M71 152h205M90 152V91h30v61m13 0V61h33v91m13 0V38h36v114m13 0V77h31v75M195 38V26M146 61V47" fill="none" stroke="currentColor" stroke-width="2"/><path d="M98 102h12m-12 12h12m31-38h15m-15 12h15m31-33h20m-20 13h20m29 29h14" fill="none" stroke="currentColor" stroke-width="3"/>'
    };
    return `<div class="game-art" style="--base:${base};--glow:${glow};--ink:${ink}"><svg viewBox="0 0 340 190" aria-hidden="true">${paths[game.theme] || paths.orbit}</svg>${chip?`<span class="art-chip">${chip}</span>`:''}<span class="art-label">Illustration / kein Spielbild</span></div>`;
  }
  function primaryShot(routes) {return routes.flatMap(r=>r.media||[]).find(m=>C.safeURL(m.url));}
  function shotImage(m,css='') {
    const src=C.safeURL(m.url);
    if(!src)return '';
    return `<img class="remote-photo ${css}" src="${E(src)}" alt="${E(m.caption||'Screenshot der Spielvariante')}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
  }
  function routeScreens(r,limit=3) {
    const items=(r.media||[]).filter(m=>C.safeURL(m.url)).slice(0,limit);
    if(!items.length) return `<div class="media-unavailable">${icon('info')} Für diesen Spielweg fehlt noch ein zugeordneter, überprüfter Screenshot. ${link(sources.get(r.sources[0])?.url||'','Bilder im Originalprojekt suchen')}</div>`;
    return `<div class="route-screen-grid">${items.map(m=>`<figure class="route-shot"><a href="${E(C.safeURL(m.url))}" target="_blank" rel="noopener noreferrer" title="Originalbild öffnen"><span class="image-placeholder">Bild vom Originalprojekt laden oder hier öffnen</span>${shotImage(m)}</a><figcaption><span>${E(m.caption)}</span>${link(m.sourceUrl,'Quelle')}</figcaption></figure>`).join('')}</div>`;
  }
  function gameCard(game,routes) {
    const indexed=!game.routes.length;
    const dual=routes.some(r=>r.features.includes('dual-screen'));
    const kinds=[...new Set(routes.map(r=>catalog.kinds[r.kind]))];
    const media=primaryShot(routes);
    const artPart=media?`<div class="game-cover">${art(game)}${shotImage(media,'game-cover-img')}<span class="cover-credit">Screenshot: ${E(media.sourceLabel||'Originalprojekt')}</span></div>`:art(game,indexed?'Für Watchlist':dual?icon('dual')+'Dual-Screen':icon('box')+'Varianten');
    return `<article class="game-card ${indexed?'index-card':''}">
      <button type="button" class="save-btn ${prefs.watch[game.id]?'saved':''}" data-watch="${game.id}" aria-label="${prefs.watch[game.id]?'Aus Merkliste entfernen':'Merken'}: ${E(game.title)}" aria-pressed="${!!prefs.watch[game.id]}">${icon('bookmark')}</button>
      <button type="button" class="card-open" data-game="${game.id}" aria-label="${E(game.title)}: ${indexed?'Watchlist / Recherche':'Spielwege ansehen'}">${artPart}
       <div class="card-copy"><div class="card-meta">${E(game.original)}${indexed?' · nicht geprüft':' · '+E(game.genre)}</div><h3>${E(game.title)}</h3><div class="route-tags">${indexed?tag('Noch keine geprüften Wege','amber'):kinds.slice(0,2).map(k=>tag(k)).join('')}</div></div></button>
      <div class="card-bottom"><span>${indexed?'Spieleindex / Watchlist':routes.length+' von '+game.routes.length+' Spielwegen'}</span><button type="button" data-game="${game.id}"><strong>${indexed?'Ansehen':'Varianten'} ${icon('arrow')}</strong></button></div></article>`;
  }
  function discover() {
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
      ${cheapNotice}<section class="game-grid" aria-label="Spielergebnisse">${results.length?results.slice(0,visibleLimit).map(x=>gameCard(x.game,x.routes)).join(''):`<div class="empty">${icon('search')}<h3>Keine passende, geprüfte Variante gefunden.</h3><p>Das ist kein Beweis, dass das Spiel nicht existiert. Für Akku- und FPS-Filter fehlen noch systematisch erhobene Messwerte.</p><button class="secondary" type="button" data-reset>Filter zurücksetzen</button>${filters.q.trim().length>1&&!catalog.games.some(g=>C.normalize(g.title)===C.normalize(filters.q.trim()))?`<button class="primary" type="button" data-add-custom>„${E(filters.q.trim().slice(0,70))}“ für die Merkliste erfassen</button>`:''}</div>`}</section>
      ${results.length>visibleLimit?`<div class="load-more"><button class="secondary" type="button" data-more>Mehr Spiele anzeigen (${results.length-visibleLimit} weitere)</button></div>`:''}
      <p class="footer-note">Stand ${date(catalog.reviewedAt)}. Ohne eigene ROMs, keine Downloads von Spieldaten. Externe Projektbilder werden mit Ursprungsquelle eingeblendet; offline stehen sie nicht zur Verfügung.</p>`;
  }
  function franchisesView() {
    const groups = [...new Set(catalog.games.map(g=>g.franchise))].sort();
    return `${mobileProfile()}<div class="page-title"><div class="eyebrow">VON DER SERIE ZUM SPIELWEG</div><h1>Deine Franchises.</h1><p>Originalplattformen, Neuinterpretationen und Community-Projekte gemeinsam entdecken.</p></div><div class="info-banner neutral">Dies ist ein erweiterter, noch nicht vollst\u00e4ndiger Franchise-Index. Nur Spielwege mit Quellen gelten als dokumentiert. Plattformprofil und Filter wirken erst beim \u00d6ffnen einer Franchise.</div><section class="franchise-grid">${groups.map(f=>{const gs=catalog.games.filter(g=>g.franchise===f);return `<button type="button" class="franchise-card" data-franchise="${E(f)}">${icon('library')}<h3>${E(f)}</h3><p>${gs.length} ${gs.length===1?'Spiel':'Spiele'} / ${gs.reduce((n,g)=>n+g.routes.length,0)} Spielwege</p><p style="margin-top:8px">${E([...new Set(gs.map(g=>g.original))].join(' \u00b7 '))}</p></button>`;}).join('')}</section>`;
  }
  function watchlistView() {
    const items=Object.entries(prefs.watch);
    const events=C.eventsForWatchlist(updates.events,prefs.watch,catalog);
    const newForWatch=(projects.projects||[]).filter(p=>!p.curated&&p.gameIds.some(id=>prefs.watch[id])).slice(0,10);
    return `<div class="page-title"><div class="eyebrow">DEIN PERS\u00d6NLICHER RADAR</div><h1>Dranbleiben statt nachlesen.</h1><p>Merke Spiele, die du noch nicht besitzt, und w\u00e4hle, welche Funktionen dich interessieren.</p></div><div class="info-banner">Die Merkliste lebt nur in diesem Browser. Kein Konto, kein Push-Dienst und keine Hintergrund\u00fcberwachung. Neue Hinweise erscheinen beim \u00d6ffnen einer aktualisierten Katalogversion. Ein Release allein beweist keine neue Funktion.</div><div class="toolbar"><button class="secondary" data-export type="button">${icon('download')} Merkliste sichern</button><button class="secondary" data-import type="button">Sicherung importieren</button><button class="quiet" data-nav="updates" type="button">${events.length} passende \u00c4nderungen ${icon('arrow')}</button></div>${items.length?items.map(([id,w])=>{const g=games.get(id);return `<article class="watch-row"><div><button type="button" data-game="${id}" style="text-align:left;padding:0"><h3>${E(g.title)}</h3></button><span class="tag">Seit ${date(w.addedAt)}</span></div><div><div class="interest-label">Dar\u00fcber m\u00f6chte ich auf dem Laufenden bleiben:</div><div class="interest-group">${[['updates','Alle Projekt-Updates'],...Object.entries(catalog.features).filter(([key])=>['dual-screen','mods','widescreen','controller','fps60-tested'].includes(key))].map(([key,label])=>`<label class="interest"><input type="checkbox" data-interest="${key}" data-for="${id}" ${w.interests.includes(key)?'checked':''}>${E(label)}</label>`).join('')}</div></div><button class="remove-btn" type="button" data-watch="${id}" aria-label="${E(g.title)} aus Merkliste entfernen">${icon('close')}</button></article>`;}).join(''):`<div class="empty">${icon('bookmark')}<h3>Hier beginnt dein n\u00e4chstes Projekt.</h3><p>Das Lesezeichen auf einer Spielekarte merkt das Spiel. Die Merkliste setzt weder einen Besitznachweis noch eine Installation voraus.</p><button class="primary" type="button" data-nav="discover">Spiele entdecken</button></div>`}${newForWatch.length?`<h2 class="source-heading">Neue Projektfunde für deine Spiele</h2><div class="discovery-grid">${newForWatch.map(projectCard).join('')}</div>`:''}${!storageAvailable?'<p class="info-banner amber">Lokales Speichern ist eingeschr\u00e4nkt. Sichere deine Merkliste vor dem Schlie\u00dfen als JSON.</p>':''}`;
  }
  function eventRow(event) {
    const titles={release:'Neuer Projekt-Release',feature_added:'Redaktionell best\u00e4tigte Funktion',archived:'Repository archiviert',source_changed:'Entdeckungsquelle ge\u00e4ndert',repository_changed:'Projekt-Metadaten ge\u00e4ndert'};
    return `<article class="feed-row">${icon('pulse')}<div><small>${date(event.detectedAt)} / ${E(titles[event.type]||'Projekt\u00e4nderung')}</small><h3>${E(event.title || event.repo || 'Katalog\u00e4nderung')}</h3><p>${E(event.summary || 'Quellen\u00e4nderung. Kompatibilit\u00e4t und Funktionen m\u00fcssen separat gepr\u00fcft werden.')}</p>${event.url?link(event.url,'Originalquelle ansehen'):''}</div></article>`;
  }
  function projectCard(p) {
    const discovered = (p.documentation==='unclassified-lead')?'Neu gefunden / Spiel noch nicht zugeordnet':
      (p.documentation==='ai-source-lead')?'KI-Quellenhinweis – noch nicht verifiziert':'Originalprojekt gefunden – nicht getestet';
    const names = p.gameIds.map(id=>games.get(id)?.title || id).join(' · ');
    const picture = (p.media||[]).find(m=>C.safeURL(m.url));
    return `<article class="discovery-card">${picture?`<div class="discovery-media">${shotImage(picture)}<span>Bildkandidat · Rechte nicht geklärt</span></div>`:''}<div class="discovery-body">${tag(discovered,'amber')}<h3>${E(p.name)}</h3>${names?`<p class="discovery-game">${E(names)}</p>`:''}${p.evidence?.length?`<p>${E(p.evidence[0].excerpt)}</p>`:'<p>Automatisch gefundenes Repository. Spielzuordnung und Funktionen noch nicht belegt.</p>'}<div class="route-actions">${link(p.url,'Projekt ansehen','secondary')}${p.evidence?.[0]?.sourceUrl?link(p.evidence[0].sourceUrl,'Beleg ansehen'):''}</div></div></article>`;
  }
  function updatesView() {
    const matched=C.eventsForWatchlist(updates.events,prefs.watch,catalog);
    const fresh = (projects.projects || []).filter(p=>!p.curated);
    return `<div class="page-title"><div class="eyebrow">NEUE VERSION IST NICHT GLEICH BESSERE VERSION</div><h1>Was hat sich ge\u00e4ndert?</h1><p>Projekt-Releases und best\u00e4tigte Funktions\u00e4nderungen bleiben bewusst getrennt.</p></div><div class="info-banner neutral">Letzter vollst\u00e4ndiger Quellenabgleich: <strong>${date(updates.lastSuccessAt)}</strong>. Letzter Versuch: ${date(updates.lastAttemptAt)}. ${location.protocol==='file:'?'Diese heruntergeladene HTML-Kopie aktualisiert sich nicht von selbst. Nach einem Quellenlauf die neue Handheld-Atlas.html von GitHub herunterladen.':'Diese gehostete App kann neue Projekt- und Release-Daten von ihrem Server laden.'} Projekt-Datenstand: ${date(projects.generatedAt)}.</div><div class="toolbar"><button class="secondary" type="button" data-refresh>${icon('pulse')} Ver\u00f6ffentlichte Release-Daten laden</button><button class="quiet" type="button" data-nav="sources">Aktualisierung verstehen ${icon('arrow')}</button></div>${fresh.length?`<h2 class="source-heading">Neue Projektfunde (${fresh.length})</h2><div class="discovery-grid">${fresh.slice(0,24).map(projectCard).join('')}</div><p class="footer-note">Automatisch gefunden: Projekt- und Bildhinweise sind keine bestätigten Installations- oder Leistungstests. Versionen und Bildrechte beim Original prüfen.</p>`:`<div class="info-banner neutral">Noch keine LIVE-Projektfunde. Beispiel- und Fixture-Daten werden absichtlich nicht als aktuelle Entdeckungen ausgegeben. Starte den Quellenworkflow auf GitHub.</div>`}${matched.length?`<h2 class="source-heading">F\u00fcr deine Merkliste</h2>${matched.map(eventRow).join('')}`:''}<h2 class="source-heading">Katalog-Feed</h2>${updates.events.length?updates.events.slice(0,80).map(eventRow).join(''):`<div class="empty">${icon('pulse')}<h3>Noch keine \u00c4nderungsereignisse.</h3><p>Der erste Quellenabgleich legt einen Ausgangsstand an. Bestehende Releases werden nicht als neue Entdeckungen ausgegeben. Erst sp\u00e4tere \u00c4nderungen erscheinen hier.</p></div>`}${updates.errors.length?`<h2 class="source-heading">Nicht erreichbare Quellen</h2><div class="info-banner amber">${updates.errors.map(e=>E(e.repo||e.source||'Quelle')+': '+E(e.message)).join('<br>')}<br>Bestehende Daten bleiben erhalten; fehlgeschlagene Abrufe sind kein Beleg f\u00fcr ein eingestelltes Projekt.</div>`:''}`;
  }
  function sourceCard(s) {
    const project = s.repo ? updates.projects[s.repo] : null;
    const role={primary:'Originalprojekt / Prim\u00e4rquelle',discovery:'Entdeckungsquelle',planned:'Anbindung vorgesehen'}[s.role];
    return `<article class="source-card">${tag(role,s.role==='primary'?'green':'')}<h3>${E(s.name)}</h3><p>${E(s.note)}</p>${s.repo?`<p class="mono">${E(s.repo)}</p>`:''}<p>Inhalt gepr\u00fcft: ${date(s.checkedAt)}${project?`<br>Metadaten: ${date(project.checkedAt)}${project.latestRelease?` / ${E(project.latestRelease.tag)}`:''}${project.archived?' / archiviert':''}`:''}</p>${link(s.url,'Quelle \u00f6ffnen')}</article>`;
  }
  function sourcesView() {
    const researchStatus = `<section class="research-overview"><h2>Recherche-Radar (0.4)</h2><p>Automatisierte GitHub-/Modrinth-Suche und optional CurseForge-API; Versionshinweise werden nur als Kandidaten gesammelt.</p><div class="research-metrics"><span>${quality.catalogGames} kuratierte Spiele</span><span>${quality.watchlistOnlyGames} Indexeinträge</span><span>${quality.routesWithoutPictures} Spielwege ohne Screenshots</span><span>${quality.pendingResearchCandidates} Treffer in Prüfung</span></div><p class="footer-note">${research.lastMode==='fixture'?'Aktueller Trefferbestand ist ein Offline-Demolauf, keine Live-API-Recherche.':'Kandidaten entsprechen nicht geprüften Spielwegen.'} Vollständigkeit nicht bestätigt. Quellenfunde erscheinen automatisch, tatsächliche Kompatibilität erst mit echten Testbelegen.</p></section>`;
    return `<div class="page-title"><div class="eyebrow">NACHVOLLZIEHBAR STATT MAGISCH</div><h1>Ein Katalog. Viele Quellen.</h1><p>Spiele werden redaktionell mit Varianten verkn\u00fcpft. Jede Aussage hat eine Herkunft; eine neue Versionsnummer ist noch kein neuer Kompatibilit\u00e4tstest.</p></div>${researchStatus}<div class="pipeline"><div><b>01 / ENTDECKEN</b><h3>Projektlinks sammeln</h3><p>GitHub-Listen liefern Kandidaten. Websites ohne freigegebene Schnittstelle bleiben zun\u00e4chst Linkquellen.</p></div><div><b>02 / NORMALISIEREN</b><h3>Doppelte Eintr\u00e4ge verbinden</h3><p>Spiel, Edition, Architektur, Runtime und Mod werden getrennt modelliert.</p></div><div><b>03 / PR\u00dcFEN</b><h3>Quellenstatus</h3><p>Neue Funde können automatisch sichtbar werden; als spielbar oder empfohlen gelten sie erst mit nachgewiesenen Tests.</p></div><div><b>04 / VER\u00d6FFENTLICHEN</b><h3>Versionierter Katalog</h3><p>Quellenfilter, JSON-Validierung, Tests und PWA-Build. Kein Token im Browser.</p></div></div><div class="info-banner amber">Die Browser-App installiert keine APKs und greift nicht auf dein Ger\u00e4t zu. Setup-Checklisten sind Anleitungen, keine ausgef\u00fchrten Installationsrezepte. Eigene Tests auf Thor-Hardware stehen aus.</div><div class="toolbar"><button class="secondary" type="button" data-catalog-export>${icon('download')} Katalog als JSON</button><button class="secondary" type="button" data-candidate-export>Kandidaten exportieren (${candidates.candidates.length})</button><button class="secondary" type="button" data-install>Als App nutzen</button></div><h2 class="source-heading">Entdecken und Erweitern</h2><div class="source-grid">${catalog.sources.filter(s=>s.role==='discovery').map(sourceCard).join('')}</div><h2 class="source-heading">Vorgesehene Anbindungen \u2014 noch kein Datenimport</h2><div class="source-grid">${catalog.sources.filter(s=>s.role==='planned').map(sourceCard).join('')}</div><h2 class="source-heading">Originalprojekte und Dokumentation</h2><div class="source-grid">${catalog.sources.filter(s=>s.role==='primary').map(sourceCard).join('')}</div><h2 class="source-heading">Rechte, Bilder und Aktualit\u00e4t</h2><div class="info-banner neutral">Die Spielkarten zeigen dort Original-Screenshots, wo sie einer konkreten Variante über das Quellen-README zugeordnet wurden. Andere Karten zeigen weiterhin abstrakte Illustrationen. Projektbilder werden extern eingebettet, nicht in diesem Paket gespiegelt; Bild- und Spielgrafikrechte sind separat zu klären. Ein \u00f6ffentliches Repository gibt nicht automatisch Rechte an s\u00e4mtlichen Bildern, Texten oder Spieldaten frei. Die Native-Ports-Liste weist CC0 aus; Fremdprojekte behalten ihre eigenen Bedingungen.</div><p class="footer-note">Lokal gespeichert werden Plattformprofil, Merkliste und abgehakte Checklisten. Keine Analyse-Skripte, kein Tracking, keine Zugangsdaten und kein Upload von ROMs. API-Schl\u00fcssel geh\u00f6ren ausschlie\u00dflich in die serverseitige Aktualisierung.</p>`;
  }
  function render() {
    renderNav();
    $('#main').innerHTML=({discover,franchises:franchisesView,watchlist:watchlistView,updates:updatesView,sources:sourcesView}[view]||discover)();
  }
  function navigate(next) {if(!['discover','franchises','watchlist','updates','sources'].includes(next))return;view=next;$('#detail-dialog').close();if(location.hash!==`#${next}`)history.replaceState(null,'',`#${next}`);render();window.scrollTo({top:0,behavior:'instant'});}
  function watch(id) {
    if(!games.has(id))return;
    if(prefs.watch[id]){delete prefs.watch[id];toast('Aus der Merkliste entfernt.');}
    else {prefs.watch[id]={interests:['dual-screen','updates'],addedAt:new Date().toISOString()};toast('Gemerkt. Interessen kannst du in der Merkliste anpassen.');}
    persist();render();if(selected&&$('#detail-dialog').open)renderDetail();
  }
  function routeCard(r) {
    const fit=C.platformMatch(r,selectedProfile());
    const features=r.features.filter(f=>!['live-map','touch-inventory'].includes(f));
    return `<article class="route-card ${fit?'':'incompatible'}"><div class="route-head"><div>${tag(catalog.kinds[r.kind])} ${tag(statusLabel(r.status),r.status==='documented'?'green':'amber')}${!fit?' '+tag('Anderes Plattformprofil','amber'):''}<h3>${E(r.name)}</h3><p class="route-sub">${E(r.edition)} / ${E(r.runtime)}</p></div><label class="select-compare"><input type="checkbox" data-compare="${r.id}" ${comparing.has(r.id)?'checked':''}>Vergleichen</label></div>
      <div class="route-tags">${features.map(f=>tag(catalog.features[f],f==='dual-screen'?'green':'')).join('')||tag('Keine Zusatzfunktion belegt')}</div>
      <p class="route-benefit">${E(r.benefit)}</p>${routeScreens(r)}
      <p class="route-caveat">${E(r.caveat)}</p><details class="requirements"><summary>Voraussetzungen / ${E(effort(r.effort))}</summary><ul>${r.requires.map(t=>`<li>${E(t)}</li>`).join('')}</ul></details>
      <div class="route-actions"><button type="button" class="primary" data-setup="${r.id}">Setup ansehen ${icon('arrow')}</button>${link(sources.get(r.sources[0])?.url||'','Originalprojekt','secondary')}${r.stores.map(st=>link(st.url,E(st.name),'secondary')).join('')}</div>
      <p class="route-source">Quellen: ${r.sources.map(id=>link(sources.get(id)?.url||'',E(sources.get(id)?.name||id))).join(' / ')}<br>Redaktion: ${date(r.reviewedAt)} / Keine eigenen Gerätemessungen.${r.requiredVersion?`<br>Versionsbindung: ${E(r.requiredVersion)}`:''}</p></article>`;
  }
  function researchForGame(game) {
    const audit = auditByGame.get(game.id);
    const leads = (research.candidates || []).filter(x=>x.gameId===game.id);
    const fixture = research.lastMode === 'fixture';
    const banner = `<div class="info-banner ${fixture?'amber':'neutral'}">${fixture?'Die angezeigten Recherchetreffer stammen aus einem Offline-Demolauf und wurden nicht live von den APIs abgerufen.':'Recherchequellen liefern Kandidaten, keine garantierten Kompatibilitätsdaten.'} Die Vollständigkeit aller Varianten ist unbekannt.</div>`;
    const stats = audit ? `<div class="research-metrics"><span>${audit.cataloguedRoutes} dokumentierte Spielwege</span><span>${audit.dualScreenRoutes} mit Dual-Screen</span><span>${audit.routesWithPictures} mit Screenshots</span><span>${audit.missingPicturesRouteIds.length} ohne Bilder</span></div>` : '<p>Für dieses Spiel liegt noch keine Katalogprüfung vor.</p>';
    const projectLeads=(projects.projects||[]).filter(p=>!p.curated&&p.gameIds.includes(game.id));
    const cards=leads.slice(0,24).map(item=>`<article class="research-lead">${tag('In Prüfung','amber')} ${tag(item.provider)}<h3>${E(item.project)}</h3><p>${E(item.label||'Keine Beschreibung')}</p>${item.versionsMentioned?.length?`<p><strong>Versionshinweise:</strong> ${E(item.versionsMentioned.slice(0,14).join(' / '))}</p>`:''}${item.loadersMentioned?.length?`<p><strong>Loader:</strong> ${E(item.loadersMentioned.join(', '))}</p>`:''}${item.evidence?.length?`<p><strong>Auszug (noch zu prüfen):</strong> ${E(item.evidence[0].excerpt)}</p>`:''}<div class="route-actions">${link(item.url,'Originalquelle','secondary')}</div></article>`).join('');
    return `${banner}${stats}${projectLeads.length?`<h3 class="source-heading">Automatisch veröffentlichte Quellenfunde (${projectLeads.length})</h3><div class="discovery-grid">${projectLeads.map(projectCard).join('')}</div>`:''}<h3 class="source-heading">Ungeprüfte Recherchewarteschlange (${leads.length})</h3>${leads.length?`<div class="research-leads">${cards}</div>`:`<div class="media-unavailable">Noch keine überprüften neuen Recherchetreffer. Das bedeutet nicht, dass es keine weiteren Varianten gibt.</div>`}<p class="footer-note">Quellen- und Versionsangaben müssen beim jeweiligen Originalprojekt gegen die genaue Edition und Mod-Datei überprüft werden. Katalog und Recherchewarteschlange sind technisch getrennt.</p>`;
  }
  function unreviewedScreens(game) {
    const documented=new Set(game.routes.flatMap(r=>(r.media||[]).map(m=>m.url)));
    const extras=(projects.projects||[]).filter(p=>p.gameIds.includes(game.id))
      .flatMap(p=>(p.media||[]).map(m=>({...m,project:p.name})))
      .filter(m=>C.safeURL(m.url)&&!documented.has(m.url)).slice(0,12);
    if(!extras.length)return '';
    return `<section class="gallery-section"><h3>Neue Bildkandidaten aus Originalprojekten</h3><p class="footer-note">Automatisch zugeordnete Projektbilder. Bildinhalt, Version und Nutzungsrechte sind noch nicht unabhängig verifiziert. Das sind keine bestätigten Mod-Screenshots.</p><div class="route-screen-grid">${extras.map(m=>`<figure class="route-shot"><a href="${E(C.safeURL(m.url))}" target="_blank" rel="noopener noreferrer"><span class="image-placeholder">Quellbild ansehen</span>${shotImage(m)}</a><figcaption>${E(m.project)} · ${E(m.vision==='plausible'?'KI-Bildprüfung: plausibel':'nicht verifiziert')} ${link(m.sourceUrl,'Bildquelle')}</figcaption></figure>`).join('')}</div></section>`;
  }
  function comparison() {
    const rs=selected.routes.filter(r=>comparing.has(r.id));
    if(rs.length<2)return '<div class="empty"><h3>Mindestens zwei Spielwege ausw\u00e4hlen.</h3><p>Im Reiter Spielwege die Vergleichsfelder aktivieren.</p><button type="button" class="secondary" data-tab="routes">Zu den Spielwegen</button></div>';
    const rows=[['Edition',r=>E(r.edition)],['Technischer Weg',r=>E(catalog.kinds[r.kind])],['Runtime',r=>E(r.runtime)],['Plattform',r=>r.targets.map(platformName).map(E).join('<br>')],['Zweiter Bildschirm',r=>E(r.dual||'Nicht belegt')],['Zusatzfunktionen',r=>r.features.map(f=>tag(catalog.features[f])).join(' ')||'Nicht belegt'],['Vorteil',r=>E(r.benefit)],['Einschr\u00e4nkung',r=>E(r.caveat)],['Ben\u00f6tigte Version',r=>E(r.requiredVersion||'Im Originalprojekt pr\u00fcfen')],['Voraussetzungen',r=>r.requires.map(E).join('<br>')],['Nachweis',r=>E(statusLabel(r.status))],['Gemessene Leistung',()=>'<strong>Nicht getestet.</strong> Keine vergleichbaren FPS-Daten.'],['Setup',r=>`<button class="secondary" data-setup="${r.id}" type="button">Checkliste</button>`]];
    return `<div class="info-banner neutral">Keine automatische Rangfolge: ohne vergleichbare Ger\u00e4tetests gibt es keinen belegten Performance-Sieger.</div><div class="table-wrap"><table class="compare-table"><thead><tr><th scope="col">Eigenschaft</th>${rs.map(r=>`<th scope="col">${E(r.name)}</th>`).join('')}</tr></thead><tbody>${rows.map(([label,fn])=>`<tr><th scope="row">${E(label)}</th>${rs.map(r=>`<td>${fn(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function renderDetail() {
    if(!selected)return;
    let content='';
    if(tab==='routes')content=(selected.routes.length?selected.routes.map(routeCard).join(''):`<div class="empty"><h3>Dieses Spiel kannst du schon beobachten.</h3><p>Es ist im Spieleindex oder als eigener Suchlisten-Eintrag erfasst. Noch kein einzeln geprüfter, gerätespezifischer Spielweg liegt in Atlas vor. Das bedeutet NICHT, dass keine Emulation oder Mod existiert.</p><div class="toolbar"><button class="primary" data-watch="${selected.id}" type="button">${icon('bookmark')} ${prefs.watch[selected.id]?'Aus Merkliste entfernen':'Für Dual-Screen-Mods merken'}</button><button class="secondary" data-research="${selected.id}" type="button">GitHub-Projekte suchen ${icon('external')}</button></div></div>`) + (selected.routes.length?`<div class="compare-bar"><span>${comparing.size} von maximal 3 Spielwegen ausgew\u00e4hlt</span><button type="button" class="primary" data-tab="compare" ${comparing.size<2?'disabled':''}>Vergleich \u00f6ffnen ${icon('arrow')}</button></div>`:'');
    if(tab==='compare')content=comparison();
    if(tab==='research')content=researchForGame(selected);
    if(tab==='media')content=selected.routes.length?selected.routes.map(r=>`<section class="gallery-section"><h3>${E(r.name)}</h3><p class="route-sub">${E(r.edition)} · ${E(r.runtime)}</p>${routeScreens(r,15)}</section>`).join(''):'<p class="info-banner neutral">Für dieses Spiel liegen noch keine zugeordneten Projektbilder vor.</p>';
    if(tab==='media') content += unreviewedScreens(selected);
    $('#detail-content').innerHTML=`<div class="dialog-head"><div class="eyebrow">SPIEL / EDITION / SPIELWEG</div><button type="button" class="close" data-close="detail" aria-label="Spieldetails schlie\u00dfen">${icon('close')}</button></div><div class="detail-hero">${art(selected)}<div><div class="card-meta">${E(selected.franchise)} / ${E(selected.original)}</div><h2 id="detail-title">${E(selected.title)}</h2><p>${E(selected.blurb)}</p><div class="route-actions"><button type="button" class="secondary" data-watch="${selected.id}">${icon('bookmark')}${prefs.watch[selected.id]?'Gemerkt':'Spiel merken'}</button><button type="button" class="quiet" data-share="${selected.id}">Link kopieren</button></div></div></div><div class="detail-body"><div class="detail-tabs" role="tablist" aria-label="Spielansichten">${[['routes',`Spielwege (${selected.routes.length})`],['compare','Direktvergleich'],['media','Galerie je Variante'],['research','Recherche-Stand']].map(([id,label])=>`<button class="detail-tab ${tab===id?'active':''}" type="button" role="tab" aria-selected="${tab===id}" data-tab="${id}">${label}</button>`).join('')}</div>${content}</div>`;
  }
  function openGame(id) {const g=games.get(id);if(!g)return;lastFocus=document.activeElement;selected=g;tab='routes';comparing=new Set();renderDetail();if(!$('#detail-dialog').open)$('#detail-dialog').showModal();$('#detail-dialog').scrollTop=0;}
  function info(title,body) {$('#info-content').innerHTML=`<div class="dialog-head"><h2 id="info-title" style="font-size:19px">${E(title)}</h2><button class="close" type="button" data-close="info" aria-label="Dialog schlie\u00dfen">${icon('close')}</button></div><div class="info-body">${body}</div>`;if(!$('#info-dialog').open)$('#info-dialog').showModal();}
  function getRoute(id) {for(const g of catalog.games){const r=g.routes.find(r=>r.id===id);if(r)return {g,r};}return null;}
  function setup(id) {
    const found=getRoute(id);if(!found)return;const {g,r}=found;
    const steps=['Lizenz und eigene Spieldateien pr\u00fcfen. Keine ROMs aus dem Katalog beziehen.','Vorhandene Spielst\u00e4nde und Einstellungen au\u00dferhalb dieser App sichern.',...r.steps];
    info(`${r.name}: Setup-Checkliste`,`<div class="info-banner amber">Gef\u00fchrte Vorbereitung, keine automatische Installation. Es wurden keine Dateien gepr\u00fcft, keine Backups erstellt und keine APKs installiert.</div><p>${E(g.title)} / ${E(r.edition)}</p><h3>Du ben\u00f6tigst</h3><p>${r.requires.map(E).join('<br>')}</p><div class="setup-list">${steps.map((s,i)=>`<label class="setup-item ${(prefs.checks[id]||[]).includes(i)?'done':''}"><input type="checkbox" data-step="${i}" data-route="${id}" ${(prefs.checks[id]||[]).includes(i)?'checked':''}><span>${E(s)}</span></label>`).join('')}</div><div class="toolbar">${link(sources.get(r.sources[0]).url,'Originalanleitung','primary')}<button class="secondary" type="button" data-recipe="${id}">${icon('download')} Plan als JSON</button></div><p class="footer-note">Abhaken ist eine eigene Notiz, kein erfolgreicher Systemtest. Diese Checkliste bleibt lokal in deinem Browser.</p>`);
  }
  function installInfo() {
    if(deferredInstall){deferredInstall.prompt();deferredInstall.userChoice.then(()=>{deferredInstall=null;});return;}
    info('Browser zuerst. App-Gef\u00fchl inklusive.','<p>Atlas ist als Progressive Web App vorbereitet. Auf einer HTTPS-Adresse oder localhost kannst du sie \u00fcber das Browser-Men\u00fc installieren bzw. zum Startbildschirm hinzuf\u00fcgen, sofern dein Browser das unterst\u00fctzt.</p><p>Eine lokal ge\u00f6ffnete HTML-Datei ist eine Vorschau: ohne Service Worker und ohne PWA-Installation. F\u00fcr Offline-Cache und Installation den beiliegenden Server oder HTTPS-Hosting verwenden.</p><p>Die PWA ersetzt keinen Emulator und steuert nicht das zweite Display anderer Apps. Native Android-Integrationen kommen erst in einer sp\u00e4teren Ausbaustufe.</p><div class="code">python scripts/serve.py\n\nhttp://localhost:8765</div>');
  }
  async function refresh() {
    if(!/^https?:$/.test(location.protocol)) {
      toast('HTML-Datei ist ein Offline-Schnappschuss. Aktualisierte Datei von GitHub herunterladen.');return;
    }
    try {
      const [ru,rp]=await Promise.all([
        fetch('data/updates.json',{cache:'no-store'}),
        fetch('data/projects.json',{cache:'no-store'})
      ]);
      if(!ru.ok||!rp.ok)throw new Error('Not reachable');
      const [next,nextProjects]=await Promise.all([ru.json(),rp.json()]);
      if(next.schemaVersion!==1||!Array.isArray(next.events)||!Array.isArray(next.errors)||!next.projects||
         nextProjects.schemaVersion!==1||!Array.isArray(nextProjects.projects))throw new Error('Invalid catalog update');
      const changed=JSON.stringify(nextProjects)!==JSON.stringify(projects);
      updates=next;projects=nextProjects;render();
      toast(changed?'Neue Projekt- und Release-Daten geladen.':'Bereits auf dem veröffentlichten Datenstand.');
    } catch(e) {
      toast('Veröffentlichte Daten nicht erreichbar; bisheriger Stand bleibt erhalten.');
    }
  }
  document.addEventListener('click',async event=>{
    const b=event.target.closest('button,a');if(!b)return;
    if(b.dataset.nav)navigate(b.dataset.nav);
    if(b.dataset.game)openGame(b.dataset.game);
    if(b.dataset.watch)watch(b.dataset.watch);
    if('feature' in b.dataset){filters.feature=b.dataset.feature;filters.effort='';visibleLimit=48;view='discover';render();$('#browse')?.scrollIntoView({block:'start',behavior:'instant'});}
    if(b.dataset.franchise){filters=defaults();filters.franchise=b.dataset.franchise;$('#search').value='';navigate('discover');$('#browse')?.scrollIntoView({block:'start'});}
    if('reset' in b.dataset){visibleLimit=48;filters=defaults();$('#search').value='';render();}
    if(b.dataset.close){$('#'+b.dataset.close+'-dialog').close();if(b.dataset.close==='detail'&&lastFocus?.isConnected)lastFocus.focus();}
    if(b.dataset.tab){tab=b.dataset.tab;renderDetail();$('#detail-dialog').scrollTop=0;}
    if(b.dataset.setup)setup(b.dataset.setup);
    if(b.dataset.recipe){const {g,r}=getRoute(b.dataset.recipe);download(`atlas-plan-${r.id}.json`,{schemaVersion:1,readOnly:true,automaticExecution:false,gameId:g.id,routeId:r.id,reviewedAt:r.reviewedAt,requirements:r.requires,steps:r.steps,sources:r.sources.map(id=>sources.get(id).url),warning:'Vorbereitung, keine getestete automatische Installation. Keine ROMs enthalten.'});}
    if('export' in b.dataset)download('atlas-merkliste.json',{...prefs,exportedAt:new Date().toISOString()});
    if('import' in b.dataset)$('#import-file').click();
    if('catalogExport' in b.dataset)download('atlas-katalog.json',catalog);
    if('candidateExport' in b.dataset)download('atlas-kandidaten.json',candidates);
    if('refresh' in b.dataset)refresh();
    if('more' in b.dataset){visibleLimit+=48;render();}
    if('addCustom' in b.dataset) {
      const title=filters.q.trim().slice(0,100);
      if(title.length<2)return;
      const id='custom-'+C.normalize(title).replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,60);
      if(id.length<=8)return;
      prefs.customGames ||= {};
      if(Object.keys(prefs.customGames).length>=200&&!prefs.customGames[id]){toast('Maximal 200 eigene Spieltitel möglich.');return;}
      prefs.customGames[id]={title,platform:filters.original||'Plattform unbekannt'};
      restoreCustomGames();
      prefs.watch[id]={interests:['dual-screen','updates'],addedAt:new Date().toISOString()};
      persist();filters=defaults();filters.q=title;$('#search').value=title;
      render();toast('Eigener Titel gespeichert – noch ohne geprüfte Varianten oder automatische Benachrichtigung.');
    }
    if('easy' in b.dataset){filters.effort=filters.effort==='easy'?'':'easy';filters.feature='';visibleLimit=48;render();}
    if('infoBattery' in b.dataset)info('Akkufilter ist noch nicht belastbar','<p>Ein einfach zu emulierendes Retrospiel kann weniger Leistung benötigen, aber Laufzeit hängt von Bildschirmhelligkeit, Emulator, Displayanzahl, Leistungsprofil und Spiel ab. Atlas behauptet ohne standardisierte Messungen keine verifizierten Batteriewerte. Als Zwischenlösung kannst du nach ursprünglicher Konsole oder einfachem Setup filtern.</p>');
    if(b.dataset.research){const g=games.get(b.dataset.research);if(g){const q=encodeURIComponent('"'+g.title+'" dual screen android handheld');const url='https://github.com/search?q='+q+'&type=repositories';window.open(url,'_blank','noopener,noreferrer');}}

    if('install' in b.dataset||b.id==='install')installInfo();
    if(b.dataset.share){const u=new URL(location.href);u.hash='game/'+b.dataset.share;try{await navigator.clipboard.writeText(u.href);toast('Link kopiert. Lokale Dateipfade funktionieren nur auf diesem Computer.');}catch(_){info('Spiel-Link',`<p>Zum Kopieren:</p><div class="code">${E(u.href)}</div>`);}}
  });
  document.addEventListener('change',event=>{
    const el=event.target;
    if(el.id==='device'||'profile' in el.dataset){prefs.profile=el.value;filters.profile=el.value;persist();render();if($('#detail-dialog').open)renderDetail();}
    if(el.dataset.filter){filters[el.dataset.filter]=el.type==='checkbox'?el.checked:el.value;visibleLimit=48;render();}
    if(el.dataset.compare){if(el.checked){if(comparing.size>=3){el.checked=false;toast('Bis zu drei Varianten gleichzeitig vergleichen.');return;}comparing.add(el.dataset.compare);}else comparing.delete(el.dataset.compare);const bar=$('.compare-bar');if(bar){bar.querySelector('span').textContent=`${comparing.size} von maximal 3 Spielwegen ausgew\u00e4hlt`;bar.querySelector('button').disabled=comparing.size<2;}}
    if(el.dataset.interest){const w=prefs.watch[el.dataset.for];if(w){const set=new Set(w.interests);el.checked?set.add(el.dataset.interest):set.delete(el.dataset.interest);w.interests=[...set];persist();}}
    if(el.dataset.step!==undefined){const id=el.dataset.route;const set=new Set(prefs.checks[id]||[]);el.checked?set.add(Number(el.dataset.step)):set.delete(Number(el.dataset.step));prefs.checks[id]=[...set];el.closest('.setup-item').classList.toggle('done',el.checked);persist();}
  });
  $('#import-file').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>1000000)throw new Error('Datei gr\u00f6\u00dfer als 1 MB.');const clean=C.sanitizePreferences(JSON.parse(await file.text()),catalog);prefs.customGames={...prefs.customGames,...clean.customGames};restoreCustomGames();prefs.watch={...prefs.watch,...clean.watch};prefs.checks={...prefs.checks,...clean.checks};prefs.profile=clean.profile;filters.profile=clean.profile;persist();render();toast('Sicherung eingelesen. Nur bekannte Spiele und Funktionen wurden \u00fcbernommen.');}catch(err){toast('Import abgelehnt: '+err.message);}finally{e.target.value='';}});
  $('#search').addEventListener('input',e=>{filters.q=e.target.value;if(view!=='discover')view='discover';render();});
  $('#search-icon').innerHTML=icon('search');$('#bookmark-icon').innerHTML=icon('bookmark');
  // Only expose a photograph when the original project really delivers the image.
  // Offline/unreachable links remain honest, readable placeholders.
  document.addEventListener('load', e => {if(e.target.matches?.('img.remote-photo'))e.target.classList.add('loaded');}, true);
  document.addEventListener('error', e => {if(e.target.matches?.('img.remote-photo'))e.target.classList.add('unavailable');}, true);
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)&&!$('dialog[open]')){e.preventDefault();$('#search').focus();}if(e.key==='Escape'&&!$('dialog[open]'))$('#search').blur();});
  for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',e=>{if(e.target===dialog){const rect=dialog.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)dialog.close();}});
  window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstall=e;$('#install').innerHTML='App installieren '+icon('download');});
  function applyHash(){const hash=decodeURIComponent(location.hash.slice(1));if(hash.startsWith('game/')){navigate('discover');openGame(hash.slice(5));}else if(['discover','franchises','watchlist','updates','sources'].includes(hash))navigate(hash);else render();}
  window.addEventListener('hashchange',applyHash);
  function moveFocus(dx,dy){const root=$('#info-dialog[open]')||$('#detail-dialog[open]')||document;const elements=[...root.querySelectorAll('button:not(:disabled),a[href],input,select,summary')].filter(el=>el.getClientRects().length&&!el.hidden);if(!elements.length)return;const current=document.activeElement;if(!elements.includes(current)){elements[0].focus();return;}const a=current.getBoundingClientRect(),ax=a.x+a.width/2,ay=a.y+a.height/2;let best=null,score=Infinity;for(const el of elements){if(el===current)continue;const b=el.getBoundingClientRect(),x=b.x+b.width/2-ax,y=b.y+b.height/2-ay;if(dx*x+dy*y<8)continue;const s=Math.hypot(x,y)+2.5*Math.abs(dx?y:x);if(s<score){score=s;best=el;}}if(best){best.focus();best.scrollIntoView({block:'nearest'});}}
  let padTime=0,padButtons=[];
  function gamepadFrame(time){try{const pad=Array.from(navigator.getGamepads?.()||[]).find(Boolean);if(pad){const pressed=pad.buttons.map(b=>b.pressed);if(time-padTime>170){const x=pressed[14]?-1:pressed[15]?1:Math.abs(pad.axes[0]||0)>.65?Math.sign(pad.axes[0]):0;const y=pressed[12]?-1:pressed[13]?1:Math.abs(pad.axes[1]||0)>.65?Math.sign(pad.axes[1]):0;if(x||y){moveFocus(x,y);padTime=time;}}if(pressed[0]&&!padButtons[0])document.activeElement?.click();if(pressed[1]&&!padButtons[1])($('#info-dialog[open]')||$('#detail-dialog[open]'))?.close();padButtons=pressed;}else padButtons=[];}catch(_){}requestAnimationFrame(gamepadFrame);}
  applyHash();requestAnimationFrame(gamepadFrame);
  if('serviceWorker' in navigator&&/^https?:$/.test(location.protocol))navigator.serviceWorker.register('sw.js').catch(()=>{});
})();
