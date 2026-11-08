"""Art/cover/route distinction in a network-blocked Chromium context."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'Handheld-Atlas.html').read_text(encoding='utf-8')
media=json.loads((ROOT/'data/game_media.json').read_text())
media['games']['stardew-valley']={
 'cover':{'url':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/413150/library_600x900.jpg','caption':'Steam library portrait','sourceUrl':'https://store.steampowered.com/app/413150/','portrait':True},
 'screenshots':[{'url':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/413150/ss_test.jpg','sourceUrl':'https://store.steampowered.com/app/413150/','caption':'Original gameplay'}]}
from html import escape
needle='<script id="media-data" type="application/json">'
start=html.index(needle)+len(needle)
end=html.index('</script>',start)
html=html[:start]+json.dumps(media).replace('<','\\u003c')+html[end:]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':900})
 page.route('https://**',lambda r:r.abort('internetdisconnected'))
 errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.set_content(html,wait_until='domcontentloaded')
 page.locator('#search').fill('Stardew Valley')
 card=page.locator('.game-card[data-abc]') if False else page.locator('.game-card').first
 assert card.locator('.game-cover-img').count()==1
 assert card.locator('img[data-hover-src]').count()==1
 card.hover()
 assert card.locator('img[data-hover-src]').get_attribute('src')
 card.locator('.card-open').click()
 assert page.locator('.detail-cover').count()==1
 page.locator('[data-tab="media"]').click()
 assert 'Originalspiel' in page.locator('#detail-dialog').inner_text()
 assert page.locator('.original-shot').count()==1
 page.locator('[data-close="detail"]').click()
 page.locator('#search').fill('Super Mario 64')
 page.locator('.card-open[data-game="super-mario-64"]').click()
 assert 'Mupen64Plus FZ' in page.locator('#detail-dialog').inner_text()
 assert 'keine Einzelspiel' in page.locator('#detail-dialog').inner_text()
 page.locator('[data-close="detail"]').click()
 page.locator('#search').fill('Minecraft')
 page.locator('.card-open[data-game="minecraft"]').click()
 page.locator('[data-tab="mods"]').click()
 assert 'Sodium' in page.locator('#detail-dialog').inner_text()
 assert 'nicht offiziell' in page.locator('#detail-dialog').inner_text()
 assert not errs,errs
 browser.close()
print('PASS cover, hover preview, general screenshot, N64 platform option, performance mods, no JS error')
