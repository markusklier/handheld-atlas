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
const fmtDate = (d) => {
  if (!d) return '';
  const dt = new Date(d.length === 10 ? d + 'T12:00:00Z' : d);
  return isNaN(dt) ? d : dt.toLocaleDateString('de-DE', { day: 'numeric', month: 'short', year: 'numeric' });
};

const DB = { games: [], byId: new Map(), projects: {}, platforms: {}, meta: {}, changelog: [], franchises: [] };
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
  const img = g.cover ? `<img src="${esc(g.cover.url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : '';
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
    <div><div class="t">${esc(g.title)}</div><div class="s">${ways}</div></div></a>`;
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
  stopPreview();
  const g = DB.byId.get(card.dataset.game);
  const slides = g ? previewSlides(g) : [];
  if (!slides.length) return;
  Object.assign(preview, { card, slides, i: 0 });
  preview.delay = setTimeout(() => {
    showSlide(0);
    preview.timer = setInterval(() => showSlide(preview.i + 1), 1600);
  }, 350); // don't flicker while the mouse just passes over
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
  preview.timer = setInterval(() => showSlide(preview.i + 1), 2600);
}
document.addEventListener('mouseover', (e) => { const c = e.target.closest?.('.card'); if (c) startPreview(c); });
document.addEventListener('mouseout', (e) => { const c = e.target.closest?.('.card'); if (c && !c.contains(e.relatedTarget)) stopPreview(); });
document.addEventListener('focusin', (e) => { const c = e.target.closest?.('.card'); if (c) startPreview(c); else stopPreview(); });

const gridHTML = (games) => games.length ? `<div class="grid">${games.map(cardHTML).join('')}</div>` : `<div class="empty">Nichts gefunden.</div>`;

function verifTag(v) {
  const ic = { 'thor-tested': 'check', community: 'gamepad', documented: 'info', 'ai-unverified': 'ai' }[v] || 'info';
  return `<span class="tag v-${esc(v)}">${icon(ic)}${esc(label('verification', v))}</span>`;
}

function shotsHTML(shots, group) {
  if (!shots?.length) return '';
  return `<div class="gallery">${shots.map((s, i) => {
    const pixel = s.url.includes('libretro-thumbnails') ? ' pixel' : '';
    return `<button class="shot${pixel}" data-lightbox="${esc(group)}" data-i="${i}" aria-label="Bild vergrößern: ${esc(s.caption || '')}"><img src="${esc(s.url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.closest('.shot').remove()">${s.caption ? `<figcaption>${esc(s.caption)}</figcaption>` : ''}</button>`;
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
      <select class="chip" id="sort" aria-label="Sortierung">${[['relevance', 'Relevanz'], ['title', 'A–Z'], ['updated', 'Zuletzt aktualisiert']].map(([v, l]) => `<option value="${v}" ${v === state.sort ? 'selected' : ''}>${l}</option>`).join('')}</select>
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
    if (recentGames.length) html += shelf('Zuletzt aktualisiert', recentGames, '#/neu');
    if (DB.games.some((g) => g._ai)) html += shelf('Neue KI-Funde', DB.games.filter((g) => g._ai), '#/filter/ai');
  }
  const list = filterGames();
  html += `<section class="section"><div class="result-head"><h2>${filtering ? 'Ergebnisse' : 'Alle Spiele'}</h2><span class="faint">${list.length} Spiele</span></div>
    ${gridHTML(list.slice(0, state.limit))}
    ${list.length > state.limit ? `<div class="more"><button class="btn" id="more">Mehr laden (${list.length - state.limit} weitere)</button></div>` : ''}</section>`;
  return html;
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
      ways.push({ key: 'o:' + v.id, type: 'official', v, name: 'Offizielle Android-App', kind: 'native', features: [...(v.traits || [])] });
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
  }
  for (const w of ways) Object.assign(w, rate(w));
  return ways;
}

/* Transparent ranking for the selected device. Every point comes with a visible reason. */
function rate(w) {
  const reasons = [];
  const r = w.r;
  const targets = r?.targets || w.targets || ['android'];
  if (device().target && !targets.includes(device().target)) return { score: -999, reasons, fits: false };
  let score = w.type === 'route' ? VERIF_SCORE[r.verification] ?? 8 : w.type === 'official' ? 22 : 5;
  if (w.type === 'route' && r.verification === 'thor-tested') reasons.push(['check', 'Auf dem Thor getestet']);
  if (w.type === 'route' && r.verification === 'community') reasons.push(['gamepad', 'Erfahrungsberichte']);
  if (w.type === 'official') reasons.push(['check', 'Offiziell für Android']);
  if (w.features.includes('dual-screen')) { score += device().dualScreen ? 25 : 4; reasons.push(['dual', 'Dual Screen']); }
  if (NATIVE.has(w.kind) || w.type === 'official') { score += 12; reasons.push(['chip', 'Läuft nativ']); }
  for (const [f, txt] of [['widescreen', 'Widescreen'], ['high-fps', 'Hohe Bildrate'], ['upscaling', 'Höhere Auflösung'], ['crossplay', 'Crossplay']]) {
    if (w.features.includes(f)) { score += 4; reasons.push(['spark', txt]); }
  }
  if (w.features.includes('mods')) { score += 3; reasons.push(['wrench', 'Mods']); }
  if (w.type === 'generic') reasons.push(['info', 'Allgemein, ungeprüft']);
  const effort = r?.effort || (w.type === 'generic' ? 'guided' : 'easy');
  score += { easy: 6, guided: 2, advanced: 0, experimental: -6 }[effort] ?? 0;
  if (r?.status === 'archived') { score -= 40; reasons.push(['alert', 'Archiviert']); }
  if (r?.status === 'experimental') { score -= 6; reasons.push(['alert', 'Experimentell']); }
  const reports = r?.reports?.length || 0;
  if (reports) score += Math.min(reports * 3, 15);
  return { score, reasons, fits: true, effort, reports, perf: r?.performance?.length || 0 };
}

function wayTag(w) {
  if (w.type === 'route') return verifTag(w.r.verification);
  if (w.type === 'official') return `<span class="tag v-documented">${icon('check')}Offizielle App</span>`;
  return `<span class="tag">${icon('info')}Allgemein</span>`;
}

function wayBody(g, w) {
  if (w.type === 'route') return routeHTML(g, w.r);
  if (w.type === 'official') {
    return `<article class="route"><p>${esc(w.v.name)} ist offiziell für Android erschienen: kaufen und installieren über den Play Store, keine Emulation nötig.</p>
      ${(w.v.links || []).length ? `<div class="row">${w.v.links.map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ${icon('ext')}</a>`).join('')}</div>` : ''}
      <p class="faint">Controller- und Zweitbildschirm-Unterstützung sind für diese Fassung noch nicht eingetragen.</p></article>`;
  }
  return `<article class="route"><p class="muted">${esc(w.o.note)}</p><p class="faint">Allgemeiner Emulator für ${esc(w.v.platforms.join(', '))}. Ob ${esc(g.title)} darin gut läuft, ist noch nicht spielspezifisch geprüft.</p>${projectLine(DB.projects[w.o.project])}</article>`;
}

const wayId = (key) => 'w-' + key.replace(/[^a-z0-9-]/gi, '_');

function wayRow(g, w, open) {
  const dual = w.features.includes('dual-screen');
  const mini = w.reasons.filter(([ic]) => ic === 'spark' || ic === 'wrench' || ic === 'chip').map(([, t]) => `<span class="tag">${esc(t)}</span>`).join('');
  return `<details class="way${w.type === 'generic' ? ' generic' : ''}" id="${wayId(w.key)}" ${open ? 'open' : ''}>
    <summary><span class="way-name">${esc(w.name)}<small>${esc(label('kinds', w.kind))}${w.r?.runtime ? ' · ' + esc(w.r.runtime) : ''}</small></span>
      <span class="way-tags">${dual ? `<span class="tag dual">${icon('dual')}Dual</span>` : ''}${mini}${wayTag(w)}</span></summary>
    ${wayBody(g, w)}</details>`;
}

function versionCard(g, v, ways) {
  const meta = [label('versionTypes', v.type), v.year].filter(Boolean).join(' · ');
  const android = v.platforms.includes('Android');
  const shown = state.dualOnly ? ways.filter((w) => w.features.includes('dual-screen')) : ways;
  const plats = v.platforms.length > 1 || v.platforms[0] !== v.name ? ' · ' + esc(v.platforms.join(', ')) : '';
  return `<section class="version" id="v-${esc(v.id)}">
    <div class="version-head"><div><h3>${esc(v.name)}</h3><div class="sub">${esc(meta)}${plats}</div></div>
      <div class="row">${android ? `<span class="tag v-documented">${icon('check')}Android offiziell</span>` : ''}${(v.traits || []).map((t) => `<span class="tag">${esc(label('features', t))}</span>`).join('')}</div></div>
    ${v.note ? `<p class="muted">${esc(v.note)}</p>` : ''}
    ${shown.length ? `<div class="ways">${shown.map((w) => wayRow(g, w, state.openWay === w.key)).join('')}</div>`
      : `<p class="faint">${ways.length ? 'Kein Dual-Screen-Weg für diese Fassung.' : 'Für diese Fassung ist auf Android noch kein Weg bekannt.'}</p>`}
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
    <td>${w.reports || '<span class="no">–</span>'}</td><td>${w.perf ? `${w.perf} Messung(en)` : '<span class="no">noch keine</span>'}</td></tr>`).join('')}
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
  } else {
    body = `<div class="mods">${g.mods.map((m) => `<div class="mod"><div class="row" style="justify-content:space-between"><h3>${esc(m.name)}</h3>${verifTag(m.verification || 'documented')}</div>
      <div class="row">${m.category ? `<span class="tag">${esc(m.category)}</span>` : ''}${m.edition ? `<span class="tag">${esc(m.edition)}</span>` : ''}</div>
      <p class="muted" style="margin:0">${esc(m.description)}</p>${shotsHTML(m.screenshots, 'm:' + m.id)}<a class="link" href="${esc(m.url)}" target="_blank" rel="noopener">Zum Mod ${icon('ext')}</a></div>`).join('')}</div>`;
  }
  return `<a class="btn back" href="#/" data-back>${icon('back')}Zurück</a>
    <div class="hero">${coverHTML(g, { badges: false })}<div class="meta">
      <a class="franchise" href="#/franchise/${encodeURIComponent(g.franchise)}">${esc(g.franchise)}</a>
      <h1>${esc(g.title)}</h1>
      <div class="row"><span class="tag">${versions.length} ${versions.length === 1 ? 'Fassung' : 'Fassungen'}</span><span class="tag">${fitting.length} ${fitting.length === 1 ? 'Weg' : 'Wege'} für ${esc(device().name)}</span>${g.genre ? `<span class="tag">${esc(g.genre)}</span>` : ''}${g._dual ? `<span class="tag dual">${icon('dual')}Dual Screen</span>` : ''}</div>
      ${g.summary ? `<p>${esc(g.summary)}</p>` : ''}
      <div class="row"><button class="btn ${fav ? 'on' : ''}" id="fav">${icon('bookmark')}${fav ? 'Gemerkt' : 'Merken'}</button>
      ${DB.meta.repo ? `<a class="btn" href="https://github.com/${esc(DB.meta.repo)}/issues/new?labels=recherche&title=${encodeURIComponent('Recherche: ' + g.title)}&body=${encodeURIComponent('game: ' + g.id + '\n\nWas soll recherchiert werden? (optional)')}" target="_blank" rel="noopener">${icon('ai')}Recherche anfordern</a>` : ''}
      ${g.routes.length ? `<span class="faint">Stand ${fmtDate(g.updatedAt)}</span>` : ''}</div>
    </div></div>
    ${recommendation(g, fitting)}
    ${g.screenshots.length ? `<section class="section"><div class="section-head"><h2>Originalspiel</h2></div>${shotsHTML(g.screenshots, 'game')}</section>` : ''}
    <section class="section"><div class="seg" role="tablist">${tabs.map(([k, l, n]) => `<button role="tab" data-gtab="${k}" aria-selected="${tab === k}">${l}<span class="n">${n}</span></button>`).join('')}</div>${body}</section>`;
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
    ${shotsHTML(r.screenshots, 'r:' + r.id)}
    <div class="cols">
      ${r.benefit ? `<div><h4>Vorteil</h4><p>${esc(r.benefit)}</p></div>` : ''}
      ${r.caveat ? `<div><h4>Beachten</h4><p class="warn">${esc(r.caveat)}</p></div>` : ''}
      ${r.requires?.length ? `<div><h4>Du brauchst</h4><ul>${r.requires.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
      <div><h4>So geht's</h4>${steps}</div>
    </div>
    ${r.version ? `<div class="faint">Version: ${esc(r.version)}</div>` : ''}
    ${projects ? `<div class="projects-line"><h4 class="faint" style="margin:0">Projekte</h4>${projects}</div>` : ''}
    ${links ? `<div class="row">${links}</div>` : ''}
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
      <div class="grow"><div class="title">${esc(f.name)}</div><div class="desc">${f.games.length} Spiele${f.routes ? ` · ${f.routes} Spielwege` : ''}${f.dual ? ' · Dual Screen' : ''}</div></div></a>`).join('')}</div>
    <p class="faint section">Einzeltitel ohne Reihe findest du über die Suche (${list.length - withRoutes.length} weitere).</p>`;
}

function viewFranchise(name) {
  const f = DB.franchises.find((x) => x.name === name);
  if (!f) return '<div class="empty">Franchise nicht gefunden.</div>';
  return `<a class="btn back" href="#/franchises" data-back>${icon('back')}Franchises</a><h1>${esc(f.name)}</h1>
    <p class="muted">${f.games.length} Spiele${f.routes ? ` · ${f.routes} dokumentierte Spielwege` : ''}</p><div class="section">${gridHTML(f.games)}</div>`;
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

function viewInfo() {
  return `<h1>Info</h1>
  <div class="panels section">
    <div class="panel"><h3>Dein Gerät</h3><p class="muted">Spielwege für andere Plattformen werden eingeklappt.</p>
      <div class="chips">${(DB.meta.devices || []).map((d) => `<button class="chip" data-device="${esc(d.id)}" aria-pressed="${d.id === state.device}">${esc(d.name)}</button>`).join('')}</div></div>
    <div class="panel"><h3>Was die Markierungen bedeuten</h3><div class="legend">
      ${Object.keys(DB.meta.verification || {}).map((k) => `<div>${verifTag(k)}</div>`).join('')}</div></div>
    <div class="panel"><h3>Steuerung</h3><p class="muted">Steuerkreuz bewegt den Fokus, <kbd>A</kbd> öffnet, <kbd>B</kbd> geht zurück, <kbd>L1</kbd>/<kbd>R1</kbd> wechseln den Bereich, <kbd>Start</kbd> springt zur Suche.</p></div>
    <div class="panel"><h3>Daten</h3><p class="muted">Stand ${fmtDate(DB.builtAt)}. ${DB.games.length} Spiele, ${Object.keys(DB.projects).length} Projekte. Die App holt sich neue Daten selbst, sobald sie online geöffnet wird.</p>
      <div class="row"><button class="btn" id="update">Nach Updates suchen</button>${window.ATLAS_EMBEDDED ? '' : '<a class="btn" href="Handheld-Atlas-offline.html" download>Offline-Version laden</a>'}</div></div>
  </div>
  <p class="faint section">Atlas installiert und startet keine Spiele und enthält keine ROMs, APKs oder Spieldaten. Alle Projekte gehören ihren Urhebern; Bilder sind verlinkt und stammen aus den angegebenen Quellen (u. a. libretro-thumbnails, Steam, Projekt-Repositories).</p>`;
}

/* ---------------- router ---------------- */
const scrollMemo = new Map();
let currentKey = '';

function route() {
  const hash = location.hash.replace(/^#/, '') || '/';
  const [, a = '', ...rest] = hash.split('/');
  const b = decodeURIComponent(rest.join('/'));
  let html, tab = 'discover';
  if (a === 'spiel') { if (state.lastGame !== b) { state.gameTab = 'versions'; state.dualOnly = false; state.openWay = null; } state.lastGame = b; html = viewGame(b); tab = null; }
  else if (a === 'franchises') { html = viewFranchises(); tab = 'franchises'; }
  else if (a === 'franchise') { html = viewFranchise(b); tab = 'franchises'; }
  else if (a === 'projekte') { html = viewProjects(); tab = 'projects'; }
  else if (a === 'projekt') { html = viewProject(b); tab = 'projects'; }
  else if (a === 'neu') { html = viewNews(); tab = 'news'; }
  else if (a === 'merkliste') { html = viewFavs(); tab = 'favs'; }
  else if (a === 'info') { html = viewInfo(); tab = 'info'; }
  else if (a === 'filter') { state.chips = new Set([b]); state.q = ''; $('#q').value = ''; state.limit = PAGE; history.replaceState({ d: depth }, '', '#/'); html = viewDiscover(); }
  else html = viewDiscover();
  scrollMemo.set(currentKey, window.scrollY);
  currentKey = hash;
  stopPreview();
  $('#view').innerHTML = html;
  renderTabs(tab);
  window.scrollTo(0, scrollMemo.get(hash) || 0);
}

function rerender() { const y = window.scrollY; stopPreview(); $('#view').innerHTML = viewDiscover(); window.scrollTo(0, y); }
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
    lb.innerHTML = `<img class="${pixel}" src="${esc(s.url)}" alt="${esc(s.caption || '')}" referrerpolicy="no-referrer">
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
});

let qTimer;
document.addEventListener('input', (e) => {
  if (e.target.id !== 'q') return;
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    state.q = e.target.value; state.limit = PAGE;
    const h = location.hash.replace(/^#/, '') || '/';
    if (h === '/' || h.startsWith('/franchises') || h.startsWith('/projekte')) rerenderList(h);
    else location.hash = '#/';
  }, 120);
});
function rerenderList(h) {
  const v = h.startsWith('/franchises') ? viewFranchises : h.startsWith('/projekte') ? viewProjects : viewDiscover;
  $('#view').innerHTML = v();
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
      a: pressed(0), b: pressed(1), l: pressed(4), r: pressed(5), start: pressed(9),
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
    if (edge('start')) $('#q').focus();
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
  if ('serviceWorker' in navigator && location.protocol === 'https:' && !window.ATLAS_EMBEDDED) navigator.serviceWorker.register('sw.js').catch(() => {});
  document.addEventListener('visibilitychange', () => { if (!document.hidden) checkUpdate(false); });
  if (navigator.getGamepads && [...navigator.getGamepads()].some(Boolean)) { pads.running = true; requestAnimationFrame(pollPads); }
}
init();
