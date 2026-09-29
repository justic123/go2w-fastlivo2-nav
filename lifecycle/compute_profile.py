import sys
from service_core import ROOT,read,atomic,snapshot,ControlLock
mode=sys.argv[1]
if mode=='status':print(read(ROOT/'compute_location.json').get('mode','board'))
elif mode in ('board','desktop'):
 with ControlLock(ROOT/'capture_control_v2.lock'):
  s=snapshot('capture');n=snapshot('nav')
  if s['running'] or s['children_alive'] or n['running'] or n['children_alive']:raise SystemExit('Stop mapping and Nav2 before switching compute location')
  atomic(ROOT/'compute_location.json',dict(mode=mode));print(mode)
else:raise SystemExit('board/desktop/status')
