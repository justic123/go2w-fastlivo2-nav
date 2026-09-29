import importlib.util,io,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
class ForwardTests(unittest.TestCase):
 def run_worker(self, bad=False):
  messages=[]
  def msg():return S(header=S(),orientation_covariance=[0]*9,angular_velocity=S(),linear_acceleration=S())
  ros=S(init_node=lambda *a:None,Publisher=lambda *a,**k:S(publish=messages.append),is_shutdown=lambda:False,signal_shutdown=lambda *a:None,Time=S(from_sec=lambda x:x))
  spec=importlib.util.spec_from_file_location('worker_under_test',Path(__file__).with_name('imu_forward.py'));m=importlib.util.module_from_spec(spec)
  with patch.dict(sys.modules,{'rospy':ros,'sensor_msgs':S(),'sensor_msgs.msg':S(Imu=msg)}):spec.loader.exec_module(m)
  header='receive_unix_ns,receive_monotonic_ns,tick,gx,gy,gz,ax,ay,az\n'
  rows=''.join(f'{1000000000+i*2000000},{i*2000000},{i*2},{"nan" if bad and i==600 else "0"},0,.1,0,0,9.81\n' for i in range(2000))
  proc=S(stdout=io.BytesIO((header+rows).encode()),poll=lambda:0,wait=lambda **k:0)
  with tempfile.TemporaryDirectory() as d,patch.object(sys,'argv',['worker',d]),patch.object(m.signal,'signal'),patch.object(m.subprocess,'Popen',return_value=proc):
   with self.assertRaises(SystemExit):m.main()
   summary=json.loads((Path(d)/'imu_summary.json').read_text())
  return messages,summary
 def test_ordered_continuous_without_cloud(self):
  a,s=self.run_worker();self.assertEqual(len(a),1501)
  self.assertTrue(all(y.header.stamp>x.header.stamp for x,y in zip(a,a[1:])))
  self.assertAlmostEqual(a[-1].header.stamp,4.998)
  self.assertEqual(s['failure'],'IMU source ended unexpectedly')
 def test_nonfinite_stops_before_publication(self):
  a,s=self.run_worker(True);self.assertEqual(len(a),101);self.assertEqual(s['failure'],'Nonfinite IMU')
if __name__=='__main__':unittest.main()
