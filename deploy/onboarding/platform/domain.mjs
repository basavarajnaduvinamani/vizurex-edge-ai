export const SOURCES=['detector','asr','rule','human'];
export const ROLES=['inspector','qa_lead','plant_manager'];
export const PLANTS=[
  {id:'plant-a',name:'Plant A (demo)',stations:['Assembly A (demo)','Incoming A (demo)','Packing A (demo)'],defects:['Surface mark','Missing component','Wrong label','Other']},
  {id:'plant-b',name:'Plant B (demo)',stations:['Machining B (demo)','Quality B (demo)','Dispatch B (demo)'],defects:['Surface mark','Dimension concern','Wrong label','Other']}
];
export const TEMPLATES={Gemba:['Observe the station and flow','Ask about a current obstacle','Review open actions'],
  '5S':['Sort unnecessary items','Set tools in order','Clean the station','Check standard labels','Review sustain actions'],
  Safety:['Check walkways and access','Check guarding and PPE','Record a hazard or near miss'],
  LPA:['Check the work instruction','Check a critical process step','Check traceability and previous actions']};
export const f=(value,source='human',confirmed=source==='human')=>({value,source,confirmed});
export const v=(record,key)=>record?.fields?.[key]?.value;
export function record(type,fields,{id=crypto.randomUUID(),at=new Date().toISOString(),demo=false}={}){
  return {schemaVersion:`${type}.v1`,id,revision:1,fields:{createdAt:f(at,'rule',true),demo:f(demo,'rule',true),...fields}};
}
export function dueBy(severity,at=new Date()){
  const date=new Date(at);date.setUTCDate(date.getUTCDate()+({high:1,medium:3,low:7}[severity]??3));return date.toISOString().slice(0,10);
}
export function structureNote(note,plantId,at=new Date()){
  const plant=PLANTS.find(p=>p.id===plantId);if(!plant)throw Error('Choose a plant');
  const lower=note.toLowerCase();let category='operations';
  if(/defect|scratch|reject|quality|label|crack|damage/.test(lower))category='quality';
  else if(/hazard|unsafe|guard|injury|blocked|safety/.test(lower))category='safety';
  else if(/clean|clutter|tool|5s|spill/.test(lower))category='5s';
  const severity=/urgent|danger|injury|critical|unsafe|exposed/.test(lower)?'high':/minor|cosmetic|tidy/.test(lower)?'low':'medium';
  const station=plant.stations.find(s=>lower.includes(s.replace(' (demo)','').toLowerCase()))||plant.stations[0];
  return {station:f(station,'rule'),category:f(category,'rule'),severity:f(severity,'rule'),dueDate:f(dueBy(severity,at),'rule'),ownerRole:f(severity==='high'?'plant_manager':'qa_lead','rule')};
}
export function confirmField(field){return {...field,confirmed:true};}
export function createFinding({walkId,plantId,note,noteSource='human',photo=null,checklist=[],at}){
  return record('Finding',{walkId:f(walkId),plantId:f(plantId),note:f(note,noteSource),...structureNote(note,plantId,at),photo:f(photo),checklist:f(checklist),status:f('open','rule',true)},{at});
}
export function actionFromFinding(finding){
  return record('Action',{plantId:structuredClone(finding.fields.plantId),station:structuredClone(finding.fields.station),
    findingId:f(finding.id,'rule',true),ncrId:f(null,'rule',true),title:structuredClone(finding.fields.note),
    ownerRole:structuredClone(finding.fields.ownerRole),dueDate:structuredClone(finding.fields.dueDate),status:f('open','rule',true),afterPhoto:f(null),closedAt:f(null)});
}
export function ncrFromFinding(finding){
  return record('NcrRecord',{plantId:structuredClone(finding.fields.plantId),station:structuredClone(finding.fields.station),
    findingId:f(finding.id,'rule',true),part:f('', 'human'),photo:structuredClone(finding.fields.photo),heatmap:f(null),
    modelDecision:f(null),modelScore:f(null),modelThreshold:f(null),bankVersion:f(null),
    note:structuredClone(finding.fields.note),qtyInspected:f(null),qtyRejected:f(null),defectCode:f(''),suspectedSource:f(''),
    status:f('draft','rule',true),disposition:f(''),rootCause:f(''),capaAction:f(''),capaDueDate:f(''),capaStatus:f('not_open','rule',true),afterPhoto:f(null)});
}
export function ncrFromInspection(detail,plantId,station){
  if(detail.decision!=='ANOMALY')throw Error('Create an inspection NCR only from an ANOMALY result');
  const draft=ncrFromFinding({id:null,fields:{plantId:f(plantId),station:f(station),photo:f(detail.photo),note:f('Review the visual anomaly','rule')}});
  Object.assign(draft.fields,{part:f(detail.part||'','rule'),heatmap:f(detail.heatmap,'detector'),
    modelDecision:f(detail.decision,'detector'),modelScore:f(detail.score,'detector'),modelThreshold:f(detail.threshold,'detector'),
    bankVersion:f(detail.bankVersion,'detector')});return draft;
}
export function pendingSuggestions(entity){return Object.entries(entity.fields).filter(([,field])=>field.source!=='human'&&!field.confirmed).map(([key])=>key);}
export function closeAction(action,afterPhoto,role,at=new Date().toISOString()){
  if(!ROLES.includes(role))throw Error('Choose an actor role');
  if(role!==v(action,'ownerRole')&&role!=='plant_manager')throw Error('Only the owner role or plant manager can close this action');
  if(!afterPhoto?.dataUrl)throw Error('An after photo is required to close an action');
  if(v(action,'status')==='closed')throw Error('Action already closed');
  const next=structuredClone(action);next.revision++;Object.assign(next.fields,{status:f('closed'),afterPhoto:f(afterPhoto),closedAt:f(at)});
  return next;
}
export function transitionNcr(ncr,target,role,{actions=[],at=new Date().toISOString()}={}){
  const next=structuredClone(ncr),from=v(ncr,'status');
  if(!ROLES.includes(role))throw Error('Choose an actor role');
  const allowed={draft:'submitted',submitted:'dispositioned',dispositioned:'capa_open',capa_open:'closed'};
  if(allowed[from]!==target)throw Error(`Cannot move ${from} to ${target}`);
  if(target!=='submitted'&&!['qa_lead','plant_manager'].includes(role))throw Error('QA lead or plant manager role required');
  if(target==='submitted'){
    if(pendingSuggestions(ncr).length)throw Error('Confirm all suggested fields before submitting');
    const inspected=v(ncr,'qtyInspected'),rejected=v(ncr,'qtyRejected');
    if(!Number.isInteger(inspected)||inspected<1||!Number.isInteger(rejected)||rejected<0||rejected>inspected)throw Error('Enter valid inspected/rejected quantities');
    for(const key of ['part','station','defectCode','suspectedSource'])if(!String(v(ncr,key)||'').trim())throw Error(`Enter ${key}`);
    const plant=PLANTS.find(p=>p.id===v(ncr,'plantId'));if(!plant?.defects.includes(v(ncr,'defectCode')))throw Error('Choose a defect code from this plant');
  }
  if(target==='dispositioned'&&!['rework','use-as-is','scrap','return-to-vendor'].includes(v(ncr,'disposition')))throw Error('Choose a disposition');
  if(target==='capa_open'){
    for(const key of ['rootCause','capaAction','capaDueDate'])if(!v(ncr,key))throw Error(`Enter ${key}`);
    next.fields.capaStatus=f('open');
  }
  if(target==='closed'){
    if(v(ncr,'capaStatus')!=='closed')throw Error('NCR cannot close with open CAPA');
    if(!v(ncr,'afterPhoto')?.dataUrl)throw Error('An after photo is required');
    const linked=actions.filter(a=>v(a,'ncrId')===ncr.id);
    if(!linked.length||linked.some(a=>v(a,'status')!=='closed'))throw Error('Close the linked CAPA actions first');
  }
  next.fields.status=f(target);next.revision++;
  const event=record('AuditEvent',{recordId:f(ncr.id,'rule',true),from:f(from,'rule',true),to:f(target),actorRole:f(role),at:f(at,'rule',true)});
  return {next,event};
}
export function completeCapa(ncr,actions,afterPhoto,role){
  if(!['qa_lead','plant_manager'].includes(role))throw Error('QA lead or plant manager role required');
  if(v(ncr,'status')!=='capa_open')throw Error('Open CAPA before completing it');
  if(!afterPhoto?.dataUrl)throw Error('An after photo is required');
  const linked=actions.filter(a=>v(a,'ncrId')===ncr.id);
  if(!linked.length||linked.some(a=>v(a,'status')!=='closed'))throw Error('Close linked CAPA actions first');
  const next=structuredClone(ncr);next.revision++;next.fields.afterPhoto=f(afterPhoto);next.fields.capaStatus=f('closed');return next;
}
export function overdue(action,today=new Date().toISOString().slice(0,10)){return v(action,'status')!=='closed'&&v(action,'dueDate')<today;}
export function csv(rows){
  const esc=value=>{let s=String(value??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  return rows.map(row=>row.map(esc).join(',')).join('\r\n');
}
export function recordCsv(entity){
  return csv([['id','schemaVersion',...Object.keys(entity.fields).flatMap(k=>[k,`${k}.source`,`${k}.confirmed`])],
    [entity.id,entity.schemaVersion,...Object.values(entity.fields).flatMap(field=>[typeof field.value==='object'?JSON.stringify(field.value):field.value,field.source,field.confirmed])]]);
}
export function summary(data,plantId=null,today){
  const filter=items=>items.filter(x=>!plantId||v(x,'plantId')===plantId);
  const walks=filter(data.walks),findings=filter(data.findings),ncrs=filter(data.ncrs),actions=filter(data.actions);
  const tally=(items,key)=>Object.fromEntries([...new Set(items.map(r=>v(r,key)))].map(k=>[k,items.filter(r=>v(r,key)===k).length]));
  const repeats={};findings.forEach(r=>{const key=[v(r,'plantId'),v(r,'station'),v(r,'category')].join(' / ');repeats[key]=(repeats[key]||0)+1;});
  return {walks:walks.length,findings:findings.length,ncrs:ncrs.length,actions:actions.length,
    open:actions.filter(a=>v(a,'status')!=='closed').length,overdue:actions.filter(a=>overdue(a,today)).length,
    closed:actions.filter(a=>v(a,'status')==='closed').length,categories:tally(findings,'category'),defects:tally(ncrs,'defectCode'),
    repeatKeys:Object.values(repeats).filter(n=>n>1).length};
}
