import importlib.util,json,tempfile,time,unittest,io,sys
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('console',Path(__file__).with_name('console.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class FlowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.patch=patch.multiple(c,ROOT=self.root,MPPI=self.root/'navigation/mppi',STATE=self.root/'demo/state.json');self.patch.start()
  c.write(c.STATE,dict(phase='navigation',session='s1',map_id='m1',points={'B':dict(source_session='s1',map_id='m1',pose=[0,0,0])}))
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def test_saved_map_does_not_hide_failed_fusion(self):
  r=self.root/'run';r.mkdir();c.write(r/'runtime.json',dict(phase='failed',error='Child exited: receive'))
  with patch.object(c,'desk',return_value={'folder':str(r)}):
   self.assertIn('Child exited: receive',c.service_problem())
 def test_stale_fusion_blocks_ready_message(self):
  r=self.root/'run';r.mkdir();c.write(r/'runtime.json',dict(phase='running'))
  c.write(r/'health.json',dict(ready=True,updated=time.time()-10))
  with patch.object(c,'desk',return_value={'folder':str(r)}):
   self.assertIn('过期',c.service_problem())
 def recovery_fixture(self):
  m=c.MPPI/'maps/m1';m.mkdir(parents=True)
  for n in ('map.yaml','map.pgm','points.npy'):(m/n).touch()
  d=c.state();d['points']['B']['frame']='map';c.write(c.STATE,d)
  r=self.root/'run';r.mkdir();candidate=dict(map_id='m1',source_session='s2',accepted=True,consensus=4,created=time.time(),transform=[[1,0,0,2],[0,1,0,3],[0,0,1,0],[0,0,0,1]])
  c.write(r/'registration_candidate.json',candidate);return r,candidate
 def test_restore_preserves_map_coordinates_and_requires_new_preview(self):
  r,_=self.recovery_fixture();c.save(route_resume_preview={'source_session':'s1','success':True})
  with patch.object(c,'assert_no_motion'),patch.object(c,'desk',return_value={'run':'s2'}),patch.object(c,'folder',return_value=r),patch.object(c,'run') as run,patch.object(c,'wait_ready'),patch.object(c,'health'):
   c.restore()
   d=c.state();self.assertEqual(d['session'],'s2');self.assertEqual(d['points']['B']['pose'],[0,0,0]);self.assertEqual(d['points']['B']['source_session'],'s2');self.assertEqual(d['points']['B']['original_source_session'],'s1');self.assertIsNone(d['preview']);self.assertIsNone(d['route_resume_preview'])
   self.assertFalse(any('return-execute' in call.args[0] for call in run.call_args_list))
 def test_rejected_match_keeps_old_goals_unbound(self):
  r,candidate=self.recovery_fixture();candidate['accepted']=False;c.write(r/'registration_candidate.json',candidate)
  with patch.object(c,'assert_no_motion'),patch.object(c,'desk',return_value={'run':'s2'}),patch.object(c,'folder',return_value=r),patch.object(c,'run'),patch.object(c,'wait_ready'),patch.object(c,'health'):
   with self.assertRaisesRegex(RuntimeError,'匹配'):c.restore()
  d=c.state();self.assertEqual(d['phase'],'recovery_failed');self.assertEqual(d['points']['B']['source_session'],'s1');self.assertFalse((c.MPPI/'selection.json').exists())
 def test_registration_rejects_wrong_session_stale_and_invalid_transform(self):
  _,candidate=self.recovery_fixture()
  for change in ({'source_session':'s1'},{'created':time.time()-61},{'transform':[[0]*4]*4},{'consensus':2}):
   with self.subTest(change=change),self.assertRaises(RuntimeError):c.validate_registration(dict(candidate,**change),'m1','s2')
 def test_assisted_registration_requires_four_supporters_even_if_marked_accepted(self):
  _,candidate=self.recovery_fixture()
  with self.assertRaisesRegex(RuntimeError,'一致候选 3'):
   c.validate_registration(dict(candidate,method='user_hint_multistart_icp',consensus=3),'m1','s2')
 def test_failed_recovery_cannot_navigate(self):
  c.save(phase='recovery_failed')
  with patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'尚未恢复'):c.navigate('B')
   run.assert_not_called()
 def test_live_validation_failure_does_not_rebind_goals(self):
  r,_=self.recovery_fixture()
  with patch.object(c,'assert_no_motion'),patch.object(c,'desk',return_value={'run':'s2'}),patch.object(c,'folder',return_value=r),patch.object(c,'run'),patch.object(c,'wait_ready',side_effect=[None,RuntimeError('validation failed')]),patch.object(c,'health'):
   with self.assertRaisesRegex(RuntimeError,'validation failed'):c.restore()
  self.assertEqual(c.state()['points']['B']['source_session'],'s1');self.assertEqual(c.state()['phase'],'recovery_failed')
 def test_assist_rejects_unfinished_mapping(self):
  c.save(phase='mapping')
  with patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'结束扫图'):c.assisted_restore()
   run.assert_not_called()
 def test_assisted_prepare_keeps_healthy_fusion(self):
  r,_=self.recovery_fixture();c.write(r/'runtime.json',dict(phase='running'));c.write(r/'health.json',dict(ready=True,updated=time.time()))
  with patch.object(c,'desk',return_value={'folder':str(r)}),patch.object(c,'assert_no_motion'),patch.object(c,'wait_ready'),patch.object(c,'run') as run:
   c.prepare_assisted_inputs()
   commands=[call.args[0] for call in run.call_args_list]
   self.assertFalse(any('重新采集.sh' in x or 'desktop/control.py' in x for x in commands))
   self.assertIn(['bash','MPPI导航.sh','stop'],commands)
 def test_load_saved_map_preserves_targets_but_blocks_motion(self):
  self.recovery_fixture()
  with patch.object(c,'assert_no_motion'),patch.object(c,'run') as run,patch.object(c,'view'):
   c.load_map('m1')
   self.assertEqual(c.state()['points']['B']['pose'],[0,0,0]);self.assertEqual(c.state()['phase'],'map_selected')
   self.assertIn('尚未验证',c.service_problem())
   with self.assertRaises(RuntimeError):c.navigate('B')
   self.assertFalse(any('return-execute' in call.args[0] for call in run.call_args_list))
 def test_visual_profile_matches_gray_reference(self):
  import yaml
  root=Path(__file__).resolve().parents[1]/'navigation/mppi'
  d=yaml.safe_load((root/'view.rviz').read_text())['Visualization Manager'];displays=d['Displays']
  for topic in ('/global_costmap/costmap','/local_costmap/costmap'):
   layer=next(x for x in displays if x.get('Topic',{}).get('Value')==topic)
   self.assertEqual(layer['Enabled'],topic=='/global_costmap/costmap');self.assertEqual(layer['Color Scheme'],'map')
  self.assertTrue(all(x['Enabled'] for x in displays if x['Class']=='rviz_default_plugins/PointCloud2'))
  self.assertTrue(any(x['Class']=='rviz_default_plugins/SetInitialPose' for x in d['Tools']))
  goal=next(x for x in d['Tools'] if x['Class']=='rviz_default_plugins/SetGoal')
  self.assertEqual(goal['Topic'],'/demo/goal_pose')
 def test_stop_cancels_remaining_route_even_between_legs(self):
  r,_=self.recovery_fixture();(r/'route_active.json').write_text('{}')
  with patch.object(c,'folder',return_value=r),patch.object(c.subprocess,'run'):
   c.stop_motion()
  self.assertTrue((r/'route_cancel.request').exists())
 def test_new_session_rejects_old_goal_before_any_command(self):
  with patch.object(c,'desk',return_value={'run':'s2'}),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'会话'):c.navigate('B')
   run.assert_not_called()
 def test_no_preview_cannot_move(self):
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'预演'):c.navigate('B')
   run.assert_not_called()
 def test_expired_preview_cannot_move(self):
  c.save(preview={'name':'B','at':time.time()-61,'pose':[0,0,0]})
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'预演'):c.navigate('B')
   run.assert_not_called()
 def test_wrong_target_preview_cannot_move(self):
  c.save(preview={'name':'A','at':time.time(),'pose':[0,0,0]})
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'预演'):c.navigate('B')
   run.assert_not_called()
 def test_robot_moved_after_preview_cannot_move(self):
  c.save(preview={'name':'B','at':time.time(),'pose':[0,0,0]});r=self.root/'run';r.mkdir()
  c.write(r/'input.json',{'pose':{'pose':[1,0,0,0,0,0,1]}});c.write(r/'localization.json',{'transform':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]})
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'folder',return_value=r),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'位置/朝向'):c.navigate('B')
   run.assert_not_called()
 def test_health_failure_cannot_move(self):
  with patch.object(c,'check_session'),patch.object(c,'health',side_effect=RuntimeError('stale')),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'stale'):c.navigate('B')
   run.assert_not_called()
 def test_record_before_finish_is_rejected(self):
  c.save(phase='mapping')
  with patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'结束扫图'):c.record('B')
   run.assert_not_called()
 def test_point_names_are_data_not_shell(self):
  r=self.root/'run';r.mkdir();name='终点; $(example)'
  c.write(r/'accuracy_target.json',{'source_session':'s1','map_id':'m1','pose':[0,0,0]})
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'folder',return_value=r),patch.object(c,'run') as run:
   c.record(name);self.assertEqual(run.call_args.args[0],['bash','MPPI导航.sh','record',name]);self.assertIn(name,c.state()['points'])
 def test_point_action_persists_with_map_and_invalidates_both_previews(self):
  c.save(preview={'name':'B'},route_preview={'success':True},route={'names':['B','B']})
  original=c.state()['points']['B']['pose']
  with patch.object(c,'assert_no_motion'):
   c.point_settings.edit(c,'B','obstacle')
  d=c.state();self.assertEqual(d['points']['B']['pose'],original);self.assertEqual(d['points']['B']['arrival_motion'],{'switch':True,'mode':'obstacle'})
  self.assertIsNone(d['preview']);self.assertIsNone(d['route_preview'])
  book=c.read(c.MPPI/'maps/m1/console_points.json');self.assertEqual(book['points']['B']['arrival_motion'],d['points']['B']['arrival_motion']);self.assertEqual(book['route'],d['route'])
 def test_point_action_cannot_be_edited_during_motion_or_mapping(self):
  with patch.object(c,'assert_no_motion',side_effect=RuntimeError('已有运动')):
   with self.assertRaises(RuntimeError):c.point_settings.edit(c,'B','obstacle')
  c.save(phase='mapping')
  with patch.object(c,'assert_no_motion'):
   with self.assertRaisesRegex(RuntimeError,'结束扫图'):c.point_settings.edit(c,'B','obstacle')
  self.assertNotIn('arrival_motion',c.state()['points']['B'])
 def test_changed_point_action_blocks_single_goal_old_preview(self):
  c.save(preview={'name':'B','at':time.time(),'pose':[0,0,0],'target_fingerprint':c.point_fingerprint(c.state()['points']['B'])})
  d=c.state();d['points']['B']['arrival_motion']={'switch':True,'mode':'obstacle'};c.write(c.STATE,d)
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'current_map_pose',return_value=[0,0,0]),patch.object(c,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'到点参数变化'):c.navigate('B')
   run.assert_not_called()
 def test_recording_same_point_preserves_arrival_parameter(self):
  r=self.root/'run';r.mkdir();c.write(r/'accuracy_target.json',{'name':'B','source_session':'s1','map_id':'m1','pose':[1,0,0]})
  with patch.object(c,'assert_no_motion'):c.point_settings.edit(c,'B','obstacle',True)
  with patch.object(c,'check_session'),patch.object(c,'health'),patch.object(c,'folder',return_value=r),patch.object(c,'run'):
   c.record('B')
  self.assertTrue(c.state()['points']['B']['manual_handoff']);self.assertTrue(c.state()['points']['B']['arrival_motion']['switch']);self.assertEqual(c.state()['points']['B']['pose'],[1,0,0])
 def test_point_settings_updates_matching_selected_goal_file(self):
  r=self.root/'run';r.mkdir();d=c.state();d['points']['B']['name']='B';c.write(c.STATE,d);c.write(r/'accuracy_target.json',d['points']['B'])
  with patch.object(c,'assert_no_motion'),patch.object(c,'folder',return_value=r):c.point_settings.edit(c,'B','obstacle')
  self.assertTrue(c.read(r/'accuracy_target.json')['arrival_motion']['switch'])
 def test_map_click_replacement_preserves_handoff(self):
  with patch.object(c,'assert_no_motion'):c.point_settings.edit(c,'B','obstacle',True)
  p=c.MPPI/'maps/m1/clicked_goal.json';c.write(p,dict(map_id='m1',created=time.time()+1,pose=[2,3,.1]))
  with patch.object(c,'assert_no_motion'),patch.object(c,'view'),patch.object(c.compute_backend,'onboard',return_value=False):c.record_map_point('B')
  self.assertTrue(c.state()['points']['B']['manual_handoff'])
  self.assertTrue(c.state()['points']['B']['arrival_motion']['switch'])
 def test_record_menu_offers_point_action_without_robot_calls(self):
  with patch.object(sys,'argv',['console.py']),patch.object(sys,'stdin',io.StringIO('3\nB\n1\n0\n')),patch.dict(sys.modules,{'console':c}),patch.object(c.select,'select',return_value=([object()],[],[])),patch.object(c,'service_problem',return_value=None),patch.object(c,'record') as record,patch.object(c,'assert_no_motion'),patch.object(c,'run') as run,patch('builtins.print'):
   c.main()
  record.assert_called_once_with('B');run.assert_not_called();self.assertEqual(c.state()['points']['B']['arrival_motion'],{'switch':True,'mode':'obstacle'})

class StartupRegressionTests(unittest.TestCase):
 def test_cold_start_can_finish_after_thirty_seconds(self):
  clock=[0.0]
  def health(selected):
   if clock[0]<45:raise RuntimeError('lifecycle未就绪')
  with patch.object(c,'health',side_effect=health),patch.object(c,'folder',return_value=Path('/unused')),patch.object(c,'read',return_value={'phase':'running'}),patch.object(c.time,'monotonic',side_effect=lambda:clock[0]),patch.object(c.time,'sleep',side_effect=lambda dt:clock.__setitem__(0,clock[0]+dt)):
   c.wait_ready(False)
  self.assertEqual(clock[0],45)
 def test_failed_child_exits_immediately_with_reason(self):
  with patch.object(c,'health',side_effect=RuntimeError('not ready')),patch.object(c,'folder',return_value=Path('/unused')),patch.object(c,'read',return_value={'phase':'stopped','error':'Input adapter exited'}),patch.object(c.time,'sleep') as sleep:
   with self.assertRaisesRegex(RuntimeError,'Input adapter exited'):c.wait_ready(True)
   sleep.assert_not_called()
 def test_missing_status_keys_wait_and_timeout_is_bounded(self):
  clock=[0.0]
  with patch.object(c,'health',side_effect=KeyError('phase')),patch.object(c,'folder',return_value=Path('/unused')),patch.object(c,'read',return_value={}),patch.object(c.time,'monotonic',side_effect=lambda:clock[0]),patch.object(c.time,'sleep',side_effect=lambda dt:clock.__setitem__(0,clock[0]+dt)):
   with self.assertRaisesRegex(RuntimeError,'60秒'):c.wait_ready(False)
  self.assertEqual(clock[0],60)
 def test_start_failure_does_not_leave_initializing_state(self):
  with patch.object(c,'assert_no_motion'),patch.object(c,'archive_state'),patch.object(c,'save') as save,patch.object(c,'_start_mapping_services',side_effect=RuntimeError('activation failed')):
   with self.assertRaisesRegex(RuntimeError,'activation failed'):c.start_mapping()
   self.assertEqual(save.call_args.kwargs['phase'],'start_failed')
 def test_known_launch_blocker_preserves_map_and_never_starts_services(self):
  with patch.object(c,'assert_no_motion'),patch.object(c,'check_startup',side_effect=RuntimeError('传感器被占用')),patch.object(c,'archive_state') as archive,patch.object(c,'save') as save,patch.object(c,'_start_mapping_services') as start:
   with self.assertRaisesRegex(RuntimeError,'占用'):c.start_mapping()
   archive.assert_not_called();save.assert_not_called();start.assert_not_called()
 def test_saved_map_remains_available_after_localization_failure(self):
  saved={'phase':'mapping','map_id':None}
  def fail(d):saved.update(phase='validating_map',map_id='saved-new');raise RuntimeError('localization failed')
  with patch.object(c,'state',side_effect=lambda:saved),patch.object(c,'_finish_mapping',side_effect=fail),patch.object(c,'save',side_effect=lambda **kw:saved.update(kw)):
   with self.assertRaisesRegex(RuntimeError,'localization failed'):c.finish_mapping()
   self.assertEqual(saved['phase'],'recovery_failed');self.assertEqual(saved['map_id'],'saved-new')

if __name__=='__main__':unittest.main()
