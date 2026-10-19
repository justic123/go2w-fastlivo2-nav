#!/usr/bin/env python3
"""Run serial, isolated bag comparisons. Never starts live capture or changes power."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

HERE=Path(__file__).resolve().parent
CASES={
    'dense10': ['--image-profile','10hz'],
    'dense5': ['--image-profile','5hz'],
    'lio_dense': ['--image-profile','off'],
    'balanced10': ['--image-profile','10hz','--point-filter-num','4','--surface-leaf-size','.15'],
    'balanced5': ['--image-profile','5hz','--point-filter-num','4','--surface-leaf-size','.15'],
}
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--release',type=Path,required=True)
p.add_argument('--bag',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--seconds',type=float,default=120)
p.add_argument('--threads',type=int,choices=[1,2,4],default=2)
p.add_argument('--cases',nargs='+',choices=sorted(CASES),default=['dense5','lio_dense','balanced10'])
a=p.parse_args()
if len(set(a.cases))!=len(a.cases):raise SystemExit('Each case must be unique')
a.output.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('board_analysis',HERE/'analyze.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)
power=subprocess.run(['/usr/sbin/nvpmodel','-q'],capture_output=True,text=True)
machine=dict(cpu_online=Path('/sys/devices/system/cpu/online').read_text().strip(),
             nvpmodel_stdout=power.stdout,nvpmodel_stderr=power.stderr,
             nvpmodel_returncode=power.returncode)
(a.output/'machine.json').write_text(json.dumps(machine,indent=2))
results=[]
for name in a.cases:
    folder=a.output/name
    monitor=None;telemetry=None
    print(json.dumps(dict(phase='started',case=name,seconds=a.seconds,threads=a.threads)),flush=True)
    try:
        tegra=shutil.which('tegrastats')
        if tegra:
            telemetry=(a.output/(name+'-tegrastats.log')).open('w')
            monitor=subprocess.Popen([tegra,'--interval','1000'],stdout=telemetry,
                                     stderr=subprocess.STDOUT,start_new_session=True)
        command=['/usr/bin/python3',str(HERE/'replay.py'),'--release',str(a.release),
                 '--bag',str(a.bag),'--output',str(folder),'--seconds',str(a.seconds),
                 '--threads',str(a.threads),'--backend','cpu']+CASES[name]
        with (a.output/(name+'-controller.log')).open('w') as log:
            replay=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    finally:
        if monitor and monitor.poll() is None:
            os.killpg(monitor.pid,signal.SIGTERM)
            monitor.wait(timeout=5)
        if telemetry:telemetry.close()
    result=dict(case=name,returncode=replay.returncode)
    if (folder/'observations.jsonl').exists() and (folder/'run.json').exists():
        summary=analysis.summarize(folder)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
        result.update(profile_count=summary['profile_count'],odom_count=summary['odom_count'],
                      source_duration_s=summary['source_duration_s'],
                      stage_ms={k:v for k,v in summary['stages_ms'].items()
                                if k in ('lio_full','vio_full','loop_work','callbacks')},
                      lag_s=summary['metrics'].get('processing_lag_s'),
                      final_metrics=summary['run'].get('final_profile',{}).get('metrics',{}),
                      error=summary['run'].get('error'))
        events=[json.loads(row) for row in (folder/'observations.jsonl').read_text().splitlines()]
        odom=[event['data'] for event in events if event['kind']=='odom']
        if odom:
            result['pose_span_xyz_m']=[max(x['pose'][i] for x in odom)-min(x['pose'][i] for x in odom) for i in range(3)]
        images=folder/'images.json'
        if images.exists():result['images']=json.loads(images.read_text())
    else:
        result['error']=(a.output/(name+'-controller.log')).read_text()[-4000:]
    results.append(result)
    (a.output/'comparison.json').write_text(json.dumps(results,indent=2,allow_nan=False))
    print(json.dumps(dict(phase='finished',**result),allow_nan=False),flush=True)
    if replay.returncode:
        raise SystemExit('Case failed; inspect logs before continuing: '+name)
