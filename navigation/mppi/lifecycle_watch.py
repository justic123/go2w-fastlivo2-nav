"""Fail closed on failed activation or later lifecycle loss; process alive != ready."""
import time,json
from pathlib import Path
import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import GetState
rclpy.init();n=Node('mppi_lifecycle_watch');root=Path('/state');names=(['map_server'] if Path('/work/selection.json').exists() else [])+['planner_server','controller_server','velocity_smoother','bt_navigator'];clients={k:n.create_client(GetState,'/'+k+'/get_state') for k in names};deadline=time.monotonic()+25;active=False
try:
 while rclpy.ok():
  states={}
  for k,c in clients.items():
   if not c.wait_for_service(timeout_sec=.3):states[k]='unavailable';continue
   f=c.call_async(GetState.Request());end=time.monotonic()+1
   while not f.done() and time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
   states[k]=f.result().current_state.label if f.done() else 'timeout'
  ready=all(v=='active' for v in states.values());tmp=root/'lifecycle.tmp';tmp.write_text(json.dumps(dict(ready=ready,states=states,updated=time.time())));tmp.replace(root/'lifecycle.json')
  if ready:active=True
  elif active or time.monotonic()>deadline:raise RuntimeError('Nav2 lifecycle unhealthy: '+str(states))
  time.sleep(.5)
finally:n.destroy_node();rclpy.shutdown()
