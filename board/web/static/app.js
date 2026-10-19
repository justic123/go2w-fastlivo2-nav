'use strict';
const $=id=>document.getElementById(id), phaseNames={idle:'待开始',starting:'初始化中',start_failed:'扫图启动未完成',mapping:'扫图中',validating_map:'保存并验证',navigation:'地图已保存',map_selected:'待重定位',recovering:'正在重定位',recovery_failed:'重定位未通过'};
let state=null,connected=false,busy=false,route=[],routeDirty=false,routeKey='',pick=null,startDrag=null,dragMoved=false,grid=null,gridImage=null,localImage=null,localMeta=null,gridTag='',gridOwner=null,localTag='',images={},tab='2d',pan=[0,0],scale=1,fitKey='',lastStatus=0,assetBusy=false,camURL='',camTag='',cameraBusy=false,modeKey='',modeDirty=false,pendingAction=null,pollBusy=false,uiMap=null,cloudPan=false,toastTimer;
const canvas=$('map2d'),ctx=canvas.getContext('2d');
function toast(s){$('toast').textContent=s;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5000)}
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',signal:AbortSignal.timeout(8000),headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let d=await r.json();if(!r.ok){if(r.status===401){connected=false;if(pendingAction){pendingAction.resolve(false);pendingAction=null;busy=false;toast('连接会话失效，请重新登录并核对保存结果')}if(!$('login').open)$('login').showModal()}throw Error(d.error||'连接失败')}return d}
function ask(title,text){$('confirmTitle').textContent=title;$('confirmText').textContent=text;$('confirm').showModal();return new Promise(resolve=>{$('confirm').addEventListener('close',()=>resolve($('confirm').returnValue==='yes'),{once:true})})}
async function act(action,extra={}){
 if(!connected||Date.now()-lastStatus>3500){toast('连接或状态已过期，等待刷新后再操作');return false}
 if(busy||pendingAction){toast('请等待当前操作完成');return false}
 busy=true;
 try{const d=await api('action',{action,generation:state?.generation,map_id:state?.state.map_id,...extra});
  toast('操作已提交，等待后台完成');
  const result=new Promise(resolve=>{pendingAction={id:d.job,action,extra,resolve}});
  await poll();return await result;
 }catch(e){busy=false;toast(e.message);return false}
}
async function createPoint(action,extra={}){
 if(action==='record'){const gate=recordAvailability(state,busy,connected&&Date.now()-lastStatus<3500);if(!gate.enabled)return toast(gate.reason)}
 const n=extra.name??$('pointName').value.trim();if(!n)return toast('请填写新点名称');
 const map=extra.map_id??state?.state.map_id,mode=extra.arrival_motion??$('newMode').value;
 if(map!==state?.state.map_id)return toast('地图已变化，请重新添加点');
 const old=state?.state.points?.[n];let replacement=null;
 if(old){replacement=state.point_fingerprints?.[n];if(!replacement)return toast('请刷新页面后重试');if(!await ask('覆盖已有目标 · '+n,'会替换该点的位置、朝向与到点动作；使用该点的路线需要重新预演。'))return}
 if(await act(action,{...extra,name:n,map_id:map,arrival_motion:mode,manual_handoff:extra.manual_handoff??$('newHandoff').checked,replace_fingerprint:replacement})){
  $('targets').value=n;$('routeTarget').value=n;modeDirty=false;syncMode(true);$('pointName').value='';toast('目标已保存并选中：'+n);draw();
 }
}
$('loginForm').onsubmit=async e=>{e.preventDefault();try{await api('login',{key:$('accessKey').value});$('accessKey').value='';$('login').close();connected=true;await api('heartbeat',{});await poll()}catch(e){$('loginError').textContent=e.message}};
$('login').addEventListener('cancel',e=>e.preventDefault());
$('stop').onclick=async()=>{try{await api('stop',{});toast('已请求停车；请确认实机停稳，必要时遥控接管')}catch(e){toast('停车请求未送达，请立即遥控接管：'+e.message)}};
$('start').onclick=async()=>{if(await ask('开始新的扫图？','机器狗需站稳静止。当前地图和目标会备份，新会话从当前位置初始化。初始化成功后再遥控移动。'))act('start',{stationary:true})};
$('finish').onclick=async()=>{if(await ask('结束扫图并保存？','请先停稳。保存地图后融合仍会运行，用于实时定位。'))act('finish',{stationary:true})};
$('load').onclick=()=>act('load-map',{name:$('maps').value});
$('deleteMap').onclick=async()=>{
 const n=$('maps').value,version=state?.map_versions?.[n];if(!version)return toast('地图列表已变化，请刷新后重试');
 if(await ask('删除地图 · '+n,'地图及其目标点将移入回收站，可恢复。若为当前地图，将停止导航服务并清除当前预演；融合不会重新初始化。'))await act('delete-map',{name:n,map_version:version,confirm_delete:true});
};
$('restoreMap').onclick=()=>act('restore-map',{trash_id:$('trashMaps').value});
function mapButtons(s){
 const locked=busy||['mapping','starting','validating_map','recovering'].includes(s?.state.phase);
 $('deleteMap').disabled=locked||!s?.map_versions?.[$('maps').value];
 $('restoreMap').disabled=locked||!$('trashMaps').value;
}
function trashOptions(s){
 const el=$('trashMaps'),items=s.trash||[],sig=JSON.stringify(items),old=el.value;
 if(el.dataset.sig!==sig){el.replaceChildren();for(const t of items){const o=document.createElement('option');o.value=t.id;o.textContent=t.map_id+' · '+new Date(t.deleted_at*1000).toLocaleString();el.append(o)}el.dataset.sig=sig;if(items.some(t=>t.id===old))el.value=old}
 mapButtons(s);
}
$('trashMaps').onchange=()=>mapButtons(state);
$('restore').onclick=async()=>{if(await ask('自动恢复旧地图定位','请保持静止。程序会重新初始化并匹配旧图，不会发送运动指令；存在匹配歧义时请使用手动标记。'))act('restore',{stationary:true})};
function anchorAvailability(s,isBusy,isConnected=true){
 const locked=!isConnected||!s||isBusy||!s.state?.map_id||['mapping','starting','validating_map','recovering'].includes(s.state?.phase);
 return {save:!locked&&s.ready,use:!locked&&Object.keys(s.anchors||{}).length>0};
}
function updateAnchors(s){
 const names=Object.keys(s.anchors||{});options('anchors',names);
 const gate=anchorAvailability(s,busy,connected);
 $('saveAnchor').disabled=!gate.save;$('useAnchor').disabled=!gate.use;$('deleteAnchor').disabled=!gate.use;
 const a=s.anchors?.[$('anchors').value];
 $('anchorNote').textContent=s.anchor_error||(!names.length?'本地图还没有固定定位点。先完成定位并核对位置、朝向，再保存地面标记。':a?'已保存：'+a.name+'；只用于恢复定位，不会自动导航。请使用相同站姿和机身参考点。':'请选择固定定位点。');
}
$('anchors').onchange=()=>updateAnchors(state);
$('saveAnchor').onclick=async()=>{
 const n=$('anchorName').value.trim(),map=state?.state.map_id;
 if(!n)return toast('请填写固定定位点名称');
 if(state?.anchors?.[n])return toast('固定点已存在，请换名或先删除旧点');
 if(await ask('保存固定定位点 · '+n,'请确认地图上的位置和机头方向正确，已在地面标好同一机身参考点和朝向，并保持正常站立、静止。采样约3.5秒，不改导航目标。')){
  if(await act('anchor-save',{name:n,map_id:map,stationary:true})){$('anchorName').value='';await poll();$('anchors').value=n;updateAnchors(state)}
 }
};
$('useAnchor').onclick=async()=>{
 const n=$('anchors').value,a=state?.anchors?.[n],map=state?.state.map_id;if(!a)return;
 if(await ask('固定位置重定位 · '+n,'请确认机器狗已放回这个地面标记：同一机身参考点对齐，机头沿原朝向，正常站立并保持静止。程序会用雷达确认匹配；失败将保留地图并禁止导航。不会发送运动指令。'))await act('anchor-use',{name:n,map_id:map,anchor_version:a.version,stationary:true,confirm_placement:true});
};
$('deleteAnchor').onclick=async()=>{
 const n=$('anchors').value,a=state?.anchors?.[n],map=state?.state.map_id;if(!a)return;
 if(await ask('删除固定定位点 · '+n,'只删除此定位参考；地图、导航目标和路线保留。下次需要重新标定。'))await act('anchor-delete',{name:n,map_id:map,anchor_version:a.version,confirm_delete:true});
};
function setPick(type){if(busy)return;if(!grid||grid.frame!=='map'||gridOwner!==state?.state.map_id||!state?.state.map_id){toast('请先加载已保存地图');return}setTab('2d');pick={type,map_id:state.state.map_id,name:$('pointName').value.trim(),arrival_motion:$('newMode').value,manual_handoff:$('newHandoff').checked};$('mapInstruction').hidden=false;$('mapInstruction').firstChild.textContent=type==='assist'?'在机器人实际位置按住，沿机头方向拖动 ':'在目标位置按住，沿期望朝向拖动 ';canvas.style.cursor='crosshair';$('mapArea').scrollIntoView({block:'center',behavior:'smooth'})}
$('assist').onclick=()=>setPick('assist');$('mapPoint').onclick=()=>{if(!$('pointName').value.trim())return toast('请先填写目标名称');setPick('point')};
$('cancelPick').onclick=()=>{pick=null;startDrag=null;$('mapInstruction').hidden=true;canvas.style.cursor='';draw()};
$('record').onclick=()=>createPoint('record');
$('recordLocate').onclick=()=>setPick('assist');
$('preview').onclick=()=>act('preview',{name:$('targets').value});
$('navigate').onclick=async()=>{const n=$('targets').value;if(await ask('开始实际导航 · '+n,'请确认预演路线合理、沿途和线缆允许，现场人员可遥控接管。确认后机器人将实际运动。网页需保持连接。'))act('navigate',{name:n,confirm_motion:true})};
$('addRoute').onclick=()=>{let n=$('routeTarget').value;if(n&&!busy){if(route.length>=50)return toast('最多50个途经点');route.push(n);routeDirty=true;drawRoute()}};
$('clearRoute').onclick=()=>{if(busy)return;route=[];routeDirty=true;drawRoute()};
function drawRoute(){const el=$('routeChips');el.replaceChildren();if(!route.length){const t=document.createElement('span');t.className='subtle';t.textContent='选择途经点，按顺序添加';el.append(t)}route.forEach((n,i)=>{const chip=document.createElement('span');chip.className='chip';const text=document.createElement('span');text.textContent=(i+1)+'. '+n+' · '+modeLabel(modeOf(n))+(handoffOf(n)?' · 人工接管':'');chip.append(text);for(const [label,fn] of [['←',()=>{if(i){[route[i-1],route[i]]=[route[i],route[i-1]];routeDirty=true;drawRoute()}}],['×',()=>{route.splice(i,1);routeDirty=true;drawRoute()}]]){const b=document.createElement('button');b.textContent=label;b.disabled=busy;b.onclick=fn;chip.append(b)}el.append(chip)});$('addRoute').disabled=busy||!$('routeTarget').value;$('clearRoute').disabled=busy;$('saveRoute').disabled=busy||!routeDirty||route.length===1||!state?.state.map_id;$('saveRoute').textContent=route.length?'保存路线':'保存清空路线';$('previewRoute').disabled=busy||routeDirty||!state?.ready||route.length<2;const reason=routeBlockReason();$('executeRoute').disabled=!!reason;$('routeGate').textContent='从头执行整条路线：'+(reason||'预演有效；此操作会从第一个点重新开始');updateResume()}
$('saveRoute').onclick=async()=>{const names=route.slice();if(await act('route-set',{names})){routeDirty=false;routeKey=JSON.stringify(names);route=names;drawRoute()}};
$('previewRoute').onclick=()=>act('route-preview');
$('executeRoute').onclick=async()=>{const r=state?.resume;const warning=r?.available?'已有停止任务，已完成 '+r.completed+'/'+r.total+'。本操作会放弃当前续跑进度，从第一个点重新执行！\n若要继续，请取消并点击“预演剩余路线”。\n\n':'';if(await ask('从头重新执行整条路线',warning+'顺序：'+route.join(' → ')+'\n普通点停稳后自动继续；人工接管点必须是末点，到点结束自动任务。路线只到楼梯入口，不跨越楼梯。现场请随时接管。'))act('route-execute',{confirm_motion:true,restart_token:r?.available?r.token:undefined})};
function options(id,values,preferred){const el=$(id),old=el.value;const sig=JSON.stringify(values);if(el.dataset.sig!==sig){el.replaceChildren();for(const v of values){const o=document.createElement('option');o.value=v;o.textContent=v;el.append(o)}el.dataset.sig=sig;el.value=values.includes(old)?old:values.includes(preferred)?preferred:values[0]||''}}
function handoffOf(n){return state?.state.points?.[n]?.manual_handoff===true}
function modeOf(n){const a=state?.state.points?.[n]?.arrival_motion;return a?.switch?a.mode:'keep'}
function modeLabel(m){return {keep:'保持模式',obstacle:'普通越障',normal:'默认模式'}[m]||m}
function modeBlocked(n){const m=modeOf(n);return m!=='keep'&&!(state?.motion_modes?.supported||[]).includes(m)}
function syncMode(force=false){const n=$('targets').value,k=n+':'+modeOf(n)+':'+handoffOf(n);if(force||(!modeDirty&&k!==modeKey)){$('arrivalMode').value=modeOf(n);$('arrivalHandoff').checked=handoffOf(n);modeKey=k;modeDirty=false}$('modeNote').textContent=modeDirty?'当前点的设置尚未保存，不影响新点设置。':modeBlocked(n)?'该点已设置模式切换，但实机接口尚未启用，不能执行导航。':(state?.motion_modes?.note||'');$('saveMode').disabled=busy||!modeDirty||!n||!state?.state.map_id||['mapping','starting','validating_map'].includes(state?.state.phase);$('arrivalMode').disabled=busy||!n;$('arrivalHandoff').disabled=busy||!n}
function resumeAvailability(s,isBusy,dirty,online=true){
 const deny=reason=>({preview:false,execute:false,reason});
 if(!online||!s)return deny('网页连接中断，请等待恢复');
 if(isBusy)return deny('当前操作进行中，请等待结束');
 if(dirty)return deny('路线或到点设置尚未保存');
 const r=s.resume;if(!r?.available)return deny(r?.reason||'没有可继续的停止任务');
 if(!s.ready)return {preview:true,execute:false,reason:'任务进度已保留；定位或输入未就绪。可点击“预演剩余路线”短暂等待恢复；未恢复前禁止运动。'};
 const ageReason=navigationAgeReason(s);if(ageReason)return {preview:true,execute:false,reason:'任务进度已保留；'+ageReason+'。可预演等待恢复，当前不会运动。'};
 const p=s.state.route_resume_preview,valid=p?.success&&p.resume_token===r.token&&s.now-p.created>=0&&s.now-p.created<60;
 return {preview:true,execute:!!valid,reason:'已完成 '+r.completed+'/'+r.total+'；继续顺序：'+r.remaining.join(' → ')+(valid?'。剩余路线预演有效，可确认继续。':'。请先预演剩余路线，不会重走已完成点。')};
}
function updateResume(){const gate=resumeAvailability(state,busy,routeDirty||modeDirty,connected&&Date.now()-lastStatus<3500);$('previewResume').disabled=!gate.preview;$('resumeRoute').disabled=!gate.execute;$('resumeGate').textContent=gate.reason}
$('previewResume').onclick=()=>act('route-resume-preview',{resume_token:state?.resume?.token});
$('resumeRoute').onclick=async()=>{const token=state?.resume?.token,names=state?.resume?.remaining||[];if(await ask('继续未完成任务','将从未完成点继续：'+names.join(' → ')+'。\n已完成点不会重走；当前点会重新规划、到位停稳后再继续。请确认障碍已处理、路线及线缆允许，并在旁监控。'))act('route-resume',{resume_token:token,confirm_motion:true})};
$('arrivalHandoff').onchange=$('arrivalMode').onchange=()=>{modeDirty=true;syncMode();$('navigate').disabled=true;$('preview').disabled=true;$('executeRoute').disabled=true};
$('saveMode').onclick=async()=>{if(await act('point-settings',{name:$('targets').value,arrival_motion:$('arrivalMode').value,manual_handoff:$('arrivalHandoff').checked})){modeDirty=false;await poll();syncMode(true)}};
function age(x){return typeof x==='number'?x.toFixed(2)+' s':'—'}
function validPreview(){const p=state?.state.preview;return state?.ready&&p&&p.name===$('targets').value&&state.now-p.at>=0&&state.now-p.at<60}
function navigationAgeReason(s=state){
 const name=s?.speed?.active?.name,limit=name==='hall08'?.3:name==='corridor04'?.6:.5;
 for(const [key,label] of [['pose_age_s','位姿'],['cloud_age_s','点云']]){const age=s?.input?.[key];if(!Number.isFinite(age)||age<-.05||age>limit)return label+'数据未满足运动要求（'+(Number.isFinite(age)?age.toFixed(2)+'秒':'无数据')+'，上限'+limit.toFixed(2)+'秒）'}
 return '';
}
function routeBlockReason(){
 if(!connected||Date.now()-lastStatus>3500)return '网页连接或状态已过期';
 if(busy)return '当前操作进行中，请等待完成';
 if(routeDirty)return '路线尚未保存，请先保存路线';
 if(modeDirty)return '到点参数尚未保存';
 if(!state?.ready)return '定位或导航输入未就绪，请查看运行状态和日志';
 const ageReason=navigationAgeReason();if(ageReason)return ageReason;
 if(route.length<2)return '请保存至少两个途经点；单点使用左侧导航';
 if(route.some(modeBlocked))return '某个途经点要求的模式当前不可用';
 if(!validRoutePreview())return '需要重新预演整条路线（预演有效期60秒）';
 return '';
}
function validRoutePreview(){const p=state?.state.route_preview;return state?.ready&&p?.success&&state.now-p.created>=0&&state.now-p.created<60}
// Recording a live pose requires an accepted transform into the saved map.
// Explain the unmet step instead of silently disabling the button.
function recordAvailability(s,isBusy,isConnected=true){
 const deny=(reason,locate=false)=>({enabled:false,reason,locate});
 if(!isConnected||!s)return deny('网页连接已中断，等待重新连接后再记录。');
 if(isBusy)return deny('当前操作正在执行，完成后再记录当前位置。');
 const d=s.state||{};
 if(d.phase==='mapping')return deny('正在扫图：先停稳，点击“结束并保存”，地图验证通过后即可记录当前位置。');
 if(!d.map_id)return deny('尚未选择地图：加载已保存地图并完成定位，或开始新扫图并保存。');
 if(!s.fusion_ready)return deny('融合输入未就绪：保持静止，先恢复定位或检查传感器。',true);
 if(!s.nav_ready)return deny('导航输入未就绪：等待服务恢复；若持续异常，请查看操作日志。',true);
 if(!s.localized)return deny(d.phase==='recovery_failed'?'旧地图重定位失败：请在二维地图标记机器狗实际位置，沿机头方向拖动；匹配通过后按钮会自动启用。':'尚未确定机器狗在旧地图中的位置：请先标记实际位置与朝向，完成重定位。',true);
 if(!s.ready)return deny('地图验证尚未完成，请等待定位流程结束；若持续未就绪，请查看操作日志。');
 return {enabled:true,reason:'可以记录：先停稳并填写目标名称，将保存当前地图中的位置和朝向（采样约3.5秒）。',locate:false};
}
function updateRecord(s,isBusy,isConnected=true){
 const gate=recordAvailability(s,isBusy,isConnected);
 $('record').disabled=!gate.enabled;$('record').title=gate.reason;
 $('recordNote').textContent=gate.reason;
 $('recordLocate').hidden=!gate.locate;$('recordLocate').disabled=!gate.locate;
}
function recentJobFailure(s){const elapsed=s.now-(s.job?.ended||s.job?.started||0);return s.job?.phase==='failed'&&elapsed>=0&&elapsed<60}
function update(s){state=s;lastStatus=Date.now();
 $('mapWarning').hidden=!s.map_geometry_warning;$('mapWarning').textContent=s.map_geometry_warning||'';
 if(pendingAction&&s.job?.id===pendingAction.id&&s.job.phase!=='running'){const p=pendingAction;pendingAction=null;p.resolve(s.job.phase==='done');toast(s.job.phase==='done'?'操作已完成':'操作未完成，草稿保留，请查看日志')}
 busy=!!pendingAction||s.job?.phase==='running'||s.stopping||s.external_operation;
 if(uiMap!==s.state.map_id){uiMap=s.state.map_id;routeDirty=false;routeKey='';route=[];modeDirty=false;modeKey='';$('cancelPick').click();$('pointName').value='';$('anchorName').value='';grid=null;gridTag='';fitKey=''}options('maps',s.maps,s.state.map_id);trashOptions(s);const names=Object.keys(s.state.points||{});options('targets',names,s.state.selected);options('routeTarget',names);$('phase').textContent=(!busy&&['starting','recovering','validating_map'].includes(s.state.phase))?(s.fusion_ready?'服务已启动，待选择地图':'初始化已中断'):phaseNames[s.state.phase]||s.state.phase||'待开始';
 const badges=$('badges');badges.replaceChildren();for(const [label,ok] of [['板载融合',s.fusion_ready],['导航输入',s.nav_ready],['旧图定位',s.localized]]){const e=document.createElement('span');e.className=ok?'good':'warn';e.textContent=(ok?'● ':'○ ')+label+(ok?'正常':'未就绪');badges.append(e)}
 let text=s.ready?'定位已就绪，无需重复恢复。记录目标 → 遥控离开并停稳 → 预演 → 开始导航。':s.state.phase==='mapping'?'正在扫图。可遥控移动采集，完成后停稳并保存。':s.fusion_ready?'融合正在板载运行。旧地图定位尚未验证，当前不能导航。':'融合尚未就绪；请检查服务或保持静止开始扫图。';
 if(s.state.phase==='start_failed')text='扫图启动未完成，请查看日志并重新开始扫图。'+(s.state.recovery_error||'');
 if(s.state.phase==='recovery_failed')text='旧地图重定位失败，已有地图和目标保留。可放回固定定位点后恢复，或在二维地图标记实际位置与朝向；匹配通过后才能记录当前位置和导航。';
 if(s.job?.phase==='running')text='正在执行：'+actionLabel(s.job.action)+'。'+(['navigate','route-execute','route-resume'].includes(s.job.action)?'实机运动中，请保持监控。':'请查看操作日志，初始化与定位期间保持静止。');
 if(s.external_operation&&s.job?.phase!=='running')text='控制台正在执行操作，请等待完成。当前阶段：'+(phaseNames[s.state.phase]||s.state.phase);
 if(!busy&&recentJobFailure(s)&&s.state.phase!=='recovery_failed')text='上次操作未完成。'+(s.last_result?.reason||(['route-execute','route-resume'].includes(s.job?.action)?s.route_progress?.error:'')||s.state.recovery_error||'请查看右侧日志中的具体原因。');
 if(s.nav_runtime?.phase==='degraded')text='导航已暂停，后台仍在接收传感器并检查定位。请先停稳，等待重新验证；若持续不通过，再使用固定位置或地图标记重定位。中断的路线不会自动继续。';
 $('notice').textContent=text;$('notice').className=recentJobFailure(s)||(!busy&&['start_failed','recovery_failed'].includes(s.state.phase))?'error':'';
 const metrics=[['计算位置','Go2W 板载'],['前进速度上限',s.speed?.active?s.speed.active.vx_max+' m/s（运行中）':s.speed?.selected?s.speed.selected.vx_max+' m/s（待启动）':'—'],['地图',s.state.map_id||'未选择'],['融合延迟',s.fusion_ready?age(s.fusion.lag_last_s):'未运行 / 数据过期'],['位姿数据年龄',s.nav_ready?age(s.input.pose_age_s):'输入未就绪'],['点云数据年龄',s.nav_ready?age(s.input.cloud_age_s):'输入未就绪'],['旧图匹配率',s.localization?.stats?.fitness!=null?(s.localization.stats.fitness*100).toFixed(1)+'%':'—']];
 $('metrics').replaceChildren();for(const [k,v] of metrics){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;dd.title=v;if(k==='地图')dd.textContent=v.length>21?v.slice(0,18)+'…':v;$('metrics').append(dt,dd)}
 $('jobStatus').textContent=s.stopping?'正在请求停车，请确认实机停稳':s.job?.action?actionLabel(s.job.action)+' · '+({running:'执行中',done:'完成',failed:'未完成',cancelled:'已取消'}[s.job.phase]||s.job.phase):'没有正在执行的操作';
 if(s.last_stop?.at&&s.now-s.last_stop.at<30&&!s.stopping){$('jobStatus').textContent=s.last_stop.confirmed?'取消请求已处理，请现场确认已停稳':'停车未获确认，请立即遥控接管';if(!s.last_stop.confirmed){$('notice').textContent='停车未获确认，请立即遥控接管。'+(s.last_stop.detail||'');$('notice').className='error'}}
 if(s.job?.phase!=='running'&&s.now-(s.job?.ended||s.job?.started||0)>=60)$('jobStatus').textContent+='（历史记录）';
 $('logKind').textContent=s.job?.phase==='running'?'实时':s.job?.action?'最近一次操作':'等待';$('log').textContent=s.job?.log||'等待操作…';$('log').scrollTop=$('log').scrollHeight;
 for(const id of ['load','start','restore','assist','record','mapPoint','preview','finish'])$(id).disabled=busy;
 $('finish').disabled=busy||s.state.phase!=='mapping';$('restore').disabled=busy||!s.state.map_id||s.state.phase==='mapping';$('restore').disabled||=s.ready;$('assist').disabled=$('restore').disabled;$('load').disabled=busy||s.state.phase==='mapping'||(s.ready&&$('maps').value===s.state.map_id);
 updateRecord(s,busy);updateAnchors(s);$('preview').disabled=busy||modeDirty||!s.ready||!names.length;$('navigate').disabled=busy||modeDirty||modeBlocked($('targets').value)||!validPreview()||!!navigationAgeReason(s);$('navigate').title=navigationAgeReason(s);$('mapPoint').disabled=busy||!s.state.map_id||s.state.phase==='mapping';
 syncMode();const rk=JSON.stringify(s.state.route?.names||[]);if(!routeDirty&&rk!==routeKey){route=s.state.route?.names?.slice()||[];routeKey=rk}drawRoute();
 const rp=s.route_progress;$('routeProgress').textContent=rp?.phase?'任务：'+(({awaiting_manual:'已结束，等待人工接管',stopped:'已停止，进度保留',countdown:'启动倒计时',navigating:'前往目标',dwelling:'到点停靠',completed:'全部完成'}[rp.phase]||rp.phase))+' · 已完成 '+rp.completed+'/'+(rp.names?.length||0)+(rp.error?' · '+rp.error:''):routeDirty?(route.length===1?'只有1个途经点，请再添加一个；单点导航请使用左侧按钮。':'路线已修改，请先保存再预演'):'';
 const cameraFresh=s.now-(s.camera.updated||0)<3;$('cameraAge').textContent=cameraFresh?'实时 · '+age(s.now-s.camera.updated):'输入过期';$('cameraEmpty').hidden=cameraFresh&&!!camURL;$('cameraEmpty').textContent=camURL?'相机输入已中断':'等待相机输入';$('camera').style.opacity=cameraFresh?'1':'.35';
 draw();loadAssets();loadCamera();
}
function actionLabel(a){return {'anchor-save':'保存固定定位点','anchor-use':'固定位置重定位','anchor-delete':'删除固定定位点',start:'开始扫图',finish:'保存地图','load-map':'加载地图',restore:'自动重定位',assist:'辅助重定位',record:'记录当前位置','point-settings':'保存到点模式','map-point':'保存地图目标',preview:'预演路线',navigate:'导航','route-set':'保存多点路线','route-preview':'预演整条路线','route-execute':'执行整条路线','route-resume-preview':'预演剩余路线','route-resume':'继续未完成任务','delete-map':'删除地图','restore-map':'恢复回收站地图'}[a]||a}
async function poll(){if(pollBusy)return;pollBusy=true;try{const s=await api('status');connected=true;update(s)}catch(e){if(connected)toast(e.message);connected=false;markDisconnected()}finally{pollBusy=false}}
setInterval(()=>{if(connected)api('heartbeat',{}).catch(()=>{});},1000);
function markDisconnected(){
 connected=false;
 $('notice').textContent='与机器人连接中断。不要继续操作；运动中请遥控确认已停稳。';$('notice').className='error';
 $('badges').textContent='○ 实时状态已过期';$('cameraAge').textContent='历史画面 · 连接中断';
 for(const id of ['saveAnchor','useAnchor','deleteAnchor','load','start','finish','restore','assist','record','mapPoint','preview','navigate','deleteMap','restoreMap','saveMode','saveRoute','previewRoute','executeRoute','previewResume','resumeRoute'])$(id).disabled=true;
 updateRecord(state,busy,false);draw();
}
setInterval(()=>{if(!document.hidden||busy)poll();if(Date.now()-lastStatus>3500&&lastStatus)markDisconnected()},1000);

$('maps').onchange=()=>{if(state)$('load').disabled=busy||state.state.phase==='mapping'||(state.ready&&$('maps').value===state.state.map_id);mapButtons(state)};
$('targets').onchange=()=>{syncMode(true);$('navigate').disabled=busy||modeBlocked($('targets').value)||!validPreview()};
async function blobImage(file,stamp){const r=await fetch('/data/'+file+'?v='+stamp,{signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error('无图像');return createImageBitmap(await r.blob())}
async function loadCamera(){const s=state;if(cameraBusy||!s?.camera.updated||s.now-s.camera.updated>=3||camTag===String(s.camera.updated))return;cameraBusy=true;try{const r=await fetch('/data/camera.jpg?v='+s.camera.updated,{signal:AbortSignal.timeout(4000)});if(!r.ok)throw Error('camera');const u=URL.createObjectURL(await r.blob());$('camera').src=u;$('camera').hidden=false;$('cameraEmpty').hidden=true;URL.revokeObjectURL(camURL);camURL=u;camTag=String(s.camera.updated)}catch(e){$('cameraEmpty').textContent='相机画面加载失败，正在重试';$('cameraEmpty').hidden=false}finally{cameraBusy=false}}
async function loadAssets(){if(assetBusy||!state)return;assetBusy=true;try{const s=state,v=s.view;let key='';if(s.state.map_id){if(v.saved?.map_id===s.state.map_id)key=s.localized&&v.grid?.frame==='map'&&s.now-v.grid.updated<4?'grid':'saved'}else if(v.grid?.frame==='camera_init'&&v.session===s.input?.session&&s.now-v.grid.updated<4)key='grid';
 if(key){const meta=v[key],tag=key+meta.updated;if(tag!==gridTag){const image=await blobImage(key+'.png',meta.updated);if(state?.state.map_id!==s.state.map_id){image.close();return}gridImage?.close();gridImage=image;grid=meta;gridOwner=s.state.map_id;gridTag=tag;const fk=JSON.stringify([key==='saved'?meta.map_id:'live',meta.frame,meta.width,meta.height,meta.origin]);if(fk!==fitKey){fitKey=fk;fitMap()}}}else{grid=null;gridImage=null;gridTag=''}
 if(v.local&&state.now-v.local.updated<3&&localTag!==String(v.local.updated)){localImage?.close();localImage=await blobImage('local.png',v.local.updated);localMeta=v.local;localTag=String(v.local.updated)}

 if(tab==='3d')await loadCloud(s);
 draw();}catch(e){/* Status panel exposes missing/stale inputs; keep previous asset visibly dated. */}finally{assetBusy=false}}
function setTab(t){tab=t;canvas.hidden=t!=='2d';$('cloud3d').hidden=t!=='3d';$('tab2d').classList.toggle('active',t==='2d');$('tab3d').classList.toggle('active',t==='3d');$('coordinates').textContent=t==='2d'?'滚轮缩放 · 拖动平移':'左键旋转 · 右键/Shift平移 · 滚轮缩放';$('cloudPan').hidden=t!=='3d';$('reset3d').hidden=t!=='3d';$('focusRobot').hidden=t!=='3d';$('cloudOverlay').hidden=t!=='3d';if(t==='3d'){$('cancelPick').click();loadAssets()}draw()}
$('tab2d').onclick=()=>setTab('2d');$('tab3d').onclick=()=>setTab('3d');$('fit').onclick=()=>{if(tab==='2d')fitMap();else fitCloud();draw()};$('localLayer').onchange=draw;
function size(c){const r=c.getBoundingClientRect(),d=Math.min(window.devicePixelRatio||1,2);if(c.width!==Math.round(r.width*d)||c.height!==Math.round(r.height*d)){c.width=Math.round(r.width*d);c.height=Math.round(r.height*d)}return [r.width,r.height,d]}
function fitMap(){if(!grid)return;const r=canvas.getBoundingClientRect();const b=grid.bounds||[0,0,grid.width,grid.height],pad=1/grid.resolution,bw=b[2]-b[0]+2*pad,bh=b[3]-b[1]+2*pad;scale=Math.min((r.width-50)/bw,(r.height-80)/bh);pan=[r.width/2-(b[0]+b[2])/2*scale,r.height/2-(grid.height-(b[1]+b[3])/2)*scale]}
function w2s(p){const dx=p[0]-grid.origin[0],dy=p[1]-grid.origin[1],a=grid.origin[2];return [pan[0]+(Math.cos(a)*dx+Math.sin(a)*dy)/grid.resolution*scale,pan[1]+(grid.height-(-Math.sin(a)*dx+Math.cos(a)*dy)/grid.resolution)*scale]}
function s2w(p){const x=(p[0]-pan[0])/scale*grid.resolution,y=(grid.height-(p[1]-pan[1])/scale)*grid.resolution,a=grid.origin[2];return [grid.origin[0]+Math.cos(a)*x-Math.sin(a)*y,grid.origin[1]+Math.sin(a)*x+Math.cos(a)*y]}
function line(points,color,width=2,closed=false){if(!points?.length)return;ctx.beginPath();points.forEach((p,i)=>{const s=w2s(p);i?ctx.lineTo(...s):ctx.moveTo(...s)});if(closed)ctx.closePath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke()}
function arrow(x,y,a,color,length=23){const p=w2s([x,y]),q=w2s([x+Math.cos(a),y+Math.sin(a)]);ctx.save();ctx.translate(...p);ctx.rotate(Math.atan2(q[1]-p[1],q[0]-p[0]));ctx.fillStyle=color;ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(length,0);ctx.lineTo(-8,-8);ctx.lineTo(-4,0);ctx.lineTo(-8,8);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore()}
function displayPlans(s,frame){
 const p=s?.state.route_resume_preview;
 if(frame==='map'&&p?.success&&p.map_id===s.state.map_id&&p.source_session===s.state.session&&p.resume_token===s.resume?.token&&s.now-p.created>=0&&s.now-p.created<60)return [{points:p.segments.flatMap(x=>x.path),color:'#2a8be8'}];
 const v=s?.view||{};return ['route_plan','plan'].filter(k=>v[k]?.frame===frame&&s.now-v[k].updated>=0&&s.now-v[k].updated<60).map(k=>({points:v[k].points,color:k==='plan'?'#08b594':'#2a8be8'}));
}
function draw(){if(tab==='3d'){drawCloud();return}const [w,h,d]=size(canvas);ctx.setTransform(d,0,0,d,0,0);ctx.clearRect(0,0,w,h);$('emptyMap').hidden=!!(grid&&gridImage);if(!grid||!gridImage){$('mapLabel').textContent='地图数据未就绪或已过期';$('coordinates').textContent='滚轮缩放 · 拖动平移';return;}ctx.imageSmoothingEnabled=false;ctx.drawImage(gridImage,pan[0],pan[1],grid.width*scale,grid.height*scale);
 const freshConnection=Date.now()-lastStatus<3500,s=state,v=s?.view||{},overlay=freshConnection&&s.nav_ready&&(grid.frame!=='map'||s.localized)&&v.session===s.input?.session;
 if(overlay&&$('localLayer').checked&&localImage&&localMeta?.frame===grid.frame&&s.now-localMeta.updated<3){const m=localMeta,a=m.origin[2],res=m.resolution;const ll=w2s(m.origin),lr=w2s([m.origin[0]+Math.cos(a)*m.width*res,m.origin[1]+Math.sin(a)*m.width*res]),ul=w2s([m.origin[0]-Math.sin(a)*m.height*res,m.origin[1]+Math.cos(a)*m.height*res]);ctx.save();ctx.transform((lr[0]-ll[0])/m.width,(lr[1]-ll[1])/m.width,(ll[0]-ul[0])/m.height,(ll[1]-ul[1])/m.height,ul[0],ul[1]);ctx.globalAlpha=.45;ctx.drawImage(localImage,0,0);ctx.restore()}
 if(overlay){for(const p of displayPlans(s,grid.frame))line(p.points,p.color,3);if(v.footprint?.frame===grid.frame&&s.now-v.footprint.updated<2)line(v.footprint.points,'#ff8b3a',1.5,true);if(v.robot?.frame===grid.frame&&s.now-v.robot.updated<2){const p=v.robot.pose;arrow(p[0],p[1],p[3],'#f88834',25)}}
 if(grid.frame==='map')for(const [n,t] of Object.entries(s?.state.points||{})){if(t.map_id!==s.state.map_id)continue;const p=w2s(t.pose);ctx.fillStyle='#2678d8';ctx.beginPath();ctx.arc(...p,5,0,Math.PI*2);ctx.fill();ctx.fillStyle='#113d63';ctx.font='bold 12px system-ui';ctx.fillText(n,p[0]+9,p[1]-8)}
 if(startDrag?.world&&pick){line([startDrag.world,startDrag.end||startDrag.world],'#ffc24b',3);const end=startDrag.end||startDrag.world;arrow(...startDrag.world,Math.atan2(end[1]-startDrag.world[1],end[0]-startDrag.world[0]),'#eaaa21')}
 $('mapLabel').textContent=(!freshConnection?'历史画面 · 连接中断':grid.frame==='map'?(s?.localized?'旧图定位':'仅显示旧地图 · 待定位'):'实时建图')+' · '+grid.frame+' · '+grid.resolution.toFixed(2)+' m/格';
}
function pointer(e){const r=canvas.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]}
canvas.onpointerdown=e=>{if(!grid||e.button!==0)return;canvas.setPointerCapture(e.pointerId);const p=pointer(e);startDrag={screen:p,pan:pan.slice(),world:pick?s2w(p):null};dragMoved=false};
canvas.onpointermove=e=>{if(!grid)return;const p=pointer(e),world=s2w(p);$('coordinates').textContent=world[0].toFixed(2)+', '+world[1].toFixed(2)+' m';if(startDrag){dragMoved=true;if(pick)startDrag.end=world;else pan=[startDrag.pan[0]+p[0]-startDrag.screen[0],startDrag.pan[1]+p[1]-startDrag.screen[1]];draw()}};
canvas.onpointerup=async e=>{
 if(!startDrag)return;const d=startDrag;startDrag=null;
 if(pick){
  if(!dragMoved||Math.hypot(pointer(e)[0]-d.screen[0],pointer(e)[1]-d.screen[1])<=12){toast('请按住目标位置，拖出朝向箭头后松开');draw();return}
  const chosen={...pick},p=d.world,end=s2w(pointer(e)),a=Math.atan2(end[1]-p[1],end[0]-p[0]);$('cancelPick').click();
  if(chosen.map_id!==state?.state.map_id)return toast('地图已变化，请重新标点');
  if(await ask(chosen.type==='assist'?'确认定位提示':'确认新目标 · '+chosen.name,`位置 x=${p[0].toFixed(2)} m，y=${p[1].toFixed(2)} m，朝向 ${(a*180/Math.PI).toFixed(0)}°\n`+(chosen.type==='assist'?'请保持静止，匹配旧地图。':'仅保存目标，不会运动。'))){
   const extra={map_id:chosen.map_id,pose:[...p,a],name:chosen.name,arrival_motion:chosen.arrival_motion,manual_handoff:chosen.manual_handoff};
   if(chosen.type==='assist')await act('assist',{...extra,stationary:true});else await createPoint('map-point',extra);
  }
 }
 draw();
};
canvas.onpointercancel=()=>{startDrag=null;draw()};canvas.onwheel=e=>{e.preventDefault();if(!grid)return;const p=pointer(e),s=scale,f=Math.exp(-e.deltaY*.001);scale=Math.max(.05,Math.min(30,scale*f));pan=[p[0]-(p[0]-pan[0])*scale/s,p[1]-(p[1]-pan[1])*scale/s];draw()};
let rgbData=new Float32Array(),rgbLive=new Float32Array(),rgbSavedTag='',rgbLiveTag='';
let gl=null,program,buffer,cloudData=new Float32Array(),cloudHistory=[],voxelPoints=new Map(),voxelSize=.05,cloudFrame='',cloudSession='',cloudMap='',savedCloudTag='',liveCloudTag='',center=[0,0,0],radius=10,yaw=-.5,pitch=.9,glDrag=null;
function initGL(){gl=$('cloud3d').getContext('webgl',{antialias:true});if(!gl){toast('浏览器不支持WebGL，请使用二维地图');return false}function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 p;attribute vec3 color;varying vec3 rgb;uniform vec3 center;uniform vec2 angle;uniform vec2 size;uniform float radius;varying float height;void main(){vec3 a=p-center;float x=cos(angle.x)*a.x-sin(angle.x)*a.y;float y=sin(angle.x)*a.x+cos(angle.x)*a.y;float v=cos(angle.y)*y-sin(angle.y)*a.z;float z=sin(angle.y)*y+cos(angle.y)*a.z;gl_Position=vec4(x/radius*size.y/size.x,-v/radius,z/1000.,1.);gl_PointSize=2.;height=p.z;rgb=color;}'));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying float height;varying vec3 rgb;uniform float hasColor;void main(){gl_FragColor=vec4(hasColor>0.5?rgb:vec3(0.52,0.56,0.59),1.);}'));gl.linkProgram(program);buffer=gl.createBuffer();return true}
async function loadCloud(s){const v=s.view;let ident=s.state.map_id,sc=v.saved_cloud;const frame=ident?'map':'camera_init';if(cloudFrame!==frame||cloudSession!==s.view.session||cloudMap!==ident||(!ident&&savedCloudTag)){cloudHistory=[];voxelPoints.clear();voxelSize=.05;cloudData=new Float32Array();cloudSession=s.view.session;cloudMap=ident;cloudFrame=frame;savedCloudTag='';liveCloudTag='';rgbData=new Float32Array();rgbLive=new Float32Array();rgbSavedTag='';rgbLiveTag=''}
 if(ident&&sc?.map_id===ident&&savedCloudTag!==ident+sc.updated){const r=await fetch('/data/saved-cloud.bin?v='+sc.updated,{signal:AbortSignal.timeout(8000)});if(r.ok){const bytes=await r.arrayBuffer();if(state?.state.map_id!==ident)return;cloudData=new Float32Array(bytes);savedCloudTag=ident+sc.updated;cloudHistory=[];fitCloud();const robot=freshCloudRobot(s);if(robot){center=robot.slice(0,3);radius=6}}}
 if(v.cloud?.frame===frame&&s.now-v.cloud.updated<2&&(!ident||s.localized)&&liveCloudTag!==String(v.cloud.updated)){const r=await fetch('/data/cloud.bin?v='+v.cloud.updated,{signal:AbortSignal.timeout(8000)});if(r.ok){const a=new Float32Array(await r.arrayBuffer());if(!ident){const first=voxelPoints.size===0;for(let i=0;i<a.length;i+=3){const p=[a[i],a[i+1],a[i+2]],key=p.map(x=>Math.floor(x/voxelSize)).join(',');voxelPoints.set(key,p)}while(voxelPoints.size>400000){voxelSize*=1.5;const next=new Map();for(const p of voxelPoints.values())next.set(p.map(x=>Math.floor(x/voxelSize)).join(','),p);voxelPoints=next}cloudData=new Float32Array(voxelPoints.size*3);let offset=0;for(const p of voxelPoints.values()){cloudData.set(p,offset);offset+=3}if(first)fitCloud()}liveCloudTag=String(v.cloud.updated)}}
 const sr=v.saved_rgb,lr=v.rgb_cloud;
 if(ident&&sr?.map_id===ident&&rgbSavedTag!==ident+sr.updated){const r=await fetch('/data/saved-rgb.bin?v='+sr.updated,{signal:AbortSignal.timeout(8000)});if(r.ok){const bytes=await r.arrayBuffer();if(state?.state.map_id!==ident||state?.view.session!==s.view.session)return;if(bytes.byteLength===sr.count*24){rgbData=new Float32Array(bytes);rgbSavedTag=ident+sr.updated}}}
 if(lr?.frame===frame&&lr.session===s.view.session&&(!ident||(s.localized&&lr.map_id===ident))&&s.now-lr.updated>=0&&s.now-lr.updated<3&&rgbLiveTag!==String(lr.updated)){const r=await fetch('/data/rgb-cloud.bin?v='+lr.updated,{signal:AbortSignal.timeout(8000)});if(r.ok){const bytes=await r.arrayBuffer();if(state?.state.map_id!==ident||state?.view.session!==s.view.session)return;if(bytes.byteLength===lr.count*24){rgbLive=new Float32Array(bytes);rgbLiveTag=String(lr.updated);if(!cloudData.length)fitCloud()}}}
 drawCloud()}
function fitCloud(){const data=cloudData.length?cloudData:rgbLive,step=cloudData.length?3:6;if(!data.length)return;const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(let i=0;i<data.length;i+=step)for(let k=0;k<3;k++){lo[k]=Math.min(lo[k],data[i+k]);hi[k]=Math.max(hi[k],data[i+k])}center=lo.map((x,k)=>(x+hi[k])/2);radius=Math.max(2,(hi[0]-lo[0])*.6,(hi[1]-lo[1])*.6)}
function projectCloud(p,w,h){
 const a=p.map((v,i)=>v-center[i]),x=Math.cos(yaw)*a[0]-Math.sin(yaw)*a[1],y=Math.sin(yaw)*a[0]+Math.cos(yaw)*a[1];
 const v=Math.cos(pitch)*y-Math.sin(pitch)*a[2];return [w/2+x*h/(2*radius),h/2+v*h/(2*radius)];
}
function freshCloudRobot(s=state){
 const r=s?.view?.robot;
 return connected&&Date.now()-lastStatus<3500&&(cloudFrame!=='map'||cloudMap===s?.state?.map_id)&&s?.nav_ready&&(cloudFrame!=='map'||s.localized)&&s.view.session===s.input?.session&&r?.frame===cloudFrame&&s.now-r.updated>=0&&s.now-r.updated<2&&r.pose?.length===4&&r.pose.every(Number.isFinite)?r.pose:null;
}
function drawCloudOverlay(){
 const c=$('cloudOverlay'),[w,h,d]=size(c),ct=c.getContext('2d');ct.setTransform(d,0,0,d,0,0);ct.clearRect(0,0,w,h);
 const robot=freshCloudRobot(),s=state,v=s?.view||{};$('focusRobot').disabled=!robot;
 function path(points,color){if(points.length<2)return;ct.beginPath();points.forEach((p,i)=>{const q=projectCloud(p,w,h);i?ct.lineTo(...q):ct.moveTo(...q)});ct.strokeStyle=color;ct.lineWidth=3;ct.stroke()}
 if(robot){
  for(const line of displayPlans(s,cloudFrame))path(line.points.map(p=>[p[0],p[1],robot[2]]),line.color);
  if(cloudFrame==='map')for(const [name,t] of Object.entries(s.state.points||{})){if(t.map_id!==s.state.map_id)continue;const q=projectCloud([t.pose[0],t.pose[1],robot[2]],w,h);ct.fillStyle='#5eb7ff';ct.beginPath();ct.arc(...q,5,0,2*Math.PI);ct.fill();ct.fillStyle='white';ct.font='bold 13px sans-serif';ct.fillText(name,q[0]+9,q[1]-8)}
  const q=projectCloud(robot.slice(0,3),w,h),tip=projectCloud([robot[0]+Math.cos(robot[3]),robot[1]+Math.sin(robot[3]),robot[2]],w,h),angle=Math.atan2(tip[1]-q[1],tip[0]-q[0]);
  ct.save();ct.translate(...q);ct.rotate(angle);ct.fillStyle='#ff8b3a';ct.strokeStyle='white';ct.lineWidth=2;ct.beginPath();ct.moveTo(26,0);ct.lineTo(-10,-9);ct.lineTo(-5,0);ct.lineTo(-10,9);ct.closePath();ct.fill();ct.stroke();ct.restore();
  ct.fillStyle='white';ct.font='bold 13px sans-serif';ct.fillText('机器人 · +X机头',q[0]+16,q[1]+24);
  $('mapLabel').textContent+=' · 机器人实时位置（路线为平面投影）';
 }else $('mapLabel').textContent+=' · 实时位置不可用';
}
$('focusRobot').onclick=()=>{const p=freshCloudRobot();if(!p)return toast('定位或实时位姿未就绪');center=p.slice(0,3);radius=5;drawCloud()};
function drawCloud(){
 if(tab!=='3d')return;const c=$('cloud3d'),[w,h,d]=size(c);if(!gl&&!initGL())return;
 $('emptyMap').hidden=!!(cloudData.length||rgbData.length||rgbLive.length);gl.viewport(0,0,c.width,c.height);gl.clearColor(.10,.10,.11,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.useProgram(program);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
 gl.uniform3fv(gl.getUniformLocation(program,'center'),center);gl.uniform2f(gl.getUniformLocation(program,'angle'),yaw,pitch);gl.uniform2f(gl.getUniformLocation(program,'size'),w,h);gl.uniform1f(gl.getUniformLocation(program,'radius'),radius);
 const pa=gl.getAttribLocation(program,'p'),ca=gl.getAttribLocation(program,'color');
 function render(a,rgb){if(!a.length)return;gl.bufferData(gl.ARRAY_BUFFER,a,gl.DYNAMIC_DRAW);gl.enableVertexAttribArray(pa);gl.vertexAttribPointer(pa,3,gl.FLOAT,false,rgb?24:12,0);if(rgb){gl.enableVertexAttribArray(ca);gl.vertexAttribPointer(ca,3,gl.FLOAT,false,24,12)}else{gl.disableVertexAttribArray(ca);gl.vertexAttrib3f(ca,0,0,0)}gl.uniform1f(gl.getUniformLocation(program,'hasColor'),rgb?1:0);gl.drawArrays(gl.POINTS,0,a.length/(rgb?6:3))}
 if(!rgbData.length&&(!rgbLive.length||state?.state.map_id))render(cloudData,false);
 render(rgbData,true);render(rgbLive,true);
 const colored=rgbData.length+rgbLive.length,count=colored/6+(rgbData.length?0:cloudData.length/3);
 const label=rgbData.length?'已保存 RGB 彩色地图':rgbLive.length?(state?.state.map_id?'导航地图 + 当前 RGB 彩色观测':'FAST-LIVO2 RGB 彩色累计地图'):'导航几何地图（未保存RGB）';
 const stale=rgbLive.length&&(!connected||!state?.fusion_ready||state.now-(state.view.rgb_cloud?.updated||0)>=3)?' · 彩色观测未更新':'';
 $('mapLabel').textContent=label+stale+' · '+cloudFrame+' · '+Math.round(count).toLocaleString()+' 显示点';drawCloudOverlay()
}
function panCloud(dx,dy,initial=center){
 const h=Math.max(1,$('cloud3d').getBoundingClientRect().height),k=2*radius/h;
 const right=[Math.cos(yaw),-Math.sin(yaw),0],down=[Math.sin(yaw)*Math.cos(pitch),Math.cos(yaw)*Math.cos(pitch),-Math.sin(pitch)];
 center=initial.map((v,i)=>v-k*(dx*right[i]+dy*down[i]));
}
$('cloudPan').onclick=()=>{cloudPan=!cloudPan;$('cloudPan').textContent='平移：'+(cloudPan?'开':'关');$('cloud3d').style.cursor=cloudPan?'grab':''};
$('reset3d').onclick=()=>{yaw=-.5;pitch=.9;fitCloud();drawCloud()};
$('cloud3d').oncontextmenu=e=>e.preventDefault();
$('cloud3d').onpointerdown=e=>{e.preventDefault();$('cloud3d').setPointerCapture(e.pointerId);glDrag={x:e.clientX,y:e.clientY,yaw,pitch,center:center.slice(),pan:cloudPan||e.shiftKey||e.button===2||e.button===1}};
$('cloud3d').onpointermove=e=>{if(!glDrag)return;const dx=e.clientX-glDrag.x,dy=e.clientY-glDrag.y;if(glDrag.pan)panCloud(dx,dy,glDrag.center);else{yaw=glDrag.yaw+dx*.008;pitch=Math.max(.1,Math.min(1.55,glDrag.pitch+dy*.008))}drawCloud()};
$('cloud3d').onpointerup=()=>glDrag=null;$('cloud3d').onpointercancel=()=>glDrag=null;
$('cloud3d').onwheel=e=>{e.preventDefault();radius=Math.max(.5,Math.min(200,radius*Math.exp(e.deltaY*.001)));drawCloud()};
new ResizeObserver(()=>{draw()}).observe($('mapArea'));
(async()=>{try{const key=new URLSearchParams(location.hash.slice(1)).get('key');if(key){history.replaceState(null,'',location.pathname);await api('login',{key})}await poll()}catch(e){if(!$('login').open)$('login').showModal()}})();
