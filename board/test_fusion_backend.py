import unittest
from fusion_backend import plan
from runtime_profile import settings


class BackendTests(unittest.TestCase):
    def test_existing_install_defaults_to_livo_and_recording(self):
        p=plan({})
        self.assertTrue(p['vision']);self.assertTrue(p['recording_enabled'])
        self.assertIn(('camera.yaml','/go2w_lio/laserMapping'),p['parameters'])
        self.assertEqual(p['binary'],'ws/devel/lib/fast_livo/fastlivo_mapping')

    def test_lio_has_no_camera_dependency_and_retains_topics(self):
        cfg=dict(fusion_backend='fastlio2',image_hz=0,recording_enabled=False)
        p=plan(cfg);s=settings(cfg)
        self.assertFalse(p['vision']);self.assertFalse(p['recording_enabled'])
        self.assertEqual(p['parameters'],[('fastlio.yaml','/go2w_lio')])
        self.assertEqual(p['binary'],'ws/devel/lib/fast_lio/fastlio_mapping')
        self.assertIn('/Odometry:=/go2w_lio/odometry',p['remaps'])
        self.assertEqual(s['image_hz'],0);self.assertIsNone(s['decoder_mode'])
        self.assertEqual(s['env']['OMP_THREAD_LIMIT'],'4')

    def test_unknown_backends_and_mistyped_recording_are_errors(self):
        for cfg in [dict(fusion_backend='lio'),dict(fusion_backend=None),dict(recording_enabled='false')]:
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):plan(cfg)

    def test_livo_keeps_camera_validation(self):
        with self.assertRaises(ValueError):settings(dict(image_hz=0))
        self.assertEqual(settings(dict(image_hz=5))['image_hz'],5)


if __name__=='__main__':unittest.main()
