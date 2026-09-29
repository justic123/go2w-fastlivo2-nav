"""Global FPFH candidates followed by ICP. Writes a candidate, never silently activates it."""
import json,time,numpy as np,open3d as o3d
from pathlib import Path
root=Path('/state');reg=o3d.pipelines.registration
source=np.load(root/'local_scan.npy');target=np.load('/work/maps/room-20260928/points.npy')
def cloud(a,v):
 p=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(a));p=p.voxel_down_sample(v);p.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=v*3,max_nn=40));return p
s=cloud(source,.25);t=cloud(target,.25);sf=reg.compute_fpfh_feature(s,o3d.geometry.KDTreeSearchParamHybrid(radius=1.25,max_nn=100));tf=reg.compute_fpfh_feature(t,o3d.geometry.KDTreeSearchParamHybrid(radius=1.25,max_nn=100));fine_s=cloud(source,.08);fine_t=cloud(target,.08)
results=[]
for seed in range(4):
 r=reg.registration_ransac_based_on_feature_matching(s,t,sf,tf,True,.4,reg.TransformationEstimationPointToPoint(False),3,[reg.CorrespondenceCheckerBasedOnEdgeLength(.9),reg.CorrespondenceCheckerBasedOnDistance(.4)],reg.RANSACConvergenceCriteria(150000,.999))
 icp=reg.registration_icp(fine_s,fine_t,.2,r.transformation,reg.TransformationEstimationPointToPlane(),reg.ICPConvergenceCriteria(max_iteration=60))
 T=icp.transformation;tilt=np.arccos(np.clip(T[2,2],-1,1))
 d=dict(seed=seed,fitness=icp.fitness,rmse=icp.inlier_rmse,tilt=float(tilt),transform=T.tolist());results.append(d);print(json.dumps(d),flush=True)
results.sort(key=lambda r:(r['tilt']<.25,r['fitness'],-r['rmse']),reverse=True);best=results[0];T=np.array(best['transform']);agree=sum(np.linalg.norm(np.array(r['transform'])[:3,3]-T[:3,3])<.15 and np.linalg.norm(np.array(r['transform'])[:3,:3]-T[:3,:3])<.1 for r in results)
d=dict(map_id='room-20260928',source_session=json.loads((root/'input.json').read_text())['session'],created=time.time(),source_points=len(source),target_points=len(target),candidates=results,consensus=int(agree),accepted=bool(best['fitness']>.65 and best['rmse']<.12 and best['tilt']<.25 and agree>=3),transform=best['transform'])
(root/'registration_candidate.json').write_text(json.dumps(d,indent=2));print('accepted',d['accepted'],'consensus',agree,flush=True)
