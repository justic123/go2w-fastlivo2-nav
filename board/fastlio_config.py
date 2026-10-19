"""Translate the installed XT16/IMU calibration, without changing its frame."""
import math


def configuration(livo):
    extrinsic=livo['extrin_calib'];pre=livo['preprocess'];imu=livo['imu']
    t=extrinsic['extrinsic_T'];r=extrinsic['extrinsic_R']
    if len(t)!=3 or len(r)!=9 or not all(type(v) in (int,float) and math.isfinite(v) for v in t+r):
        raise ValueError('Expected finite LiDAR-to-IMU T[3], R[9]')
    for i in range(3):
        for j in range(3):
            if abs(sum(r[3*k+i]*r[3*k+j] for k in range(3))-(1 if i==j else 0))>1e-5:
                raise ValueError('Extrinsic rotation is not orthonormal')
    determinant=r[0]*(r[4]*r[8]-r[5]*r[7])-r[1]*(r[3]*r[8]-r[5]*r[6])+r[2]*(r[3]*r[7]-r[4]*r[6])
    if determinant<.99999:raise ValueError('Extrinsic reflection is invalid')
    if pre['lidar_type']!=5 or pre['scan_line']!=16:
        raise ValueError('This adapter requires the installed XT16 input')
    count=pre['point_filter_num'];leaf=pre['filter_size_surf'];blind=pre['blind']
    if type(count) is not int or not 1<=count<=32 or not 0<leaf<=1 or not 0<blind<10:
        raise ValueError('Invalid installed filtering parameters')
    return dict(common=dict(lid_topic='/go2w_lio/points',imu_topic='/go2w_lio/imu',
                            time_sync_en=False,time_offset_lidar_to_imu=0.),
                preprocess=dict(lidar_type=5,scan_line=16,timestamp_unit=0,scan_rate=10,blind=blind),
                point_filter_num=count,feature_extract_enable=False,
                filter_size_surf=leaf,filter_size_map=leaf,cube_side_length=600.,max_iteration=5,
                mapping=dict(det_range=95.,fov_degree=360.,acc_cov=imu['acc_cov'],gyr_cov=imu['gyr_cov'],
                             b_acc_cov=imu.get('b_acc_cov',.0001),b_gyr_cov=imu.get('b_gyr_cov',.0001),
                             extrinsic_est_en=False,extrinsic_T=list(t),extrinsic_R=list(r)),
                publish=dict(path_en=True,scan_publish_en=True,dense_publish_en=True,scan_bodyframe_pub_en=False),
                runtime_pos_log_enable=False,pcd_save=dict(pcd_save_en=False,interval=-1))


if __name__=='__main__':
    import argparse,json,yaml
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--from-livo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    # JSON is a YAML subset accepted by rosparam; no timestamp or calibration rounding.
    args.output.write_text(json.dumps(configuration(yaml.safe_load(args.from_livo.read_text())),indent=2)+'\n')
