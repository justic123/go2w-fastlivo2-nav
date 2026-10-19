import math,sys,unittest
from pose_transform import map_pose
class PoseConversion(unittest.TestCase):
 def test_rotated_map_position_and_body_heading(self):
  T=[[0,-1,0,10],[1,0,0,20],[0,0,1,0],[0,0,0,1]]
  p=map_pose([1,2,3,0,0,math.sin(.2),math.cos(.2)],T)
  self.assertEqual(p[:2],[8,21]);self.assertAlmostEqual(p[2],math.pi/2+.4)
 def test_invalid_values_rejected(self):
  T=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
  for p in ([0,0,0,0,0,0,0],[float('nan'),0,0,0,0,0,1]):
   with self.assertRaises((ValueError,RuntimeError)):map_pose(p,T)
 def test_import_does_not_load_numpy(self):
  import subprocess
  from pathlib import Path
  p=subprocess.run([sys.executable,'-c',"import pose_transform,sys; assert 'numpy' not in sys.modules"],cwd=Path(__file__).parent)
  self.assertEqual(p.returncode,0)
if __name__=='__main__':unittest.main()
