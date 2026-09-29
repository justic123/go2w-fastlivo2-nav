#!/usr/bin/env python3
"""Isolated stationary synthetic input; never use as robot calibration."""
import math
import time
import rospy
from sensor_msgs.msg import Imu, PointField
from sensor_msgs import point_cloud2
from nav_msgs.msg import Odometry
from std_msgs.msg import Header

rospy.init_node('synthetic_lio_test')
odometry = []
invalid_odometry = []
def record(msg):
    p = msg.pose.pose.position
    q = msg.pose.pose.orientation
    values = [p.x, p.y, p.z, q.x, q.y, q.z, q.w]
    if not all(math.isfinite(x) for x in values):
        invalid_odometry.append(values)
    odometry.append(values)
sub = rospy.Subscriber('/aft_mapped_to_init', Odometry, record, queue_size=100)
lidar = rospy.Publisher('/fast_livo2_smoke/no_lidar', point_cloud2.PointCloud2, queue_size=10)
imu = rospy.Publisher('/fast_livo2_smoke/no_imu', Imu, queue_size=100)
limit = time.monotonic() + 10
while not (lidar.get_num_connections() and imu.get_num_connections()):
    if time.monotonic() > limit:
        raise RuntimeError('No LIO input subscribers')
    time.sleep(.1)
fields = [PointField(n, off, typ, 1) for n, off, typ in [
    ('x',0,7),('y',4,7),('z',8,7),('intensity',12,7),('ring',16,4),('timestamp',18,8)]]
# Three intersecting planes, static IMU with +g along z; identity extrinsic.
xyz = []
for a in range(-15,16):
    for b in range(-15,16):
        u,v = a*.1,b*.1
        xyz.extend([(3.,u,v),(u,3.,v),(u,v,-2.)])
# Empty and incompatible-schema frames must not block subsequent valid scans.
empty = point_cloud2.create_cloud(Header(stamp=rospy.Time.now()), fields, [])
lidar.publish(empty)
bad_fields = [PointField(f.name if f.name != 'timestamp' else 'time', f.offset, f.datatype, f.count) for f in fields]
lidar.publish(point_cloud2.create_cloud(Header(stamp=rospy.Time.now()), bad_fields, [(3.,0.,0.,20.,0,1.)]))
time.sleep(.2)
start = rospy.Time.now().to_sec()
wall = time.monotonic()
for step in range(1800):
    ts = start + step*.005
    if step % 20 == 0:
        points = [(x,y,z,20.,i%16,ts+i*.095/(len(xyz)-1)) for i,(x,y,z) in enumerate(xyz)]
        cloud = point_cloud2.create_cloud(Header(stamp=rospy.Time.from_sec(ts), frame_id='synthetic_lidar'), fields, points)
        lidar.publish(cloud)
    msg = Imu()
    msg.header.stamp = rospy.Time.from_sec(ts)
    msg.header.frame_id = 'synthetic_imu'
    msg.orientation.w = 1.
    msg.linear_acceleration.z = 9.81
    imu.publish(msg)
    time.sleep(max(0., wall+(step+1)*.005-time.monotonic()))
time.sleep(2.)
assert not invalid_odometry, 'Nonfinite odometry received'
assert len(odometry) >= 10, 'Insufficient odometry: %d' % len(odometry)
max_position = max(math.sqrt(sum(v*v for v in p[:3])) for p in odometry)
assert max_position < .2, 'Static synthetic position drift: %s' % max_position
print('PASS: %d finite odometry outputs; max static position %.6f m' % (len(odometry),max_position))
