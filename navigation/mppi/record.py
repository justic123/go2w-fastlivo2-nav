"""Record a checked stationary estimate; no claim of independently measured truth."""
import argparse,json,time,sys
from pathlib import Path
from record_policy import Recorder

def main():
    parser=argparse.ArgumentParser();parser.add_argument('name',nargs='?',default='精度返回点');parser.add_argument('--anchor',action='store_true');args=parser.parse_args()
    root=Path('/state');selection=json.loads(Path('/work/selection.json').read_text())
    recorder=Recorder(selection['map_id'],selection['source_session'])
    for _ in range(35):
        d=json.loads((root/'input.json').read_text());l=json.loads((root/'localization.json').read_text())
        recorder.observe(d,l,time.time());time.sleep(.1)
    current=json.loads(Path('/work/selection.json').read_text())
    if any(current.get(k)!=selection.get(k) for k in ('map_id','source_session')):raise ValueError('地图选择已变化，未记录')
    target=recorder.target(args.name,time.time())
    output=root/('localization_anchor_capture.json' if args.anchor else 'accuracy_target.json')
    temp=output.with_suffix('.tmp');temp.write_text(json.dumps(target,ensure_ascii=False,indent=2,allow_nan=False));temp.replace(output)
    print(json.dumps(target,ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as e:raise SystemExit(str(e))
