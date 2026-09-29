#!/usr/bin/env python3
"""Bounded, subscription-only capture. Receive timestamps are NOT sample times."""
import argparse
import json
import pathlib
import time
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rclpy.serialization import serialize_message
from sensor_msgs.msg import PointCloud2, Imu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--save-all', action='store_true', help='Preserve every received point cloud as CDR')
    parser.add_argument('--seconds', type=float, default=15)
    parser.add_argument('--topic', action='append', choices=[
        '/unitree/slam_lidar/points', '/utlidar/cloud', '/utlidar/imu'])
    args = parser.parse_args()
    if not 0 < args.seconds <= 60:
        parser.error('seconds must be in (0, 60]')
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    rclpy.init()
    node = Node('fast_livo2_input_audit')
    counts = {}
    qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT,
                     durability=DurabilityPolicy.VOLATILE)
    log = (out / 'messages.jsonl').open('w')

    def receive(topic, msg):
        wall, mono = time.time_ns(), time.monotonic_ns()
        counts[topic] = counts.get(topic, 0) + 1
        row = dict(topic=topic, index=counts[topic], receive_unix_ns=wall,
                   receive_monotonic_ns=mono, frame_id=msg.header.frame_id,
                   stamp_sec=msg.header.stamp.sec, stamp_nanosec=msg.header.stamp.nanosec)
        if isinstance(msg, PointCloud2):
            row.update(width=msg.width, height=msg.height, point_step=msg.point_step,
                       row_step=msg.row_step, is_bigendian=msg.is_bigendian,
                       is_dense=msg.is_dense, data_bytes=len(msg.data),
                       fields=[dict(name=f.name, datatype=f.datatype, offset=f.offset,
                                    count=f.count) for f in msg.fields])
            # Inspect the measured packed XT16 schema without reinterpreting its time units.
            schema = {(f.name, f.datatype, f.offset, f.count) for f in msg.fields}
            expected = {('x',7,0,1),('y',7,4,1),('z',7,8,1),('intensity',7,12,1),('ring',4,16,1),('time',7,18,1)}
            if schema == expected and not msg.is_bigendian and msg.point_step == 22 and msg.height == 1 and msg.width > 0 and len(msg.data) >= msg.width * 22:
                dtype = np.dtype({'names':['x','y','z','intensity','ring','time'], 'formats':['<f4','<f4','<f4','<f4','<u2','<f4'], 'offsets':[0,4,8,12,16,18], 'itemsize':22})
                points = np.frombuffer(msg.data, dtype=dtype, count=msg.width)
                ts = points['time'].astype(float)
                row['point_stats'] = dict(time_min=float(ts.min()), time_max=float(ts.max()), time_decreases=int(np.sum(np.diff(ts)<0)), ring_min=int(points['ring'].min()), ring_max=int(points['ring'].max()), nonfinite=sum(int(np.sum(~np.isfinite(points[k]))) for k in ['x','y','z','time']), xyz_mean=[float(points[k].mean()) for k in ['x','y','z']])
            # Default keeps 5 frames; --save-all keeps every received cloud.
            if args.save_all or counts[topic] <= 5:
                name = topic.strip('/').replace('/', '_') + f'_{counts[topic]}.cdr'
                (out / name).write_bytes(serialize_message(msg))
                row['cdr_file'] = name
        else:
            row.update(angular_velocity=[msg.angular_velocity.x, msg.angular_velocity.y,
                                         msg.angular_velocity.z],
                       linear_acceleration=[msg.linear_acceleration.x,
                                            msg.linear_acceleration.y,
                                            msg.linear_acceleration.z],
                       orientation_xyzw=[msg.orientation.x, msg.orientation.y,
                                         msg.orientation.z, msg.orientation.w],
                       angular_velocity_covariance=list(msg.angular_velocity_covariance),
                       linear_acceleration_covariance=list(msg.linear_acceleration_covariance),
                       orientation_covariance=list(msg.orientation_covariance))
        log.write(json.dumps(row) + '\n')

    topics = {'/unitree/slam_lidar/points': PointCloud2,
              '/utlidar/cloud': PointCloud2, '/utlidar/imu': Imu}
    if args.topic:
        topics = {topic: topics[topic] for topic in args.topic}
    subscriptions = [node.create_subscription(typ, topic,
                     lambda msg, t=topic: receive(t, msg), qos)
                     for topic, typ in topics.items()]
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.seconds:
            rclpy.spin_once(node, timeout_sec=0.2)
        summary = dict(duration_seconds=time.monotonic()-start, counts=counts,
                       requested_topics=list(topics), save_all=args.save_all,
                       discovered_topics=node.get_topic_names_and_types(),
                       note='Receive times only; hardware origin and physical stillness unverified.')
        (out / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
    finally:
        log.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0 if counts else 1


if __name__ == '__main__':
    raise SystemExit(main())
