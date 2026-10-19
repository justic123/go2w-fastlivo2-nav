"""Exercise web actions against isolated state; never contact ROS or the SDK."""
import copy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import action
from motion_modes import point_fingerprint

class PointActions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'demo').mkdir()
        self.data={'phase':'navigation','map_id':'map1','session':'s1','points':{},'preview':{'old':True},'route_preview':{'old':True}}
        def save(**kw):self.data.update(copy.deepcopy(kw))
        def write(path,data):
            if path==self.root/'state.json':self.data=copy.deepcopy(data)
        self.patches=[patch.object(action,'ROOT',self.root),patch.object(action.c,'STATE',self.root/'state.json'),patch.object(action.c,'state',lambda:copy.deepcopy(self.data)),patch.object(action.c,'assert_no_motion'),patch.object(action.c,'save',save),patch.object(action.c,'write',write)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def add(self,**kw):
        action.run(dict(action='map-point',map_id='map1',name='A',pose=[1,2,.3],arrival_motion='keep',**kw))
    def test_anchor_requires_map_stationary_and_placement_confirmation(self):
        with patch.object(action.localization_anchors,'restore') as restore:
            base=dict(action='anchor-use',map_id='map1',name='A',anchor_version='v')
            for extra in ({},{'stationary':True},{'stationary':True,'confirm_placement':True,'map_id':'other'}):
                with self.assertRaises(ValueError):action.run(dict(base,**extra))
            restore.assert_not_called()
            action.run(dict(base,stationary=True,confirm_placement=True))
            restore.assert_called_once_with(action.c,'A','v')
    def test_anchor_capture_and_delete_are_not_navigation_actions(self):
        with patch.object(action.localization_anchors,'capture') as capture:
            action.run(dict(action='anchor-save',map_id='map1',name='A',stationary=True))
            capture.assert_called_once_with(action.c,'A')
        with patch.object(action.localization_anchors,'remove') as remove:
            with self.assertRaises(ValueError):action.run(dict(action='anchor-delete',map_id='map1',name='A',anchor_version='v'))
            remove.assert_not_called()
            action.run(dict(action='anchor-delete',map_id='map1',name='A',anchor_version='v',confirm_delete=True))
            remove.assert_called_once_with(action.c,'A','v')
    def test_delete_requires_confirmation_before_store(self):
        with patch.object(action.map_store,'delete') as delete:
            with self.assertRaisesRegex(ValueError,'确认'):action.run(dict(action='delete-map',name='map1'))
            delete.assert_not_called()
    def test_delete_and_restore_route_to_store(self):
        with patch.object(action.map_store,'delete') as delete:
            action.run(dict(action='delete-map',name='map1',confirm_delete=True,map_version='v1'))
            delete.assert_called_once_with(action.c,'map1','v1')
        with patch.object(action.map_store,'restore') as restore:
            action.run(dict(action='restore-map',trash_id='t1'))
            restore.assert_called_once_with(action.c,'t1')
    def test_new_point_invalidates_previews(self):
        self.add();self.assertEqual(self.data['selected'],'A');self.assertIsNone(self.data['preview']);self.assertIsNone(self.data['route_preview'])
    def test_handoff_saved_and_bad_type_rejected_before_write(self):
        self.add(manual_handoff=True);self.assertTrue(self.data['points']['A']['manual_handoff'])
        with self.assertRaises(ValueError):action.run(dict(action='map-point',map_id='map1',name='B',pose=[1,2,0],manual_handoff='true'))
        self.assertNotIn('B',self.data['points'])
    def test_duplicate_cannot_silently_replace(self):
        self.add();before=copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError,'同名'):self.add()
        self.assertEqual(self.data,before)
    def test_confirmed_replace_and_stale_confirmation(self):
        self.add();fp=point_fingerprint(self.data['points']['A']);self.add(replace_fingerprint=fp)
        self.data['points']['A']['pose'][0]=5
        with self.assertRaisesRegex(ValueError,'同名'):self.add(replace_fingerprint=fp)
        self.assertEqual(self.data['points']['A']['pose'][0],5)
    def test_wrong_map_rejected(self):
        with self.assertRaisesRegex(ValueError,'地图已变化'):action.run(dict(action='map-point',map_id='other',name='A',pose=[1,2,0]))
        self.assertFalse(self.data['points'])
    def test_invalid_mode_no_point_written(self):
        with self.assertRaises(ValueError):action.run(dict(action='map-point',map_id='map1',name='A',pose=[1,2,0],arrival_motion='bad'))
        self.assertFalse(self.data['points'])
    def test_clear_route_persists_and_invalidates_preview(self):
        self.data['route']={'names':['A','B']}
        action.run(dict(action='route-set',map_id='map1',names=[]))
        self.assertEqual(self.data['route']['names'],[]);self.assertIsNone(self.data['route_preview'])
    def test_single_leg_route_keeps_old_route(self):
        self.data['route']={'names':['A','B']}
        with self.assertRaises(ValueError):action.run(dict(action='route-set',map_id='map1',names=['A']))
        self.assertEqual(self.data['route']['names'],['A','B'])
if __name__=='__main__':unittest.main()
