"""Browser smoke test for landscape cards, image carousel, keyboard and dual-preview toggles."""
import json, os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'Handheld-Atlas.html').read_text(encoding='utf-8')
media=json.loads((ROOT/'data/game_media.json').read_text(encoding='utf-8'))
media.setdefault('games',{})['stardew-valley']={
 'cover':{'url':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/413150/library_600x900.jpg','caption':'Stardew original cover','sourceUrl':'https://store.steampowered.com/app/413150/'},
 'screenshots':[{'url':f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/413150/ss_test_{i}.jpg','caption':f'Stardew original scene {i}','sourceUrl':'https://store.steampowered.com/app/413150/'} for i in range(1,4)]}
media['games']['animal-crossing-new-horizons']={
 'cover':{'url':'https://images.igdb.com/igdb/image/upload/t_cover_big/co12345.jpg','caption':'Official cover','sourceUrl':'https://www.igdb.com/games/animal-crossing-new-horizons'},
 'screenshots':[{'url':f'https://images.igdb.com/igdb/image/upload/t_screenshot_med/ac_scene_{i}.jpg','caption':f'Original Animal Crossing {i}','sourceUrl':'https://www.igdb.com/games/animal-crossing-new-horizons'} for i in range(1,4)]}
start=html.index('<script id="media-data" type="application/json">')+len('<script id="media-data" type="application/json">')
end=html.index('</script>',start)
html=html[:start]+json.dumps(media).replace('<','\\u003c')+html[end:]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 for width in [1440,390]:
  page=browser.new_page(viewport={'width':width,'height':900},has_touch=width<500,is_mobile=width<500)
  page.route('https://**',lambda route:route.abort('internetdisconnected'))
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html,wait_until='domcontentloaded')
  page.locator('#search').fill('Stardew Valley')
  card=page.locator('.game-card').first
  assert card.count()==1
  assert card.locator('.card-photo').count()==1
  assert card.locator('[data-card-step]').count()==2
  dims=card.locator('.game-cover').bounding_box()
  assert dims['width']>0 and dims['height']>0
  # Landscape image container fits card rather than the previous 3:4 portrait layout.
  assert dims['width']>=dims['height']*.90,(width,dims)
  before=card.get_attribute('data-preview-index')
  card.locator('[data-card-step="1"]').click()
  assert card.get_attribute('data-preview-index')!='0'
  assert 'Originalspiel' in card.locator('[data-preview-label]').inner_text() or 'Spielcover' in card.locator('[data-preview-label]').inner_text()
  card.locator('.card-open').click()
  assert page.locator('#detail-dialog').is_visible()
  hero=page.locator('.detail-original-gallery .atlas-gallery')
  assert hero.count()==1
  assert hero.locator('[data-gallery-index]').count()==3
  assert hero.locator('[data-gallery-counter]').inner_text()=='1 / 3'
  hero.locator('[data-gallery-step="1"]').click()
  assert hero.locator('[data-gallery-counter]').inner_text()=='2 / 3'
  hero.locator('[data-gallery-index="2"]').click()
  assert hero.locator('[data-gallery-counter]').inner_text()=='3 / 3'
  hero.focus();page.keyboard.press('ArrowLeft')
  assert hero.locator('[data-gallery-counter]').inner_text()=='2 / 3'
  page.locator('[data-close="detail"]').click()
  page.locator('#search').fill('Animal Crossing: New Horizons')
  page.locator('.game-card .card-open').first.click()
  assert page.locator('.detail-original-gallery .atlas-gallery').count()==1
  assert page.locator('.detail-original-gallery .atlas-gallery-photo').get_attribute('alt').startswith('Original Animal Crossing')
  # A documented game route shows its OWN variant screenshot gallery under the Spielwege tab.
  route_gallery=page.locator('.route-card .atlas-gallery').first
  assert route_gallery.count()==1
  assert route_gallery.locator('.atlas-gallery-photo').count()==1
  assert route_gallery.get_attribute('data-gallery')!=page.locator('.detail-original-gallery .atlas-gallery').get_attribute('data-gallery')
  page.locator('[data-tab="media"]').click()
  assert page.locator('.detail-body').inner_text().count('Originalspiel · allgemeine Spielszenen')==0
  assert page.locator('.detail-original-gallery .atlas-gallery').count()==1
  assert not errors,(width,errors)
  page.close()
 browser.close()
print('PASS 0.5.1: landscape card, manual image controls, keyboard, separate hero and route galleries, mobile')
