import unittest
from localization_policy import fresh_scan, correction_allowed, ValidationWindow, registration_problem, completed_trial_problem


class LocalizationPolicyTests(unittest.TestCase):
    def test_late_worker_or_stale_inputs_cannot_renew_localization(self):
        self.assertIsNone(completed_trial_problem(.82, True, .05))
        for values in ((2.,True,.05),(-1.,True,.05),(float('nan'),True,.05),
                       (.3,False,.05),(.3,True,1.),(.3,True,-.1)):
            with self.subTest(values=values):self.assertIsNotNone(completed_trial_problem(*values))
        window=ValidationWindow();window.observe(True,10.,0.);window.observe(True,12.,2.)
        # Completion does not extend the lifetime of an observation taken earlier.
        self.assertFalse(window.ready(7.))

    def test_bad_match_immediately_blocks_then_requires_two_new_good_scans(self):
        g=ValidationWindow();g.observe(True,10.,0.);g.observe(True,11.,2.)
        self.assertTrue(g.ready(2.))
        g.observe(False,12.,4.);self.assertFalse(g.ready(4.))
        g.observe(True,13.,6.);g.observe(True,13.,7.)
        self.assertFalse(g.ready(7.))
        g.observe(True,14.,8.);self.assertTrue(g.ready(8.))
        self.assertFalse(g.ready(14.))
        g.observe(True,20.,14.);self.assertFalse(g.ready(14.))
    def test_rejected_registration_is_not_made_acceptable(self):
        self.assertIsNone(registration_problem(.91,.07,.01,.01))
        self.assertIsNotNone(registration_problem(.907,.073,.409,.091))
        for values in [(.5,.07,.01,.01),(.91,.13,.01,.01),(.91,.07,.01,.13),(float('nan'),.07,.01,.01)]:
            self.assertIsNotNone(registration_problem(*values))
    def test_stationary_requires_lateral_stop_and_fresh_pose(self):
        self.assertTrue(correction_allowed(0.,0.,0.,.2,False))
        for values in ((0.,.03,0.,.2,False),(.011,.011,0.,.2,False),
                       (0.,0.,0.,.7,False),(0.,0.,0.,.2,True),
                       (0.,float('nan'),0.,.2,False)):
            self.assertFalse(correction_allowed(*values))

    def test_repeated_or_stale_scans_cannot_revalidate_map(self):
        self.assertTrue(fresh_scan(10.,10.2,.1,9.8))
        for values in ((10.,10.2,.1,10.),(9.9,10.2,.1,10.),
                       (10.,11.,.1,9.8),(10.,10.2,.7,9.8),
                       (11.,10.2,.1,9.8)):
            self.assertFalse(fresh_scan(*values))


if __name__=='__main__':unittest.main()
