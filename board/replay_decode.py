#!/usr/bin/env python3
"""JPEG decoder: sample replay by source time; native camera is already rate limited."""
import json
import time
from image_sampling import ImageSampler
import signal
import sys
from pathlib import Path

import cv2
import numpy as np
import rospy
from sensor_msgs.msg import CompressedImage, Image

cv2.setNumThreads(1)
rospy.init_node('go2w_replay_image_decode')
output=Path(sys.argv[1])
mode=sys.argv[2]
if mode not in ('5hz','10hz'):
    raise SystemExit('Expected 5hz or 10hz')
source_rate_limited='--source-rate-limited' in sys.argv[3:]
sampler=ImageSampler(mode,source_rate_limited)
publisher=rospy.Publisher('/go2w_livo/image_raw',Image,queue_size=2)
stats=dict(received=0,published=0,rejected=0,rate_skipped=0,mode=mode,source_rate_limited=source_rate_limited,
           input_size=[1920,1080],output_size=[640,360],
           first_stamp=None,last_stamp=None,
           stamp_source='original SDK response stamp; not calibrated exposure time')
last_health=0.

def receive(message):
    global last_health
    began=time.monotonic()
    stats['received']+=1
    stamp=message.header.stamp.to_sec()
    if not sampler.accept(stamp):
        stats['rate_skipped']+=1
        return
    try:
        frame=cv2.imdecode(np.frombuffer(message.data,dtype=np.uint8),cv2.IMREAD_COLOR)
        if frame is None or frame.shape!=(1080,1920,3):
            raise ValueError('Expected original 1920x1080 JPEG')
        frame=cv2.resize(frame,(640,360),interpolation=cv2.INTER_AREA)
        image=Image()
        image.header=message.header
        image.height=360;image.width=640;image.encoding='bgr8'
        image.is_bigendian=False;image.step=1920;image.data=frame.tobytes()
        publisher.publish(image)
        stats['published']+=1
        if stats['first_stamp'] is None:stats['first_stamp']=stamp
        stats['last_stamp']=stamp
        stats['decode_s']=time.monotonic()-began
        if time.monotonic()-last_health>=1:
            stats['updated']=time.time()
            health=output.with_name('image_health.json');temp=health.with_suffix('.tmp')
            temp.write_text(json.dumps(stats));temp.replace(health);last_health=time.monotonic()
    except Exception as error:
        stats['rejected']+=1
        rospy.logerr(str(error))

subscriber=rospy.Subscriber('/go2w_livo/jpeg',CompressedImage,receive,
                            queue_size=2,buff_size=4*1024*1024)
def stop(*_):
    rospy.signal_shutdown('Replay supervisor stopped decoder')
signal.signal(signal.SIGTERM,stop)
try:
    rospy.spin()
finally:
    subscriber.unregister()
    duration=(stats['last_stamp']-stats['first_stamp']) if stats['published']>1 else 0.0
    stats['published_hz']=(stats['published']-1)/duration if duration else None
    output.write_text(json.dumps(stats,indent=2)+'\n')
