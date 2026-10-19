"""Small map pose conversion without starting a BLAS thread pool in the control UI."""
import math

def map_pose(v,T):
    if len(v)!=7 or len(T)!=4 or any(len(row)!=4 for row in T):raise ValueError('位姿或地图变换维度无效')
    if not all(math.isfinite(x) for x in list(v)+[x for row in T for x in row]):raise ValueError('位姿或地图变换数值无效')
    x,y,z,w=v[3:];norm=x*x+y*y+z*z+w*w
    if abs(norm-1)>.02:raise RuntimeError('姿态四元数无效')
    xyz=[sum(T[i][j]*v[j] for j in range(3))+T[i][3] for i in range(3)]
    f=[1-2*(y*y+z*z)/norm,2*(x*y+w*z)/norm,2*(x*z-w*y)/norm]
    forward=[sum(T[i][j]*f[j] for j in range(3)) for i in range(3)]
    return [xyz[0],xyz[1],math.atan2(forward[1],forward[0])]
