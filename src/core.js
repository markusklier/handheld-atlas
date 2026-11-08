/* Pure domain functions, shared by the browser and Node's test runner. */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AtlasCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  const normalize = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const escapeHTML = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function safeURL(value) {
    try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password ? u.href : null; }
    catch (_) { return null; }
  }
  function platformMatch(route, profile) {
    if (!profile || profile.platform === 'all') return true;
    if (!route.targets.includes(profile.platform)) return false;
    if (route.features.includes('dual-screen') && !profile.dual) return false;
    return true;
  }
  function matchingRoutes(game, filters, profiles) {
    const profile = profiles.find(p => p.id === filters.profile) || profiles[0];
    const tokens = normalize(filters.q).trim().split(/\s+/).filter(Boolean);
    return game.routes.filter(r => {
      if (!filters.showOtherPlatforms && !platformMatch(r, profile)) return false;
      if (!filters.includeArchived && r.status === 'archived') return false;
      if (filters.kind && r.kind !== filters.kind) return false;
      if (filters.evidence === 'documented' && r.status !== 'documented') return false;
      if (filters.feature && !r.features.includes(filters.feature)) return false;
      if (filters.effort && r.effort !== filters.effort) return false;
      if (filters.original && !normalize([game.original,...(game.knownPlatforms||[]),r.edition].join(' ')).includes(normalize(filters.original))) return false;
      if (filters.franchise && game.franchise !== filters.franchise) return false;
      const haystack = normalize([game.title, game.franchise, game.original, game.genre, r.name, r.edition, r.runtime, ...r.features].join(' '));
      return tokens.every(t => haystack.includes(t));
    });
  }
  function filterGames(catalog, filters, watchlist) {
    const tokens = normalize(filters.q).trim().split(/\s+/).filter(Boolean);
    const all = catalog.games.map(game => {
      const routes = matchingRoutes(game, filters, catalog.profiles);
      const broadIndex = game.routes.length === 0;
      const eligibleIndex = broadIndex && !filters.feature && !filters.kind && !filters.effort && !filters.evidence &&
        (!filters.franchise || game.franchise===filters.franchise) &&
        (!filters.original || (game.knownPlatforms||[]).includes(filters.original)) &&
        tokens.every(t=>normalize([game.title,game.franchise,game.original].join(' ')).includes(t));
      return {game,routes,eligible:routes.length>0 || eligibleIndex};
    }).filter(x=>x.eligible && (!filters.onlyWatched || Boolean(watchlist[x.game.id])));
    return all.sort((a,b) => {
      if(filters.sort==='az')return a.game.title.localeCompare(b.game.title,'de');
      // Routes with documentation take precedence, but every title remains searchable/watchable.
      if(Boolean(a.routes.length)!==Boolean(b.routes.length))return b.routes.length-a.routes.length;
      return a.game.title.localeCompare(b.game.title,'de');
    });
  }
  function sanitizePreferences(raw, catalog) {
    if (!raw || raw.schemaVersion !== 1 || typeof raw !== 'object') throw new Error('Unbekanntes Exportformat.');
    const customGames = Object.create(null);
    for (const [id,item] of Object.entries(raw.customGames || {}).slice(0,500)) {
      if (!/^custom-[a-z0-9-]{2,65}$/.test(id) || !item || typeof item !== 'object') continue;
      const title = String(item.title || '').trim().slice(0,100);
      const platform = String(item.platform || '').trim().slice(0,90);
      if (title.length < 2 || /[<>]/.test(title) || /[<>]/.test(platform)) continue;
      customGames[id] = {title,platform:platform || 'Plattform unbekannt'};
    }
    const ids = new Set([...catalog.games.map(g => g.id),...Object.keys(customGames)]);
    const routeIds = new Set(catalog.games.flatMap(g => g.routes.map(r => r.id)));
    const allowedInterests = new Set(['updates', ...Object.keys(catalog.features)]);
    const watch = Object.create(null);
    for (const [id, value] of Object.entries(raw.watch || {}).slice(0, 10000)) {
      if (!ids.has(id) || !value || typeof value !== 'object') continue;
      const interests = Array.isArray(value.interests) ? value.interests.filter(i => allowedInterests.has(i)) : [];
      watch[id] = {interests: [...new Set(interests)].slice(0, 20), addedAt: validDate(value.addedAt) ? value.addedAt : new Date().toISOString()};
    }
    const checks = Object.create(null);
    for (const [id, v] of Object.entries(raw.checks || {}).slice(0, 10000)) {
      if (routeIds.has(id) && Array.isArray(v)) checks[id] = [...new Set(v.filter(n => Number.isInteger(n) && n >= 0 && n < 30))];
    }
    const profile = catalog.profiles.some(p => p.id === raw.profile) ? raw.profile : 'thor';
    return {schemaVersion:1, watch, customGames, checks, profile, lastSeen:validDate(raw.lastSeen) ? raw.lastSeen : null};
  }
  function validDate(s) { return typeof s === 'string' && s.length <= 40 && Number.isFinite(Date.parse(s)); }
  function eventsForWatchlist(events, watch, catalog) {
    const repoGames = new Map();
    const sources = new Map(catalog.sources.map(s => [s.id, s]));
    catalog.games.forEach(g => g.routes.forEach(r => r.sources.forEach(id => {
      const repo = sources.get(id)?.repo;
      if (repo) { if (!repoGames.has(repo)) repoGames.set(repo, new Set()); repoGames.get(repo).add(g.id); }
    })));
    return events.filter(event => {
      const ids = event.gameId ? [event.gameId] : [...(repoGames.get(event.repo) || [])];
      return ids.some(id => {
        const item = watch[id];
        if (!item || Date.parse(event.detectedAt) < Date.parse(item.addedAt)) return false;
        return item.interests.includes('updates') ||
          (event.type === 'feature_added' && event.reviewed === true && item.interests.includes(event.feature));
      });
    });
  }
  return {normalize, escapeHTML, safeURL, platformMatch, matchingRoutes, filterGames, sanitizePreferences, eventsForWatchlist};
});
