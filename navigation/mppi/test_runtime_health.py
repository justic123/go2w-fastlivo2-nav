import unittest
from runtime_health import RuntimeHealth


class RecoveryTests(unittest.TestCase):
    def test_immediate_pause_and_stable_recovery(self):
        g=RuntimeHealth()
        self.assertEqual(g.observe(0,None),('running',None))
        self.assertEqual(g.observe(1,'pose invalid'),('degraded','pose invalid'))
        self.assertEqual(g.observe(2,None)[0],'degraded')
        self.assertEqual(g.observe(2.5,'pose invalid')[0],'degraded')
        self.assertEqual(g.observe(3,None)[0],'degraded')
        self.assertEqual(g.observe(4,None),('running',None))

    def test_persistent_failure_never_becomes_ready(self):
        g=RuntimeHealth()
        for now in range(100):
            self.assertEqual(g.observe(now,'cloud stale')[0],'degraded')


if __name__=='__main__':unittest.main()
