"""Optional board recording in desktop mode; retain the 5 GiB hard reserve."""
GIB = 1024**3


class AuxiliaryRecording:
    def __init__(self, free_bytes):
        self.state = dict(
            phase='running' if free_bytes >= 7 * GIB else 'disabled',
            reason=None if free_bytes >= 7 * GIB else 'Less than 7 GiB free; board bag disabled',
        )

    def tick(self, free_bytes, now, running, interrupt):
        phase = self.state['phase']
        if phase in ('running', 'closing'):
            if not running:
                self.state.update(phase='closed' if phase == 'closing' else 'exited')
            elif phase == 'running' and free_bytes < 6 * GIB:
                self.state.update(phase='closing', reason='Less than 6 GiB free', stop_started=now)
                interrupt()
            elif phase == 'closing' and now - self.state['stop_started'] > 15:
                # Stop sensor production; let the existing supervisor seal the bag.
                raise RuntimeError('Auxiliary recorder did not seal within 15s')
        if free_bytes < 5 * GIB:
            raise RuntimeError('Disk reserve reached')
