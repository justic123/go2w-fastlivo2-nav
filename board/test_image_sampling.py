import unittest
from image_sampling import ImageSampler
class SamplingTests(unittest.TestCase):
    def test_native_5hz_jitter_does_not_drop_a_second_frame(self):
        stamps=[10.,10.207,10.388,10.608,10.80]
        replay=ImageSampler('5hz');native=ImageSampler('5hz',True)
        self.assertEqual([s for s in stamps if replay.accept(s)],[10.,10.207,10.608,10.80])
        self.assertEqual([s for s in stamps if native.accept(s)],stamps)
    def test_offline_10_to_5hz_is_still_sampled(self):
        sampler=ImageSampler('5hz');stamps=[10.+i*.1 for i in range(11)]
        self.assertEqual([s for s in stamps if sampler.accept(s)],stamps[::2])
    def test_passthrough_never_invents_a_missing_frame_or_new_stamp(self):
        for mode in ('5hz','10hz'):
            sampler=ImageSampler(mode,True);stamps=[10.,10.2,10.8]
            self.assertEqual([s for s in stamps if sampler.accept(s)],stamps)
    def test_bad_profile_rejected(self):
        with self.assertRaises(ValueError):ImageSampler('unknown',True)
if __name__=='__main__':unittest.main()
