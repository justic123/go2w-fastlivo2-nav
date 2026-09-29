"""Bounded FIFO for sensor packets. Overflow is fatal, never drop old IMU samples."""
import queue
import threading

class SensorBuffer:
    def __init__(self, max_packets=2200, max_bytes=128 * 1024 * 1024):
        self.queue = queue.Queue(max_packets)
        self.max_bytes = max_bytes
        self.bytes = 0
        self.lock = threading.Lock()

    def put_nowait(self, item):
        with self.lock:
            size = len(item[1])
            if self.bytes + size > self.max_bytes:
                raise queue.Full('Sensor buffer byte limit exceeded')
            self.queue.put_nowait(item)
            self.bytes += size

    def get(self, timeout=None):
        item = self.queue.get(timeout=timeout)
        with self.lock:
            self.bytes -= len(item[1])
        return item

    def snapshot(self):
        with self.lock:
            return dict(queue=self.queue.qsize(), queue_bytes=self.bytes)
