import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import status_store as store
from health_policy import check_context, ContextError


class StatusStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'run'
        self.root.mkdir()
        self.base = Path(self.temp.name) / 'ram'
        self.mock = patch.object(store, '_base', return_value=self.base)
        self.mock.start()
        self.writers = []

    def tearDown(self):
        for writer in self.writers:
            writer.close()
            if writer.thread:
                writer.thread.join(1)
        self.mock.stop()
        self.temp.cleanup()

    def writer(self, name='input'):
        writer = store.StatusWriter(self.root, name)
        self.writers.append(writer)
        return writer

    def test_symlink_remains_and_latest_health_is_exact(self):
        store.prepare(self.root)
        writer = self.writer()
        for data in [dict(ready=True, updated=1, source_ages={'pose': .7}),
                     dict(ready=False, updated=2, fault='clock reset')]:
            writer.publish(data)
            self.assertEqual(json.loads((self.root/'input.json').read_text()), data)
            self.assertTrue((self.root/'input.json').is_symlink())

    def test_blocked_archive_cannot_block_publisher_or_queue_updates(self):
        store.prepare(self.root)
        entered, release = threading.Event(), threading.Event()
        atomic = store._atomic
        def blocked(path, text):
            if path.parent.name == 'health-archive':
                entered.set()
                release.wait(5)
            atomic(path, text)
        with patch.object(store, '_atomic', side_effect=blocked):
            writer = self.writer()
            writer.publish(dict(ready=True, updated=1))
            self.assertTrue(entered.wait(1))
            try:
                begin = time.monotonic()
                for i in range(200):
                    writer.publish(dict(ready=False, updated=2+i))
                self.assertLess(time.monotonic()-begin, 1.)
                self.assertEqual(json.loads((self.root/'input.json').read_text())['updated'], 201)
                self.assertEqual(json.loads(writer.latest)['updated'], 201)
            finally:
                release.set()
                writer.close()
                writer.thread.join(1)

    def test_missing_ram_store_never_reads_ready_archive(self):
        store.prepare(self.root)
        (self.root/'health-archive/input.json').write_text('{"ready":true}')
        (self.base/'run').rmdir()
        with self.assertRaises(ValueError):self.writer()
        self.assertFalse((self.root/'input.json').exists())

    def test_missing_ram_during_runtime_fails_without_disk_fallback(self):
        store.prepare(self.root)
        writer = self.writer()
        (self.base/'run').rmdir()
        with self.assertRaises(OSError):writer.publish(dict(ready=True))
        self.assertTrue((self.root/'input.json').is_symlink())

    def test_wrong_link_and_foreign_store_are_rejected(self):
        store.prepare(self.root)
        link = self.root/'input.json'
        link.unlink();link.symlink_to(self.root/'foreign.json')
        with self.assertRaises(ValueError):self.writer()
        (self.root/'health-store.json').write_text(json.dumps(dict(version=1,directory='/tmp/foreign')))
        with self.assertRaises(ValueError):self.writer('runtime')

    def test_bounded_payload_and_finite_numbers(self):
        store.prepare(self.root)
        writer = self.writer()
        for data in [dict(error='x'*store.MAX_BYTES), dict(age=float('nan'))]:
            with self.assertRaises(ValueError):writer.publish(data)
        self.assertFalse((self.root/'input.json').exists())

    def test_finalize_preserves_history_and_does_not_invent_missing_health(self):
        store.prepare(self.root)
        writer = self.writer('runtime')
        data = dict(phase='stopped', updated=1)
        writer.publish(data);writer.close();writer.thread.join(1)
        store.finalize(self.root)
        self.assertEqual(json.loads((self.root/'runtime.json').read_text()), data)
        self.assertFalse((self.root/'runtime.json').is_symlink())
        self.assertFalse((self.root/'input.json').exists())
        self.assertFalse((self.base/'run').exists())
        store.finalize(self.root)  # Repeated stop remains safe.

    def test_legacy_desktop_path_still_works(self):
        writer = self.writer()
        writer.publish(dict(ready=False, updated=1))
        self.assertFalse((self.root/'input.json').is_symlink())
        self.assertIsNone(writer.thread)

    def test_existing_action_gate_uses_ram_and_rejects_age_fault_and_expiry(self):
        store.prepare(self.root)
        docs = dict(input=dict(ready=True, updated=100, session='s', pose_age_s=.2, cloud_age_s=.4),
                    localization=dict(ready=True, updated=100, map_id='m', source_session='s'),
                    lifecycle=dict(ready=True, updated=100), runtime=dict(phase='running', updated=100))
        writers = {name:self.writer(name) for name in store.NAMES}
        for name, data in docs.items():writers[name].publish(data)
        target = dict(map_id='m', source_session='s')
        check_context(self.root, target, .6, now=100)
        for change in [dict(cloud_age_s=.600001), dict(ready=False), dict(updated=98), dict(session='old')]:
            writers['input'].publish(dict(docs['input'], **change))
            with self.assertRaises(ContextError):check_context(self.root, target, .6, now=100)


if __name__ == '__main__':unittest.main()
