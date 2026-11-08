"""Media discovery must use source galleries, not guessed screenshots."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from enrich_media import from_modrinth_gallery, from_github_tree, enrich_queue

class MediaEnrichmentTests(unittest.TestCase):
    def test_modrinth_gallery_uses_only_images_and_project_attribution(self):
        url='https://modrinth.com/mod/dual-screen-hud'
        entries=[{'url':'https://cdn.modrinth.com/data/a/images/screen.png','title':'Second-screen HUD'},
                 {'url':'https://evil.example/track.png','title':'Bad'},
                 {'url':'https://cdn.modrinth.com/data/a/images/screen.png','title':'Duplicate'}]
        x=from_modrinth_gallery(entries,url)
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]['caption'],'Second-screen HUD')
        self.assertEqual(x[0]['sourceUrl'],url)

    def test_github_tree_excludes_icons_and_embeds_project_origin(self):
        files=[{'type':'blob','path':'screenshots/dual-screen-map.png'},
               {'type':'blob','path':'src/assets/icons/button.png'},
               {'type':'blob','path':'docs/gallery/main-gameplay.webp'},
               {'type':'tree','path':'screenshots'}]
        x=from_github_tree(files,'example/handheld-mod','main')
        self.assertEqual(len(x),2)
        self.assertTrue(all(q['url'].startswith('https://raw.githubusercontent.com/example/handheld-mod/main/') for q in x))
        self.assertTrue(all('sourceUrl' in q for q in x))

    def test_queued_modrinth_project_is_enriched_without_ai(self):
        candidate={'id':'1','provider':'modrinth','gameId':'minecraft','project':'Dual Screen HUD',
                   'label':'Dual screen mod for Minecraft on Android handheld',
                   'url':'https://modrinth.com/mod/dual-screen-hud','discoveryMode':'live',
                   'score':2,'mediaCandidates':[]}
        def fake(url):
            self.assertEqual(url,'https://api.modrinth.com/v2/project/dual-screen-hud')
            return {'gallery':[{'url':'https://cdn.modrinth.com/data/a/images/actual.png','title':'In-game HUD'}]}
        x,stats=enrich_queue({'candidates':[candidate]},fake,lambda repo:None,stamp='2026-11-08T16:00:00Z')
        self.assertEqual(stats['newImages'],1)
        self.assertEqual(x['candidates'][0]['mediaCandidates'][0]['caption'],'In-game HUD')
        x2,s2=enrich_queue(x,lambda url:self.fail('refetch too soon'),lambda repo:None,stamp='2026-11-09T16:00:00Z')
        self.assertEqual(s2['checked'],0)

    def test_irrelevant_pet_companion_not_enriched(self):
        bad={'provider':'modrinth','gameId':'minecraft','project':'More Companions',
             'label':'Adds tameable pets to Minecraft','url':'https://modrinth.com/mod/pets',
             'discoveryMode':'live','score':2}
        _,stats=enrich_queue({'candidates':[bad]},lambda url:self.fail('should skip'),lambda repo:None)
        self.assertEqual(stats['eligible'],0)

    def test_github_readme_relative_images_are_branch_correct(self):
        candidate={'provider':'github','gameId':'minecraft','project':'Minecraft dual screen',
            'label':'Dual screen Android','url':'https://github.com/example/dualmod',
            'discoveryMode':'live','score':2,'mediaCandidates':[]}
        def fake(url):
            if url.endswith('/git/trees/main?recursive=1'):
                return {'tree':[]}
            return {'default_branch':'main'}
        x,stats=enrich_queue({'candidates':[candidate]},fake,
            lambda repo:'Readme\n![Dual screen](screenshots/dual.png)',
            stamp='2026-11-08T16:00:00Z')
        self.assertEqual(stats['newImages'],1)
        self.assertIn('/example/dualmod/main/screenshots/dual.png',x['candidates'][0]['mediaCandidates'][0]['url'])

if __name__=='__main__':unittest.main()
