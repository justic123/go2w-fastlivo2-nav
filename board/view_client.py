"""Thin ROS2 display client: no localization, planner, controller or Unitree SDK."""
import os
import socket
import threading
import time
import rclpy
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.serialization import serialize_message,deserialize_message
from view_transport import TOPICS,INPUTS,send,receive,message_class as get_message

rclpy.init();node=rclpy.create_node('onboard_view_import');connection=None;lock=threading.Lock()
classes={k:get_message(v[0]) for k,v in TOPICS.items()}
pubs={k:node.create_publisher(classes[k],k,QoSProfile(depth=10 if v[0]=='visualization_msgs/msg/Marker' else 1,durability=DurabilityPolicy.TRANSIENT_LOCAL if v[1] else DurabilityPolicy.VOLATILE)) for k,v in TOPICS.items()}


def clicked(message,topic):
    with lock:
        if connection is None:return
        try:send(connection,topic,serialize_message(message))
        except OSError:pass


for topic,typ in INPUTS.items():node.create_subscription(get_message(typ),topic,lambda m,t=topic:clicked(m,t),10)


def worker():
    global connection
    while rclpy.ok():
        try:
            with socket.create_connection(('127.0.0.1',11345),timeout=3) as conn:
                conn.settimeout(10)
                with lock:connection=conn
                while rclpy.ok():
                    topic,raw=receive(conn,TOPICS)
                    pubs[topic].publish(deserialize_message(raw,classes[topic]))
        except (OSError,EOFError,ValueError) as e:node.get_logger().info(str(e));time.sleep(1)
        finally:
            with lock:connection=None


threading.Thread(target=worker,daemon=True).start()
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.try_shutdown()
