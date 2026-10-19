const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/static/app.js','utf8');
const pan=source.slice(source.indexOf('function panCloud('),source.indexOf("$('cloudPan').onclick="));
const env={Math,center:[0,0,0],radius:10,yaw:0,pitch:Math.PI/2,$:()=>({getBoundingClientRect:()=>({height:400})})};vm.createContext(env);vm.runInContext(pan,env);
vm.runInContext('panCloud(20,0)',env);assert(Math.abs(env.center[0]+1)<1e-10);assert(Math.abs(env.center[1])<1e-10);
vm.runInContext('panCloud(0,20,[0,0,0])',env);assert(Math.abs(env.center[2]-1)<1e-10);
// A queued request must not resolve as successful before the server finishes.
const act=source.slice(source.indexOf('async function act('),source.indexOf('async function createPoint('));
const state={generation:1,state:{map_id:'m'}};
const a={connected:true,lastStatus:Date.now(),Date,busy:false,pendingAction:null,state,api:async()=>({job:'job123'}),toast:()=>{},poll:async()=>{}};vm.createContext(a);vm.runInContext(act,a);
(async()=>{let settled=false;const result=vm.runInContext("act('route-set',{names:['A','B']})",a).then(v=>{settled=true;return v});await new Promise(setImmediate);assert.equal(settled,false);assert.equal(a.pendingAction.id,'job123');a.pendingAction.resolve(false);assert.equal(await result,false);console.log('UI: pan transform and asynchronous save tests passed');})().catch(e=>{console.error(e);process.exitCode=1});

const notice=source.slice(source.indexOf('function recentJobFailure('),source.indexOf('function update('));
const noticeEnv={};vm.createContext(noticeEnv);vm.runInContext(notice,noticeEnv);
assert.equal(noticeEnv.recentJobFailure({now:100,job:{phase:'failed',ended:99}}),true);
assert.equal(noticeEnv.recentJobFailure({now:100,job:{phase:'failed',ended:1}}),false);
assert.equal(noticeEnv.recentJobFailure({now:100,job:{phase:'failed',ended:101}}),false);
assert.equal(noticeEnv.recentJobFailure({now:100,job:{phase:'done',ended:99}}),false);

// Lost localization must not be confused with a broken record button.
const recordCode=source.slice(source.indexOf('function recordAvailability('),source.indexOf('function recentJobFailure('));
const controls={record:{},recordNote:{},recordLocate:{}};
const re={$:id=>controls[id]};vm.createContext(re);vm.runInContext(recordCode,re);
const healthy={state:{phase:'navigation',map_id:'m'},fusion_ready:true,nav_ready:true,localized:true,ready:true};
re.updateRecord(healthy,false);assert.equal(controls.record.disabled,false);assert.equal(controls.recordLocate.hidden,true);
const failed={...healthy,state:{phase:'recovery_failed',map_id:'m'},localized:false,ready:false};
re.updateRecord(failed,false);assert.equal(controls.record.disabled,true);assert.equal(controls.recordLocate.hidden,false);assert.match(controls.recordNote.textContent,/旧地图重定位失败/);
re.updateRecord(healthy,false,false);assert.equal(controls.record.disabled,true);assert.match(controls.recordNote.textContent,/连接已中断/);
re.updateRecord(healthy,true);assert.equal(controls.record.disabled,true);assert.equal(controls.recordLocate.hidden,true);
assert.match(re.recordAvailability({...healthy,state:{phase:'mapping'}},false).reason,/结束并保存/);
assert.match(re.recordAvailability({...healthy,state:{}},false).reason,/尚未选择地图/);
assert.match(re.recordAvailability({...healthy,fusion_ready:false},false).reason,/融合输入未就绪/);
assert.match(re.recordAvailability({...healthy,nav_ready:false},false).reason,/导航输入未就绪/);
re.updateRecord(healthy,false);assert.equal(controls.record.disabled,false);assert.equal(controls.recordLocate.hidden,true);
console.log('UI: record gating, recovery guidance and disconnect/recovery tests passed');

const mapGate=source.slice(source.indexOf('function mapButtons('),source.indexOf('function trashOptions('));
const mb={maps:{value:'m'},deleteMap:{},restoreMap:{},trashMaps:{value:'trash1'}};
const me={busy:false,$:id=>mb[id]};vm.createContext(me);vm.runInContext(mapGate,me);
me.mapButtons({state:{phase:'navigation'},map_versions:{m:'v'}});assert.equal(mb.deleteMap.disabled,false);assert.equal(mb.restoreMap.disabled,false);
me.mapButtons({state:{phase:'mapping'},map_versions:{m:'v'}});assert.equal(mb.deleteMap.disabled,true);assert.equal(mb.restoreMap.disabled,true);
me.mapButtons({state:{phase:'idle'},map_versions:{}});assert.equal(mb.deleteMap.disabled,true);
me.busy=true;me.mapButtons({state:{phase:'idle'},map_versions:{m:'v'}});assert.equal(mb.deleteMap.disabled,true);
console.log('UI: map deletion disabled during mapping, missing selection and active jobs');

// A stale page may not submit an action even if an old control is still visible.
const offline={connected:false,lastStatus:Date.now(),Date,toast:()=>{},api:()=>{throw Error('must not send')}};vm.createContext(offline);vm.runInContext(act,offline);
vm.runInContext("act('navigate')",offline).then(v=>assert.equal(v,false)).catch(e=>{console.error(e);process.exitCode=1});
const disconnectedCode=source.slice(source.indexOf('function markDisconnected('),source.indexOf('setInterval(()=>{if(!document.hidden'));
const dc=new Map(),de={connected:true,state:{},busy:false,$:id=>{if(!dc.has(id))dc.set(id,{});return dc.get(id)},updateRecord:()=>{},draw:()=>{}};vm.createContext(de);vm.runInContext(disconnectedCode,de);de.markDisconnected();assert.equal(de.connected,false);
for(const id of ['record','navigate','start','deleteMap','saveRoute'])assert.equal(dc.get(id).disabled,true);
assert.match(dc.get('badges').textContent,/过期/);assert.match(dc.get('cameraAge').textContent,/历史/);
console.log('UI: disconnected controls and stale-action submission blocked');

const project=source.slice(source.indexOf('function projectCloud('),source.indexOf('function drawCloudOverlay('));
const pe={Math,Number,Date,center:[0,0,0],radius:5,yaw:0,pitch:Math.PI/2,connected:true,lastStatus:Date.now(),cloudFrame:'map',cloudMap:'m'};vm.createContext(pe);vm.runInContext(project,pe);
assert.deepEqual(Array.from(pe.projectCloud([0,0,0],800,400)),[400,200]);assert.deepEqual(Array.from(pe.projectCloud([1,0,0],800,400)),[440,200]);assert(Math.abs(pe.projectCloud([0,0,1],800,400)[1]-160)<1e-8);
const live={state:{map_id:'m'},now:100,nav_ready:true,localized:true,input:{session:'s'},view:{session:'s',robot:{frame:'map',updated:100,pose:[1,2,3,0]}}};
assert.deepEqual(pe.freshCloudRobot(live),[1,2,3,0]);assert.equal(pe.freshCloudRobot({...live,localized:false}),null);assert.equal(pe.freshCloudRobot({...live,now:103}),null);assert.equal(pe.freshCloudRobot({...live,input:{session:'other'}}),null);
console.log('UI: 3D projection and stale/session-mismatched robot markers tested');
const ageCode=source.slice(source.indexOf('function navigationAgeReason('),source.indexOf('function routeBlockReason('));
const ae={Number};vm.createContext(ae);vm.runInContext(ageCode,ae);
assert.equal(ae.navigationAgeReason({input:{pose_age_s:.2,cloud_age_s:.4}}),'');assert.match(ae.navigationAgeReason({input:{pose_age_s:.2,cloud_age_s:.66}}),/点云/);assert.match(ae.navigationAgeReason({input:{pose_age_s:.2,cloud_age_s:.4},speed:{active:{name:'hall08'}}}),/0.30/);
for(const key of ['pose_age_s','cloud_age_s']){
 const status={input:{pose_age_s:.2,cloud_age_s:.2},speed:{active:{name:'corridor04'}}};
 for(const age of [.5,.55,.6]){status.input[key]=age;assert.equal(ae.navigationAgeReason(status),'')}
 status.input[key]=.600001;assert.match(ae.navigationAgeReason(status),/0.60/);
}
assert.equal(pe.freshCloudRobot({...live,state:{map_id:'different'}}),null);
console.log('UI: navigation age limits and 3D map identity tested');

const anchorCode=source.slice(source.indexOf('function anchorAvailability('),source.indexOf('function updateAnchors('));
const anchorEnv={};vm.createContext(anchorEnv);vm.runInContext(anchorCode,anchorEnv);
const anchorsReady={state:{map_id:'m',phase:'navigation'},ready:true,anchors:{A:{version:'v'}}};
assert.equal(anchorEnv.anchorAvailability(anchorsReady,false).save,true);assert.equal(anchorEnv.anchorAvailability(anchorsReady,false).use,true);
assert.equal(anchorEnv.anchorAvailability({...anchorsReady,ready:false,state:{map_id:'m',phase:'recovery_failed'}},false).use,true);
assert.equal(anchorEnv.anchorAvailability({...anchorsReady,ready:false},false).save,false);
assert.equal(anchorEnv.anchorAvailability({...anchorsReady,anchors:{}},false).use,false);
for(const phase of ['mapping','starting','validating_map','recovering'])assert.equal(anchorEnv.anchorAvailability({...anchorsReady,state:{map_id:'m',phase}},false).use,false);
assert.equal(anchorEnv.anchorAvailability(anchorsReady,true).use,false);assert.equal(anchorEnv.anchorAvailability(anchorsReady,false,false).use,false);
console.log('UI: fixed anchors remain available for recovery, with busy/offline/map gates');

const resumeCode=source.slice(source.indexOf('function resumeAvailability('),source.indexOf('function updateResume('));
const resumeEnv={navigationAgeReason:ae.navigationAgeReason};vm.createContext(resumeEnv);vm.runInContext(resumeCode,resumeEnv);
const rs={ready:true,now:100,state:{},resume:{available:true,token:'a',completed:1,total:2,remaining:['B']},input:{pose_age_s:.2,cloud_age_s:.3}};
assert.equal(resumeEnv.resumeAvailability(rs,false,false).preview,true);assert.equal(resumeEnv.resumeAvailability(rs,false,false).execute,false);
rs.state.route_resume_preview={success:true,resume_token:'a',created:90};assert.equal(resumeEnv.resumeAvailability(rs,false,false).execute,true);
for(const [s,b,d,o] of [[rs,true,false,true],[rs,false,true,true],[rs,false,false,false],[{...rs,ready:false},false,false,true],[{...rs,now:200},false,false,true],[{...rs,resume:{...rs.resume,token:'changed'}},false,false,true],[{...rs,input:{pose_age_s:.2,cloud_age_s:.7}},false,false,true]])assert.equal(resumeEnv.resumeAvailability(s,b,d,o).execute,false);
console.log('UI: resume preview, checkpoint token, expiry, dirty state, disconnect and freshness gates tested');
assert.equal(resumeEnv.resumeAvailability({...rs,ready:false},false,false).preview,true);
assert.equal(resumeEnv.resumeAvailability({...rs,input:{pose_age_s:.2,cloud_age_s:.7}},false,false).preview,true);
const planCode=source.slice(source.indexOf('function displayPlans('),source.indexOf('function draw(){'));
const planEnv={};vm.createContext(planEnv);vm.runInContext(planCode,planEnv);
const ps={now:100,state:{map_id:'m',session:'s',route_resume_preview:{success:true,map_id:'m',source_session:'s',resume_token:'token',created:99,segments:[{path:[[0,0],[1,1]]}]}},resume:{token:'token'},view:{route_plan:{frame:'map',updated:99,points:[[4,4],[5,5]]}}};
assert.equal(JSON.stringify(planEnv.displayPlans(ps,'map')[0].points),'[[0,0],[1,1]]');assert.equal(JSON.stringify(planEnv.displayPlans({...ps,resume:{token:'changed'}},'map')[0].points),'[[4,4],[5,5]]');
console.log('UI: continuation displays only the remaining validated path');
