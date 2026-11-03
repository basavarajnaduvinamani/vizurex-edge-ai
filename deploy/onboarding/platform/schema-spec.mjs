const text={type:'string'},nullableText={type:['string','null']},photo={type:['object','null'],additionalProperties:true};
const enumeration=(...values)=>({enum:values});
const common={createdAt:text,demo:{type:'boolean'}};
const parts={
  Walk:{plantId:text,template:enumeration('Gemba','5S','Safety','LPA'),status:enumeration('active','ended'),checklist:{type:'array',items:text},endedAt:nullableText},
  Finding:{walkId:nullableText,plantId:text,note:text,station:text,category:enumeration('quality','safety','5s','operations'),severity:enumeration('low','medium','high'),dueDate:text,ownerRole:enumeration('inspector','qa_lead','plant_manager'),photo,checklist:{type:'array',items:text},status:enumeration('open','closed')},
  NcrRecord:{plantId:text,station:text,findingId:nullableText,part:text,photo,heatmap:{type:['string','null']},modelDecision:{enum:['ANOMALY',null]},modelScore:{type:['number','null']},modelThreshold:{type:['number','null']},bankVersion:nullableText,note:text,qtyInspected:{type:['integer','null'],minimum:0},qtyRejected:{type:['integer','null'],minimum:0},defectCode:text,suspectedSource:text,status:enumeration('draft','submitted','dispositioned','capa_open','closed'),disposition:text,rootCause:text,capaAction:text,capaDueDate:text,capaStatus:enumeration('not_open','open','closed'),afterPhoto:photo},
  Action:{plantId:text,station:text,findingId:nullableText,ncrId:nullableText,title:text,ownerRole:enumeration('inspector','qa_lead','plant_manager'),dueDate:text,status:enumeration('open','closed'),afterPhoto:photo,closedAt:nullableText},
  CaptureEvent:{plantId:text,station:text,origin:enumeration('phone','glasses','generated'),photo,note:text,decision:{enum:['GOOD','ANOMALY','RETAKE',null]},modelScore:{type:['number','null']},bankVersion:nullableText},
  AuditEvent:{recordId:text,from:text,to:text,actorRole:enumeration('inspector','qa_lead','plant_manager'),at:text}
};
export const schemas=Object.fromEntries(Object.entries(parts).map(([name,fields])=>{
  const properties=Object.fromEntries(Object.entries({...common,...fields}).map(([key,value])=>[key,{type:'object',additionalProperties:false,required:['value','source','confirmed'],properties:{value,source:enumeration('detector','asr','rule','human'),confirmed:{type:'boolean'}}}]));
  return [name,{$schema:'http://json-schema.org/draft-07/schema#',$id:`${name}.v1`,title:`VisureX ${name} v1`,type:'object',additionalProperties:false,required:['schemaVersion','id','revision','fields'],properties:{schemaVersion:{const:`${name}.v1`},id:{type:'string',minLength:1},revision:{type:'integer',minimum:1},fields:{type:'object',additionalProperties:false,required:Object.keys(properties),properties}}}];
}));
