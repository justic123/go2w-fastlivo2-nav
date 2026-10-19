"""Host-side arrival hook, after the protected executor has stopped the robot."""
import json
import math
from pathlib import Path
import time

from motion_modes import apply_after_stop, point_fingerprint
from route_model import stationary
from health_policy import check_context as checked_context
from speed_profiles import source_age_limit


def check_context(state, target, *, route=False):
    state = Path(state)
    if (state / 'arrival_cancel.request').exists() or (route and (state / 'route_cancel.request').exists()):
        raise RuntimeError('到点动作已取消，不继续下一段')
    speed = json.loads((state / 'motion_profile.json').read_text())
    checked_context(state,target,source_age_limit(speed['name']))
    current = json.loads((state / 'accuracy_target.json').read_text())
    if point_fingerprint(current) != point_fingerprint(target):
        raise RuntimeError('到点参数变化，停止切换')


def wait_stable(state, check, timeout_s=5.):
    samples = []
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        check()
        pose = json.loads((Path(state) / 'input.json').read_text())['pose']
        if not samples or pose['stamp'] != samples[-1][3]:
            p = pose['pose']
            x, y, z, w = p[3:]
            angle = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
            samples.append([p[0], p[1], angle, pose['stamp']])
            samples = samples[-100:]
        if stationary(samples):
            return
        time.sleep(.05)
    raise RuntimeError('切换后未重新停稳，不进入下一段')


def finish(state, target, *, adapter, started, route=False):
    state = Path(state)
    paths = [p for p in state.glob('protected-execute-*.json') if p.stat().st_mtime >= started]
    if not paths:
        raise RuntimeError('缺少本轮到点停车结果，不执行切换')
    path = max(paths, key=lambda p: (p.stat().st_mtime_ns, p.name))
    result = json.loads(path.read_text())
    check = lambda: check_context(state, target, route=route)
    outcome = None
    try:
        outcome = apply_after_stop(target, result, adapter=adapter, check=check)
        wait_stable(state, check)
        outcome['stationary_after_switch'] = True
        result['arrival_motion_result'] = outcome
    except BaseException as error:
        result['navigation_success'] = result.get('success', False)
        result['success'] = False
        result['reason'] = '到点动作失败：' + (str(error) or '用户取消')
        result['arrival_motion_result'] = dict(success=False, error=str(error), request_result=outcome)
        raise
    finally:
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        temp.replace(path)
        summary=state/'last-action-result.json';temp=summary.with_suffix('.tmp')
        temp.write_text(json.dumps(dict(result,finished=time.time()),ensure_ascii=False));temp.replace(summary)
    return outcome
