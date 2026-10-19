"""Verify deployment separation and visualization cannot forward velocity commands."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lifecycle'))
import compute_backend as backend
import view_transport as transport
from initialization import StationaryInitialization


class BackendTests(unittest.TestCase):
    def test_timing_before_first_pose_never_reports_initialized(self):
        init=StationaryInitialization()
        self.assertFalse(init.observe(dict(ready=True,updated=100,pose=None,odom_count=0),100,1))
        self.assertFalse(init.observe(dict(ready=True,updated=100,pose=[0,0,0],odom_count=1),100,2))
        self.assertFalse(init.observe(dict(ready=True,updated=104,pose=[0,0,0],odom_count=1),104,6))
        self.assertTrue(init.observe(dict(ready=True,updated=105,pose=[.001,0,0],odom_count=41),105,7))

    def test_movement_and_stale_input_invalidate_initialization(self):
        init=StationaryInitialization()
        h=dict(ready=True,updated=100,pose=[0,0,0],odom_count=1)
        init.observe(h,100,1)
        self.assertFalse(init.observe(h,103,4))
        h.update(updated=104,odom_count=15)
        self.assertFalse(init.observe(h,104,5))
        h.update(pose=[.16,0,0])
        with self.assertRaisesRegex(RuntimeError,'15cm'):init.observe(h,104,5.1)

    def test_missing_marker_keeps_desktop(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            self.assertEqual(backend.control(p),p/'desktop/control.py')
            self.assertEqual(backend.guard_command(False,p)[0],'ssh')

    def test_installed_board_has_no_ssh_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'board').mkdir()
            (p/'board/deployment.json').write_text(json.dumps(dict(backend='board')))
            self.assertEqual(backend.control(p),p/'board/control.py')
            command=backend.guard_command(False,p)
            self.assertNotIn('ssh',command);self.assertEqual(command[-1],'preview')
            self.assertEqual(backend.guard_command(True,p)[-1],'execute')

    def test_view_rejects_velocity_and_direct_goal(self):
        for topic in ('/cmd_vel','/mppi/cmd_vel_smoothed','/goal_pose'):
            with self.subTest(topic=topic):
                a,b=socket.socketpair()
                try:
                    transport.send(a,topic,b'123')
                    with self.assertRaisesRegex(ValueError,'not allowed'):
                        transport.receive(b,transport.INPUTS)
                finally:a.close();b.close()

    def test_display_goal_is_data_only(self):
        a,b=socket.socketpair()
        try:
            transport.send(a,'/demo/goal_pose',b'goal-cdr')
            self.assertEqual(transport.receive(b,transport.INPUTS),('/demo/goal_pose',b'goal-cdr'))
        finally:a.close();b.close()


if __name__=='__main__':unittest.main()
