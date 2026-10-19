#!/usr/bin/env python3
"""Compare complete replay evidence; pose agreement is NOT ground-truth accuracy."""
import argparse
import json
import re
from pathlib import Path
from analyze import summarize, compare, describe


def visual_summary(folder):
    text = (folder / 'algorithm.log').read_text(errors='replace')
    retrieval = [float(v) * 1000 for v in re.findall(r'retrieveFromVisualSparseMap\s*\|\s*([\d.]+)', text)]
    added = [int(v) for v in re.findall(r'\[ VIO \] Append (\d+)', text)]
    tracked = [int(v) for v in re.findall(r'\[ VIO \] Retrieve (\d+) points', text)]
    result = summarize(folder)
    result['visual'] = dict(retrieval_ms=describe(retrieval), first100_ms=describe(retrieval[:100]),
                            last100_ms=describe(retrieval[-100:]), points_added=sum(added),
                            last100_points_added=sum(added[-100:]), tracked=describe(tracked))
    poses = [json.loads(s)['data']['pose'] for s in (folder/'observations.jsonl').read_text().splitlines()
             if json.loads(s)['kind'] == 'odom']
    if poses:
        result['first_pose'] = poses[0]
        result['last_pose'] = poses[-1]
    result['max_rss_mib'] = max((int(s['rss'].split()[1])/1024 for s in result['run']['samples']), default=0)
    result['run'].pop('samples', None)
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    runs = [visual_summary(x) for x in (a.baseline,a.candidate)]
    a.output.write_text(json.dumps(dict(runs=runs,comparison=compare(a.baseline,a.candidate)),indent=2,allow_nan=False)+'\n')
    for r in runs:
        print(json.dumps(dict(release=r['run']['release'],error=r['run']['error'],odom_count=r['odom_count'],
                              duration=r['source_duration_s'],visual=r['visual'],max_rss_mib=r['max_rss_mib']),indent=2))
