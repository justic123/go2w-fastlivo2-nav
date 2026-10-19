"""Cold-start settling only; does not relax runtime or motion freshness limits."""
class StartupGate:
    def __init__(self,now,timeout=40,stable_seconds=1):
        self.deadline=now+timeout;self.stable_seconds=stable_seconds;self.good_since=None
    def observe(self,now,inputs_ready,lifecycle_ready):
        if now>self.deadline:raise RuntimeError('Nav2启动后输入未能稳定，请检查传感器及生命周期日志')
        if not (inputs_ready and lifecycle_ready):self.good_since=None;return False
        if self.good_since is None:self.good_since=now
        return now-self.good_since>=self.stable_seconds
