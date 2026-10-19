"""The portable application must not resurrect deleted maps or carry stale manifests."""
import pathlib,shutil,subprocess,sys,tarfile,tempfile,unittest

class Packaging(unittest.TestCase):
 def test_code_archive_excludes_runtime_data_and_has_one_manifest(self):
  with tempfile.TemporaryDirectory() as temp:
   root=pathlib.Path(temp);(root/'board').mkdir()
   shutil.copy2(pathlib.Path(__file__).with_name('stage_deployment.py'),root/'board/stage_deployment.py')
   names=('desktop/monitor.py','desktop/ros1_view_source.py','desktop/backlog_policy.py','migration/select_speed.py','migration/test_select_speed.py','navigation/mppi/maps-trash/removed/metadata.json','navigation/mppi/map-save-incomplete/metadata.json','navigation/mppi/maps/active/metadata.json','board/source-manifest.json','board/web-state/key.json')
   for name in names:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
   subprocess.run(['git','init','-q',str(root)],check=True)
   subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-qm','fixture'],cwd=root,check=True)
   archive=root/'code.tar.gz'
   subprocess.run([sys.executable,str(root/'board/stage_deployment.py'),str(archive),'--code-only'],check=True,capture_output=True)
   with tarfile.open(archive) as tar:items=tar.getnames()
   self.assertEqual(items.count('board/source-manifest.json'),1)
   self.assertFalse(any(any(x in n for x in ('maps-trash','map-save-','/maps/','web-state')) for n in items))
   self.assertIn('desktop/monitor.py',items)

if __name__=='__main__':unittest.main()
