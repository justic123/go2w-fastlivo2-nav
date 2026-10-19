import copy,json,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parent))
import localization_anchors as a

class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.mppi=self.root/'mppi';self.map=self.mppi/'maps'/'m';self.map.mkdir(parents=True)
        for n in ('map.yaml','map.pgm','points.npy'):(self.map/n).write_text(n)
        self.run=self.root/'run';self.run.mkdir()
        self.data=dict(phase='navigation',map_id='m',session='s',points={'A':dict(map_id='m',frame='map',source_session='s')},selected='A',route={'names':['A','B']},preview={'valid':True})
        self.c=SimpleNamespace(MPPI=self.mppi,read=lambda p:json.loads(p.read_text()),write=lambda p,v:p.write_text(json.dumps(v)),state=lambda:copy.deepcopy(self.data),assert_no_motion=Mock(),check_session=Mock(),health=Mock(),folder=lambda:self.run,run=Mock(side_effect=self.capture_output),prepare_assisted_inputs=Mock(),desk=lambda:dict(run='new'),validate_registration=Mock(),activate_registration=Mock(),save=lambda **kw:self.data.update(kw))
    def tearDown(self):self.tmp.cleanup()
    def capture_output(self,*args):
        self.c.write(self.run/'localization_anchor_capture.json',dict(map_id='m',frame='map',source_session='s',pose=[1,2,.2],map_pose=[1,2,.4,0,0,0,1],created=time.time(),source='stationary_fused_pose',samples=18))
    def save_anchor(self):
        a.capture(self.c,'大厅');return a.entries(self.c,'m')['大厅']
    def test_capture_preserves_goal_and_route_and_uses_separate_output(self):
        before=copy.deepcopy(self.data);(self.run/'accuracy_target.json').write_text('original')
        t=self.save_anchor();self.assertEqual(self.data,before);self.assertEqual((self.run/'accuracy_target.json').read_text(),'original');self.assertEqual(t['map_pose'][2],.4)
        self.assertIn('--anchor',self.c.run.call_args.args[0][-3]);self.assertEqual(a.entries(self.c,'m')['大厅']['version'],t['version'])
    def test_no_capture_without_localization_or_while_mapping(self):
        for phase in ('recovery_failed','mapping','recovering'):
            self.data['phase']=phase
            with self.assertRaises(ValueError):self.save_anchor()
        self.c.run.assert_not_called()
    def test_duplicates_cannot_overwrite(self):
        t=self.save_anchor()
        with self.assertRaisesRegex(ValueError,'同名'):self.save_anchor()
        self.assertEqual(a.entries(self.c,'m')['大厅'],t)
    def test_invalid_capture_rejected(self):
        for changes in (dict(source_session='wrong'),dict(map_id='other'),dict(created=0),dict(map_pose=[0]*7),dict(samples=2)):
            def invalid(*args):
                self.capture_output();p=self.run/'localization_anchor_capture.json';t=self.c.read(p);t.update(changes);self.c.write(p,t)
            self.c.run.side_effect=invalid
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.save_anchor()
            self.assertEqual(a.entries(self.c,'m'),{})
    def test_wrong_version_or_modified_geometry_never_restarts(self):
        t=self.save_anchor()
        with self.assertRaises(ValueError):a.restore(self.c,'大厅','wrong')
        (self.map/'map.pgm').write_text('changed')
        with self.assertRaisesRegex(ValueError,'地图内容'):a.restore(self.c,'大厅',t['version'])
        self.c.prepare_assisted_inputs.assert_not_called()
    def prepare_recovery(self):
        t=self.save_anchor();self.data['phase']='recovery_failed';self.c.write(self.run/'input.json',dict(session='new',pose=dict(pose=[0,0,0,0,0,0,1])))
        def candidate(*args):self.c.write(self.run/'registration_candidate.json',dict(map_id='m',source_session='new',accepted=True))
        self.c.run.side_effect=candidate
        return t
    def test_recovery_uses_full_pose_and_validates_before_activation(self):
        t=self.prepare_recovery();a.restore(self.c,'大厅',t['version'])
        hint=self.c.read(self.run/'initial_pose.json');self.assertEqual(hint['map_pose'],t['map_pose']);self.assertEqual(hint['source_session'],'new')
        self.c.validate_registration.assert_called_once();self.c.activate_registration.assert_called_once()
        commands=[x.args[0] for x in self.c.run.call_args_list];self.assertTrue(all('Move' not in str(cmd) for cmd in commands))
    def test_failed_matching_does_not_activate_or_change_targets(self):
        t=self.prepare_recovery();before=copy.deepcopy(self.data);self.c.validate_registration.side_effect=ValueError('匹配未通过')
        with self.assertRaisesRegex(ValueError,'匹配'):a.restore(self.c,'大厅',t['version'])
        self.c.activate_registration.assert_not_called();self.assertEqual(self.data['points'],before['points']);self.assertEqual(self.data['route'],before['route']);self.assertIsNone(self.data['preview']);self.assertIsNone(self.data['route_preview'])
    def test_remove_requires_version_and_keeps_map(self):
        t=self.save_anchor()
        with self.assertRaises(ValueError):a.remove(self.c,'大厅','old')
        a.remove(self.c,'大厅',t['version']);self.assertEqual(a.entries(self.c,'m'),{});self.assertTrue((self.map/'points.npy').exists())
    def test_cannot_use_another_maps_anchor_file(self):
        self.save_anchor();p=self.map/a.FILE;t=self.c.read(p);t['map_id']='another';self.c.write(p,t)
        with self.assertRaises(ValueError):a.entries(self.c,'m')

if __name__=='__main__':unittest.main()
