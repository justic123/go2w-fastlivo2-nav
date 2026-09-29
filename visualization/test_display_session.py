import unittest
from display_session import DisplaySession
class SessionTests(unittest.TestCase):
 def test_reconnect_preserves_session(self):
  s=DisplaySession();m=dict(session_id='A',kind='cloud',frame='camera_init')
  self.assertEqual(s.observe(m,1),'initial_session');self.assertIsNone(s.observe(m,2));self.assertIsNone(s.observe(m,3))
 def test_new_map_resets_even_on_same_socket(self):
  s=DisplaySession();s.observe(dict(session_id='A',kind='odom',frame='camera_init'),1)
  self.assertEqual(s.observe(dict(session_id='B',kind='camera'),1),'new_session')
 def test_legacy_does_not_merge_unidentified_maps(self):
  s=DisplaySession();m=dict(kind='cloud',frame='camera_init');s.observe(m,1)
  self.assertIsNone(s.observe(m,1));self.assertEqual(s.observe(m,2),'legacy_reconnect')
 def test_optical_image_frame_does_not_reset_map(self):
  s=DisplaySession();s.observe(dict(session_id='A',kind='cloud',frame='camera_init'),1)
  self.assertIsNone(s.observe(dict(session_id='A',kind='image',frame='camera'),1))
  self.assertEqual(s.observe(dict(session_id='A',kind='cloud',frame='different_map'),1),'frame_changed')
if __name__=='__main__':unittest.main()
