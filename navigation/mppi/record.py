"""Record a stationary measured target in the selected saved-map frame."""
import json,time,math,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
root=Path('/state');samples=[];last=None
for _ in range(35):
 d=json.loads((root/'input.json').read_text());l=json.loads((root/'localization.json').read_text())
 if not d['ready'] or not l['ready'] or max(time.time()-d['updated'],time.time()-l['updated'])>1:raise SystemExit('Localization/input not fresh')
 p=d['pose'];stamp=p['stamp']
 if stamp!=last:
  v=p['pose'];T=np.array(l['transform']);xyz=T[:3,:3]@v[:3]+T[:3,3];R=T[:3,:3]@Rotation.from_quat(v[3:]).as_matrix();yaw=math.atan2(R[1,0],R[0,0]);samples.append([*xyz,yaw,stamp]);last=stamp
 time.sleep(.1)
a=np.array(samples)
if len(a)<15 or np.max(np.linalg.norm(a[:,:3]-a[0,:3],axis=1))>.025 or np.max(np.abs(np.angle(np.exp(1j*(a[:,3]-a[0,3])))))>.025:raise SystemExit('Not stationary; target not recorded')
target=dict(name=sys.argv[1] if len(sys.argv)>1 else '精度返回点',frame='map',map_id=l['map_id'],source_session=l['source_session'],pose=[float(np.median(a[:,0])),float(np.median(a[:,1])),float(np.angle(np.mean(np.exp(1j*a[:,3]))))],created=time.time(),samples=len(a),ground_truth='user marked position and heading; errors unmeasured')
(root/'accuracy_target.json').write_text(json.dumps(target,ensure_ascii=False,indent=2));print(json.dumps(target,ensure_ascii=False))
