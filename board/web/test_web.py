import importlib.util,json,sys,tempfile,threading,unittest,http.client
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import common

class PolicyTests(unittest.TestCase):
    def test_pose_rejects_nonfinite_and_boolean(self):
        for p in ([0,0,float('nan')],[True,0,0],[0,0],['1',0,0]):
            with self.assertRaises(ValueError):common.pose(p)
    def test_angle_normalization(self):
        self.assertAlmostEqual(common.pose([1,2,7])[2],7-2*3.141592653589793)
    def test_name_is_data(self):
        self.assertEqual(common.name('目标; $(echo hi)'),'目标; $(echo hi)')
        with self.assertRaises(ValueError):common.name('x\n')
    def test_fresh_rejects_future(self):
        with patch('common.time.time',return_value=100):
            self.assertFalse(common.fresh({'ready':True,'updated':101}))
            self.assertFalse(common.fresh({'ready':True,'updated':90}))
            self.assertTrue(common.fresh({'ready':True,'updated':99}))

class CameraTests(unittest.TestCase):
    def test_disabled_backend_never_exposes_cached_frames(self):
        from camera_policy import status,enabled
        self.assertTrue(enabled({}))
        self.assertTrue(enabled(dict(fusion_backend='fastlivo2')))
        d=status(dict(fusion_backend='fastlio2'),dict(updated=100,phase='ready'),'new')
        self.assertFalse(d['enabled']);self.assertEqual(d['updated'],0)
        self.assertEqual(d['phase'],'disabled');self.assertEqual(d['session'],'new')
        self.assertTrue(status({},dict(updated=100),'old')['enabled'])
    def test_restart_after_master_session_changes(self):
        from camera_policy import reconnect_needed as check
        self.assertTrue(check('new','old',0,False,True,0))
        self.assertTrue(check('same','same',9,False,True,7))
        self.assertFalse(check('same','same',4,False,True,7))
        self.assertFalse(check('same','same',9,False,False,7))
        self.assertTrue(check('same','same',9,True,False,7))

class RestartTests(unittest.TestCase):
    def test_worker_failure_message_is_visible_and_bounded(self):
        import server
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'log';p.write_text('details\n操作未完成：传感器被其他建图程序占用\n')
            self.assertEqual(server.failure_message(p),'传感器被其他建图程序占用')
            p.write_text('操作未完成：'+'x'*2000+'\n')
            self.assertEqual(len(server.failure_message(p)),1000)
            p.unlink();self.assertIn('操作失败',server.failure_message(p))
    def test_stopped_mission_requires_explicit_matching_restart_token(self):
        import action
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'demo').mkdir()
            with patch.object(action,'ROOT',root),patch.object(action.c,'state',return_value={'map_id':'m'}),patch.object(action.mission,'resume_status',return_value={'available':True,'token':'current'}),patch.object(action.mission,'execute') as execute:
                req=dict(action='route-execute',map_id='m',confirm_motion=True)
                for token in (None,'stale'):
                    with self.assertRaisesRegex(ValueError,'已有停止任务'):action.run(dict(req,restart_token=token))
                execute.assert_not_called()
                action.run(dict(req,restart_token='current'));execute.assert_called_once()

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.patch=patch.multiple(common,STATE=Path(cls.temp.name),CACHE=Path(cls.temp.name)/'cache');cls.patch.start()
        import server
        cls.s=server;cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.port=cls.http.server_address[1]
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.patch.stop();cls.temp.cleanup()
    def request(self,method,path,data=None,cookie=None,origin=True,host='localhost'):
        c=http.client.HTTPConnection('127.0.0.1',self.port);headers={'Host':host+':'+str(self.port),'Content-Type':'application/json'}
        if origin:headers['Origin']='http://'+headers['Host']
        if cookie:headers['Cookie']=cookie
        c.request(method,path,json.dumps(data) if data is not None else None,headers);r=c.getresponse();body=r.read();h=dict(r.getheaders());code=r.status;c.close();return code,h,body
    def login(self):
        code,h,_=self.request('POST','/api/login',{'key':self.s.KEY});self.assertEqual(code,200);return h['Set-Cookie'].split(';')[0]
    def test_status_requires_auth(self):self.assertEqual(self.request('GET','/api/status')[0],401)
    def test_csrf_rejected(self):self.assertEqual(self.request('POST','/api/stop',{},cookie=self.login(),origin=False)[0],403)
    def test_dns_host_rejected(self):self.assertEqual(self.request('GET','/',host='evil.example')[0],403)
    def test_motion_needs_explicit_confirmation(self):self.assertEqual(self.request('POST','/api/action',{'action':'navigate'},cookie=self.login())[0],400)
    def test_resume_needs_motion_confirmation(self):self.assertEqual(self.request('POST','/api/action',{'action':'route-resume'},cookie=self.login())[0],400)
    def test_resume_uses_motion_lease(self):
        self.assertTrue(self.s.heartbeat_lost(dict(action='route-resume',phase='running',owner='a'),{'a':{'seen':90}},100))
    def test_arbitrary_command_rejected(self):self.assertEqual(self.request('POST','/api/action',{'action':'shell','cmd':'echo unsafe'},cookie=self.login())[0],400)
    def test_arbitrary_path_rejected(self):self.assertEqual(self.request('GET','/data/../../etc/passwd',cookie=self.login())[0],404)
    def test_old_page_after_stop_cannot_enqueue(self):
        cookie=self.login()
        code,_,_=self.request('POST','/api/action',{'action':'load-map','name':'x','generation':-1},cookie=cookie)
        self.assertEqual(code,400)
    def test_motion_lease(self):
        j=dict(action='navigate',phase='running',owner='a')
        self.assertTrue(self.s.heartbeat_lost(j,{'a':{'seen':90}},100))
        self.assertFalse(self.s.heartbeat_lost(j,{'a':{'seen':99}},100))
        self.assertFalse(self.s.heartbeat_lost(dict(j,action='restore'),{},100))
        self.assertFalse(self.s.heartbeat_lost(dict(j,phase='done'),{},100))
    def test_heartbeat(self):self.assertEqual(self.request('POST','/api/heartbeat',{},cookie=self.login())[0],200)
    def test_stop_works_independent_of_worker(self):
        with patch.object(self.s,'stop_action') as stop:
            self.assertEqual(self.request('POST','/api/stop',{},cookie=self.login())[0],202);stop.assert_called_once()

if __name__=='__main__':unittest.main()
