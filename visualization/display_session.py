"""Keep display accumulation across transport reconnects, never across map sessions."""
class DisplaySession:
    def __init__(self):
        self.identity = None
        self.frame = None

    def observe(self, metadata, connection):
        # Legacy senders have no session identity: conservatively retain old reset
        # behavior rather than merge unrelated coordinate systems after a restart.
        session = metadata.get('session_id')
        identity = ('session', session) if isinstance(session, str) and session else ('legacy', connection)
        reason = None
        if identity != self.identity:
            reason = 'initial_session' if self.identity is None else ('legacy_reconnect' if identity[0] == 'legacy' else 'new_session')
            self.identity = identity
            self.frame = None
        if metadata.get('kind') in ('cloud', 'odom'):
            frame = metadata.get('frame') or 'camera_init'
            if self.frame is not None and frame != self.frame:
                reason = 'frame_changed'
            self.frame = frame
        return reason
