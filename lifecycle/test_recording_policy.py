import unittest
from recording_policy import AuxiliaryRecording, GIB


class RecordingPolicyTests(unittest.TestCase):
    def test_low_space_start_keeps_reserve(self):
        policy = AuxiliaryRecording(5.5 * GIB)
        self.assertEqual(policy.state['phase'], 'disabled')
        policy.tick(5.5 * GIB, 0, False, self.fail)
        with self.assertRaisesRegex(RuntimeError, 'Disk reserve reached'):
            policy.tick(4.9 * GIB, 1, False, self.fail)

    def test_crossing_soft_limit_interrupts_once_and_closes(self):
        policy = AuxiliaryRecording(8 * GIB)
        signals = []
        for now in range(10):
            policy.tick(5.9 * GIB, now, True, lambda: signals.append('SIGINT'))
        self.assertEqual(signals, ['SIGINT'])
        policy.tick(5.8 * GIB, 10, False, self.fail)
        self.assertEqual(policy.state['phase'], 'closed')
        policy.tick(8 * GIB, 11, False, self.fail)
        self.assertEqual(policy.state['phase'], 'closed')

    def test_recorder_exit_does_not_stop_sensors(self):
        policy = AuxiliaryRecording(8 * GIB)
        policy.tick(8 * GIB, 0, False, self.fail)
        self.assertEqual(policy.state['phase'], 'exited')

    def test_stuck_recorder_stops_pipeline_without_forced_kill(self):
        policy = AuxiliaryRecording(8 * GIB)
        policy.tick(5.9 * GIB, 0, True, lambda: None)
        with self.assertRaisesRegex(RuntimeError, 'did not seal'):
            policy.tick(5.8 * GIB, 16, True, self.fail)

    def test_fast_disk_exhaustion_keeps_hard_stop(self):
        policy = AuxiliaryRecording(8 * GIB)
        signals = []
        with self.assertRaisesRegex(RuntimeError, 'Disk reserve reached'):
            policy.tick(4.9 * GIB, 0, True, lambda: signals.append('SIGINT'))
        self.assertEqual(signals, ['SIGINT'])


if __name__ == '__main__':
    unittest.main()
