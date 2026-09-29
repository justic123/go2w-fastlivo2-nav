#!/usr/bin/env python3
"""Check recorded algorithm input stamps; does not replace the raw tick gate."""
import rosbag,json,csv,sys
from pathlib import Path
root=Path(sys.argv[1]);summary=json.loads((root/'bridge/summary.json').read_text());raw=list(csv.DictReader((root/'bridge/imu_timing.csv').open()));ticks=[int(x['tick']) for x in raw];ts=[]
with rosbag.Bag(str(root/'sensors.bag')) as bag:
 for topic,msg,t in bag.read_messages(topics=['/go2w_lio/imu']):ts.append(msg.header.stamp.to_sec())
gaps=[(b-a)*1000 for a,b in zip(ts,ts[1:])]
large=[dict(row=i,relative_tick_s=(ticks[i]-ticks[0])/1000,gap_ms=ticks[i]-ticks[i-1],end_stamp_from_anchor=summary['tick_anchor']+(ticks[i]-ticks[0])/1000) for i in range(1,len(ticks)) if ticks[i]-ticks[i-1]>20]
r=dict(recorded_imu_count=len(ts),first_recorded_stamp=ts[0],max_recorded_stamp_gap_ms=max(gaps),recorded_gaps_over_20ms=sum(g>20.001 for g in gaps),raw_large_gaps=large,all_raw_large_gaps_before_first_recorded_imu=bool(large) and all(x['end_stamp_from_anchor']<ts[0] for x in large),note='Recorded topic is algorithm input, not proof of every internal sample consumed.')
(root/'recorded_imu_quality.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
