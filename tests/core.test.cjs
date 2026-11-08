const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../src/core.js');
const catalog = JSON.parse(fs.readFileSync(new URL('../data/catalog.json', 'file://' + __filename), 'utf8'));
const base = {profile:'thor',q:'',feature:'',kind:'',franchise:'',evidence:'',includeArchived:false,showOtherPlatforms:false};

test('the curated catalog has sourced routes and a separate broad games index',()=>{
  assert.equal(catalog.games.length,41);
  assert.equal(new Set(catalog.games.flatMap(g=>g.routes.map(r=>r.id))).size,60);
  assert.ok(catalog.gameIndex.length>=300);
  assert.ok(catalog.games.some(g=>g.routes.some(r=>r.media?.length)));
});
test('search is case and accent insensitive and finds project names',()=>{
  assert.ok(C.filterGames(catalog,{...base,q:'POKEMON'},{}).length>=1);
  assert.ok(C.filterGames(catalog,{...base,q:'Eden'}, {}).some(x=>x.game.id==='metroid-dread'));
});
test('dual-screen feature filtering applies to routes, not just games',()=>{
  const results=C.filterGames(catalog,{...base,feature:'dual-screen'},{});
  assert.ok(results.length>5);
  assert.ok(results.every(x=>x.routes.every(r=>r.features.includes('dual-screen'))));
  assert.ok(!results.some(x=>x.game.id==='cyberpunk-2077'));
});
test('no measured FPS evidence is invented',()=>{
  assert.deepEqual(C.filterGames(catalog,{...base,feature:'fps60-tested'},{}),[]);
});
test('archived variants are hidden unless requested',()=>{
  const game=catalog.games.find(g=>g.id==='super-metroid');
  assert.equal(C.matchingRoutes(game,base,catalog.profiles).length,2);
  assert.equal(C.matchingRoutes(game,{...base,includeArchived:true},catalog.profiles).length,3);
});
test('desktop and Android are not interchangeable',()=>{
  const r=catalog.games.find(g=>g.id==='majoras-mask').routes.find(r=>r.id==='mm-recomp');
  assert.equal(C.platformMatch(r,catalog.profiles.find(p=>p.id==='thor')),false);
  assert.equal(C.platformMatch(r,catalog.profiles.find(p=>p.id==='linux-x86_64')),true);
  assert.equal(C.platformMatch(r,catalog.profiles.find(p=>p.id==='linux-arm64')),false);
});
test('dangerous URL protocols and credentials are rejected',()=>{
  for(const u of ['javascript:alert(1)','data:text/html,x','http://github.com/a/b','https://me:secret@github.com/a/b','not-a-url'])assert.equal(C.safeURL(u),null);
  assert.equal(C.safeURL('https://github.com/a/b'),'https://github.com/a/b');
  assert.equal(C.escapeHTML('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;');
});
test('backup import only accepts known games, feature interests and checklist indices',()=>{
  const raw=JSON.parse('{"schemaVersion":1,"watch":{"super-metroid":{"interests":["updates","dual-screen","bad"]},"__proto__":{"interests":["updates"]}},"checks":{"sm-snes9x":[0,0,1,-1,40,"2"]},"profile":"unknown"}');
  const result=C.sanitizePreferences(raw,catalog);
  assert.deepEqual(Object.keys(result.watch),['super-metroid']);
  assert.deepEqual(result.watch['super-metroid'].interests,['updates','dual-screen']);
  assert.deepEqual(result.checks['sm-snes9x'],[0,1]);
  assert.equal(result.profile,'thor');
  assert.throws(()=>C.sanitizePreferences({schemaVersion:999},catalog));
});
test('a release does not satisfy a feature-specific watch',()=>{
  const watch={'minecraft':{interests:['dual-screen'],addedAt:'2026-01-01T00:00:00Z'}};
  const release={type:'release',repo:'exojosh/AynThorSecondScreen',detectedAt:'2026-02-01T00:00:00Z'};
  assert.equal(C.eventsForWatchlist([release],watch,catalog).length,0);
  const feature={...release,type:'feature_added',feature:'dual-screen',reviewed:true};
  assert.equal(C.eventsForWatchlist([feature],watch,catalog).length,1);
  assert.equal(C.eventsForWatchlist([{...feature,reviewed:false}],watch,catalog).length,0);
  assert.equal(C.eventsForWatchlist([{...feature,detectedAt:'2025-01-01T00:00:00Z'}],watch,catalog).length,0);
});
test('general update watches include new releases through source relationships',()=>{
  const watch={'minecraft':{interests:['updates'],addedAt:'2026-01-01T00:00:00Z'}};
  assert.equal(C.eventsForWatchlist([{type:'release',repo:'exojosh/AynThorSecondScreen',detectedAt:'2026-02-01T00:00:00Z'}],watch,catalog).length,1);
});

test('index-only titles are searchable and watchable but never claim routes',()=>{
  const e=catalog.gameIndex.find(x=>!catalog.games.some(g=>g.id===x.id));
  assert.ok(e,'at least one broad-index game exists');
  const withIndex={...catalog,games:[...catalog.games,{...e,original:e.platforms.join(' · '),routes:[],indexOnly:true}]};
  const hits=C.filterGames(withIndex,{...base,q:e.title},{});
  assert.ok(hits.some(x=>x.game.id===e.id && x.routes.length===0));
  const filtered=C.filterGames(withIndex,{...base,q:e.title,feature:'dual-screen'},{});
  assert.ok(!filtered.some(x=>x.game.id===e.id));
  const checked=C.sanitizePreferences({schemaVersion:1,watch:{[e.id]:{interests:['dual-screen']}},checks:{},profile:'thor'},withIndex);
  assert.deepEqual(checked.watch[e.id].interests,['dual-screen']);
});
test('Minecraft variants explicitly distinguish editions and runtimes',()=>{
  const mc=catalog.games.find(g=>g.id==='minecraft');
  assert.ok(mc.routes.length>=5);
  const exo=mc.routes.find(r=>r.id==='mc-exojosh');
  const abacus=mc.routes.find(r=>r.id==='mc-abacus');
  assert.ok(exo && abacus);
  assert.notEqual(exo.requiredVersion,abacus.requiredVersion);
  assert.notEqual(exo.runtime,abacus.runtime);
});
test('arbitrary custom titles can be exported and safely imported as watch-only placeholders',()=>{
  const data={schemaVersion:1,customGames:{'custom-unknown-n64-game':{title:'Unknown N64 Game',platform:'Nintendo 64'},'evil<script>':{title:'Injected'}} ,watch:{'custom-unknown-n64-game':{interests:['dual-screen','updates']}},checks:{},profile:'thor'};
  const clean=C.sanitizePreferences(data,catalog);
  assert.equal(clean.customGames['custom-unknown-n64-game'].title,'Unknown N64 Game');
  assert.equal(clean.customGames['evil<script>'],undefined);
  assert.deepEqual(clean.watch['custom-unknown-n64-game'].interests,['dual-screen','updates']);
});
