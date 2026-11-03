import test from 'node:test';
import assert from 'node:assert/strict';
import Ajv from 'ajv';
import {schemas} from '../platform/schema-spec.mjs';
import {f,v,record,createFinding,actionFromFinding,ncrFromFinding,transitionNcr,completeCapa,closeAction,pendingSuggestions,structureNote,summary,recordCsv,ncrFromInspection} from '../platform/domain.mjs';
import {seeds,demoPhoto} from '../platform/seed.mjs';
const ajv=new Ajv({strict:true,allowUnionTypes:true});
const check=Object.fromEntries(Object.entries(schemas).map(([k,s])=>[k,ajv.compile(s)]));
function validDraft(){const finding=createFinding({walkId:'walk',plantId:'plant-a',note:'Quality scratch',photo:demoPhoto()});const ncr=ncrFromFinding(finding);
  Object.assign(ncr.fields,{part:f('Owned cap'),qtyInspected:f(4),qtyRejected:f(1),defectCode:f('Surface mark'),suspectedSource:f('Handling')});Object.values(ncr.fields).forEach(x=>x.confirmed=true);return ncr;}
test('every seeded record conforms to its versioned contract and field provenance',()=>{
  for(const {record:r}of seeds(new Date('2026-11-04T10:00:00Z'))){const validate=check[r.schemaVersion.split('.')[0]];assert.ok(validate(r),JSON.stringify(validate.errors));for(const field of Object.values(r.fields))assert.ok(['detector','rule','asr','human'].includes(field.source));}
});
test('contracts reject missing source, unknown fields and invalid role',()=>{
  const draft=validDraft();delete draft.fields.note.source;assert.equal(check.NcrRecord(draft),false);
  const action=actionFromFinding(createFinding({walkId:'w',plantId:'plant-a',note:'minor tidy'}));action.fields.ownerRole=f('admin');assert.equal(check.Action(action),false);
  const walk=record('Walk',{plantId:f('plant-a'),template:f('Gemba'),status:f('active'),checklist:f([]),endedAt:f(null)});assert.ok(check.Walk(walk));walk.fields.unexpected=f('x');assert.equal(check.Walk(walk),false);
});
test('rule suggestions retain provenance and due defaults; ASR is unconfirmed',()=>{
  const fields=structureNote('Urgent unsafe guard at Assembly A','plant-a',new Date('2026-11-04T00:00:00Z'));
  assert.equal(fields.severity.value,'high');assert.equal(fields.dueDate.value,'2026-11-05');assert.equal(fields.station.source,'rule');
  const finding=createFinding({walkId:'w',plantId:'plant-a',note:'scratch',noteSource:'asr'});assert.ok(pendingSuggestions(finding).includes('note'));
});
test('inspector can submit but cannot disposition; original and audit remain immutable',()=>{
  const original=validDraft(),submitted=transitionNcr(original,'submitted','inspector');assert.equal(v(original,'status'),'draft');assert.equal(v(submitted.next,'status'),'submitted');assert.ok(check.AuditEvent(submitted.event));
  submitted.next.fields.disposition=f('rework');assert.throws(()=>transitionNcr(submitted.next,'dispositioned','inspector'),/role required/);
  assert.equal(v(transitionNcr(submitted.next,'dispositioned','qa_lead').next,'status'),'dispositioned');
});
test('submit rejects unconfirmed inference, missing human quantities and invalid defect code',()=>{
  let draft=validDraft();draft.fields.station.confirmed=false;draft.fields.station.source='rule';assert.throws(()=>transitionNcr(draft,'submitted','inspector'),/Confirm/);
  draft=validDraft();draft.fields.qtyRejected=f(5);assert.throws(()=>transitionNcr(draft,'submitted','inspector'),/quantities/);
  draft=validDraft();draft.fields.defectCode=f('Invented code');assert.throws(()=>transitionNcr(draft,'submitted','inspector'),/plant/);
});
test('cannot close action without after photo or wrong owner role',()=>{
  const action=actionFromFinding(createFinding({walkId:'w',plantId:'plant-a',note:'quality mark'}));assert.throws(()=>closeAction(action,null,'qa_lead'),/after photo/);
  assert.throws(()=>closeAction(action,demoPhoto(),'inspector'),/owner role/);assert.equal(v(closeAction(action,demoPhoto(),'qa_lead'),'status'),'closed');
});
test('full NCR lifecycle requires completed CAPA and linked closed after-photo action',()=>{
  let ncr=transitionNcr(validDraft(),'submitted','inspector').next;ncr.fields.disposition=f('rework');ncr=transitionNcr(ncr,'dispositioned','qa_lead').next;
  Object.assign(ncr.fields,{rootCause:f('Handling example'),capaAction:f('Protect the tray'),capaDueDate:f('2026-11-10')});ncr=transitionNcr(ncr,'capa_open','qa_lead').next;
  assert.throws(()=>transitionNcr(ncr,'closed','qa_lead'),/open CAPA/);
  const action=actionFromFinding(createFinding({walkId:'w',plantId:'plant-a',note:'quality mark'}));action.fields.ncrId=f(ncr.id);
  assert.throws(()=>completeCapa(ncr,[action],demoPhoto(),'qa_lead'),/linked CAPA/);
  const closed=closeAction(action,demoPhoto(),'qa_lead');ncr=completeCapa(ncr,[closed],demoPhoto(),'qa_lead');ncr=transitionNcr(ncr,'closed','qa_lead',{actions:[closed]}).next;assert.equal(v(ncr,'status'),'closed');assert.ok(check.NcrRecord(ncr));
});
test('only ANOMALY can create a detector NCR and its score is preserved',()=>{
  assert.throws(()=>ncrFromInspection({decision:'GOOD'},'plant-a','Assembly A (demo)'));
  const draft=ncrFromInspection({decision:'ANOMALY',score:.4,threshold:.2,bankVersion:'bank-test',photo:demoPhoto(),heatmap:null,part:'Cap'},'plant-a','Assembly A (demo)');assert.equal(v(draft,'modelScore'),.4);assert.equal(draft.fields.modelScore.source,'detector');assert.equal(v(draft,'qtyInspected'),null);assert.ok(check.NcrRecord(draft));
});
test('seeded dashboard aggregates actual local rows and CSV neutralises formula cells',()=>{
  const rows=seeds(new Date('2026-11-04T00:00:00Z')),data={walks:[],findings:[],actions:[],ncrs:[]};rows.forEach(r=>data[r.store].push(r.record));
  const all=summary(data,null,'2026-11-04'),plant=summary(data,'plant-a','2026-11-04');assert.equal(all.findings,6);assert.equal(plant.findings,3);assert.equal(all.closed,2);assert.equal(all.overdue,2);assert.equal(all.repeatKeys,2);
  const draft=validDraft();draft.fields.note=f('=1+1');assert.match(recordCsv(draft),/'=1\+1/);
});
