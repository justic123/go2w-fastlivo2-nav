"""Validate a stationary map-frame recording without ROS or robot control."""
import math
import numpy as np
from scipy.spatial.transform import Rotation

class Recorder:
    def __init__(self,map_id,session):
        if not map_id or not session:raise ValueError('未选择有效地图与会话')
        self.map_id=map_id;self.session=session;self.samples=[];self.rotations=[]
    def observe(self,d,l,now):
        for value in (d,l):
            if not value.get('ready') or not 0<=now-value.get('updated',0)<1:raise ValueError('定位或输入过期/时钟异常，未记录')
        if d.get('session')!=self.session or l.get('source_session')!=self.session or l.get('map_id')!=self.map_id:
            raise ValueError('采样期间地图或定位会话变化，未记录')
        for key in ('pose_age_s','cloud_age_s'):
            age=d.get(key)
            if type(age) not in (float,int) or not math.isfinite(age) or not -.05<=age<.6:raise ValueError('传感器时间戳异常，未记录')
        p=d['pose'];stamp=p['stamp'];v=np.asarray(p['pose'],dtype=float);T=np.asarray(l['transform'],dtype=float)
        if not math.isfinite(stamp) or v.shape!=(7,) or not np.isfinite(v).all() or abs(float(v[3:]@v[3:])-1)>.02:
            raise ValueError('位姿数值或四元数无效，未记录')
        if T.shape!=(4,4) or not np.isfinite(T).all() or not np.allclose(T[3],[0,0,0,1]) or not np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-5) or not np.isclose(np.linalg.det(T[:3,:3]),1):
            raise ValueError('地图变换无效，未记录')
        if self.samples and stamp<self.samples[-1][4]:raise ValueError('位姿时间倒退，未记录')
        if self.samples and stamp==self.samples[-1][4]:return
        xyz=T[:3,:3]@v[:3]+T[:3,3];R=T[:3,:3]@Rotation.from_quat(v[3:]).as_matrix()
        self.rotations.append(Rotation.from_matrix(R))
        self.samples.append([*xyz,math.atan2(R[1,0],R[0,0]),stamp])
    def target(self,name,now):
        a=np.asarray(self.samples)
        if len(a)<15 or a[-1,4]-a[0,4]<2.8:raise ValueError('有效采样不足，请保持静止后重试')
        if np.max(np.linalg.norm(a[:,:3]-a[0,:3],axis=1))>.025 or np.max(np.abs(np.angle(np.exp(1j*(a[:,3]-a[0,3])))))>.025:
            raise ValueError('采样期间位置或朝向变化，请停稳后重试')
        if max((self.rotations[0].inv()*rotation).magnitude() for rotation in self.rotations)>.025:
            raise ValueError('采样期间姿态变化，请停稳后重试')
        return dict(name=name,frame='map',map_id=self.map_id,source_session=self.session,
                    pose=[float(np.median(a[:,0])),float(np.median(a[:,1])),float(np.angle(np.mean(np.exp(1j*a[:,3]))))],
                    map_pose=[*np.median(a[:,:3],axis=0).tolist(),*self.rotations[-1].as_quat().tolist()],
                    created=now,samples=len(a),ground_truth=None,source='stationary_fused_pose')
