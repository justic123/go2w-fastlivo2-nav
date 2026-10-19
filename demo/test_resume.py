import copy,json,time,unittest,hashlib
from unittest.mock import patch
from test_mission import RouteTests
import mission
from route_model import route_spec

class ResumeTests(unittest.TestCase):
 def setUp(self):
  self.fixture=RouteTests();self.fixture.setUp();f=self.fixture
  self.c=f.c;self.d=f.d;self.run=f.run;self.fp=route_spec(self.d)['fingerprint']
  self.progress=dict(phase='stopped',mission_id='mission1',fingerprint=self.fp,map_id='m',source_session='s',names=['A','B'],completed=1,index=1,results=[dict(name='A')],updated=time.time())
  self.write_progress();self.motion=f.c.run.side_effect
 def tearDown(self):self.fixture.tearDown()
 def write_progress(self):(self.run/'route_progress.json').write_text(json.dumps(self.progress))
 def plan(self,*_):
  req=json.loads((self.run/'route_request.json').read_text())
  (self.run/'route_preview.json').write_text(json.dumps(dict(success=True,fingerprint=req['fingerprint'],source_session='s',created=time.time(),start=[0,0,0],segments=[dict(name=t['name'],length_m=1,timeout_s=90) for t in req['targets']])))
 def preview(self):
  self.c.run.side_effect=self.plan;mission.preview(self.c,resume=True)
 def execute(self):
  self.c.run.side_effect=self.motion
  with patch.object(mission.time,'sleep'),patch.object(mission.time,'monotonic',side_effect=self.fixture.clock):mission.execute(self.c,resume=True)
 def test_continue_only_remaining_point(self):
  self.preview();self.assertEqual([t['name'] for t in json.loads((self.run/'route_request.json').read_text())['targets']],['B'])
  self.execute();self.assertEqual(self.fixture.chosen,['B']);p=json.loads((self.run/'route_progress.json').read_text());self.assertEqual(p['completed'],2);self.assertEqual(p['phase'],'completed');self.assertEqual([r['name'] for r in p['results']],['A','B'])
 def test_full_preview_is_not_resume_preview(self):
  with self.assertRaisesRegex(RuntimeError,'剩余路线'):self.execute()
  self.assertEqual(self.fixture.chosen,[])
 def test_reject_target_edit_and_other_session(self):
  self.d['points']['B']['pose'][0]=4
  self.assertFalse(mission.resume_status(self.c)['available'])
  self.d['points']['B']['pose'][0]=2;self.d['session']='other'
  self.assertFalse(mission.resume_status(self.c)['available'])
 def test_reject_route_reorder(self):
  self.d['route']['names']=['B','A'];self.assertFalse(mission.resume_status(self.c)['available'])
 def test_reject_expired_preview(self):
  self.preview();self.d['route_resume_preview']['created']-=61
  with self.assertRaisesRegex(RuntimeError,'预演'):self.execute()
  self.assertFalse(self.fixture.chosen)
 def test_reject_move_after_preview(self):
  self.preview();self.c.current_map_pose.return_value=[1,0,0]
  with self.assertRaisesRegex(RuntimeError,'已移动'):self.execute()
 def test_progress_change_invalidates_preview(self):
  self.preview();self.progress['updated']+=1;self.write_progress()
  with self.assertRaisesRegex(RuntimeError,'预演'):self.execute()
 def test_bad_token_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'进度已变化'):mission.preview(self.c,resume=True,expected_token='old')
 def test_all_completed_and_handoff_not_resumable(self):
  for phase in ('completed','awaiting_manual','navigating'):
   self.progress['phase']=phase;self.write_progress();self.assertFalse(mission.resume_status(self.c)['available'])
 def test_bad_completed_prefix_not_skipped(self):
  self.progress['results']=[dict(name='B')];self.write_progress();self.assertFalse(mission.resume_status(self.c)['available'])
 def test_legacy_requires_unchanged_original_snapshot(self):
  self.progress.pop('fingerprint');self.progress.pop('mission_id');self.write_progress()
  self.assertFalse(mission.resume_status(self.c)['available'])
  req=route_spec(self.d);req['source_session']='s';(self.run/'route_request.json').write_text(json.dumps(req));self.progress['updated']=time.time()+.001;self.write_progress()
  self.assertTrue(mission.resume_status(self.c)['available']);self.preview();self.execute();self.assertEqual(self.fixture.chosen,['B'])
 def test_newer_preview_cannot_certify_legacy(self):
  self.progress.pop('fingerprint');self.progress['updated']=time.time()-30;self.write_progress()
  req=route_spec(self.d);req['source_session']='s';(self.run/'route_request.json').write_text(json.dumps(req))
  self.assertFalse(mission.resume_status(self.c)['available'])
 def test_repeated_name_uses_index_not_name(self):
  self.d['route']['names']=['A','B','A'];self.progress.update(names=['A','B','A'],fingerprint=route_spec(self.d)['fingerprint'],completed=2,results=[dict(name='A'),dict(name='B')]);self.write_progress()
  self.preview();self.execute();self.assertEqual(self.fixture.chosen,['A']);self.assertEqual(json.loads((self.run/'route_progress.json').read_text())['completed'],3)
 def test_failed_resume_retains_completed_count(self):
  self.preview()
  def fail(*_):raise RuntimeError('data stale')
  self.motion=fail
  with self.assertRaisesRegex(RuntimeError,'data stale'):self.execute()
  p=json.loads((self.run/'route_progress.json').read_text());self.assertEqual(p['completed'],1);self.assertEqual(p['phase'],'stopped')
 def test_resume_does_not_send_anything_when_unhealthy(self):
  self.preview();self.c.health.side_effect=RuntimeError('unhealthy')
  with self.assertRaisesRegex(RuntimeError,'unhealthy'):self.execute()
  self.assertFalse(self.fixture.chosen)
if __name__=='__main__':unittest.main()
