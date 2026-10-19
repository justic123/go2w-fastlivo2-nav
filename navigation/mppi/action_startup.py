"""Wait for live feedback before opening any motion transport; never relax its limits."""


def wait_stationary(pump, healthy, stationary, clock, fatal, timeout=12., settle=4.):
    start = clock()
    last_error = '等待定位与代价地图订阅'
    retries = 0
    while clock() - start < timeout:
        problem = fatal()
        if problem:
            raise RuntimeError(problem)
        pump()
        if clock() - start < settle:
            continue
        try:
            healthy()
        except (RuntimeError, ValueError) as error:
            last_error = str(error)
            retries += 1
            continue
        if stationary():
            return dict(wait_s=clock()-start, retries=retries,
                        last_wait_reason=last_error if retries else None)
        last_error = '尚未采集到连续静止位姿'
    raise RuntimeError('启动前等待新鲜、静止定位超时：' + last_error)
