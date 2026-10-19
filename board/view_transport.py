"""Explicit ROS topic allowlist for the SSH visualization link, never cmd_vel."""
import json
import struct
import importlib

TOPICS = {
    '/clock': ('rosgraph_msgs/msg/Clock', False),
    '/tf': ('tf2_msgs/msg/TFMessage', False),
    '/tf_static': ('tf2_msgs/msg/TFMessage', True),
    '/mppi/odom': ('nav_msgs/msg/Odometry', False),
    '/mppi/cloud': ('sensor_msgs/msg/PointCloud2', False),
    '/global_costmap/costmap': ('nav_msgs/msg/OccupancyGrid', True),
    '/local_costmap/costmap': ('nav_msgs/msg/OccupancyGrid', True),
    '/local_costmap/published_footprint': ('geometry_msgs/msg/PolygonStamped', False),
    '/plan': ('nav_msgs/msg/Path', False),
    '/mppi/body_heading': ('visualization_msgs/msg/Marker', False),
    '/saved_map/cloud': ('sensor_msgs/msg/PointCloud2', True),
    '/demo/saved_cloud': ('sensor_msgs/msg/PointCloud2', True),
    '/demo/saved_map': ('nav_msgs/msg/OccupancyGrid', True),
    '/demo/view_status': ('visualization_msgs/msg/Marker', True),
    '/demo/mission': ('visualization_msgs/msg/MarkerArray', True),
    '/demo/route_plan': ('nav_msgs/msg/Path', True),
}
INPUTS = {
    '/initialpose': 'geometry_msgs/msg/PoseWithCovarianceStamped',
    '/demo/goal_pose': 'geometry_msgs/msg/PoseStamped',
}
MAX_PACKET = 64 * 1024 * 1024


def message_class(name):
    if name not in {v[0] for v in TOPICS.values()} | set(INPUTS.values()):
        raise ValueError('Message type not allowed')
    package,kind,cls=name.split('/')
    return getattr(importlib.import_module(package+'.'+kind),cls)


def exact(conn, size):
    data = bytearray()
    while len(data) < size:
        part = conn.recv(size - len(data))
        if not part:raise EOFError('Visualization disconnected')
        data.extend(part)
    return bytes(data)


def send(conn, topic, raw):
    if len(raw) > MAX_PACKET:raise ValueError('Visualization packet too large')
    h = json.dumps(dict(topic=topic)).encode()
    conn.sendall(struct.pack('!II', len(h), len(raw)) + h + raw)


def receive(conn, allowed, limit=MAX_PACKET):
    n, size = struct.unpack('!II', exact(conn, 8))
    if not 0 < n <= 1024 or not 0 < size <= limit:raise ValueError('Invalid packet size')
    topic = json.loads(exact(conn, n))['topic']
    if topic not in allowed:raise ValueError('Topic not allowed: ' + topic)
    return topic, exact(conn, size)
