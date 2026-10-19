"""Reconnect only the passive subscriber, never the fusion service."""
def reconnect_needed(session, subscribed_session, retry_age, exited, fusion_ready, frame_age):
    return session != subscribed_session or (retry_age > 8 and (exited or (fusion_ready and frame_age > 6)))
