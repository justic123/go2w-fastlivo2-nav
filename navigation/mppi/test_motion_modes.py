"""No robot calls: exercise arrival ordering, cancellation and unsupported hardware."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import arrival_runner
import motion_modes as modes
import run_protected


def point(mode='obstacle'):
    return dict(name='台阶前', map_id='room', source_session='run', pose=[1., 2., 0.],
                arrival_motion=modes.action_choice(mode))


def stopped(target):
    return dict(execute=True, success=True, stationary_after_stop=True,
                guard_stop={'stop_code': 0}, target=copy.deepcopy(target))


class Adapter:
    def __init__(self, code=0):
        self.code = code
        self.requests = []

    def supported_modes(self):
        return {'obstacle', 'normal'}

    def set_mode(self, mode, *, checkpoint):
        self.requests.append((mode, checkpoint))
        return self.code

    def read_mode(self):
        return dict(mode=self.requests[-1][0], received_monotonic=time.monotonic())


class ArrivalTests(unittest.TestCase):
    def test_ack_wait_does_not_consume_feedback_window(self):
        target=point();adapter=Adapter();clock=[10.]
        def slow_ack(mode,**kwargs):
            clock[0]+=4.;adapter.requests.append((mode,{}));return 0
        adapter.set_mode=slow_ack
        with patch.object(modes.time,'monotonic',side_effect=lambda:clock[0]):
            self.assertTrue(modes.apply_after_stop(target,stopped(target),adapter=adapter,timeout_s=3.)['confirmed'])

    def test_old_point_never_loads_adapter(self):
        with patch.object(modes, 'Go2WModeAdapter') as factory:
            self.assertIsNone(modes.require_available([{'pose': [0, 0, 0]}]))
            self.assertFalse(modes.apply_after_stop({}, {})['requested'])
            factory.assert_not_called()

    def test_unverified_mode_is_rejected_before_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'current.json').write_text(json.dumps({'folder': tmp}))
            (root / 'accuracy_target.json').write_text(json.dumps(point()))
            with patch.object(modes.Go2WModeAdapter, 'supported_modes', return_value=frozenset()), patch.object(run_protected.subprocess, 'run') as child, patch.object(run_protected.subprocess, 'Popen') as guard:
                with self.assertRaisesRegex(RuntimeError, '尚未配置'):
                    run_protected.run_action(argparse.Namespace(execute=True, route=False, timeout=90), root)
                child.assert_not_called()
                guard.assert_not_called()

    def test_preview_never_calls_adapter_or_arrival_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'current.json').write_text(json.dumps({'folder': tmp}))
            (root / 'accuracy_target.json').write_text(json.dumps(point()))
            (root / 'guard.sock').touch()
            guard = Mock()
            with patch.object(run_protected, 'require_available') as capability, patch.object(run_protected, 'finish') as hook, patch.object(run_protected.subprocess, 'Popen', return_value=guard), patch.object(run_protected.subprocess, 'run', return_value=Mock(returncode=0)) as child:
                self.assertEqual(run_protected.run_action(argparse.Namespace(execute=False, route=True, timeout=90), root), 0)
                capability.assert_not_called()
                hook.assert_not_called()
                self.assertTrue(any('GO2W_ARRIVAL_ACTION_HOST=0' in call.args[0] for call in child.call_args_list))

    def test_live_hook_follows_guard_shutdown_and_owns_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'current.json').write_text(json.dumps({'folder': tmp}))
            (root / 'accuracy_target.json').write_text(json.dumps(point()))
            (root / 'guard.sock').touch()
            guard = Mock()
            def hook(*args, **kwargs):
                guard.wait.assert_called_once()
                self.assertEqual(json.loads((root / 'motion_active').read_text())['phase'], 'arrival_motion')
                raise RuntimeError('feedback failed')
            with patch.object(run_protected, 'require_available', return_value=Adapter()), patch.object(run_protected, 'finish', side_effect=hook), patch.object(run_protected.subprocess, 'Popen', return_value=guard), patch.object(run_protected.subprocess, 'run', return_value=Mock(returncode=0)):
                with self.assertRaisesRegex(RuntimeError, 'feedback failed'):
                    run_protected.run_action(argparse.Namespace(execute=True, route=True, timeout=90), root)
            self.assertFalse((root / 'motion_active').exists())

    def test_failed_or_unconfirmed_stop_never_switches(self):
        target = point()
        for change in ({'execute': False}, {'success': False}, {'stationary_after_stop': False}, {'guard_stop': {'stop_code': 1}}):
            adapter = Adapter()
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                modes.apply_after_stop(target, dict(stopped(target), **change), adapter=adapter)
            self.assertFalse(adapter.requests)

    def test_stale_target_result_never_switches(self):
        target = point()
        result = stopped(target)
        result['target']['arrival_motion'] = modes.action_choice('normal')
        adapter = Adapter()
        with self.assertRaisesRegex(RuntimeError, '不一致'):
            modes.apply_after_stop(target, result, adapter=adapter)
        self.assertFalse(adapter.requests)

    def test_ack_requires_fresh_target_feedback(self):
        target = point()
        adapter = Adapter()
        response = modes.apply_after_stop(target, stopped(target), adapter=adapter)
        self.assertTrue(response['confirmed'])
        self.assertEqual(adapter.requests[0][0], 'obstacle')
        for mode, received in [('normal', time.monotonic()), ('obstacle', time.monotonic() - 5), ('obstacle', time.monotonic() + 5)]:
            adapter = Adapter()
            adapter.read_mode = lambda: dict(mode=mode, received_monotonic=received)
            with self.subTest(mode=mode, received=received), self.assertRaisesRegex(RuntimeError, '状态确认'):
                modes.apply_after_stop(target, stopped(target), adapter=adapter, timeout_s=.01)

    def test_sdk_error_or_cancel_is_not_retried(self):
        target = point()
        adapter = Adapter(code=7004)
        with self.assertRaisesRegex(RuntimeError, '7004'):
            modes.apply_after_stop(target, stopped(target), adapter=adapter)
        self.assertEqual(len(adapter.requests), 1)
        adapter = Adapter()
        with self.assertRaisesRegex(RuntimeError, '取消'):
            modes.apply_after_stop(target, stopped(target), adapter=adapter,
                                   check=Mock(side_effect=RuntimeError('取消')))
        self.assertFalse(adapter.requests)

    def test_failed_hook_is_written_as_overall_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = point()
            path = root / 'protected-execute-1.json'
            path.write_text(json.dumps(stopped(target)))
            adapter = Adapter(code=7004)
            with patch.object(arrival_runner, 'check_context'), self.assertRaises(RuntimeError):
                arrival_runner.finish(root, target, adapter=adapter, started=time.time() - 1)
            result = json.loads(path.read_text())
            self.assertFalse(result['success'])
            self.assertTrue(result['navigation_success'])
            self.assertFalse(result['arrival_motion_result']['success'])

    def test_switch_confirmation_is_followed_by_stationary_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = point()
            path = root / 'protected-execute-1.json'
            path.write_text(json.dumps(stopped(target)))
            with patch.object(arrival_runner, 'check_context'), patch.object(arrival_runner, 'wait_stable', side_effect=RuntimeError('切换后未重新停稳')) as stable:
                with self.assertRaisesRegex(RuntimeError, '未重新停稳'):
                    arrival_runner.finish(root, target, adapter=Adapter(), started=time.time() - 1)
                stable.assert_called_once()
            result = json.loads(path.read_text())
            self.assertFalse(result['success'])
            self.assertTrue(result['arrival_motion_result']['request_result']['confirmed'])

    def test_cancel_marker_blocks_arrival_before_health_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'arrival_cancel.request').touch()
            with self.assertRaisesRegex(RuntimeError, '取消'):
                arrival_runner.check_context(root, point())

    def test_invalid_metadata_does_not_silently_disable_switch(self):
        for value in (None, True, {}, {'switch': 'false', 'mode': 'obstacle'}, {'switch': True, 'mode': 'stairs'}, {'switch': True, 'mode': 'obstacle', 'typo': 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                modes.arrival_motion({'arrival_motion': value})


if __name__ == '__main__':
    unittest.main()
