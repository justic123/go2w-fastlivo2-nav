import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import map_publish as m
class PublishTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.src=self.root/'source';self.src.mkdir();self.points=self.root/'points.npy';self.points.write_bytes(b'point payload');self.dest=self.root/'maps/new'
  for name in ('map.yaml','map.pgm'):(self.src/name).write_bytes(b'grid')
  (self.src/'metadata.json').write_text(json.dumps(dict(session='s')))
 def tearDown(self):self.tmp.cleanup()
 def test_complete_publish(self):
  m.publish(self.src,self.points,self.dest,'s');self.assertEqual((self.dest/'points.npy').read_bytes(),b'point payload');self.assertEqual(len(list(self.dest.iterdir())),4)
 def test_rgb_same_session_only(self):
  cache=self.root/'cache';cache.mkdir();(cache/'native-rgb.bin').write_bytes(bytes(24))
  meta=dict(session='s',frame='camera_init',from_mapping=True,count=1)
  (cache/'native-rgb.json').write_text(json.dumps(meta))
  m.publish(self.src,self.points,self.dest,'s',cache)
  self.assertEqual((self.dest/'display-rgb.bin').read_bytes(),bytes(24))
  self.assertEqual(json.loads((self.dest/'display-rgb.json').read_text())['frame'],'map')
  meta['session']='other';(cache/'native-rgb.json').write_text(json.dumps(meta))
  other=self.root/'maps/other';m.publish(self.src,self.points,other,'s',cache)
  self.assertFalse((other/'display-rgb.bin').exists())
 def test_copy_failure_leaves_no_loadable_map(self):
  real=m.shutil.copy2
  def fail(src,dest):
   if Path(src)==self.points:raise OSError('disk full')
   return real(src,dest)
  with patch.object(m.shutil,'copy2',side_effect=fail),self.assertRaises(OSError):m.publish(self.src,self.points,self.dest,'s')
  self.assertFalse(self.dest.exists());self.assertFalse(list(self.root.glob('map-save-*')));self.assertTrue(self.points.exists())
 def test_existing_map_and_wrong_session_preserved(self):
  with self.assertRaises(ValueError):m.publish(self.src,self.points,self.dest,'wrong')
  m.publish(self.src,self.points,self.dest,'s')
  with self.assertRaises(ValueError):m.publish(self.src,self.points,self.dest,'s')
  self.assertEqual((self.dest/'points.npy').read_bytes(),b'point payload')
if __name__=='__main__':unittest.main()
