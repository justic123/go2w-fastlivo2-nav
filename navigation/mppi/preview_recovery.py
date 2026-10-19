"""Bounded freshness recovery for read-only planning, never velocity execution."""
import time

def wait_healthy(check,pump=None,timeout=3.,settle=.2,clock=time.monotonic):
    pump=pump or (lambda:time.sleep(.05))
    end=clock()+timeout;recovering=False;good_since=None;last=None
    while True:
        try:
            result=check()
            if not recovering:return result
            if good_since is None:good_since=clock()
            if clock()-good_since>=settle:return result
        except (RuntimeError,OSError,ValueError,KeyError) as e:
            recovering=True;good_since=None;last=e
        if clock()>=end:
            raise RuntimeError('等待新鲜输入超时；任务进度保留，请稍后重新预演：'+str(last)) from last
        pump()
