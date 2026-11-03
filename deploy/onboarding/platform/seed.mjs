import {record,f,v,createFinding,actionFromFinding,ncrFromFinding} from './domain.mjs';
export function demoPhoto(){return {dataUrl:'data:image/svg+xml;charset=utf-8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240"><rect width="320" height="240" fill="#747a75"/><circle cx="160" cy="108" r="65" fill="#d2d6cf"/><circle cx="160" cy="108" r="24" fill="#747a75"/><text x="160" y="212" text-anchor="middle" font-family="sans-serif" font-size="18" fill="white">Generated demo data</text></svg>'),width:320,height:240,privacy:{method:'generated illustration',faces:0}};}
export function seeds(at=new Date()){
  const walks=[],findings=[],actions=[],ncrs=[];
  for(const [i,plantId]of ['plant-a','plant-b'].entries()){
    const walk=record('Walk',{plantId:f(plantId,'rule',true),template:f('Gemba','rule',true),status:f('ended','rule',true),checklist:f(['Observe the station and flow'],'rule',true),endedAt:f(at.toISOString(),'rule',true)},{id:`seed-walk-${i}`,demo:true});walks.push(walk);
    for(let j=0;j<3;j++){
      const note=j===0?'Example quality scratch at station':j===1?'Example clutter around tools':'Example quality label issue';
      const finding=createFinding({walkId:walk.id,plantId,note,photo:demoPhoto()});finding.id=`seed-finding-${i}-${j}`;
      finding.fields.demo=f(true,'rule',true);Object.values(finding.fields).forEach(x=>x.confirmed=true);findings.push(finding);
      const action=actionFromFinding(finding);action.id=`seed-action-${i}-${j}`;action.fields.demo=f(true,'rule',true);
      if(j===0){const day=new Date(at);day.setUTCDate(day.getUTCDate()-2);action.fields.dueDate=f(day.toISOString().slice(0,10),'rule',true);}
      if(j===1){action.fields.status=f('closed','rule',true);action.fields.afterPhoto=f(demoPhoto(),'rule',true);action.fields.closedAt=f(at.toISOString(),'rule',true);}
      actions.push(action);
      if(j===0){const ncr=ncrFromFinding(finding);ncr.id=`seed-ncr-${i}`;ncr.fields.demo=f(true,'rule',true);ncr.fields.part=f('Example washer (demo)','rule',true);ncr.fields.defectCode=f('Surface mark','rule',true);ncr.fields.note=f('Fictional quality example; not a measured detector result','rule',true);ncrs.push(ncr);}
    }
  }
  return [...walks.map(record=>({store:'walks',record})),...findings.map(record=>({store:'findings',record})),...actions.map(record=>({store:'actions',record})),...ncrs.map(record=>({store:'ncrs',record}))];
}
