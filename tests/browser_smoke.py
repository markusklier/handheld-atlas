"""Browser UI smoke tests; offline network blocked on purpose, no physical device claim."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'qa-artifacts'
OUT.mkdir(exist_ok=True)
html=(ROOT/'Handheld-Atlas.html').read_text(encoding='utf-8')
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':900},accept_downloads=True)
    page=context.new_page()
    page.route('https://raw.githubusercontent.com/**',lambda route:route.abort('internetdisconnected'))
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.evaluate("""() => {const values={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>values[k]||null,setItem:(k,v)=>values[k]=v,removeItem:k=>delete values[k]},configurable:true});} """)
    page.set_content(html,wait_until='domcontentloaded')
    assert page.locator('.game-card').count()==48
    assert '374 Spiele' in page.locator('#main').inner_text()
    assert page.locator('button[data-more]').count()==1
    checks.append('Expanded catalogue with pagination and separate broad index')
    page.screenshot(path=str(OUT/'desktop.png'),full_page=False)

    page.locator('#search').fill('Minecraft')
    assert page.locator('.game-card').count()>=1
    page.locator('.card-open[data-game="minecraft"]').click()
    assert page.locator('#detail-dialog').is_visible()
    assert page.locator('.route-card').count()>=5
    assert '1.21.1' in page.locator('#detail-dialog').inner_text()
    assert '1.21.11' in page.locator('#detail-dialog').inner_text()
    assert 'DroidBridge + Dual Screen HUD' in page.locator('#detail-dialog').inner_text()
    page.locator('[data-tab="research"]').click()
    assert 'Offline-Demolauf' in page.locator('#detail-dialog').inner_text()
    assert page.locator('.research-lead').count()>=3
    page.screenshot(path=str(OUT/'minecraft-research.png'),full_page=False)
    checks.append('Game-specific research tab separates synthetic candidate evidence from published routes')
    page.locator('[data-tab="routes"]').click()
    page.locator('[data-compare="mc-exojosh"]').check()
    page.locator('[data-compare="mc-abacus"]').check()
    page.locator('.compare-bar [data-tab="compare"]').click()
    assert page.locator('.compare-table thead th').count()==3
    assert 'Nicht getestet' in page.locator('.compare-table').inner_text()
    checks.append('Minecraft editions and cross-runtime comparison with no invented benchmarks')
    page.screenshot(path=str(OUT/'comparison.png'),full_page=False)
    page.locator('[data-tab="routes"]').click()
    page.locator('[data-setup="mc-exojosh"]').click()
    page.locator('#info-dialog [data-step="0"]').check()
    assert 'done' in page.locator('#info-dialog .setup-item').first.get_attribute('class')
    with page.expect_download() as event:
        page.locator('[data-recipe="mc-exojosh"]').click()
    plan=json.loads(Path(event.value.path()).read_text())
    assert plan['readOnly'] and not plan['automaticExecution']
    page.locator('[data-close="info"]').click()
    page.locator('#detail-dialog [data-watch="minecraft"]').click()
    page.locator('[data-close="detail"]').click()
    page.locator('#nav [data-nav="watchlist"]').click()
    assert page.locator('.watch-row').count()==1
    with page.expect_download() as event:page.locator('[data-export]').click()
    backup=json.loads(Path(event.value.path()).read_text())
    assert 'minecraft' in backup['watch']
    checks.append('Setup checklist and read-only export; watchlist persistence')

    # An unverified N64 game in the index must be watchable, not portrayed as tested.
    game_index=json.loads((ROOT/'data/catalog.json').read_text())['gameIndex']
    sample=next(g for g in game_index if 'Nintendo 64' in g['platforms'])
    page.locator('#nav [data-nav="discover"]').click()
    page.locator('#search').fill(sample['title'])
    page.locator(f'.card-open[data-game="{sample["id"]}"]').first.click()
    assert page.locator('#detail-dialog').is_visible()
    assert 'kein einzeln geprüfter' in page.locator('#detail-dialog').inner_text().lower()
    assert page.locator('.route-card').count()==0
    page.locator('#detail-dialog [data-watch]').first.click()
    page.locator('[data-close="detail"]').click()
    page.locator('#nav [data-nav="watchlist"]').click()
    assert page.locator('.watch-row').count()==2
    checks.append('An unverified Nintendo 64 title can be added to a feature watchlist')

    # Freeform private watchlist fallback when no game metadata exists yet.
    page.locator('#nav [data-nav="discover"]').click()
    page.locator('#search').fill('Example Unindexed N64 Homebrew')
    assert page.locator('.game-card').count()==0
    page.locator('[data-add-custom]').click()
    assert page.locator('.game-card').count()==1
    assert 'Example Unindexed N64 Homebrew' in page.locator('.game-card').inner_text()
    page.locator('#nav [data-nav="watchlist"]').click()
    assert page.locator('.watch-row').count()==3
    checks.append('Unknown custom game can be privately added to watchlist without compatibility claims')

    page.locator('#nav [data-nav="discover"]').click()
    page.locator('#search').fill('Metroid Dread')
    page.locator('.card-open[data-game="metroid-dread"]').click()
    assert page.locator('.route-screen-grid img[src^="https://raw.githubusercontent.com/igawa6/"]').count()>=1
    assert page.locator('.route-shot figcaption a').count()>=1
    # Network is explicitly blocked; fallback should be readable, not an empty rectangle.
    assert page.locator('.image-placeholder').count()>=1
    page.locator('[data-tab="media"]').click()
    assert page.locator('.gallery-section img').count()>=1
    page.locator('[data-close="detail"]').click()
    checks.append('Screenshots are attached to individual variants with source attributions and an offline fallback')

    page.locator('#search').fill('')
    page.locator('[data-feature="fps60-tested"]').count() == 0  # Not a marketing shortcut.
    page.locator('[data-reset]').click()
    page.locator('#evidence').select_option('documented')
    assert page.locator('.game-card').count()<=41
    page.locator('[data-reset]').click()
    page.locator('#franchise').select_option('The Legend of Zelda')
    assert page.locator('.game-card').count()>=3
    checks.append('Documented-only and franchise filters work without hiding index-only titles globally')

    payload={'schemaVersion':1,'watch':{'super-metroid':{'interests':['updates','bad']},'injected':{'interests':['updates']}},'checks':{},'profile':'thor'}
    page.locator('#import-file').set_input_files({'name':'prefs.json','mimeType':'application/json','buffer':json.dumps(payload).encode()})
    page.wait_for_timeout(50)
    page.locator('#nav [data-nav="watchlist"]').click()
    assert page.locator('.watch-row').count()==4
    checks.append('Sanitized import ignores unknown game IDs')

    page.locator('#nav [data-nav="discover"]').click()
    page.locator('[data-reset]').click()
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('#mobile-device').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(OUT/'mobile.png'),full_page=False)
    page.locator('.card-open[data-game="super-metroid"]').first.click()
    assert page.locator('#detail-dialog').is_visible()
    assert page.evaluate('document.querySelector("#detail-dialog").getBoundingClientRect().width <= innerWidth')
    page.locator('[data-close="detail"]').click()
    checks.append('390px mobile layout and dialog fit')
    assert errors==[],errors
    checks.append('No JavaScript page errors throughout interaction test')
    (OUT/'results.json').write_text(json.dumps({'passed':checks,'errors':errors,'mode':'HTML set_content, storage mocked, external images blocked'},indent=2))
    browser.close()
print('\n'.join('PASS '+c for c in checks))
