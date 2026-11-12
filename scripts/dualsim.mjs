#!/usr/bin/env node
/* Zwei-Bildschirm-Simulator für die Atlas-Oberfläche (ohne Gerät).

   Startet Chromium mit zwei Seiten in EINEM Profil (gemeinsamer localStorage wie die beiden WebViews der App) und
   baut die native Brücke „AtlasBridge“ nach: info, relay, second, inputReady/setRole/setInput, Tasten des Controllers.
   Damit lässt sich die Dual-Screen-Logik (app/dual.js) durchspielen und als Bild ansehen.

     python3 scripts/atlas.py build            # einmal, für dist/data.json
     node scripts/dualsim.mjs [szenario] [--density=2.25] [--apk=11] [--out=/pfad]

   Szenarien stehen unten in SCENARIOS (Standard: tour). --apk=7 simuliert eine alte App ohne Tastenverteilung
   (dann sehen beide Seiten dasselbe Gamepad, wie auf dem Gerät). Bilder: <out>/<nn>-<name>.png (oben + unten). */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')));
const scenario = process.argv.slice(2).find((a) => !a.startsWith('--')) || 'tour';
const density = +(args.density || 2.25);          // Thor: 1920×1080 und 1240×1080 Pixel; CSS-Größe = Pixel / Dichte
const APK = +(args.apk || 11);
const OUT = path.resolve(args.out || path.join(ROOT, 'dist', 'dualsim'));
const TOP = { width: Math.round(1920 / density), height: Math.round(1080 / density) };
const BOTTOM = { width: Math.round(1240 / density), height: Math.round(1080 / density) };

/* ---------- Dateien: app/ live, Daten aus dist/ ---------- */
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/json' };
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
  const file = [path.join(ROOT, 'app', p), path.join(ROOT, 'dist', p)].find((f) => f.startsWith(ROOT) && fs.existsSync(f) && fs.statSync(f).isFile());
  if (!file || p === 'sw.js') { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

/* ---------- nachgebaute App ---------- */
const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: '127.0.0.1,localhost' } : undefined;
const browser = await chromium.launch({ proxy });
const ctx = await browser.newContext({ deviceScaleFactor: 2, hasTouch: true });
const win = { main: null, companion: null };         // wie Screens.kt: großes Display = main, kleines = companion
const router = { roles: new Map(), ready: new Set(), target: 'browse' };
const pad = { buttons: {}, axes: [0, 0] };           // alte App: Gamepad-Zustand, den beide Seiten sehen
const log = [];

const pages = () => Object.values(win).filter(Boolean);
const emit = (page, event, data = null) => page.evaluate((m) => window.AtlasBridge?.onmessage?.({ data: m }), JSON.stringify({ event, data })).catch(() => {});
const emitAll = (event, data) => Promise.all(pages().map((p) => emit(p, event, data)));
const info = (page) => ({
  app: { version: `0.1.${APK}`, code: APK, package: 'io.github.markusklier.handheldatlas', webview: 'sim' },
  role: page === win.companion ? 'companion' : 'main', displayId: page === win.companion ? 4 : 0,
  dual: !args.single, second: !!win.companion,
  device: { manufacturer: 'AYN', brand: 'AYN', model: 'AYN Thor', soc: 'SM8550', ramGb: 16, storageGb: 1024, storageFreeGb: 800, android: '13', sdk: 33, abis: ['arm64-v8a'] },
  displays: [{ id: 0, width: 1920, height: 1080, game: true }, { id: 4, width: 1240, height: 1080 }],
  shizuku: { installed: false, running: false, granted: false }, canInstall: true, notifications: true, measuring: false,
});

async function nativeCall(page, method, p) {
  switch (method) {
    case 'info': return info(page);
    case 'packages': return {};
    case 'redditState': return { loggedIn: false };
    case 'measureState': return { running: false, live: null, last: null };
    case 'relay': await Promise.all(pages().filter((x) => x !== page).map((x) => emit(x, 'relay', p))); return true;
    case 'second':
      if (p.open && !win.companion) await openWindow('companion');
      else if (!p.open && win.companion) { const c = win.companion; win.companion = null; router.roles.delete(c); router.ready.delete(c); await c.close(); await emitAll('screens'); }
      return { open: !!win.companion, dual: true };
    case 'focusSelf': case 'focusOther': case 'openUrl': case 'leave': return true;
    case 'inputReady': case 'setRole': case 'setInput': case 'input':
      if (APK < 10 || (method === 'input' && APK < 11)) throw new Error('Unbekannte Funktion: ' + method);
      if (method === 'inputReady') router.ready.add(page);
      if (method === 'input') { router.roles.set(page, p.role || 'single'); router.ready.add(page); return { primary: [...router.roles.values()].includes('primary') }; }
      if (method === 'setInput') { router.target = p.role || 'browse'; await emitAll('inputTarget', { role: router.target, pad: !!p.pad }); }
      else router.roles.set(page, p.role || 'single');
      return { target: router.target };
    default: throw new Error('Unbekannte Funktion: ' + method);
  }
}

async function openWindow(kind) {
  const page = await ctx.newPage();
  await page.setViewportSize(kind === 'main' ? TOP : BOTTOM);
  page.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource|net::ERR/.test(m.text())) log.push(`[${kind}] ${m.text()}`); });
  page.on('pageerror', (e) => log.push(`[${kind}] ${e.message}`));
  await page.exposeBinding('__atlasNative', async ({ page: src }, s) => {
    const { id, method, params } = JSON.parse(s);
    let answer;
    try { answer = { id, ok: true, result: await nativeCall(src, method, params || {}) }; } catch (e) { answer = { id, ok: false, error: e.message }; }
    src.evaluate((m) => window.AtlasBridge?.onmessage?.({ data: m }), JSON.stringify(answer)).catch(() => {});
  });
  await page.addInitScript(() => {
    window.AtlasBridge = { postMessage: (s) => window.__atlasNative(s), onmessage: null };
    // alte App: ein Gamepad, das jede Seite des Prozesses sieht
    window.__pad = null;
    navigator.getGamepads = () => (window.__pad ? [window.__pad] : []);
  });
  win[kind] = page;
  await page.goto(`${BASE}?app=${APK}${kind === 'companion' ? '&screen=companion' : ''}`);
  await page.waitForFunction(() => window.DB?.games?.length || document.querySelector('.card, .cp, .pv'), null, { timeout: 20000 }).catch(() => {});
  await Promise.all(pages().filter((x) => x !== page).map((x) => emit(x, 'screens')));
  return page;
}

/* ---------- Bedienung ---------- */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const NAMES = { up: 12, down: 13, left: 14, right: 15, a: 0, b: 1, x: 2, y: 3, l: 4, r: 5, l2: 6, r2: 7, select: 8, start: 9 };
/* Eine Controller-Taste. Neue App: InputRouter schickt sie an genau ein Fenster. Alte App: beide Seiten sehen das Gamepad. */
async function press(key, times = 1) {
  for (let i = 0; i < times; i++) {
    if (APK >= 11) {
      const target = pages().find((p) => router.roles.get(p) === 'primary' && router.ready.has(p)) || win.main;
      await emit(target, 'input', { key, repeat: false });
    } else if (APK === 10) {
      const target = pages().find((p) => router.roles.get(p) === router.target && router.ready.has(p)) || win.main;
      await emit(target, 'input', { key, repeat: false });
    } else {
      const set = (down) => Promise.all(pages().map((p) => p.evaluate(([n, d]) => {
        const g = window.__pad || (window.__pad = { buttons: Array.from({ length: 17 }, () => ({ pressed: false })), axes: [0, 0, 0, 0] });
        g.buttons[n] = { pressed: d };
        if (d) window.dispatchEvent(new Event('gamepadconnected'));
      }, [NAMES[key], down])));
      await set(true); await sleep(70); await set(false);
    }
    await sleep(140);
  }
}
let shotNo = 0;
async function shot(name) {
  fs.mkdirSync(OUT, { recursive: true });
  await sleep(350);
  const bufs = await Promise.all([win.main, win.companion].map((p) => (p ? p.screenshot({ type: 'png' }) : null)));
  const sheet = await ctx.newPage();
  await sheet.setViewportSize({ width: TOP.width + 40, height: TOP.height + (bufs[1] ? BOTTOM.height + 44 : 0) + 48 });
  await sheet.setContent(`<body style="margin:0;background:#1b1f1d;font:12px system-ui;color:#9aa;display:grid;justify-items:center;gap:6px;padding:8px 20px">
    <div>oben · ${TOP.width}×${TOP.height}</div><img src="data:image/png;base64,${bufs[0].toString('base64')}" style="width:${TOP.width}px;border-radius:6px">
    ${bufs[1] ? `<div>unten · ${BOTTOM.width}×${BOTTOM.height}</div><img src="data:image/png;base64,${bufs[1].toString('base64')}" style="width:${BOTTOM.width}px;border-radius:6px">` : ''}</body>`);
  const file = path.join(OUT, `${String(++shotNo).padStart(2, '0')}-${name}.png`);
  await sheet.screenshot({ path: file });
  await sheet.close();
  console.log('Bild:', file);
}
const state = async () => Object.fromEntries(await Promise.all(Object.entries(win).filter(([, p]) => p).map(async ([k, p]) => [k, await p.evaluate(() => ({
  hash: location.hash, body: document.body.className, y: Math.round(scrollY),
  focus: document.activeElement?.dataset?.game || document.activeElement?.id || document.activeElement?.className?.toString().slice(0, 40) || document.activeElement?.tagName,
  view: document.querySelector('[data-cp]')?.dataset.cp || null, game: document.querySelector('[data-cp-game]')?.dataset.cpGame || null,
}))])));

/* ---------- Szenarien ---------- */
const SCENARIOS = {
  /* einmal durch alles: stöbern, Vorschau, Spiel ansehen, Bilder blättern, tauschen, aus/an */
  async tour() {
    await shot('start');
    await win.main.evaluate(() => { document.body.classList.add('kbd-nav'); document.querySelectorAll('main .card')[1].focus(); });
    await press('right');
    await shot('karte-markiert');
    await press('r2', 2);
    await shot('bilder-geblaettert');
    await press('a');
    await shot('spiel-angesehen');
    await press('down', 4);
    await shot('spielseite-weiter');
    await press('b');
    await shot('zurueck-in-liste');
    await press('select');
    await shot('getauscht');
    await press('down'); await press('a');
    await shot('getauscht-spiel');
    await press('select');
    await shot('zurueckgetauscht');
    await win.main.evaluate(() => document.querySelector('[data-dual="toggle"]')?.click());
    await sleep(900);
    await shot('dual-aus');
    await win.main.evaluate(() => document.querySelector('[data-dual="toggle"]')?.click());
    await sleep(1500);
    await shot('dual-wieder-an');
  },
  /* nur der Begleiter: Vorschau und Bilder verschiedener Spiele (--games=a,b,c), dazu getauscht */
  async vorschau() {
    const games = (args.games || 'super-metroid,the-legend-of-zelda-ocarina-of-time,pokemon-emerald').split(',');
    for (const id of games) {
      await win.main.evaluate((g) => window.dualShow(g), id);
      await sleep(2500);
      await shot('vorschau-' + id);
    }
    await win.main.evaluate((g) => { location.hash = '#/spiel/' + g; }, games[0]);
    await sleep(2500);
    await shot('bilder-' + games[0]);
    await press('b'); await press('select');
    await sleep(2500);
    await shot('getauscht-vorschau');
  },
  /* Einrichten und Messfahrt: Live-Werte groß auf dem Begleiter */
  async einrichten() {
    await win.main.evaluate((g) => { location.hash = '#/spiel/' + g; }, args.games || 'super-metroid');
    await sleep(1500);
    const href = await win.main.evaluate(() => document.querySelector('.su-bar a[href^="#/einrichten/"]')?.getAttribute('href'));
    if (!href) throw new Error('kein Einrichten-Knopf gefunden');
    await win.main.evaluate((h) => { location.hash = h; }, href);
    await sleep(2000);
    await shot('einrichten');
    await emitAll('measure', { state: 'running', fps: 58.6, seconds: 150, elapsed: 42, temp: { skinMax: 41 }, label: 'Super Metroid' });
    await sleep(600);
    await shot('messfahrt');
  },
  /* Zufällige Bedienung (--steps=150 --seed=1): Tasten, Tippen auf dem Begleiter, Tauschen, Aus/An.
     Nach jedem Schritt muss gelten: genau ein Hauptbildschirm, der Begleiter zeigt keine eigene Seite und passt zum Hauptbildschirm. */
  async stress() {
    let seed = +(args.seed || 1);
    const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
    const pick = (list) => list[Math.floor(rnd() * list.length)];
    const steps = +(args.steps || 120);
    const fails = [];
    const tap = (page, sel) => page.evaluate((q) => { const els = [...document.querySelectorAll(q)]; const el = els[Math.floor(Math.random() * els.length)]; if (el) el.click(); return !!el; }, sel).catch(() => false);
    for (let i = 0; i < steps; i++) {
      const r = rnd();
      let what;
      const kinds = await Promise.all(pages().map((p) => p.evaluate(() => document.body.classList.contains('dual-companion')).catch(() => false)));
      const comp = pages().find((p, k) => kinds[k]), main = pages().find((p, k) => !kinds[k]) || win.main;
      if (r < 0.62) { what = 'Taste ' + pick(['up', 'down', 'down', 'left', 'right', 'right', 'a', 'a', 'b', 'l', 'r', 'l2', 'r2']); await press(what.slice(6)); }
      else if (r < 0.70) { what = 'Select'; await press('select'); }
      else if (r < 0.90 && comp) { const sel = pick(['[data-cp-open]', '[data-cp-way]', '[data-cp-thumb]', '[data-cp-step]', '[data-cp-pick]', '.cp [data-dual="swap"]']); what = 'Begleiter tippt ' + sel; await tap(comp, sel); }
      else if (r < 0.95) { what = 'Dual Screen an/aus'; await tap(main, '[data-dual="toggle"]'); await sleep(1400); }
      else { what = 'Hauptbildschirm tippt Karte'; await tap(main, 'main a[href^="#/spiel/"]'); }
      await sleep(what.startsWith('Taste') ? 160 : 900);
      const st = await Promise.all(pages().map((p) => p.evaluate(() => ({
        role: document.body.classList.contains('dual-companion') ? 'companion' : document.body.classList.contains('dual-primary') ? 'primary' : 'single',
        hash: location.hash, cp: document.querySelector('[data-cp]')?.dataset.cp || null, cpGame: document.querySelector('[data-cp-game]')?.dataset.cpGame || null,
        page: !!document.querySelector('main > :not(.cp)'), marked: document.querySelector('.card.marked')?.dataset.game || null,
      }))));
      const roles = st.map((x) => x.role).sort().join('+');
      const prim = st.find((x) => x.role !== 'companion'), co = st.find((x) => x.role === 'companion');
      const bad = [];
      if (st.length === 2 && roles !== 'companion+primary') bad.push('Rollen: ' + roles);
      if (st.length === 1 && roles !== 'single') bad.push('ein Fenster, aber Rolle ' + roles);
      if (co && (!co.cp || co.page)) bad.push('Begleiter zeigt eine eigene Seite');
      if (prim && prim.cp) bad.push('Hauptbildschirm zeigt den Begleiter');
      const m = prim && /^#\/spiel\/([^/]+)/.exec(prim.hash);
      if (co && m && (co.cp !== 'game' || co.cpGame !== decodeURIComponent(m[1]))) bad.push(`Spiel oben ${decodeURIComponent(m[1])}, Begleiter ${co.cp}/${co.cpGame}`);
      if (bad.length) { fails.push(`Schritt ${i} (${what}): ${bad.join('; ')}`); await shot('fehler-' + i); if (fails.length > 4) break; }
    }
    console.log(fails.length ? 'FEHLER:\n' + fails.join('\n') : `Stresstest: ${steps} Schritte ohne Abweichung (seed ${args.seed || 1}).`);
    await shot('ende');
    if (fails.length) process.exitCode = 1;
  },
};

await openWindow('main');
if (!args.single) await openWindow('companion');
await sleep(1500);
try {
  await SCENARIOS[scenario]();
  console.log(JSON.stringify(await state(), null, 1));
} finally {
  if (log.length) console.log('Fehler in den Seiten:\n' + [...new Set(log)].join('\n'));
  await browser.close();
  server.close();
}
