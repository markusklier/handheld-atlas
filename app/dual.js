/* Handheld Atlas – zwei Bildschirme (Atlas-App auf Geräten wie dem AYN Thor). Lädt nach app.js und setup.js.

   Zwei Fenster, zwei Rollen:
     Stöbern  (standardmäßig oben)  – die normale Atlas-Oberfläche: Entdecken, Suche, Reihen, Neu, Info.
     Bühne    (standardmäßig unten) – was du gerade ansiehst: große Vorschau des markierten Spiels,
                                      nach „Öffnen“ die Spielseite mit den Wegen, dann der Setup-Assistent.
   Ein Tipp auf ⇅ tauscht die Rollen. Select (bzw. der Knopf „Fokus“) springt mit der Steuerung zum anderen Bildschirm.
   Die Fenster sprechen über die Brücke („relay“) miteinander; die Rollen-Einstellung teilen sie über localStorage. */
'use strict';

const dual = { on: false, set: false, preview: null, slide: 0, timer: null, active: true, lastRelay: 0 };
const dualOn = () => dual.on;
/* main = größerer Bildschirm (oben). Ohne Tausch stöbert man oben, die Bühne ist unten. */
function dualRole() {
  if (!dual.on) return 'single';
  const swapped = !!store.get('dualSwap', false);
  return (native.screen === 'main') !== swapped ? 'browse' : 'stage';
}
const relay = (data) => native.call('relay', data).catch(() => {});
const focusOther = () => native.call('focusOther').catch(() => {});

/* Called by setup.js whenever the app reports its screens (start, second window opened or closed). */
function dualSetup() {
  const on = native.available && !!su.info?.dual && !!su.info?.second;
  const changed = on !== dual.on || !dual.set;
  dual.on = on;
  dual.set = true;
  document.body.classList.toggle('dual', on);
  document.body.classList.toggle('dual-browse', dualRole() === 'browse');
  document.body.classList.toggle('dual-stage', dualRole() === 'stage');
  dualHeader();
  if (!changed || !on) return;
  if (dualRole() === 'stage') {
    // the stage never shows lists: start with the preview of the last game (or the welcome screen)
    if (!/^#\/(spiel|einrichten|vorschau|projekt)\//.test(location.hash)) location.hash = '#/vorschau/' + encodeURIComponent(store.get('lastGame', '') || '');
  } else if (/^#\/(spiel|einrichten|vorschau)\//.test(location.hash)) {
    location.hash = '#/';
  }
}

/* Header: browse keeps tabs and search; the stage gets a slim bar. Both get the swap button. */
function dualHeader() {
  let bar = document.getElementById('dual-ctl');
  if (!dual.on) { bar?.remove(); return; }
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'dual-ctl';
    document.querySelector('.top').appendChild(bar);
  }
  const stage = dualRole() === 'stage';
  bar.innerHTML = `${stage ? `<button class="dual-btn" data-dual="focus" title="Zum Stöbern (Select)">${icon('compass')}<span>Stöbern</span></button>` : `<button class="dual-btn" data-dual="focus" title="Zur Bühne (Select)">${icon('play')}<span>Bühne</span></button>`}
    <button class="dual-btn" data-dual="swap" title="Bildschirme tauschen">${icon('dual')}<span>Tauschen</span></button>`;
}

/* ---------- Bühne: große Vorschau ---------- */
function viewPreview(id) {
  const g = DB.byId.get(id);
  if (!g) return dualWelcome();
  const slides = previewSlides(g);
  const ways = waysFor(g).filter((w) => w.fits && w.r?.status !== 'archived').sort((a, b) => b.score - a.score);
  const top = ways[0];
  const dualWays = ways.filter((w) => w.features.includes('dual-screen') || w.features.includes('two-screens'));
  const year = versionsOf(g).find((v) => v.type === 'original')?.year || versionsOf(g)[0]?.year;
  const cover = g.cover?.url || slides[0]?.url;
  dual.preview = { id, slides };
  dual.slide = 0;
  const pic = (s, on) => `<figure class="pv-slide${on ? ' on' : ''}"><img src="${esc(fullSrc(s.url))}"${fullSrc(s.url) !== s.url ? ` data-fb="${esc(s.url)}"` : ''} alt="" referrerpolicy="no-referrer" onerror="if(this.dataset.fb){this.src=this.dataset.fb;delete this.dataset.fb}else this.closest('figure').remove()"><figcaption${s.dual ? ' class="dual"' : ''}>${s.dual ? icon('dual') : ''}${esc(s.label)}</figcaption></figure>`;
  return `<div class="pv" data-preview="${esc(g.id)}">
    ${cover ? `<div class="pv-bg" style="background-image:url('${esc(cover)}')"></div>` : ''}
    <div class="pv-stage">${slides.length ? slides.map((s, i) => pic(s, i === 0)).join('') : `<div class="pv-empty">${coverHTML(g, { badges: false })}</div>`}
      ${slides.length > 1 ? `<div class="pv-dots">${slides.map((_, i) => `<i class="${i ? '' : 'on'}"></i>`).join('')}</div>` : ''}</div>
    <div class="pv-info">
      <a class="franchise" href="#/franchise/${encodeURIComponent(g.franchise)}">${esc(g.franchise)}</a>
      <h1>${esc(g.title)}</h1>
      <div class="pv-meta">${year ? `<span>${year}</span>` : ''}<span class="pfs">${badges(g.platforms, 4)}</span></div>
      <div class="pv-tags">${dualWays.length ? `<span class="tag dual">${icon('dual')}${dualWays.length === 1 ? esc(dualLabel(dualWays[0])) : dualWays.length + '× Dual Screen'}</span>` : ''}
        <span class="tag">${ways.length} ${ways.length === 1 ? 'Weg' : 'Wege'}</span>
        ${top?.best ? `<span class="rating ${RANK_CLASS(top.best.rank)}">${esc(top.best.ratingDe || top.best.rating)}</span>` : ''}</div>
      ${top ? `<div class="pv-best"><span class="faint">Empfehlung</span><b>${esc(top.name)}</b><span class="faint">${esc(label('kinds', top.kind))}</span></div>` : ''}
      <a class="btn primary pv-open" href="#/spiel/${esc(g.id)}" data-pv-open>${icon('play')}Spiel öffnen</a>
      <p class="pv-hint faint">${dualRole() === 'stage' ? '<kbd>A</kbd> öffnet · <kbd>Select</kbd> zurück zum Stöbern' : ''}</p>
    </div></div>`;
}
function dualWelcome() {
  const picks = DB.games.filter((g) => g._dual && (g.cover || g.screenshots.length)).sort((a, b) => b.routes.length - a.routes.length).slice(0, 8);
  return `<div class="pv pv-welcome">
    <div class="pv-info">
      <img src="icon.svg" alt="" width="54" height="54">
      <h1>Atlas auf zwei Bildschirmen</h1>
      <p class="muted">Stöbere auf dem ${store.get('dualSwap', false) ? 'unteren' : 'oberen'} Bildschirm. Hier erscheint das markierte Spiel groß – mit „Öffnen“ seine Spielwege und das Einrichten.</p>
      <p class="faint"><kbd>Select</kbd> wechselt den Bildschirm · ${icon('dual')} Tauschen dreht die Rollen um.</p>
    </div>
    ${picks.length ? `<div class="pv-picks">${picks.map((g) => `<a class="pv-pick" href="#/vorschau/${esc(g.id)}">${g.cover ? `<img src="${esc(g.cover.url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}<span>${esc(g.title)}</span></a>`).join('')}</div>` : ''}
  </div>`;
}
function pvTick() {
  clearInterval(dual.timer);
  dual.timer = setInterval(() => {
    const el = document.querySelector('.pv-stage');
    if (!el || document.hidden) return;
    const figs = el.querySelectorAll('.pv-slide');
    if (figs.length < 2) return;
    dual.slide = (dual.slide + 1) % figs.length;
    figs.forEach((f, i) => f.classList.toggle('on', i === dual.slide));
    el.querySelectorAll('.pv-dots i').forEach((d, i) => d.classList.toggle('on', i === dual.slide));
  }, 5000);
}
/* Swap the preview without re-rendering the whole page (no flicker while the user moves through a list). */
function showPreview(id) {
  if (dualRole() !== 'stage') return;
  if (!/^#\/vorschau\//.test(location.hash) && location.hash !== '' && location.hash !== '#/') return;   // reading a game page: leave it
  history.replaceState(history.state, '', '#/vorschau/' + encodeURIComponent(id));
  const view = document.getElementById('view');
  view.classList.add('pv-fade');
  setTimeout(() => { view.innerHTML = viewPreview(id); view.classList.remove('pv-fade'); pvTick(); }, 140);
}

/* ---------- Ereignisse ---------- */
let pvTimer = null;
function announce(id) {          // browse: the marked game appears big on the stage
  if (dualRole() !== 'browse' || !id) return;
  clearTimeout(pvTimer);
  pvTimer = setTimeout(() => { relay({ preview: id }); document.querySelectorAll('.card.marked').forEach((c) => c.classList.remove('marked')); document.querySelector(`.card[data-game="${CSS.escape(id)}"]`)?.classList.add('marked'); }, 220);
}
document.addEventListener('focusin', (e) => { if (dual.on) announce(e.target.closest?.('.card')?.dataset.game); });
document.addEventListener('mouseover', (e) => { if (dual.on && !document.body.classList.contains('kbd-nav')) announce(e.target.closest?.('.card')?.dataset.game); });

document.addEventListener('click', (e) => {
  if (!dual.on) return;
  const ctl = e.target.closest('[data-dual]');
  if (ctl) {
    e.preventDefault();
    if (ctl.dataset.dual === 'swap') {
      store.set('dualSwap', !store.get('dualSwap', false));
      relay({ swap: true });
      dualApplyRole();
    } else focusOther();
    return;
  }
  const a = e.target.closest('a[href^="#/"]');
  if (!a) return;
  const href = a.getAttribute('href');
  const role = dualRole();
  if (role === 'browse' && /^#\/(spiel|einrichten|vorschau)\//.test(href)) {
    // open on the stage, keep the list here
    e.preventDefault(); e.stopPropagation();
    const id = decodeURIComponent(href.split('/')[2] || '');
    store.set('lastGame', id);
    relay({ nav: href.startsWith('#/vorschau/') ? '#/spiel/' + encodeURIComponent(id) : href, way: a.dataset.gotoWay || null });
    document.querySelectorAll('.card.marked').forEach((c) => c.classList.remove('marked'));
    a.closest('.card')?.classList.add('marked');
    focusOther();
  } else if (role === 'stage' && !/^#\/(spiel|einrichten|vorschau|projekt)\//.test(href)) {
    // lists, series, news … belong to the browse screen
    e.preventDefault(); e.stopPropagation();
    relay({ nav: href });
    focusOther();
  } else if (role === 'stage' && a.matches('[data-back]') && href === '#/') {
    e.preventDefault(); e.stopPropagation();
    dualBack();
  }
}, true);

/* B / Zurück on the stage: game page → preview (and back to browsing), setup → game page. */
function dualBack() {
  if (dualRole() !== 'stage') return false;
  const m = /^#\/(spiel|einrichten|vorschau)\/([^/]+)/.exec(location.hash);
  if (!m) { location.hash = '#/vorschau/' + encodeURIComponent(store.get('lastGame', '')); return true; }
  if (m[1] === 'einrichten') { location.hash = '#/spiel/' + m[2]; return true; }
  if (m[1] === 'spiel') { location.hash = '#/vorschau/' + m[2]; focusOther(); return true; }
  focusOther();
  return true;
}

function dualApplyRole() {
  dual.set = false;
  dualSetup();
  route();
  toast(dualRole() === 'stage' ? 'Dieser Bildschirm ist jetzt die Bühne.' : 'Hier stöberst du jetzt.', 2500);
}

native.on('relay', (d) => {
  if (!d || !dual.on) return;
  if (d.swap) { dualApplyRole(); return; }
  if (d.preview) { showPreview(d.preview); return; }
  if (d.nav) {
    if (d.way) { state.pendingWay = d.way; }
    if (location.hash === d.nav) { if (d.way) { state.openWay = d.way; state.pendingWay = null; state.scrollToWay = true; } route(); } else location.hash = d.nav;
    window.focus();
  }
});
native.on('windowFocus', (has) => {
  dual.active = !!has;
  document.body.classList.toggle('screen-idle', dual.on && !has);
  if (has && document.body.classList.contains('kbd-nav') && (!document.activeElement || document.activeElement === document.body)) {
    // arriving with the controller: put the focus somewhere useful
    const first = document.querySelector('.card.marked') || document.querySelector('[data-pv-open]') || document.querySelector('main a, main button');
    first?.focus({ preventScroll: false });
  }
});
window.addEventListener('hashchange', () => {
  if (location.hash.startsWith('#/vorschau/')) setTimeout(pvTick, 50); else clearInterval(dual.timer);
  const m = /^#\/(?:spiel|vorschau)\/([^/]+)/.exec(location.hash);
  if (m && decodeURIComponent(m[1])) store.set('lastGame', decodeURIComponent(m[1]));
});
if (location.hash.startsWith('#/vorschau/')) setTimeout(pvTick, 50);
