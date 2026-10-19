import unittest
from runtime_profile import settings


class RuntimeProfileTests(unittest.TestCase):
    def test_missing_frequency_defaults_to_current_five_hz_profile(self):
        self.assertEqual(settings({})['decoder_mode'], '5hz')

    def test_camera_decoder_and_native_profile_agree(self):
        for hz in (5, 10):
            result = settings(dict(image_hz=hz, omp_threads=4))
            self.assertEqual(result['image_hz'], hz)
            self.assertEqual(result['decoder_mode'], f'{hz}hz')
            self.assertEqual(result['env']['GO2W_IMAGE_PROFILE'], f'{hz}hz')
            self.assertEqual(result['env']['OMP_NUM_THREADS'], '4')
            self.assertEqual(result['env']['OMP_THREAD_LIMIT'], '4')

    def test_unknown_profile_is_rejected(self):
        for config in (dict(image_hz=8), dict(image_hz=True), dict(omp_threads=8), dict(omp_threads='4')):
            with self.assertRaises(ValueError):
                settings(config)


if __name__ == '__main__':
    unittest.main()
