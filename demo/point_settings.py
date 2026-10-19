"""Edit saved waypoint metadata without querying or commanding the robot."""
from motion_modes import action_choice, action_label, arrival_motion, manual_handoff


def edit(c, name=None, choice=None, handoff=None):
    c.assert_no_motion()
    data = c.state()
    if data.get('phase') in ('mapping', 'starting', 'validating_map'):
        raise RuntimeError('请先结束扫图并保存地图，再设置途经点参数')
    if not data.get('map_id'):
        raise RuntimeError('请先保存或选择地图')
    if name is None:
        print('已保存点：' + '、'.join(data.get('points', {})))
        name = input('要编辑的点名称（回车取消）：').strip()
    if not name:
        return
    if name not in data.get('points', {}):
        raise RuntimeError('目标点不存在：' + name)
    if choice is None and handoff is not None:
        current = arrival_motion(data['points'][name])
        choice = current['mode'] if current['switch'] else 'keep'
    if choice is None:
        print(name + ' 当前到点动作：' + action_label(data['points'][name]))
        print('0 不切换\n1 到点停稳后切换普通越障模式\n2 到点停稳后恢复默认模式')
        value = input('选择到点动作（回车保持原设置）：').strip()
        if not value:
            return
        choices = {'0': 'keep', '1': 'obstacle', '2': 'normal'}
        if value not in choices:
            raise ValueError('请输入0、1或2；原设置未改动')
        choice = choices[value]
    action = action_choice(choice)
    if handoff is not None:
        manual_handoff({'manual_handoff': handoff})
        data['points'][name]['manual_handoff'] = handoff
    data['points'][name]['arrival_motion'] = action
    c.save(points=data['points'], preview=None, route_preview=None)
    c.write(c.MPPI / 'maps' / data['map_id'] / 'console_points.json',
            dict(points=data['points'], selected=data.get('selected'), route=data.get('route')))
    # Keep the selected single-goal file consistent for the shared protected
    # executor, without selecting or relocating a different target.
    try:
        path = c.folder() / 'accuracy_target.json'
        current = c.read(path)
    except (OSError, ValueError, KeyError):
        pass
    else:
        target = data['points'][name]
        if all(current.get(key) == target.get(key) for key in ('name', 'map_id', 'source_session', 'pose')):
            c.write(path, target)
    print('已保存点参数：' + name + ' → ' + action_label(data['points'][name]) + '；请重新预演。')
    if action['switch']:
        from go2w_mode_adapter import Go2WModeAdapter
        if action['mode'] in Go2WModeAdapter().supported_modes():
            print('已启用本机验证的到点模式切换；停稳后调用，并核验新鲜状态反馈。')
        else:
            print('当前板端切换接口尚未通过验证；设置可保存，执行前会阻止未验证调用。')


def summary(target):
    try:
        arrival_motion(target)
        return action_label(target)
    except (ValueError, TypeError):
        return '到点参数无效，请编辑修正'
