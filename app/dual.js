/* Handheld Atlas – zwei Bildschirme (Atlas-App auf Geräten wie dem AYN Thor). Lädt nach app.js und setup.js.

   Feste Rollen, ein Controller:
     Stöbern (standardmäßig oben)  – Entdecken, Suche, Reihen, Neu, Info … zeigt NIE eine Spielseite.
     Bühne   (standardmäßig unten) – nur das Spiel: große Vorschau → Spielseite → Einrichten. Zeigt NIE Listen.
   Der Router hält das ein (dualGuard): was nicht zur Rolle passt, geht ans andere Fenster. Damit gibt es nie zwei
   offene Spiele und nie zwei Listen.
   Controller: Die App leitet jede Taste an genau ein Fenster (android/…/InputRouter.kt) – an die Rolle, die `setInput`
   gewählt hat. Spiel ansehen → Bühne, Zurück aus dem Spiel → Stöbern, Select wechselt, Antippen holt den Controller.
   Gemeinsamer Zustand (localStorage, beide Fenster): wo jede Rolle steht und wie weit gescrollt ist – nach dem
   Tauschen oder Aus-/Einschalten geht es genau dort weiter. Ohne zweiten Bildschirm (oder ausgeschaltet, z. B. auf
   einem Odin) ist alles wie gewohnt auf einem Bildschirm. */
'use strict';

const D = {
  on: false, role: 'single', input: 'browse', started: false, router: false, focused: native.screen !== 'companion',
  pad: false, nextY: null, slideTimer: null, pausedUntil: 0,
};
const STAGE_ONLY = /^#\/(spiel|einrichten|vorschau)\//;
const ANY_ROLE = /^#\/projekt\//;
const dualOn = () => D.on;
const dualRole = () => D.role;
const enc = encodeURIComponent;
const lastGame = () => store.get('lastGame', '') || '';
const dstate = () => store.get('dualState', {});
const fitsRole = (role, h) => ANY_ROLE.test(h) || (role === 'stage') === STAGE_ONLY.test(h);
function computeRole() {
  if (!D.on) return 'single';
  return (native.screen === 'main') !== !!store.get('dualSwap', false) ? 'browse' : 'stage';
}
/* Gamepad API in the page: only in the browser, or with an older app without the controller router */
const padsAllowed = () => !native.available || (!D.router && D.focused);

/* ---------- gemeinsamer Zustand ---------- */
function saveRole() {
  if (D.role === 'single') return;
  const h = location.hash || '#/';
  if (!fitsRole(D.role, h)) return;
  const st = dstate();
  st[D.role] = { hash: h, y: Math.round(scrollY) };
  store.set('dualState', st);
}
function dualScrollSet(hash, y) {
  if (!D.on || !hash || !fitsRole(D.role, '#' + hash)) return;
  const m = store.get('dualScroll', {});
  m[D.role + '|' + hash] = Math.round(y);
  const keys = Object.keys(m);
  if (keys.length > 80) delete m[keys[0]];
  store.set('dualScroll', m);
}
/* scroll position for route() in app.js: explicit (dualGo) → remembered per role → app.js default */
function dualScrollGet(hash) {
  if (D.nextY != null) { const y = D.nextY; D.nextY = null; return y; }
  if (!D.on) return undefined;
  if (hash.startsWith('/vorschau/')) return 0;
  return store.get('dualScroll', {})[D.role + '|' + hash];
}
let saveTimer = null;
addEventListener('scroll', () => {
  if (!D.on) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => { saveRole(); dualScrollSet((location.hash || '#/').slice(1) || '/', scrollY); }, 200);
}, { passive: true });

/* called by route() in app.js before the old page goes and after the new one is shown */
function dualLeave(hash, y) { clearTimeout(D.pvSwap); document.getElementById('view')?.classList.remove('pv-fade'); dualScrollSet(hash, y); }
function dualRouted() {
  const m = /^#\/(?:spiel|vorschau|einrichten)\/([^/]+)/.exec(location.hash);
  if (m && decodeURIComponent(m[1])) store.set('lastGame', decodeURIComponent(m[1]));
  if (location.hash.startsWith('#/vorschau/')) pvStart(); else pvStop();
  saveRole();
  if (D.on && D.role === 'browse') markCard(lastGame());
  if (D.on && D.input === D.role) setTimeout(dualFocus, 40);
}

/* ---------- Controller-Ziel ---------- */
const relay = (data) => (D.on ? native.call('relay', data).catch(() => {}) : Promise.resolve());
function setInput(role) {
  if (!D.on) return;
  const changed = D.input !== role;
  D.input = role;
  markInput();
  if (changed) native.call('setInput', { role, pad: D.pad }).catch(() => {});
}
function markInput() {
  const here = D.on && D.input === D.role;
  document.body.classList.toggle('input-here', here);
  document.body.classList.toggle('input-away', D.on && !here);
  if (here) setTimeout(dualFocus, 40);
  else if (D.on && document.activeElement && document.activeElement !== document.body && !document.activeElement.matches('input')) document.activeElement.blur();
}

/* ---------- Rollen ---------- */
function dualSetup() {
  const before = { on: D.on, role: D.role };
  D.on = native.available && !!su.info?.dual && !!su.info?.second;
  store.set('dualLast', D.on);
  applyRole(before);
}
function applyRole(before) {
  D.role = computeRole();
  document.body.classList.toggle('dual', D.on);
  document.body.classList.toggle('dual-browse', D.role === 'browse');
  document.body.classList.toggle('dual-stage', D.role === 'stage');
  if (native.available) native.call('setRole', { role: D.role }).catch(() => {});
  dualHeader();
  if (D.started && before.on === D.on && before.role === D.role) return markInput();
  D.started = true;
  enterRole(before);
}
/* A window takes over a role and continues where that role was last time. */
function enterRole(before) {
  const here = location.hash || '#/';
  const st = dstate();
  if (D.role === 'single') {
    // dual screen switched off: the main window stays and takes the game that was open on the stage
    // (as a new step, so B leads back to the list you came from)
    document.body.classList.remove('input-here', 'input-away');
    const t = native.screen === 'main' ? store.get('dualOffTarget', null) : null;
    if (t) store.set('dualOffTarget', null);
    if (before.on && t && t !== here) { D.nextY = 0; location.hash = t; }
    else if (here.startsWith('#/vorschau/')) dualGo('#/spiel/' + here.slice(11), 0);
    return;
  }
  if (!before.on) { D.input = ''; setInput('browse'); }      // just switched on: the controller starts on browsing
  if (D.role === 'stage') {
    const t = STAGE_ONLY.test(here) ? here : st.stage?.hash && STAGE_ONLY.test(st.stage.hash) ? st.stage.hash : '#/vorschau/' + enc(lastGame());
    dualGo(t, t === here ? undefined : st.stage?.y ?? 0);
  } else {
    if (STAGE_ONLY.test(here) && !before.on) {   // just switched on with a game open: it moves to the stage
      st.stage = { hash: here.replace(/^#\/vorschau\//, '#/spiel/'), y: Math.round(scrollY) };
      store.set('dualState', st);
      relay({ nav: st.stage.hash, y: st.stage.y });
    }
    const t = !STAGE_ONLY.test(here) && (here !== '#/' || !st.browse) ? here : st.browse?.hash && !STAGE_ONLY.test(st.browse.hash) ? st.browse.hash : '#/';
    dualGo(t, st.browse?.hash === t ? st.browse.y : undefined);
  }
  markInput();
}
function dualGo(hash, y) {
  if (y != null) D.nextY = y;
  history.replaceState(history.state, '', hash);
  route();
}

/* Router guard (first thing route() does): each role shows only its own pages. */
function dualGuard() {
  if (!D.on) return;
  const h = location.hash || '#/';
  if (fitsRole(D.role, h)) return;
  if (D.role === 'browse') {
    if (D.started) showOnStage(h.replace(/^#\/vorschau\//, '#/spiel/'));
    const b = dstate().browse?.hash;
    history.replaceState(history.state, '', b && !STAGE_ONLY.test(b) ? b : '#/');
  } else {
    if (D.started && h !== '#/') { relay({ nav: h }); setInput('browse'); }
    const s = dstate().stage?.hash;
    history.replaceState(history.state, '', s && STAGE_ONLY.test(s) ? s : '#/vorschau/' + enc(lastGame()));
  }
}
function showOnStage(hash, way) {
  const id = decodeURIComponent(hash.split('/')[2] || '');
  if (id) { store.set('lastGame', id); markCard(id); }
  relay({ nav: hash, way: way || null, top: true });
  setInput('stage');
}
function markCard(id) {          // browse: the card of the game that is on the stage
  document.querySelectorAll('.card.marked').forEach((c) => c.classList.remove('marked'));
  if (id) document.querySelector(`.card[data-game="${CSS.escape(id)}"]`)?.classList.add('marked');
}

/* B on the stage: setup → game page → preview (and the controller goes back to browsing). */
function dualBack() {
  if (D.role !== 'stage') return false;
  const m = /^#\/(spiel|einrichten|vorschau|projekt)\/([^/]*)/.exec(location.hash);
  if (!m || m[1] === 'projekt') dualGo('#/spiel/' + enc(lastGame()));
  else if (m[1] === 'einrichten') dualGo('#/spiel/' + m[2]);
  else if (m[1] === 'spiel') { dualGo('#/vorschau/' + m[2], 0); setInput('browse'); }
  else setInput('browse');
  return true;
}

/* Controller keys with a special meaning on two screens (padInput in app.js asks here first). */
function dualInput(key, repeat) {
  if (key === 'back') return D.role === 'stage' && dualBack();   // back gesture on the stage screen
  D.pad = true;
  if (!D.on) return false;
  if (key === 'select') { if (!repeat) setInput(D.input === 'browse' ? 'stage' : 'browse'); return true; }
  if (D.role === 'browse') {
    if (key !== 'a' || repeat) return false;
    const a = document.activeElement?.closest?.('a[href]');
    const href = a?.getAttribute('href') || '';
    if (!STAGE_ONLY.test(href)) return false;
    showOnStage(href.replace(/^#\/vorschau\//, '#/spiel/'), a.dataset.gotoWay);
    return true;
  }
  const preview = location.hash.startsWith('#/vorschau/');
  if (preview && (key === 'l' || key === 'r' || ((key === 'left' || key === 'right') && document.activeElement?.matches('[data-pv-open]')))) {
    pvStep(key === 'left' || key === 'l' ? -1 : 1, true);
    return true;
  }
  if (!preview && (key === 'l' || key === 'r') && !repeat) {
    const tabs = [...document.querySelectorAll('.seg [data-gtab]')];
    if (!tabs.length) return true;
    const i = tabs.findIndex((t) => t.getAttribute('aria-selected') === 'true');
    tabs[(i + (key === 'l' ? -1 : 1) + tabs.length) % tabs.length].click();
    setTimeout(() => document.querySelector('.seg [aria-selected="true"]')?.focus({ preventScroll: true }), 30);
    return true;
  }
  if (key === 'start' && !repeat) { setInput('browse'); relay({ focusSearch: true }); return true; }
  return false;
}
/* The controller arrives: focus something sensible that is on screen. */
function dualFocus() {
  if (!D.pad || D.input !== D.role) return;
  document.body.classList.add('kbd-nav');
  const a = document.activeElement;
  const visible = (el) => { const r = el?.getBoundingClientRect(); return r && r.width && r.bottom > 56 && r.top < innerHeight - 10; };
  if (a && a !== document.body && visible(a) && a.closest('main, .top')) return;
  let el;
  if (D.role === 'browse') el = document.querySelector('.card.marked') || [...document.querySelectorAll('main .card, main a, main button')].find(visible);
  else if (location.hash.startsWith('#/vorschau/')) el = document.querySelector('[data-pv-open]') || document.querySelector('.pv-pick');
  else el = [...document.querySelectorAll('main details > summary, .seg [aria-selected="true"], main .btn:not(.back), main a, main button')].find(visible);
  if (!el) return;
  D.quiet = true;                 // arriving is not choosing: don't send a new preview to the stage
  el.focus({ preventScroll: true });
  D.quiet = false;
  if (!visible(el)) el.scrollIntoView({ block: 'center' });
}

/* ---------- Kopfzeile: Dual Screen an/aus und Tauschen ---------- */
function dualHeader() {
  let bar = document.getElementById('dual-ctl');
  const capable = native.available && !!su.info?.dual;
  if (!capable) { bar?.remove(); return; }
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'dual-ctl';
    document.querySelector('.top').appendChild(bar);
  }
  bar.innerHTML = `${D.on ? `<button class="dual-btn" data-dual="swap" title="Bildschirme tauschen">${icon('swap')}<span class="lbl">Tauschen</span></button>` : ''}
    <button class="dual-switch${D.on ? ' on' : ''}" data-dual="toggle" role="switch" aria-checked="${D.on}" title="Zweiten Bildschirm ${D.on ? 'ausschalten' : 'einschalten'}">${icon('dual')}<span class="lbl">Dual Screen</span><i aria-hidden="true"></i></button>`;
}
function dualSwap() {
  saveRole();
  const before = { on: D.on, role: D.role };
  store.set('dualSwap', !store.get('dualSwap', false));
  relay({ swap: true });
  applyRole(before);
  toast(D.role === 'stage' ? 'Hier ist jetzt die Bühne – das Spiel im Großformat.' : 'Hier stöberst du jetzt.', 2400);
}
async function dualToggle() {
  const on = !D.on;
  saveRole();
  if (!on) {
    const s = dstate().stage?.hash;
    store.set('dualOffTarget', s && /^#\/(spiel|einrichten)\//.test(s) ? s : null);
  }
  try { await native.call('second', { open: on }); } catch (e) { toast(esc(e.message)); }
  setTimeout(() => suLoadInfo(), 500);
}

/* ---------- Bühne: große Vorschau (Bilder zum Wischen und Tippen, Cover, das Wichtigste) ---------- */
function pvImg(url, cls = '') {
  const src = fullSrc(url);
  return `<img class="${cls}" src="${esc(src)}"${src !== url ? ` data-fb="${esc(url)}"` : ''} alt="" decoding="async" referrerpolicy="no-referrer" onload="pvLoaded(this)" onerror="if(this.dataset.fb){this.src=this.dataset.fb;delete this.dataset.fb}else pvBroken(this)">`;
}
/* a landscape "cover" (store banner) is shown wide instead of cropped to a box */
function pvLoaded(img) { const c = img.closest('.pv-cover'); if (c) c.classList.toggle('wide', img.naturalWidth > img.naturalHeight * 1.15); }
/* a picture that does not load leaves the carousel (dot, counter and caption follow) */
function pvBroken(img) {
  const cover = img.closest('.pv-cover');
  if (cover) return cover.remove();
  const slide = img.closest('.pv-slide');
  const track = slide?.parentNode;
  if (!track) return;
  if (track.children.length === 1) { slide.classList.add('broken'); return; }
  const i = [...track.children].indexOf(slide);
  const cap = document.querySelector('.pv-cap');
  if (cap) { const caps = JSON.parse(cap.dataset.caps || '[]'); caps.splice(i, 1); cap.dataset.caps = JSON.stringify(caps); }
  document.querySelectorAll('.pv-dots button')[i]?.remove();
  document.querySelectorAll('.pv-dots button').forEach((b, k) => { b.dataset.pvDot = k; });
  slide.remove();
  const n = track.children.length;
  const count = document.querySelector('.pv-count');
  if (count) count.innerHTML = `<b>1</b> / ${n}`;
  if (n < 2) document.querySelectorAll('.pv-nav, .pv-dots, .pv-count').forEach((e) => e.remove());
  pvSync();
}
function viewPreview(id) {
  const g = DB.byId.get(id);
  if (!g) return dualWelcome();
  let slides = previewSlides(g);
  const coverOnly = !slides.length && g.cover;
  if (coverOnly) slides = [{ url: g.cover.url, label: 'Cover' }];
  const ways = waysFor(g).filter((w) => w.fits && w.r?.status !== 'archived').sort((a, b) => b.score - a.score);
  const top = ways[0];
  const dualWays = ways.filter(isDual);
  const year = versionsOf(g).find((v) => v.type === 'original')?.year || versionsOf(g)[0]?.year;
  const backdrop = slides.find((s) => !s.url.includes('libretro-thumbnails'))?.url || slides[0]?.url;
  const many = slides.length > 1;
  return `<section class="pv" data-preview="${esc(g.id)}">
    ${backdrop ? `<div class="pv-bg" style="background-image:url('${esc(fullSrc(backdrop))}')"></div>` : ''}
    <div class="pv-hero">
      <div class="pv-track">${slides.map((s, i) => `<figure class="pv-slide${coverOnly ? ' cover-only' : ''}" data-i="${i}">${pvImg(s.url, s.url.includes('libretro-thumbnails') ? 'pixel' : '')}</figure>`).join('')
        || `<figure class="pv-slide empty"><span class="ph" style="--h:${hue(g.franchise || g.title)}">${esc(g.title)}</span></figure>`}</div>
      ${slides.length ? `<span class="pv-cap${slides[0].dual ? ' dual' : ''}" data-caps='${esc(JSON.stringify(slides.map((s) => [s.label, !!s.dual])))}'>${slides[0].dual ? icon('dual') : ''}<span>${esc(slides[0].label)}</span></span>` : ''}
      ${many ? `<span class="pv-count"><b>1</b> / ${slides.length}</span>
        <button class="pv-nav prev" data-pv="-1" tabindex="-1" aria-label="Vorheriges Bild">${icon('back')}</button>
        <button class="pv-nav next" data-pv="1" tabindex="-1" aria-label="Nächstes Bild">${icon('back')}</button>
        <div class="pv-dots">${slides.map((_, i) => `<button data-pv-dot="${i}" tabindex="-1" class="${i ? '' : 'on'}" aria-label="Bild ${i + 1}"></button>`).join('')}</div>` : ''}
    </div>
    <div class="pv-card">
      ${g.cover && !coverOnly ? `<div class="pv-cover">${pvImg(g.cover.url)}</div>` : ''}
      <div class="pv-text">
        <span class="pv-franchise">${esc(g.franchise)}${year ? `<span> · ${year}</span>` : ''}</span>
        <h1>${esc(g.title)}</h1>
        <div class="pv-meta"><span class="pfs">${badges(g.platforms, 2)}</span>
          ${dualWays.length ? `<span class="tag dual">${icon('dual')}${dualWays.length === 1 ? esc(dualLabel(dualWays[0])) : dualWays.length + '× Dual Screen'}</span>` : ''}</div>
      </div>
      <div class="pv-foot">
        ${top ? `<div class="pv-best"><span>Empfehlung${ways.length > 1 ? ` · ${ways.length} Wege` : ''}</span><b>${esc(top.name)}</b>${top.best ? `<span class="rating ${RANK_CLASS(top.best.rank)}">${esc(top.best.ratingDe || top.best.rating)}</span>` : ''}</div>`
          : `<div class="pv-best"><span>Spielwege</span><b>${g.platforms.length ? 'Emulation' : 'noch keiner bekannt'}</b></div>`}
        <a class="btn primary pv-open" href="#/spiel/${esc(g.id)}" data-pv-open>${icon('play')}Spiel ansehen</a>
      </div>
    </div></section>`;
}
function dualWelcome() {
  const picks = DB.games.filter((g) => g._dual && g.cover).sort((a, b) => b.routes.length - a.routes.length).slice(0, 12);
  const where = store.get('dualSwap', false) ? 'unten' : 'oben';
  return `<section class="pv pv-welcome">
    <div class="pv-welcome-text">
      <img src="icon.svg" alt="" width="40" height="40">
      <h1>Wähle ${where} ein Spiel</h1>
      <p>Es erscheint hier groß – mit Bildern zum Durchwischen. <b>Spiel ansehen</b> zeigt alle Wege und das Einrichten.</p>
      <p class="pv-keys"><span><kbd>Select</kbd> Controller zum anderen Bildschirm</span><span><kbd>B</kbd> zurück</span></p>
    </div>
    ${picks.length ? `<div class="pv-picks" aria-label="Dual-Screen-Spiele">${picks.map((g) => `<a class="pv-pick" href="#/vorschau/${esc(g.id)}" title="${esc(g.title)}"><img src="${esc(g.cover.url)}" alt="${esc(g.title)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()"></a>`).join('')}</div>` : ''}
  </section>`;
}
const pvTrack = () => document.querySelector('.pv-track');
function pvIndex(track = pvTrack()) { return track ? Math.round(track.scrollLeft / Math.max(1, track.clientWidth)) : 0; }
function pvStep(d, user) {
  const track = pvTrack();
  const n = track?.children.length || 0;
  if (n < 2) return;
  pvGoto((pvIndex(track) + d + n) % n, user);
}
function pvGoto(i, user) {
  const track = pvTrack();
  if (!track) return;
  if (user) D.pausedUntil = Date.now() + 15000;
  track.scrollTo({ left: i * track.clientWidth, behavior: 'smooth' });
}
function pvSync() {
  const track = pvTrack();
  if (!track) return;
  const i = pvIndex(track);
  document.querySelectorAll('.pv-dots button').forEach((b, k) => b.classList.toggle('on', k === i));
  const n = document.querySelector('.pv-count b');
  if (n) n.textContent = i + 1;
  const cap = document.querySelector('.pv-cap');
  const caps = cap ? JSON.parse(cap.dataset.caps || '[]') : [];
  if (caps[i]) { cap.classList.toggle('dual', caps[i][1]); cap.innerHTML = `${caps[i][1] ? icon('dual') : ''}<span>${esc(caps[i][0])}</span>`; }
}
function pvLayout() {
  document.documentElement.style.setProperty('--top-h', (document.querySelector('.top')?.offsetHeight || 54) + 'px');
}
function pvStart() {
  pvStop();
  pvLayout();
  requestAnimationFrame(() => {
    const track = pvTrack();
    if (!track || track._wired) return;
    track._wired = true;
    track.addEventListener('scroll', () => { clearTimeout(track._t); track._t = setTimeout(pvSync, 60); }, { passive: true });
    track.addEventListener('pointerdown', () => { D.pausedUntil = Date.now() + 15000; }, { passive: true });
  });
  D.slideTimer = setInterval(() => { if (!document.hidden && Date.now() > D.pausedUntil) pvStep(1, false); }, 6000);
}
function pvStop() { clearInterval(D.slideTimer); }
addEventListener('resize', () => { const t = pvTrack(); if (t) { pvLayout(); t.scrollLeft = 0; pvSync(); } });

/* the browse window marks a game: swap only the preview, no page rebuild (no flicker while scrolling a list) */
function showPreview(id, tapped) {
  if (D.role !== 'stage' || !DB.byId.has(id)) return;
  const h = location.hash || '';
  if (h === '#/vorschau/' + enc(id)) return;
  if (!tapped && D.input === 'stage') return;                 // you are using the stage: nothing changes under you
  if (!tapped && h.startsWith('#/einrichten/')) return;       // never pull the setup away
  history.replaceState(history.state, '', '#/vorschau/' + enc(id));
  store.set('lastGame', id);
  const view = document.getElementById('view');
  view.classList.add('pv-fade');
  clearTimeout(D.pvSwap);
  D.pvSwap = setTimeout(() => {
    view.classList.remove('pv-fade');
    if (location.hash !== '#/vorschau/' + enc(id)) return;   // something else was opened meanwhile
    view.innerHTML = viewPreview(id);
    view.classList.remove('pv-fade');
    scrollTo(0, 0);
    renderTabs(null);
    dualRouted();
  }, 110);
}

/* ---------- Ereignisse ---------- */
let announceTimer = null;
function announce(id) {          // browse: the marked game appears big on the stage
  if (!D.on || D.role !== 'browse' || !id) return;
  clearTimeout(announceTimer);
  announceTimer = setTimeout(() => { markCard(id); relay({ preview: id }); }, 180);
}
document.addEventListener('focusin', (e) => { if (D.on && D.pad && !D.quiet) announce(e.target.closest?.('.card')?.dataset.game); });
document.addEventListener('pointerdown', (e) => {
  if (!D.on) return;
  D.pad = false;
  document.body.classList.remove('kbd-nav');
  if (!e.target.closest?.('[data-dual]')) setInput(D.role);
}, true);

document.addEventListener('click', (e) => {
  const ctl = e.target.closest('[data-dual]');
  if (ctl) { e.preventDefault(); e.stopPropagation(); if (ctl.dataset.dual === 'swap') dualSwap(); else dualToggle(); return; }
  const nav = e.target.closest('[data-pv]');
  if (nav) { e.preventDefault(); e.stopPropagation(); pvStep(+nav.dataset.pv, true); return; }
  const dot = e.target.closest('[data-pv-dot]');
  if (dot) { e.preventDefault(); e.stopPropagation(); pvGoto(+dot.dataset.pvDot, true); return; }
  const slide = e.target.closest('.pv-slide');
  if (slide) {                                   // tap the picture: left third back, otherwise on
    const r = slide.getBoundingClientRect();
    pvStep(e.clientX < r.left + r.width / 3 ? -1 : 1, true);
    return;
  }
  if (!D.on) return;
  const a = e.target.closest('a[href^="#/"]');
  if (!a) return;
  const href = a.getAttribute('href');
  if (D.role === 'browse' && STAGE_ONLY.test(href)) {
    e.preventDefault(); e.stopPropagation();
    const card = a.closest('.card');
    const id = decodeURIComponent(href.split('/')[2] || '');
    if (card && !D.pad && lastGame() !== id) {  // touch: first tap shows it big, second tap opens it
      markCard(id);
      store.set('lastGame', id);
      relay({ preview: id, tapped: true });
      return;
    }
    showOnStage(href.replace(/^#\/vorschau\//, '#/spiel/'), a.dataset.gotoWay);
  } else if (D.role === 'stage' && STAGE_ONLY.test(href)) {
    e.preventDefault(); e.stopPropagation();
    if (a.dataset.gotoWay) state.pendingWay = a.dataset.gotoWay;
    const deeper = location.hash.startsWith('#/vorschau/') || href.startsWith('#/einrichten/');
    dualGo(href, deeper ? 0 : undefined);
    if (!href.startsWith('#/vorschau/')) setInput('stage');
  } else if (D.role === 'stage' && a.matches('[data-back]')) {
    e.preventDefault(); e.stopPropagation();
    dualBack();
  } else if (D.role === 'stage' && !ANY_ROLE.test(href)) {
    e.preventDefault(); e.stopPropagation();
    relay({ nav: href });
    setInput('browse');
  }
}, true);

native.on('relay', (d) => {
  if (!d || !D.on) return;
  if (d.swap) { const before = { on: D.on, role: D.role }; applyRole(before); return; }
  if (d.preview) { showPreview(d.preview, d.tapped); return; }
  if (d.focusSearch) { if (D.role === 'browse') { native.call('focusSelf').catch(() => {}); $('#q')?.focus(); } return; }
  if (d.nav) {
    if (!fitsRole(D.role, d.nav)) return;
    if (d.way) state.pendingWay = d.way;
    dualGo(d.nav, d.top ? 0 : d.y);
  }
});
native.on('inputTarget', (d) => { if (d?.role) { if (d.pad) D.pad = true; D.input = d.role; markInput(); } });
native.on('windowFocus', (f) => { D.focused = !!f; });

/* first guess before the app has reported its screens (the second window only exists in dual mode) */
if (native.available) {
  D.on = native.screen === 'companion' || !!store.get('dualLast', false);
  D.role = computeRole();
  document.body.classList.toggle('dual', D.on);
  document.body.classList.toggle('dual-browse', D.role === 'browse');
  document.body.classList.toggle('dual-stage', D.role === 'stage');
  native.call('inputReady', { role: D.role })
    .then((r) => { D.router = true; if (r?.target) { D.input = r.target; markInput(); } })
    .catch(() => { D.router = false; });   // older app: Gamepad API only in the window that has the focus
}
