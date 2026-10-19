import unittest
from action_startup import wait_stationary


class ActionStartup(unittest.TestCase):
    def test_discovery_delay_then_real_stationary_feedback(self):
        now = [0.]
        def pump(): now[0] += .1
        def healthy():
            if now[0] < 5: raise RuntimeError('receipt stale')
        result = wait_stationary(pump, healthy, lambda: now[0] >= 6.5,
                                 lambda: now[0], lambda: None)
        self.assertGreaterEqual(result['wait_s'], 6.5)
        self.assertGreater(result['retries'], 0)

    def test_persistent_stale_never_starts(self):
        now = [0.]
        def pump(): now[0] += .1
        def healthy(): raise RuntimeError('source data stale')
        with self.assertRaisesRegex(RuntimeError, 'source data stale'):
            wait_stationary(pump, healthy, lambda: True, lambda: now[0], lambda: None)
        self.assertLess(now[0], 12.2)

    def test_cancel_does_not_wait_out_timeout(self):
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            wait_stationary(lambda: self.fail('pumped after cancellation'),
                            lambda: None, lambda: True, lambda: 0., lambda: 'cancelled')


if __name__ == '__main__': unittest.main()
