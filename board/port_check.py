"""Probe listeners with the same reuse semantics as the owned ROS/TCP servers."""
import socket

def check_ports(ports,host='127.0.0.1'):
    for port in ports:
        with socket.socket() as s:
            # Closed connections may remain in TIME_WAIT after an orderly stop.
            # REUSEADDR permits that case; an active listener still rejects bind.
            s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:s.bind((host,port))
            except OSError as e:raise RuntimeError('端口 %s 仍被占用，请检查已有服务；不启动重复进程'%port) from e
