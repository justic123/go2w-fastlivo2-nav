import queue
import unittest
from backlog_policy import BacklogGuard
from transport_buffer import SensorBuffer

class TransportTests(unittest.TestCase):
    def test_159_second_stall_preserves_all_samples_and_order(self):
        q = SensorBuffer()
        # 500 Hz IMU plus 10 Hz cloud/JPEG over a 1.59 s blocked send.
        expected = [(i % 3, str(i).encode(), 0.) for i in range(827)]
        for item in expected:
            q.put_nowait(item)
        guard = BacklogGuard()
        self.assertEqual(guard.check(1.59, 1.59), 'catching_up')
        self.assertEqual([q.get(0) for _ in expected], expected)
        self.assertEqual(guard.check(.01, 1.7), 'live')
        self.assertEqual(q.snapshot(), {'queue': 0, 'queue_bytes': 0})

    def test_byte_limit_fails_without_evicting_existing_samples(self):
        q = SensorBuffer(max_packets=10, max_bytes=5)
        first = (0, b'1234', 0.)
        q.put_nowait(first)
        with self.assertRaises(queue.Full):
            q.put_nowait((1, b'56', 0.))
        self.assertEqual(q.get(0), first)
        q.put_nowait((0, b'12345', 0.))
        self.assertEqual(q.snapshot()['queue_bytes'], 5)

    def test_packet_limit_fails_without_evicting(self):
        q = SensorBuffer(max_packets=1)
        q.put_nowait((0, b'a', 0.))
        with self.assertRaises(queue.Full):
            q.put_nowait((0, b'b', 0.))
        self.assertEqual(q.get(0)[1], b'a')

    def test_old_or_persistently_late_data_still_fails(self):
        with self.assertRaises(RuntimeError):
            BacklogGuard().check(3., 3.)
        guard = BacklogGuard()
        guard.check(1.6, 1.6)
        with self.assertRaises(RuntimeError):
            guard.check(1.1, 6.7)

if __name__ == '__main__':
    unittest.main()
