import importlib.util,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('console',Path(__file__).with_name('console.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class FlowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.patch=patch.multiple(c,ROOT=self.root,MPPI=self.root/'navigation/mppi',STATE=self.root/'demo/state.json');self.patch.start()
  c.write(c.STATE,dict(phase='navigation',session='s1',map_id='m1',points={'B':dict(source_session='s1',map_id='m1',pose=[0,0,0])}))
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
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
if __name__=='__main__':unittest.main()
