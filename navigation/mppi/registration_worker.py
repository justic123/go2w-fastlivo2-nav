"""Single-process scan matching; no ROS, TF, files, or motion commands in a job."""
import time
import numpy as np
_target = None


def initialize(path):
    global _target
    import open3d as o3d
    _target = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.load(path)))
    _target.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.3, max_nn=40))


def match(points, transform):
    import open3d as o3d
    started = time.monotonic()
    src = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points)).voxel_down_sample(.1)
    reg = o3d.pipelines.registration
    result = reg.registration_icp(src, _target, .2, transform,
                                  reg.TransformationEstimationPointToPlane(),
                                  reg.ICPConvergenceCriteria(max_iteration=25))
    return dict(candidate=result.transformation, fitness=result.fitness,
                rmse=result.inlier_rmse, points=np.asarray(src.points),
                processing_s=time.monotonic()-started)
