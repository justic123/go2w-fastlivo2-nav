import unittest,copy,numpy as np
from record_policy import Recorder
class RecordingTests(unittest.TestCase):
 def data(self,stamp=100):
  return dict(ready=True,updated=100,session='s',pose_age_s=.2,cloud_age_s=.3,pose=dict(stamp=stamp,pose=[1,2,0,0,0,0,1])),dict(ready=True,updated=100,map_id='m',source_session='s',transform=np.eye(4).tolist())
 def test_stationary_record_is_estimate_not_ground_truth(self):
  r=Recorder('m','s')
  for i in range(18):r.observe(*self.data(100+i*.2),100)
  t=r.target('A',100);self.assertEqual(t['pose'],[1,2,0]);self.assertIsNone(t['ground_truth'])
 def test_full_pose_keeps_height_and_pitch_and_rejects_pitch_motion(self):
  from scipy.spatial.transform import Rotation
  r=Recorder('m','s');q=Rotation.from_euler('xyz',[.01,.02,.3]).as_quat().tolist()
  for i in range(18):
   d,l=self.data(100+i*.2);d['pose']['pose']=[1,2,.7,*q];r.observe(d,l,100)
  t=r.target('A',100);self.assertAlmostEqual(t['map_pose'][2],.7);np.testing.assert_allclose(t['map_pose'][3:],q)
  d,l=self.data(104);d['pose']['pose']=[1,2,.7,*Rotation.from_euler('xyz',[.01,.1,.3]).as_quat().tolist()];r.observe(d,l,100)
  with self.assertRaises(ValueError):r.target('A',100)
 def test_changed_map_session_future_and_nonfinite_rejected(self):
  for side,key,value in [(0,'session','other'),(1,'source_session','other'),(1,'map_id','other'),(0,'updated',101),(0,'updated',float('nan')),(0,'cloud_age_s',float('nan'))]:
   d,l=self.data();[d,l][side][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):Recorder('m','s').observe(d,l,100)
 def test_backward_time_and_motion_rejected(self):
  r=Recorder('m','s');r.observe(*self.data(100),100)
  with self.assertRaises(ValueError):r.observe(*self.data(99),100)
  for i in range(1,18):
   d,l=self.data(100+i*.2);d['pose']['pose'][0]+=.1;r.observe(d,l,100)
  with self.assertRaisesRegex(ValueError,'变化'):r.target('A',100)
 def test_duplicates_and_invalid_transform_cannot_produce_target(self):
  r=Recorder('m','s')
  for _ in range(35):r.observe(*self.data(),100)
  with self.assertRaises(ValueError):r.target('A',100)
  d,l=self.data();l['transform'][0][0]=2
  with self.assertRaises(ValueError):r.observe(d,l,100)
if __name__=='__main__':unittest.main()
