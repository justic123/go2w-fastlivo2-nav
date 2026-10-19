"""Fresh observations and full planar stop checks for saved-map corrections."""
import math


class ValidationWindow:
    """Reject immediately, revalidate on distinct observations; never accept a bad pose."""
    def __init__(self):
        self.consecutive=0;self.checked=None;self.stamp=None
    def observe(self,accepted,stamp,now):
        if not accepted:
            self.consecutive=0;self.checked=None
            return
        if self.stamp is not None and stamp<=self.stamp:return
        if self.checked is not None and now-self.checked>=5:self.consecutive=0
        self.stamp=stamp;self.checked=now;self.consecutive+=1
    def ready(self,now):
        return self.consecutive>=2 and self.checked is not None and 0<=now-self.checked<5


def registration_problem(fitness,rmse,shift,turn):
    values=(fitness,rmse,shift,turn)
    if not all(math.isfinite(v) for v in values):return 'Nonfinite registration result'
    if fitness<.6 or rmse>.12 or shift>.15 or turn>.12:
        return 'Scan no longer agrees with saved map'
    return None


def fresh_scan(stamp, now, receipt_age, previous_stamp):
    return (all(math.isfinite(v) for v in (stamp, now, receipt_age))
            and -.05 <= now-stamp < .6 and 0 <= receipt_age < .6
            and (previous_stamp is None or stamp > previous_stamp))


def correction_allowed(vx, vy, yaw_rate, receipt_age, motion_active):
    return (not motion_active and all(math.isfinite(v) for v in (vx, vy, yaw_rate, receipt_age))
            and 0 <= receipt_age < .6 and math.hypot(vx, vy) < .015
            and abs(yaw_rate) < .025)


def completed_trial_problem(elapsed, input_ready, input_age):
    """Do not let a late worker result renew readiness or correct the map."""
    if not math.isfinite(elapsed) or not 0 <= elapsed < 2:
        return 'Map validation result expired'
    if not input_ready or not math.isfinite(input_age) or not 0 <= input_age < 1:
        return 'Inputs became stale during map validation'
    return None
