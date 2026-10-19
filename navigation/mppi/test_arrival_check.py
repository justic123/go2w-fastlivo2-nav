import unittest
from arrival_check import stationary_report,verify_stop,completion_issues
class Tests(unittest.TestCase):
 def test_jittered_5hz(self):
  self.assertTrue(stationary_report([[0,0,0,i*.215] for i in range(12)])['stationary'])
 def test_not_enough_time_duplicate_gap_movement(self):
  for rows in ([[0,0,0,i*.1] for i in range(6)],[[0,0,0,1]]*12,[[0,0,0,i*.5] for i in range(12)],[[i*.01,0,0,i*.2] for i in range(12)]):self.assertFalse(stationary_report(rows)['stationary'])
 def test_stationary_after_transient(self):
  rows=[[i*.1,0,0,i*.2] for i in range(4)]+[[.3,0,0,i*.2] for i in range(4,20)]
  self.assertTrue(stationary_report(rows)['stationary'])
 def test_wait_fresh_samples_and_fail_stale(self):
  rows=[];clock=[0.]
  def pump():clock[0]+=.21;rows.append([0,0,0,clock[0]])
  result=verify_stop(pump,lambda:None,lambda:rows,lambda:clock[0]);self.assertTrue(result['stationary']);self.assertGreater(result['wait_s'],1.5)
  def unhealthy():raise RuntimeError('stale')
  self.assertFalse(verify_stop(pump,unhealthy,lambda:rows,lambda:clock[0])['stationary'])
  self.assertTrue(verify_stop(pump,lambda:None,lambda:rows,lambda:clock[0])['stationary'])
 def test_arrival_not_just_nav2_success(self):
  r=dict(navigation_status=4,stationary_after_stop=True,guard_stop=dict(stop_code=0),estimated_xy_error=.0495,estimated_yaw_error=.1007)
  self.assertEqual(completion_issues(r),[])
  self.assertTrue(completion_issues(dict(r,stationary_after_stop=False)))
  self.assertTrue(completion_issues(dict(r,estimated_xy_error=.081)))
  self.assertTrue(completion_issues(dict(r,reason='cancelled')))
if __name__=='__main__':unittest.main()
