import copy,importlib.util,json,tempfile,time,unittest,os
from pathlib import Path
from unittest.mock import Mock,patch
import mission
from route_model import route_spec,leg_timeout,stationary
from motion_modes import action_choice
class RouteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir();self.map=self.root/'maps/m';self.map.mkdir(parents=True)
  self.d=dict(phase='navigation',map_id='m',session='s',points={n:dict(name=n,pose=[i,0,0],frame='map',map_id='m',source_session='s') for i,n in enumerate(['A','B'],1)},route=dict(names=['A','B']))
  self.c=Mock();self.c.assert_no_motion=Mock();self.c.MPPI=self.root;self.c.state.side_effect=lambda:self.d;self.c.folder.return_value=self.run;self.c.current_map_pose.return_value=[0,0,0]
  self.c.write.side_effect=lambda p,d:Path(p).write_text(json.dumps(d));self.c.read.side_effect=lambda p:json.loads(Path(p).read_text());self.c.save.side_effect=lambda **kw:self.d.update(kw)
  fp=route_spec(self.d)['fingerprint'];self.d['route_preview']=dict(success=True,fingerprint=fp,source_session='s',created=time.time(),start=[0,0,0],segments=[dict(timeout_s=90),dict(timeout_s=90)])
  self.chosen=[];self.c.choose.side_effect=lambda n:self.chosen.append(n)
  def success(*_):
   target=self.d['points'][self.chosen[-1]];p=self.run/('protected-execute-'+str(len(self.chosen))+'.json');p.write_text(json.dumps(dict(success=True,stationary_after_stop=True,target=target)))
  self.c.run.side_effect=success;self.tick=0
 def tearDown(self):self.tmp.cleanup()
 def clock(self):self.tick+=.5;return self.tick
 def execute(self):
  with patch.object(mission.time,'sleep'),patch.object(mission.time,'monotonic',side_effect=self.clock):mission.execute(self.c)
 def test_order_and_stop_at_each(self):
  self.execute();self.assertEqual(self.chosen,['A','B']);self.assertEqual(json.loads((self.run/'route_progress.json').read_text())['completed'],2);self.assertFalse((self.run/'route_active.json').exists())
 def test_manual_handoff_cannot_have_automatic_successor(self):
  self.d['points']['A']['manual_handoff']=True
  with self.assertRaisesRegex(ValueError,'最后一点'):self.execute()
  self.c.run.assert_not_called()
 def test_last_point_handoff_ends_task_without_auto_resume(self):
  self.d['points']['B']['manual_handoff']=True;self.d['route_preview']['fingerprint']=route_spec(self.d)['fingerprint']
  self.execute();progress=json.loads((self.run/'route_progress.json').read_text())
  self.assertEqual(progress['phase'],'awaiting_manual');self.assertEqual(self.chosen,['A','B']);self.assertFalse((self.run/'route_active.json').exists())
 def test_handoff_change_invalidates_preview(self):
  self.d['points']['B']['manual_handoff']=True
  with self.assertRaisesRegex(RuntimeError,'重新预演'):self.execute()
  self.c.run.assert_not_called()
 def test_first_leg_failure_prevents_next(self):
  self.c.run.side_effect=RuntimeError('localization lost')
  with self.assertRaises(RuntimeError):self.execute()
  self.assertEqual(self.chosen,['A']);self.assertEqual(json.loads((self.run/'route_progress.json').read_text())['phase'],'stopped')
 def test_failure_reason_survives_nonzero_process(self):
  def bad(*_):
   (self.run/'protected-execute-new.json').write_text(json.dumps(dict(success=False,stationary_after_stop=False,target=self.d['points']['A'],reason='未确认停稳')))
   raise RuntimeError('generic command failed')
  self.c.run.side_effect=bad
  with self.assertRaisesRegex(RuntimeError,'未确认停稳'):self.execute()
  self.assertEqual(self.chosen,['A']);self.assertEqual(json.loads((self.run/'route_progress.json').read_text())['failed_result']['reason'],'未确认停稳')
 def test_old_success_cannot_complete_a_new_leg(self):
  p=self.run/'protected-execute-old.json';p.write_text(json.dumps(dict(success=True,stationary_after_stop=True,target=self.d['points']['A'])))
  os.utime(p,(time.time()-60,time.time()-60));self.c.run.side_effect=lambda *_:None
  with self.assertRaisesRegex(RuntimeError,'没有新执行结果'):self.execute()
  self.assertEqual(self.chosen,['A'])
 def test_wrong_coordinates_in_fresh_result_prevent_next_leg(self):
  def wrong(*_):
   t=copy.deepcopy(self.d['points']['A']);t['pose']=[99,0,0]
   (self.run/'protected-execute-new.json').write_text(json.dumps(dict(success=True,stationary_after_stop=True,target=t)))
  self.c.run.side_effect=wrong
  with self.assertRaisesRegex(RuntimeError,'坐标、地图'):self.execute()
  self.assertEqual(self.chosen,['A'])
 def test_stop_in_gap_does_not_start_next(self):
  original=self.c.run.side_effect
  def stop(*args):original(*args);(self.run/'route_cancel.request').touch()
  self.c.run.side_effect=stop
  with self.assertRaisesRegex(RuntimeError,'取消'):self.execute()
  self.assertEqual(self.chosen,['A'])
 def test_goal_edit_invalidates_preview(self):
  self.d['points']['A']['pose'][0]=3
  with self.assertRaisesRegex(RuntimeError,'重新预演'):self.execute()
  self.c.run.assert_not_called()
 def test_point_action_edit_invalidates_preview(self):
  self.d['points']['B']['arrival_motion']=action_choice('obstacle')
  with self.assertRaisesRegex(RuntimeError,'重新预演'):self.execute()
  self.c.run.assert_not_called()
 def test_unavailable_action_at_later_point_blocks_all_departure(self):
  self.d['points']['B']['arrival_motion']=action_choice('obstacle');self.d['route_preview']['fingerprint']=route_spec(self.d)['fingerprint']
  with patch('go2w_mode_adapter.Go2WModeAdapter.supported_modes',return_value=frozenset()),self.assertRaisesRegex(RuntimeError,'尚未配置'):self.execute()
  self.c.run.assert_not_called();self.assertEqual(self.chosen,[])
 def test_repeat_point_carries_the_saved_point_parameter(self):
  self.d['points']['A']['arrival_motion']=action_choice('obstacle')
  targets=route_spec(self.d,['A','B','A'])['targets']
  self.assertEqual([t['arrival_motion']['switch'] for t in targets],[True,False,True])
 def test_preview_expiry_does_not_move(self):
  self.d['route_preview']['created']=time.time()-61
  with self.assertRaises(RuntimeError):self.execute()
  self.c.run.assert_not_called()
 def test_not_stationary_after_stop_prevents_next(self):
  def bad(*_):(self.run/'protected-execute-1.json').write_text(json.dumps(dict(success=True,stationary_after_stop=False,target=self.d['points']['A'])))
  self.c.run.side_effect=bad
  with self.assertRaises(RuntimeError):self.execute()
  self.assertEqual(self.chosen,['A'])
 def test_repeat_target_keeps_order(self):self.assertEqual([x['name'] for x in route_spec(self.d,['A','B','A'])['targets']],['A','B','A'])
 def test_wrong_map_rejected(self):
  self.d['points']['A']['map_id']='other'
  with self.assertRaises(ValueError):route_spec(self.d)
 def test_time_budget_bounded_and_scales(self):
  self.assertEqual(leg_timeout(1),90);self.assertEqual(leg_timeout(20),280)
  with self.assertRaises(ValueError):leg_timeout(200)
 def test_stationary_requires_time_span_and_no_drift(self):
  rows=[[0,0,0,i/10] for i in range(20)];self.assertTrue(stationary(rows));self.assertFalse(stationary(rows[-5:]));rows[-1][0]=.1;self.assertFalse(stationary(rows))
if __name__=='__main__':unittest.main()
