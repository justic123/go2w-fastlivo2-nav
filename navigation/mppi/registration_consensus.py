"""Choose a coherent set before choosing its representative, never by fitness alone."""
import itertools
import math
import numpy as np


def select(candidates, *, hint=None):
    required=4 if hint is not None else 3
    if not candidates:raise ValueError('No registration candidates')
    if len({c['seed'] for c in candidates})!=len(candidates):raise ValueError('Duplicate registration seeds')
    eligible=[]
    for c in candidates:
        T=np.asarray(c['transform'],dtype=float)
        valid=(T.shape==(4,4) and np.isfinite(T).all() and np.allclose(T[3],[0,0,0,1]) and
               np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-5) and np.isclose(np.linalg.det(T[:3,:3]),1))
        if not valid:continue
        if not (math.isfinite(c['fitness']) and math.isfinite(c['rmse']) and c['fitness']>.65 and 0<=c['rmse']<.12 and math.acos(float(np.clip(T[2,2],-1,1)))<.25):continue
        if hint is not None:
            delta=np.asarray(hint)[:3,:3].T@T[:3,:3]
            turn=math.acos(float(np.clip((np.trace(delta)-1)/2,-1,1)))
            if np.linalg.norm(T[:3,3]-np.asarray(hint)[:3,3])>=.75 or turn>=.35:continue
        eligible.append(c)

    def distance(a,b):
        A=np.asarray(a['transform']);B=np.asarray(b['transform'])
        return np.linalg.norm(A[:3,3]-B[:3,3])/.15,np.linalg.norm(A[:3,:3]-B[:3,:3])/.1

    groups=[]
    for size in range(1,len(eligible)+1):
        for group in itertools.combinations(eligible,size):
            if all(max(distance(a,b))<1 for a,b in itertools.combinations(group,2)):groups.append(group)
    if not groups:
        best=max(candidates,key=lambda c:(c['fitness'],-c['rmse']))
        return dict(best=best,consensus=0,accepted=False,supporting_seeds=[])
    group=max(groups,key=lambda g:(len(g),float(np.median([c['fitness'] for c in g])),-float(np.median([c['rmse'] for c in g]))))
    # Medoid is an actual validated ICP solution, close to the other supporters.
    best=min(group,key=lambda c:(sum(sum(distance(c,b)) for b in group),-c['fitness'],c['rmse']))
    return dict(best=best,consensus=len(group),accepted=len(group)>=required,
                supporting_seeds=sorted(c['seed'] for c in group))
