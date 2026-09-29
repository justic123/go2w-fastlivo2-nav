#!/usr/bin/env python3
import csv,json,sys,time
from pathlib import Path
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy,DurabilityPolicy
from unitree_go.msg import LowState
from sensor_msgs.msg import Imu
out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
rclpy.init();node=rclpy.create_node('go2w_ros2_sdk_comparison')
f=(out/'ros2.csv').open('w');writer=csv.writer(f);writer.writerow(['receive_unix_ns','receive_monotonic_ns','tick','gx','gy','gz','ax','ay','az','qw','qx','qy','qz'])
counts={'lowstate':0,'dog_imu_raw':0};dog=(out/'dog_imu_raw.jsonl').open('w')
def low(m):
 wall,mono=time.time_ns(),time.monotonic_ns();i=m.imu_state
 writer.writerow([wall,mono,m.tick,*i.gyroscope,*i.accelerometer,*i.quaternion]);counts['lowstate']+=1
def raw(m):
 counts['dog_imu_raw']+=1;dog.write(json.dumps(dict(receipt_ns=time.time_ns(),sec=m.header.stamp.sec,nanosec=m.header.stamp.nanosec,frame=m.header.frame_id,gyro=[m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z],acc=[m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z]))+'\n')
qos=QoSProfile(depth=100,reliability=ReliabilityPolicy.BEST_EFFORT,durability=DurabilityPolicy.VOLATILE)
subs=[node.create_subscription(LowState,'/lowstate',low,qos),node.create_subscription(Imu,'/dog_imu_raw',raw,qos)]
start=time.monotonic()
try:
 while time.monotonic()-start<30:rclpy.spin_once(node,timeout_sec=.1)
 summary=dict(duration=time.monotonic()-start,counts=counts,publishers={k:node.count_publishers(k) for k in ['/lowstate','/dog_imu_raw']})
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
finally:f.close();dog.close();node.destroy_node();rclpy.shutdown()
