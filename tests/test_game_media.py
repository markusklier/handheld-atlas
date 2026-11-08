import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from enrich_game_media import same_game,clean_image,steam_metadata,igdb_metadata,run

class GameMediaTests(unittest.TestCase):
 def test_safe_urls(self):
  self.assertIsNone(clean_image('http://shared.fastly.steamstatic.com/a.jpg'))
  self.assertIsNone(clean_image('https://bad.example.com/a.png'))
  self.assertIsNone(clean_image('https://localhost/x.jpg'))
  self.assertIsNotNone(clean_image('https://shared.fastly.steamstatic.com/steam/apps/70/header.jpg'))
 def test_name_matches_are_exact(self):
  self.assertTrue(same_game('The Witcher 3: Wild Hunt','Witcher 3 Wild Hunt'))
  self.assertFalse(same_game('Minecraft Dungeons II','Minecraft Dungeons'))
 def test_steam_provider_sources_cover_and_scenes(self):
  def fetch(url):return {'413150':{'success':True,'data':{'name':'Stardew Valley',
     'header_image':'https://shared.fastly.steamstatic.com/steam/apps/413150/header.jpg',
     'screenshots':[{'path_full':'https://shared.fastly.steamstatic.com/steam/apps/413150/ss_a.jpg'}]}}}
  out=steam_metadata({'title':'Stardew Valley'},413150,fetch,lambda u:True)
  self.assertEqual(out['cover']['type'],'game-cover')
  self.assertTrue(out['cover']['portrait'])
  self.assertEqual(out['screenshots'][0]['type'],'original-game')
 def test_steam_wrong_game_rejected(self):
  out=steam_metadata({'title':'Portal 2'},400,lambda u:{'400':{'success':True,'data':{'name':'Portal'}}},lambda u:True)
  self.assertIsNone(out)
 def test_igdb_ambiguous_or_fuzzy_rejected(self):
  def fetched(url,headers=None,data=None):return [{'name':'Minecraft: Java Edition','cover':{'image_id':'coabc123'}}]
  self.assertIsNone(igdb_metadata({'title':'Minecraft'},'x','token',fetched))
 def test_run_preserves_existing(self):
  catalog={'games':[{'id':'stardew-valley','title':'Stardew Valley'}]}
  existing={'schemaVersion':1,'games':{'old':{'cover':{'url':'https://shared.fastly.steamstatic.com/a.jpg'}}}}
  result,info=run(catalog,{'steam':{'stardew-valley':413150}},existing,limit=1,fetch=lambda u:{'413150':{
    'success':True,'data':{'name':'Stardew Valley','header_image':'https://shared.fastly.steamstatic.com/steam/apps/413150/header.jpg','screenshots':[]}}},check=lambda u:False)
  self.assertIn('old',result['games'])
  self.assertEqual(info['added'],1)
  self.assertFalse(result['games']['stardew-valley']['cover']['portrait'])
if __name__=='__main__':unittest.main()
