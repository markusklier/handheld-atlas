import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_project_sources import api_for_project,verify_one,select_projects
class ProjectChecksTests(unittest.TestCase):
 def test_only_known_api_hosts(self):
  self.assertEqual(api_for_project('https://github.com/azahar-emu/azahar'),'https://api.github.com/repos/azahar-emu/azahar')
  self.assertEqual(api_for_project('https://modrinth.com/mod/sodium'),'https://api.modrinth.com/v2/project/sodium')
  self.assertIsNone(api_for_project('https://github.com/owner/../secret'))
  self.assertIsNone(api_for_project('http://github.com/x/y'))
 def test_existing_repo_does_not_become_playability_claim(self):
  r=verify_one('https://github.com/azahar-emu/azahar',lambda api:{'full_name':'azahar-emu/azahar'},'2026-11-08T00:00:00Z')
  self.assertEqual(r['status'],'source-exists');self.assertNotIn('deviceTest',r)
 def test_rotation_selects_oldest(self):
  data={'projects':[{'url':'https://github.com/foo/bar'},{'url':'https://github.com/foo/baz'}]}
  previous={'projects':{'https://github.com/foo/bar':{'checkedAt':'2026-11-08'}}}
  self.assertEqual(select_projects(data,previous,1)[0]['url'],'https://github.com/foo/baz')
if __name__=='__main__':unittest.main()
