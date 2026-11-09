import {PLANTS,TEMPLATES,ROLES,f,v,record,createFinding,actionFromFinding,ncrFromFinding,ncrFromInspection,pendingSuggestions,transitionNcr,completeCapa,closeAction,overdue,recordCsv,csv,summary} from './domain.mjs';
import {all,saveMany,snapshot,updateNcr} from './store.mjs';
import {seeds} from './seed.mjs';
import {sanitizePhoto} from './privacy.mjs';
import {el,button,option,field,download,notify,safe,$,roleName,facts,tag,statusName,shortDate} from './ui.mjs';
const verdictName=decision=>({GOOD:'OK',ANOMALY:'Defect',RETAKE:'Retake photo'}[decision]||decision);
const round3=value=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(3):value;
const state={plantId:'plant-a',role:'inspector',data:null,walk:null,finding:null,ncr:null,afterPhoto:null,inspection:null,noteSource:'human'};
async function assertRecord(entity){const validators=await import('./validators.mjs');const fn=validators[`validate${entity.schemaVersion.split('.')[0]}`];if(!fn||!fn(entity))throw Error('Record does not match its v1 contract');return entity;}
async function save(entries){await Promise.all(entries.filter(e=>e.store!=='meta').map(e=>assertRecord(e.record)));await saveMany(entries);await refresh();}
async function refresh(){state.data=await snapshot();}
const plant=()=>PLANTS.find(p=>p.id===state.plantId),actor=()=>state.role;
const photoPreview=photo=>photo?.dataUrl?el('figure',{class:'evidence'},el('img',{src:photo.dataUrl,alt:'Locally stored, face-redacted object evidence',width:240}),el('figcaption',{},photo.privacy?.method||'Generated demo data')):el('p',{class:'fine'},'No photo attached');
const photoInput=(id,label='Photo of your own object')=>el('label',{for:id},label,el('input',{id,type:'file',accept:'image/png,image/jpeg,image/webp',capture:'environment'}));
const roleSelect=(id,value)=>{const select=el('select',{id},...ROLES.map(r=>option(r,roleName(r))));select.value=value;return select;};
async function filePhoto(id){const file=$(id)?.files[0];if(!file)throw Error('Choose an after photo of your own object');notify('Checking the photo for faces on this device…');const photo=await sanitizePhoto(file);if(photo.privacy.fullyObscured)notify(photo.privacy.method);return photo;}
function collect(entity,prefix,keys){for(const key of keys){const input=$(`${prefix}-${key}`);if(!input)continue;const old=entity.fields[key],raw=input.value;const value=['qtyInspected','qtyRejected'].includes(key)?raw===''?null:Number(raw):raw;if(value!==old.value){entity.fields[key]=f(value);}else old.value=value;}return entity;}
function confirmAll(entity){Object.values(entity.fields).forEach(field=>field.confirmed=true);}
function auditEvent(id,from,to){return record('AuditEvent',{recordId:f(id,'rule',true),from:f(from,'rule',true),to:f(to),actorRole:f(actor()),at:f(new Date().toISOString(),'rule',true)});}
function route(){const name=location.hash.slice(1)||'home',valid=['home','inspect','walk','ncr','actions','dashboard'];const target=valid.includes(name)?name:'home';
  document.querySelectorAll('[data-view]').forEach(node=>node.hidden=node.dataset.view!==target);
  document.querySelectorAll('[data-route]').forEach(node=>node.setAttribute('aria-current',node.dataset.route===target?'page':'false'));
  const shared=$('inspection-bench');
  if(target==='home'||target==='inspect'){
    const slot=$(target+'-inspection');
    if(shared.parentElement!==slot){
      slot.append(shared);
      if(target==='inspect')$('bank-details').open=true;
    }
  }
  document.querySelector('.context-bar').hidden=target==='home';
  if(state.data)render(target);
}
function navigate(name){location.hash=name;route();}
window.addEventListener('hashchange',route);
route();
function render(view){if(view==='walk')renderWalk();if(view==='ncr')renderNcr();if(view==='actions')renderActions();if(view==='dashboard')renderDashboard();}
function currentWalk(){return state.data.walks.find(w=>w.id===state.walk)||state.data.walks.find(w=>v(w,'plantId')===state.plantId&&v(w,'status')==='active');}
function listOpen(station){const actions=state.data.actions.filter(a=>v(a,'plantId')===state.plantId&&v(a,'station')===station&&v(a,'status')!=='closed');
  return el('div',{class:'open-items'},el('h3',{},`Open items at this station (n=${actions.length})`),actions.length?el('ul',{class:'item-list'},...actions.map(a=>el('li',{},el('strong',{},v(a,'title')),facts([['Owner',roleName(v(a,'ownerRole'))],['Due',v(a,'dueDate')]],overdue(a)?tag('Overdue','alert'):null)))):el('p',{},'No open local items at this station.'));
}
function renderWalk(){
  const box=$('view-walk');box.replaceChildren(el('h1',{},'Walk the production line'),el('p',{class:'fine'},'Plant and station names are fictional demo data. New records stay in IndexedDB on this device.'));
  const walk=currentWalk();
  if(!walk||v(walk,'status')==='ended'){
    const select=el('select',{id:'walk-template'},...Object.keys(TEMPLATES).map(t=>option(t)));
    box.append(el('label',{for:'walk-template'},'Walk template',select),button('Start walk',safe(async()=>{
      const template=$('walk-template').value,r=record('Walk',{plantId:f(state.plantId),template:f(template),status:f('active','rule',true),checklist:f([]),endedAt:f(null)});
      await save([{store:'walks',record:r}]);state.walk=r.id;renderWalk();notify('Walk started on this device.');
    }),{class:'primary',id:'start-walk'}));
    const ended=state.data.walks.filter(w=>v(w,'plantId')===state.plantId&&v(w,'status')==='ended');
    if(ended.length)box.append(el('h2',{},'Saved walk reports'),el('ul',{class:'plain-list'},...ended.map(w=>el('li',{},button(`${v(w,'template')} walk report, ${shortDate(v(w,'createdAt')).slice(0,10)}${v(w,'demo')?' (demo data)':''}`,()=>renderWalkReport(w))))));return;
  }
  state.walk=walk.id;
  box.append(facts([['Walk template',v(walk,'template')],['Plant',plant().name],['Started',shortDate(v(walk,'createdAt'))]]));
  const checklist=el('fieldset',{},el('legend',{},'Checklist'));
  TEMPLATES[v(walk,'template')].forEach((item,i)=>{const input=el('input',{type:'checkbox',id:`walk-item-${i}`,value:item,...(v(walk,'checklist').includes(item)?{checked:true}:{})});input.onchange=safe(async()=>{const next=structuredClone(walk);next.revision++;next.fields.checklist=f(Array.from(checklist.querySelectorAll('input:checked'),x=>x.value));await save([{store:'walks',record:next}]);});checklist.append(el('label',{class:'checkbox'},input,item));});box.append(checklist);
  const station=el('select',{id:'walk-station'},...plant().stations.map(s=>option(s)));box.append(el('label',{for:'walk-station'},'Station',station));
  const open=el('div',{id:'station-open'});const showOpen=()=>open.replaceChildren(listOpen(station.value));station.onchange=showOpen;showOpen();box.append(open);
  box.append(photoInput('finding-photo'),el('label',{for:'finding-note'},'Finding note',el('textarea',{id:'finding-note',rows:3,placeholder:'Describe what you observed; no people or private details.'})),
    button('Start voice note',startVoice,{id:'voice-note'}),el('p',{class:'fine',id:'voice-hint'},'Optional browser speech recognition may use your browser provider. Typing stays local. Review every transcript.'),
    button('Structure finding',safe(async()=>{
      const note=$('finding-note').value.trim();if(!note)throw Error('Describe the finding first');
      const photo=$('finding-photo').files.length?await filePhoto('finding-photo'):null;
      const finding=createFinding({walkId:walk.id,plantId:state.plantId,note,noteSource:state.noteSource,photo,checklist:v(walk,'checklist')});
      finding.fields.station=f(station.value);state.finding=finding;renderFindingDraft();
    }),{class:'primary',id:'structure-finding'}));
  $('finding-note').addEventListener('input',()=>state.noteSource='human');
  box.append(el('div',{id:'finding-draft'}));if(state.finding)renderFindingDraft();
  const items=state.data.findings.filter(r=>v(r,'walkId')===walk.id);
  box.append(el('h2',{},`Findings in this walk (n=${items.length})`),...items.map(finding=>findingLine(finding)),
    button('End walk and show report',safe(async()=>{const next=structuredClone(currentWalk());next.revision++;next.fields.status=f('ended');next.fields.endedAt=f(new Date().toISOString());await save([{store:'walks',record:next}]);renderWalkReport(next);}),{id:'end-walk'}));
}
function renderFindingDraft(){
  const finding=state.finding,box=$('finding-draft');if(!box||!finding)return;
  box.replaceChildren(el('h2',{},'Review the structured finding'),el('p',{class:'fine'},'Suggested values keep their rule/ASR source until you confirm or edit them.'),
    field('Note','finding-edit-note',finding.fields.note,{type:'textarea'}),field('Station','finding-edit-station',finding.fields.station,{options:plant().stations}),
    field('Category','finding-edit-category',finding.fields.category,{options:['quality','safety','5s','operations']}),field('Severity','finding-edit-severity',finding.fields.severity,{options:['low','medium','high']}),
    field('Owner role','finding-edit-ownerRole',finding.fields.ownerRole,{options:ROLES.map(value=>({value,label:roleName(value)}))}),field('Due date','finding-edit-dueDate',finding.fields.dueDate,{type:'date'}),photoPreview(v(finding,'photo')),
    button('Confirm suggested fields',()=>{collect(finding,'finding-edit',['note','station','category','severity','ownerRole','dueDate']);confirmAll(finding);renderFindingDraft();},{id:'confirm-finding'}),
    button('Save finding',safe(async()=>{
      collect(finding,'finding-edit',['note','station','category','severity','ownerRole','dueDate']);
      if(pendingSuggestions(finding).length)throw Error('Confirm or edit suggested fields first');
      if(!v(finding,'note').trim()||!v(finding,'dueDate'))throw Error('Note and due date are required');
      const action=actionFromFinding(finding);await save([{store:'findings',record:finding,addOnly:true},{store:'actions',record:action,addOnly:true}]);state.finding=null;state.noteSource='human';renderWalk();notify('Finding and owner action saved locally.');
    }),{class:'primary',id:'save-finding'}));
}
function startVoice(){
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Recognition){notify('Speech recognition is unavailable here. Type the note instead.');return;}
  const recognition=new Recognition();recognition.lang='en-IN';recognition.continuous=false;recognition.interimResults=false;
  recognition.onresult=event=>{$('finding-note').value=event.results[0][0].transcript;state.noteSource='asr';notify('Transcript added. Review it before confirming.');};
  recognition.onerror=()=>notify('Speech recognition did not finish. Type the note instead.',true);
  recognition.start();notify('Listening. Tap stop in your browser to cancel.');
}
function findingLine(finding){return el('article',{class:'record-row'},el('h3',{},v(finding,'note')),facts([['Station',v(finding,'station')],['Category',v(finding,'category')],['Severity',v(finding,'severity')]],v(finding,'demo')?tag('Demo data'):null),
  v(finding,'category')==='quality'?button('Create NCR',safe(()=>createNcr(finding)),{'data-finding-id':finding.id}):null);}
async function createNcr(finding){
  const existing=state.data.ncrs.find(n=>v(n,'findingId')===finding.id);if(existing){state.ncr=existing.id;navigate('ncr');return;}
  const draft=ncrFromFinding(finding),entries=[{store:'ncrs',record:draft,addOnly:true},{store:'audit',record:auditEvent(draft.id,'none','draft')}];
  for(const action of state.data.actions.filter(a=>v(a,'findingId')===finding.id)){const next=structuredClone(action);next.revision++;next.fields.ncrId=f(draft.id,'rule',true);entries.push({store:'actions',record:next});}
  await save(entries);state.ncr=draft.id;state.afterPhoto=null;navigate('ncr');notify('NCR draft created. Enter the human quantity and defect fields.');
}
function renderWalkReport(walk){
  const items=state.data.findings.filter(r=>v(r,'walkId')===walk.id),actions=state.data.actions.filter(a=>items.some(r=>v(a,'findingId')===r.id));
  const text=[`${v(walk,'template')} walk at ${PLANTS.find(p=>p.id===v(walk,'plantId'))?.name}`,`Local prototype report; ${items.length} findings`,...items.map((r,i)=>`${i+1}. ${v(r,'station')}: ${v(r,'note')} [${v(r,'category')}/${v(r,'severity')}] Owner: ${roleName(v(r,'ownerRole'))}; due ${v(r,'dueDate')}.`),`Open actions: ${actions.filter(a=>v(a,'status')!=='closed').length}. Fictional demo plants; not a factory pilot.`].join('\n');
  const report=el('section',{id:'walk-report',class:'print-report'},el('h1',{},`${v(walk,'template')} walk report`),facts([['Plant',PLANTS.find(p=>p.id===v(walk,'plantId'))?.name],['Created',shortDate(v(walk,'createdAt'))]]),el('p',{},`Findings n=${items.length}; linked actions n=${actions.length}. All plant names are demo data.`),...items.map(findingLine));
  $('view-walk').replaceChildren(report,el('div',{class:'report-tools'},button('Copy for WhatsApp',safe(async()=>{await navigator.clipboard.writeText(text);notify('Summary copied. Nothing was sent.');}),{id:'copy-walk'}),button('Export walk CSV',()=>download(`walk-${walk.id}.csv`,csv([['finding_id','station','note','category','severity','owner','due'],...items.map(r=>[r.id,v(r,'station'),v(r,'note'),v(r,'category'),v(r,'severity'),v(r,'ownerRole'),v(r,'dueDate')])]),'text/csv'),{id:'walk-csv'}),button('Print one-page report',()=>window.print()),button('Back to walks',renderWalk)));
}
const ncrEditable=['part','note','qtyInspected','qtyRejected','defectCode','suspectedSource','disposition','rootCause','capaAction','capaDueDate'];
function currentNcr(){return state.data.ncrs.find(n=>n.id===state.ncr)||state.data.ncrs.filter(n=>v(n,'plantId')===state.plantId).at(-1);}
function ncrFields(ncr){return collect(ncr,'ncr',ncrEditable);}
function renderNcr(){
  const box=$('view-ncr');box.replaceChildren(el('h1',{},'Nonconformance reports'),el('p',{class:'fine'},'Local role checks demonstrate workflow rules; this is not multi-user authentication. Export compatibility with WCTE’s NCR app is not yet verified.'));
  const records=state.data.ncrs.filter(n=>v(n,'plantId')===state.plantId);
  if(!records.length){box.append(el('p',{},'Create an NCR from a quality finding on a walk, or from a Defect result in Inspect.'));return;}
  const selected=currentNcr();if(!selected||v(selected,'plantId')!==state.plantId){state.ncr=records.at(-1).id;return renderNcr();}state.ncr=selected.id;
  const select=el('select',{id:'ncr-select'},...records.map((n,i)=>option(n.id,`NCR ${i+1}: ${v(n,'part')||'Untitled part'}, ${statusName(v(n,'status'))}${v(n,'demo')?' (demo data)':''}`)));select.value=selected.id;select.onchange=()=>{state.ncr=select.value;state.afterPhoto=null;renderNcr();};
  box.append(el('label',{for:'ncr-select'},'NCR record',select),el('p',{class:'status-line',id:'ncr-state'},`Status: ${statusName(v(selected,'status'))}. CAPA: ${statusName(v(selected,'capaStatus'))}. Revision ${selected.revision}.`));
  const draft=structuredClone(selected),fields=el('div',{id:'ncr-fields'}),closed=v(selected,'status')==='closed';
  fields.append(field('Part','ncr-part',draft.fields.part,{readonly:closed}),field('Station','ncr-station',draft.fields.station,{readonly:true}),field('Note','ncr-note',draft.fields.note,{type:'textarea',readonly:closed}),
    field('Quantity inspected','ncr-qtyInspected',draft.fields.qtyInspected,{type:'number',readonly:closed}),field('Quantity rejected','ncr-qtyRejected',draft.fields.qtyRejected,{type:'number',readonly:closed}),
    field('Defect code','ncr-defectCode',draft.fields.defectCode,{options:[{value:'',label:'Choose a defect code'},...plant().defects]}),field('Suspected source','ncr-suspectedSource',draft.fields.suspectedSource,{readonly:closed}));
  if(v(selected,'modelDecision'))fields.append(el('div',{class:'strong-result'},facts([['Detector verdict',verdictName(v(selected,'modelDecision'))],['Score',round3(v(selected,'modelScore'))],['Threshold',round3(v(selected,'modelThreshold'))]]),el('p',{class:'fine'},`Original bank: ${v(selected,'bankVersion')}. Model score is not confidence. Source: detector.`)));
  fields.append(photoPreview(v(selected,'photo')));
  if(v(selected,'heatmap'))fields.append(el('img',{class:'heatmap-evidence',src:v(selected,'heatmap'),alt:'Privacy-redacted detector heatmap',width:224}));
  box.append(fields);
  if(!closed)box.append(button('Confirm suggested NCR fields',()=>{ncrFields(draft);confirmAll(draft);Object.assign(selected.fields,draft.fields);renderNcr();notify('Suggestions confirmed; save or transition to persist.');},{id:'confirm-ncr'}),
    button('Save NCR draft edits',safe(async()=>{if(v(selected,'status')!=='draft')throw Error('Use the lifecycle controls for submitted records');ncrFields(draft);draft.revision++;await updateNcr(await assertRecord(draft),await assertRecord(auditEvent(draft.id,'draft','draft_edit')));await refresh();renderNcr();notify('Draft edits saved.');}),{id:'save-ncr'}));
  const status=v(selected,'status');
  const transitionButton=(label,target)=>button(label,safe(async()=>{
    ncrFields(draft);const {next,event}=transitionNcr(draft,target,actor(),{actions:state.data.actions});
    const additional=[];
    if(target==='capa_open'){
      const linked=record('Action',{plantId:structuredClone(next.fields.plantId),station:structuredClone(next.fields.station),findingId:structuredClone(next.fields.findingId),ncrId:f(next.id,'rule',true),title:structuredClone(next.fields.capaAction),ownerRole:f('qa_lead','rule',true),dueDate:structuredClone(next.fields.capaDueDate),status:f('open','rule',true),afterPhoto:f(null),closedAt:f(null)});additional.push({store:'actions',record:await assertRecord(linked)});
    }
    await updateNcr(await assertRecord(next),await assertRecord(event),additional);await refresh();
    if(target==='closed'&&v(next,'findingId')){const finding=state.data.findings.find(r=>r.id===v(next,'findingId'));if(finding){const item=structuredClone(finding);item.revision++;item.fields.status=f('closed');await save([{store:'findings',record:item}]);}}
    renderNcr();notify(`NCR moved to ${target}.`);
  }),{class:'primary',id:`ncr-${target}`});
  if(status==='draft')box.append(transitionButton('Submit NCR','submitted'));
  if(status==='submitted')box.append(field('Disposition','ncr-disposition',draft.fields.disposition,{options:[{value:'',label:'Choose disposition'},'rework','use-as-is','scrap','return-to-vendor']}),transitionButton('Apply disposition','dispositioned'));
  if(status==='dispositioned')box.append(field('Root cause','ncr-rootCause',draft.fields.rootCause,{type:'textarea'}),field('CAPA action','ncr-capaAction',draft.fields.capaAction,{type:'textarea'}),field('CAPA due date','ncr-capaDueDate',draft.fields.capaDueDate,{type:'date'}),transitionButton('Open CAPA','capa_open'));
  if(status==='capa_open'){
    const linked=state.data.actions.filter(a=>v(a,'ncrId')===selected.id);
    box.append(el('h2',{},`Linked actions (n=${linked.length})`),el('ul',{class:'item-list'},...linked.map(a=>el('li',{},el('strong',{},v(a,'title')),facts([['Owner',roleName(v(a,'ownerRole'))],['Status',statusName(v(a,'status'))]])))),photoInput('ncr-after-photo','After photo for action/CAPA closure'),state.afterPhoto?photoPreview(state.afterPhoto):null,
      button('Close linked actions with after photo',safe(async()=>{
        state.afterPhoto=await filePhoto('ncr-after-photo');const entries=[];
        for(const action of linked.filter(a=>v(a,'status')!=='closed'))entries.push({store:'actions',record:closeAction(action,state.afterPhoto,actor())},{store:'audit',record:auditEvent(action.id,'open','action_closed')});
        if(!entries.length)throw Error('All linked actions are already closed');await save(entries);renderNcr();notify('Linked actions closed with redacted evidence.');
      }),{id:'close-linked-actions'}),
      button('Complete CAPA',safe(async()=>{
        const photo=state.afterPhoto||await filePhoto('ncr-after-photo');const next=completeCapa(selected,state.data.actions,photo,actor());
        await updateNcr(await assertRecord(next),await assertRecord(auditEvent(next.id,'capa_open','capa_complete')));await refresh();renderNcr();notify('CAPA completed. Review and close the NCR.');
      }),{id:'complete-capa'}),transitionButton('Close NCR','closed'));
  }
  const log=state.data.audit.filter(r=>v(r,'recordId')===selected.id).sort((a,b)=>v(a,'at').localeCompare(v(b,'at')));
  box.append(el('h2',{},`Append-only local audit log (n=${log.length})`),el('ol',{id:'ncr-audit'},...log.map(r=>el('li',{},`${shortDate(v(r,'at'))}, ${roleName(v(r,'actorRole'))}: ${statusName(v(r,'from'))} to ${statusName(v(r,'to'))}`))),
    button('Export NcrRecord v1 JSON',()=>download(`NCR-${selected.id}.json`,JSON.stringify(selected,null,2),'application/json'),{id:'ncr-json'}),button('Export NCR CSV',()=>download(`NCR-${selected.id}.csv`,recordCsv(selected),'text/csv'),{id:'ncr-csv'}));
}
function renderActions(){
  const box=$('view-actions'),items=state.data.actions.filter(a=>v(a,'plantId')===state.plantId);box.replaceChildren(el('h1',{},'Corrective actions'),el('p',{},`Local actions n=${items.length}. Overdue flags are rule-based; no notifications are sent.`));
  for(const action of items){
    const row=el('article',{class:'record-row'},el('h2',{},v(action,'title')),facts([['Station',v(action,'station')],['Owner',roleName(v(action,'ownerRole'))],['Due',v(action,'dueDate')],['Status',statusName(v(action,'status'))]],overdue(action)?tag('Overdue: escalates to plant manager','alert'):null,v(action,'demo')?tag('Demo data'):null));
    if(v(action,'status')!=='closed'){
      const id=`action-photo-${action.id}`;row.append(photoInput(id,'After photo'),button('Close action',safe(async()=>{const photo=await filePhoto(id);await save([{store:'actions',record:closeAction(action,photo,actor())},{store:'audit',record:auditEvent(action.id,'open','action_closed')}]);renderActions();notify('Action closed with after-photo evidence.');}),{class:'primary','data-action':action.id}));
    }else row.append(photoPreview(v(action,'afterPhoto')));box.append(row);
  }
}
function renderDashboard(){
  const box=$('view-dashboard'),scope=el('select',{id:'dashboard-scope'},option('plant','Selected plant'),option('network','Demo network aggregates'));
  box.replaceChildren(el('h1',{},'Plant and network view'),el('p',{class:'notice'},'Demo data: two fictional plants and stations. Counts below are local seeded examples plus your local entries, not deployment or impact metrics.'),el('label',{for:'dashboard-scope'},'Dashboard scope',scope),el('div',{id:'dashboard-results'}));
  const draw=()=>{
    const network=scope.value==='network',result=summary(state.data,network?null:state.plantId),data=network?state.data.findings:state.data.findings.filter(finding=>v(finding,'plantId')===state.plantId),seeded=data.filter(r=>v(r,'demo')).length;
    const target=$('dashboard-results');target.replaceChildren(el('h2',{},network?'Network: aggregate counts only':plant().name),el('p',{},`Finding records n=${result.findings}: seeded demo data n=${seeded}; local entries n=${result.findings-seeded}.`));
    const dl=el('dl',{class:'metrics'});for(const [label,key]of [['Walks','walks'],['Findings','findings'],['NCRs','ncrs'],['Actions','actions'],['Open actions','open'],['Overdue actions','overdue'],['Closed actions','closed'],['Repeated station and category','repeatKeys']]){dl.append(el('div',{},el('dt',{},label),el('dd',{},`n=${result[key]}`)));}target.append(dl);
    for(const [title,counts]of [['Findings by category',result.categories],['NCRs by defect code',result.defects]])target.append(el('h3',{},title),el('dl',{class:'metrics'},...Object.entries(counts).map(([key,count])=>el('div',{},el('dt',{},key||'Not entered'),el('dd',{},`n=${count}`)))));
    target.append(el('p',{class:'fine'},'A repeat is the same plant/station/category key occurring more than once; it is not an inferred root cause. The network view does not expose notes or photos.'));
  };scope.onchange=draw;draw();
}
window.addEventListener('visurex:inspection',event=>{
  state.inspection=event.detail;let entry=$('inspect-create-ncr');if(!entry){entry=button('Create NCR from this anomaly',safe(async()=>{
    if(!state.inspection||state.inspection.decision!=='ANOMALY')throw Error('Inspect an anomalous image first');
    notify('Checking inspection evidence for faces before saving…');
    const photo=await sanitizePhoto(state.inspection.photo),overlay=await sanitizePhoto(state.inspection.heatmap);
    const draft=ncrFromInspection({...state.inspection,photo,heatmap:overlay.dataUrl},state.plantId,plant().stations[0]);
    await save([{store:'ncrs',record:draft,addOnly:true},{store:'audit',record:auditEvent(draft.id,'none','draft')}]);state.ncr=draft.id;state.afterPhoto=null;navigate('ncr');notify('Inspection NCR drafted. Enter human quantities and defect information.');
  }),{id:'inspect-create-ncr'});$('result').after(entry);}
  entry.hidden=event.detail.decision!=='ANOMALY';
});
const plantSelect=$('context-plant'),role=$('context-role');
PLANTS.forEach(p=>plantSelect.append(option(p.id,p.name)));ROLES.forEach(r=>role.append(option(r,roleName(r))));
plantSelect.onchange=()=>{state.plantId=plantSelect.value;state.walk=null;state.finding=null;state.ncr=null;state.afterPhoto=null;route();};
role.onchange=()=>{state.role=role.value;route();notify(`Role: ${roleName(state.role)}. Prototype checks only.`);};
try{
  const meta=await all('meta');if(!meta.some(r=>r.id==='seed-v1'))await saveMany([...seeds(),{store:'meta',record:{id:'seed-v1',createdAt:new Date().toISOString()}}]);
  await refresh();route();
}catch(error){notify(`Local storage unavailable: ${error.message}. Inspect still works without records.`,true);}
// Diagnostics for schema/IndexedDB acceptance, not an unauthenticated server API.
window.visurexPlatform={snapshot,schemasVersion:1,getState:()=>({plantId:state.plantId,role:state.role}),assertRecord};
