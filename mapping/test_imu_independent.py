"""Exercise the production IMU reader without ROS or any lidar arrivals."""
import ast,csv,io,queue,threading,unittest
from pathlib import Path
from collections import deque
from types import SimpleNamespace as S
import numpy as np
class ReaderTests(unittest.TestCase):
 def test_imu_publishes_without_cloud_and_preserves_samples(self):
  source=ast.parse(Path(__file__).with_name('mapping_bridge.py').read_text())
  reader=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='imu_reader')
  published=[];stop=threading.Event();errors=queue.Queue();samples=deque(maxlen=4000)
  def msg():return S(header=S(),orientation_covariance=[0]*9,angular_velocity=S(),linear_acceleration=S())
  ns=dict(csv=csv,np=np,stop=stop,timing=io.StringIO(),errors=errors,clock=S(observe=lambda tick,receipt:receipt),stats={'max_receipt_tick_residual_ms':0.,'imu_published':0},Imu=msg,rospy=S(Time=S(from_sec=lambda x:x)),lock=threading.Lock(),imus=samples,ipub=S(publish=published.append))
  exec(compile(ast.Module(body=[reader],type_ignores=[]),'production_imu_reader','exec'),ns)
  header='receive_unix_ns,receive_monotonic_ns,tick,gx,gy,gz,ax,ay,az\n'
  rows=''.join(f'{1000000000+i*2000000},{i*2000000},{i*2},0,0,.1,0,0,9.81\n' for i in range(1500))
  ns['imu_reader'](S(stdout=io.BytesIO((header+rows).encode())))
  self.assertEqual(len(published),1500)
  self.assertEqual(len(samples),1500)
  self.assertEqual(ns['stats']['imu_published'],1500)
  self.assertAlmostEqual(published[-1].header.stamp,3.998)
  self.assertEqual(errors.get(),'IMU source ended unexpectedly')
if __name__=='__main__':unittest.main()
