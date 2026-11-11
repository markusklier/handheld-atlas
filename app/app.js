/* Handheld Atlas – game-first discovery for Android handhelds.
   Loads data.json (built from data/ by scripts/atlas.py). No framework, no build step. */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const norm = (s) => String(s ?? '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
const store = {
  get(k, d) { try { const v = localStorage.getItem('atlas.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('atlas.' + k, JSON.stringify(v)); } catch { /* private mode */ } },
};
/* Atlas-App (android/): die Seite läuft dort in einem WebView und bekommt „AtlasBridge“ (docs/SETUP.md).
   native.call('info') → Promise; native.on('measure', fn) für Ereignisse. Im Browser ist native.available false. */
const native = (() => {
  const bridge = window.AtlasBridge;
  const waiting = new Map();
  const listeners = new Map();
  let seq = 0;
  if (bridge) {
    bridge.onmessage = (e) => {
      let m; try { m = JSON.parse(e.data); } catch { return; }
      if (m.event) { for (const fn of listeners.get(m.event) || []) { try { fn(m.data); } catch (err) { console.error(err); } } return; }
      const w = waiting.get(m.id);
      if (!w) return;
      waiting.delete(m.id); clearTimeout(w.timer);
      m.ok ? w.resolve(m.result) : w.reject(new Error(m.error || 'Fehler in der App'));
    };
  }
  return {
    available: !!bridge,
    screen: new URLSearchParams(location.search).get('screen') === 'companion' ? 'companion' : 'main',
    call(method, params = {}, timeout = 30000) {
      if (!bridge) return Promise.reject(new Error('Nur in der Atlas-App möglich'));
      return new Promise((resolve, reject) => {
        const id = String(++seq);
        const timer = setTimeout(() => { waiting.delete(id); reject(new Error('Die App antwortet nicht')); }, timeout);
        waiting.set(id, { resolve, reject, timer });
        bridge.postMessage(JSON.stringify({ id, method, params }));
      });
    },
    on(event, fn) { if (!listeners.has(event)) listeners.set(event, []); listeners.get(event).push(fn); },
  };
})();

const fmtDate = (d) => {
  if (!d) return '';
  const dt = new Date(d.length === 10 ? d + 'T12:00:00Z' : d);
  return isNaN(dt) ? d : dt.toLocaleDateString('de-DE', { day: 'numeric', month: 'short', year: 'numeric' });
};

const DB = { games: [], byId: new Map(), projects: {}, platforms: {}, meta: {}, changelog: [], franchises: [], reddit: [], setup: { devices: [], apps: [], policy: {}, runs: {}, learned: {} } };
const state = {
  q: '', chips: new Set(), platform: '', sort: 'relevance', limit: 48,
  device: store.get('device', 'thor'),
  favs: new Set(store.get('favs', [])),
  version: null,
};
const PAGE = 48;
const NATIVE_KINDS = new Set(['native', 'native-mod', 'decomp', 'recomp', 'source-port']);
const EMU_KINDS = new Set(['emulation', 'emulator-mod']);
const FILTERS = [
  { id: 'dual', label: 'Dual Screen', icon: 'dual', test: (g) => g._dual },
  { id: 'routes', label: 'Mit Spielwegen', icon: 'play', test: (g) => g.routes.length > 0 },
  { id: 'android', label: 'Android offiziell', icon: 'check', test: (g) => (g.versions || []).some((v) => v.platforms.includes('Android')) },
  { id: 'native', label: 'Native Ports', icon: 'chip', test: (g) => g.routes.some((r) => NATIVE_KINDS.has(r.kind)) || (g.versions || []).some((v) => v.platforms.includes('Android')) },
  { id: 'emu', label: 'Emulation', icon: 'gamepad', test: (g) => g.routes.some((r) => EMU_KINDS.has(r.kind)) || g._platformOptions > 0 },
  { id: 'mods', label: 'Mods', icon: 'wrench', test: (g) => g.mods.length > 0 || g.routes.some((r) => r.features?.includes('mods')) },
  { id: 'tested', label: 'Thor-getestet', icon: 'check', test: (g) => g.routes.some((r) => r.verification === 'thor-tested') },
  { id: 'ai', label: 'KI-Funde', icon: 'ai', test: (g) => g._ai },
];
const F = (id) => FILTERS.find((f) => f.id === id).test;
const TABS = [
  { id: 'discover', href: '#/', label: 'Entdecken', icon: 'compass' },
  { id: 'dual', href: '#/dual', label: 'Dual Screen', icon: 'dual' },
  { id: 'franchises', href: '#/franchises', label: 'Franchises', icon: 'layers' },
  { id: 'projects', href: '#/projekte', label: 'Projekte', icon: 'box' },
  { id: 'news', href: '#/neu', label: 'Neu', icon: 'spark' },
  { id: 'favs', href: '#/merkliste', label: 'Merkliste', icon: 'bookmark' },
  { id: 'info', href: '#/info', label: 'Info', icon: 'info' },
];

/* ---------------- data ---------------- */
async function loadData() {
  if (window.ATLAS_EMBEDDED) return window.ATLAS_EMBEDDED;
  const res = await fetch('data.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error('data.json ' + res.status);
  return res.json();
}

function index(data) {
  DB.meta = data.meta;
  DB.projects = data.projects || {};
  DB.platforms = data.platforms || {};
  DB.changelog = data.changelog || [];
  DB.builtAt = data.builtAt;
  DB.inboxCount = data.inboxCount || 0;
  DB.agent = data.agent || {};
  DB.researched = data.researched || {};
  DB.queue = data.queue || [];
  DB.dualScan = data.dualScan || {};
  DB.franchiseScan = data.franchiseScan || {};
  DB.imageRequests = data.imageRequests || {};
  DB.usage = data.usage || {};
  DB.reddit = data.reddit || [];
  DB.researchMode = data.researchMode || {};
  DB.setup = data.setup || { devices: [], apps: [], policy: {}, runs: {}, learned: {} };
  DB.games = data.games.map((g) => {
    g.routes = g.routes || [];
    g.mods = g.mods || [];
    g.platforms = g.platforms || [];
    g.screenshots = g.screenshots || [];
    g._dual = g.routes.some((r) => r.features?.includes('dual-screen'));
    g._ai = g.routes.some((r) => r.verification === 'ai-unverified') || g.mods.some((m) => m.verification === 'ai-unverified');
    g._platformOptions = g.platforms.reduce((n, p) => n + (DB.platforms[p]?.length || 0), 0);
    g._search = norm([g.title, g.franchise, g.platforms.join(' '), g.genre,
      ...g.routes.flatMap((r) => [r.name, r.runtime, ...(r.projects || []).map((p) => DB.projects[p]?.name)]),
      ...g.mods.map((m) => m.name)].join(' '));
    g._score = g.routes.length * 10 + (g._dual ? 25 : 0) + g.mods.length * 3 + (g.cover ? 2 : 0);
    const ty = /\((\d{4})\)/.exec(g.title);
    const ys = (g.versions || []).filter((v) => v.year && v.type === 'original').map((v) => v.year);
    g._year = ty ? +ty[1] : ys.length ? Math.min(...ys) : null;
    return g;
  });
  DB.byId = new Map(DB.games.map((g) => [g.id, g]));
  const fr = new Map();
  for (const g of DB.games) {
    if (!fr.has(g.franchise)) fr.set(g.franchise, []);
    fr.get(g.franchise).push(g);
  }
  DB.franchises = [...fr.entries()].map(([name, games]) => ({
    name, games: games.sort((a, b) => b._score - a._score || a.title.localeCompare(b.title)),
    routes: games.reduce((n, g) => n + g.routes.length, 0), dual: games.some((g) => g._dual),
  })).sort((a, b) => (b.routes > 0) - (a.routes > 0) || b.games.length - a.games.length || a.name.localeCompare(b.name));
  redditMerge();
  DB.allPlatforms = [...new Set(DB.games.flatMap((g) => g.platforms))].sort((a, b) => a.localeCompare(b, 'de'));
}

const device = () => DB.meta.devices?.find((d) => d.id === state.device) || DB.meta.devices?.[0] || {};
const routeFits = (r) => !device().target || (r.targets || []).includes(device().target);
const label = (group, key) => DB.meta[group]?.[key] || key;

/* ---------------- building blocks ---------------- */
const hue = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };

function coverHTML(g, { badges = true } = {}) {
  const h = hue(g.franchise || g.title);
  const ph = `<div class="ph" style="background:linear-gradient(160deg,hsl(${h} 35% 22%),hsl(${(h + 40) % 360} 30% 11%));color:hsl(${h} 70% 88%)">${esc(g.title)}<small>${esc(g.platforms[0] || '')}</small></div>`;
  const portrait = g.cover?.url?.includes('steamstatic') ? ' portrait' : '';
  // no cover yet: show the first picture we have (original game, then a way) instead of an empty tile
  const src = g.cover?.url || g.screenshots.find((x) => x.caption !== 'Titelbild')?.url || g.screenshots[0]?.url
    || g.routes.flatMap((r) => r.screenshots || [])[0]?.url;
  // loaded → the title placeholder disappears and a blurred copy fills the free space around box art of any shape
  const img = src ? `<img src="${esc(src)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onload="this.parentNode.classList.add('ok');this.parentNode.style.setProperty('--img','url(&quot;'+this.src+'&quot;)')" onerror="this.remove()">` : '';
  let b = '';
  if (badges) {
    if (g._dual) b += `<span class="tag dual">${icon('dual')}Dual</span>`;
    if (g._ai) b += `<span class="tag ai">${icon('ai')}KI</span>`;
  }
  return `<div class="cover${portrait}">${ph}${img}${b ? `<div class="badges">${b}</div>` : ''}</div>`;
}

/* Slides for the card preview: original screenshots and screenshots of the ways to play.
   On a dual-screen device the dual-screen variants come first. */
function previewSlides(g) {
  const orig = g.screenshots.map((s) => ({ url: s.url, label: s.caption === 'Titelbild' ? 'Titelbild' : 'Original' }));
  const dual = [], other = [];
  for (const r of g.routes) {
    const isDual = r.features?.includes('dual-screen');
    for (const s of r.screenshots || []) (isDual ? dual : other).push({ url: s.url, label: `${isDual ? 'Dual Screen · ' : ''}${r.name}`, dual: isDual });
  }
  for (const m of g.mods) for (const s of m.screenshots || []) other.push({ url: s.url, label: `Mod · ${m.name}` });
  const ordered = device().dualScreen ? [...dual, ...orig, ...other] : [...orig, ...dual, ...other];
  const seen = new Set();
  return ordered.filter((s) => !seen.has(s.url) && seen.add(s.url)).slice(0, 12);
}

function cardHTML(g) {
  const ways = g.routes.length
    ? `<b>${g.routes.length} ${g.routes.length === 1 ? 'Spielweg' : 'Spielwege'}</b> · ${(g.versions || []).length > 1 ? `${g.versions.length} Fassungen` : esc(g.platforms[0] || '')}`
    : `${esc(g.platforms.join(', '))}${g._platformOptions ? ' · Emulation' : ''}`;
  const h = hue(g.franchise || g.title);
  const backdrop = g.screenshots.find((s) => s.caption !== 'Titelbild') || g.screenshots[0];
  const slides = previewSlides(g).length;
  let badges = '';
  if (g._dual) badges += `<span class="tag dual">${icon('dual')}Dual</span>`;
  if (g._ai) badges += `<span class="tag ai">${icon('ai')}KI</span>`;
  return `<a class="card" href="#/spiel/${esc(g.id)}" data-game="${esc(g.id)}">
    <div class="media" style="--h:${h}">
      <div class="ph"><span>${esc(g.title)}</span><small>${esc(g.platforms[0] || '')}</small></div>
      ${backdrop ? `<img class="bg" src="${esc(backdrop.url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      ${g.cover ? `<img class="box" src="${esc(g.cover.url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      <div class="slide" aria-hidden="true"></div>
      ${badges ? `<div class="badges">${badges}</div>` : ''}
      ${slides > 1 ? `<span class="nav prev" data-slide="-1" aria-hidden="true">${icon('back')}</span><span class="nav next" data-slide="1" aria-hidden="true">${icon('back')}</span>` : ''}
      ${slides ? `<span class="shots">${icon('compass')}${slides}</span>` : ''}
    </div>
    <div><div class="t">${esc(g.title)}</div><div class="s">${ways}</div>
      <i class="explored lvl-${completeness(g).level}" style="--v:${completeness(g).pct}%" title="Datenstand: ${LEVEL_LABEL[completeness(g).level]} (${completeness(g).pct} %)"></i></div></a>`;
}

/* ---- card slideshow (mouse hover, gamepad/keyboard focus, arrows) ---- */
const preview = { card: null, i: 0, timer: null, slides: [] };
function showSlide(i) {
  const { card, slides } = preview;
  if (!card || !slides.length) return;
  preview.i = (i + slides.length) % slides.length;
  const s = slides[preview.i];
  const layer = card.querySelector('.slide');
  const pixel = s.url.includes('libretro-thumbnails') ? ' pixel' : '';
  layer.innerHTML = `<img class="${pixel}" src="${esc(s.url)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">
    <span class="cap${s.dual ? ' dual' : ''}">${esc(s.label)}</span>
    <span class="dots">${slides.map((_, k) => `<i class="${k === preview.i ? 'on' : ''}"></i>`).join('')}</span>`;
  card.classList.add('previewing');
}
function startPreview(card) {
  if (preview.card === card) return;
  if (typeof dualOn === 'function' && dualOn()) return;   // two screens: the big preview runs on the stage
  stopPreview();
  const g = DB.byId.get(card.dataset.game);
  const slides = g ? previewSlides(g) : [];
  if (!slides.length) return;
  Object.assign(preview, { card, slides, i: 0 });
  preview.delay = setTimeout(() => {
    showSlide(0);
    preview.timer = setInterval(() => showSlide(preview.i + 1), 4000);
  }, 450); // don't flicker while the mouse just passes over
}
function stopPreview() {
  clearTimeout(preview.delay); clearInterval(preview.timer);
  if (preview.card) { preview.card.classList.remove('previewing'); preview.card.querySelector('.slide').innerHTML = ''; }
  preview.card = null;
}
function stepPreview(card, d) {
  if (preview.card !== card) { startPreview(card); clearTimeout(preview.delay); showSlide(d > 0 ? 0 : -1); }
  else showSlide(preview.i + d);
  clearInterval(preview.timer);
  preview.timer = setInterval(() => showSlide(preview.i + 1), 5000);
}
document.addEventListener('mouseover', (e) => { const c = e.target.closest?.('.card'); if (c) startPreview(c); });
document.addEventListener('mouseout', (e) => { const c = e.target.closest?.('.card'); if (c && !c.contains(e.relatedTarget)) stopPreview(); });
document.addEventListener('focusin', (e) => { const c = e.target.closest?.('.card'); if (c) startPreview(c); else stopPreview(); });

const gridHTML = (games) => games.length ? `<div class="grid">${games.map(cardHTML).join('')}</div>`
  : `<div class="empty">${state.q.trim().length > 2 ? `„${esc(state.q.trim())}“ ist noch nicht in Atlas – siehe unten.` : 'Nichts gefunden.'}</div>`;

/* ---------- online index: Wikipedia's game articles, queried live from this device ---------- */
const onlineCache = new Map();
const titleKey = (t) => norm(t).replace(/\(.*?\)/g, '').replace(/^the\s+/, '').replace(/[^a-z0-9]/g, '');
function onlineIndexSection(q) {
  if (q.length < 3) return '';
  return `<section class="section" id="online-index" data-q="${esc(q)}"><div class="section-head"><h2>${icon('search')} Noch nicht in Atlas</h2>
    <span class="faint">Treffer aus Wikipedia – mit einem Klick recherchieren lassen</span></div>
    <div class="list"><div class="empty">Suche läuft …</div></div></section>`;
}
async function wikiQuery(params) {
  const url = 'https://en.wikipedia.org/w/api.php?' + new URLSearchParams({ action: 'query', prop: 'pageimages|description', piprop: 'thumbnail',
    pithumbsize: '160', pilicense: 'any', format: 'json', formatversion: '2', origin: '*', ...params });
  const data = await (await fetch(url)).json();
  return (data.query?.pages || []).sort((a, b) => a.index - b.index);
}
const GAME_DESC = /video game|computer game|mobile game|game series|video game series|franchise|role-playing game|shooter|platform game|simulation game|strategy game|adventure game|racing game|fighting game/i;
/* Local game that a Wikipedia article is about: same title AND (if Wikipedia disambiguates by year) the same year.
   "Tomb Raider (2013 video game)" is not our Tomb Raider (1996). */
function localMatch(it) {
  const key = titleKey(it.title);
  let maybe = null;
  for (const g of DB.games) {
    if (titleKey(g.title) !== key) continue;
    if (!it.year || !g._year || Math.abs(g._year - it.year) <= 1) {
      if (!it.year || g._year) return { game: g, sure: true };
      maybe = maybe || g;   // our entry has no year yet – could be the same game
    }
  }
  return maybe ? { game: maybe, sure: false } : null;
}
async function fillOnlineIndex() {
  const sec = document.getElementById('online-index');
  if (!sec) return;
  const q = sec.dataset.q;
  let items = onlineCache.get(q);
  if (!items) {
    await new Promise((r) => setTimeout(r, 450));            // typing: only ask Wikipedia once the query settles
    if (!document.body.contains(sec) || sec.dataset.q !== q) return;
    try {
      const [prefix, search, plain] = await Promise.all([
        wikiQuery({ generator: 'prefixsearch', gpssearch: q, gpslimit: '15' }),
        wikiQuery({ generator: 'search', gsrsearch: `${q} video game`, gsrlimit: '20' }),
        wikiQuery({ generator: 'search', gsrsearch: q, gsrlimit: '10' })]);
      const seen = new Set();
      items = [...prefix, ...search, ...plain].filter((p) => GAME_DESC.test(p.description || '') && !seen.has(p.title) && seen.add(p.title))
        .map((p) => {
          const m = / \((?:(\d{4}) )?(?:video game|game|franchise|series|video game series)\)$/.exec(p.title);
          const dy = /\b(19[7-9]\d|20[0-4]\d)\b/.exec(p.description || '');
          return { title: m ? p.title.slice(0, m.index) : p.title, year: m?.[1] ? +m[1] : null, descYear: dy ? +dy[1] : null,
            desc: p.description, thumb: p.thumbnail?.source,
            series: /series|franchise/i.test(p.description || '') && !/^\d{4} /.test(p.description || ''),
            url: 'https://en.wikipedia.org/wiki/' + encodeURIComponent(p.title.replace(/ /g, '_')) };
        });
      onlineCache.set(q, items);
    } catch {
      items = null;
    }
  }
  if (!document.body.contains(sec)) return;
  const list = sec.querySelector('.list');
  if (!items) { list.innerHTML = '<div class="empty">Online-Index gerade nicht erreichbar.</div>'; return; }
  const issue = (title, body) => DB.meta.repo ? esc(issueUrl(title, body)) : '';
  let inAtlas = 0;
  const rows = items.map((it) => {
    if (it.series) {
      const fr = DB.franchises.find((f) => titleKey(f.name) === titleKey(it.title));
      if (fr) { inAtlas++; return ''; }       // shown above as series
      return `<div class="item online">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span class="mini"></span>'}
        <div class="grow"><div class="title">${esc(it.title)} <span class="tag">${icon('layers')}Reihe</span></div>
        <div class="desc">${esc(it.desc)} · <a class="link" href="${esc(it.url)}" target="_blank" rel="noopener">Wikipedia</a></div></div>
        <div class="row">${DB.meta.repo ? `<a class="btn primary" href="${issue('Reihe: ' + it.title, 'franchise: ' + it.title)}" target="_blank" rel="noopener">${icon('layers')}Ganze Reihe aufnehmen</a>` : ''}</div></div>`;
    }
    const year = it.year || it.descYear;
    const hit = localMatch({ title: it.title, year });
    if (hit?.sure) { inAtlas++; return ''; }
    // a same-named older game exists → the new entry keeps its year in the title ("Tomb Raider (2013)")
    const named = DB.games.some((g) => titleKey(g.title) === titleKey(it.title)) && year ? `${it.title} (${year})` : it.title;
    return `<div class="item online">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span class="mini"></span>'}
      <div class="grow"><div class="title">${esc(named)}</div>
      <div class="desc">${esc(it.desc)} · <a class="link" href="${esc(it.url)}" target="_blank" rel="noopener">Wikipedia</a>
        ${hit ? ` · vielleicht schon in Atlas als <a class="link" href="#/spiel/${esc(hit.game.id)}">${esc(hit.game.title)}</a>` : ''}</div></div>
      <div class="row"><a class="btn primary" href="#/neu-spiel/${encodeURIComponent(named)}">${icon('ai')}Sofortanalyse</a>
        ${DB.meta.repo ? `<a class="btn" href="${issue('Recherche: ' + named, 'new-game: ' + named)}" target="_blank" rel="noopener">${icon('spark')}Aufnehmen (3–5 Min.)</a>` : ''}</div></div>`;
  }).join('');
  list.innerHTML = rows || `<div class="empty">${inAtlas ? 'Alle Treffer sind schon in Atlas.' : 'Auch online nichts gefunden.'}</div>`;
  if (rows && inAtlas) list.insertAdjacentHTML('beforeend', `<p class="faint">${inAtlas} weitere Treffer sind schon in Atlas (oben).</p>`);
}

/* Series whose name matches the search – shown above the single games */
function franchiseHits(q) {
  const k = titleKey(q);
  if (k.length < 3) return [];
  return DB.franchises.filter((f) => f.games.length > 1 && (titleKey(f.name).includes(k) || k.includes(titleKey(f.name))))
    .sort((a, b) => (titleKey(b.name) === k) - (titleKey(a.name) === k) || b.games.length - a.games.length).slice(0, 4);
}
function franchiseRow(f) {
  const c = franchiseCoverage(f);
  const covers = [...f.games.filter((g) => g.cover), ...f.games.filter((g) => !g.cover)].slice(0, 4);
  return `<a class="item fr-hit" href="#/franchise/${encodeURIComponent(f.name)}">
    <div class="thumbs">${covers.map((g) => g.cover ? `<img src="${esc(g.cover.url)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="mini" style="background:hsl(${hue(f.name)} 30% 22%)"></span>`).join('')}</div>
    <div class="grow"><div class="title">${icon('layers')} ${esc(f.name)} <span class="faint">· Reihe</span></div>
    <div class="desc">${f.games.length} Spiele${f.routes ? ` · ${f.routes} Spielwege` : ''}${f.dual ? ' · Dual Screen' : ''} · ${c.done}/${c.total} tiefenrecherchiert</div></div>
    <span class="btn">Reihe öffnen</span></a>`;
}

function verifTag(v) {
  const ic = { 'thor-tested': 'check', community: 'gamepad', documented: 'info', 'ai-unverified': 'ai' }[v] || 'info';
  return `<span class="tag v-${esc(v)}">${icon(ic)}${esc(label('verification', v))}</span>`;
}

function shotsHTML(shots, group) {
  if (!shots?.length) return '';
  return `<div class="gallery">${shots.map((s, i) => {
    const pixel = s.url.includes('libretro-thumbnails') ? ' pixel' : '';
    const src = fullSrc(s.url);
    return `<button class="shot${pixel}${s._device ? ' dev' : ''}" data-lightbox="${esc(group)}" data-i="${i}" aria-label="Bild vergrößern: ${esc(s.caption || '')}"><img src="${esc(src)}"${src !== s.url ? ` data-fb="${esc(s.url)}"` : ''} alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="atlasImgErr(this)">${s._device ? '<span class="dev-tag">Reddit · vom Gerät</span>' : ''}${s.caption ? `<figcaption>${esc(s.caption)}</figcaption>` : ''}</button>`;
  }).join('')}</div>`;
}

/* ---------------- views ---------------- */
function filterGames() {
  const q = norm(state.q.trim());
  const terms = q.split(/\s+/).filter(Boolean);
  let list = DB.games.filter((g) => terms.every((t) => g._search.includes(t)));
  for (const f of FILTERS) if (state.chips.has(f.id)) list = list.filter(f.test);
  if (state.platform) list = list.filter((g) => g.platforms.includes(state.platform));
  const sorters = {
    relevance: (a, b) => {
      if (q) {
        const at = norm(a.title), bt = norm(b.title);
        const s = (t) => (t.startsWith(q) ? 2 : t.includes(q) ? 1 : 0);
        if (s(bt) !== s(at)) return s(bt) - s(at);
      }
      return b._score - a._score || a.title.localeCompare(b.title, 'de');
    },
    title: (a, b) => a.title.localeCompare(b.title, 'de'),
    updated: (a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || '') || b._score - a._score,
    explored: (a, b) => completeness(a).pct - completeness(b).pct || b._score - a._score,
  };
  return list.sort(sorters[state.sort] || sorters.relevance);
}

function viewDiscover() {
  const filtering = state.q || state.chips.size || state.platform;
  const curated = DB.games.filter((g) => g.routes.length);
  const routes = curated.reduce((n, g) => n + g.routes.length, 0);
  let html = `<div class="intro"><div><h1>Ein Spiel. Alle Wege, es zu spielen.</h1>
    <p>Emulation, native Ports, Dual-Screen-Mods und PC-Laufzeiten für ${esc(device().name || 'deinen Handheld')}, sortiert nach Spiel statt nach Emulator.</p></div>
    <div class="stats"><div><b>${DB.games.length}</b>Spiele</div><div><b>${routes}</b>Spielwege</div><div><b>${DB.games.filter((g) => g._dual).length}</b>Dual Screen</div></div></div>
    <div class="filters" role="group" aria-label="Filter">
      ${FILTERS.map((f) => `<button class="chip" data-chip="${f.id}" aria-pressed="${state.chips.has(f.id)}">${icon(f.icon)}${f.label}</button>`).join('')}
      <select class="chip" id="platform" aria-label="Plattform"><option value="">Alle Plattformen</option>${DB.allPlatforms.map((p) => `<option ${p === state.platform ? 'selected' : ''}>${esc(p)}</option>`).join('')}</select>
      <select class="chip" id="sort" aria-label="Sortierung">${[['relevance', 'Relevanz'], ['title', 'A–Z'], ['updated', 'Zuletzt aktualisiert'], ['explored', 'Wenig erkundet zuerst']].map(([v, l]) => `<option value="${v}" ${v === state.sort ? 'selected' : ''}>${l}</option>`).join('')}</select>
      ${filtering ? '<button class="chip" id="reset">Zurücksetzen</button>' : ''}
    </div>`;
  if (!filtering) {
    const shelf = (title, games, href) => games.length ? `<section class="section"><div class="section-head"><h2>${title}</h2>${href ? `<a href="${href}">Alle</a>` : ''}</div><div class="shelf">${games.slice(0, 18).map(cardHTML).join('')}</div></section>` : '';
    const byScore = (a, b) => b._score - a._score;
    const recent = DB.changelog.flatMap((e) => [e.game, ...(e.games || [])]).filter(Boolean);
    const recentGames = [...new Set(recent)].map((id) => DB.byId.get(id)).filter((g) => g && g.routes.length);
    html += shelf('Dual Screen auf dem Thor', DB.games.filter((g) => g._dual).sort(byScore), '#/filter/dual');
    html += shelf('Native Ports, Decomps &amp; Recomps', curated.filter(F('native')).sort(byScore), '#/filter/native');
    html += shelf('Offiziell für Android erschienen', DB.games.filter(F('android')).sort(byScore), '#/filter/android');
    html += shelf('Mit Mods', DB.games.filter(F('mods')).sort(byScore), '#/filter/mods');
    const cutoff = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
    const newWays = [...new Set(DB.changelog.filter((e) => e.type === 'route-added' && e.date >= cutoff).map((e) => e.game))].map((id) => DB.byId.get(id)).filter(Boolean);
    html += shelf('Neu spielbar (letzte 30 Tage)', newWays, '#/neu');
    if (recentGames.length) html += shelf('Zuletzt aktualisiert', recentGames, '#/neu');
    if (DB.games.some((g) => g._ai)) html += shelf('Neue KI-Funde', DB.games.filter((g) => g._ai), '#/filter/ai');
  }
  const list = filterGames();
  const frs = state.q.trim() ? franchiseHits(state.q.trim()) : [];
  if (frs.length) html += `<section class="section"><div class="section-head"><h2>${icon('layers')} Reihen</h2></div><div class="list">${frs.map(franchiseRow).join('')}</div></section>`;
  html += `<section class="section"><div class="result-head"><h2>${filtering ? (frs.length ? 'Einzelne Spiele' : 'Ergebnisse') : 'Alle Spiele'}</h2><span class="faint">${list.length} Spiele</span></div>
    ${gridHTML(list.slice(0, state.limit))}
    ${list.length > state.limit ? `<div class="more"><button class="btn" id="more">Mehr laden (${list.length - state.limit} weitere)</button></div>` : ''}</section>
    ${onlineIndexSection(state.q.trim())}`;
  return html;
}


/* ---------- platform badges (own icons + short codes; no manufacturer logos) ---------- */
const PLATFORMS = {
  'NES': ['NES', 'console', 'nintendo'], 'SNES': ['SNES', 'console', 'nintendo'], 'Nintendo 64': ['N64', 'console', 'nintendo'],
  'Nintendo GameCube': ['GC', 'console', 'nintendo'], 'Wii': ['Wii', 'console', 'nintendo'], 'Wii U': ['Wii U', 'console', 'nintendo'],
  'Nintendo Switch': ['Switch', 'handheld', 'nintendo'], 'Game Boy / Game Boy Color': ['GB', 'handheld', 'nintendo'],
  'Game Boy Advance': ['GBA', 'handheld', 'nintendo'], 'Nintendo DS': ['DS', 'handheld', 'nintendo'], 'Nintendo 3DS': ['3DS', 'handheld', 'nintendo'],
  'PlayStation': ['PS1', 'console', 'sony'], 'PlayStation 2': ['PS2', 'console', 'sony'], 'PlayStation 3': ['PS3', 'console', 'sony'],
  'PlayStation 4': ['PS4', 'console', 'sony'], 'PlayStation 5': ['PS5', 'console', 'sony'], 'PSP': ['PSP', 'handheld', 'sony'],
  'PlayStation Vita': ['Vita', 'handheld', 'sony'], 'Xbox': ['Xbox', 'console', 'microsoft'], 'Xbox 360': ['360', 'console', 'microsoft'],
  'Xbox One': ['XB1', 'console', 'microsoft'], 'Xbox Series': ['XSX', 'console', 'microsoft'], 'Dreamcast': ['DC', 'console', 'sega'],
  'Sega Saturn': ['Saturn', 'console', 'sega'], 'Sega Mega Drive': ['MD', 'console', 'sega'], 'PC': ['PC', 'pc', 'pc'],
  'Android': ['Android', 'phone', 'android'], 'iOS': ['iOS', 'phone', 'apple'], 'Arcade': ['Arcade', 'arcade', 'pc'], 'Nokia N-Gage': ['N-Gage', 'handheld', 'pc'],
};
const ICON_OF = { console: 'console', handheld: 'handheld', pc: 'pc', phone: 'phone', arcade: 'arcade' };
function platformBadge(p) {
  const [abbr, family, maker] = PLATFORMS[p] || [p.length > 8 ? p.split(' ').map((w) => w[0]).join('') : p, 'console', 'pc'];
  return `<span class="pf mk-${maker}" title="${esc(p)}">${icon(ICON_OF[family])}${esc(abbr)}</span>`;
}
const badges = (list, max = 5) => list.slice(0, max).map(platformBadge).join('') + (list.length > max ? `<span class="pf mk-pc">+${list.length - max}</span>` : '');

const modsFor = (g, v) => (g.mods || []).filter((m) => (m.release || []).includes(v.id));

function modsView(g) {
  const cats = DB.meta.modCategories || {};
  const vname = (id) => versionsOf(g).find((v) => v.id === id)?.name || id;
  const present = Object.keys(cats).filter((c) => g.mods.some((m) => (m.category || 'other') === c));
  const sel = state.modCat && present.includes(state.modCat) ? state.modCat : null;
  const shown = g.mods.filter((m) => !sel || (m.category || 'other') === sel);
  return `<p class="muted" style="margin:14px 0 8px">Community-Mods und Patches. „Funktioniert mit“ zeigt, welche Fassung du dafür brauchst – das entscheidet oft, welchen Spielweg du wählst.</p>
    ${present.length > 1 ? `<div class="chips"><button class="chip" data-modcat="" aria-pressed="${!sel}">Alle</button>${present.map((c) => `<button class="chip" data-modcat="${esc(c)}" aria-pressed="${sel === c}">${esc(cats[c])}</button>`).join('')}</div>` : ''}
    <div class="mods">${shown.map((m) => `<div class="mod"><div class="row" style="justify-content:space-between"><h3>${esc(m.name)}</h3>${verifTag(m.verification || 'documented')}</div>
      <div class="row"><span class="tag">${icon('wrench')}${esc(label('modCategories', m.category || 'other'))}</span>
        ${(m.release || []).length ? `<span class="faint">Funktioniert mit:</span>${m.release.map((id) => `<button class="tag linkish" data-open-version="${esc(id)}">${esc(vname(id))}</button>`).join('')}` : (m.edition ? `<span class="faint">${esc(m.edition)}</span>` : '')}</div>
      <p class="muted" style="margin:0">${esc(m.description)}</p><div data-shots="m:${esc(m.id)}">${shotsHTML(m.screenshots, 'm:' + m.id)}</div><a class="link" href="${esc(m.url)}" target="_blank" rel="noopener">Zum Mod ${icon('ext')}</a></div>`).join('')}</div>`;
}

/* ---------- versions ("Fassungen") and ways to play them ---------- */
const NATIVE = new Set(['native', 'native-mod', 'decomp', 'recomp', 'source-port']);
const VERIF_SCORE = { 'thor-tested': 50, community: 30, documented: 18, 'ai-unverified': 8 };

function versionsOf(g) {
  if (g.versions?.length) return g.versions;
  return g.platforms.map((p, i) => ({ id: 'p' + i, name: p, type: i ? 'release' : 'original', platforms: [p] }));
}

/* Every way to play the game: game-specific routes, official Android apps, generic platform emulators. */
function waysFor(g) {
  const versions = versionsOf(g);
  const ways = [];
  for (const v of versions) {
    const own = g.routes.filter((r) => r.release === v.id || (!r.release && v === versions[0]));
    for (const r of own) ways.push({ key: 'r:' + r.id, type: 'route', r, v, name: r.name, kind: r.kind, features: [...(r.features || [])] });
    if (v.platforms.includes('Android') && !own.some((r) => r.kind === 'native')) {
      ways.push({ key: 'o:' + v.id, type: 'official', v, name: 'Offizielle Android-App', kind: 'native', features: [...(v.traits || [])],
        link: g.playStore || null });
    }
    // an official Android release makes emulating its other platforms pointless noise
    if (v.platforms.includes('Android')) continue;
    const seen = new Set(own.flatMap((r) => r.projects || []));
    // multi-platform re-releases: only the primary (first) platform, otherwise every console emulator shows up
    for (const p of v.platforms.slice(0, 1)) for (const o of DB.platforms[p] || []) {
      if (seen.has(o.project)) continue;
      seen.add(o.project);
      ways.push({ key: `g:${v.id}:${o.project}`, type: 'generic', o, v, name: o.name, kind: o.kind, features: [], targets: o.targets });
    }
    attachReports(ways.filter((w) => w.v === v), v);
  }
  for (const w of ways) { w.g = g; Object.assign(w, rate(w)); }
  return ways;
}

/* Community reports (EmuReady etc.) live on the version; give each way the reports of its emulator.
   Emulators nobody in Atlas knows yet become their own way, so e.g. Winlator vs GameNative shows up by itself. */
const PC_RUNTIMES = /gamenative|winlator|gamehub|droiddeck|mobox|exagear|cassia/i;
function attachReports(ways, v) {
  const reps = v.reports || [];
  const key = (s) => norm(s).replace(/[^a-z0-9]/g, '');
  const used = new Set();
  const namesOf = (w) => [w.name, w.r?.runtime, ...(w.r?.projects || []).map((p) => DB.projects[p]?.name), DB.projects[w.o?.project]?.name]
    .filter(Boolean).map(key);
  for (const w of ways) w.community = [];
  for (const rep of reps) {
    const e = key(rep.emulator);
    if (!e) continue;
    const loose = ways.filter((w) => namesOf(w).some((n) => n.includes(e) || e.includes(n.slice(0, Math.max(4, e.length)))));
    // "Eden" reports belong to the Eden way, not also to its fork "Eden Duo" – an exact name wins
    const exact = loose.filter((w) => namesOf(w).includes(e));
    for (const w of exact.length ? exact : loose) w.community.push(rep);
    if (loose.length) used.add(rep);
  }
  const rest = reps.filter((rep) => !used.has(rep) && rep.emulator);
  const byEmu = new Map();
  for (const rep of rest) { if (!byEmu.has(rep.emulator)) byEmu.set(rep.emulator, []); byEmu.get(rep.emulator).push(rep); }
  for (const [emu, list] of byEmu) {
    ways.push({ key: `c:${v.id}:${key(emu)}`, type: 'community', v, name: emu, kind: PC_RUNTIMES.test(emu) ? 'pc-runtime' : 'emulation',
      features: [], targets: ['android'], community: list });
  }
}

/* Best own measurement of a way (setup.js), with the verdict. */
function suBestRunFor(w) {
  return w.g ? suBestRun(w.g, w) : null;
}

/* Transparent ranking for the selected device. Every point comes with a visible reason. */
function rate(w) {
  const reasons = [];
  const r = w.r;
  const targets = r?.targets || w.targets || ['android'];
  if (device().target && !targets.includes(device().target)) return { score: -999, reasons, fits: false };
  let score = w.type === 'route' ? VERIF_SCORE[r.verification] ?? 8 : w.type === 'official' ? 22 : w.type === 'community' ? 6 : 5;
  if (w.type === 'route' && r.verification === 'thor-tested') reasons.push(['check', 'Auf dem Thor getestet']);
  if (w.type === 'route' && r.verification === 'community') reasons.push(['gamepad', 'Erfahrungsberichte']);
  if (w.type === 'official') reasons.push(['check', 'Offiziell für Android']);
  if (w.features.includes('dual-screen')) { score += device().dualScreen ? 25 : 4; reasons.push(['dual', 'Dual Screen']); }
  if (NATIVE.has(w.kind) || w.type === 'official') { score += 12; reasons.push(['chip', 'Läuft nativ']); }
  for (const [f, txt] of [['widescreen', 'Widescreen'], ['high-fps', 'Hohe Bildrate'], ['upscaling', 'Höhere Auflösung'], ['crossplay', 'Crossplay']]) {
    if (w.features.includes(f)) { score += 4; reasons.push(['spark', txt]); }
  }
  if (w.features.includes('mods')) { score += 3; reasons.push(['wrench', 'Mods']); }
  if (w.type === 'generic' && !(w.community || []).length) reasons.push(['info', 'Allgemein, ungeprüft']);
  if (w.type === 'community') score += 4;
  // what this device knows: own measurements, favourite emulator per platform, apps already installed
  const run = typeof suBestRun === 'function' && w.g ? suBestRunFor(w) : null;
  if (run) {
    const ok = run.verdict !== 'bad' && run.verdict !== 'broken';
    score += ok ? 22 : -20;
    reasons.push([ok ? 'check' : 'alert', ok ? `Auf dem Thor gemessen: Ø ${run.fps.avg} FPS` : 'Auf dem Thor schlecht gelaufen']);
  }
  if (typeof suWayInstalled === 'function' && suWayInstalled(w)) { score += 4; reasons.push(['check', 'Schon installiert']); }
  const effort = r?.effort || (w.type === 'generic' ? 'guided' : 'easy');
  score += { easy: 6, guided: 2, advanced: 0, experimental: -6 }[effort] ?? 0;
  if (r?.status === 'archived') { score -= 40; reasons.push(['alert', 'Archiviert']); }
  if (r?.status === 'experimental') { score -= 6; reasons.push(['alert', 'Experimentell']); }
  const community = w.community || [];
  const reports = (r?.reports?.length || 0) + community.length;
  if (reports) score += Math.min(reports * 2, 10);
  const best = community.reduce((b, rep) => (rep.rank && rep.rank < (b?.rank ?? 99) ? rep : b), null);
  if (best) {
    score += { 1: 20, 2: 15, 3: 8, 4: 0, 5: -5, 6: -10, 7: -12, 8: -15 }[best.rank] ?? 0;
    reasons.push([best.rank <= 3 ? 'gamepad' : 'alert', `Community: ${best.ratingDe || best.rating} (${community.length})`]);
  }
  return { score, reasons, fits: true, effort, reports, best, perf: r?.performance?.length || 0 };
}

function wayTag(w) {
  if (w.type === 'route') return verifTag(w.r.verification);
  if (w.type === 'official') return `<span class="tag v-documented">${icon('check')}Offizielle App</span>`;
  if (w.type === 'community') return `<span class="tag v-community">${icon('gamepad')}Laut Community</span>`;
  return `<span class="tag">${icon('info')}Allgemein</span>`;
}

const RANK_CLASS = (rank) => (rank <= 2 ? 'good' : rank <= 3 ? 'ok' : 'bad');
function communityHTML(w) {
  const list = w.community || [];
  if (!list.length) return '';
  return `<div class="community"><h4>Erfahrungen von Geräten mit dem Chip des ${esc(DB.meta.devices?.[0]?.name || 'Referenzgeräts')} <span class="faint">· Quelle: EmuReady</span></h4>
    ${list.slice(0, 5).map((rep) => `<div class="report"><span class="rating ${RANK_CLASS(rep.rank)}">${esc(rep.ratingDe || rep.rating)}</span>
      <div class="grow"><div><b>${esc(rep.device)}</b> · ${esc(rep.emulator)}${rep.date ? ' · ' + fmtDate(rep.date) : ''}</div>
      ${rep.summary ? `<div class="muted">${esc(rep.summary)}</div>` : ''}
      ${rep.settings ? `<details class="settings"><summary>Einstellungen (${Object.keys(rep.settings).length})</summary><dl>${Object.entries(rep.settings).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl></details>` : ''}</div>
      <a class="btn" href="${esc(rep.url)}" target="_blank" rel="noopener">Bericht ${icon('ext')}</a></div>`).join('')}
    ${list.length > 5 ? `<p class="faint">${list.length - 5} weitere Berichte auf EmuReady.</p>` : ''}</div>`;
}

function wayBody(g, w) {
  const extra = communityHTML(w);
  if (w.type === 'route') return routeHTML(g, w.r).replace(/<\/article>$/, extra + '</article>');
  if (w.type === 'community') {
    return `<article class="route"><p class="muted">${esc(w.name)} ist in Atlas noch nicht als Weg für ${esc(w.v.name)} eingetragen, aber Nutzer berichten davon.</p>${extra}</article>`;
  }
  if (w.type === 'official') {
    return `<article class="route"><p>${esc(w.v.name)} ist offiziell für Android erschienen: kaufen und installieren über den Play Store, keine Emulation nötig.</p>
      ${(w.v.links || []).length || w.link ? `<div class="row">${w.link ? `<a class="btn primary" href="${esc(w.link)}" target="_blank" rel="noopener">Google Play ${icon('ext')}</a>` : ''}${(w.v.links || []).map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ${icon('ext')}</a>`).join('')}</div>` : ''}
      <p class="faint">Controller- und Zweitbildschirm-Unterstützung sind für diese Fassung noch nicht eingetragen.</p>${extra}</article>`;
  }
  return `<article class="route"><p class="muted">${esc(w.o.note)}</p><p class="faint">Allgemeiner Emulator für ${esc(w.v.platforms.join(', '))}. ${(w.community || []).length ? '' : `Ob ${esc(g.title)} darin gut läuft, ist noch nicht spielspezifisch geprüft.`}</p>${extra}${projectLine(DB.projects[w.o.project])}</article>`;
}

const wayId = (key) => 'w-' + key.replace(/[^a-z0-9-]/gi, '_');

function wayRow(g, w, open) {
  const dual = w.features.includes('dual-screen');
  const mini = w.reasons.filter(([ic]) => ic === 'spark' || ic === 'wrench' || ic === 'chip').map(([, t]) => `<span class="tag">${esc(t)}</span>`).join('');
  return `<details class="way${w.type === 'generic' ? ' generic' : ''}" id="${wayId(w.key)}" ${open ? 'open' : ''}>
    <summary><span class="way-name">${esc(w.name)}<small>${esc(label('kinds', w.kind))}${w.r?.runtime ? ' · ' + esc(w.r.runtime) : ''}</small></span>
      <span class="way-tags">${dual || w.features.includes('two-screens') ? `<span class="tag dual">${icon('dual')}${esc(dualLabel(w))}</span>` : ''}${mini}${typeof setupBadge === 'function' ? setupBadge(g, w) : ''}${w.best ? `<span class="rating ${RANK_CLASS(w.best.rank)}">${esc(w.best.ratingDe || w.best.rating)} · ${w.community.length}</span>` : ''}${wayTag(w)}</span></summary>
    ${typeof setupBar === 'function' ? setupBar(g, w) : ''}${wayBody(g, w)}</details>`;
}

function versionCard(g, v, ways) {
  const meta = [label('versionTypes', v.type), v.year].filter(Boolean).join(' · ');
  const android = v.platforms.includes('Android');
  const shown = state.dualOnly ? ways.filter((w) => w.features.includes('dual-screen')) : ways;
  const plats = v.platforms.length > 1 || v.platforms[0] !== v.name ? ' · ' + esc(v.platforms.join(', ')) : '';
  return `<section class="version" id="v-${esc(v.id)}">
    <div class="version-head"><div><div class="pfs">${badges(v.platforms)}</div><h3>${esc(v.name)}</h3><div class="sub">${esc(meta)}${plats}</div></div>
      <div class="row">${android ? `<span class="tag v-documented">${icon('check')}Android offiziell</span>` : ''}${(v.traits || []).map((t) => `<span class="tag">${esc(label('features', t))}</span>`).join('')}
        ${modsFor(g, v).length ? `<button class="tag linkish" data-gtab="mods">${icon('wrench')}${modsFor(g, v).length} Mods</button>` : ''}
        <button class="btn small" data-analyze="${esc(g.id)}" data-focus="${esc(v.id)}" title="Sofortanalyse nur für diese Fassung">${icon('ai')}${ways.length ? 'Mehr finden' : 'Wege suchen'}</button></div></div>
    ${v.note ? `<p class="muted">${esc(v.note)}</p>` : ''}
    ${(() => {
      if (!shown.length) return `<p class="faint">${ways.length ? 'Kein Dual-Screen-Weg für diese Fassung.' : 'Für diese Fassung ist auf Android noch kein Weg bekannt.'}</p>`;
      // emulators of the platform (generic + only known from reports) are one group: the best one is marked
      const isEmu = (w) => w.type === 'generic' || w.type === 'community';
      const main = shown.filter((w) => !isEmu(w));
      const gen = shown.filter(isEmu).sort((a, b) => b.score - a.score);
      const open = gen.some((w) => w.key === state.openWay);
      const plat = v.platforms[0];
      return `<div class="ways">${main.map((w) => wayRow(g, w, state.openWay === w.key)).join('')}
        ${gen.length ? `<details class="generic-group" ${open || !main.length ? 'open' : ''}><summary>${icon('gamepad')}<span>${gen.length > 1 ? `${gen.length} Emulatoren für ${esc(plat)}` : `Emulator für ${esc(plat)}`}: ${gen.map((w, i) => `${i === 0 && gen.length > 1 ? '<b>' : ''}${esc(w.name)}${i === 0 && gen.length > 1 ? '</b> <span class="tag best">beste Wahl</span>' : ''}${w.best ? ` <span class="rating ${RANK_CLASS(w.best.rank)}">${esc(w.best.ratingDe)}</span>` : ''}`).join(' · ')}</span></summary>
          ${gen.length > 1 ? `<p class="faint emu-why">Sortiert nach Berichten von Geräten mit dem Thor-Chip, deinen Messfahrten und dem, was schon installiert ist. Beim Einrichten kannst du jederzeit einen anderen nehmen.</p>` : ''}
          <div class="ways">${gen.map((w) => wayRow(g, w, state.openWay === w.key)).join('')}</div></details>` : ''}</div>`;
    })()}
    ${(v.links || []).length ? `<div class="row">${v.links.map((l) => `<a class="link" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ${icon('ext')}</a>`).join('')}</div>` : ''}
  </section>`;
}

function compareTable(g, ways) {
  const yes = (b, txt = 'ja') => b ? `<span class="yes">${icon('check')}${txt}</span>` : '<span class="no">–</span>';
  const pic = (w) => ['widescreen', 'upscaling', 'high-fps'].filter((f) => w.features.includes(f)).map((f) => label('features', f)).join(', ');
  const ART = { emulation: 'emuliert', 'emulator-mod': 'emuliert + Mod', companion: 'mit Companion', java: 'Java-Laufzeit', 'pc-runtime': 'PC-Laufzeit' };
  const art = (w) => NATIVE.has(w.kind) || w.type === 'official' ? 'nativ' : ART[w.kind] || label('kinds', w.kind);
  return `<p class="muted" style="margin:14px 0 8px">Alle Wege nebeneinander, sortiert wie die Empfehlung. Performance-Messungen und Erfahrungsberichte füllen sich nach und nach.</p>
  <div class="table-wrap"><table class="compare"><thead><tr><th>Weg</th><th>Fassung</th><th>Art</th><th>Dual Screen</th><th>Bild</th><th>Mods</th><th>Aufwand</th><th>Prüfstufe</th><th>Berichte</th><th>Performance</th></tr></thead><tbody>
  ${ways.map((w) => `<tr><td><button class="linkish" data-open="${esc(w.key)}">${esc(w.name)}</button></td><td>${esc(w.v.name)}</td><td>${art(w)}</td>
    <td>${yes(w.features.includes('dual-screen'))}</td><td>${pic(w) ? esc(pic(w)) : '<span class="no">–</span>'}</td>
    <td>${yes(w.features.includes('mods'))}</td><td>${esc(label('effort', w.effort))}</td><td>${wayTag(w)}</td>
    <td>${w.reports || '<span class="no">–</span>'}</td><td>${w.best ? `<span class="rating ${RANK_CLASS(w.best.rank)}">${esc(w.best.ratingDe || w.best.rating)}</span>` : w.perf ? `${w.perf} Messung(en)` : '<span class="no">noch keine</span>'}</td></tr>`).join('')}
  </tbody></table></div>`;
}

function recommendation(g, ways) {
  const top = ways.filter((w) => w.fits && w.r?.status !== 'archived').slice(0, 3);
  if (!top.length) return '';
  return `<section class="section reco"><div class="section-head"><h2>Für ${esc(device().name || 'dein Gerät')} zuerst ansehen</h2>
      <span class="faint">Reihenfolge aus Prüfstufe, Dual Screen, nativ oder emuliert und Aufwand – keine Messung</span></div>
    <div class="reco-grid">${top.map((w, i) => `<button class="reco-card" data-open="${esc(w.key)}">
      <span class="rank">${i + 1}</span><span class="reco-main"><b>${esc(w.name)}</b><small>${esc(w.v.name)}</small>
      <span class="reasons">${w.reasons.slice(0, 4).map(([ic, t]) => `<span class="tag${ic === 'dual' ? ' dual' : ''}">${icon(ic)}${esc(t)}</span>`).join('')}</span></span></button>`).join('')}</div></section>`;
}

function viewGame(id) {
  const g = DB.byId.get(id);
  if (!g) return `<div class="empty">Spiel nicht gefunden. <a class="link" href="#/">Zur Übersicht</a></div>`;
  const tab = state.gameTab || 'versions';
  const versions = versionsOf(g);
  const ways = waysFor(g).sort((a, b) => b.score - a.score);
  const fitting = ways.filter((w) => w.fits);
  const hidden = ways.length - fitting.length;
  const fav = state.favs.has(g.id);
  const tabs = [['versions', 'Fassungen', versions.length], ['compare', 'Vergleich', fitting.length], ['mods', 'Mods', g.mods.length]]
    .filter(([k, , n]) => n > 0 || k === 'versions');
  const best = (v) => Math.max(-998, ...fitting.filter((w) => w.v === v).map((w) => w.score));
  let body = '';
  if (tab === 'versions') {
    const order = [...versions].sort((a, b) => best(b) - best(a));
    body = `<p class="explain"><b>Fassung</b> = welche Version des Spiels (z. B. PS2-Original, PC-Fassung, Android-App, Remaster). <b>Spielweg</b> = womit du sie auf deinem Gerät spielst (Emulator, nativer Port, App, Mod).</p>
      ${g._dual ? `<div class="row" style="margin-top:10px"><button class="chip" id="dualOnly" aria-pressed="${!!state.dualOnly}">${icon('dual')}Nur Dual Screen</button></div>` : ''}
      <div class="versions">${order.filter((v) => fitting.some((w) => w.v === v)).map((v) => versionCard(g, v, fitting.filter((w) => w.v === v))).join('')}</div>
      ${(() => {
        const rest = order.filter((v) => !fitting.some((w) => w.v === v));
        if (!rest.length) return '';
        return `<details class="more-versions section"><summary>${rest.length} weitere ${rest.length === 1 ? 'Fassung' : 'Fassungen'} ohne bekannten Weg auf ${esc(device().name)}: ${esc(rest.map((v) => v.name).join(', '))}</summary>
          <div class="versions">${rest.map((v) => versionCard(g, v, [])).join('')}</div></details>`;
      })()}
      ${hidden ? `<p class="faint section">${hidden} Weg(e) nur für andere Plattformen als ${esc(device().name)} ausgeblendet (Info → Gerät).</p>` : ''}`;
  } else if (tab === 'compare') {
    body = compareTable(g, fitting);
    const rms = remakesOf(g);
    if (rms.length) {
      const rw = rms.flatMap((rm) => waysFor(rm).filter((w) => w.fits).sort((a, b) => b.score - a.score).slice(0, 4).map((w) => ({ ...w, v: { ...w.v, name: rm.title } })));
      body += `<details class="settings section"><summary>Zum Vergleich: Wege der ${rms.length === 1 ? 'Remakes' : `${rms.length} Remakes`} (${rw.length})</summary>${compareTable(g, rw).replace(/^<p class="muted"[^>]*>.*?<\/p>/s, '')}</details>`;
    }
  } else {
    body = modsView(g);
  }
  return `<a class="btn back" href="#/" data-back>${icon('back')}Zurück</a>
    <div class="hero">${coverHTML(g, { badges: false })}<div class="meta">
      <a class="franchise" href="#/franchise/${encodeURIComponent(g.franchise)}">${esc(g.franchise)}</a>
      <h1>${esc(g.title)}</h1>
      ${g.remakeOf && DB.byId.get(g.remakeOf) ? `<a class="remake-of" href="#/spiel/${esc(g.remakeOf)}">${icon('back')}Remake von <b>${esc(DB.byId.get(g.remakeOf).title)}</b>${(() => { const y = versionsOf(DB.byId.get(g.remakeOf))[0]?.year; return y ? ' (' + y + ')' : ''; })()}</a>` : ''}
      <div class="pfs">${badges(g.platforms, 8)}</div>
      <div class="row"><span class="tag">${versions.length} ${versions.length === 1 ? 'Fassung' : 'Fassungen'}</span><span class="tag">${fitting.length} ${fitting.length === 1 ? 'Weg' : 'Wege'} für ${esc(device().name)}</span>${g.genre ? `<span class="tag">${esc(g.genre)}</span>` : ''}${g._dual ? `<span class="tag dual">${icon('dual')}Dual Screen</span>` : ''}</div>
      ${g.summary ? `<p>${esc(g.summary)}</p>` : ''}
      <div class="row"><button class="btn ${fav ? 'on' : ''}" id="fav">${icon('bookmark')}${fav ? 'Gemerkt' : 'Merken'}</button>
      <button class="btn" data-analyze="${esc(g.id)}" title="Sofort auf diesem Gerät mit deinem OpenAI-Schlüssel">${icon('ai')}Sofortanalyse</button>
      </div><div class="row">${researchStatus(g)}${g.updatedAt ? `<span class="faint">zuletzt geändert ${fmtDate(g.updatedAt)}</span>` : ''}
        ${g.wikipedia ? `<a class="link small" href="${esc(g.wikipedia)}" target="_blank" rel="noopener">Wikipedia ${icon('ext')}</a>` : ''}
        ${g.wikidata ? `<a class="link small" href="https://www.wikidata.org/wiki/${esc(g.wikidata)}" target="_blank" rel="noopener">Wikidata ${icon('ext')}</a>` : ''}</div>
    </div></div>
    ${g.screenshots.length ? `<section class="section"><div class="section-head"><h2>So sieht das Spiel aus</h2><span class="faint">Originalspiel</span></div><div data-shots="game">${shotsHTML(g.screenshots, 'game')}</div></section>` : ''}
    ${dataPanel(g)}
    ${analysisPanel(g.id)}
    ${recommendation(g, fitting)}
    ${dualBox(g, fitting)}
    <section class="section"><div class="seg" role="tablist">${tabs.map(([k, l, n]) => `<button role="tab" data-gtab="${k}" aria-selected="${tab === k}">${l}<span class="n">${n}</span></button>`).join('')}</div>${body}</section>
    ${remakesSection(g, fitting)}
    ${relatedSections(g)}`;
}

/* Remakes are games of their own (remakeOf); the original shows them compactly – what they offer, with a link. */
const remakesOf = (g) => DB.games.filter((x) => x.remakeOf === g.id).sort((a, b) => (versionsOf(a)[0]?.year || 0) - (versionsOf(b)[0]?.year || 0));
function remakesSection(g, ownWays) {
  const list = remakesOf(g);
  if (!list.length) return '';
  const ownBest = ownWays[0];
  return `<section class="section remakes"><div class="section-head"><h2>${icon('spark')} ${list.length === 1 ? 'Remake' : `${list.length} Remakes`}</h2>
      <span class="faint">eigene Spiele mit eigenen Spielwegen</span></div>
    ${list.map((rm) => {
      const v = versionsOf(rm)[0] || {};
      const ways = waysFor(rm).filter((w) => w.fits).sort((a, b) => b.score - a.score);
      const top = ways.filter((w) => w.r?.status !== 'archived').slice(0, 3);
      const dual = ways.some((w) => w.features.includes('dual-screen'));
      const extra = [dual && !ownWays.some((w) => w.features.includes('dual-screen')) ? 'Dual Screen nur im Remake' : '',
        ways.some((w) => NATIVE.has(w.kind) || w.type === 'official') && !ownWays.some((w) => NATIVE.has(w.kind) || w.type === 'official') ? 'nativ spielbar' : '',
        top[0]?.best && (!ownBest?.best || top[0].best.rank < ownBest.best.rank) ? `läuft laut Berichten besser (${top[0].best.ratingDe})` : ''].filter(Boolean);
      return `<details class="remake"><summary>
          <a class="remake-cover" href="#/spiel/${esc(rm.id)}">${rm.cover ? `<img src="${esc(rm.cover.url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : icon('image')}</a>
          <span class="remake-main"><b>${esc(rm.title)}</b><span class="faint">${[v.year, (rm.platforms || []).join(', ')].filter(Boolean).map(esc).join(' · ')}</span>
            <span class="row">${dual ? `<span class="tag dual">${icon('dual')}Dual Screen</span>` : ''}<span class="tag">${ways.length} ${ways.length === 1 ? 'Weg' : 'Wege'}</span>${extra.map((x) => `<span class="tag best">${esc(x)}</span>`).join('')}</span></span>
          <span class="remake-more faint">Was es bietet</span></summary>
        <div class="remake-body">${v.note ? `<p class="muted">${esc(v.note)}</p>` : rm.summary ? `<p class="muted">${esc(rm.summary)}</p>` : ''}
          ${top.length ? `<div class="remake-ways">${top.map((w, i) => `<div><span class="n">${i + 1}</span><b>${esc(w.name)}</b> <span class="faint">${esc(label('kinds', w.kind))}</span>${w.best ? ` <span class="rating ${RANK_CLASS(w.best.rank)}">${esc(w.best.ratingDe || w.best.rating)}</span>` : ''}${w.features.includes('dual-screen') ? ` <span class="tag dual">${icon('dual')}</span>` : ''}</div>`).join('')}</div>` : '<p class="faint">Noch kein Spielweg bekannt.</p>'}
          <a class="btn primary" href="#/spiel/${esc(rm.id)}">Zum Remake ${icon('ext')}</a></div></details>`;
    }).join('')}</section>`;
}

function projectLine(p) {
  if (!p?.id) return '';
  const rel = p.latestRelease?.tag ? `${esc(p.latestRelease.tag)}${p.latestRelease.date ? ' · ' + fmtDate(p.latestRelease.date) : ''}` : (p.pushedAt ? 'Aktiv ' + fmtDate(p.pushedAt) : '');
  return `<div class="proj"><a class="name" href="#/projekt/${esc(p.id)}">${esc(p.name)}</a>${p.archived ? '<span class="tag archived">archiviert</span>' : ''}${rel ? `<span class="rel">${rel}</span>` : ''}<a class="btn" href="${esc(p.latestRelease?.url || p.url)}" target="_blank" rel="noopener">${p.latestRelease?.url ? 'Release' : 'Projekt'} ${icon('ext')}</a></div>`;
}

function routeHTML(g, r) {
  const feats = (r.features || []).filter((f) => f !== 'dual-screen').map((f) => `<span class="tag">${esc(label('features', f))}</span>`).join('');
  const projects = (r.projects || []).map((id) => projectLine(DB.projects[id])).join('');
  const links = (r.links || []).map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ${icon('ext')}</a>`).join('');
  const steps = r.steps?.length ? `<ol>${r.steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>` : '<p class="muted">Anleitung im Projekt lesen, Spielstände sichern und zuerst ohne Zusatz-Mods testen.</p>';
  return `<article class="route${r.verification === 'ai-unverified' ? ' is-ai' : ''}" id="r-${esc(r.id)}">
    <div class="route-head"><div><h3>${esc(r.name)}</h3><div class="sub">${esc(label('kinds', r.kind))}${r.runtime ? ' · ' + esc(r.runtime) : ''}${r.edition ? ' · ' + esc(r.edition) : ''}</div></div>
      <div class="row">${verifTag(r.verification)}<span class="tag">${esc(label('effort', r.effort || 'guided'))}</span>${r.status === 'archived' ? '<span class="tag archived">archiviert</span>' : r.status === 'experimental' ? '<span class="tag">experimentell</span>' : ''}</div></div>
    ${r.verification === 'ai-unverified' ? `<div class="note-ai">${icon('ai')}<span>Vom Pflege-Agenten gefunden und aus der Projektquelle zusammengefasst, aber noch auf keinem Gerät geprüft.</span></div>` : ''}
    ${r.features?.includes('dual-screen') ? `<div class="dualbox">${icon('dual')}<span>Zweiter Bildschirm: ${esc(r.dualScreen || 'unterstützt')}</span></div>` : ''}
    ${feats ? `<div class="row">${feats}</div>` : ''}
    <div data-shots="r:${esc(r.id)}">${shotsHTML(r.screenshots, 'r:' + r.id)}</div>
    ${redditBox(g, r)}
    ${wayImageButton(g, r)}
    <div class="cols">
      ${r.benefit ? `<div><h4>Vorteil</h4><p>${esc(r.benefit)}</p></div>` : ''}
      ${r.caveat ? `<div><h4>Beachten</h4><p class="warn">${esc(r.caveat)}</p></div>` : ''}
      ${r.requires?.length ? `<div><h4>Du brauchst</h4><ul>${r.requires.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
      <div><h4>So geht's</h4>${steps}</div>
    </div>
    ${r.version ? `<div class="faint">Version: ${esc(r.version)}</div>` : ''}
    ${projects ? `<div class="projects-line"><h4 class="faint" style="margin:0">Projekte</h4>${projects}</div>` : ''}
    ${links ? `<div class="row">${links}</div>` : ''}
    ${(r.reports || []).length ? `<div class="community"><h4>Erfahrungsberichte</h4>${r.reports.map((rep) => `<div class="report"><span class="rating ok">${esc(rep.device || 'Bericht')}</span>
      <div class="grow muted">${esc(rep.summary)}</div><a class="btn" href="${esc(rep.url)}" target="_blank" rel="noopener">Bericht ${icon('ext')}</a></div>`).join('')}</div>` : ''}
    ${(r.performance || []).length ? `<div class="community"><h4>Performance</h4>${r.performance.map((pf) => `<div class="report"><span class="rating good">${esc(pf.device)}</span>
      <div class="grow">${esc(pf.result)}${pf.settings ? `<div class="faint">${esc(pf.settings)}</div>` : ''}</div><a class="btn" href="${esc(pf.source)}" target="_blank" rel="noopener">Quelle ${icon('ext')}</a></div>`).join('')}</div>` : ''}
    <div class="faint">Geprüft am ${fmtDate(r.checkedAt)}${r.testedOn?.length ? ' · getestet auf ' + esc(r.testedOn.join(', ')) : ''}</div>
  </article>`;
}

function viewFranchises() {
  const q = norm(state.q.trim());
  const list = DB.franchises.filter((f) => !q || norm(f.name).includes(q) || f.games.some((g) => g._search.includes(q)));
  const withRoutes = list.filter((f) => f.routes > 0 || f.games.length > 1);
  return `<h1>Franchises</h1><p class="muted">Spielereihen mit allen bekannten Teilen. Reihen mit dokumentierten Spielwegen stehen oben.</p>
    <div class="fr-grid section">${withRoutes.map((f) => `<a class="item" href="#/franchise/${encodeURIComponent(f.name)}">
      <div class="thumbs">${[...f.games.filter((g) => g.cover), ...f.games.filter((g) => !g.cover)].slice(0, 3).map((g) => g.cover ? `<img src="${esc(g.cover.url)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span class="mini" style="background:hsl(${hue(f.name)} 30% 22%)"></span>`).join('')}</div>
      <div class="grow"><div class="title">${esc(f.name)}</div><div class="desc">${f.games.length} Spiele${f.routes ? ` · ${f.routes} Spielwege` : ''}${f.dual ? ' · Dual Screen' : ''} · ${franchiseCoverage(f).done}/${f.games.length} recherchiert</div></div></a>`).join('')}</div>
    <p class="faint section">Einzeltitel ohne Reihe findest du über die Suche (${list.length - withRoutes.length} weitere).</p>`;
}

function viewFranchise(name) {
  const f = DB.franchises.find((x) => x.name === name);
  if (!f) return '<div class="empty">Franchise nicht gefunden.</div>';
  const c = franchiseCoverage(f);
  return `<a class="btn back" href="#/franchises" data-back>${icon('back')}Franchises</a><h1>${esc(f.name)}</h1>
    <p class="muted">${f.games.length} Spiele${f.routes ? ` · ${f.routes} dokumentierte Spielwege` : ''}</p>
    <div class="panel section coverage"><div class="meter"><span>Tiefenrecherchiert</span><b>${c.done} von ${c.total}${c.queued ? ` · ${c.queued} in der Warteschlange` : ''}</b><i style="--v:${Math.round((c.done / c.total) * 100)}%"></i></div>
      <p class="muted">Fehlen Spiele oder Fassungen? Die Reihen-Analyse legt fehlende Spiele an und recherchiert danach jedes Spiel einzeln in der Tiefe (die ersten sofort, der Rest alle 2 Stunden).</p>
      ${(() => {
        const scan = DB.franchiseScan[f.name];
        if (!scan) return '<p class="faint">Für diese Reihe lief noch keine Reihen-Analyse – ob Spiele fehlen, ist also noch offen.</p>';
        return `<p class="faint">Letzte Reihen-Analyse ${fmtDate(scan.date)} (${scan.source === 'wikidata' ? 'Wikidata' : 'KI-Websuche'}): ${scan.listed} Titel gefunden, ${scan.added.length} neu aufgenommen, ${scan.versions.length} als Fassung eingeordnet${scan.queued != null ? `, ${scan.queued} zur Tiefenrecherche vorgemerkt, ${scan.basic} behalten das Basisprofil` : ''}${scan.skipped.length ? `; übersprungen: ${esc(scan.skipped.slice(0, 12).map((x) => x.title).join(', '))}${scan.skipped.length > 12 ? ' …' : ''}` : ''}.</p>`;
      })()}
      <div class="row">${DB.meta.repo ? `<a class="btn primary" href="${esc(issueUrl('Reihe: ' + f.name, 'franchise: ' + f.name))}" target="_blank" rel="noopener">${icon('layers')}Reihe vervollständigen &amp; recherchieren</a>
        <a class="btn" href="${esc(issueUrl('Bilder: Reihe ' + f.name, 'images-franchise: ' + f.name))}" target="_blank" rel="noopener" title="Cover, Originalbilder und Spielweg-Bilder für bis zu 25 Spiele der Reihe">${icon('image')}Bilder für die Reihe suchen</a>` : ''}
        <span class="faint">${f.games.filter((g) => g.cover).length}/${f.games.length} mit Cover</span></div></div>
    <div class="section">${gridHTML(f.games)}</div>`;
}

const PROJECT_GROUPS = [
  ['Emulatoren & Forks', ['emulator', 'emulator-fork']], ['Native Ports', ['port']], ['Launcher & Laufzeiten', ['launcher', 'runtime', 'official']],
  ['Mods & Companions', ['mod', 'companion']], ['Verzeichnisse & Datenquellen', ['directory', 'data-source', 'tool', 'other']],
];

function viewProjects() {
  const q = norm(state.q.trim());
  const all = Object.values(DB.projects).filter((p) => !q || norm(p.name + ' ' + (p.description || '')).includes(q));
  return `<h1>Projekte</h1><p class="muted">Emulatoren, Ports, Launcher und Mods hinter den Spielwegen, mit dem neuesten Release, das der Watcher gefunden hat.</p>
    ${PROJECT_GROUPS.map(([title, kinds]) => {
      const ps = all.filter((p) => kinds.includes(p.kind)).sort((a, b) => (b.games?.length || 0) - (a.games?.length || 0) || a.name.localeCompare(b.name));
      if (!ps.length) return '';
      return `<section class="section"><div class="section-head"><h2>${title}</h2><span class="faint">${ps.length}</span></div><div class="list">${ps.map((p) => `
        <a class="item" href="#/projekt/${esc(p.id)}"><div class="grow"><div class="title">${esc(p.name)} ${p.archived ? '<span class="tag archived">archiviert</span>' : ''}</div>
        <div class="desc">${esc(p.description || p.url)}</div></div>
        <div class="faint" style="text-align:right">${p.latestRelease?.tag ? esc(p.latestRelease.tag) + '<br>' + fmtDate(p.latestRelease.date) : ''}${p.games?.length ? `<br>${p.games.length} Spiel${p.games.length > 1 ? 'e' : ''}` : ''}</div></a>`).join('')}</div></section>`;
    }).join('')}`;
}

function viewProject(id) {
  const p = DB.projects[id];
  if (!p) return '<div class="empty">Projekt nicht gefunden.</div>';
  const games = DB.games.filter((g) => g.routes.some((r) => r.projects?.includes(id)) || p.games?.includes(g.id));
  const plats = Object.entries(DB.platforms).filter(([, os]) => os.some((o) => o.project === id)).map(([k]) => k);
  return `<a class="btn back" href="#/projekte" data-back>${icon('back')}Projekte</a><h1>${esc(p.name)}</h1>
    <p class="muted">${esc(label('kinds', p.kind) === p.kind ? p.kind : label('kinds', p.kind))}${p.description ? ' · ' + esc(p.description) : ''}</p>
    <div class="section">${projectLine(p)}</div>
    ${plats.length ? `<p class="muted section">Allgemeine Option für: ${plats.map(esc).join(', ')}</p>` : ''}
    ${games.length ? `<section class="section"><div class="section-head"><h2>Spiele mit diesem Projekt</h2></div>${gridHTML(games)}</section>` : ''}`;
}

function viewNews() {
  const days = new Map();
  for (const e of DB.changelog.slice(0, 200)) {
    if (!days.has(e.date)) days.set(e.date, []);
    days.get(e.date).push(e);
  }
  const ic = { release: 'box', 'route-added': 'play', 'route-updated': 'play', 'game-added': 'compass', 'mod-added': 'wrench', 'project-added': 'box', 'screenshot-added': 'compass', verified: 'check', removed: 'alert', system: 'info' };
  const agent = DB.agent || {};
  return `<h1>Neu</h1><p class="muted">Was der Watcher und der Pflege-Agent zuletzt gefunden und eingetragen haben.</p>
    <div class="panels section">
      <div class="panel"><div class="faint">Datenstand</div><div class="big">${fmtDate(DB.builtAt)}</div></div>
      <div class="panel"><div class="faint">Letzter Agenten-Lauf</div><div class="big">${agent.lastRun ? fmtDate(agent.lastRun) : '–'}</div>${agent.summary ? `<div class="faint">${esc(agent.summary)}</div>` : ''}</div>
      <div class="panel"><div class="faint">Unsortierte Funde</div><div class="big">${DB.inboxCount}</div><div class="faint">warten darauf, einem Spiel zugeordnet zu werden</div></div>
    </div>
    ${[...days.entries()].map(([d, es]) => `<div class="log-day"><h3>${fmtDate(d)}</h3>${es.map((e) => {
      const games = [e.game, ...(e.games || [])].filter(Boolean).map((id) => DB.byId.get(id)).filter(Boolean);
      const ai = e.by === 'agent' || e.by === 'ai-research';
      return `<div class="log"><div class="ico ${esc(e.type)}${ai ? ' ai' : ''}">${icon(ai ? 'ai' : ic[e.type] || 'info')}</div><div>
        <div>${esc(e.text)}</div>
        <div class="faint">${games.slice(0, 6).map((g) => `<a href="#/spiel/${esc(g.id)}">${esc(g.title)}</a>`).join(' · ')}${e.url ? ` ${games.length ? '· ' : ''}<a href="${esc(e.url)}" target="_blank" rel="noopener">Quelle</a>` : ''}</div>
      </div></div>`;
    }).join('')}</div>`).join('') || '<div class="empty">Noch keine Einträge.</div>'}`;
}

function viewFavs() {
  const games = [...state.favs].map((id) => DB.byId.get(id)).filter(Boolean);
  return `<h1>Merkliste</h1><p class="muted">Gespeichert nur auf diesem Gerät.</p><div class="section">${games.length ? gridHTML(games) : '<div class="empty">Noch nichts gemerkt. Öffne ein Spiel und tippe auf „Merken“.</div>'}</div>`;
}

function qualityPanel() {
  const routes = DB.games.flatMap((g) => g.routes);
  const shots = routes.flatMap((r) => r.screenshots || []);
  const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
  const withShots = routes.filter((r) => (r.screenshots || []).length).length;
  const verified = shots.filter((s) => ['ai-verified', 'source-verified'].includes(s.check)).length;
  const versions = DB.games.flatMap((g) => g.versions || []);
  const rows = [
    ['Spiele mit Cover', pct(DB.games.filter((g) => g.cover).length, DB.games.length)],
    ['Spielwege mit Screenshots', pct(withShots, routes.length)],
    ['Screenshots geprüft', pct(verified, shots.length)],
    ['Fassungen mit Erscheinungsjahr', pct(versions.filter((v) => v.year).length, versions.length)],
  ];
  return `<div class="panel"><h3>Datenqualität</h3>${rows.map(([l, v]) => `<div class="meter"><span>${l}</span><b>${v} %</b><i style="--v:${v}%"></i></div>`).join('')}
    <p class="faint">${routes.filter((r) => (r.features || []).includes('dual-screen') && !(r.screenshots || []).length).length} Dual-Screen-Wege noch ohne Bild ·
      ${shots.filter((s) => ['readme', 'ai', 'ai-unclear'].includes(s.check)).length} Bilder warten auf Prüfung ·
      ${versions.filter((v) => (v.reports || []).length).length} Fassungen mit Community-Berichten · ${DB.inboxCount} unsortierte Funde</p></div>`;
}

function usagePanel() {
  const months = Object.keys(DB.usage || {}).sort().reverse();
  if (!months.length) return '';
  const m = DB.usage[months[0]];
  const n = (x) => (x || 0).toLocaleString('de-DE');
  const KIND = { recherche: 'Tiefenrecherche', warteschlange: 'Warteschlange', reihe: 'Reihen-Analyse', bilder: 'Bilder', bildpruefung: 'Bildprüfung', dualscreen: 'Dual-Screen-Suchlauf' };
  const kinds = Object.entries(m.byKind || {}).sort((a, b) => (b[1].input + b[1].output * 4) - (a[1].input + a[1].output * 4));
  return `<div class="panel"><h3>${icon('ai')} KI-Verbrauch ${esc(months[0])}</h3>
    <p class="muted">${n(m.runs)} Läufe · ${n(m.calls)} Anfragen · ${n(m.searches)} Websuchen · ${n(m.input)} Eingabe- / ${n(m.output)} Ausgabe-Tokens${m.estimate != null ? ` · geschätzt <b>${m.estimate.toLocaleString('de-DE', { minimumFractionDigits: 2 })}</b>` : ''}</p>
    <div class="table-wrap"><table class="compare"><thead><tr><th>Bereich</th><th>Anfragen</th><th>Websuchen</th><th>Tokens (ein/aus)</th></tr></thead><tbody>
    ${kinds.map(([k, v]) => `<tr><td>${esc(KIND[k] || k)}</td><td>${n(v.calls)}</td><td>${n(v.searches)}</td><td>${n(v.input)} / ${n(v.output)}</td></tr>`).join('')}</tbody></table></div>
    <p class="faint">Warteschlange: ${(DB.queue || []).length} Spiele, höchstens ${DB.meta.maxQueuePerDay || 12} pro Tag. Eine Euro-Schätzung erscheint, wenn im Repo die Preis-Variablen gesetzt sind.</p></div>`;
}

function viewInfo() {
  return `<h1>Info</h1>
  <div class="panels section">
    <div class="panel"><h3>Dein Gerät</h3><p class="muted">Spielwege für andere Plattformen werden eingeklappt.</p>
      <div class="chips">${(DB.meta.devices || []).map((d) => `<button class="chip" data-device="${esc(d.id)}" aria-pressed="${d.id === state.device}">${esc(d.name)}</button>`).join('')}</div></div>
    <div class="panel"><h3>Was die Markierungen bedeuten</h3><div class="legend">
      ${Object.keys(DB.meta.verification || {}).map((k) => `<div>${verifTag(k)}</div>`).join('')}</div></div>
    <div class="panel"><h3>${icon('ai')} KI-Sofortanalyse</h3><p class="muted">Mit deinem OpenAI-API-Schlüssel recherchiert Atlas ein Spiel oder eine Fassung sofort (1–3 Minuten, kostet API-Guthaben). Der Schlüssel bleibt auf diesem Gerät und geht nur an api.openai.com.</p>
      <label class="field">API-Schlüssel<input id="ai-key" type="password" autocomplete="off" placeholder="sk-…" value="${esc(aiKey())}"></label>
      <label class="field">Modell<input id="ai-model" type="text" autocomplete="off" placeholder="${esc(DB.research?.model || '')}" value="${esc(store.get('openaiModel', ''))}"></label>
      <div class="row"><button class="btn primary" id="ai-save">Speichern</button>${aiKey() ? '<button class="btn" id="ai-clear">Löschen</button>' : ''}</div></div>
    ${researchPanel()}
    ${typeof setupPanel === 'function' ? setupPanel() : ''}
    ${redditPanel()}
    ${usagePanel()}
    ${qualityPanel()}
    <div class="panel"><h3>Steuerung</h3><p class="muted">Steuerkreuz bewegt den Fokus, <kbd>A</kbd> öffnet, <kbd>B</kbd> geht zurück, <kbd>L1</kbd>/<kbd>R1</kbd> wechseln den Bereich, <kbd>Start</kbd> springt zur Suche. Mit zwei Bildschirmen: <kbd>Select</kbd> wechselt zwischen Stöbern und Bühne.</p></div>
    <div class="panel"><h3>Daten</h3><p class="muted">Stand ${fmtDate(DB.builtAt)}. ${DB.games.length} Spiele, ${Object.keys(DB.projects).length} Projekte. Die App holt sich neue Daten selbst, sobald sie online geöffnet wird.</p>
      <div class="row"><button class="btn" id="update">Nach Updates suchen</button>${window.ATLAS_EMBEDDED ? '' : '<a class="btn" href="Handheld-Atlas-offline.html" download>Offline-Version laden</a>'}</div></div>
  </div>
  <p class="faint section">Atlas enthält keine ROMs, BIOS-Dateien, APKs oder Spieldaten. Die Atlas-App installiert Apps nur aus den Quellen der Projekte (GitHub-Releases, Google Play) und nur nach deiner Bestätigung; im Browser installiert Atlas nichts. Alle Projekte gehören ihren Urhebern; Bilder sind verlinkt und stammen aus den angegebenen Quellen (u. a. libretro-thumbnails, Steam, Projekt-Repositories).</p>`;
}

/* ---------------- instant analysis (OpenAI, straight from this device) ----------------
   Same rules and JSON schema as scripts/ai_research.py (shipped in data.json → DB.research).
   The API key never leaves this device except towards api.openai.com. Results are shown immediately and
   are NOT saved; "Dauerhaft übernehmen" opens a GitHub issue that the KI-Recherche workflow applies. */
const analyses = new Map();   // key: game id or "new:<title>"
const aiKey = () => store.get('openaiKey', '');
const aiModel = () => store.get('openaiModel', '') || DB.research?.model || 'gpt-6.1-sol';

function analysisPrompt(g, focus) {
  const known = {
    versions: versionsOf(g).map((v) => ({ key: v.id, name: v.name, platforms: v.platforms, year: v.year ?? null })),
    routes: (g.routes || []).map((r) => ({ name: r.name, version: r.release, kind: r.kind })),
    mods: (g.mods || []).map((m) => m.name),
  };
  const v = focus && versionsOf(g).find((x) => x.id === focus);
  const focusText = v ? `\nSCHWERPUNKT: Fassung „${v.name}“ (key ${v.id}, ${v.platforms.join(', ')}). Suche vor allem Wege, Erfahrungsberichte, Einstellungen und Mods für genau diese Fassung auf dem AYN Thor.\n` : '';
  return `Du recherchierst für „Handheld Atlas“, einen spielzentrierten Katalog für Android-Handhelds
(Referenzgerät AYN Thor: Snapdragon 8 Gen 2, zwei Displays, Controller). Spiel: „${g.title}“ (${(g.platforms || []).join(', ') || 'Plattformen unbekannt'}).
${focusText}
Bereits bekannt (nicht wiederholen, nur ergänzen oder korrigieren): ${JSON.stringify(known)}
Allgemeine Emulatoren je Plattform sind schon hinterlegt: ${Object.keys(DB.platforms).sort().join(', ')} – liste sie NICHT als Spielweg,
außer es gibt spielspezifische Belege (Kompatibilität, Patches, empfohlene Einstellungen, Fork mit Dual Screen).

${DB.research.rules}`;
}

async function runAnalysis(key, g, focus) {
  if (!aiKey()) { analyses.set(key, { status: 'nokey', focus }); refreshAnalysis(key); return; }
  const ctrl = new AbortController();
  const a = { status: 'running', focus, started: Date.now(), ctrl };
  analyses.set(key, a);
  refreshAnalysis(key);
  a.tick = setInterval(() => { const el = document.getElementById('an-elapsed'); if (el) el.textContent = Math.round((Date.now() - a.started) / 1000) + ' s'; }, 1000);
  try {
    const res = await fetch('https://api.openai.com/v1/responses', {
      method: 'POST', signal: ctrl.signal,
      headers: { Authorization: 'Bearer ' + aiKey(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: aiModel(), store: false, tools: [{ type: 'web_search', search_context_size: 'high' }],
        include: ['web_search_call.action.sources'], tool_choice: 'required', reasoning: { effort: 'medium' },
        text: { format: DB.research.format }, input: analysisPrompt(g, focus), max_output_tokens: 16000 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || `HTTP ${res.status}`);
    if (data.status && data.status !== 'completed') throw new Error(`Antwort unvollständig (${data.incomplete_details?.reason || data.status})`);
    const text = (data.output || []).filter((o) => o.type === 'message').flatMap((o) => o.content || [])
      .filter((c) => c.type === 'output_text').map((c) => c.text).join('\n');
    const sources = new Set();
    for (const o of data.output || []) {
      for (const s of o.action?.sources || []) if (s.url) sources.add(s.url);
      for (const c of o.content || []) for (const an of c.annotations || []) if (an.url) sources.add(an.url);
    }
    Object.assign(a, { status: 'done', result: JSON.parse(text), sources: [...sources], at: new Date().toISOString() });
  } catch (err) {
    Object.assign(a, { status: err.name === 'AbortError' ? 'cancelled' : 'error', error: err.message });
  } finally {
    clearInterval(a.tick);
    refreshAnalysis(key);
  }
}

function refreshAnalysis(key) {
  const el = document.getElementById('analysis');
  if (el && el.dataset.key === key) el.outerHTML = analysisPanel(key);
}

function issueUrl(title, body) {
  return `https://github.com/${DB.meta.repo}/issues/new?labels=recherche&title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}
/* Open a prepared GitHub issue. GitHub rejects very long links ("Whoops, something went wrong"): then the text goes to
   the clipboard and the issue opens with a short note to paste it. With a GitHub key (Info) none of this is needed. */
async function openIssue(title, body) {
  let url = issueUrl(title, body);
  if (url.length > 7000) {
    let copied = false;
    try { await navigator.clipboard.writeText(body); copied = true; } catch { /* no clipboard permission */ }
    url = issueUrl(title, copied ? 'Der Inhalt ist in der Zwischenablage – bitte hier einfügen (lange tippen → Einfügen) und dann „Create“.'
      : body.split('```')[0].trim() + '\n\n(zu lang für einen Link – bitte unter Info einen GitHub-Schlüssel eintragen, dann sendet Atlas direkt)');
    toast(copied ? 'Text in die Zwischenablage kopiert – auf GitHub einfügen und „Create“ tippen. Einfacher: GitHub-Schlüssel unter Info eintragen.'
      : 'Zu lang für einen GitHub-Link. Bitte unter Info einen GitHub-Schlüssel eintragen – dann sendet Atlas direkt.', 9000);
  }
  if (window.AtlasBridge) native.call('openUrl', { url }).catch(() => window.open(url, '_blank', 'noopener'));
  else window.open(url, '_blank', 'noopener');
}

function adoptUrl(key, g, a) {
  const head = key.startsWith('new:') ? `new-game: ${g.title}` : `game: ${g.id}`;
  const json = JSON.stringify(a.result);
  const withJson = `${head}\n\nErgebnis der Sofortanalyse vom ${fmtDate(a.at)} (${aiModel()}), wird ohne neue KI-Anfrage übernommen:\n\n\`\`\`json\n${json}\n\`\`\``;
  // GitHub limits URL length; very large results are researched again by the workflow instead
  return issueUrl(`Recherche: ${g.title}`, encodeURIComponent(withJson).length < 7000 ? withJson : `${head}${a.focus ? `\nversion: ${a.focus}` : ''}`);
}

function analysisPanel(key) {
  const a = analyses.get(key);
  if (!a) return `<div id="analysis" data-key="${esc(key)}"></div>`;
  const g = key.startsWith('new:') ? { id: null, title: key.slice(4), platforms: [], versions: [], routes: [], mods: [] } : DB.byId.get(key);
  const focusName = a.focus ? versionsOf(g).find((v) => v.id === a.focus)?.name : null;
  let body;
  if (a.status === 'nokey') {
    body = `<p>Für die Sofortanalyse braucht Atlas einmalig deinen OpenAI-API-Schlüssel. Er wird nur auf diesem Gerät gespeichert.</p>
      <div class="row"><a class="btn primary" href="#/info">Schlüssel eintragen</a>
      ${DB.meta.repo ? `<a class="btn" href="${esc(issueUrl(`Recherche: ${g.title}`, key.startsWith('new:') ? `new-game: ${g.title}` : `game: ${g.id}${a.focus ? `\nversion: ${a.focus}` : ''}`))}" target="_blank" rel="noopener">Stattdessen über GitHub recherchieren (3–5 Min.)</a>` : ''}</div>`;
  } else if (a.status === 'running') {
    body = `<div class="row"><span class="spinner"></span><span>Recherchiere${focusName ? ` „${esc(focusName)}“` : ''} mit Websuche … <b id="an-elapsed">0 s</b> (meist 1–3 Minuten)</span>
      <button class="btn" data-an-cancel="${esc(key)}">Abbrechen</button></div>`;
  } else if (a.status === 'error' || a.status === 'cancelled') {
    body = `<p class="warn">${a.status === 'cancelled' ? 'Abgebrochen.' : 'Fehler: ' + esc(a.error)}</p>
      <div class="row"><button class="btn" data-analyze="${esc(key)}" data-focus="${esc(a.focus || '')}">Erneut versuchen</button></div>`;
  } else {
    const r = a.result;
    const knownV = new Set(versionsOf(g).flatMap((v) => [v.id, norm(v.name)]));
    const vName = (k) => (r.versions.find((v) => v.key === k)?.name) || versionsOf(g).find((v) => v.id === k)?.name || k;
    const src = (u) => u ? `<a class="link" href="${esc(u)}" target="_blank" rel="noopener">Quelle ${icon('ext')}</a>` : '';
    body = `${r.summary ? `<p>${esc(r.summary)}</p>` : ''}
      ${r.versions.length ? `<h4>Fassungen</h4><div class="an-list">${r.versions.map((v) => `<div class="an-item">
        <div class="row"><b>${esc(v.name)}</b>${knownV.has(v.key) || knownV.has(norm(v.name)) ? '<span class="tag">bekannt</span>' : '<span class="tag v-ai-unverified">neu</span>'}
        <span class="faint">${esc(label('versionTypes', v.type))}${v.year ? ' · ' + v.year : ''} · ${esc(v.platforms.join(', '))}</span></div>
        ${v.note ? `<div class="muted">${esc(v.note)}</div>` : ''}${src(v.sourceUrl)}</div>`).join('')}</div>` : ''}
      ${r.routes.length ? `<h4>Spielwege</h4><div class="an-list">${r.routes.map((w) => `<div class="an-item">
        <div class="row"><b>${esc(w.name)}</b><span class="faint">${esc(vName(w.versionKey))} · ${esc(label('kinds', w.kind))}</span>
        ${(w.features || []).map((f) => `<span class="tag${f === 'dual-screen' ? ' dual' : ''}">${esc(label('features', f))}</span>`).join('')}</div>
        ${w.benefit ? `<div>${esc(w.benefit)}</div>` : ''}${w.caveat ? `<div class="warn">${esc(w.caveat)}</div>` : ''}
        ${(w.requires || []).length ? `<div class="faint">Du brauchst: ${esc(w.requires.join(' · '))}</div>` : ''}
        ${(w.screenshots || []).length ? `<div class="an-shots">${w.screenshots.map((s) => `<img src="${esc(s.url)}" alt="${esc(s.caption)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`).join('')}</div>` : ''}
        ${(w.reports || []).map((rep) => `<div class="faint">${icon('gamepad')} ${esc(rep.device)}: ${esc(rep.summary)} <a class="link" href="${esc(rep.url)}" target="_blank" rel="noopener">Bericht</a></div>`).join('')}
        <div class="row">${w.projectUrl ? `<a class="link" href="${esc(w.projectUrl)}" target="_blank" rel="noopener">${esc(w.projectName || 'Projekt')} ${icon('ext')}</a>` : ''}${src(w.sourceUrl)}</div></div>`).join('')}</div>` : ''}
      ${r.mods.length ? `<h4>Mods</h4><div class="an-list">${r.mods.map((m) => `<div class="an-item"><div class="row"><b>${esc(m.name)}</b>
        <span class="tag">${esc(label('modCategories', m.category))}</span><span class="faint">${esc((m.versionKeys || []).map(vName).join(', '))}</span></div>
        ${m.description ? `<div class="muted">${esc(m.description)}</div>` : ''}<a class="link" href="${esc(m.url)}" target="_blank" rel="noopener">Zum Mod ${icon('ext')}</a></div>`).join('')}</div>` : ''}
      ${!r.versions.length && !r.routes.length && !r.mods.length ? '<p class="muted">Nichts Neues gefunden.</p>' : ''}
      <details class="settings"><summary>${a.sources.length} Quellen der Websuche</summary><ul>${a.sources.slice(0, 40).map((u) => `<li><a class="link" href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, '').slice(0, 80))}</a></li>`).join('')}</ul></details>
      <div class="row">${DB.meta.repo ? `<a class="btn primary" href="${esc(adoptUrl(key, g, a))}" target="_blank" rel="noopener">${icon('check')}Dauerhaft in Atlas übernehmen</a>` : ''}
        <button class="btn" data-analyze="${esc(key)}" data-focus="${esc(a.focus || '')}">Neu analysieren</button></div>
      <p class="faint">Nicht gespeichert, bis du übernimmst. Übernommene Einträge erscheinen als „KI-Fund, ungeprüft“ nach etwa 2–3 Minuten.</p>`;
  }
  return `<section class="section analysis" id="analysis" data-key="${esc(key)}"><div class="section-head"><h2>${icon('ai')} Sofortanalyse${focusName ? `: ${esc(focusName)}` : ''}</h2>
    <span class="faint">KI mit Websuche · ${esc(aiModel())} · ungeprüft</span></div>${body}</section>`;
}

function viewNewGame(title) {
  const key = 'new:' + title;
  return `<a class="btn back" href="#/" data-back>${icon('back')}Zurück</a>
    <h1>${esc(title)}</h1><p class="muted">Dieses Spiel ist noch nicht in Atlas. Die Sofortanalyse sucht Fassungen und Wege, ohne etwas zu speichern; übernehmen kannst du das Ergebnis danach mit einem Klick.</p>
    <div class="row section"><button class="btn primary" data-analyze="${esc(key)}">${icon('ai')}Sofortanalyse starten</button>
    ${DB.meta.repo ? `<a class="btn" href="${esc(issueUrl(`Recherche: ${title}`, `new-game: ${title}`))}" target="_blank" rel="noopener">Direkt aufnehmen lassen (GitHub)</a>
      <a class="btn" href="${esc(issueUrl(`Reihe: ${title}`, `franchise: ${title}`))}" target="_blank" rel="noopener">${icon('layers')}Als ganze Reihe erfassen</a>` : ''}</div>
    ${analysisPanel(key)}`;
}

/* ---------- dual screen overview, per-game dual comparison, research status ---------- */
const isDual = (w) => w.features.includes('dual-screen') || w.features.includes('two-screens');
const dualLabel = (w) => label('dualScreenTypes', w.r?.dualScreenType || (w.features.includes('two-screens') ? 'native' : 'integrated'));

const isDualRoute = (r) => (r.features || []).some((f) => f === 'dual-screen' || f === 'two-screens');

/* How well explored is a game? Transparent checklist – each point says what is missing and what helps. */
function completeness(g) {
  const orig = g.screenshots.filter((s) => s.caption !== 'Titelbild').length;
  const routes = g.routes;
  const shotRatio = routes.length ? routes.filter((r) => (r.screenshots || []).length).length / routes.length : 0;
  const dual = routes.filter(isDualRoute);
  const dualShots = dual.filter((r) => (r.screenshots || []).length).length;
  const vers = g.versions || [];
  const researched = DB.researched?.[g.id];
  const reports = vers.some((v) => (v.reports || []).length) || routes.some((r) => (r.reports || []).length);
  const items = [
    (() => { const ri = researchInfo(g);
      return { ok: ri.state === 'fresh' || ri.state === 'aging', part: ri.state === 'news' || ri.state === 'old' ? 0.6 : 0, w: 3, fix: researched ? 'update' : 'research',
        label: !researched ? (g.wikidata ? 'Nur Basisprofil (Wikidata), keine Tiefenrecherche' : 'Noch nicht tiefenrecherchiert')
          : `Tiefenrecherche ${fmtDate(researched)}${ri.events.length ? ` – seitdem ${ri.events.length} Neuigkeit(en)` : ri.state === 'old' ? ' – älter als 6 Monate' : ''}` }; })(),
    { ok: !!g.cover, w: 1, label: g.cover ? 'Cover' : 'Kein Cover', fix: 'images' },
    { ok: orig >= 3, part: Math.min(orig, 3) / 3, w: 2, label: `${orig} ${orig === 1 ? 'Originalbild' : 'Originalbilder'}`, fix: 'images' },
    { ok: vers.length > 1 && vers.filter((v) => v.year).length >= vers.length / 2, part: vers.length > 1 ? 0.5 : 0, w: 1,
      label: `${vers.length} ${vers.length === 1 ? 'Fassung' : 'Fassungen'}${vers.filter((v) => v.year).length ? `, ${vers.filter((v) => v.year).length} mit Jahr` : ''}`, fix: 'research' },
    { ok: routes.length > 0, w: 2, label: routes.length ? `${routes.length} ${routes.length === 1 ? 'Spielweg' : 'Spielwege'}` : 'Keine eigenen Spielwege (nur allgemeine Emulatoren)', fix: 'research' },
  ];
  if (routes.length) items.push({ ok: shotRatio >= 0.8, part: shotRatio, w: 2, label: `Spielwege mit Bild ${routes.filter((r) => (r.screenshots || []).length).length}/${routes.length}`, fix: 'images' });
  if (dual.length) items.push({ ok: dualShots === dual.length, part: dualShots / dual.length, w: 2, label: `Dual Screen mit Bild ${dualShots}/${dual.length}`, fix: 'images' });
  items.push({ ok: reports, w: 1, label: reports ? 'Erfahrungsberichte vorhanden' : 'Keine Erfahrungsberichte', fix: null });
  const total = items.reduce((n, i) => n + i.w, 0);
  const got = items.reduce((n, i) => n + i.w * (i.ok ? 1 : i.part || 0), 0);
  const pct = Math.round((got / total) * 100);
  return { pct, items, level: pct >= 75 ? 'gut' : pct >= 45 ? 'teils' : 'wenig' };
}
const LEVEL_LABEL = { gut: 'Gut erkundet', teils: 'Teilweise erkundet', wenig: 'Wenig erkundet' };

function dataPanel(g) {
  const c = completeness(g);
  const req = pendingFor(g.id);
  const needImages = c.items.some((i) => !i.ok && i.fix === 'images');
  const needResearch = c.items.some((i) => !i.ok && i.fix === 'research');
  const needUpdate = c.items.some((i) => !i.ok && i.fix === 'update');
  const imgReq = DB.imageRequests[g.id];
  const btn = (kind, primary) => !DB.meta.repo ? '' : kind === 'images'
    ? `<a class="btn small${primary ? ' primary' : ''}" href="${esc(issueUrl('Bilder: ' + g.title, 'images: ' + g.id))}" target="_blank" rel="noopener" title="Cover, Originalbilder und Bilder für jeden Spielweg (Dual Screen zuerst)">${icon('image')}Bilder suchen</a>`
    : kind === 'update'
      ? `<a class="btn small${primary ? ' primary' : ''}" href="${esc(issueUrl('Aktualisieren: ' + g.title, 'update: ' + g.id))}" target="_blank" rel="noopener" title="Sucht nur, was sich seit der letzten Tiefenrecherche geändert hat – günstiger als eine neue Tiefenrecherche">${icon('spark')}Aktualisieren</a>`
      : `<a class="btn small${primary ? ' primary' : ''}" href="${esc(issueUrl('Recherche: ' + g.title, 'game: ' + g.id + '\n\nWas soll recherchiert werden? (optional)'))}" target="_blank" rel="noopener" title="Komplett neu recherchieren: alle Fassungen, Spielwege, Emulatoren, Mods und Berichte">${icon('spark')}${DB.researched?.[g.id] ? 'Neue Tiefenrecherche' : 'Tiefenrecherche anfordern'}</a>`;
  const stage = typeof dualRole === 'function' && dualRole() === 'stage';   // small stage screen: keep it folded
  return `<details class="panel section datapanel lvl-${c.level}"${c.level !== 'gut' && !stage ? ' open' : ''}>
    <summary><span class="meter"><span>Datenstand: <b>${LEVEL_LABEL[c.level]}</b></span><b>${c.pct} %</b><i style="--v:${c.pct}%"></i></span></summary>
    <ul class="checklist">${c.items.map((i) => `<li class="${i.ok ? 'ok' : i.part ? 'part' : 'miss'}">${icon(i.ok ? 'check' : 'alert')}${esc(i.label)}</li>`).join('')}</ul>
    <p class="req-run" data-req-game="${esc(g.id)}"${req ? '' : ' hidden'}>${icon('spark')} <span>${esc(req?.label || '')}</span></p>
    ${DB.meta.repo ? `<label class="field req-note">Was fehlt dir? <span class="faint">(optional – geht als Auftrag mit, z. B. „DroidDeck und GameHub fehlen“)</span><input id="req-note" type="text" autocomplete="off" placeholder="z. B. weitere Emulatoren, eine bestimmte Fassung, Dual-Screen-Mods"></label>` : ''}
    <div class="row">${DB.researched?.[g.id] ? btn('update', needUpdate) + btn('research', false) : btn('research', needResearch && !needImages)}${btn('images', needImages)}
      ${DB.meta.repo ? `<button class="btn small" data-addimage="${esc(g.id)}" data-title="${esc(g.title)}" title="Link zu einem Bild, Video oder Artikel einfügen">${icon('ext')}Bild-Link einfügen</button>` : ''}
      ${imgReq ? `<span class="faint">Bilder zuletzt gesucht ${fmtDate(imgReq)}</span>` : ''}</div>
    <p class="faint">${researchWhere()} Tiefenrecherche = alles neu: Fassungen, Spielwege, Emulatoren, Mods und Berichte (3–5 Min.). Aktualisieren = nur Änderungen seit der letzten Recherche (neue Versionen, eingestellte Projekte, neue Wege) – günstiger, sucht aber nicht gezielt nach Fehlendem. Bilder suchen = Cover, Originalbilder und Bilder je Spielweg aus Wikipedia, Steam, Google Play, YouTube, Reddit und Projektseiten (2–4 Min.); die KI-Bildprüfung sortiert danach Unpassendes aus.</p>
  </details>`;
}

function wayImageButton(g, r) {
  if (!DB.meta.repo) return '';
  const n = (r.screenshots || []).length;
  const dual = isDualRoute(r);
  if (n >= 4 && !dual) return '';
  const label = n ? (dual ? 'Mehr Dual-Screen-Bilder suchen' : 'Mehr Bilder suchen') : (dual ? 'Wie sieht das aus? Dual-Screen-Bilder suchen' : 'Bilder für diesen Weg suchen');
  return `<div class="row"><a class="btn small${n ? '' : ' primary'}" href="${esc(issueUrl(`Bilder: ${g.title} – ${r.name}`, `images: ${g.id}/${r.id}`))}" target="_blank" rel="noopener"
    title="Sucht Videos, Beiträge und Projektseiten, die genau diesen Weg zeigen">${icon('image')}${label}</a>
    <button class="btn small" data-addimage="${esc(g.id)}/${esc(r.id)}" data-title="${esc(g.title + ' – ' + r.name)}" title="Link zu einem Reddit-Beitrag, Video oder Bild einfügen">${icon('ext')}Bild-Link einfügen</button>
    ${n ? '' : '<span class="faint">Noch kein Bild für diesen Weg.</span>'}</div>`;
}

/* ---------- requests (GitHub issues) the user started from this device: live status ---------- */
const REQ_KEY = 'requests';
const requests = () => store.get(REQ_KEY, []).filter((r) => Date.now() - r.at < (r.state === 'abo' ? 5 * 86400e3 : 3 * 3600e3));
function pendingFor(gameId) {
  const r = requests().find((x) => x.game === gameId && x.state !== 'done');
  if (!r) return null;
  const min = Math.max(1, Math.round((Date.now() - r.at) / 60000));
  return { ...r, label: r.state === 'abo' ? `${r.title}: wartet auf die Abo-Aufgabe (${DB.researchMode?.aboSchedule || 'nächster Pflegelauf'})` : r.state === 'open' ? `${r.title} läuft seit ${min} Min. (${DB.researchMode?.backend === 'abo' ? 'Abo' : 'API'}) …` : r.state === 'closed' ? `${r.title} ist fertig – die App wird gerade aktualisiert …` : `${r.title}: warte, bis das Issue auf GitHub abgeschickt ist …` };
}
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('[data-addimage]');
  if (!b) return;
  e.preventDefault();
  const url = (prompt('Link einfügen: Reddit-Beitrag, YouTube-Video, Artikel oder direkt die Bildadresse', '') || '').trim();
  if (!/^https:\/\//.test(url)) { if (url) toast('Bitte einen Link mit https:// einfügen.'); return; }
  const title = `Bild: ${b.dataset.title}`;
  const body = `add-image: ${b.dataset.addimage}\nurl: ${url}`;
  const list = requests().filter((r) => r.title !== title);
  list.unshift({ title, game: b.dataset.addimage.split('/')[0], at: Date.now(), state: 'new' });
  store.set(REQ_KEY, list.slice(0, 12));
  if (store.get('githubToken', '')) sendIssue(title, body).then(() => toast('Bild-Link gesendet – Atlas holt das Bild in wenigen Minuten.')).catch((err) => toast(esc(err.message)));
  else window.open(issueUrl(title, body), '_blank', 'noopener');
  scheduleRequestPoll(20000);
});
/* Every request button is a GitHub "new issue" link. With a GitHub key (Info) Atlas sends it right away; without one
   GitHub opens with everything filled in and you tap "Create". */
async function sendIssue(title, body) {
  const res = await fetch(`https://api.github.com/repos/${DB.meta.repo}/issues`, {
    method: 'POST', headers: { Authorization: 'Bearer ' + store.get('githubToken', ''), Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, body, labels: ['recherche'] }) });
  if (!res.ok) throw new Error('GitHub antwortet ' + res.status + (res.status === 401 || res.status === 403 ? ' – Schlüssel prüfen (Issues: Lesen und Schreiben)' : ''));
  return res.json();
}
document.addEventListener('click', async (e) => {
  const a = e.target.closest?.('a[href*="/issues/new?"]');
  if (!a) return;
  const u = new URL(a.href);
  const title = u.searchParams.get('title');
  let body = u.searchParams.get('body') || '';
  const note = document.getElementById('req-note')?.value.trim();
  if (note && /^(game|update):/m.test(body)) body = body.replace(/\n*Was soll recherchiert werden\? \(optional\)\s*$/, '') + `\n\nWas soll recherchiert werden? (optional)\n${note}`;
  const m = /^(?:game|images|new-game|update):\s*([^\n/]+)/m.exec(body);
  const list = requests().filter((r) => r.title !== title);
  list.unshift({ title, game: m ? m[1].trim() : null, at: Date.now(), state: 'new' });
  store.set(REQ_KEY, list.slice(0, 12));
  if (store.get('githubToken', '')) {
    e.preventDefault();
    try {
      await sendIssue(title, body);
      list[0].state = 'open';
      store.set(REQ_KEY, list.slice(0, 12));
      toast(`Anfrage gesendet: ${esc(title)}. ${esc(researchWhere(true))}`);
    } catch (err) { toast(esc(err.message)); }
  } else {
    e.preventDefault();
    openIssue(title, body);
    toast('Anfrage vorbereitet – bitte auf GitHub „Create“ tippen. Ohne Umweg geht es mit einem GitHub-Schlüssel (Info).');
  }
  scheduleRequestPoll(20000);
});

/* Where does research run right now? (data/research.json, docs/RECHERCHE.md) */
function researchWhere(short) {
  const m = DB.researchMode || {};
  const apiDown = m.status && m.status.ok === false;
  if (m.backend === 'abo') return short ? `Erledigt die Abo-Aufgabe (${m.aboSchedule || 'beim nächsten Pflegelauf'}).` : `Recherchen laufen gerade über dein Claude-Abo: die Pflegeaufgabe erledigt sie ${m.aboSchedule || 'beim nächsten Lauf'}.`;
  if (apiDown) return short ? `API gerade nicht nutzbar (${m.status.reason}) – geht an die Abo-Aufgabe.` : `Die API ist gerade nicht nutzbar (${m.status.reason}); Anfragen gehen automatisch an die Abo-Aufgabe (${m.aboSchedule || 'nächster Pflegelauf'}).`;
  return short ? 'Läuft gleich über die API (3–5 Min.).' : 'Recherchen laufen sofort über die API (OpenAI); ist sie nicht nutzbar, übernimmt die Abo-Aufgabe.';
}
function researchPanel() {
  if (!DB.meta.repo) return '';
  const m = DB.researchMode || {};
  const abo = m.backend === 'abo';
  const waiting = (reqCache || []).filter((i) => i.state === 'open' && (i.labels || []).some((l) => l.name === 'abo'));
  const months = Object.keys(DB.usage || {}).sort().reverse();
  const est = months.length ? DB.usage[months[0]].estimate : null;
  return `<div class="panel"><h3>${icon('spark')} Wo wird recherchiert?</h3>
    <div class="chips"><button class="chip" data-backend="api" aria-pressed="${!abo}">API (OpenAI)</button><button class="chip" data-backend="abo" aria-pressed="${abo}">Abo (Claude-Aufgabe)</button></div>
    <ul class="checklist">
      <li class="${abo ? 'part' : m.status?.ok === false ? 'miss' : 'ok'}">${icon(abo || m.status?.ok === false ? 'alert' : 'check')}${esc(researchWhere())}</li>
      <li class="ok">${icon('info')}Abo-Aufgabe: ${esc(m.aboSchedule || 'geplant')} – erledigt offene Anfragen mit Label „abo“, prüft KI-Funde und pflegt Daten.</li>
      ${est != null ? `<li class="ok">${icon('info')}API-Verbrauch ${esc(months[0])}: ca. ${est.toLocaleString('de-DE', { minimumFractionDigits: 2 })}</li>` : ''}
      ${waiting.length ? `<li class="part">${icon('alert')}${waiting.length} ${waiting.length === 1 ? 'Anfrage wartet' : 'Anfragen warten'} auf die Abo-Aufgabe: ${waiting.slice(0, 4).map((i) => esc(i.title)).join(', ')}</li>` : ''}
    </ul>
    <label class="field">GitHub-Schlüssel ${ghToken() ? '<span class="tag v-documented">gespeichert</span>' : ''}<input id="gh-token" type="password" autocomplete="off" placeholder="github_pat_…" value="${esc(ghToken())}"></label>
    <p class="faint">Damit gehen Anfragen, Bilder-Links und Rückmeldungen des Geräts direkt an Atlas – ohne Umweg über die GitHub-Seite. Fein abgestufter Schlüssel nur für ${esc(DB.meta.repo)}, Berechtigung „Issues: Lesen und Schreiben“. Bleibt auf diesem Gerät und geht nur an api.github.com.</p>
    <div class="row"><button class="btn primary" id="gh-save">Speichern</button>${ghToken() ? '<button class="btn" id="gh-clear">Löschen</button>' : ''}</div>
    <p class="faint">Kostenlos und ohne KI laufen immer: Watcher, Wikidata, EmuReady, Bilder aus libretro/Steam/Wikipedia und alle Rückmeldungen vom Gerät. Umschalten schickt eine kurze Anfrage; der neue Modus gilt nach etwa einer Minute.</p></div>`;
}
document.addEventListener('click', async (e) => {
  const b = e.target.closest?.('[data-backend]');
  if (!b || b.getAttribute('aria-pressed') === 'true') return;
  const to = b.dataset.backend;
  const title = `Recherche-Modus: ${to === 'abo' ? 'Abo' : 'API'}`;
  const body = `research-backend: ${to}`;
  if (store.get('githubToken', '')) {
    try { await sendIssue(title, body); toast(`Umgeschaltet auf ${to === 'abo' ? 'Abo' : 'API'} – gilt in etwa einer Minute.`); } catch (err) { toast(esc(err.message)); }
  } else window.open(issueUrl(title, body), '_blank', 'noopener');
});
let reqTimer = null, reqEtag = null, reqCache = null;
function scheduleRequestPoll(ms = 75000) {
  clearTimeout(reqTimer);
  if (!DB.meta.repo || !requests().some((r) => r.state !== 'done')) { renderRequestPill(); return; }
  reqTimer = setTimeout(pollRequests, ms);
  renderRequestPill();
}
async function pollRequests() {
  if (document.hidden) { scheduleRequestPoll(); return; }
  try {
    // ETag: unchanged answers (304) do not count against GitHub's limit for anonymous requests
    const res = await fetch(`https://api.github.com/repos/${DB.meta.repo}/issues?labels=recherche&state=all&sort=created&direction=desc&per_page=30`,
      { headers: reqEtag ? { 'If-None-Match': reqEtag } : {} });
    if (res.status === 200) { reqEtag = res.headers.get('ETag'); reqCache = await res.json(); }
    const issues = reqCache || [];
    const list = requests();
    let finished = false;
    for (const r of list) {
      if (r.state === 'done') continue;
      const is = issues.find((i) => i.title === r.title && new Date(i.created_at).getTime() >= r.at - 120000);
      if (!is) { if (Date.now() - r.at > 20 * 60000) r.state = 'done'; continue; }     // never submitted
      r.url = is.html_url;
      if (is.state === 'open') r.state = (is.labels || []).some((l) => l.name === 'abo') ? 'abo' : 'open';
      else if (r.state !== 'closed') { r.state = 'closed'; r.closedAt = Date.now(); finished = true; }
      if (r.state === 'closed' && Date.now() - (r.closedAt || 0) > 8 * 60000) r.state = 'done';
    }
    store.set(REQ_KEY, list);
    if (list.some((r) => r.state === 'closed')) await waitForData(finished);
  } catch { /* offline – try again later */ }
  scheduleRequestPoll(requests().some((r) => r.state === 'closed') ? 25000 : 75000);
}
async function waitForData(justFinished) {
  try {
    const v = await (await fetch('version.json', { cache: 'no-store' })).json();
    if (state.version && v.version !== state.version) {
      const list = requests().map((r) => (r.state === 'closed' ? { ...r, state: 'done' } : r));
      store.set(REQ_KEY, list);
      toast(`Deine Anfrage ist fertig – neue Daten sind da. <button class="btn primary" onclick="location.reload()">Jetzt laden</button>`, 0);
    } else if (justFinished) toast('Anfrage fertig – die App wird gerade neu veröffentlicht (etwa 1 Minute).');
  } catch { /* ignore */ }
}
function renderRequestPill() {
  for (const el of document.querySelectorAll('[data-req-game]')) {       // status line in the open game page
    const req = pendingFor(el.dataset.reqGame);
    el.hidden = !req;
    if (req) el.querySelector('span').textContent = req.label;
  }
  let pill = document.getElementById('req-pill');
  const open = requests().filter((r) => r.state !== 'done');
  if (!open.length) { pill?.remove(); return; }
  if (!pill) { pill = document.createElement('div'); pill.id = 'req-pill'; document.body.appendChild(pill); }
  const word = { new: 'wartet auf Abschicken', open: 'läuft', abo: 'wartet auf die Abo-Aufgabe', closed: 'fertig, wird veröffentlicht' };
  pill.innerHTML = `${icon('spark')}<span>${open.length === 1 ? esc(open[0].title) + ' – ' + word[open[0].state] : `${open.length} Anfragen: ` + open.map((r) => word[r.state]).join(', ')}</span>`
    + (open[0].url ? `<a class="link" href="${esc(open[0].url)}" target="_blank" rel="noopener">Details</a>` : '');
}

/* ---------- Reddit-Quelle: Bilder aus Reddit-Beiträgen, geladen vom Gerät (docs/REDDIT.md) ----------
   Reddit beantwortet seit Mai 2026 nur noch angemeldete Abrufe; GitHub Actions sind gesperrt. Deshalb holt der Handheld
   die Beiträge der Abholliste (DB.reddit, vom Build erzeugt) selbst, zeigt die Bilder sofort und meldet sie per Issue
   („reddit-images:“ + JSON) zurück; die Action „KI-Recherche“ übernimmt sie ohne KI, die Bildprüfung folgt.
   Abrufwege, in dieser Reihenfolge: 1. Atlas-App (native „redditFetch“, mit Reddit-Anmeldung in der App)
   2. direkt aus dem Browser (klappt nur, wenn Reddit dem Browser antwortet – wird getestet und gemerkt). */
const RD_IMG_HOST = /^https:\/\/(i\.redd\.it|preview\.redd\.it|external-preview\.redd\.it|i\.imgur\.com)\//;
const rdState = { running: false, last: null };
function redditPostId(url) {
  try {
    const u = new URL(url);
    if (u.hostname === 'redd.it') return (/^\/([a-z0-9]{4,12})\/?$/i.exec(u.pathname) || [])[1]?.toLowerCase() || null;
    if (!/(^|\.)reddit\.com$/.test(u.hostname)) return null;
    return (/^\/(?:r\/[A-Za-z0-9_]+\/)?comments\/([a-z0-9]{4,12})(?:\/|$)/i.exec(u.pathname) || [])[1]?.toLowerCase() || null;
  } catch { return null; }
}
const redditMediaId = (url) => (/^https:\/\/(?:i|preview)\.redd\.it\/(?:[^/?]*-v0-)?([a-z0-9]{8,20})\.(?:jpe?g|png|webp|gif)/i.exec(url || '') || [])[1]?.toLowerCase() || null;
/* verkleinerte Vorschau (preview.redd.it …?width=640) → Original auf i.redd.it; die Vorschau bleibt Ersatz (data-fb) */
const fullSrc = (url) => {
  const m = /^https:\/\/preview\.redd\.it\/(?:[^/?]*-v0-)?([a-z0-9]{8,20})\.(jpe?g|png|gif)(?:\?|$)/i.exec(url || '');
  return m ? `https://i.redd.it/${m[1]}.${m[2]}` : url;
};
window.atlasImgErr = (img) => {
  if (img.dataset.fb) { img.src = img.dataset.fb; delete img.dataset.fb; } else img.closest('.shot')?.remove();
};

/** Post-JSON von Reddit → {title, author, gone, images:[{url, fallback, w, h}]} (Galerie in Originalreihenfolge). */
function redditParse(listing) {
  let p = listing?.[0]?.data?.children?.[0]?.data;
  if (!p) return null;
  const gone = !!p.removed_by_category || p.author === '[deleted]';
  if (p.crosspost_parent_list?.[0]) p = { ...p.crosspost_parent_list[0], title: p.title, author: p.author };
  const out = [];
  const add = (url, w, h, fallback) => {
    url = String(url || '').replace(/&amp;/g, '&');
    fallback = fallback ? String(fallback).replace(/&amp;/g, '&') : null;
    if (!RD_IMG_HOST.test(url) || out.some((o) => o.url === url || (redditMediaId(url) && redditMediaId(o.url) === redditMediaId(url)))) return;
    out.push({ url, fallback: fallback && fallback !== url ? fallback : null, w: w || null, h: h || null });
  };
  const meta = p.media_metadata || {};
  const order = p.gallery_data?.items?.map((i) => i.media_id) || Object.keys(meta);
  for (const id of order) {
    const m = meta[id];
    if (!m || (m.status && m.status !== 'valid') || (m.e && m.e !== 'Image')) continue;
    const ext = { 'image/jpg': 'jpg', 'image/jpeg': 'jpg', 'image/png': 'png', 'image/gif': 'gif' }[m.m];
    add(ext ? `https://i.redd.it/${id}.${ext}` : m.s?.u, m.s?.x, m.s?.y, m.s?.u);
  }
  const src = p.preview?.images?.[0]?.source;
  if (/^https:\/\/i\.redd\.it\//.test(p.url_overridden_by_dest || '')) add(p.url_overridden_by_dest, src?.width, src?.height, src?.url);
  else if (/^https:\/\/i\.imgur\.com\/\w+\.(jpe?g|png)$/i.test(p.url_overridden_by_dest || '')) add(p.url_overridden_by_dest, src?.width, src?.height);
  if (!out.length && src?.url && (p.is_video || p.post_hint === 'image' || p.post_hint === 'hosted:video')) add(src.url, src.width, src.height);
  return { title: String(p.title || '').slice(0, 120), author: p.author && p.author !== '[deleted]' ? p.author : '', gone, images: out.slice(0, 10) };
}

/* In der Atlas-App liest ein unsichtbares Browserfenster den Beitrag mit deiner Reddit-Anmeldung (native „redditFetch“). */
const hasNative = () => native.available;
async function nativeFetch(url) {
  const res = await native.call('redditFetch', { url }, 40000);
  if (res.status >= 200 && res.status < 300) { try { return JSON.parse(res.body); } catch { throw new Error('Antwort ist kein JSON'); } }
  throw Object.assign(new Error(res.status ? 'HTTP ' + res.status : 'Zeitüberschreitung'), { status: res.status });
}

const PROBE_TTL = 24 * 3600e3;
const redditProbe = () => store.get('redditProbe', null);   // {mode: 'direct'|'direct-cred'|'blocked', at, detail}
function redditMethod() {
  if (hasNative()) return store.get('redditLogin', false) ? 'native' : 'native-login';
  const p = redditProbe();
  if (!p) return 'untested';
  if (p.mode === 'blocked' && Date.now() - p.at > PROBE_TTL) return 'untested';
  return p.mode;
}
const METHOD_LABEL = {
  native: 'Atlas-App mit deiner Reddit-Anmeldung', 'native-login': 'Atlas-App – noch nicht bei Reddit angemeldet', direct: 'direkt aus dem Browser', 'direct-cred': 'direkt aus dem Browser (mit Reddit-Anmeldung)',
  blocked: 'aus dem Browser gesperrt', untested: 'noch nicht getestet',
};

/** Einen Beitrag laden. Ergebnis: Eintrag wie im Cache {at, status: ok|no-images|gone|failed, title, author, images, method}. */
async function redditGet(post) {
  const jsonUrl = `https://www.reddit.com/comments/${post.id}/.json?raw_json=1&limit=1`;
  let data = null, method = redditMethod(), detail = '';
  if (method === 'native') {
    try { data = await nativeFetch(jsonUrl); } catch (e) {
      if (e.status === 404) return { at: Date.now(), status: 'gone', method };
      if (e.status === 403 || e.status === 401) { store.set('redditLogin', false); return null; }   // Anmeldung fehlt oder abgelaufen: nicht als Fehlversuch melden
      return { at: Date.now(), status: 'failed', method, detail: e.message };
    }
  } else {
    if (method === 'blocked') return null;
    const tries = method === 'direct-cred' ? ['include'] : method === 'direct' ? ['omit'] : ['omit', 'include'];
    for (const cred of tries) {
      try {
        const res = await fetch(jsonUrl, { credentials: cred, cache: 'no-store', referrerPolicy: 'no-referrer' });
        if (res.ok) { data = await res.json(); method = cred === 'include' ? 'direct-cred' : 'direct'; break; }
        if (res.status === 404) return { at: Date.now(), status: 'gone', method: cred === 'include' ? 'direct-cred' : 'direct' };
        detail = 'Reddit antwortet ' + res.status;
      } catch { detail = navigator.onLine ? 'Reddit erlaubt dem Browser den Abruf nicht (CORS/Sperre)' : 'offline'; }
    }
    if (!data) {
      if (navigator.onLine) store.set('redditProbe', { mode: 'blocked', at: Date.now(), detail });
      return null;
    }
    store.set('redditProbe', { mode: method, at: Date.now(), detail: '' });
  }
  const p = redditParse(data);
  if (!p) return { at: Date.now(), status: 'failed', method, detail: 'Unbekanntes Antwortformat' };
  if (p.gone && !p.images.length) return { at: Date.now(), status: 'gone', method };
  const images = [];
  for (const im of p.images) {            // nur Bilder melden, die auf dem Gerät wirklich laden (mit echter Größe)
    const ok = await imageSize(im.url) || (im.fallback && await imageSize(im.fallback));
    if (ok) images.push({ url: ok.url, w: ok.w, h: ok.h });
  }
  return { at: Date.now(), status: images.length ? 'ok' : 'no-images', method, title: p.title, author: p.author, images };
}
function imageSize(url) {
  return new Promise((resolve) => {
    const img = new Image();
    const t = setTimeout(() => resolve(null), 12000);
    img.referrerPolicy = 'no-referrer';
    img.onload = () => { clearTimeout(t); resolve(img.naturalWidth >= 200 ? { url, w: img.naturalWidth, h: img.naturalHeight } : null); };
    img.onerror = () => { clearTimeout(t); resolve(null); };
    img.src = url;
  });
}

const rdCache = () => store.get('redditCache', {});
function rdRemember(id, entry) {
  const c = rdCache();
  c[id] = entry;
  const keys = Object.keys(c).sort((a, b) => c[b].at - c[a].at);
  store.set('redditCache', Object.fromEntries(keys.slice(0, 400).map((k) => [k, c[k]])));
  if (entry.status !== 'failed' || (entry.fails || 0) >= 2) {   // einzelne Aussetzer nicht melden
    const post = DB.reddit.find((p) => p.id === id);
    const out = store.get('redditOutbox', []).filter((o) => o.id !== id);
    out.push({ id, post: post?.url, status: entry.status, title: entry.title, author: entry.author, images: entry.images || [] });
    store.set('redditOutbox', out);
  }
}
const rdOutbox = () => store.get('redditOutbox', []).filter((o) => DB.reddit.some((p) => p.id === o.id));
const rdDue = (p) => { const c = rdCache()[p.id]; return !c || (c.status === 'failed' && Date.now() - c.at > 6 * 3600e3); };

function rdHolder(target) {
  const [gid, rest] = target.split('/');
  const g = DB.byId.get(gid);
  if (!g || !rest) return g;
  return rest.startsWith('mod:') ? g.mods.find((m) => m.id === rest.slice(4)) : g.routes.find((r) => r.id === rest);
}
/** Geladene, noch nicht übernommene Reddit-Bilder in die Galerien einblenden (nur im Speicher, markiert _device). */
function redditMerge() {
  const cache = rdCache();
  let n = 0;
  for (const p of DB.reddit) {
    const c = cache[p.id];
    if (c?.status !== 'ok') continue;
    for (const t of p.targets) {
      const h = rdHolder(t);
      if (!h) continue;
      h.screenshots = h.screenshots || [];
      for (const im of c.images) {
        const mid = redditMediaId(im.url);
        if (h.screenshots.some((s) => s.url === im.url || (mid && redditMediaId(s.url) === mid)) || h.screenshots.length >= 8) continue;
        h.screenshots.push({ url: im.url, caption: c.title || h.name || '', source: p.url, credit: `Reddit${c.author ? ' · u/' + c.author : ''} · vom Gerät geladen`, _device: true });
        n += 1;
      }
    }
  }
  return n;
}
function rdRefreshGalleries() {
  const g = DB.byId.get(state.lastGame);
  if (!g) return;
  for (const el of document.querySelectorAll('[data-shots]')) {
    const key = el.dataset.shots;
    const h = key === 'game' ? g : key.startsWith('m:') ? g.mods.find((m) => 'm:' + m.id === key) : g.routes.find((r) => 'r:' + r.id === key);
    if (h?.screenshots?.length) el.innerHTML = shotsHTML(h.screenshots, key);
  }
  for (const el of document.querySelectorAll('[data-reddit-pending]')) {
    const r = g.routes.find((x) => x.id === el.dataset.redditPending);
    if (r) el.outerHTML = redditBox(g, r) || '<div hidden></div>';
  }
}

/** Abholliste abarbeiten: erst die Beiträge des offenen Spiels, dann der Rest (Dual Screen zuerst), sanft getaktet. */
async function redditSync({ game = null, max = 12, report = true } = {}) {
  if (rdState.running || !DB.reddit.length || !navigator.onLine || redditMethod() === 'blocked' || redditMethod() === 'native-login') return;
  rdState.running = true;
  let loaded = 0;
  try {
    const list = DB.reddit.filter(rdDue).sort((a, b) => (game ? (b.targets.some((t) => t.split('/')[0] === game) - a.targets.some((t) => t.split('/')[0] === game)) : 0));
    for (const p of list.slice(0, max)) {
      const entry = await redditGet(p);
      if (!entry) break;                                  // Browser gesperrt: nicht weiter anfragen
      if (entry.status === 'failed') entry.fails = (rdCache()[p.id]?.fails || 0) + 1;
      rdRemember(p.id, entry);
      loaded += 1;
      if (entry.status === 'ok' && redditMerge() && state.lastGame && p.targets.some((t) => t.startsWith(state.lastGame + '/') || t === state.lastGame)) rdRefreshGalleries();
      await new Promise((r) => setTimeout(r, 1500));      // höflich: höchstens ein Beitrag alle 1,5 s
    }
  } finally { rdState.running = false; rdState.last = Date.now(); }
  if (location.hash.startsWith('#/spiel/')) rdRefreshGalleries();
  if (location.hash.startsWith('#/info')) route();
  if (report && loaded) redditReport(false);
}

const ghToken = () => store.get('githubToken', '');
function redditPayload(items) {
  return { kind: 'reddit-images', device: device().name || 'Handheld', method: redditMethod(), at: new Date().toISOString(),
    posts: items.map((o) => ({ post: o.post, status: o.status, title: o.title || '', author: o.author || '', images: o.images || [] })) };
}
function redditIssue(items) {
  const n = items.length;
  const imgs = items.reduce((s, o) => s + (o.images?.length || 0), 0);
  return { title: `Reddit-Bilder vom Gerät: ${n} ${n === 1 ? 'Beitrag' : 'Beiträge'}, ${imgs} Bilder (${new Date().toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })})`,
    body: `reddit-images: ${n}\n\nAutomatische Rückmeldung von Handheld Atlas (${device().name || 'Handheld'}): Bilder aus Reddit-Beiträgen, `
      + `direkt auf dem Gerät geladen. Die Action übernimmt sie ohne KI; die KI-Bildprüfung sieht sie danach an (docs/REDDIT.md).\n\n`
      + '```json\n' + JSON.stringify(redditPayload(items)) + '\n```\n' };
}
/** Ergebnisse zurückmelden: mit GitHub-Schlüssel automatisch per API, sonst (manuell) als vorbereitetes Issue. */
async function redditReport(manual) {
  const items = rdOutbox().slice(0, 25);
  if (!items.length) { if (manual) toast('Keine neuen Reddit-Ergebnisse zum Zurückmelden.'); return; }
  const { title, body } = redditIssue(items);
  const done = () => {
    store.set('redditOutbox', store.get('redditOutbox', []).filter((o) => !items.some((i) => i.id === o.id)));
    const list = requests().filter((r) => r.title !== title);
    list.unshift({ title, game: null, at: Date.now(), state: 'new' });
    store.set(REQ_KEY, list.slice(0, 12));
    scheduleRequestPoll(20000);
  };
  if (!ghToken()) {
    if (manual) { openIssue(title, body); done(); }
    return;
  }
  try {
    const res = await fetch(`https://api.github.com/repos/${DB.meta.repo}/issues`, {
      method: 'POST', headers: { Authorization: 'Bearer ' + ghToken(), Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, body, labels: ['recherche'] }),
    });
    if (!res.ok) throw new Error('GitHub antwortet ' + res.status + (res.status === 401 || res.status === 403 ? ' – Schlüssel prüfen (Issues: Lesen und Schreiben)' : ''));
    done();
    toast(`${items.length} Reddit-Ergebnis(se) an Atlas gemeldet – die Bilder sind in wenigen Minuten für alle Geräte in der Datenbank.`);
  } catch (e) { if (manual) toast(esc(e.message)); store.set('redditReportError', { at: Date.now(), detail: e.message }); }
}

/* Kasten unter der Galerie eines Spielwegs: Reddit-Beiträge, deren Bilder noch nicht in Atlas sind. */
function redditBox(g, r) {
  const posts = DB.reddit.filter((p) => p.targets.includes(`${g.id}/${r.id}`));
  if (!posts.length) return '';
  const cache = rdCache();
  const open = posts.filter((p) => cache[p.id]?.status !== 'ok');
  if (!open.length) return '';
  const method = redditMethod();
  const busy = rdState.running && method !== 'blocked';
  const embeds = open.slice(0, 3).map((p, i) => {
    const sub = (/\/r\/([A-Za-z0-9_]+)\//.exec(p.url) || [])[1];
    return sub ? `<button class="btn small" data-reddit-embed="${esc(sub)}/${esc(p.id)}">${icon('image')}Reddit-Beitrag ${open.length > 1 ? i + 1 + ' ' : ''}hier anzeigen</button>` : '';
  }).join('');
  return `<div class="reddit-box" data-reddit-pending="${esc(r.id)}">
    <p class="faint">${icon('image')} ${open.length} Reddit-${open.length === 1 ? 'Beitrag' : 'Beiträge'} zu diesem Weg ${busy ? 'werden gerade auf diesem Gerät geladen …'
      : method === 'blocked' ? '– der Browser darf Reddit nicht direkt lesen. Ansehen geht trotzdem:' : 'warten auf das Laden über dieses Gerät.'}</p>
    <div class="row">${embeds}${open.slice(0, 3).map((p, i) => `<a class="btn small" href="${esc(p.url)}" target="_blank" rel="noopener">Auf Reddit${open.length > 1 ? ' ' + (i + 1) : ''} ${icon('ext')}</a>`).join('')}</div>
    <div class="reddit-embeds"></div></div>`;
}

function redditPanel() {
  if (!DB.meta.repo) return '';
  const method = redditMethod();
  const probe = redditProbe();
  const cache = rdCache();
  const open = DB.reddit.filter((p) => cache[p.id]?.status !== 'ok' && cache[p.id]?.status !== 'gone' && cache[p.id]?.status !== 'no-images');
  const dual = open.filter((p) => p.dual).length;
  const loaded = DB.reddit.filter((p) => cache[p.id]?.status === 'ok').length;
  const out = rdOutbox();
  const err = store.get('redditReportError', null);
  return `<div class="panel"><h3>${icon('image')} Reddit-Bilder vom Gerät</h3>
    <p class="muted">Reddit sperrt Server (auch GitHub). Atlas lädt die Bilder verlinkter Reddit-Beiträge deshalb direkt auf diesem Gerät, zeigt sie sofort und meldet sie zurück in die Datenbank – Dual-Screen-Wege zuerst.</p>
    <ul class="checklist">
      <li class="${method === 'native' || method.startsWith('direct') ? 'ok' : method === 'blocked' ? 'miss' : 'part'}">${icon(method === 'blocked' ? 'alert' : 'check')}Abruf: ${esc(METHOD_LABEL[method])}${probe?.at ? ` (Test ${fmtDate(new Date(probe.at).toISOString())})` : ''}${method === 'blocked' && probe?.detail ? ' – ' + esc(probe.detail) : ''}</li>
      <li class="${open.length ? 'part' : 'ok'}">${icon(open.length ? 'alert' : 'check')}${open.length} ${open.length === 1 ? 'Beitrag' : 'Beiträge'} auf der Abholliste${dual ? `, davon ${dual} Dual Screen` : ''}; ${loaded} hier geladen</li>
      <li class="${out.length ? 'part' : 'ok'}">${icon(out.length ? 'alert' : 'check')}${out.length ? `${out.length} Ergebnis(se) warten auf Rückmeldung` : 'Alles zurückgemeldet'}${err && out.length ? ' – letzter Fehler: ' + esc(err.detail) : ''}</li>
    </ul>
    ${method === 'blocked' ? '<p class="faint">Seit Mai 2026 antwortet Reddit nur noch angemeldeten Nutzern, und eine Webseite darf deine Reddit-Anmeldung nicht mitbenutzen. Vollautomatisch klappt es in der Atlas-App (Info → Atlas-App): dort meldest du dich einmal bei Reddit an. Im Browser: Beiträge über „hier anzeigen“ am Spielweg ansehen. Atlas testet den Browser-Weg einmal am Tag neu.</p>' : ''}
    ${native.available ? `<p class="faint">${method === 'native' ? 'Du bist in der App bei Reddit angemeldet.' : 'Melde dich einmal in der App bei Reddit an (Benutzername und Passwort; die Google-Anmeldung funktioniert in App-Fenstern nicht). Atlas sieht dein Passwort nicht.'}</p>
      <div class="row"><button class="btn${method === 'native' ? '' : ' primary'}" data-su="reddit-login">${method === 'native' ? 'Reddit-Anmeldung öffnen' : 'Bei Reddit anmelden'}</button></div>` : ''}
    ${ghToken() ? '' : '<p class="faint">Für die automatische Rückmeldung den GitHub-Schlüssel unter „Wo wird recherchiert?“ eintragen.</p>'}
    <div class="row"><button class="btn" id="rd-sync"${open.length ? '' : ' disabled'}>${icon('spark')}${method === 'blocked' ? 'Erneut testen' : 'Jetzt laden'}</button>
      ${out.length ? `<button class="btn" id="rd-report">${icon('ext')}${ghToken() ? 'Jetzt zurückmelden' : 'Als Issue senden'}</button>` : ''}</div></div>`;
}

const daysSince = (d) => Math.floor((Date.now() - new Date(d + 'T00:00:00Z').getTime()) / 86400000);
/* What happened to this game since its deep research: releases of its projects, maintenance changes. */
function eventsSince(g, since) {
  const pids = new Set(g.routes.flatMap((r) => r.projects || []));
  return DB.changelog.filter((e) => e.date > since && ((e.type === 'release' && pids.has(e.project)) || (e.game === g.id && e.by !== 'ai-research')));
}
/* Discovery: games of the same system / similar games, best explored first */
function relatedSections(g) {
  const sys = g.platforms[0];
  const others = DB.games.filter((x) => x.id !== g.id);
  const rank = (a, b) => b._score - a._score || completeness(b).pct - completeness(a).pct;
  const sameSystem = sys ? others.filter((x) => x.platforms[0] === sys && x.franchise !== g.franchise).sort(rank) : [];
  const words = (x) => new Set(norm(x.genre || '').split(/[^a-z0-9]+/).filter((w) => w.length > 3));
  const gw = words(g);
  const similar = gw.size ? others.filter((x) => x.franchise !== g.franchise && [...words(x)].some((w) => gw.has(w))
    && x.platforms.some((p) => g.platforms.includes(p))).sort(rank) : [];
  const shelf = (title, list, href) => list.length ? `<section class="section"><div class="section-head"><h2>${title}</h2>${href ? `<a href="${href}">Alle</a>` : ''}</div><div class="shelf">${list.slice(0, 14).map(cardHTML).join('')}</div></section>` : '';
  return shelf(`Ähnliche Spiele${g.genre ? ` · ${esc(g.genre)}` : ''}`, similar)
    + shelf(`Mehr für ${esc(sys || '')}`, sameSystem, sys ? `#/plattform/${encodeURIComponent(sys)}` : '');
}

function researchInfo(g) {
  const d = DB.researched?.[g.id];
  const qi = (DB.queue || []).findIndex((j) => j.game === g.id);
  const job = qi >= 0 ? DB.queue[qi] : null;
  if (!d) return { state: 'none', d, job, qi, events: [], age: null };
  const age = daysSince(d);
  const events = eventsSince(g, d);
  return { state: age > 180 ? 'old' : events.length ? 'news' : age > 60 ? 'aging' : 'fresh', d, age, events, job, qi };
}
function researchStatus(g) {
  const ri = researchInfo(g);
  if (ri.job) return `<span class="tag v-ai-unverified">${icon('ai')}${ri.job.kind === 'update' ? 'Aktualisierung' : 'Tiefenrecherche'} in der Warteschlange (Platz ${ri.qi + 1})</span>`;
  if (ri.state === 'none') return `<span class="tag">${icon('info')}${g.wikidata ? 'Basisprofil (Wikidata) – noch nicht tiefenrecherchiert' : 'Noch nicht tiefenrecherchiert'}</span>`;
  const when = ri.age === 0 ? 'heute' : ri.age === 1 ? 'gestern' : `vor ${ri.age} Tagen`;
  const label = { fresh: 'aktuell', aging: 'etwas älter', news: `seitdem ${ri.events.length} ${ri.events.length === 1 ? 'Neuigkeit' : 'Neuigkeiten'}`, old: 'veraltet' }[ri.state];
  return `<span class="tag research-${ri.state}" title="${esc(ri.events.map((e) => fmtDate(e.date) + ': ' + e.text).join('\n'))}">${icon(ri.state === 'fresh' ? 'check' : 'alert')}Tiefenrecherche ${when} · ${label}</span>`;
}

function dualBox(g, ways) {
  const dual = ways.filter(isDual);
  if (!dual.length) return '';
  return `<section class="section"><div class="section-head"><h2>${icon('dual')} Dual Screen für dieses Spiel</h2><span class="faint">${dual.length} ${dual.length === 1 ? 'Möglichkeit' : 'Möglichkeiten'}</span></div>
    <div class="table-wrap"><table class="compare dual-table"><thead><tr><th>Weg</th><th>Fassung</th><th>Integration</th><th>Zweiter Bildschirm</th><th>Prüfstufe</th></tr></thead><tbody>
    ${dual.map((w) => `<tr><td><button class="linkish" data-open="${esc(w.key)}">${esc(w.name)}</button>${w.r?.status === 'archived' ? ' <span class="tag archived">archiviert</span>' : ''}
      ${w.r && !(w.r.screenshots || []).length && DB.meta.repo ? `<br><a class="link small" href="${esc(issueUrl(`Bilder: ${g.title} – ${w.r.name}`, `images: ${g.id}/${w.r.id}`))}" target="_blank" rel="noopener">${icon('image')}Kein Bild – suchen</a>` : ''}</td>
      <td>${esc(w.v.name)}</td><td><span class="tag dual">${esc(dualLabel(w))}</span></td><td>${esc(w.r?.dualScreen || '–')}</td><td>${wayTag(w)}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="faint">Im Spiel integriert = das Spiel oder der Port zeichnet selbst live auf den zweiten Bildschirm · Companion-App = separate Begleit-App · Zusatzinfos = statische Karte/Infos.</p></section>`;
}

/* Dual Screen tab: one card per game (cover + all its dual-screen ways as sub-rows).
   DS/3DS/Wii U games count too – their original had two screens, every emulator for them uses both. */
const NATIVE_DUAL = ['Nintendo DS', 'Nintendo 3DS', 'Wii U'];
const dualType = (w) => w.r?.dualScreenType || (w.features.includes('two-screens') ? 'native' : 'integrated');
function dualEntries() {
  return DB.games.map((g) => {
    const ways = waysFor(g).filter((w) => w.fits);
    const dual = ways.filter(isDual);
    const nativePlat = g.platforms.find((p) => NATIVE_DUAL.includes(p));
    // the emulators of the two-screen original (melonDS, Azahar …), best rated first
    const emus = nativePlat ? ways.filter((w) => !isDual(w) && w.v.platforms.includes(nativePlat)).sort((a, b) => b.score - a.score) : [];
    if (!dual.length && !nativePlat) return null;
    const types = new Set(dual.map(dualType));
    if (nativePlat) types.add('native');
    const score = Math.max(...dual.map((w) => w.score + 40), ...emus.map((w) => w.score), -999);
    const newest = dual.map((w) => w.r?.checkedAt || '').sort().pop() || '';
    return { g, dual, emus, nativePlat, types, score, newest };
  }).filter(Boolean);
}
function dualCard(e, sel) {
  const { g } = e;
  const dual = e.dual.filter((w) => !sel || dualType(w) === sel || (sel === 'native' && dualType(w) === 'native'));
  const shot = e.dual.flatMap((w) => w.r?.screenshots || []).find((x) => x.dual) || e.dual.flatMap((w) => w.r?.screenshots || [])[0];
  const rows = dual.sort((a, b) => b.score - a.score).map((w) => `<a class="dual-way" href="#/spiel/${esc(g.id)}" data-goto-way="${esc(w.key)}">
      <div class="grow"><div class="name">${esc(w.name)} <span class="faint">· ${esc(w.v.name)}</span></div>
        <div class="desc">${esc(w.r?.dualScreen || 'Zweiter Bildschirm unterstützt')}</div></div>
      <div class="tags"><span class="tag dual">${esc(dualLabel(w))}</span>${wayTag(w)}${w.best ? `<span class="rating ${RANK_CLASS(w.best.rank)}">${esc(w.best.ratingDe)}</span>` : ''}</div></a>`);
  if (e.nativePlat && (!sel || sel === 'native')) {
    const emu = e.emus[0];
    rows.push(`<a class="dual-way" href="#/spiel/${esc(g.id)}"${emu ? ` data-goto-way="${esc(emu.key)}"` : ''}>
      <div class="grow"><div class="name">${esc(e.nativePlat)}-Original <span class="faint">· ${emu ? esc(e.emus.slice(0, 3).map((w) => w.name).join(', ')) : 'Emulator folgt'}</span></div>
        <div class="desc">Das Spiel nutzt beide Bildschirme von Haus aus – der Emulator legt sie auf beide Displays.</div></div>
      <div class="tags"><span class="tag dual">${esc(label('dualScreenTypes', 'native'))}</span>${emu?.best ? `<span class="rating ${RANK_CLASS(emu.best.rank)}">${esc(emu.best.ratingDe)}</span>` : ''}</div></a>`);
  }
  return `<article class="dual-card">
    <a class="dual-head" href="#/spiel/${esc(g.id)}">
      <span class="dual-cover">${g.cover ? `<img src="${esc(g.cover.url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}<span class="ph" style="--h:${hue(g.franchise || g.title)}">${esc(g.title)}</span></span>
      <span class="grow"><span class="title">${esc(g.title)}</span>
        <span class="faint">${esc(g.franchise !== g.title ? g.franchise + ' · ' : '')}${esc(g.platforms.slice(0, 3).join(', '))}</span>
        <span class="faint">${e.dual.length ? `${e.dual.length} Dual-Screen-${e.dual.length === 1 ? 'Weg' : 'Wege'}` : 'Original mit zwei Bildschirmen'}</span></span>
      ${shot ? `<img class="dual-shot" src="${esc(shot.url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
    </a>
    <div class="dual-ways">${rows.join('')}</div></article>`;
}
function viewDual() {
  const types = DB.meta.dualScreenTypes || {};
  const sel = state.dualType || '';
  const sort = state.dualSort || 'best';
  const q = norm(state.q.trim());
  const all = dualEntries().filter((e) => !q || q.split(/\s+/).every((t) => e.g._search.includes(t)));
  const list = all.filter((e) => !sel || e.types.has(sel));
  const cmp = sort === 'az' ? (a, b) => a.g.title.localeCompare(b.g.title, 'de')
    : sort === 'new' ? (a, b) => b.newest.localeCompare(a.newest) || b.score - a.score
      : (a, b) => b.score - a.score || a.g.title.localeCompare(b.g.title, 'de');
  const withWays = list.filter((e) => e.dual.length && (!sel || e.dual.some((w) => dualType(w) === sel))).sort(cmp);
  const nativeOnly = list.filter((e) => !withWays.includes(e)).sort(cmp);
  const count = (t) => all.filter((e) => e.types.has(t)).length;
  const scan = DB.dualScan || {};
  const limit = state.dualLimit || 40;
  const section = (title, items, note) => items.length ? `<section class="section"><div class="section-head"><h2>${title}</h2><span class="faint">${items.length} Spiele</span></div>
    ${note ? `<p class="faint">${note}</p>` : ''}<div class="dual-grid">${items.slice(0, limit).map((e) => dualCard(e, sel)).join('')}</div>
    ${items.length > limit ? `<div class="more"><button class="btn" data-duallimit="${limit + 40}">Mehr laden (${items.length - limit} weitere)</button></div>` : ''}</section>` : '';
  return `<h1>Dual Screen</h1>
    <p class="muted">Was auf dem zweiten Bildschirm geht – ${all.length} Spiele${q ? ` für „${esc(state.q.trim())}“` : ''}.
      ${scan.lastRun ? `Letzter Dual-Screen-Suchlauf: ${fmtDate(scan.lastRun)} (${scan.found} neu).` : 'Der Dual-Screen-Suchlauf läuft wöchentlich.'}</p>
    <div class="filters">
      <button class="chip" data-dualtype="" aria-pressed="${!sel}">Alle <span class="faint">${all.length}</span></button>
      ${Object.entries(types).map(([k, l]) => `<button class="chip" data-dualtype="${k}" aria-pressed="${sel === k}">${esc(l)} <span class="faint">${count(k)}</span></button>`).join('')}
      <select class="chip" id="dualsort" aria-label="Sortierung">${[['best', 'Empfehlung'], ['new', 'Neueste'], ['az', 'A–Z']].map(([v, l]) => `<option value="${v}" ${v === sort ? 'selected' : ''}>${l}</option>`).join('')}</select>
      ${DB.meta.repo ? `<a class="chip" href="${esc(issueUrl('Dual-Screen-Suchlauf', 'dual-scan: ja'))}" target="_blank" rel="noopener">${icon('ai')}Suchlauf jetzt starten</a>` : ''}
    </div>
    ${section(`${icon('dual')} Mit Dual-Screen-Mod, Port oder Companion`, withWays, sel ? '' : 'Spiele, deren Port, Mod oder Begleit-App den zweiten Bildschirm nutzt. Unterpunkte = die einzelnen Wege.')}
    ${section(`${icon('handheld')} Original mit zwei Bildschirmen`, nativeOnly, 'DS-, 3DS- und Wii-U-Spiele: der Emulator legt beide Bildschirme auf die zwei Displays.')}
    ${!withWays.length && !nativeOnly.length ? '<div class="empty">Keine Treffer.</div>' : ''}`;
}

function franchiseCoverage(f) {
  const done = f.games.filter((g) => DB.researched?.[g.id]).length;
  const queued = f.games.filter((g) => (DB.queue || []).some((j) => j.game === g.id)).length;
  return { done, queued, total: f.games.length };
}

/* ---------------- router ---------------- */
const scrollMemo = new Map();
let currentKey = '';

function route() {
  const hash = location.hash.replace(/^#/, '') || '/';
  const [, a = '', ...rest] = hash.split('/');
  const b = decodeURIComponent(rest.join('/'));
  let html, tab = 'discover';
  if (a === 'spiel') {
    if (state.lastGame !== b) { state.gameTab = 'versions'; state.dualOnly = false; state.openWay = null; }
    if (state.pendingWay) { state.openWay = state.pendingWay; state.pendingWay = null; state.scrollToWay = true; }
    state.lastGame = b; html = viewGame(b); tab = null;
  }
  else if (a === 'franchises') { html = viewFranchises(); tab = 'franchises'; }
  else if (a === 'dual') { html = viewDual(); tab = 'dual'; }
  else if (a === 'franchise') { html = viewFranchise(b); tab = 'franchises'; }
  else if (a === 'projekte') { html = viewProjects(); tab = 'projects'; }
  else if (a === 'projekt') { html = viewProject(b); tab = 'projects'; }
  else if (a === 'neu') { html = viewNews(); tab = 'news'; }
  else if (a === 'merkliste') { html = viewFavs(); tab = 'favs'; }
  else if (a === 'info') { html = viewInfo(); tab = 'info'; }
  else if (a === 'neu-spiel') { html = viewNewGame(b); tab = null; }
  else if (a === 'einrichten' && typeof viewSetup === 'function') { html = viewSetup(b); tab = null; }
  else if (a === 'vorschau' && typeof viewPreview === 'function') { html = viewPreview(b); tab = null; }
  else if (a === 'plattform') { state.chips = new Set(); state.platform = decodeURIComponent(b || ''); state.q = ''; $('#q').value = ''; state.limit = PAGE; history.replaceState({ d: depth }, '', '#/'); html = viewDiscover(); }
  else if (a === 'filter') { state.chips = new Set([b]); state.q = ''; $('#q').value = ''; state.limit = PAGE; history.replaceState({ d: depth }, '', '#/'); html = viewDiscover(); }
  else html = viewDiscover();
  scrollMemo.set(currentKey, window.scrollY);
  currentKey = hash;
  stopPreview();
  $('#view').innerHTML = html;
  fillOnlineIndex();
  if (a === 'spiel' && DB.reddit.some((p) => rdDue(p) && p.targets.some((t) => t.split('/')[0] === b))) setTimeout(() => redditSync({ game: b, max: 6 }), 600);
  if (state.scrollToWay) {
    state.scrollToWay = false;
    requestAnimationFrame(() => document.getElementById(wayId(state.openWay))?.scrollIntoView({ block: 'center' }));
    return void renderTabs(tab);
  }
  renderTabs(tab);
  window.scrollTo(0, scrollMemo.get(hash) || 0);
}

function rerender() { const y = window.scrollY; stopPreview(); $('#view').innerHTML = viewDiscover(); window.scrollTo(0, y); fillOnlineIndex(); }
let depth = 0; // how many in-app steps we can go back without leaving Atlas

function renderTabs(active) {
  $('#tabs').innerHTML = TABS.map((t) => `<a class="tab" href="${t.href}" ${t.id === active ? 'aria-current="page"' : ''}>${icon(t.icon)}<span class="lbl">${t.label}</span>${t.id === 'favs' && state.favs.size ? `<span class="count" style="background:var(--surface-3);color:var(--muted)">${state.favs.size}</span>` : ''}</a>`).join('');
}

/* ---------------- events ---------------- */
function openLightbox(group, i) {
  let shots;
  if (group === 'game') shots = DB.byId.get(state.lastGame)?.screenshots;
  else {
    const g = DB.byId.get(state.lastGame);
    for (const r of g?.routes || []) if ('r:' + r.id === group) shots = r.screenshots;
    for (const m of g?.mods || []) if ('m:' + m.id === group) shots = m.screenshots;
  }
  if (!shots?.length) return;
  const lb = $('#lightbox');
  const show = (k) => {
    const s = shots[(k + shots.length) % shots.length];
    lb.dataset.i = (k + shots.length) % shots.length;
    const pixel = s.url.includes('libretro-thumbnails') ? 'pixel' : '';
    const src = fullSrc(s.url);
    lb.innerHTML = `<img class="${pixel}" src="${esc(src)}"${src !== s.url ? ` data-fb="${esc(s.url)}" onerror="if(this.dataset.fb){this.src=this.dataset.fb;delete this.dataset.fb}"` : ''} alt="${esc(s.caption || '')}" referrerpolicy="no-referrer">
      <div class="bar"><span>${esc(s.caption || '')}${s.credit ? ' · ' + esc(s.credit) : ''}</span>
      ${shots.length > 1 ? `<button class="btn" data-lb="-1">${icon('back')}</button><span>${+lb.dataset.i + 1} / ${shots.length}</span><button class="btn" data-lb="1" style="transform:scaleX(-1)">${icon('back')}</button>` : ''}
      ${s.source ? `<a class="btn" href="${esc(s.source)}" target="_blank" rel="noopener">Quelle ${icon('ext')}</a>` : ''}<button class="btn primary" data-lb="close">Schließen</button></div>`;
    lb.querySelector('[data-lb="close"]').focus();
  };
  lb.hidden = false;
  lb.step = (d) => show(+lb.dataset.i + d);
  show(i);
}
const closeLightbox = () => { const lb = $('#lightbox'); if (!lb.hidden) { lb.hidden = true; lb.innerHTML = ''; return true; } return false; };

document.addEventListener('click', (e) => {
  const arrow = e.target.closest('[data-slide]');
  if (arrow) { e.preventDefault(); e.stopPropagation(); stepPreview(arrow.closest('.card'), +arrow.dataset.slide); return; }
  const t = e.target.closest('button, a');
  if (!t) return;
  if (t.dataset.dualtype !== undefined) { e.preventDefault(); state.dualType = t.dataset.dualtype; state.dualLimit = 40; route(); restoreFocus(`[data-dualtype="${t.dataset.dualtype}"]`); return; }
  if (t.dataset.duallimit) { e.preventDefault(); state.dualLimit = +t.dataset.duallimit; const y = window.scrollY; route(); window.scrollTo(0, y); return; }
  if (t.dataset.gotoWay) { state.pendingWay = t.dataset.gotoWay; }
  if (t.dataset.analyze) {
    e.preventDefault();
    const key = t.dataset.analyze;
    const g = key.startsWith('new:') ? { id: null, title: key.slice(4), platforms: [], versions: [], routes: [], mods: [] } : DB.byId.get(key);
    runAnalysis(key, g, t.dataset.focus || null);
    requestAnimationFrame(() => document.getElementById('analysis')?.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    return;
  }
  if (t.dataset.modcat !== undefined) { e.preventDefault(); state.modCat = t.dataset.modcat || null; route(); restoreFocus(`[data-modcat="${t.dataset.modcat}"]`); return; }
  if (t.dataset.openVersion) {
    e.preventDefault(); state.gameTab = 'versions'; route();
    document.getElementById('v-' + t.dataset.openVersion)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    return;
  }
  if (t.dataset.anCancel) { e.preventDefault(); analyses.get(t.dataset.anCancel)?.ctrl?.abort(); return; }
  if (t.id === 'ai-save') {
    store.set('openaiKey', $('#ai-key').value.trim()); store.set('openaiModel', $('#ai-model').value.trim());
    toast(aiKey() ? 'Schlüssel gespeichert (nur auf diesem Gerät).' : 'Kein Schlüssel eingetragen.'); route(); return;
  }
  if (t.id === 'ai-clear') { store.set('openaiKey', ''); toast('Schlüssel gelöscht.'); route(); return; }
  if (t.id === 'gh-save') {
    store.set('githubToken', $('#gh-token').value.trim());
    toast(ghToken() ? 'GitHub-Schlüssel gespeichert (nur auf diesem Gerät). Reddit-Ergebnisse werden ab jetzt automatisch gemeldet.' : 'Kein Schlüssel eingetragen.');
    route(); if (ghToken()) redditReport(false); return;
  }
  if (t.id === 'gh-clear') { store.set('githubToken', ''); toast('GitHub-Schlüssel gelöscht.'); route(); return; }
  if (t.id === 'rd-sync') {
    e.preventDefault();
    if (redditMethod() === 'blocked') store.set('redditProbe', null);
    toast('Lade Reddit-Beiträge auf diesem Gerät …');
    redditSync({ max: 25 }).then(() => { route(); toast(`Reddit: ${METHOD_LABEL[redditMethod()]}.`); });
    return;
  }
  if (t.id === 'rd-report') { e.preventDefault(); redditReport(true).then(() => route()); return; }
  if (t.dataset.redditEmbed) {
    e.preventDefault();
    const [sub, id] = t.dataset.redditEmbed.split('/');
    const box = t.closest('.reddit-box')?.querySelector('.reddit-embeds');
    if (box && !box.querySelector(`[data-embed="${id}"]`)) {
      box.insertAdjacentHTML('beforeend', `<iframe data-embed="${esc(id)}" class="reddit-embed" loading="lazy" title="Reddit-Beitrag"
        src="https://embed.reddit.com/r/${encodeURIComponent(sub)}/comments/${encodeURIComponent(id)}/?embed=true&amp;theme=dark&amp;showmedia=true&amp;showmore=false"
        sandbox="allow-scripts allow-same-origin allow-popups" referrerpolicy="no-referrer"></iframe>`);
    }
    t.remove();
    return;
  }
  if (t.dataset.open) {
    e.preventDefault();
    state.openWay = t.dataset.open; state.gameTab = 'versions'; route();
    const el = document.getElementById(wayId(t.dataset.open));
    if (el) { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); el.querySelector('summary')?.focus({ preventScroll: true }); }
    return;
  }
  if (t.dataset.chip) { state.chips.has(t.dataset.chip) ? state.chips.delete(t.dataset.chip) : state.chips.add(t.dataset.chip); state.limit = PAGE; rerender(); restoreFocus(`[data-chip="${t.dataset.chip}"]`); }
  else if (t.id === 'reset') { state.chips.clear(); state.platform = ''; state.q = ''; $('#q').value = ''; rerender(); }
  else if (t.id === 'more') { state.limit += PAGE; rerender(); restoreFocus('#more'); }
  else if (t.dataset.gtab) { state.gameTab = t.dataset.gtab; route(); restoreFocus(`[data-gtab="${t.dataset.gtab}"]`); }
  else if (t.id === 'dualOnly') { state.dualOnly = !state.dualOnly; route(); restoreFocus('#dualOnly'); }
  else if (t.id === 'fav') { const id = state.lastGame; state.favs.has(id) ? state.favs.delete(id) : state.favs.add(id); store.set('favs', [...state.favs]); route(); restoreFocus('#fav'); }
  else if (t.dataset.device) { state.device = t.dataset.device; store.set('device', state.device); route(); restoreFocus(`[data-device="${t.dataset.device}"]`); }
  else if (t.dataset.lightbox) openLightbox(t.dataset.lightbox, +t.dataset.i);
  else if (t.dataset.lb) { t.dataset.lb === 'close' ? closeLightbox() : $('#lightbox').step(+t.dataset.lb); }
  else if (t.id === 'update') checkUpdate(true);
  else if (t.hasAttribute('data-back') && depth > 0) { e.preventDefault(); history.back(); }
  else return;
  if (t.tagName === 'BUTTON' || t.hasAttribute('data-back')) e.preventDefault();
});
const restoreFocus = (sel) => requestAnimationFrame(() => $(sel)?.focus({ preventScroll: true }));

document.addEventListener('change', (e) => {
  if (e.target.id === 'platform') { state.platform = e.target.value; state.limit = PAGE; rerender(); restoreFocus('#platform'); }
  if (e.target.id === 'sort') { state.sort = e.target.value; rerender(); restoreFocus('#sort'); }
  if (e.target.id === 'dualsort') { state.dualSort = e.target.value; route(); restoreFocus('#dualsort'); }
});

let qTimer;
document.addEventListener('input', (e) => {
  if (e.target.id !== 'q') return;
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    state.q = e.target.value; state.limit = PAGE;
    const h = location.hash.replace(/^#/, '') || '/';
    if (h === '/' || h.startsWith('/franchises') || h.startsWith('/projekte') || h.startsWith('/dual')) rerenderList(h);
    else location.hash = '#/';
  }, 120);
});
function rerenderList(h) {
  const v = h.startsWith('/franchises') ? viewFranchises : h.startsWith('/projekte') ? viewProjects : h.startsWith('/dual') ? viewDual : viewDiscover;
  $('#view').innerHTML = v();
  fillOnlineIndex();
}

/* ---------------- gamepad & d-pad navigation ---------------- */
const focusables = () => [...document.querySelectorAll(
  $('#lightbox').hidden ? '.top a, .top input, main a, main button, main select, main summary' : '#lightbox button, #lightbox a')]
  .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !el.closest('[hidden]') && !el.closest('details:not([open]) > :not(summary)'); });

let lastNav = 0;
function move(dir) {
  const now = performance.now();
  if (now - lastNav < 70) return; // Android may deliver the same press as key event *and* gamepad state
  lastNav = now;
  document.body.classList.add('kbd-nav');
  const cur = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
  const els = focusables();
  if (!cur || !els.includes(cur)) { (els.find((el) => el.closest('main')) || els[0])?.focus(); return; }
  const c = cur.getBoundingClientRect();
  const cx = c.left + c.width / 2, cy = c.top + c.height / 2;
  let best = null, bestScore = Infinity;
  for (const el of els) {
    if (el === cur) continue;
    const r = el.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const dx = x - cx, dy = y - cy;
    let main, cross;
    if (dir === 'right') { if (r.left < c.right - 4 || dx <= 0) continue; main = r.left - c.right; cross = Math.abs(dy); }
    else if (dir === 'left') { if (r.right > c.left + 4 || dx >= 0) continue; main = c.left - r.right; cross = Math.abs(dy); }
    else if (dir === 'down') { if (r.top < c.bottom - 4 || dy <= 0) continue; main = r.top - c.bottom; cross = Math.abs(dx); }
    else { if (r.bottom > c.top + 4 || dy >= 0) continue; main = c.top - r.bottom; cross = Math.abs(dx); }
    const score = Math.max(main, 0) + cross * 2.2;
    if (score < bestScore) { bestScore = score; best = el; }
  }
  if (best) { best.focus({ preventScroll: true }); best.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' }); }
  if (best && (dir === 'up' || dir === 'down') && best.closest('main')) {
    const r = best.getBoundingClientRect();
    if (r.top < 90) window.scrollBy({ top: r.top - 100, behavior: 'smooth' });
  }
}
function back() {
  if (closeLightbox()) return;
  if (typeof dualBack === 'function' && dualBack()) return;
  if (depth > 0) history.back();
  else if ((location.hash || '#/') !== '#/') location.hash = '#/';
}
function switchTab(d) {
  const cur = TABS.findIndex((t) => $(`.tab[href="${t.href}"]`)?.getAttribute('aria-current'));
  const next = TABS[(Math.max(cur, 0) + d + TABS.length) % TABS.length];
  location.hash = next.href;
}

document.addEventListener('keydown', (e) => {
  const typing = e.target.matches('input, select');
  const dirs = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
  if (!$('#lightbox').hidden && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) { $('#lightbox').step(e.key === 'ArrowLeft' ? -1 : 1); e.preventDefault(); return; }
  if (dirs[e.key] && !(typing && (e.key === 'ArrowLeft' || e.key === 'ArrowRight') && e.target.value) && !(e.target.tagName === 'SELECT' && (e.key === 'ArrowUp' || e.key === 'ArrowDown'))) {
    e.preventDefault(); move(dirs[e.key]);
  } else if (e.key === 'Escape' || (e.key === 'Backspace' && !typing) || e.key === 'GoBack' || e.key === 'BrowserBack') {
    if (typing) { e.target.blur(); return; }
    e.preventDefault(); back();
  } else if (e.key === '/' && !typing) { e.preventDefault(); $('#q').focus(); }
  else if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('summary')) { /* native */ }
});

const pads = { prev: {} };
function pollPads() {
  const gp = [...(navigator.getGamepads?.() || [])].find(Boolean);
  if (gp) {
    const pressed = (i) => gp.buttons[i]?.pressed;
    const axis = (i) => gp.axes[i] || 0;
    const now = {
      up: pressed(12) || axis(1) < -0.6, down: pressed(13) || axis(1) > 0.6,
      left: pressed(14) || axis(0) < -0.6, right: pressed(15) || axis(0) > 0.6,
      a: pressed(0), b: pressed(1), l: pressed(4), r: pressed(5), select: pressed(8), start: pressed(9),
    };
    const edge = (k) => now[k] && !pads.prev[k];
    for (const d of ['up', 'down', 'left', 'right']) {
      if (edge(d)) { pads.hold = performance.now() + 380; move(d); }
      else if (now[d] && performance.now() > pads.hold) { pads.hold = performance.now() + 110; move(d); }
    }
    if (edge('a')) document.activeElement?.click();
    if (edge('b')) back();
    if (edge('l')) { if (!$('#lightbox').hidden) $('#lightbox').step(-1); else switchTab(-1); }
    if (edge('r')) { if (!$('#lightbox').hidden) $('#lightbox').step(1); else switchTab(1); }
    if (edge('start')) { if (typeof dualRole === 'function' && dualRole() === 'stage') native.call('focusOther').catch(() => {}); else $('#q').focus(); }
    if (edge('select') && typeof dualOn === 'function' && dualOn()) native.call('focusOther').catch(() => {});
    pads.prev = now;
  }
  requestAnimationFrame(pollPads);
}
window.addEventListener('gamepadconnected', () => { if (!pads.running) { pads.running = true; requestAnimationFrame(pollPads); } });
document.addEventListener('pointerdown', () => document.body.classList.remove('kbd-nav'));

/* ---------------- updates ---------------- */
function toast(html, ms = 6000) {
  const t = $('#toast');
  t.innerHTML = html; t.hidden = false;
  clearTimeout(t._t); if (ms) t._t = setTimeout(() => { t.hidden = true; }, ms);
}
async function checkUpdate(manual) {
  if (window.ATLAS_EMBEDDED || location.protocol === 'file:') { if (manual) toast('Offline-Version: neue Daten gibt es über die Online-App.'); return; }
  try {
    const v = await (await fetch('version.json', { cache: 'no-store' })).json();
    if (state.version && v.version !== state.version) {
      toast(`Neue Daten vom ${fmtDate(v.builtAt)} verfügbar. <button class="btn primary" onclick="location.reload()">Laden</button>`, 0);
    } else if (manual) toast('Atlas ist aktuell.');
  } catch { if (manual) toast('Keine Verbindung – du siehst den zuletzt geladenen Stand.'); }
}

async function init() {
  try {
    const data = await loadData();
    index(data);
    if (!window.ATLAS_EMBEDDED) fetch('version.json', { cache: 'no-store' }).then((r) => r.json()).then((v) => { state.version = v.version; }).catch(() => {});
  } catch (err) {
    $('#view').innerHTML = `<div class="empty">Daten konnten nicht geladen werden (${esc(err.message)}).<br>Beim ersten Start ist eine Internetverbindung nötig.</div>`;
    return;
  }
  history.replaceState({ d: 0 }, '');
  window.addEventListener('hashchange', () => {
    if (typeof history.state?.d === 'number') depth = history.state.d;  // back / forward
    else { depth += 1; history.replaceState({ d: depth }, ''); }       // new navigation
    closeLightbox(); route();
  });
  route();
  if (typeof suReady === 'function') suReady();   // Setup-Assistent (setup.js)
  scheduleRequestPoll(3000);
  setTimeout(() => redditSync({ max: 12 }), 5000);   // Reddit-Abholliste im Hintergrund (docs/REDDIT.md)
  window.addEventListener('online', () => redditReport(false));
  if ('serviceWorker' in navigator && location.protocol === 'https:' && !window.ATLAS_EMBEDDED) navigator.serviceWorker.register('sw.js').catch(() => {});
  document.addEventListener('visibilitychange', () => { if (!document.hidden) checkUpdate(false); });
  if (navigator.getGamepads && [...navigator.getGamepads()].some(Boolean)) { pads.running = true; requestAnimationFrame(pollPads); }
}
init();
