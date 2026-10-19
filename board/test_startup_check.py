import json,tempfile,unittest
from pathlib import Path
from startup_check import external_owners,problem,describe


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'board').mkdir();(self.root/'board/deployment.json').write_text(json.dumps(dict(backend='board')))
        self.proc=self.root/'proc';self.proc.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def process(self,pid,parent,name,birth='100'):
        p=self.proc/str(pid);p.mkdir();fields=['S',str(parent)]+['0']*17+[birth]
        (p/'stat').write_text(str(pid)+' (program) '+' '.join(fields))
        (p/'cmdline').write_bytes(('/path/'+name).encode()+b'\0')
    def test_external_driver_and_slam_are_reported_without_changes(self):
        self.process(10,1,'xt16_driver');self.process(11,1,'unitree_slam')
        self.assertEqual({p['pid'] for p in external_owners(self.root,self.proc)},{10,11})
        self.assertIn('PID 10',problem(self.root,self.proc));self.assertTrue((self.proc/'10/stat').exists())
    def test_only_descendants_of_verified_owned_supervisor_are_ignored(self):
        self.process(20,1,'python3');self.process(21,20,'bash');self.process(22,21,'xt16_driver');self.process(23,1,'fastlio_mapping')
        current=self.root/'board/current.json';current.write_text(json.dumps(dict(pid=20,birth='100')))
        self.assertEqual([p['pid'] for p in external_owners(self.root,self.proc)],[23])
        current.write_text(json.dumps(dict(pid=20,birth='wrong')))
        self.assertEqual({p['pid'] for p in external_owners(self.root,self.proc)},{22,23})
    def test_missing_process_and_desktop_do_not_invent_blockers(self):
        p=self.proc/'9';p.mkdir();self.assertIsNone(problem(self.root,self.proc))
        (self.root/'board/deployment.json').unlink();self.assertEqual(external_owners(self.root,self.proc),[])
    def test_readable_errors_keep_safety_limits(self):
        self.assertIn('占用',describe('RuntimeError: External sensor/fusion owner PID 10'))
        self.assertIn('5GiB',describe('Need 5 GiB free before starting'))
