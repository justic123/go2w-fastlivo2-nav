"""Read-only saved target, ordered route and planning-result display."""
import json,time,math
from pathlib import Path
from geometry_msgs.msg import Point,PoseStamped
from nav_msgs.msg import Path as RosPath
from visualization_msgs.msg import Marker,MarkerArray
from route_model import route_spec

def read(p,default):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return default

def messages(maproot):
 book=read(maproot/'console_points.json',{});points=book.get('points',{});names=(book.get('route') or {}).get('names',[]);progress=read(maproot/'mission_progress.json',{})
 markers=MarkerArray();clear=Marker();clear.action=Marker.DELETEALL;markers.markers.append(clear)
 for index,(name,target) in enumerate(points.items()):
  if target.get('map_id')!=maproot.name or target.get('frame')!='map':continue
  pose=target['pose'];m=Marker();m.header.frame_id='map';m.ns='saved_targets';m.id=index*2;m.type=Marker.ARROW;m.pose.position.x,m.pose.position.y=map(float,pose[:2]);m.pose.position.z=.12;m.pose.orientation.z=math.sin(pose[2]/2);m.pose.orientation.w=math.cos(pose[2]/2);m.scale.x=.28;m.scale.y=.06;m.scale.z=.06;m.color.r=.15;m.color.g=.7;m.color.b=1.;m.color.a=1.
  order=[str(i+1) for i,v in enumerate(names) if v==name];markers.markers.append(m)
  label=Marker();label.header.frame_id='map';label.ns='saved_targets';label.id=index*2+1;label.type=Marker.TEXT_VIEW_FACING;label.pose.position.x=float(pose[0]);label.pose.position.y=float(pose[1])+.22;label.pose.position.z=.25;label.pose.orientation.w=1.;label.scale.z=.18;label.color=m.color;label.text=('/'.join(order)+': ' if order else '')+name;markers.markers.append(label)
 plan=RosPath();plan.header.frame_id='map';preview=read(maproot/'mission_view.json',{})
 try:fingerprint=route_spec(dict(map_id=maproot.name,points=points,route=book.get('route')))['fingerprint']
 except (ValueError,TypeError,AttributeError,KeyError):fingerprint=None
 if fingerprint and preview.get('fingerprint')==fingerprint and preview.get('success'):
  for segment in preview['segments']:
   for x,y in segment['path']:
    p=PoseStamped();p.header.frame_id='map';p.pose.position.x=float(x);p.pose.position.y=float(y);p.pose.position.z=.03;p.pose.orientation.w=1.;plan.poses.append(p)
 info=Marker();info.header.frame_id='map';info.ns='mission';info.id=0;info.type=Marker.TEXT_VIEW_FACING;info.pose.position.y=2.5;info.pose.position.z=.6;info.pose.orientation.w=1.;info.scale.z=.18;info.color.r=1.;info.color.g=.75;info.color.b=.15;info.color.a=1.
 text='ROUTE (stop at each): '+' > '.join(names) if names else 'No ordered route; save points then choose menu 14'
 if progress.get('names')==names and names:text+='\n'+str(progress.get('phase'))+' | completed '+str(progress.get('completed',0))+'/'+str(len(names))
 if plan.poses:text+='\nPLAN PREVIEW'+(' (expired - replan before motion)' if time.time()-preview.get('created',0)>60 else '')
 info.text=text;markers.markers.append(info);return markers,plan
