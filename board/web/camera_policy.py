"""Reconnect only the passive subscriber, never the fusion service."""
def enabled(deployment):
    return deployment.get('fusion_backend', 'fastlivo2') == 'fastlivo2'


def status(deployment, camera, session):
    if not enabled(deployment):
        return dict(enabled=False, updated=0, phase='disabled', session=session,
                    reason='FAST-LIO2 使用雷达与IMU，相机已关闭')
    return dict(camera, enabled=True)


def reconnect_needed(session, subscribed_session, retry_age, exited, fusion_ready, frame_age):
    return session != subscribed_session or (retry_age > 8 and (exited or (fusion_ready and frame_age > 6)))
