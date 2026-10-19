import tempfile
import unittest
from pathlib import Path

from action_diagnostics import checkpoint, failure_details, abort_reason


class ActionDiagnostics(unittest.TestCase):
    def test_only_current_action_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'bt_navigator.log'
            p.write_text('[ERROR] old failure\n')
            before = checkpoint(folder)
            with p.open('a') as f:
                f.write('[WARN] Behavior Tree tick rate exceeded\n')
                f.write('[WARN] Timed out while waiting for action server to acknowledge goal request for compute_path_to_pose\n')
                f.write('[ERROR] Goal failed\n')
            details = failure_details(folder, before)
            self.assertEqual(len(details), 2)
            self.assertNotIn('old failure', str(details))
            self.assertIn('服务确认超时', abort_reason(6, details))

    def test_missing_logs_do_not_hide_action_status(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(failure_details(folder, {}), [])
            self.assertIn('status 6', abort_reason(6, []))


if __name__ == '__main__':
    unittest.main()
