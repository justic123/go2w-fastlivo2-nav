"""Fail closed on lifecycle loss while retaining observation for recovery."""
import time,json
from pathlib import Path
from status_store import publish as publish_status
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
   if not f.done():f.cancel()
  ready=all(v=='active' for v in states.values());publish_status(root,'lifecycle',dict(ready=ready,states=states,updated=time.time()))
  if ready:active=True
  elif not active and time.monotonic()>deadline:raise RuntimeError('Nav2 activation failed: '+str(states))
  # After activation, an unhealthy response revokes action eligibility via
  # lifecycle.json. Keep observing; do not kill input/localization on one timeout.
  time.sleep(.5)
except KeyboardInterrupt:pass
finally:n.destroy_node();rclpy.try_shutdown()
