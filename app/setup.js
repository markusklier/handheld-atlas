/* Handheld Atlas – Setup-Assistent (docs/SETUP.md). Lädt nach app.js und nutzt dessen Helfer.
   Von „Spielweg gewählt“ bis „läuft gut“: Apps installieren, Startkonfiguration aus Berichten, spielen, Messfahrt,
   auswerten, gezielt nachstellen, Ergebnis zurückmelden. Im Browser ist es eine Checkliste; in der Atlas-App
   (native Brücke) wird installiert, gestartet und gemessen. Erstes unterstütztes Gerät: AYN Thor Max. */
'use strict';

const su = { info: null, pkgs: {}, installing: {}, live: null, busy: {}, selftest: null, release: null };
const suPolicy = () => DB.setup.policy || {};
const suKey = (s) => norm(s).replace(/[^a-z0-9]/g, '');
let suSessCache = null;   // parsed once per change – the ranking asks for every way of every game
const suSessions = () => (suSessCache ||= store.get('setupSessions', {}));
const suSession = (g, w) => suSessions()[g.id + '|' + w.key] || { rounds: [], variant: 0, files: {}, configured: false, target: 'auto' };
function suSave(g, w, s) {
  const all = suSessions();
  all[g.id + '|' + w.key] = { ...s, at: Date.now() };
  const keys = Object.keys(all).sort((a, b) => all[b].at - all[a].at).slice(0, 60);
  store.set('setupSessions', Object.fromEntries(keys.map((k) => [k, all[k]])));
  suSessCache = null;
}
const suFindWay = (g, key) => waysFor(g).find((w) => w.key === key);
const suHref = (g, w) => `#/einrichten/${encodeURIComponent(g.id)}/${encodeURIComponent(w.key)}`;

/* ---------- Gerät ---------- */
const suProfile = () => DB.setup.devices?.[0] || null;      // erste Fassung: nur AYN Thor Max
function suDetected() {
  const p = suProfile(), d = su.info?.device;
  if (!p || !d) return null;
  const m = p.match || {};
  const soc = (m.socModels || []).some((x) => String(d.soc || '').toUpperCase().includes(x));
  const ok = soc && d.ramGb >= (m.minRamGb || 0) && (su.info.displays || []).filter((x) => !x.private).length >= (m.minDisplays || 1);
  return ok ? p : null;
}
/* Gerät für Rückmeldungen: erkannt oder vom Nutzer bestätigt („Ich habe einen Thor Max“). */
const suDeviceId = () => (suDetected() || (store.get('setupDeviceConfirmed', false) ? suProfile() : null))?.id || null;
const suDual = () => typeof dualOn === 'function' && dualOn();
const suShell = () => !!su.info?.shizuku?.granted;

/* ---------- Apps eines Spielwegs ---------- */
const SU_INSTALLABLE = new Set(['emulator', 'emulator-fork', 'port', 'launcher', 'companion', 'runtime', 'official', 'tool']);
const suLearned = () => ({ ...Object.fromEntries(Object.entries(DB.setup.learned || {}).map(([k, v]) => [k, v.package])), ...store.get('setupLearned', {}) });
function suAppOfProject(pid) {
  const known = DB.setup.apps.find((a) => (a.projects || []).includes(pid));
  if (known) return known;
  const p = DB.projects[pid];
  if (!p || !SU_INSTALLABLE.has(p.kind)) return null;
  const pkg = suLearned()[pid];
  return { id: 'p:' + pid, name: p.name, packages: pkg ? [pkg] : [], project: pid, adhoc: true,
    source: p.repo ? { type: 'github', repo: p.repo } : p.url ? { type: 'page', url: p.url } : null };
}
/* Bausteine eines Wegs: jeder Baustein ist eine App; bei allgemeinen Wegen gibt es Alternativen (options). */
function suComponents(g, w) {
  const comps = [];
  const byName = (names) => DB.setup.apps.filter((a) => (a.reportNames || []).some((n) => names.has(suKey(n))));
  if (w.type === 'route') {
    for (const pid of w.r.projects || []) {
      const app = suAppOfProject(pid);
      if (app) comps.push({ options: [{ ...app, unverified: w.r.verification === 'ai-unverified' && !!app.adhoc }], role: DB.projects[pid]?.kind || 'app' });
    }
    if (!comps.length) {
      const names = new Set([suKey(w.r.runtime || ''), ...(w.community || []).map((r) => suKey(r.emulator))].filter(Boolean));
      const apps = byName(names);
      if (apps.length) comps.push({ options: apps, role: 'emulator' });
    }
  } else if (w.type === 'generic') {
    // one emulator per way – other emulators are other ways (switch at the top of the assistant)
    const own = suAppOfProject(w.o.project);
    const opts = own ? [own] : byName(new Set([suKey(w.name)]));
    if (opts.length) comps.push({ options: opts, role: 'emulator' });
  } else if (w.type === 'community') {
    const apps = byName(new Set([suKey(w.name)]));
    if (apps.length) comps.push({ options: apps, role: 'emulator' });
  } else if (w.type === 'official') {
    const link = w.link || (w.v.links || []).find((l) => /play\.google\.com/.test(l.url))?.url;
    const id = link && (/[?&]id=([\w.]+)/.exec(link) || [])[1];
    comps.push({ options: [{ id: 'official', name: g.title, packages: id ? [id] : [], source: id ? { type: 'play', id } : link ? { type: 'page', url: link } : null }], role: 'official' });
  }
  return comps;
}
function suPackages(app) {
  const l = suLearned();
  return [...new Set([...(app.packages || []), l['app:' + app.id], app.project && l[app.project], ...(app.adhoc ? [] : (app.projects || []).map((p) => l[p]))].filter(Boolean))];
}
const suInstalled = (app) => suPackages(app).map((p) => (su.pkgs[p] ? { package: p, ...su.pkgs[p] } : null)).find(Boolean) || null;
function suChosen(comp, s, i) {
  const want = s.apps?.[i];
  return comp.options.find((a) => a.id === want) || comp.options.find((a) => suInstalled(a)) || comp.options[0];
}
/* Die App, die gestartet und gemessen wird: nicht die Begleit-App, wenn es noch eine andere gibt. */
function suPlayApp(comps, s) {
  const chosen = comps.map((c, i) => ({ app: suChosen(c, s, i), role: c.role }));
  const main = chosen.find((c) => c.role !== 'companion' && c.role !== 'tool' && suInstalled(c.app)) || chosen.find((c) => suInstalled(c.app));
  return main ? { app: main.app, ...suInstalled(main.app) } : null;
}
async function suRefreshPackages() {
  if (!native.available) return;
  const ids = new Set(['moe.shizuku.privileged.api']);
  for (const a of DB.setup.apps) for (const p of a.packages || []) ids.add(p);
  for (const p of Object.values(suLearned())) ids.add(p);
  for (const g of DB.games) for (const v of g.versions || []) for (const l of v.links || []) { const m = /play\.google\.com\/store\/apps\/details\?id=([\w.]+)/.exec(l.url); if (m) ids.add(m[1]); }
  try { su.pkgs = Object.fromEntries(Object.entries(await native.call('packages', { ids: [...ids] })).filter(([, v]) => v)); } catch { /* app too old */ }
}

/* Emulator ways of the same version (generic platform emulators and those only known from reports), best first. */
function suSiblings(g, w) {
  if (w.type !== 'generic' && w.type !== 'community') return [];
  return waysFor(g).filter((x) => x.v === w.v && x.fits && (x.type === 'generic' || x.type === 'community')).sort((a, b) => b.score - a.score);
}
/* Is the app of this way installed on the device? (used for the ranking in app.js) */
function suWayInstalled(w) {
  if (!native.available || !Object.keys(su.pkgs).length) return false;
  const g = { routes: [] };
  try { return suComponents(g, w).some((c) => c.options.some((a) => suInstalled(a))); } catch { return false; }
}
function suEmuChooser(g, w) {
  const sib = suSiblings(g, w);
  if (sib.length < 2) return '';
  const best = sib[0];
  const fact = (x) => {
    const run = suBestRun(g, x);
    return run ? `Ø ${run.fps.avg} FPS gemessen` : x.best ? `${x.best.ratingDe || x.best.rating} (${x.community.length})` : 'keine Berichte';
  };
  return `<section class="su-emu"><h3>${icon('gamepad')}Emulator</h3>
    <p class="muted">${best.key === w.key ? `<b>${esc(w.name)}</b> ist für dieses Spiel die beste Wahl.` : `Atlas empfiehlt <b>${esc(best.name)}</b> – du richtest gerade <b>${esc(w.name)}</b> ein.`} Du kannst jederzeit wechseln, z. B. wenn ein anderer schon installiert ist.</p>
    <div class="su-emus">${sib.map((x, i) => `<a class="su-emu-opt${x.key === w.key ? ' on' : ''}" href="${suHref(g, x)}" aria-current="${x.key === w.key}">
      <b>${esc(x.name)}</b>${i === 0 ? '<span class="tag best">Empfehlung</span>' : ''}
      <span class="faint">${esc(fact(x))}${suWayInstalled(x) ? ' · installiert' : ''}</span></a>`).join('')}</div></section>`;
}

/* ---------- Startkonfigurationen: Messfahrten vom Gerät, dann Berichte (Thor Max zuerst) ---------- */
function suVariants(g, w, app) {
  const p = suProfile();
  const mine = new Set(p?.reportNames || []), family = new Set(p?.familyReportNames || []);
  const out = [];
  for (const r of (DB.setup.runs[g.id] || []).filter((x) => x.way === w.key && x.fps && x.verdict !== 'bad' && x.verdict !== 'broken')
    .sort((a, b) => (b.verdict === 'good') - (a.verdict === 'good') || b.fps.avg - a.fps.avg).slice(0, 2)) {
    out.push({ kind: 'measured', label: `Auf dem ${p?.name || 'Gerät'} gemessen: Ø ${r.fps.avg} FPS`, source: r.variant?.source || null,
      settings: r.variant?.settings || {}, changes: r.variant?.changes || [], note: `${fmtDate(r.date)}${r.fps.low1 ? ' · 1 %-Low ' + r.fps.low1 : ''}${r.app ? ' · ' + r.app + (r.appVersion ? ' ' + r.appVersion : '') : ''}` });
  }
  const tier = (rep) => (mine.has(rep.device) ? 0 : family.has(rep.device) ? 1 : 2);
  // Berichte der gewählten App zuerst (ein Weg kann Berichte mehrerer Emulatoren tragen)
  const names = new Set((app?.reportNames || []).map(suKey));
  const all = (w.community || []).filter((rep) => rep.settings && Object.keys(rep.settings).length);
  const own = all.filter((rep) => names.has(suKey(rep.emulator)));
  const reps = (own.length ? own : all)
    .sort((a, b) => tier(a) - tier(b) || (a.rank || 9) - (b.rank || 9) || String(b.date || '').localeCompare(String(a.date || '')));
  for (const rep of reps.slice(0, 6)) {
    out.push({ kind: 'report', label: `${rep.device} · ${rep.emulator}${rep.settings['Emulator Version'] ? ' ' + rep.settings['Emulator Version'] : ''} · ${rep.ratingDe || rep.rating}${rep.date ? ' · ' + fmtDate(rep.date) : ''}`, source: rep.url, settings: rep.settings, emulator: rep.emulator,
      note: `${rep.emulator}${rep.date ? ' · ' + fmtDate(rep.date) : ''}${rep.summary ? ' · ' + rep.summary : ''}`, tier: tier(rep), rank: rep.rank });
  }
  out.push({ kind: 'default', label: 'Standardeinstellungen der App', source: null, settings: {}, note: 'Nichts ändern und erst einmal messen.' });
  return out;
}
/* Was sagen die Berichte insgesamt? Für den ehrlichen Hinweis, bevor man Zeit investiert. */
function suOutlook(w) {
  const reps = w.community || [];
  if (!reps.length) return null;
  const best = Math.min(...reps.map((r) => r.rank || 9));
  if (best >= 6) return { level: 'bad', text: `Die ${reps.length} Berichte von vergleichbaren Geräten sind schlecht (bestenfalls „${reps.find((r) => r.rank === best)?.ratingDe || 'kaum spielbar'}“). Du kannst es trotzdem versuchen – rechne damit, dass die Hardware hier die Grenze ist.` };
  if (best >= 4) return { level: 'ok', text: `Berichte von vergleichbaren Geräten: bestenfalls „${reps.find((r) => r.rank === best)?.ratingDe}“. Mit Feintuning ist etwas zu holen, perfekt wird es eher nicht.` };
  return { level: 'good', text: `Berichte von vergleichbaren Geräten: bis „${reps.find((r) => r.rank === best)?.ratingDe}“ (${reps.length} ${reps.length === 1 ? 'Bericht' : 'Berichte'}).` };
}

/* ---------- Auswertung einer Messfahrt (ohne KI) ---------- */
function suTarget(s, res) {
  if (s.target && s.target !== 'auto') return { fps: +s.target, guessed: false };
  // Ohne Angabe: nahe 30 → 30er-Spiel; sonst 60 annehmen (ein Spiel bei 35–55 kämpft meist mit einem 60er-Ziel)
  const avg = res?.fps?.avg || 0;
  return { fps: avg < 32.5 ? 30 : 60, guessed: true };
}
function suJudge(res, s) {
  if (!res?.fps) return null;
  const pol = suPolicy(), t = suTarget(s, res);
  const avg = res.fps.avg, low = res.fps.low1 || avg;
  const reached = avg >= t.fps * (pol.target?.reachedAvg || 0.97) && low >= t.fps * (pol.target?.reachedLow1 || 0.85);
  const limit = avg < t.fps * (pol.target?.hardwareLimit || 0.85);
  const hot = (res.temp?.throttleStatus || 0) >= (pol.thermal?.throttleStatus || 3) || (res.temp?.skinMax || 0) >= (pol.thermal?.skinWarnC || 45);
  const smooth = low >= avg * 0.8;
  const level = reached && !hot ? 'good' : limit ? 'bad' : 'ok';
  const text = reached ? (hot ? 'Tempo erreicht, aber das Gerät wird dabei zu warm.' : 'Ziel erreicht: läuft rund.')
    : limit ? `Deutlich unter dem Ziel von ${t.fps} FPS.` : smooth ? `Knapp unter dem Ziel von ${t.fps} FPS, aber gleichmäßig.` : `Nahe am Ziel von ${t.fps} FPS, aber mit Rucklern.`;
  return { level, text, target: t, reached, limit, hot, smooth };
}
/* Abbruchregeln aus policy.json: nicht verrennen. */
function suStop(s) {
  const pol = suPolicy().stop || {};
  const rounds = s.rounds.filter((r) => r.result?.fps);
  if (!rounds.length) return null;
  const last = rounds[rounds.length - 1], j = suJudge(last.result, s);
  const best = rounds.reduce((b, r) => (r.result.fps.avg > b.result.fps.avg ? r : b), rounds[0]);
  if (j.reached && !j.hot) return { stop: true, why: 'Ziel erreicht. Mehr Feintuning bringt nur noch Kosmetik.', best };
  if (rounds.length >= (pol.maxRounds || 6)) return { stop: true, why: `Nach ${rounds.length} Runden ist Schluss – nimm die beste Runde.`, best };
  const gains = rounds.slice(1).map((r, i) => r.result.fps.avg - rounds[i].result.fps.avg);
  const flat = gains.slice(-(pol.flatRounds || 2));
  if (flat.length >= (pol.flatRounds || 2) && flat.every((d, i) => d < (pol.minGainFps || 3) && d < rounds[rounds.length - flat.length + i - 1].result.fps.avg * (pol.minGainPct || 5) / 100)) {
    const t = j.target.fps, lock = best.result.fps.avg >= 55 ? 60 : best.result.fps.avg >= 38 ? 40 : best.result.fps.avg >= 28 ? 30 : null;
    return { stop: true, best, why: `Die letzten ${flat.length} Runden haben kaum noch etwas gebracht – mehr gibt die Hardware auf diesem Weg nicht her.`
      + (lock && lock < t ? ` Stell lieber ein festes ${lock}er-Limit ein: gleichmäßige ${lock} FPS spielen sich besser als schwankende ${Math.round(best.result.fps.avg)}.` : '') };
  }
  return { stop: false, best };
}

/* ---------- Ansicht: Einrichten ---------- */
const suIcon = (state) => `<span class="su-state ${state}">${icon(state === 'ok' ? 'check' : state === 'miss' ? 'alert' : 'info')}</span>`;
const suStep = (n, title, state, body) => `<section class="su-step ${state}"><h3>${suIcon(state)}<span class="n">${n}</span>${esc(title)}</h3>${body}</section>`;
const fmtBytes = (n) => (n > 1e9 ? (n / 1e9).toFixed(1) + ' GB' : n > 1e6 ? Math.round(n / 1e6) + ' MB' : Math.round(n / 1e3) + ' kB');

function suAppRow(g, w, comp, i, s) {
  const app = suChosen(comp, s, i);
  const inst = suInstalled(app);
  const st = su.installing[app.id];
  const src = app.source;
  const where = !src ? 'Bezugsquelle nicht hinterlegt' : src.type === 'github' ? `GitHub: ${src.repo}` : src.type === 'play' ? 'Google Play' : new URL(src.url).hostname;
  const proj = app.project ? DB.projects[app.project] : (app.projects || []).map((p) => DB.projects[p]).find(Boolean);
  let action;
  if (st?.phase === 'choose') {
    action = `<div class="su-choose"><p class="muted">Mehrere Dateien im Release – welche passt? (für den Thor: arm64)</p>${st.choices.map((c, k) => `<button class="btn small" data-su="install-asset" data-comp="${i}" data-k="${k}">${esc(c.name)} · ${fmtBytes(c.size)}</button>`).join('')}</div>`;
  } else if (st && st.phase !== 'done' && st.phase !== 'error') {
    const pct = st.total > 0 ? Math.round(st.done / st.total * 100) : null;
    action = `<span class="su-progress">${st.phase === 'search' ? 'Suche die passende Datei …' : st.phase === 'download' ? `Lade herunter${pct !== null ? ' ' + pct + ' %' : ''} …` : st.phase === 'confirm' ? 'Bestätige die Installation im Android-Dialog.' : 'Installiere …'}</span>`;
  } else if (!src) {
    action = '';
  } else if (src.type !== 'github' || !native.available) {
    const url = src.type === 'github' ? `https://github.com/${src.repo}/releases/latest` : src.type === 'play' ? `https://play.google.com/store/apps/details?id=${src.id}` : src.url;
    action = `<button class="btn${inst ? '' : ' primary'}" data-su="open-source" data-url="${esc(url)}"${src.type === 'play' ? ` data-market="${esc(src.id)}"` : ''}>${src.type === 'play' ? 'In Google Play öffnen' : src.type === 'github' ? 'Release öffnen' : 'Zur Download-Seite'} ${icon('ext')}</button>`;
  } else {
    action = `<button class="btn${inst ? '' : ' primary'}" data-su="install" data-comp="${i}">${inst ? 'Neueste Version installieren' : 'Installieren'}</button>`;
  }
  return `<div class="su-app"><div class="grow"><b>${esc(app.name)}</b>${comp.options.length > 1 ? ` <select class="su-select" data-su-app="${i}">${comp.options.map((o) => `<option value="${esc(o.id)}"${o.id === app.id ? ' selected' : ''}>${esc(o.name)}${suInstalled(o) ? ' ✓' : ''}</option>`).join('')}</select>` : ''}
      <div class="faint">${inst ? `installiert: Version ${esc(inst.version || '?')}` : native.available ? (suPackages(app).length ? 'nicht installiert' : 'Paketname noch unbekannt – wird beim Installieren erkannt') : 'Status nur in der Atlas-App sichtbar'} · ${esc(where)}${proj?.latestRelease?.tag ? ` · neuestes Release ${esc(proj.latestRelease.tag)}` : ''}</div>
      ${app.note ? `<div class="faint">${esc(app.note)}</div>` : ''}${app.unverified ? `<div class="note-ai">${icon('ai')}<span>Dieses Projekt ist ein ungeprüfter KI-Fund. Sieh dir die Projektseite an, bevor du installierst.</span></div>` : ''}
      ${st?.phase === 'error' ? `<div class="warn">${esc(st.message || 'Installation fehlgeschlagen')}</div>` : ''}</div>
    <div class="row">${action}${inst && native.available ? `<button class="btn" data-su="launch" data-pkg="${esc(inst.package)}">${icon('play')}Öffnen</button>` : ''}</div></div>`;
}

function suSettingsTable(v, prev) {
  const keys = Object.keys(v.settings || {});
  if (!keys.length) return v.changes?.length ? '' : '<p class="faint">Keine Einstellungen hinterlegt – App im Auslieferungszustand lassen.</p>';
  return `<dl class="su-settings">${keys.map((k) => {
    const changed = prev && String(prev.settings?.[k] ?? '') !== String(v.settings[k]);
    return `<dt>${esc(k)}</dt><dd class="${changed ? 'changed' : ''}">${esc(v.settings[k])}${changed && prev.settings?.[k] !== undefined ? ` <span class="faint">(vorher ${esc(prev.settings[k])})</span>` : ''}</dd>`;
  }).join('')}</dl>`;
}

function suSpark(series) {
  if (!series?.length) return '';
  const max = Math.max(...series, 1), w = 300, h = 46;
  const pts = series.map((v, i) => `${(i / Math.max(series.length - 1, 1) * w).toFixed(1)},${(h - v / max * (h - 4) - 2).toFixed(1)}`).join(' ');
  return `<svg class="su-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}"/></svg>`;
}
function suResultHTML(r, s, n) {
  if (!r.result?.fps) {
    return `<div class="su-round"><div class="su-round-head"><b>Runde ${n}</b><span class="rating bad">${r.verdict === 'broken' ? 'läuft nicht' : 'ohne Messung'}</span></div>
      <p class="muted">${esc(r.variant?.label || '')}${r.note ? ' · ' + esc(r.note) : ''}${r.result?.error === 'no-frames' ? ' · Atlas hat keine Bilder des Spiels gefunden (siehe Info → Selbsttest).' : ''}</p></div>`;
  }
  const res = r.result, j = suJudge(res, s);
  const temp = res.temp?.skinMax ? `${res.temp.skinMax} °C Gehäuse` : res.temp?.cpuMax ? `${res.temp.cpuMax} °C CPU` : '';
  return `<div class="su-round"><div class="su-round-head"><b>Runde ${n}</b><span class="rating ${j.level}">${esc(j.text)}</span>
      ${r.verdict ? `<span class="tag">${{ good: 'fühlt sich gut an', ok: 'geht so', bad: 'fühlt sich schlecht an' }[r.verdict] || ''}</span>` : ''}</div>
    <div class="su-numbers"><div><b>${res.fps.avg}</b><span>Ø FPS</span></div><div><b>${res.fps.low1 ?? '–'}</b><span>1 %-Low</span></div>
      <div><b>${res.frameMs?.p99 ?? '–'}</b><span>ms (99 %)</span></div><div><b>${res.stutters ?? '–'}</b><span>Ruckler</span></div>
      ${temp ? `<div><b>${esc(temp.split(' ')[0])}</b><span>${esc(temp.split(' ').slice(1).join(' '))}</span></div>` : ''}
      ${res.power?.avgW ? `<div><b>${res.power.avgW}</b><span>Watt</span></div>` : ''}</div>
    ${suSpark(res.series)}
    ${j.target.guessed && !j.reached ? `<p class="faint">Angenommenes Ziel: ${j.target.fps} FPS. Läuft das Spiel im Original mit ${j.target.fps === 60 ? 30 : 60}? Dann oben bei „Ziel“ umstellen.</p>` : ''}
    <p class="faint">${esc(r.variant?.label || '')}${r.variant?.changes?.length ? ' · geändert: ' + esc(r.variant.changes.join('; ')) : ''} · ${Math.round(res.seconds || 0)} s gemessen${res.refreshHz ? ` · Bildschirm ${res.refreshHz} Hz` : ''}${res.power?.plugged ? ' · am Netzteil' : ''}</p></div>`;
}

function suAiHTML(g, w, s, stopped = false) {
  const a = s.ai, busy = su.busy['ai:' + g.id + '|' + w.key];
  const pol = suPolicy().budget || {};
  const eur = s.cost?.eur || 0;
  const cost = s.cost?.calls ? `<span class="faint">KI bisher: ${s.cost.calls} ${s.cost.calls === 1 ? 'Anfrage' : 'Anfragen'}, ${Math.round((s.cost.in + s.cost.out) / 1000)} Tsd. Tokens${s.cost.priced ? `, ca. ${eur.toFixed(2).replace('.', ',')} €` : ''}</span>` : '';
  const over = s.cost?.priced && eur >= (pol.stopEur || 10) && !s.costOk;
  let body = '';
  if (busy) body = `<p class="muted">${icon('ai')} Die KI sucht nach der besten nächsten Änderung für genau dieses Spiel auf diesem Gerät … (bis zu 2 Minuten)</p>`;
  else if (a?.error) body = `<p class="warn">KI-Anfrage fehlgeschlagen: ${esc(a.error)}</p>`;
  else if (a?.advice) {
    const ad = a.advice;
    body = `<div class="su-advice"><p><b>${{ done: 'So lassen.', change: 'Vorschlag für die nächste Runde:', 'lower-target': 'Ziel senken.', 'other-way': 'Besser ein anderer Weg.' }[ad.decision] || ''}</b> ${esc(ad.summary)}</p>
      ${ad.changes?.length ? `<ol>${ad.changes.map((c) => `<li><b>${esc(c.setting)}</b> → <b>${esc(c.value)}</b>${c.where ? ` <span class="faint">(${esc(c.where)})</span>` : ''}<div class="muted">${esc(c.why)}${/^https:\/\//.test(c.source) ? ` <a class="link small" href="${esc(c.source)}" target="_blank" rel="noopener">Quelle ${icon('ext')}</a>` : ''}</div></li>`).join('')}</ol>` : ''}
      ${ad.expect ? `<p class="muted">Erwartung: ${esc(ad.expect)}</p>` : ''}${ad.alternative ? `<p class="muted">Alternative: ${esc(ad.alternative)}</p>` : ''}
      ${ad.decision === 'change' && ad.changes?.length ? `<div class="row"><button class="btn primary" data-su="ai-applied">Geändert – neu messen</button></div>` : ''}</div>`;
  }
  return `<div class="su-ai">${body}
    <div class="row">${over ? `<span class="warn">Kostengrenze von ${pol.stopEur || 10} € für diesen Spielweg erreicht.</span><button class="btn" data-su="cost-ok">Trotzdem weitermachen</button>`
      : `<button class="btn${a?.advice ? '' : ' primary'}" data-su="ai"${busy ? ' disabled' : ''}>${icon('ai')}${a?.advice ? 'KI erneut fragen' : stopped ? 'Trotzdem weitersuchen: KI fragen' : 'KI-Feintuning: nächste Änderung vorschlagen'}</button>`}${cost}</div>
    ${s.cost?.priced && eur >= (pol.warnEur || 5) && !over ? `<p class="faint">Hinweis: schon über ${pol.warnEur || 5} € für diesen Spielweg. Lohnt sich das noch?</p>` : ''}
    ${aiKey() ? '' : '<p class="faint">Dafür brauchst du einen OpenAI-Schlüssel (Info → KI-Sofortanalyse).</p>'}</div>`;
}

function viewSetup(b) {
  const [gid, ...rest] = b.split('/');
  const g = DB.byId.get(gid), key = rest.join('/');
  const w = g && suFindWay(g, key);
  if (!w) return `<div class="empty">Dieser Spielweg wurde nicht gefunden. <a class="link" href="#/">Zur Übersicht</a></div>`;
  const s = suSession(g, w);
  const prof = suProfile();
  const comps = suComponents(g, w);
  const play = suPlayApp(comps, s);
  const variants = suVariants(g, w, play?.app || (comps[0] && suChosen(comps[0], s, 0)));
  const vi = Math.min(s.variant || 0, variants.length - 1), variant = variants[vi];
  const outlook = suOutlook(w);
  const r = w.r;
  const stop = suStop(s);
  const lastRound = s.rounds[s.rounds.length - 1];
  const live = su.live && su.live.meta?.game === g.id && su.live.meta?.way === w.key ? su.live : null;
  const pol = suPolicy();
  let n = 0;

  // 1 Gerät und App
  const devOk = !native.available || !!suDeviceId();
  const devBody = !native.available
    ? `<p class="muted">Im Browser ist das hier eine Checkliste. Installieren, starten und messen kann die <b>Atlas-App</b> (Info → Atlas-App).</p>`
    : `${suDeviceId() ? `<p class="muted">${esc(prof.name)} erkannt${suDetected() ? '' : ' (von dir bestätigt)'} · ${Math.round(su.info.device.ramGb)} GB RAM · Android ${esc(su.info.device.android)}</p>`
        : `<p class="warn">Dieses Gerät (${esc(su.info?.device?.model || '?')}, ${esc(su.info?.device?.soc || 'Chip unbekannt')}) wurde nicht als ${esc(prof?.name || 'unterstütztes Gerät')} erkannt. Einrichten geht trotzdem; Messfahrten werden dann nicht in die Datenbank gemeldet.</p>
           <div class="row"><button class="btn" data-su="confirm-device">Das ist ein ${esc(prof?.name || '')}</button></div>`}
       ${suShell() ? '' : `<p class="muted">${icon('wrench')} Ohne <b>Shizuku</b> fragt Android bei jeder Installation nach und Atlas kann die Bildrate nicht messen. <a class="link" href="#/info" data-su-nav>Shizuku einrichten</a></p>`}`;

  // 2 Apps
  const appsOk = comps.length > 0 && comps.every((c, i) => suInstalled(suChosen(c, s, i)));
  const appsBody = comps.length ? comps.map((c, i) => suAppRow(g, w, c, i, s)).join('')
    : `<p class="muted">Für diesen Weg ist keine installierbare App hinterlegt. ${r?.links?.length ? 'Folge den Links des Projekts:' : 'Sieh in der Beschreibung des Wegs nach.'}</p>
       ${r?.links?.length ? `<div class="row">${r.links.map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ${icon('ext')}</a>`).join('')}</div>` : ''}`;

  // 3 Eigene Dateien
  const needs = r?.requires?.length ? r.requires : w.type === 'official' ? ['Das Spiel im Play Store kaufen bzw. installieren'] : [`Deine eigene Spieldatei von ${g.title} (${w.v.name})`];
  const filesOk = needs.every((_, i) => s.files?.[i]);
  const filesBody = `<p class="muted">Atlas lädt nie Spieldateien, BIOS oder Keys. Hak ab, was du schon auf dem Gerät hast.</p>
    <ul class="su-checks">${needs.map((x, i) => `<li><button class="su-check${s.files?.[i] ? ' on' : ''}" data-su="file" data-i="${i}" aria-pressed="${!!s.files?.[i]}">${icon('check')}</button><span>${esc(x)}</span></li>`).join('')}</ul>`;

  // 4 Einstellungen
  const prev = s.rounds.length ? lastRound.variant : null;
  const cfgBody = `${variants.length > 1 ? `<label class="field">Startpunkt<select class="su-select wide" data-su-variant>${variants.map((v, i) => `<option value="${i}"${i === vi ? ' selected' : ''}>${esc(v.label)}</option>`).join('')}</select></label>` : ''}
    <p class="faint">${esc(variant.note || '')}${variant.source ? ` <a class="link small" href="${esc(variant.source)}" target="_blank" rel="noopener">Quelle ${icon('ext')}</a>` : ''}</p>
    ${variant.kind === 'report' && variant.tier > 0 ? `<p class="faint">Stammt nicht vom ${esc(prof?.name || 'eigenen Gerät')}, aber von einem Gerät mit demselben Chip – als Startpunkt gut, die Messfahrt zeigt, ob es bei dir passt.</p>` : ''}
    ${suSettingsTable(variant, prev && prev.label !== variant.label ? prev : null)}
    ${s.nextChanges?.length ? `<div class="su-advice"><p><b>Für die nächste Runde ändern:</b></p><ol>${s.nextChanges.map((c) => `<li>${esc(c)}</li>`).join('')}</ol></div>` : ''}
    ${r?.steps?.length ? `<details class="settings"><summary>Schritte laut Projekt (${r.steps.length})</summary><ol>${r.steps.map((x) => `<li>${esc(x)}</li>`).join('')}</ol></details>` : ''}
    <p class="faint">Noch stellt Atlas diese Werte nicht selbst ein: öffne die App und übernimm sie von Hand${suDual() ? ' – die Liste bleibt hier unten stehen, während die App oben läuft' : ''}.</p>
    <div class="row">${play && native.available ? `<button class="btn" data-su="launch" data-pkg="${esc(play.package)}">${icon('wrench')}${esc(play.app.name)} öffnen</button>` : ''}
      <button class="btn${s.configured ? ' on' : ''}" data-su="configured" aria-pressed="${!!s.configured}">${icon('check')}${s.configured ? 'Eingestellt' : 'Habe ich eingestellt'}</button></div>`;

  // 5 Spielen und messen
  const secs = pol.measure?.seconds || 150;
  let playBody;
  if (live) {
    playBody = `<div class="su-live" id="su-live">${suLiveHTML(live)}</div><div class="row"><button class="btn" data-su="measure-stop">Messung jetzt beenden</button></div>`;
  } else if (!native.available) {
    playBody = `<p class="muted">Starte das Spiel in der App. Mit der Atlas-App misst Atlas dabei Bildrate, Ruckler und Temperatur.</p>`;
  } else if (!play) {
    playBody = `<p class="muted">Sobald die App installiert ist, kannst du hier starten und messen.</p>`;
  } else {
    playBody = `<p class="muted">Bei der <b>Messfahrt</b> startet Atlas ${esc(play.app.name)}, du lädst das Spiel und spielst ${(secs / 60).toLocaleString('de-DE', { maximumFractionDigits: 1 })} Minuten an einer typischen Stelle (nicht im Menü). Atlas misst im Hintergrund${suDual() ? ' und zeigt die Werte hier unten live' : ''}.</p>
      <div class="row"><span class="faint">Ziel:</span>${['auto', '30', '60'].map((t) => `<button class="chip" data-su="target" data-t="${t}" aria-pressed="${String(s.target || 'auto') === t}">${t === 'auto' ? 'automatisch' : t + ' FPS'}</button>`).join('')}</div>
      <div class="row"><button class="btn primary" data-su="measure"${suShell() ? '' : ' disabled'}>${icon('spark')}Messfahrt starten</button>
        <button class="btn" data-su="launch" data-pkg="${esc(play.package)}">${icon('play')}Nur spielen</button>
        <button class="btn" data-su="broken">Startet nicht / stürzt ab</button></div>
      ${suShell() ? '' : '<p class="faint">Messen braucht Shizuku (Info → Atlas-App). Ohne Messung kannst du unten trotzdem dein Urteil abgeben.</p>'}`;
  }

  // 6 Ergebnis
  let resBody = '<p class="faint">Noch keine Messfahrt für diesen Weg.</p>';
  if (s.rounds.length) {
    const needVerdict = lastRound.result?.fps && !lastRound.verdict;
    const untried = variants.map((v, i) => ({ v, i })).filter(({ v, i }) => i !== vi && v.kind !== 'default' && !s.rounds.some((x) => x.variant?.label === v.label));
    resBody = `${s.rounds.map((x, i) => suResultHTML(x, s, i + 1)).join('')}
      ${needVerdict ? `<div class="su-verdict"><p><b>Wie hat es sich angefühlt?</b> <span class="faint">Ton und Steuerung kann keine Messung beurteilen.</span></p>
        <div class="row"><button class="btn" data-su="verdict" data-v="good">Gut</button><button class="btn" data-su="verdict" data-v="ok">Geht so</button><button class="btn" data-su="verdict" data-v="bad">Schlecht</button></div></div>` : ''}
      ${stop?.stop ? `<div class="su-stop">${icon('check')}<span><b>Hier aufhören.</b> ${esc(stop.why)}${s.rounds.filter((x) => x.result?.fps).length > 1 ? ` Beste Runde: ${s.rounds.indexOf(stop.best) + 1} (Ø ${stop.best.result.fps.avg} FPS).` : ''}</span></div>` : ''}
      ${lastRound.result?.fps && !stop?.stop ? `<h4>Wie weiter?</h4>${suAiHTML(g, w, s)}
        ${untried.length ? `<div class="row"><span class="faint">Oder ohne KI:</span>${untried.slice(0, 2).map(({ v, i }) => `<button class="btn" data-su="try-variant" data-i="${i}">Andere Konfiguration probieren: ${esc(v.label)}</button>`).join('')}</div>` : ''}` : ''}
      ${stop?.stop && lastRound.result?.fps && !(suJudge(lastRound.result, s).reached) ? suAiHTML(g, w, s, true) : ''}
      <div class="row"><button class="btn${stop?.stop ? ' primary' : ''}" data-su="finish">${icon('check')}Fertig – so lasse ich es</button>
        <button class="btn" data-su="reset">Von vorn beginnen</button>${suOutboxHTML()}</div>`;
  }

  const back = `#/spiel/${encodeURIComponent(g.id)}`;
  return `<a class="btn back" href="${back}" data-goto-way="${esc(w.key)}">${icon('back')}Zum Spiel</a>
    <div class="su-head"><h1>Einrichten: ${esc(w.name)}</h1>
      <p class="muted">${esc(g.title)} · ${esc(w.v.name)}${prof ? ' · für ' + esc(prof.name) : ''}</p>
      <div class="row">${wayTag(w)}${isDual(w) ? `<span class="tag dual">${icon('dual')}${esc(dualLabel(w))}</span>` : ''}${s.done ? `<span class="tag v-thor-tested">${icon('check')}eingerichtet</span>` : ''}</div></div>
    ${outlook ? `<div class="su-outlook ${outlook.level}">${icon(outlook.level === 'good' ? 'check' : 'alert')}<span>${esc(outlook.text)}</span></div>` : ''}
    ${r?.status === 'archived' ? `<div class="su-outlook bad">${icon('alert')}<span>Dieses Projekt ist archiviert. ${esc(r.caveat || '')}</span></div>` : ''}
    ${r?.caveat && r.status !== 'archived' ? `<p class="warn">${esc(r.caveat)}</p>` : ''}
    ${suEmuChooser(g, w)}
    <div class="su-steps">
      ${suStep(++n, 'Gerät', devOk && (suShell() || !native.available) ? 'ok' : devOk ? 'part' : 'miss', devBody)}
      ${suStep(++n, comps.length > 1 ? 'Apps installieren' : 'App installieren', appsOk ? 'ok' : 'part', appsBody)}
      ${suStep(++n, 'Deine Dateien', filesOk ? 'ok' : 'part', filesBody)}
      ${suStep(++n, 'Einstellungen', s.configured ? 'ok' : 'part', cfgBody)}
      ${suStep(++n, 'Spielen und messen', s.rounds.some((x) => x.result?.fps) ? 'ok' : 'part', playBody)}
      ${suStep(++n, 'Ergebnis und Feintuning', s.done ? 'ok' : 'part', resBody)}
    </div>
    <details class="settings su-rules"><summary>Nach welchen Regeln Atlas optimiert</summary><ul>${(pol.rules || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ul></details>`;
}

function suLiveHTML(l) {
  if (l.state === 'waiting') return `<div class="su-live-wait">Warte auf das Spiel … <span class="faint">${l.waited || 0} s · lade jetzt das Spiel und spiel los</span></div>`;
  const left = Math.max(0, (l.seconds || 0) - (l.elapsed || 0));
  const t = l.temp?.skinMax ? `${l.temp.skinMax} °C` : l.temp?.cpuMax ? `${l.temp.cpuMax} °C` : '';
  return `<div class="su-live-fps"><b>${Math.round(l.fps)}</b><span>FPS</span></div>
    <div class="su-live-meta"><div>noch ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}</div>${t ? `<div>${t}</div>` : ''}<div class="faint">${esc(l.label || '')}</div></div>`;
}

function suRender() {
  if (!location.hash.startsWith('#/einrichten/') && !location.hash.startsWith('#/wege/') && !location.hash.startsWith('#/info')) return;
  if (/^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName || '')) return;   // nicht mitten im Tippen neu zeichnen
  const y = window.scrollY;
  const focus = document.activeElement?.dataset?.su ? `[data-su="${document.activeElement.dataset.su}"]` : null;
  route();
  window.scrollTo(0, y);
  if (focus) $(focus)?.focus({ preventScroll: true });
}

/* ---------- Badge und Leiste am Spielweg (Spielseite) ---------- */
function suBestRun(g, w) {
  const sess = suSessions()[g.id + '|' + w.key];
  if (!sess && !DB.setup.runs[g.id]) return null;
  const mine = (sess?.rounds || []).filter((r) => r.result?.fps).map((r) => ({ fps: r.result.fps, verdict: r.verdict, mine: true }));
  const db = (DB.setup.runs[g.id] || []).filter((r) => r.way === w.key && r.fps);
  return [...mine, ...db].sort((a, b) => b.fps.avg - a.fps.avg)[0] || null;
}
function setupBadge(g, w) {
  const b = suBestRun(g, w);
  return b ? `<span class="rating good" title="Messfahrt auf dem Gerät">${icon('check')}Ø ${b.fps.avg} FPS</span>` : '';
}
function setupBar(g, w) {
  if (w.fits === false) return '';
  const b = suBestRun(g, w);
  const s = suSessions()[g.id + '|' + w.key];
  const text = b ? `Auf dem ${esc(suProfile()?.name || 'Gerät')} gemessen: Ø ${b.fps.avg} FPS${b.fps.low1 ? `, 1 %-Low ${b.fps.low1}` : ''}` : s?.rounds?.length ? 'Einrichtung begonnen' : 'Noch nicht auf dem Gerät gemessen';
  return `<div class="su-bar"><a class="btn primary" href="${suHref(g, w)}">${icon('play')}${s?.done ? 'Einrichtung ansehen' : s?.rounds?.length ? 'Weiter einrichten' : 'Einrichten'}</a><span class="faint">${text}</span></div>`;
}

/* ---------- Info: Atlas-App, Shizuku, Selbsttest ---------- */
const SU_APK = () => `https://github.com/${DB.meta.repo}/releases/latest/download/handheld-atlas.apk`;
function suOutboxHTML() {
  const n = store.get('setupOutbox', []).length;
  if (!n) return '';
  return `<button class="btn" data-su="report">${icon('ext')}${n} ${n === 1 ? 'Ergebnis' : 'Ergebnisse'} ${ghToken() ? 'an Atlas melden' : 'als Issue senden'}</button>`;
}
function setupPanel() {
  const prof = suProfile();
  if (!native.available) {
    return `<div class="panel"><h3>${icon('play')} Atlas-App mit Setup-Assistent</h3>
      <p class="muted">Die App zeigt Atlas auf beiden Bildschirmen und richtet Spielwege ein: Apps installieren, starten, Bildrate messen, gezielt nachstellen. Erste Fassung nur für den ${esc(prof?.name || 'AYN Thor Max')}.</p>
      <ol class="su-install"><li>APK auf dem Handheld laden und öffnen; Android fragt einmal, ob dieser Browser Apps installieren darf.</li>
        <li>Für Updates: in Obtainium „App hinzufügen“ und <code>github.com/${esc(DB.meta.repo)}</code> eintragen.</li></ol>
      <div class="row"><a class="btn primary" href="${SU_APK()}">${icon('play')}APK laden</a><a class="btn" href="https://github.com/${esc(DB.meta.repo)}/releases" target="_blank" rel="noopener">Alle Versionen ${icon('ext')}</a></div>
      <p class="faint">Vorabversion: mit einem Schlüssel signiert, der offen im Repository liegt. Installiere die App nur von dieser Adresse.</p></div>`;
  }
  const i = su.info, sz = i?.shizuku || {};
  const st = store.get('setupSelftest', null);
  const szState = sz.granted ? 'bereit' : sz.running ? 'läuft, Freigabe fehlt' : sz.installed ? 'installiert, aber nicht gestartet' : 'nicht installiert';
  const szApp = DB.setup.apps.find((a) => a.id === 'shizuku');
  const upd = su.release && i && su.release.code > i.app.code ? su.release : null;
  const insSz = su.installing.shizuku;
  return `<div class="panel su-panel"><h3>${icon('play')} Atlas-App</h3>
    ${i ? `<ul class="checklist">
      <li class="ok">${icon('check')}Version ${esc(i.app.version)}${upd ? ` – neu: ${esc(upd.version)}` : ''}</li>
      <li class="${suDeviceId() ? 'ok' : 'part'}">${icon(suDeviceId() ? 'check' : 'alert')}${suDeviceId() ? esc(prof.name) + (suDetected() ? ' erkannt' : ' (bestätigt)') : `${esc(i.device.model)} · ${esc(i.device.soc || '?')} – nicht als ${esc(prof?.name || '')} erkannt`}</li>
      <li class="${i.dual ? (i.second ? 'ok' : 'part') : 'part'}">${icon(i.dual && i.second ? 'check' : 'info')}${i.dual ? (i.second ? 'Zwei Bildschirme aktiv' : 'Zweiter Bildschirm aus') : 'Ein Bildschirm'}</li>
      <li class="${sz.granted ? 'ok' : 'miss'}">${icon(sz.granted ? 'check' : 'alert')}Shizuku: ${szState}</li></ul>` : '<p class="muted">Lese Gerätedaten …</p>'}
    ${upd ? `<div class="row"><button class="btn primary" data-su="self-update">Atlas-App ${esc(upd.version)} installieren</button></div>` : ''}
    ${i && !suDeviceId() ? `<div class="row"><button class="btn" data-su="confirm-device">Das ist ein ${esc(prof?.name || '')}</button></div>` : ''}
    ${i?.dual ? `<div class="row"><button class="btn" data-su="second" data-open="${i.second ? '0' : '1'}">${icon('dual')}${i.second ? 'Zweiten Bildschirm ausschalten' : 'Atlas auf beiden Bildschirmen'}</button></div>` : ''}
    <h4>Shizuku</h4>
    <p class="muted">Gibt Atlas die Rechte von „adb“, ohne Root und ohne PC: installieren ohne Nachfrage, Bildrate und Temperatur messen. Nach jedem Neustart des Geräts einmal in Shizuku auf „Starten“ tippen (WLAN-Debugging).</p>
    <div class="row">${!sz.installed ? (insSz && insSz.phase !== 'error' && insSz.phase !== 'done' ? `<span class="su-progress">Shizuku wird installiert …</span>` : `<button class="btn primary" data-su="install-app" data-app="shizuku">Shizuku installieren</button>`)
      : !sz.running ? `<button class="btn primary" data-su="shizuku" data-a="open">Shizuku öffnen und starten</button>`
      : !sz.granted ? `<button class="btn primary" data-su="shizuku" data-a="request">Atlas freigeben</button>` : `<button class="btn" data-su="shizuku" data-a="open">Shizuku öffnen</button>`}
      ${szApp && insSz?.phase === 'error' ? `<span class="warn">${esc(insSz.message || '')}</span>` : ''}</div>
    ${!sz.installed || !sz.running ? `<details class="settings"><summary>So startest du Shizuku (einmal pro Neustart)</summary><ol>
      <li>Android-Einstellungen → Über das Gerät → siebenmal auf „Build-Nummer“ tippen (Entwickleroptionen).</li>
      <li>Entwickleroptionen → „Debugging über WLAN“ einschalten (WLAN muss verbunden sein).</li>
      <li>In Shizuku „Kopplung“ antippen, in den Entwickleroptionen „Gerät mit Kopplungscode koppeln“ wählen und den Code in der Shizuku-Benachrichtigung eingeben.</li>
      <li>In Shizuku auf „Starten“ tippen, dann hier „Atlas freigeben“.</li></ol></details>` : ''}
    <h4>Selbsttest</h4>
    <p class="muted">Prüft, was die App auf diesem Gerät wirklich kann, und meldet das Ergebnis zurück – damit die nächste Version zum Gerät passt.</p>
    ${st ? `<ul class="checklist">${st.checks.map((c) => `<li class="${c.ok ? 'ok' : 'miss'}" title="${esc(c.detail)}">${icon(c.ok ? 'check' : 'alert')}${esc(c.name)}</li>`).join('')}</ul>
      <details class="settings"><summary>Einzelheiten vom ${fmtDate(st.at)}</summary><dl>${st.checks.map((c) => `<dt>${esc(c.name)}</dt><dd>${esc(c.detail)}</dd>`).join('')}</dl></details>` : ''}
    <div class="row"><button class="btn${st ? '' : ' primary'}" data-su="selftest"${su.busy.selftest ? ' disabled' : ''}>${su.busy.selftest ? 'Teste …' : st ? 'Selbsttest wiederholen' : 'Selbsttest starten'}</button>${suOutboxHTML()}</div>
    <h4>KI-Kosten anzeigen</h4>
    <p class="faint">Optional: Preis deines Modells je 1 Mio. Tokens in Euro. Dann zeigt das Feintuning die Kosten je Spielweg und hält bei ${suPolicy().budget?.stopEur || 10} € an.</p>
    <div class="row"><label class="field su-price">Eingabe<input id="su-price-in" inputmode="decimal" value="${esc(store.get('aiPriceIn', ''))}"></label>
      <label class="field su-price">Ausgabe<input id="su-price-out" inputmode="decimal" value="${esc(store.get('aiPriceOut', ''))}"></label>
      <button class="btn" data-su="price-save">Speichern</button></div></div>`;
}

/* ---------- Aktionen ---------- */
function suContext() {
  const m = /^#\/einrichten\/([^/]+)\/(.+)$/.exec(location.hash);
  if (!m) return null;
  const g = DB.byId.get(decodeURIComponent(m[1]));
  const w = g && suFindWay(g, decodeURIComponent(m[2]));
  return w ? { g, w, s: suSession(g, w) } : null;
}

async function suResolveApk(repo) {
  const headers = { Accept: 'application/vnd.github+json', ...(ghToken() ? { Authorization: 'Bearer ' + ghToken() } : {}) };
  const get = async (path) => { const r = await fetch(`https://api.github.com/repos/${repo}/${path}`, { headers }); return r.ok ? r.json() : null; };
  const apks = (rel) => (rel?.assets || []).filter((a) => /\.apk$/i.test(a.name));
  let rel = await get('releases/latest');
  if (!apks(rel).length) rel = ((await get('releases?per_page=8')) || []).find((x) => apks(x).length) || null;
  const list = apks(rel);
  if (!list.length) return { none: true };
  const score = (a) => (/arm64|aarch64|v8a/i.test(a.name) ? 10 : 0) - (/x86|x64|armeabi|armv7|arm32|32bit/i.test(a.name) ? 100 : 0) + (/release/i.test(a.name) ? 1 : 0) - (/debug/i.test(a.name) ? 3 : 0);
  const ranked = list.map((a) => ({ name: a.name, size: a.size, url: a.browser_download_url, s: score(a) })).filter((a) => a.s > -50).sort((a, b) => b.s - a.s);
  if (!ranked.length) return { none: true };
  if (ranked.length === 1 || ranked[0].s > ranked[1].s) return { asset: ranked[0], tag: rel.tag_name };
  return { choices: ranked.filter((a) => a.s === ranked[0].s).slice(0, 6), tag: rel.tag_name };
}
async function suDoInstall(app, asset) {
  su.installing[app.id] = { phase: 'download', done: 0, total: asset.size, repo: app.source.repo };
  suRender();
  try {
    const res = await native.call('install', { repo: app.source.repo, url: asset.url, name: app.name, unverified: !!app.unverified }, 20 * 60e3);
    if (res.package) {
      if (!suPackages(app).includes(res.package)) {        // Paketname gelernt: lokal merken und an die Datenbank melden
        const pid = app.project || (app.projects || [])[0];
        store.set('setupLearned', { ...store.get('setupLearned', {}), ['app:' + app.id]: res.package, ...(pid ? { [pid]: res.package } : {}) });
        if (pid) suQueue({ packages: { [pid]: res.package } });
      }
    }
    su.installing[app.id] = { phase: res.done ? 'done' : 'confirm', repo: app.source.repo };
  } catch (e) {
    su.installing[app.id] = e.message === 'Abgebrochen' ? undefined : { phase: 'error', message: e.message, repo: app.source.repo };
  }
  await suRefreshPackages();
  suRender();
}
async function suInstall(app) {
  if (app.source?.type !== 'github' || !native.available) return;
  su.installing[app.id] = { phase: 'search', repo: app.source.repo };
  suRender();
  let pick;
  try { pick = await suResolveApk(app.source.repo); } catch { pick = { error: true }; }
  if (pick.asset) return suDoInstall(app, pick.asset);
  if (pick.choices) { su.installing[app.id] = { phase: 'choose', choices: pick.choices, repo: app.source.repo }; return suRender(); }
  su.installing[app.id] = { phase: 'error', repo: app.source.repo, message: pick.none ? 'Im neuesten Release liegt keine passende APK. Öffne die Projektseite.' : 'GitHub ist nicht erreichbar.' };
  suRender();
  if (pick.none) native.call('openUrl', { url: `https://github.com/${app.source.repo}/releases` }).catch(() => {});
}

function suQueue(part) {
  const out = store.get('setupOutbox', []);
  out.push(part);
  store.set('setupOutbox', out.slice(-60));
}
function suRunPayload(g, w, s, round, n) {
  const res = round.result || {};
  return { game: g.id, way: w.key, wayName: w.name, version: w.v.id, app: round.app || '', package: round.package || null, appVersion: res.appVersion || round.appVersion || '',
    round: n, target: round.result?.fps ? suTarget(s, res).fps : null, verdict: round.verdict || null, note: round.note || '',
    variant: { label: round.variant?.label || '', source: round.variant?.source || null, settings: round.variant?.settings || {}, changes: round.variant?.changes || [] },
    result: res.fps ? { seconds: res.seconds, fps: res.fps, frameMs: res.frameMs, stutters: res.stutters, refreshHz: res.refreshHz, temp: res.temp, power: res.power } : {} };
}
/** Rückmeldung an die Datenbank: mit GitHub-Schlüssel automatisch, sonst als vorbereitetes Issue. */
async function suReport(manual) {
  const parts = store.get('setupOutbox', []);
  if (!parts.length) return;
  const device = suDeviceId();
  const runs = parts.flatMap((p) => p.runs || []);
  if (runs.length && !device) { if (manual) toast('Messfahrten werden nur für das unterstützte Gerät gemeldet (Info → Atlas-App → „Das ist ein …“).'); if (!parts.some((p) => p.selftest || p.packages)) return; }
  const payload = { kind: 'setup-report', device, app: su.info?.app ? { version: su.info.app.version } : {}, at: new Date().toISOString(),
    runs: device ? runs : [], packages: Object.assign({}, ...parts.map((p) => p.packages || {})), selftest: parts.map((p) => p.selftest).filter(Boolean).pop() || undefined };
  const n = payload.runs.length;
  const title = `Setup-Rückmeldung vom Gerät: ${n} ${n === 1 ? 'Messfahrt' : 'Messfahrten'}${payload.selftest ? ' + Selbsttest' : ''} (${new Date().toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })})`;
  const body = `setup-report: ${n}\n\nAutomatische Rückmeldung des Setup-Assistenten (${suProfile()?.name || 'Gerät'}). Die Action übernimmt sie ohne KI (docs/SETUP.md).\n\n\`\`\`json\n${JSON.stringify(payload)}\n\`\`\`\n`;
  const done = () => { store.set('setupOutbox', []); scheduleRequestPoll(20000); suRender(); };
  if (!ghToken()) {
    if (manual) { openIssue(title, body); done(); }
    return;
  }
  try {
    const res = await fetch(`https://api.github.com/repos/${DB.meta.repo}/issues`, { method: 'POST',
      headers: { Authorization: 'Bearer ' + ghToken(), Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, body, labels: ['recherche'] }) });
    if (!res.ok) throw new Error('GitHub antwortet ' + res.status);
    done();
    toast('Ergebnis an Atlas gemeldet – in wenigen Minuten steht es in der Datenbank.');
  } catch (e) { if (manual) toast(esc(e.message)); }
}

/* KI-Feintuning: eine gezielte nächste Änderung, nach den Regeln aus policy.json (läuft auf dem Gerät, eigener Schlüssel). */
const SU_AI_FORMAT = { type: 'json_schema', name: 'atlas_tuning_step', strict: true, schema: { type: 'object', additionalProperties: false,
  required: ['decision', 'summary', 'target', 'changes', 'expect', 'alternative'],
  properties: {
    decision: { type: 'string', enum: ['done', 'change', 'lower-target', 'other-way'] },
    summary: { type: 'string' }, target: { type: 'integer' },
    changes: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['setting', 'value', 'where', 'why', 'source'],
      properties: { setting: { type: 'string' }, value: { type: 'string' }, where: { type: 'string' }, why: { type: 'string' }, source: { type: 'string' } } } },
    expect: { type: 'string' }, alternative: { type: 'string' } } } };
function suAiPrompt(g, w, s, play) {
  const prof = suProfile(), pol = suPolicy();
  const rounds = s.rounds.map((r, i) => ({ runde: i + 1, konfiguration: r.variant?.label, einstellungen: r.variant?.settings, geaendert: r.variant?.changes,
    ergebnis: r.result?.fps ? { fps: r.result.fps, frameMs: r.result.frameMs, ruckler: r.result.stutters, sekunden: r.result.seconds, temperatur: r.result.temp, watt: r.result.power?.avgW, bildschirmHz: r.result.refreshHz } : 'keine Messung',
    urteilDesSpielers: r.verdict || null, notiz: r.note || null }));
  const reports = (w.community || []).slice(0, 8).map((r) => ({ geraet: r.device, emulator: r.emulator, bewertung: r.ratingDe || r.rating, datum: r.date, notiz: r.summary, einstellungen: r.settings || null, quelle: r.url }));
  const others = waysFor(g).filter((x) => x.fits && x.key !== w.key).sort((a, b) => b.score - a.score).slice(0, 4).map((x) => ({ weg: x.name, fassung: x.v.name, community: x.best?.ratingDe || null }));
  return `Du bist der Feintuning-Assistent von „Handheld Atlas“. Ein Spieler hat sich bewusst für einen Spielweg entschieden und will, dass genau dieser Weg auf seinem Gerät so gut wie möglich läuft.

Gerät: ${prof?.name} (${prof?.soc}, ${prof?.gpu}, ${prof?.ramGb} GB RAM, Android ${prof?.android}; oberer Bildschirm ${prof?.displays?.[0]?.width}×${prof?.displays?.[0]?.height} mit ${prof?.displays?.[0]?.hz} Hz).
Spiel: „${g.title}“ – Fassung: ${w.v.name} (${w.v.platforms.join(', ')}). Spielweg: ${w.name} (${label('kinds', w.kind)}).
App: ${play?.app?.name || 'unbekannt'}${play?.version ? ' Version ' + play.version : ''}.
Ziel des Spielers: ${s.target && s.target !== 'auto' ? s.target + ' FPS' : 'automatisch (Originaltempo des Spiels)'}.

Bisherige Runden auf dem Gerät (gemessen von Atlas: Ø FPS, 1 %-Low, Bildzeiten, Ruckler, Temperatur):
${JSON.stringify(rounds)}

Berichte anderer Nutzer mit demselben Chip (EmuReady):
${JSON.stringify(reports)}

Andere Wege für dieses Spiel in Atlas: ${JSON.stringify(others)}

Regeln:
${(pol.rules || []).map((x, i) => `${i + 1}. ${x}`).join('\n')}

Aufgabe: Entscheide den nächsten Schritt. Suche im Web gezielt nach Einstellungen für genau dieses Spiel in dieser App auf Snapdragon 8 Gen 2 (AYN Thor, Odin 2, Retroid Pocket) und nach bekannten Problemen.
- "change": genau eine Änderung (oder ein zusammengehöriges Paar) mit der größten erwarteten Wirkung. "setting" und "value" so benennen, wie sie in der App heißen; "where" = Menüpfad; "source" = https-Adresse des Belegs oder leer.
- "done": Ziel erreicht oder weitere Runden lohnen nicht – nenne die beste Runde.
- "lower-target": Die Hardware schafft das Ziel auf diesem Weg nicht; nenne in "target" die stabile Stufe (z. B. 30) und in "changes" das Limit.
- "other-way": nur wenn dieser Weg auf dem Gerät nicht sinnvoll spielbar ist; nenne in "alternative" den besseren Weg.
"target" ist immer die Zielrate in FPS. Antworte auf Deutsch, knapp, ohne Erfundenes.`;
}
async function suAi(g, w) {
  const s = suSession(g, w), k = 'ai:' + g.id + '|' + w.key;
  if (!aiKey()) { toast('Trag zuerst deinen OpenAI-Schlüssel ein (Info → KI-Sofortanalyse).'); return; }
  su.busy[k] = true; suRender();
  try {
    const res = await fetch('https://api.openai.com/v1/responses', { method: 'POST',
      headers: { Authorization: 'Bearer ' + aiKey(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: aiModel(), store: false, tools: [{ type: 'web_search', search_context_size: 'medium' }], reasoning: { effort: 'medium' },
        text: { format: SU_AI_FORMAT }, input: suAiPrompt(g, w, s, suPlayApp(suComponents(g, w), s)), max_output_tokens: 8000 }) });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || `HTTP ${res.status}`);
    const text = (data.output || []).filter((o) => o.type === 'message').flatMap((o) => o.content || []).filter((c) => c.type === 'output_text').map((c) => c.text).join('\n');
    const pin = parseFloat(String(store.get('aiPriceIn', '')).replace(',', '.')), pout = parseFloat(String(store.get('aiPriceOut', '')).replace(',', '.'));
    const tin = data.usage?.input_tokens || 0, tout = data.usage?.output_tokens || 0;
    const c = s.cost || { calls: 0, in: 0, out: 0, eur: 0, priced: false };
    const priced = pin > 0 && pout > 0;
    s.cost = { calls: c.calls + 1, in: c.in + tin, out: c.out + tout, eur: c.eur + (priced ? (tin * pin + tout * pout) / 1e6 : 0), priced: priced || c.priced };
    s.ai = { advice: JSON.parse(text), at: Date.now() };
    if (s.ai.advice.target >= 10 && (s.ai.advice.decision === 'lower-target')) s.target = String(s.ai.advice.target);
  } catch (e) { s.ai = { error: e.message }; }
  delete su.busy[k];
  suSave(g, w, s); suRender();
}

document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-su]');
  if (!t) return;
  const act = t.dataset.su, ctx = suContext();
  e.preventDefault();
  if (act === 'open-source') {
    const url = t.dataset.market && native.available ? 'market://details?id=' + t.dataset.market : t.dataset.url;
    native.available ? native.call('openUrl', { url }).catch((err) => toast(esc(err.message))) : window.open(t.dataset.url, '_blank', 'noopener');
  } else if (act === 'launch') {
    native.call('launch', { package: t.dataset.pkg }).catch((err) => toast(esc(err.message)));
  } else if (act === 'reddit-login') {
    native.call('redditLogin').catch((err) => toast(esc(err.message)));
  } else if (act === 'shizuku') {
    native.call('shizuku', { action: t.dataset.a }).then((st) => { if (su.info) su.info.shizuku = st; suRender(); }).catch((err) => toast(esc(err.message)));
  } else if (act === 'second') {
    native.call('second', { open: t.dataset.open === '1' }).then(() => suLoadInfo()).catch((err) => toast(esc(err.message)));
  } else if (act === 'confirm-device') {
    store.set('setupDeviceConfirmed', true); suRender();
  } else if (act === 'price-save') {
    store.set('aiPriceIn', $('#su-price-in').value.trim()); store.set('aiPriceOut', $('#su-price-out').value.trim()); toast('Preise gespeichert.');
  } else if (act === 'install-app') {
    const app = DB.setup.apps.find((a) => a.id === t.dataset.app);
    if (app) suInstall(app);
  } else if (act === 'self-update') {
    suDoInstall({ id: 'atlas', name: 'Handheld Atlas', source: { type: 'github', repo: DB.meta.repo }, packages: [su.info.app.package] }, su.release.asset);
  } else if (act === 'selftest') {
    su.busy.selftest = true; suRender();
    native.call('selftest', {}, 120000).then((st) => {
      store.set('setupSelftest', st); suQueue({ selftest: st }); suReport(false);
    }).catch((err) => toast(esc(err.message))).finally(() => { delete su.busy.selftest; suRender(); });
  } else if (act === 'report') {
    suReport(true);
  } else if (ctx) {
    const { g, w, s } = ctx;
    const comps = suComponents(g, w);
    const variants = suVariants(g, w, suPlayApp(comps, s)?.app || (comps[0] && suChosen(comps[0], s, 0)));
    const variant = variants[Math.min(s.variant || 0, variants.length - 1)];
    if (act === 'install') suInstall(suChosen(comps[+t.dataset.comp], s, +t.dataset.comp));
    else if (act === 'install-asset') { const app = suChosen(comps[+t.dataset.comp], s, +t.dataset.comp); suDoInstall(app, su.installing[app.id].choices[+t.dataset.k]); }
    else if (act === 'file') { s.files = { ...s.files, [t.dataset.i]: !s.files?.[t.dataset.i] }; suSave(g, w, s); suRender(); }
    else if (act === 'configured') { s.configured = !s.configured; suSave(g, w, s); suRender(); }
    else if (act === 'target') { s.target = t.dataset.t; suSave(g, w, s); suRender(); }
    else if (act === 'measure') {
      const play = suPlayApp(comps, s);
      if (!play) return;
      const meta = { game: g.id, way: w.key };
      s.pending = { variant: { label: variant.label, source: variant.source, settings: variant.settings, changes: s.nextChanges || [] }, app: play.app.name, package: play.package, appVersion: play.version };
      suSave(g, w, s);
      su.live = { state: 'waiting', meta, label: g.title, waited: 0 };
      native.call('measureStart', { package: play.package, label: g.title, seconds: suPolicy().measure?.seconds || 150, meta, launch: true })
        .catch((err) => { su.live = null; toast(esc(err.message)); suRender(); });
      suRender();
    } else if (act === 'measure-stop') { native.call('measureStop').catch(() => {}); }
    else if (act === 'broken') {
      const note = window.prompt('Was passiert? (kurz, z. B. „schwarzer Bildschirm nach dem Logo“)') || '';
      const play = suPlayApp(comps, s);
      s.rounds.push({ at: Date.now(), variant: { label: variant.label, source: variant.source, settings: variant.settings, changes: s.nextChanges || [] }, result: null, verdict: 'broken', note,
        app: play?.app.name, package: play?.package, appVersion: play?.version });
      s.nextChanges = []; suSave(g, w, s);
      suQueue({ runs: [suRunPayload(g, w, s, s.rounds[s.rounds.length - 1], s.rounds.length)] });
      suRender();
    } else if (act === 'verdict') {
      const r = s.rounds[s.rounds.length - 1];
      r.verdict = t.dataset.v; suSave(g, w, s);
      suQueue({ runs: [suRunPayload(g, w, s, r, s.rounds.length)] });
      suRender();
    } else if (act === 'try-variant') { s.variant = +t.dataset.i; s.configured = false; s.nextChanges = []; s.ai = null; suSave(g, w, s); suRender(); window.scrollTo(0, 0); }
    else if (act === 'ai') suAi(g, w);
    else if (act === 'ai-applied') { s.nextChanges = (s.ai?.advice?.changes || []).map((c) => `${c.setting} → ${c.value}`); s.configured = true; suSave(g, w, s); suRender(); toast('Gut. Starte jetzt die nächste Messfahrt.'); }
    else if (act === 'cost-ok') { s.costOk = true; suSave(g, w, s); suRender(); }
    else if (act === 'finish') { s.done = true; suSave(g, w, s); suReport(false); suRender(); toast('Gespeichert. Viel Spaß beim Spielen!'); }
    else if (act === 'reset') { if (window.confirm('Alle Runden dieses Spielwegs auf diesem Gerät verwerfen?')) { suSave(g, w, { rounds: [], variant: 0, files: s.files, configured: false, target: 'auto' }); suRender(); } }
  }
}, true);
document.addEventListener('change', (e) => {
  const ctx = suContext();
  if (!ctx) return;
  const { g, w, s } = ctx;
  if (e.target.dataset.suVariant !== undefined) { s.variant = +e.target.value; s.configured = false; s.nextChanges = []; suSave(g, w, s); suRender(); }
  else if (e.target.dataset.suApp !== undefined) { s.apps = { ...s.apps, [e.target.dataset.suApp]: e.target.value }; suSave(g, w, s); suRender(); }
});

/* ---------- Ereignisse aus der App ---------- */
native.on('measure', (d) => {
  if (d.state === 'done') {
    const res = d.result || {}, meta = res.meta || su.live?.meta;
    su.live = null;
    const g = meta && DB.byId.get(meta.game), w = g && suFindWay(g, meta.way);
    if (w && (typeof dualRole === 'function' ? dualRole() !== 'companion' : true)) {   // only the main screen records the run
      const s = suSession(g, w), p = s.pending || {};
      if (res.series?.length > 240) { const k = Math.ceil(res.series.length / 240); res.series = res.series.filter((_, i) => i % k === 0); }
      s.rounds.push({ at: Date.now(), variant: p.variant || { label: '' }, app: p.app, package: p.package, appVersion: p.appVersion, result: res, verdict: null });
      s.pending = null; s.nextChanges = []; s.ai = null;
      suSave(g, w, s);
      if (location.hash !== suHref(g, w)) location.hash = suHref(g, w); else suRender();
    } else suRender();
    return;
  }
  const first = !su.live || su.live.state !== d.state;
  su.live = { ...d, meta: su.live?.meta || null };
  const el = document.getElementById('su-live');
  if (el && !first) el.innerHTML = suLiveHTML(su.live); else suRender();
});
native.on('install', (d) => {
  const id = Object.keys(su.installing).find((k) => su.installing[k]?.repo === d.repo);
  if (!id) return;
  if (d.phase === 'download') { Object.assign(su.installing[id], { phase: 'download', done: d.done, total: d.total }); }
  else if (d.phase === 'done') { su.installing[id] = { phase: 'done', repo: d.repo }; suRefreshPackages().then(suRender); }
  else if (d.phase === 'cancelled') { delete su.installing[id]; }
  else if (d.phase === 'error') { su.installing[id] = { phase: 'error', message: d.message, repo: d.repo }; }
  else if (d.phase === 'installing' && su.installing[id].phase !== 'confirm') su.installing[id].phase = 'installing';
  suRender();
});
native.on('shizuku', (st) => { if (su.info) { su.info.shizuku = st; suRender(); } });
native.on('reddit', (d) => { store.set('redditLogin', !!d.loggedIn); if (d.loggedIn) redditSync({ max: 12 }); suRender(); });
native.on('resume', () => { suLoadInfo(); });
native.on('screens', () => { suLoadInfo().then(() => typeof dualSetup === 'function' && dualSetup()); });   // zweites Fenster geöffnet oder geschlossen
native.on('error', (m) => toast(esc(String(m))));

async function suLoadInfo() {
  if (!native.available) return;
  try {
    su.info = await native.call('info');
    if (typeof dualSetup === 'function') dualSetup();
    const rs = await native.call('redditState').catch(() => null);
    if (rs) store.set('redditLogin', !!rs.loggedIn);
    await suRefreshPackages();
    if (!su.live) {
      const ms = await native.call('measureState').catch(() => null);
      if (ms?.running && ms.live) su.live = { ...ms.live, meta: null };
    }
    suRender();
  } catch (e) { console.error(e); }
}
async function suCheckRelease() {
  if (!native.available || !DB.meta.repo) return;
  try {
    const r = await fetch(`https://api.github.com/repos/${DB.meta.repo}/releases?per_page=10`, { headers: { Accept: 'application/vnd.github+json' } });
    if (!r.ok) return;
    // the newest build, not the first entry: GitHub does not list releases in version order
    const code = (x) => +x.tag_name.split('.').pop() || 0;
    const rel = (await r.json()).filter((x) => /^app-v/.test(x.tag_name) && (x.assets || []).some((a) => a.name === 'handheld-atlas.apk')).sort((x, y) => code(y) - code(x))[0];
    if (!rel) return;
    const a = rel.assets.find((x) => x.name === 'handheld-atlas.apk');
    const version = rel.tag_name.replace(/^app-v/, '');
    su.release = { version, code: code(rel), asset: { name: a.name, size: a.size, url: a.browser_download_url } };
    if (su.info && su.release.code > su.info.app.code && (typeof dualRole !== 'function' || dualRole() !== 'companion')) toast(`Atlas-App ${esc(version)} ist da. <button class="btn primary" data-su="self-update">Installieren</button>`, 0);
    suRender();
  } catch { /* offline */ }
}

/* Start: sobald die Daten geladen sind (app.js ruft suReady aus init(); lädt setup.js später, startet es sich selbst). */
let suStarted = false;
function suReady() {
  if (suStarted) return;
  suStarted = true;
  document.body.classList.toggle('in-app', native.available);
  route();
  if (!native.available) return;
  suLoadInfo().then(() => {
    if (store.get('setupOutbox', []).length) suReport(false);
  });
  setTimeout(suCheckRelease, 4000);
  window.addEventListener('hashchange', () => { const m = /^#\/spiel\/([^/]+)/.exec(location.hash); if (m) store.set('lastGame', decodeURIComponent(m[1])); });
}
if (DB.games.length) suReady();
