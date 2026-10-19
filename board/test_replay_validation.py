import unittest
from replay_validation import failures


class ReplayValidationTests(unittest.TestCase):
    def events(self):
        return [e for i in range(100) for e in
                [dict(kind='odom',data=dict(stamp=100+i*.1,pose=[0.,0.,0.,0.,0.,0.,1.])),
                 dict(kind='lag',data=dict(seconds=.1))]]

    def test_complete_fresh_output_passes(self):
        self.assertEqual(failures(self.events(),10),[])

    def test_missing_lag_and_invalid_observer_fail(self):
        self.assertTrue(failures([e for e in self.events() if e['kind']=='odom'],10))
        self.assertTrue(failures(self.events()+[dict(kind='invalid',data={})],10))

    def test_delayed_nonfinite_or_stopped_output_fails(self):
        for value in (.601,-.01,float('nan')):
            e=self.events();e[-1]['data']['seconds']=value
            self.assertTrue(failures(e,10))
        e=self.events();e[-2]['data']['stamp']+=1
        self.assertTrue(failures(e,10))
        e=self.events();e[-2]['data']['pose'][0]=float('nan')
        self.assertTrue(failures(e,10))
