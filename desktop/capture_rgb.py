import rospy
from sensor_msgs.msg import CompressedImage
from pathlib import Path
rospy.init_node('rgb_environment_audit')
m=rospy.wait_for_message('/go2w_livo/jpeg',CompressedImage,timeout=8)
Path('/work/evidence/current_rgb.jpg').write_bytes(m.data)
print(m.header)
