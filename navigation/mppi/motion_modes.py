"""Per-point arrival actions. Pure validation; SDK calls live behind an adapter."""
import hashlib
import json
import math
import time

from go2w_mode_adapter import Go2WModeAdapter

LABELS = {'keep': '不切换', 'obstacle': '切换普通越障模式', 'normal': '恢复默认模式'}


def arrival_motion(target):
    action = target.get('arrival_motion', {'switch': False, 'mode': 'obstacle'})
    if not isinstance(action, dict) or set(action) != {'switch', 'mode'}:
        raise ValueError('到点参数须包含switch和mode')
    if type(action['switch']) is not bool or action['mode'] not in ('obstacle', 'normal'):
        raise ValueError('到点切换参数无效')
    return dict(action)


def action_choice(choice):
    if choice not in ('keep', 'obstacle', 'normal'):
        raise ValueError('到点动作须为keep、obstacle或normal')
    return dict(switch=choice != 'keep', mode='obstacle' if choice == 'keep' else choice)


def action_label(target):
    action = arrival_motion(target)
    return LABELS[action['mode'] if action['switch'] else 'keep'] + ('；结束自动任务，人工接管' if manual_handoff(target) else '')


def manual_handoff(target):
    value = target.get('manual_handoff', False)
    if type(value) is not bool:
        raise ValueError('人工接管参数须为布尔值')
    return value


def point_fingerprint(target):
    data = {key: target.get(key) for key in ('name', 'map_id', 'source_session', 'pose')}
    data['arrival_motion'] = arrival_motion(target)
    data['manual_handoff'] = manual_handoff(target)
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def require_available(targets, adapter=None):
    modes = {action['mode'] for target in targets
             if (action := arrival_motion(target))['switch']}
    if not modes:
        return None
    adapter = adapter if adapter is not None else Go2WModeAdapter()
    if not modes.issubset(adapter.supported_modes()):
        raise RuntimeError('已保存到点切换参数，但普通越障/默认模式的实机接口尚未配置；未开始运动。可将点参数设为“不切换”使用原导航')
    limits = getattr(adapter, 'check_limits', None)
    if limits is not None:limits(modes)
    return adapter


def _apply_after_stop(target, result, *, adapter=None, check=lambda: None, timeout_s=3.):
    """A successful stop precedes the request; fresh feedback must confirm it."""
    action = arrival_motion(target)
    if not action['switch']:
        return dict(requested=False, success=True)
    if (result.get('execute') is not True or not result.get('success')
            or not result.get('stationary_after_stop')
            or result.get('guard_stop', {}).get('stop_code') != 0):
        raise RuntimeError('尚未确认闭环到位、停车成功并停稳，禁止切换模式')
    if point_fingerprint(result.get('target', {})) != point_fingerprint(target):
        raise RuntimeError('到点结果与点参数/地图/会话不一致，禁止切换')
    adapter = require_available([target], adapter)
    check()
    issued = time.monotonic()
    checkpoint = {key: target.get(key) for key in ('name', 'map_id', 'source_session')}
    code = adapter.set_mode(action['mode'], checkpoint=checkpoint)
    if type(code) is not int or code != 0:
        raise RuntimeError('到点模式切换失败，SDK返回：' + str(code))
    # The bounded SDK transport includes its own stationary check. Do not let
    # that consume the independent DDS-confirmation budget.
    feedback_deadline = time.monotonic() + timeout_s
    while time.monotonic() < feedback_deadline:
        check()
        feedback = adapter.read_mode()
        received = feedback.get('received_monotonic')
        now = time.monotonic()
        if (feedback.get('mode') == action['mode'] and type(received) in (float, int)
                and math.isfinite(received) and issued <= received <= now
                and now - received <= .5):
            check()
            return dict(requested=True, mode=action['mode'], success=True,
                        sdk_code=code, confirmed=True, feedback=feedback)
        time.sleep(.05)
    raise RuntimeError('模式切换未获得新鲜的目标状态确认，停止后续路线')


def apply_after_stop(target, result, *, adapter=None, check=lambda: None, timeout_s=3.):
    if not arrival_motion(target)['switch']:
        return dict(requested=False, success=True)
    adapter = adapter if adapter is not None else Go2WModeAdapter()
    try:
        return _apply_after_stop(target, result, adapter=adapter, check=check, timeout_s=timeout_s)
    finally:
        close = getattr(adapter, 'close', None)
        if close is not None:close()
