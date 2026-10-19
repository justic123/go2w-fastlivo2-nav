import json,tempfile,unittest,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parent))
import map_store as m
class MapTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();r=Path(self.tmp.name);self.state={'phase':'navigation','map_id':'current','points':{'A':{'pose':[1,2,0]}},'preview':{'old':True}}
  def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d))
  self.c=SimpleNamespace(MPPI=r,STATE=r/'state.json',read=lambda p:json.loads(p.read_text()),write=write,state=lambda:self.state.copy(),assert_no_motion=Mock(),archive_state=Mock(),run=Mock(),save=lambda **kw:self.state.update(kw))
  for ident in ['current','other']:
   p=r/'maps'/ident;p.mkdir(parents=True)
   for n in ['map.yaml','map.pgm','points.npy']: (p/n).write_bytes(b'map data')
 def tearDown(self):self.tmp.cleanup()
 def test_delete_and_restore_preserves_bytes_without_selecting(self):
  token=m.delete(self.c,'other',m.version(self.c,'other'));self.c.run.assert_not_called()
  self.assertEqual(m.trash_entries(self.c)[0]['map_id'],'other');self.assertFalse((self.c.MPPI/'maps/other').exists())
  m.restore(self.c,token);self.assertEqual((self.c.MPPI/'maps/other/points.npy').read_bytes(),b'map data');self.assertEqual(self.state['map_id'],'current');self.assertEqual(m.trash_entries(self.c),[])
 def test_active_map_stops_nav_clears_selection_and_preview(self):
  self.c.write(self.c.MPPI/'selection.json',{'map_id':'current'})
  m.delete(self.c,'current',m.version(self.c,'current'))
  self.c.run.assert_called_once_with(['bash','MPPI导航.sh','stop']);self.assertIsNone(self.state['map_id']);self.assertIsNone(self.state['preview']);self.assertFalse((self.c.MPPI/'selection.json').exists())
 def test_changed_map_rejects_old_confirmation(self):
  v=m.version(self.c,'other');(self.c.MPPI/'maps/other/map.yaml').write_text('new')
  with self.assertRaisesRegex(ValueError,'变化'):m.delete(self.c,'other',v)
  self.assertTrue((self.c.MPPI/'maps/other').exists())
 def test_mapping_and_motion_block_deletion(self):
  self.state['phase']='mapping'
  with self.assertRaisesRegex(ValueError,'扫图'):m.delete(self.c,'other',m.version(self.c,'other'))
  self.state['phase']='navigation';self.c.assert_no_motion.side_effect=RuntimeError('motion')
  with self.assertRaisesRegex(RuntimeError,'motion'):m.delete(self.c,'other',m.version(self.c,'other'))
 def test_paths_links_and_restore_collision_rejected(self):
  for n in ['../current','/tmp','..','']:
   with self.assertRaises(ValueError):m.delete(self.c,n,'x')
  (self.c.MPPI/'maps/link').symlink_to(self.c.MPPI/'maps/current')
  with self.assertRaises(ValueError):m.delete(self.c,'link','x')
  token=m.delete(self.c,'other',m.version(self.c,'other'));(self.c.MPPI/'maps/other').mkdir()
  with self.assertRaisesRegex(ValueError,'同名'):m.restore(self.c,token)
 def test_failed_stop_keeps_map_and_state(self):
  self.c.run.side_effect=RuntimeError('stop failed')
  with self.assertRaises(RuntimeError):m.delete(self.c,'current',m.version(self.c,'current'))
  self.assertTrue((self.c.MPPI/'maps/current').exists());self.assertEqual(self.state['map_id'],'current')
if __name__=='__main__':unittest.main()
