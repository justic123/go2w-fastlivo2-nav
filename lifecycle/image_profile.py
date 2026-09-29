"""Select decoder mode only while capture is stopped; never restarts the robot."""
import sys,json
from service_core import ROOT,read,atomic,snapshot,ControlLock
mode=sys.argv[1]
if mode=='status':
 s=snapshot('capture');print(json.dumps(dict(configured=read(ROOT/'image_profile.json').get('mode','baseline'),active=read(ROOT/s['run']/'capture_settings.json').get('image_profile','baseline') if s.get('run') else None,running=s['running']),ensure_ascii=False))
elif mode in ('baseline','5hz','10hz'):
 with ControlLock(ROOT/'capture_control_v2.lock'):
  s=snapshot('capture')
  if s['running'] or s['children_alive']:raise SystemExit('Stop capture before changing image profile')
  atomic(ROOT/'image_profile.json',dict(mode=mode));print(mode)
else:raise SystemExit('status/baseline/5hz')
