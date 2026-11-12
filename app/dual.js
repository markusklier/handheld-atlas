/* Handheld Atlas – zwei Bildschirme (Atlas-App auf Geräten wie dem AYN Thor). Lädt nach app.js und setup.js.

   Ein Hauptbildschirm, ein Begleiter – nie zwei gleichberechtigte Fenster:
     Hauptbildschirm (standardmäßig oben)  – die ganze App wie auf einem Bildschirm. NUR hier wird bedient:
                                             Controller, Fokus, Verlauf, Scroll-Position.
     Begleiter       (standardmäßig unten) – zeigt, was zum Hauptbildschirm passt: große Vorschau des markierten Spiels,
                                             Bilder des geöffneten Spiels, Live-Werte der Messfahrt. Er hat keinen eigenen
                                             Verlauf, keinen Fokus und bekommt keine Controller-Taste. Antippen wirkt als
                                             Fernbedienung („Spiel ansehen“, Weg wählen, Bilder blättern).
   Dadurch kann es weder zwei offene Spiele noch zwei bediente Bildschirme geben: Der Begleiter wird bei jeder Änderung
   vollständig aus dem Zustand des Hauptbildschirms abgeleitet (dualShow).
   Controller: L2/R2 blättern die Bilder des Begleiters, Select tauscht die Bildschirme. Die App schickt jede Taste an
   den Hauptbildschirm (android/…/InputRouter.kt); mit einer älteren App liest nur der Hauptbildschirm das Gamepad.
   Tauschen und Aus-/Einschalten: Der neue Hauptbildschirm übernimmt Verlauf, Filter, Scroll-Position und Fokus
   (dualPrimary im gemeinsamen localStorage). Ohne zweiten Bildschirm (Odin) oder ausgeschaltet: ein Bildschirm, wie gewohnt. */
'use strict';

const D = {
  on: false, capable: false, role: 'single', started: false, router: false, pad: false,
  show: null,          // what the companion shows: { v: 'preview' | 'game' | 'setup', game, way }
  trail: [],           // main screen: hashes of the in-app history (index = depth in app.js)
  nextY: null, takeFocus: null, cpShown: false, slideTimer: null, pausedUntil: 0,
  swap: !!store.get('dualSwap', false),   // kept in memory and sent with every message: localStorage reaches the other window with a delay
  peer: null,          // companion: the last state the main screen sent (for the take-over)
};
const dualOn = () => D.on;
const dualRole = () => D.role;
const dec = (s) => { try { return decodeURIComponent(s); } catch { return s; } };
function computeRole() {
  if (!D.on) return 'single';
  return (native.screen === 'main') !== D.swap ? 'primary' : 'companion';
}
/* Gamepad API in the page: in the browser, or with an older app without the controller router – and never in the companion */
const padsAllowed = () => !native.available || (!D.router && D.role !== 'companion');

/* ---------- Nachrichten zwischen den beiden Fenstern (über die App und zusätzlich direkt) ---------- */
const dualChannel = native.available && 'BroadcastChannel' in window ? new BroadcastChannel('atlas-dual') : null;
const dualSeen = [];
function dualSend(msg) {
  if (!native.available) return;
  msg._id = Math.random().toString(36).slice(2);
  native.call('relay', msg).catch(() => {});
  try { dualChannel?.postMessage(msg); } catch { /* closed */ }
}
function dualReceive(msg) {
  if (!msg || !msg._id || dualSeen.includes(msg._id)) return;
  dualSeen.push(msg._id);
  if (dualSeen.length > 60) dualSeen.shift();
  if (msg.state) D.peer = msg.state;
  if (msg.swap) { D.swap = !!msg.value; return setRole(D.on); }   // the other window swapped the screens
  if (!D.on) return;
  if (D.role === 'companion') {
    if (msg.show) cpShow(msg.show);
    else if (msg.slide) cpStep(msg.slide, true);
    return;
  }
  // main screen
  if (msg.hello) dualPublish(true);
  else if (msg.key) padInput(msg.key, !!msg.repeat);
  else if (msg.swapRequest) dualSwap();
  else if (msg.toggleRequest) dualToggle();
  else if (msg.open) dualOpen(msg.open, msg.way);
}
native.on('relay', dualReceive);
if (dualChannel) dualChannel.onmessage = (e) => dualReceive(e.data);

/* ---------- Rollen ---------- */
function dualSetup() {              // setup.js calls this whenever the app reports its screens
  D.capable = native.available && !!su.info?.dual;
  const on = D.capable && !!su.info?.second;
  store.set('dualLast', on);
  setRole(on);
}
function setRole(on) {
  const before = D.started ? D.role : null;
  D.on = on;
  D.role = computeRole();
  document.body.classList.toggle('dual', D.on);
  document.body.classList.toggle('dual-primary', D.role === 'primary');
  document.body.classList.toggle('dual-companion', D.role === 'companion');
  registerInput();
  dualHeader();
  if (before === D.role) { if (D.role === 'companion') cpControls(); return; }
  D.started = true;
  if (D.role === 'companion') return cpEnter();
  const handoff = D.peer || store.get('dualPrimary', null);
  D.peer = null;
  if (before === 'companion' || (before === null && handoff?.handoff && Date.now() - handoff.handoff < 20000)) takeOver(handoff);
  else if (D.cpShown) route();                              // the first guess was "companion": show the app after all
  D.cpShown = false;
  cpStop();
  if (D.role === 'primary') { setTimeout(() => dualPublish(true), 60); if (before === 'companion') toast('Hier bedienst du jetzt – der andere Bildschirm zeigt Bilder und Vorschau.', 2600); }
}
function registerInput() {
  if (!native.available) return;
  const role = D.role;
  native.call('input', { role }).then(() => { D.router = true; })
    // App 0.1.10: router with the old role names; its target stays on the main screen
    .catch(() => native.call('inputReady', { role: role === 'companion' ? 'stage' : role === 'primary' ? 'browse' : 'single' })
      .then(() => { D.router = true; if (role !== 'companion') native.call('setInput', { role: 'browse' }).catch(() => {}); })
      .catch(() => { D.router = false; }));   // older app: the main screen reads the gamepad itself (padsAllowed)
}

/* ---------- Hauptbildschirm: Zustand merken (für Tauschen, Aus/An) ---------- */
function savePrimary(handoff) {
  if (!D.capable || D.role === 'companion') return null;
  const p = {
    trail: D.trail.slice(-30), y: Math.round(scrollY), focus: focusKey(document.activeElement), pad: D.pad,
    filters: { q: state.q, chips: [...state.chips], platform: state.platform, sort: state.sort, limit: state.limit },
    game: { lastGame: state.lastGame || null, gameTab: state.gameTab || null, openWay: state.openWay || null, dualOnly: !!state.dualOnly },
    handoff: handoff ? Date.now() : 0,
  };
  store.set('dualPrimary', p);
  return p;
}
let saveTimer = null;
addEventListener('scroll', () => {
  if (!D.capable || D.role === 'companion') return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(savePrimary, 250);
}, { passive: true });

/* This window is the main screen now: continue exactly where the other one was. */
function takeOver(p) {
  const trail = p?.trail?.length ? p.trail : ['#/'];
  if (p?.filters) {
    Object.assign(state, { q: p.filters.q || '', chips: new Set(p.filters.chips || []), platform: p.filters.platform || '', sort: p.filters.sort || 'relevance', limit: p.filters.limit || PAGE });
    $('#q').value = state.q;
  }
  if (p?.game) Object.assign(state, p.game);
  history.replaceState({ d: 0 }, '', trail[0]);
  for (let i = 1; i < trail.length; i++) history.pushState({ d: i }, '', trail[i]);
  depth = trail.length - 1;
  D.trail = trail.slice();
  D.nextY = p?.y ?? 0;
  D.takeFocus = p?.pad ? p.focus || 'main a, main button' : null;
  if (p?.handoff) store.set('dualPrimary', { ...p, handoff: 0 });
  route();
}

/* called by route() in app.js: explicit scroll position for the next page (take-over) */
function dualScrollGet() {
  if (D.nextY == null) return undefined;
  const y = D.nextY; D.nextY = null; return y;
}
/* called by route() in app.js after every page change */
function dualRouted() {
  if (!native.available || D.role === 'companion') return;
  for (let i = 0; i < depth; i++) D.trail[i] ??= '#/';
  D.trail.length = depth;
  D.trail[depth] = location.hash || '#/';
  if (D.takeFocus) {
    const sel = D.takeFocus; D.takeFocus = null;
    D.pad = true;
    document.body.classList.add('kbd-nav');
    requestAnimationFrame(() => { let el = null; try { el = document.querySelector(sel); } catch { /* stale selector */ } (el || document.querySelector('main a, main button'))?.focus({ preventScroll: true }); });
  }
  savePrimary();
  dualPublish();
}

/* ---------- Hauptbildschirm → Begleiter: was soll er zeigen? ---------- */
function dualCurrentWay(g) {
  const d = document.activeElement?.closest?.('details.way') || (D.wayHint?.isConnected ? D.wayHint : null);
  if (d) return waysFor(g).find((w) => wayId(w.key) === d.id)?.key || null;
  return state.openWay || null;
}
function dualWant(hint) {
  const h = location.hash || '#/';
  let m = /^#\/spiel\/([^/]+)/.exec(h);
  if (m) { const g = DB.byId.get(dec(m[1])); return g ? { v: 'game', game: g.id, way: dualCurrentWay(g) } : null; }
  m = /^#\/einrichten\/([^/]+)\/(.+)$/.exec(h);
  if (m) return DB.byId.has(dec(m[1])) ? { v: 'setup', game: dec(m[1]), way: dec(m[2]) } : null;
  const a = (hint || document.activeElement)?.closest?.('a[href^="#/spiel/"], [data-game]');
  if (a) {
    const id = a.dataset.game || dec((a.getAttribute('href') || '').split('/')[2] || '');
    if (DB.byId.has(id)) return { v: 'preview', game: id, way: a.dataset.gotoWay || null };
  }
  // a list without a marked game: keep the last game – as a preview (with „Spiel ansehen“)
  const last = D.show || store.get('dualShow', null);
  return last && DB.byId.has(last.game) ? (last.v === 'preview' ? last : { v: 'preview', game: last.game, way: null }) : null;
}
function dualPublish(force, hint, explicit) {
  if (!D.on || D.role !== 'primary') return;
  const want = explicit || dualWant(hint);
  if (!want) return;
  const same = D.show && D.show.v === want.v && D.show.game === want.game && (D.show.way || null) === (want.way || null);
  if (same && !force) return;
  D.show = want;
  store.set('dualShow', want);
  dualSend({ show: want });
  dualMark();
}
/* the card of the game the companion shows (touch users see what "is on" the other screen) */
function dualMark() {
  document.querySelectorAll('.card.marked').forEach((c) => c.classList.remove('marked'));
  if (D.on && D.role === 'primary' && D.show?.v === 'preview') document.querySelector(`.card[data-game="${CSS.escape(D.show.game)}"]`)?.classList.add('marked');
}
/* dualShow(id): show a game on the companion (also used by the simulator) */
function dualShow(id) { if (DB.byId.has(id)) dualPublish(true, null, { v: 'preview', game: id, way: null }); }

let publishTimer = null;
const publishSoon = (hint) => { clearTimeout(publishTimer); publishTimer = setTimeout(() => dualPublish(false, hint), 130); };
document.addEventListener('focusin', (e) => { if (D.on && D.role === 'primary') publishSoon(e.target); });
document.addEventListener('toggle', (e) => {
  if (!D.on || D.role !== 'primary' || !e.target.matches?.('details.way') || !e.target.open) return;
  D.wayHint = e.target;
  publishSoon();
}, true);
document.addEventListener('pointerdown', (e) => {
  D.pad = false;
  if (!D.on || D.role !== 'primary') return;
  const a = e.target.closest?.('a[href^="#/spiel/"]');       // touch: the game under the finger appears on the companion
  if (a && !/^#\/(spiel|einrichten)\//.test(location.hash)) publishSoon(a);
}, true);

/* the companion asks the main screen to open something (tap on „Spiel ansehen“ or on a way) */
function dualOpen(hash, way) {
  if (!/^#\/(spiel|einrichten)\//.test(hash)) return;
  if (way && location.hash === hash) {
    state.openWay = way; state.gameTab = 'versions';
    route();
    const el = document.getElementById(wayId(way));
    if (el) { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); if (D.pad) el.querySelector('summary')?.focus({ preventScroll: true }); D.wayHint = el; dualPublish(); }
    return;
  }
  if (way) state.pendingWay = way;
  if (location.hash !== hash) location.hash = hash;
}

/* ---------- Controller ---------- */
/* padInput in app.js asks here first. true = handled. */
function dualInput(key, repeat) {
  if (D.role === 'companion') { dualSend({ key, repeat }); return true; }   // a stray key: the main screen handles it
  D.pad = true;
  if (key === 'l2' || key === 'r2') {
    if (D.on) dualSend({ slide: key === 'l2' ? -1 : 1 });
    else { const c = document.activeElement?.closest?.('.card'); if (c) stepPreview(c, key === 'l2' ? -1 : 1); }
    return true;
  }
  if (key === 'select') { if (D.on && !repeat) dualSwap(); return D.on; }
  return false;
}
/* keyboard in the companion window (or keys an old app delivers there): forward to the main screen */
const DUAL_KEYS = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Enter: 'a', Escape: 'b', Backspace: 'b', GoBack: 'b', BrowserBack: 'b' };
document.addEventListener('keydown', (e) => {
  if (D.role !== 'companion' || !DUAL_KEYS[e.key]) return;
  e.preventDefault(); e.stopImmediatePropagation();
  dualSend({ key: DUAL_KEYS[e.key], repeat: e.repeat });
}, true);

/* ---------- Kopfzeile: Tauschen und Dual Screen an/aus ---------- */
const dualButtons = () => `${D.on ? `<button class="dual-btn" data-dual="swap" title="Bildschirme tauschen (Select)">${icon('swap')}<span class="lbl">Tauschen</span></button>` : ''}
  <button class="dual-switch${D.on ? ' on' : ''}" data-dual="toggle" role="switch" aria-checked="${D.on}" title="Zweiten Bildschirm ${D.on ? 'ausschalten' : 'einschalten'}">${icon('dual')}<span class="lbl">Dual Screen</span><i aria-hidden="true"></i></button>`;
function dualHeader() {
  let bar = document.getElementById('dual-ctl');
  if (!D.capable) { bar?.remove(); return; }
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'dual-ctl';
    document.querySelector('.top').appendChild(bar);
  }
  const had = document.activeElement?.closest?.('#dual-ctl') ? document.activeElement.dataset.dual : null;
  bar.innerHTML = dualButtons();
  if (had) bar.querySelector(`[data-dual="${had}"]`)?.focus({ preventScroll: true });
}
let requestTimer = null;
function dualSwap() {
  if (!D.on) return;
  if (D.role === 'companion') {                     // the main screen swaps (it knows where it is)
    const was = D.swap;
    dualSend({ swapRequest: true });
    clearTimeout(requestTimer);
    requestTimer = setTimeout(() => { if (D.swap === was) dualSwapNow(null); }, 800);   // it did not answer: swap anyway
    return;
  }
  dualSwapNow(savePrimary());
}
function dualSwapNow(state) {
  D.swap = !D.swap;
  store.set('dualSwap', D.swap);
  dualSend({ swap: true, value: D.swap, state });
  setRole(D.on);
}
async function dualToggle() {
  const on = !D.on;
  if (D.role === 'companion') {
    dualSend({ toggleRequest: true });
    clearTimeout(requestTimer);
    requestTimer = setTimeout(() => { if (D.on) native.call('second', { open: false }).catch(() => {}); }, 800);
    return;
  }
  dualSend({ state: savePrimary(true) });           // whichever window stays or arrives continues here
  try { await native.call('second', { open: on }); } catch (e) { toast(esc(e.message)); }
  setTimeout(() => suLoadInfo(), 500);
}

/* =====================================================================================================
   Begleiter
   ===================================================================================================== */
function cpEnter() {
  D.cpShown = true;
  $('#lightbox').hidden = true;
  document.activeElement?.blur?.();
  D.show = store.get('dualShow', null);
  cpRender();
  dualSend({ hello: true });                        // the main screen answers with its current state
}
/* route() in app.js asks first: the companion never shows a page of its own. */
function dualCompanion() {
  if (D.role !== 'companion') return false;
  if (!D.cpShown || !document.querySelector('.cp')) { D.cpShown = true; D.show = D.show || store.get('dualShow', null); cpRender(); }
  return true;
}
function cpShow(next) {
  const cur = D.show;
  D.show = next;
  const el = document.querySelector('.cp');
  if (el && cur && cur.v === next.v && cur.game === next.game) {       // same game: only the way changed
    if ((cur.way || null) !== (next.way || null)) cpFocusWay(next.way);
    return;
  }
  cpRender();
}

const cpImg = (url, cls = '') => {
  const src = fullSrc(url);
  return `<img class="${cls}" src="${esc(src)}"${src !== url ? ` data-fb="${esc(url)}"` : ''} alt="" decoding="async" draggable="false" referrerpolicy="no-referrer" onload="cpFit(this)" onerror="cpBroken(this)">`;
};
/* A slide picture fills its place as far as its shape allows – small pixel art is scaled up, the frame hugs the picture. */
function cpFit(img) {
  const slide = img.closest('.cp-slide');
  if (!slide || !img.naturalWidth) return;
  const cs = getComputedStyle(slide);
  const w = slide.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), h = slide.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  const f = Math.min(w / img.naturalWidth, h / img.naturalHeight);
  img.style.width = Math.floor(img.naturalWidth * f) + 'px';
  img.style.height = Math.floor(img.naturalHeight * f) + 'px';
  img.classList.add('fit');
  if (+slide.dataset.i === cpIndex()) cpSync();
}
/* A picture that cannot be loaded leaves the gallery (small picture, counter and caption follow). */
function cpBroken(img) {
  if (img.dataset.fb) { img.src = img.dataset.fb; delete img.dataset.fb; return; }
  const cover = img.closest('.cp-cover');
  if (cover) return cover.remove();
  const slide = img.closest('.cp-slide'), track = slide?.parentNode;
  if (!track) return;                                // small pictures leave together with their slide
  document.querySelectorAll('.cp-thumb')[[...track.children].indexOf(slide)]?.remove();
  slide.remove();
  const n = track.children.length;
  [...track.children].forEach((el, k) => { el.dataset.i = k; });
  document.querySelectorAll('.cp-thumb').forEach((el, k) => { el.dataset.cpThumb = k; });
  if (n < 2) { document.querySelectorAll('.cp-nav, .cp-strip, .cp-count, .cp-keys').forEach((el) => el.remove()); document.querySelector('.cp')?.classList.add('cp-single'); cpStop(); }
  else { const c = document.querySelector('.cp-count'); if (c) c.innerHTML = `<b>1</b> / ${n}`; }
  if (!n) {
    const g = DB.byId.get(D.show?.game);
    document.querySelector('.cp-cap')?.remove();
    track.innerHTML = `<figure class="cp-slide empty"><span class="ph" style="--h:${hue(g?.franchise || g?.title || '')}">${esc(g?.title || '')}</span></figure>`;
  }
  cpSync();
}

/* Pictures for the companion: the way in focus first, then dual screen, the original game, other ways, mods. */
function cpSlides(g, show) {
  const out = [], seen = new Set();
  const add = (s, o) => { if (s?.url && !seen.has(s.url)) { seen.add(s.url); out.push({ url: s.url, ...o }); } };
  const dualR = (r) => !!r.features?.includes('dual-screen');
  const route = (r) => { for (const s of r.screenshots || []) add(s, { title: r.name, sub: s.caption && s.caption !== r.name ? s.caption : '', dual: dualR(r), way: 'r:' + r.id }); };
  const first = show.way?.startsWith('r:') ? g.routes.find((r) => 'r:' + r.id === show.way) : null;
  if (first) route(first);
  const originals = () => { for (const s of g.screenshots) add(s, { title: s.caption === 'Titelbild' ? 'Titelbild' : 'Original', sub: '' }); };
  if (!device().dualScreen) originals();
  for (const r of g.routes) if (dualR(r)) route(r);
  originals();
  for (const r of g.routes) route(r);
  for (const m of g.mods) for (const s of m.screenshots || []) add(s, { title: 'Mod · ' + m.name, sub: s.caption || '' });
  return out.slice(0, 16);
}

function cpHTML(show) {
  const g = show && DB.byId.get(show.game);
  if (!g) return cpWelcome();
  let slides = cpSlides(g, show);
  const coverOnly = !slides.length && !!g.cover;
  if (coverOnly) slides = [{ url: g.cover.url, title: 'Cover', sub: '' }];
  const ways = waysFor(g).filter((w) => w.fits && w.r?.status !== 'archived').sort((a, b) => b.score - a.score);
  const way = show.way ? ways.find((w) => w.key === show.way) || waysFor(g).find((w) => w.key === show.way) : null;
  const year = versionsOf(g).find((v) => v.type === 'original')?.year || versionsOf(g)[0]?.year;
  const many = slides.length > 1;
  const mode = show.v === 'game' ? ['image', 'Bilder'] : show.v === 'setup' ? ['wrench', 'Einrichten'] : ['compass', 'Vorschau'];
  const cap = (s) => `${s.dual ? icon('dual') : ''}<b>${esc(s.title)}</b>${s.sub ? `<span>${esc(s.sub)}</span>` : ''}`;

  let info;
  if (show.v === 'preview') {
    const top = ways[0];
    const dualWays = ways.filter(isDual);
    info = `<div class="cp-info cp-info-preview">
      ${g.cover && !coverOnly ? `<div class="cp-cover">${cpImg(g.cover.url)}</div>` : ''}
      <div class="cp-text">
        <span class="cp-kicker">${esc(g.franchise || '')}${year ? `<i> · ${year}</i>` : ''}</span>
        <h1>${esc(g.title)}</h1>
        <div class="cp-meta"><span class="pfs">${badges(g.platforms, 3)}</span>
          ${dualWays.length ? `<span class="tag dual">${icon('dual')}${dualWays.length === 1 ? esc(dualLabel(dualWays[0])) : dualWays.length + '× Dual Screen'}</span>` : ''}</div>
        ${g.summary ? `<p class="cp-sum">${esc(g.summary)}</p>` : ''}
      </div>
      <div class="cp-foot">
        ${top ? `<div class="cp-best"><span>Empfehlung${ways.length > 1 ? ` · ${ways.length} Wege` : ''}</span><b>${esc(top.name)}</b>${top.best ? `<span class="rating ${RANK_CLASS(top.best.rank)}">${esc(top.best.ratingDe || top.best.rating)}</span>` : ''}</div>`
          : `<div class="cp-best"><span>Spielwege</span><b>${g.platforms.length ? 'Emulation' : 'noch keiner bekannt'}</b></div>`}
        <button class="btn primary cp-open" data-cp-open="#/spiel/${esc(encodeURIComponent(g.id))}">${icon('play')}Spiel ansehen</button>
      </div></div>`;
  } else {
    const chips = ways.slice(0, 10).map((w) => `<button class="cp-way${w.key === show.way ? ' on' : ''}" data-cp-way="${esc(w.key)}">${isDual(w) ? icon('dual') : ''}<span>${esc(w.name)}</span>${w.best ? `<i class="dot ${RANK_CLASS(w.best.rank)}"></i>` : ''}</button>`).join('');
    info = `<div class="cp-info cp-info-game">
      <div class="cp-head">
        ${g.cover && !coverOnly ? `<div class="cp-cover">${cpImg(g.cover.url)}</div>` : ''}
        <div class="cp-text"><span class="cp-kicker">${show.v === 'setup' ? 'Einrichten' : esc(g.franchise || '')}${show.v !== 'setup' && year ? `<i> · ${year}</i>` : ''}</span>
          <h1>${esc(show.v === 'setup' && way ? way.name : g.title)}</h1>
          ${show.v === 'setup' ? `<span class="cp-sub">${esc(g.title)}</span>` : ''}</div>
      </div>
      ${show.v === 'game' && chips ? `<div class="cp-ways" aria-label="Spielwege">${chips}</div>` : ''}
    </div>`;
  }

  return `<section class="cp cp-${show.v}${many ? '' : ' cp-single'}" data-cp="${show.v}" data-cp-game="${esc(g.id)}">
    <div class="cp-bg"${slides[0] ? ` style="background-image:url('${esc(fullSrc(slides[0].url))}')"` : ''}></div>
    ${cpBar(mode, many)}
    <div class="cp-stage">
      <div class="cp-track">${slides.map((s, i) => `<figure class="cp-slide${coverOnly ? ' cover-only' : ''}" data-i="${i}"${s.way ? ` data-way="${esc(s.way)}"` : ''} data-cap="${esc(cap(s))}"${s.dual ? ' data-dual' : ''}>${cpImg(s.url, s.url.includes('libretro-thumbnails') ? 'pixel' : '')}</figure>`).join('')
        || `<figure class="cp-slide empty"><span class="ph" style="--h:${hue(g.franchise || g.title)}">${esc(g.title)}</span></figure>`}</div>
      ${slides.length ? `<span class="cp-cap${slides[0].dual ? ' dual' : ''}">${cap(slides[0])}</span>` : ''}
      ${many ? `<span class="cp-count"><b>1</b> / ${slides.length}</span>
        <button class="cp-nav prev" data-cp-step="-1" tabindex="-1" aria-label="Vorheriges Bild">${icon('back')}</button>
        <button class="cp-nav next" data-cp-step="1" tabindex="-1" aria-label="Nächstes Bild">${icon('back')}</button>` : ''}
      <div class="cp-live" hidden></div>
    </div>
    ${many ? `<div class="cp-strip">${slides.map((s, i) => `<button class="cp-thumb${i ? '' : ' on'}${s.dual ? ' dual' : ''}" data-cp-thumb="${i}" tabindex="-1" aria-label="Bild ${i + 1}">${cpImg(s.url, s.url.includes('libretro-thumbnails') ? 'pixel' : '')}</button>`).join('')}</div>` : ''}
    ${info}
  </section>`;
}
function cpBar(mode, many) {
  return `<header class="cp-bar">
    <span class="cp-mode">${icon(mode[0])}${esc(mode[1])}</span>
    ${many ? `<span class="cp-keys"><kbd>L2</kbd><kbd>R2</kbd><span>Bilder</span></span>` : ''}
    <span class="cp-ctl">${dualButtons()}</span></header>`;
}
function cpControls() { const c = document.querySelector('.cp-ctl'); if (c) c.innerHTML = dualButtons(); }
function cpWelcome() {
  const picks = DB.games.filter((g) => g._dual && g.cover).sort((a, b) => b.routes.length - a.routes.length).slice(0, 14);
  const where = native.screen === 'companion' ? 'oben' : 'unten';   // the main screen is the other one
  return `<section class="cp cp-welcome" data-cp="welcome">
    ${cpBar(['dual', 'Zwei Bildschirme'], false)}
    <div class="cp-hello">
      <img src="icon.svg" alt="" width="44" height="44">
      <h1>Markiere ${where} ein Spiel</h1>
      <p>Hier erscheint es groß – mit Cover und Bildern zum Durchwischen.</p>
      <p class="cp-legend"><span><kbd>L2</kbd><kbd>R2</kbd> Bilder blättern</span><span><kbd>Select</kbd> Bildschirme tauschen</span></p>
    </div>
    ${picks.length ? `<div class="cp-picks" aria-label="Dual-Screen-Spiele">${picks.map((g) => `<button class="cp-pick" data-cp-pick="${esc(g.id)}" title="${esc(g.title)}" tabindex="-1"><img src="${esc(g.cover.url)}" alt="${esc(g.title)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()"></button>`).join('')}</div>` : ''}
  </section>`;
}
function cpRender() {
  if (D.role !== 'companion' || !DB.games.length) return;
  cpStop();
  const view = document.getElementById('view');
  view.innerHTML = cpHTML(D.show);
  scrollTo(0, 0);
  const track = cpTrack();
  if (track) {
    track.addEventListener('scroll', () => { clearTimeout(track._t); track._t = setTimeout(cpSync, 70); }, { passive: true });
    track.addEventListener('pointerdown', cpPause, { passive: true });
    if (track.children.length > 1) D.slideTimer = setInterval(() => { if (!document.hidden && Date.now() > D.pausedUntil) cpStep(1, false); }, 6000);
  }
  cpLive();
}
function cpStop() { clearInterval(D.slideTimer); D.slideTimer = null; }
const cpTrack = () => document.querySelector('.cp-track');
const cpPause = () => { D.pausedUntil = Date.now() + 25000; };
function cpIndex(track = cpTrack()) { return track ? Math.round(track.scrollLeft / Math.max(1, track.clientWidth)) : 0; }
function cpStep(d, user) {
  const track = cpTrack();
  const n = track?.children.length || 0;
  if (n < 2) return;
  cpGoto((cpIndex(track) + d + n) % n, user);
}
function cpGoto(i, user) {
  const track = cpTrack();
  if (!track) return;
  if (user) cpPause();
  const far = Math.abs(i - cpIndex(track)) > 1;          // wrap-around or jump: no long ride through all pictures
  track.scrollTo({ left: i * track.clientWidth, behavior: far ? 'auto' : 'smooth' });
  if (far) cpSync();
}
function cpSync() {
  const track = cpTrack();
  if (!track) return;
  const i = cpIndex(track);
  const slide = track.children[i];
  document.querySelectorAll('.cp-thumb').forEach((b, k) => b.classList.toggle('on', k === i));
  const thumb = document.querySelector('.cp-thumb.on'), strip = thumb?.parentNode;
  if (strip) strip.scrollTo({ left: thumb.offsetLeft - (strip.clientWidth - thumb.offsetWidth) / 2, behavior: 'smooth' });
  const n = document.querySelector('.cp-count b');
  if (n) n.textContent = i + 1;
  const cap = document.querySelector('.cp-cap');
  if (cap && slide?.dataset.cap != null) { cap.classList.toggle('dual', slide.hasAttribute('data-dual')); cap.innerHTML = slide.dataset.cap; }
  const src = slide?.querySelector('img')?.currentSrc;
  if (src && !slide.classList.contains('broken')) document.querySelector('.cp-bg')?.style.setProperty('background-image', `url('${src.replace(/'/g, '%27')}')`);
}
/* the way in focus on the main screen changed: mark it and jump to its first picture */
function cpFocusWay(key) {
  document.querySelectorAll('.cp-way').forEach((b) => b.classList.toggle('on', b.dataset.cpWay === key));
  const on = document.querySelector('.cp-way.on');
  on?.parentNode.scrollTo({ left: on.offsetLeft - 16, behavior: 'smooth' });
  if (!key) return;
  const slide = cpTrack()?.querySelector(`.cp-slide[data-way="${CSS.escape(key)}"]`);
  if (slide) cpGoto(+slide.dataset.i, true);
}
/* Messfahrt: big live values over the pictures */
function cpLive() {
  const box = document.querySelector('.cp-live');
  if (!box) return;
  const l = typeof su !== 'undefined' ? su.live : null;
  box.hidden = !l;
  if (l) box.innerHTML = suLiveHTML(l);
}
native.on('measure', () => { if (D.role === 'companion') setTimeout(cpLive, 0); });
addEventListener('resize', () => { const t = cpTrack(); if (t) { t.scrollLeft = cpIndex(t) * t.clientWidth; t.querySelectorAll('img').forEach(cpFit); cpSync(); } });

/* ---------- Ereignisse ---------- */
document.addEventListener('click', (e) => {
  const ctl = e.target.closest('[data-dual]');
  if (ctl) { e.preventDefault(); e.stopPropagation(); if (ctl.dataset.dual === 'swap') dualSwap(); else dualToggle(); return; }
  if (D.role !== 'companion') return;
  e.preventDefault(); e.stopPropagation();           // the companion is a remote control: nothing navigates here
  const t = e.target.closest('[data-cp-step], [data-cp-thumb], [data-cp-open], [data-cp-way], [data-cp-pick], .cp-slide');
  if (!t) return;
  if (t.dataset.cpStep) cpStep(+t.dataset.cpStep, true);
  else if (t.dataset.cpThumb) cpGoto(+t.dataset.cpThumb, true);
  else if (t.dataset.cpOpen) dualSend({ open: t.dataset.cpOpen });
  else if (t.dataset.cpWay) { cpFocusWay(t.dataset.cpWay); dualSend({ open: '#/spiel/' + encodeURIComponent(D.show.game), way: t.dataset.cpWay }); }
  else if (t.dataset.cpPick) cpShow({ v: 'preview', game: t.dataset.cpPick, way: null });
  else {                                             // tap the picture: left third back, otherwise on
    const r = t.getBoundingClientRect();
    cpStep(e.clientX < r.left + r.width / 3 ? -1 : 1, true);
  }
}, true);

/* first guess before the app has reported its screens (the second window only exists in dual mode) */
if (native.available) {
  D.on = native.screen === 'companion' || !!store.get('dualLast', false);
  D.capable = D.on;
  D.role = computeRole();
  document.body.classList.toggle('dual', D.on);
  document.body.classList.toggle('dual-primary', D.role === 'primary');
  document.body.classList.toggle('dual-companion', D.role === 'companion');
  registerInput();
}
