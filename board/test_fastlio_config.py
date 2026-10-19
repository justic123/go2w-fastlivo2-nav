import copy,unittest
from fastlio_config import configuration


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.source=dict(extrin_calib=dict(extrinsic_T=[.171,0,.0908],extrinsic_R=[0,-1,0,1,0,0,0,0,1]),
                         preprocess=dict(lidar_type=5,scan_line=16,point_filter_num=4,filter_size_surf=.15,blind=.6),
                         imu=dict(acc_cov=.5,gyr_cov=.01))

    def test_preserves_calibration_and_filters_without_camera_or_clock_guess(self):
        source=copy.deepcopy(self.source);result=configuration(source)
        self.assertEqual(result['mapping']['extrinsic_T'],source['extrin_calib']['extrinsic_T'])
        self.assertEqual(result['mapping']['extrinsic_R'],source['extrin_calib']['extrinsic_R'])
        self.assertFalse(result['mapping']['extrinsic_est_en']);self.assertFalse(result['common']['time_sync_en'])
        self.assertEqual(result['preprocess']['lidar_type'],5);self.assertEqual(result['point_filter_num'],4)
        self.assertEqual(result['filter_size_surf'],.15);self.assertEqual(result['preprocess']['blind'],.6)
        self.assertNotIn('img_topic',result['common']);self.assertFalse(result['pcd_save']['pcd_save_en'])
        self.assertEqual(source,self.source)

    def test_rejects_invalid_or_reflected_extrinsics(self):
        for rotation in [[1]*9,[-1,0,0,0,1,0,0,0,1],[float('nan')]*9]:
            source=copy.deepcopy(self.source);source['extrin_calib']['extrinsic_R']=rotation
            with self.assertRaises(ValueError):configuration(source)

    def test_rejects_other_sensors_and_bad_filters(self):
        for key,value in [('lidar_type',2),('scan_line',32),('point_filter_num',0),('point_filter_num',True),('blind',0)]:
            source=copy.deepcopy(self.source);source['preprocess'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):configuration(source)


if __name__=='__main__':unittest.main()
