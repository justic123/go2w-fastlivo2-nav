"""ROS2 visualization export, bound only to loopback and reached through SSH."""
import socket
import select
import threading
import time
import rclpy
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.serialization import serialize_message, deserialize_message
from view_transport import TOPICS, INPUTS, send, receive, message_class as get_message

rclpy.init();node=rclpy.create_node('onboard_view_export')
latest={};transforms={};lock=threading.Lock();classes={k:get_message(v) for k,v in INPUTS.items()}
pubs={k:node.create_publisher(classes[k],k,10) for k in INPUTS}


def callback(message, topic):
    with lock:
        if topic in ('/tf','/tf_static'):
            table=transforms.setdefault(topic,{})
            for transform in message.transforms:table[transform.child_frame_id]=transform
            message=type(message)(transforms=list(table.values()))
        key=(topic,message.ns,message.id) if TOPICS[topic][0]=='visualization_msgs/msg/Marker' else (topic,)
        latest[key]=(time.monotonic_ns(),serialize_message(message))


for topic,(typ,latched) in TOPICS.items():
    qos=QoSProfile(depth=10 if typ=='visualization_msgs/msg/Marker' else 1,durability=DurabilityPolicy.TRANSIENT_LOCAL if latched else DurabilityPolicy.VOLATILE)
    node.create_subscription(get_message(typ),topic,lambda m,t=topic:callback(m,t),qos)


def commands(conn, done):
    try:
        while rclpy.ok() and not done.is_set():
            # Receiving no clicks is normal. Do not expire a healthy display
            # connection just because its input direction has been idle.
            if not select.select([conn],[],[],1)[0]:continue
            topic,raw=receive(conn,INPUTS,1024*1024)
            pubs[topic].publish(deserialize_message(raw,classes[topic]))
    except (OSError,EOFError,ValueError):done.set()


def server():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        listener.bind(('127.0.0.1',11345));listener.listen(1);listener.settimeout(1)
        while rclpy.ok():
            try:conn,_=listener.accept()
            except socket.timeout:continue
            with conn:
                # Idle reads use select; incomplete packets or blocked sends
                # reconnect rather than blocking fresh visualization indefinitely.
                conn.settimeout(1);done=threading.Event();sent={}
                reader=threading.Thread(target=commands,args=(conn,done),daemon=True);reader.start()
                try:
                    while rclpy.ok() and not done.is_set():
                        with lock:batch=dict(latest)
                        for key,(seq,raw) in batch.items():
                            if sent.get(key)==seq:continue
                            send(conn,key[0],raw);sent[key]=seq
                        time.sleep(.05)
                except (OSError,ValueError):pass
                finally:
                    done.set()
                    try:conn.shutdown(socket.SHUT_RDWR)
                    except OSError:pass


threading.Thread(target=server,daemon=True).start()
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.try_shutdown()
