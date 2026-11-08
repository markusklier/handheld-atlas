from pathlib import Path
p=Path('src/core.js');s=p.read_text()
start=s.index('  function matchingRoutes(')
end=s.index('  function sanitizePreferences',start)
s=s[:start]+'''  function matchingRoutes(game, filters, profiles) {
    const profile = profiles.find(p => p.id === filters.profile) || profiles[0];
    const tokens = normalize(filters.q).trim().split(/\\s+/).filter(Boolean);
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
    const tokens = normalize(filters.q).trim().split(/\\s+/).filter(Boolean);
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
''' +s[end:]
p.write_text(s)
# Make raw GitHub image allowed by CSP and clearly external and offline-unavailable.
p=Path('scripts/build.py');s=p.read_text().replace("img-src 'self' data:;", "img-src 'self' data: https://raw.githubusercontent.com;")
p.write_text(s)
# version display in template
p=Path('src/template.html');s=p.read_text().replace('<span>v0.1</span>','<span>v0.2</span>').replace('Spiel, Franchise oder Projekt suchen ...','Spiel, Franchise, Spielversion suchen ...')
p.write_text(s)
