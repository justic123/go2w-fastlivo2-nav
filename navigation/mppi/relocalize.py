"""Global FPFH candidates followed by ICP. Writes a candidate, never silently activates it."""
import argparse,json,time,numpy as np,open3d as o3d
from pathlib import Path
root=Path('/state');reg=o3d.pipelines.registration
parser=argparse.ArgumentParser();parser.add_argument('--map-id',default='room-20260928');parser.add_argument('--hint',action='store_true');args=parser.parse_args()
if Path(args.map_id).name!=args.map_id or args.map_id in ('.','..'):raise ValueError('Invalid map id')
meta=json.loads((root/'local_scan.json').read_text());inp=json.loads((root/'input.json').read_text())
if meta.get('session')!=inp['session'] or not 0<=time.time()-meta['captured']<30:raise RuntimeError('Capture is stale or belongs to another session')
source=np.load(root/'local_scan.npy');target=np.load(Path('/work/maps')/args.map_id/'points.npy')
def cloud(a,v):
 p=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(a));p=p.voxel_down_sample(v);p.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=v*3,max_nn=40));return p
fine_s=cloud(source,.08);fine_t=cloud(target,.08);hint=None
if args.hint:
 from scipy.spatial.transform import Rotation
 h=json.loads((root/'initial_pose.json').read_text())
 if h['map_id']!=args.map_id or h['source_session']!=inp['session'] or not 0<=time.time()-h['created']<180:raise RuntimeError('Initial pose hint is stale or belongs to another map/session')
 old=np.array(h['odom_pose']);now=np.array(inp['pose']['pose'])
 if np.linalg.norm(old[:3]-now[:3])>.03 or np.linalg.norm((Rotation.from_quat(old[3:]).inv()*Rotation.from_quat(now[3:])).as_rotvec())>.04:raise RuntimeError('Moved since initial pose hint; select again while stationary')
 hint=np.eye(4);hint[:3,:3]=Rotation.from_quat(h['map_pose'][3:]).as_matrix()@Rotation.from_quat(old[3:]).as_matrix().T;hint[:3,3]=np.array(h['map_pose'][:3])-hint[:3,:3]@old[:3]
else:
 s=cloud(source,.25);t=cloud(target,.25);sf=reg.compute_fpfh_feature(s,o3d.geometry.KDTreeSearchParamHybrid(radius=1.25,max_nn=100));tf=reg.compute_fpfh_feature(t,o3d.geometry.KDTreeSearchParamHybrid(radius=1.25,max_nn=100))
results=[]
for seed in range(5 if args.hint else 4):
 if args.hint:
  T=hint.copy();dx,dy,angle=[(0,0,0),(.15,0,.08),(-.15,0,-.08),(0,.15,.08),(0,-.15,-.08)][seed];T[:2,3]+=[dx,dy];T[:3,:3]=Rotation.from_rotvec([0,0,angle]).as_matrix()@T[:3,:3]
  for radius in (.4,.2):
   icp=reg.registration_icp(fine_s,fine_t,radius,T,reg.TransformationEstimationPointToPlane(),reg.ICPConvergenceCriteria(max_iteration=60));T=icp.transformation
 else:
  r=reg.registration_ransac_based_on_feature_matching(s,t,sf,tf,True,.4,reg.TransformationEstimationPointToPoint(False),3,[reg.CorrespondenceCheckerBasedOnEdgeLength(.9),reg.CorrespondenceCheckerBasedOnDistance(.4)],reg.RANSACConvergenceCriteria(150000,.999))
  icp=reg.registration_icp(fine_s,fine_t,.2,r.transformation,reg.TransformationEstimationPointToPlane(),reg.ICPConvergenceCriteria(max_iteration=60));T=icp.transformation
 tilt=np.arccos(np.clip(T[2,2],-1,1))
 d=dict(seed=seed,fitness=icp.fitness,rmse=icp.inlier_rmse,tilt=float(tilt),transform=T.tolist());results.append(d);print(json.dumps(d),flush=True)
results.sort(key=lambda r:(r['tilt']<.25,r['fitness'],-r['rmse']),reverse=True);best=results[0];T=np.array(best['transform']);agree=sum(np.linalg.norm(np.array(r['transform'])[:3,3]-T[:3,3])<.15 and np.linalg.norm(np.array(r['transform'])[:3,:3]-T[:3,:3])<.1 for r in results)
d=dict(map_id=args.map_id,source_session=inp['session'],created=time.time(),source_points=len(source),target_points=len(target),candidates=results,consensus=int(agree),accepted=bool(best['fitness']>.65 and best['rmse']<.12 and best['tilt']<.25 and agree>=3),transform=best['transform'])
if args.hint:
 shift=float(np.linalg.norm(T[:3,3]-hint[:3,3]));turn=float(np.linalg.norm(Rotation.from_matrix(hint[:3,:3].T@T[:3,:3]).as_rotvec()))
 d.update(method='user_hint_multistart_icp',hint_correction_m=shift,hint_correction_rad=turn)
 d['accepted']=bool(d['accepted'] and agree>=4 and shift<.75 and turn<.35)
(root/'registration_candidate.json').write_text(json.dumps(d,indent=2));print('accepted',d['accepted'],'consensus',agree,flush=True)
