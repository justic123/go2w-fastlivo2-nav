"""Board preview only: no DDS/SportClient. Check timing, expiry, and independent stop."""
import time,json
from guard_client import Guard
rows=[]
g=Guard(False)
for v in ((.1,0.,0.),(-.05,0.,.2),(0.,0.,0.)):g.send(v);time.sleep(.05)
stop=g.close();assert stop and stop['stop_code']==0 and stop['execute'] is False
rows.append(dict(case='bounded_forward_reverse_zero',rtt_s=g.rtt,stop=stop))
g=Guard(False)
try:
 g.send((.1,0.,0.),time.monotonic()-.25)
 raise AssertionError('Expired command accepted')
except RuntimeError:pass
stop=g.close();assert stop and stop['reason']=='invalid_or_expired_command';rows.append(dict(case='expired_rejected',stop=stop))
g=Guard(False);g.send((.1,0.,0.));time.sleep(.45);stop=g.close();assert stop and stop['reason']=='input_watchdog';rows.append(dict(case='stream_loss_stop',stop=stop))
print(json.dumps(rows,indent=2))
