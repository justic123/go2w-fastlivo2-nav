"""Read-only 15-second observation of existing camera and VIO topics."""
import rospy,time,json,statistics
from sensor_msgs.msg import Image,CompressedImage
rospy.init_node('image_rate_audit',anonymous=True)
data={k:[] for k in ['jpeg','image','vio']};subs=[]
for k,t,c in [('jpeg','/go2w_livo/jpeg',CompressedImage),('image','/go2w_livo/image_raw',Image),('vio','/rgb_img',Image)]:
 subs.append(rospy.Subscriber(t,c,lambda m,k=k:data[k].append((time.monotonic(),rospy.Time.now().to_sec()-m.header.stamp.to_sec())),queue_size=2))
time.sleep(15)
result={}
for k,a in data.items():result[k]=dict(frames=len(a),hz=(len(a)-1)/(a[-1][0]-a[0][0]) if len(a)>1 else None,median_stamp_age_s=statistics.median(v[1] for v in a) if a else None)
print(json.dumps(result,indent=2))
