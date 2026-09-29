import rclpy,time,json
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration
from sensor_msgs.msg import PointCloud2
from tf2_ros import Buffer,TransformListener
rclpy.init();n=Node('mppi_tf_probe',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)]);b=Buffer();l=TransformListener(b,n);counts={'clouds':0,'tf_ok':0};errors={};pending=[]
def cb(m):pending.append(m.header);counts['clouds']+=1;counts['points']=m.width*m.height
from rclpy.qos import qos_profile_sensor_data
n.create_subscription(PointCloud2,'/mppi/cloud',cb,qos_profile_sensor_data)
end=time.monotonic()+6
while time.monotonic()<end:
 rclpy.spin_once(n,timeout_sec=.02)
 for h in pending[:]:
  try:
   b.lookup_transform('camera_init',h.frame_id,Time.from_msg(h.stamp));counts['tf_ok']+=1;pending.remove(h)
  except Exception as e:
   errors[str(e)]=1
   if (n.get_clock().now()-Time.from_msg(h.stamp)).nanoseconds>1e9:pending.remove(h)
print(json.dumps(dict(counts=counts,pending=len(pending),errors=list(errors)[-4:]),indent=2));n.destroy_node();rclpy.shutdown()
