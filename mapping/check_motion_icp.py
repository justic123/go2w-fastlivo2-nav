"""Independent scan-pair diagnostic; not ground truth or replacement calibration."""
import numpy as np,json,sys
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from pathlib import Path
root=Path(sys.argv[1]);d=np.load(root/'motion_sample.npz');ts=d['times'];imu=d['imu'];rows=[]
for i in range(1,len(ts)):
 prev=d['p'+str(i-1)].astype(float);cur=d['p'+str(i)].astype(float);tree=cKDTree(prev);r=np.eye(3);t=np.zeros(3)
 for k in range(30):
  moved=cur@r.T+t;dist,idx=tree.query(moved);mask=dist<min(.5,max(.08,float(np.quantile(dist,.75))))
  if mask.sum()<100:break
  a=moved[mask];b=prev[idx[mask]];am=a.mean(0);bm=b.mean(0);u,s,v=np.linalg.svd((a-am).T@(b-bm));rr=v.T@u.T
  if np.linalg.det(rr)<0:v[-1]*=-1;rr=v.T@u.T
  tt=bm-rr@am;r=rr@r;t=rr@t+tt
  if np.linalg.norm(tt)<1e-5 and np.linalg.norm(Rotation.from_matrix(rr).as_rotvec())<1e-5:break
 dist,_=tree.query(cur@r.T+t)
 rows.append({'a':float(ts[i-1]),'b':float(ts[i]),'rotvec':Rotation.from_matrix(r).as_rotvec().tolist(),'translation':t.tolist(),'median_error':float(np.median(dist)),'fraction_under_20cm':float((dist<.2).mean())})
(root/'scan_pair_icp.json').write_text(json.dumps(rows,indent=2))
# Approximate scans at midpoint; no motion deskew, so offsets are exploratory.
results=[]
for shift in np.arange(-.2,.201,.01):
 lidar=[];body=[]
 for x in rows:
  if x['fraction_under_20cm']<.7 or not 60<x['a']<75:continue
  a=x['a']+.05+shift;b=x['b']+.05+shift;grid=np.linspace(a,b,50)
  v=np.column_stack([np.interp(grid,imu[:,0],imu[:,j]) for j in [1,2,3]])
  body.append(np.trapz(v,grid,axis=0));lidar.append(x['rotvec'])
 body=np.array(body);lidar=np.array(lidar);rot,rssd=Rotation.align_vectors(body,lidar)
 results.append({'gyro_query_shift_s':round(float(shift),3),'rms_rotvec_error_rad':float(rssd/np.sqrt(len(body))),'fitted_R_IL':rot.as_matrix().tolist(),'pairs':len(body)})
results.sort(key=lambda x:x['rms_rotvec_error_rad']);(root/'scan_imu_alignment_candidates.json').write_text(json.dumps(results,indent=2));print(json.dumps(results[:3],indent=2))
