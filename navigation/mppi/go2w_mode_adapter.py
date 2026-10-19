"""Board-only verified Go2W SwitchGait transport, isolated from velocity control."""
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

# The planner imports metadata from the flat /work container mount.
# Only the native board process may construct the hardware adapter.
_parents=Path(__file__).resolve().parents
ROOT=_parents[2] if len(_parents)>2 else None

class Go2WModeAdapter:
    def __init__(self, root=ROOT):
        if root is None:raise RuntimeError('运控模式接口仅在板载宿主机执行；规划容器只读取点参数')
        self.root=Path(root);self.process=None;self.feedback_queue=queue.Queue(maxsize=50)
        self.config={};self.after=0.
    def supported_modes(self):
        try:
            cfg=json.loads((self.root/'board/calibration/motion_modes.json').read_text())
            deployment=json.loads((self.root/'board/deployment.json').read_text())
            binary=self.root/'navigation/mppi/guard/build/go2w_mode_bridge'
            if (deployment.get('backend')!='board' or cfg.get('verified') is not True
                or cfg.get('machine_id')!=Path('/etc/machine-id').read_text().strip()
                or cfg.get('binary_sha256')!=hashlib.sha256(binary.read_bytes()).hexdigest()
                or cfg.get('api')!='b2.SwitchGait'
                or cfg.get('request')!={'normal':0,'obstacle':1}):return frozenset()
            observed=cfg['feedback_gait']
            if set(observed)!={'normal','obstacle'} or len(set(observed.values()))!=2 or any(type(v)!=int or not 0<=v<=255 for v in observed.values()):return frozenset()
            self.config=cfg;return frozenset(observed)
        except (OSError,ValueError,KeyError,TypeError):return frozenset()
    def check_limits(self, modes):
        if 'obstacle' not in modes:return
        from speed_profiles import selected
        profile=selected(self.root/'navigation/mppi')
        current=self.root/'navigation/mppi/current.json'
        if current.exists():
            active=Path(json.loads(current.read_text())['folder'])/'motion_profile.json'
            if active.exists():profile=json.loads(active.read_text())
        if profile['vx_max']>.7:
            raise RuntimeError('普通越障模式不支持0.8m/s大厅档位；请先切回corridor04或baseline档位并重新预演')

    def set_mode(self, mode, *, checkpoint):
        if mode not in self.supported_modes():raise RuntimeError('当前板端模式接口尚未通过实机校验')
        self.check_limits({mode})
        self.close();self.feedback_queue=queue.Queue(maxsize=50)
        self.process=subprocess.Popen([str(self.root/'navigation/mppi/guard/build/go2w_mode_bridge'),'eth0','--switch',str(self.config['request'][mode])],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        def reader():
            for line in self.process.stdout:
                try:row=json.loads(line)
                except ValueError:continue
                if self.feedback_queue.full():
                    try:self.feedback_queue.get_nowait()
                    except queue.Empty:pass
                self.feedback_queue.put(row)
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
        deadline=time.monotonic()+4.5
        while time.monotonic()<deadline:
            try:row=self.feedback_queue.get(timeout=.2)
            except queue.Empty:
                if self.process.poll() is not None:raise RuntimeError('模式接口退出，未收到SDK确认')
                continue
            if row.get('kind')=='ack':
                self.after=time.monotonic()
                return row['code']
        self.close();raise RuntimeError('模式切换SDK确认超时')
    def read_mode(self):
        try:row=self.feedback_queue.get(timeout=.2)
        except queue.Empty:return {}
        # Require independently received DDS state after the RPC response.
        stamp=row.get('received_monotonic',0);now=time.monotonic()
        if row.get('kind')!='feedback' or not self.after<stamp<=now or now-stamp>.5:return {}
        mode=next((k for k,v in self.config['feedback_gait'].items() if v==row.get('gait_type')),None)
        return dict(mode=mode,received_monotonic=stamp,gait_type=row.get('gait_type'),sport_mode=row.get('sport_mode'))
    def close(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=1)
            if hasattr(self,'reader'):self.reader.join(timeout=1)
            if self.process.stdout:self.process.stdout.close()
            self.process=None
