"""Board preview only. Refresh clocks without disabling age or stream-loss guards."""
import time,json
from pathlib import Path
from guard_client import Guard
rows=[];g=Guard(False)
try:
 end=time.monotonic()+8.2
 while time.monotonic()<end:
  created=time.monotonic();g.send((.1,0.,.1),created);time.sleep(.05)
 assert len(g.clock_checks)>=4
 rows.append(dict(case='active_clock_refresh',checks=g.clock_checks,stop=g.close()))
except Exception:
 g.close();raise
g=Guard(False)
try:
 g.offset+=.02
 try:g.send((.1,0.,0.))
 except RuntimeError:pass
 else:raise AssertionError('Future command was accepted')
 stop=g.close();assert stop['reason']=='invalid_or_expired_command';rows.append(dict(case='future_still_rejected',stop=stop))
except Exception:g.close();raise
p=Path(__file__).resolve().parent;state=Path(json.loads((p/'current.json').read_text())['folder']);(state/'guard-clock-tests.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
