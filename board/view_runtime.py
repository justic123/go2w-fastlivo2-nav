"""Own the display exporter and optional saved map without a planner or SDK."""
import signal
import subprocess
import sys
import time

stop=False;children=[]
def request(*_):
    global stop
    stop=True
signal.signal(signal.SIGINT,request);signal.signal(signal.SIGTERM,request)
try:
    children.append(subprocess.Popen(['python3','/board/view_server.py'],start_new_session=True))
    if len(sys.argv)>1 and sys.argv[1]:
        children.append(subprocess.Popen(['python3','/work/initial_pose.py','--map-id',sys.argv[1],
                                         '--display-only','--click-output','/view-state/clicked_goal.json'],start_new_session=True))
    while not stop:
        if any(p.poll() is not None for p in children):raise RuntimeError('Display child exited')
        time.sleep(.2)
finally:
    for p in children:
        if p.poll() is None:p.send_signal(signal.SIGTERM)
    for p in children:
        try:p.wait(timeout=4)
        except subprocess.TimeoutExpired:p.kill();p.wait()
