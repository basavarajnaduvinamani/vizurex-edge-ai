import {freezeCalibration,qualityFromGray,verdict} from './core.mjs';
const $=id=>document.getElementById(id);
const manifest=await fetch('samples.json').then(r=>r.json());
const state={session:null,scorer:null,bank:null,frozen:null,ready:false,busy:false,records:[],pixels:new Map()};
const mean=[.485,.456,.406],std=[.229,.224,.225];
const repo='https://github.com/basavarajnaduvinamani/vizurex-edge-ai/blob/claude/sprint-2026-11-01/docs/';
function message(s){$('status').textContent=s;}
function lock(busy){state.busy=busy;$('teach').disabled=busy;$('check').disabled=busy||!state.ready;$('part').disabled=busy;}
function clearBank(){state.bank=null;state.frozen=null;state.ready=false;$('check').disabled=true;$('result').textContent='Build a memory bank before inspecting.';$('overlay').hidden=true;}
$('part').onchange=()=>{clearBank();$('uploads').hidden=$('part').value!=='own';renderThumbs();};
$('references').onchange=()=>{clearBank();renderThumbs();};$('calibration').onchange=clearBank;
$('sample').onchange=()=>{$('test-upload').hidden=$('sample').value!=='own';};
$('theme').onclick=()=>{const dark=getComputedStyle(document.body).getPropertyValue('--bg').trim()==='#151b18';document.body.dataset.theme=dark?'light':'dark';$('theme').textContent=dark?'Dark mode':'Light mode';};
function renderThumbs(){
  $('thumbs').replaceChildren();
  const own=$('part').value==='own',refs=own?Array.from($('references').files):manifest.references;
  for(const [i,ref]of refs.entries()){
    const img=document.createElement('img');
    img.src=own?URL.createObjectURL(ref):ref.path;if(own)img.onload=()=>URL.revokeObjectURL(img.src);
    img.alt=`${own?'Uploaded':'Generated'} normal reference ${i+1}`;img.width=80;img.height=80;$('thumbs').append(img);
  }
}
renderThumbs();
async function imageData(source){
  if(source instanceof File && (source.size>20*1024*1024 || !['image/jpeg','image/png','image/webp'].includes(source.type))) throw Error('Use JPEG, PNG or WebP up to 20 MB.');
  const blob=source instanceof File?source:await fetch(source).then(r=>{if(!r.ok)throw Error('Image unavailable');return r.blob();});
  const bitmap=await createImageBitmap(blob);
  if(bitmap.width*bitmap.height>24000000){bitmap.close();throw Error('Image exceeds the 24-megapixel demo limit.');}
  const canvas=document.createElement('canvas');canvas.width=canvas.height=224;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  const scale=256/Math.min(bitmap.width,bitmap.height),w=Math.floor(bitmap.width*scale),h=Math.floor(bitmap.height*scale);
  // Match crop geometry of resize-short-edge 256 then centre crop 224.
  const resized=document.createElement('canvas');resized.width=w;resized.height=h;
  const rc=resized.getContext('2d');rc.drawImage(bitmap,0,0,w,h);
  ctx.drawImage(resized,Math.round((w-224)/2),Math.round((h-224)/2),224,224,0,0,224,224);
  const rgba=ctx.getImageData(0,0,224,224).data,gray=new Uint8Array(224*224),tensor=new Float32Array(3*224*224);
  for(let i=0;i<gray.length;i++){
    gray[i]=Math.round(.299*rgba[4*i]+.587*rgba[4*i+1]+.114*rgba[4*i+2]);
    for(let c=0;c<3;c++)tensor[c*gray.length+i]=(rgba[4*i+c]/255-mean[c])/std[c];
  }
  const quality=qualityFromGray(gray,224,224,bitmap.width,bitmap.height);bitmap.close();
  return {tensor,quality,canvas,png:canvas.toDataURL('image/png')};
}
async function runtime(){
  if(state.session)return;
  const ort=window.ort;if(!ort)throw Error('ONNX Runtime could not load.');
  ort.env.wasm.wasmPaths=new URL('ort/',location.href).href;ort.env.wasm.numThreads=1;
  state.session=await ort.InferenceSession.create('dinov2-vits14.onnx',{executionProviders:['wasm'],graphOptimizationLevel:'all'});
  state.scorer=await ort.InferenceSession.create('score.onnx',{executionProviders:['wasm'],graphOptimizationLevel:'all'});
}
async function embed(input){
  const started=performance.now();
  const output=await state.session.run({image:new window.ort.Tensor('float32',input.tensor,[1,3,224,224])});
  return {features:output.patches.data.slice(),ms:performance.now()-started};
}
async function score(features,bank=state.bank){
  const out=await state.scorer.run({patches:new window.ort.Tensor('float32',features,[256,384]),bank:new window.ort.Tensor('float32',bank,[bank.length/384,384])});
  return {score:out.score.data[0],distances:Array.from(out.distances.data)};
}
async function fileId(file){const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());return Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');}
async function onboard(){
  if(state.busy)throw Error('Wait for the current operation');
  lock(true);clearBank();const start=performance.now();
  try{
    let refs=manifest.references.map(x=>x.path),cal=manifest.calibration.map(x=>x.path);
    if($('part').value==='own'){
      refs=Array.from($('references').files);cal=Array.from($('calibration').files);
      if(refs.length!==8||cal.length<2||cal.length>16)throw Error('Choose exactly eight normal references and 2–16 separate normal calibration photos.');
    }
    const ids=await Promise.all([...refs,...cal].map(x=>x instanceof File?fileId(x):Promise.resolve(x)));
    if(new Set(ids).size!==ids.length)throw Error('Duplicate photos: references and calibration must be distinct.');
    message('Loading pretrained model and building the bank locally…');
    await runtime();const features=[];
    for(let i=0;i<refs.length;i++){
      const input=await imageData(refs[i]);if(!input.quality.passed)throw Error(`Reference ${i+1}: RETAKE — ${input.quality.reasons.join(' ')}`);
      features.push((await embed(input)).features);state.pixels.set(ids[i],input.png);message(`Reference ${i+1} of 8 encoded locally…`);
    }
    const bank=new Float32Array(8*256*384);features.forEach((v,i)=>bank.set(v,i*v.length));
    const calibration=[];
    for(let i=0;i<cal.length;i++){
      const input=await imageData(cal[i]);if(!input.quality.passed)throw Error(`Calibration ${i+1}: RETAKE — ${input.quality.reasons.join(' ')}`);
      calibration.push((await score((await embed(input)).features,bank)).score);state.pixels.set(ids[8+i],input.png);
      message(`Normal calibration ${i+1} of ${cal.length}…`);
    }
    state.frozen=freezeCalibration(calibration,ids.slice(0,8),ids.slice(8));state.bank=bank;state.ready=true;
    state.calibrationScores=calibration;state.onboardingMs=performance.now()-start;
    message(`Bank ready: 8 references + ${cal.length} separate normal calibration photos. Frozen threshold ${state.frozen.threshold.toFixed(6)}. Onboarding ${(state.onboardingMs/1000).toFixed(1)} s.`);
  }catch(error){clearBank();message(`Unable to onboard: ${error.message}`);throw error;}
  finally{lock(false);}
}
function sourceFor(name){return name==='dark'||name==='blur'?`samples/${name}.png`:`samples/test-${name}-200.png`;}
async function inspect(source,render=true){
  if(!state.ready)throw Error('Build a bank first');
  const begin=performance.now(),input=await imageData(source);
  let output,embedMs=null;
  if(!input.quality.passed)output=verdict(null,state.frozen,input.quality);
  else{const embedding=await embed(input);embedMs=embedding.ms;const scored=await score(embedding.features);output={...verdict(scored.score,state.frozen,input.quality),distances:scored.distances};}
  const record={...output,quality:input.quality,latencyMs:performance.now()-begin,embedMs,source:source instanceof File?null:source};
  if(!(source instanceof File)) {state.pixels.set(source,input.png);state.records.push(record);}
  if(render){
    const result=$('result');result.replaceChildren();const title=document.createElement('strong');title.textContent=record.decision;result.append(title);
    const description=document.createElement('p');description.className='numbers';
    description.textContent=record.decision==='RETAKE'?record.reasons.join(' '):`Score ${record.score.toFixed(6)} / frozen threshold ${state.frozen.threshold.toFixed(6)} · ${record.latencyMs.toFixed(0)} ms`;
    result.append(description);
    const limit=document.createElement('p');limit.className='fine';limit.textContent=record.decision==='RETAKE'?'No anomaly score or verdict issued.':`Capture heuristic passed; blur may still be present. ${$('part').value==='own'?'Upload threshold is not validated.':'Generated sample; this outcome is not an accuracy estimate.'}`;result.append(limit);
    const canvas=$('overlay');canvas.hidden=false;const ctx=canvas.getContext('2d');ctx.drawImage(input.canvas,0,0);
    if(record.distances){const map=document.createElement('canvas');map.width=map.height=16;const mc=map.getContext('2d'),pixels=mc.createImageData(16,16);record.distances.forEach((d,i)=>{pixels.data.set([40,100,73,Math.round(Math.min(1,d)*180)],i*4);});mc.putImageData(pixels,0,0);ctx.drawImage(map,0,0,224,224);}
  }
  return record;
}
$('teach').onclick=()=>onboard().catch(()=>{});
$('check').onclick=async()=>{lock(true);try{const source=$('sample').value==='own'?$('test-file').files[0]:sourceFor($('sample').value);if(!source)throw Error('Choose a test photo');await inspect(source);}catch(e){$('result').textContent=`Inspection unavailable: ${e.message}`;$('overlay').hidden=true;}finally{lock(false);}};
// Read-only diagnostic entry points for reproducible local acceptance tests.
window.visurex={onboard,inspect,sourceFor,snapshot:()=>({frozen:state.frozen,calibrationScores:state.calibrationScores,onboardingMs:state.onboardingMs,records:state.records,pixels:Object.fromEntries(state.pixels)}),manifest};
function row(group,method,k,data){return data.macro.find(r=>r.group===group&&r.method===method&&r.k===String(k));}
const fmt=r=>`${r.mean.toFixed(4)} [${r.ci95.map(v=>v.toFixed(4)).join(', ')}]`;
const research=await fetch('research.json').then(r=>r.json());
const resultLink=(file,label)=>`<a href="${repo+s(file)}">${label}</a>`;
function s(file){return `sprint/${file}`;}
$('strong-result').innerHTML=`<strong>Eight-reference benchmark, 15 categories</strong><br>DINOv2 ${fmt(row('all','dinov2_vits14',8,research))}<br>PatchCore ${fmt(row('all','patchcore_wrn50',8,research))}<br>${resultLink('S2_RESULTS/summary.json','Measured results and intervals')}`;
for(const k of [1,2,4,8,16]){const tr=document.createElement('tr');for(const value of [String(k),fmt(row('all','dinov2_vits14',k,research)),fmt(row('all','patchcore_wrn50',k,research))]){const td=document.createElement('td');td.textContent=value;tr.append(td);}$('research-table').tBodies[0].append(tr);}
$('split').innerHTML=`At k=8: textures (5 categories), DINOv2 ${fmt(row('texture','dinov2_vits14',8,research))} versus PatchCore ${fmt(row('texture','patchcore_wrn50',8,research))}; objects (10), ${fmt(row('object','dinov2_vits14',8,research))} versus ${fmt(row('object','patchcore_wrn50',8,research))}. ${resultLink('S2_RESULTS/summary.json','Source')}`;
$('negative').innerHTML=`Negative result: the pre-registered normal-only router did not meet its criterion. It is not used here. ${resultLink('S3_RESULTS.md','Router results')}`;
const models=research.onnx.models,bottle=models.find(m=>m.category==='bottle'),total=models.reduce((n,m)=>n+m.images,0),agree=models.reduce((n,m)=>n+m.agreeing_decisions,0);
$('onnx').innerHTML=`Separate earlier PatchCore export: ${agree}/${total} decisions agreed; bottle warm model-call ONNX* p50/p95 ${bottle.timing_ms.onnx.p50.toFixed(1)}/${bottle.timing_ms.onnx.p95.toFixed(1)} ms (n=${bottle.images}). This is laptop Python runtime timing, not this browser or glasses latency. ${resultLink('S4_RESULTS/summary.json','Source and full precision')}`;
const svg=$('chart'),NS='http://www.w3.org/2000/svg';
function element(name,attrs,text){const e=document.createElementNS(NS,name);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text)e.textContent=text;svg.append(e);return e;}
const x=i=>70+i*128,y=v=>250-(v-.7)/.3*220;
for(const t of [.7,.8,.9,1]){element('line',{x1:60,y1:y(t),x2:600,y2:y(t),stroke:'var(--rule)','stroke-width':.5});element('text',{x:12,y:y(t)+4,fill:'var(--fg)','font-size':12},t.toFixed(1));}
for(const [method,dash]of [['dinov2_vits14',''],['patchcore_wrn50','6 5']]){
  const values=[1,2,4,8,16].map(k=>row('all',method,k,research));
  values.forEach((r,i)=>{element('line',{x1:x(i),y1:y(r.ci95[0]),x2:x(i),y2:y(r.ci95[1]),stroke:method==='dinov2_vits14'?'var(--accent)':'var(--muted)','stroke-width':1});});
  element('polyline',{points:values.map((r,i)=>`${x(i)},${y(r.mean)}`).join(' '),fill:'none',stroke:method==='dinov2_vits14'?'var(--accent)':'var(--muted)','stroke-width':2,'stroke-dasharray':dash});
}
[1,2,4,8,16].forEach((k,i)=>element('text',{x:x(i),y:280,fill:'var(--fg)','font-size':12,'text-anchor':'middle'},String(k)));
