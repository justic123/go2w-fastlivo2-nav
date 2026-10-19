"""Explicit native backend selection; neither backend can enable motion."""


def plan(config):
    name = config.get('fusion_backend', 'fastlivo2')
    record = config.get('recording_enabled', True)
    if type(record) is not bool:
        raise ValueError('recording_enabled must be boolean')
    common = dict(name=name, recording_enabled=record)
    if name == 'fastlivo2':
        return dict(common, vision=True, parameters=[('livo.yaml', '/go2w_lio'),
                    ('camera.yaml', '/go2w_lio/laserMapping')],
                    binary='ws/devel/lib/fast_livo/fastlivo_mapping',
                    remaps=['/aft_mapped_to_init:=/go2w_lio/odometry',
                            '/cloud_registered:=/go2w_lio/cloud', '/path:=/go2w_lio/path',
                            '/mavros/vision_pose/pose:=/go2w_lio/unused_pose'])
    if name == 'fastlio2':
        return dict(common, vision=False, parameters=[('fastlio.yaml', '/go2w_lio')],
                    binary='ws/devel/lib/fast_lio/fastlio_mapping',
                    remaps=['/Odometry:=/go2w_lio/odometry',
                            '/cloud_registered:=/go2w_lio/cloud', '/path:=/go2w_lio/path'])
    raise ValueError('Unsupported fusion_backend: ' + str(name))
