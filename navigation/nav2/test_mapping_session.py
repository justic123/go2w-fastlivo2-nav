import json,tempfile,unittest
from pathlib import Path
from mapping_session import current_mapping_run
class SessionTests(unittest.TestCase):
 def test_desktop_restart_invalidates_places_without_capture_restart(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'continuous_capture.json').write_text(json.dumps(dict(run='capture-A')))
   self.assertEqual(current_mapping_run(p),'capture-A')
   (p/'compute_location.json').write_text(json.dumps(dict(mode='desktop')))
   (p/'desktop_navigation.json').write_text(json.dumps(dict(session='desktop-A')))
   self.assertEqual(current_mapping_run(p),'desktop-A')
   (p/'desktop_navigation.json').write_text(json.dumps(dict(session='desktop-B')))
   self.assertNotEqual(current_mapping_run(p),'desktop-A')
 def test_missing_desktop_binding_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'compute_location.json').write_text(json.dumps(dict(mode='desktop')))
   with self.assertRaises(FileNotFoundError):current_mapping_run(p)
