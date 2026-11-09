import {freezeCalibration,qualityFromGray,verdict} from './core.mjs';
const $=id=>document.getElementById(id);
const manifest=await fetch('samples.json').then(r=>r.json());
const state={session:null,scorer:null,bank:null,frozen:null,ready:false,busy:false,records:[],pixels:new Map()};
const mean=[.485,.456,.406],std=[.229,.224,.225];
const verdictLabels={GOOD:'OK',ANOMALY:'Defect',RETAKE:'Retake photo'};
function message(s){$('status').textContent=s;}
function lock(busy){
  state.busy=busy;
  $('teach').disabled=busy;
  $('check').disabled=busy||(!state.ready&&$('part').value==='own');
  $('part').disabled=busy;
  $('sample').disabled=busy;
}
function resetDecision(){
  const result=$('result');
  delete result.dataset.decision;
  result.textContent=$('part').value==='own'&&!state.ready
    ?'Build a reference bank before inspecting your photos.':'Awaiting inspection';
  const ncr=$('inspect-create-ncr');
  if(ncr)ncr.hidden=true;
  $('overlay').hidden=true;
  $('sample-preview').hidden=$('sample').value==='own';
  $('specimen-empty').hidden=$('sample').value!=='own';
}
function clearBank(){state.bank=null;state.frozen=null;state.ready=false;resetDecision();lock(state.busy);}
function updateSample(){
  const name=$('sample').value,own=name==='own',preview=$('sample-preview');
  $('test-upload').hidden=!own;
  $('specimen-caption').textContent=own?'Your test photo stays in this browser.':'Generated washer photo';
  if(!own){
    preview.src=sourceFor(name);
    preview.alt=$('sample').selectedOptions[0].textContent;
  }
  resetDecision();
}
$('part').onchange=()=>{
  clearBank();
  const own=$('part').value==='own';
  $('uploads').hidden=!own;
  if(own)$('bank-details').open=true;
  renderThumbs();
};
$('references').onchange=()=>{clearBank();renderThumbs();};
$('calibration').onchange=clearBank;
$('sample').onchange=updateSample;
$('test-file').onchange=resetDecision;
function setTheme(dark){
  document.body.dataset.theme=dark?'dark':'light';
  $('theme').textContent=dark?'Light mode':'Dark mode';
}
setTheme(matchMedia('(prefers-color-scheme: dark)').matches);
$('theme').onclick=()=>setTheme(document.body.dataset.theme!=='dark');
lock(false);
function renderThumbs(){
  $('thumbs').replaceChildren();
  const own=$('part').value==='own',refs=own?Array.from($('references').files):manifest.references;
  for(const [i,ref]of refs.entries()){
    const img=document.createElement('img');
    img.src=own?URL.createObjectURL(ref):ref.path;if(own)img.onload=()=>URL.revokeObjectURL(img.src);
    img.alt=`${own?'Uploaded':'Generated'} normal reference ${i+1}`;img.width=80;img.height=80;$('thumbs').append(img);
  }
}
$('bank-details').addEventListener('toggle',event=>{
  if(event.currentTarget.open&&!$('thumbs').hasChildNodes())renderThumbs();
});
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
  if(!window.ort)await new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    script.src='ort/ort.min.js';
    script.onload=resolve;
    script.onerror=()=>{
      script.remove();
      reject(Error('ONNX Runtime could not load.'));
    };
    document.head.append(script);
  });
  const ort=window.ort;
  if(!ort)throw Error('ONNX Runtime could not load.');
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
  lock(true);clearBank();$('result').textContent='Preparing the reference bank…';const start=performance.now();
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
    message(`Bank ready: 8 references + ${cal.length} separate normal calibration photos. Frozen threshold ${state.frozen.threshold.toFixed(6)}. Onboarding ${(state.onboardingMs/1000).toFixed(1)} s.`);resetDecision();
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
    const result=$('result');result.replaceChildren();result.dataset.decision=record.decision;const title=document.createElement('strong');title.textContent=verdictLabels[record.decision];result.append(title);
    const description=document.createElement('p');description.className='numbers';
    description.textContent=record.decision==='RETAKE'?record.reasons.join(' '):`Score ${record.score.toFixed(6)} / frozen threshold ${state.frozen.threshold.toFixed(6)} / ${record.latencyMs.toFixed(0)} ms`;
    result.append(description);
    const limit=document.createElement('p');limit.className='fine';limit.textContent=record.decision==='RETAKE'?'No anomaly score or verdict issued.':`Capture heuristic passed; blur may still be present. ${$('part').value==='own'?'Upload threshold is not validated.':'Generated sample; this outcome is not an accuracy estimate.'}`;result.append(limit);
    const canvas=$('overlay');$('sample-preview').hidden=true;$('specimen-empty').hidden=true;canvas.hidden=false;const ctx=canvas.getContext('2d');ctx.drawImage(input.canvas,0,0);
    if(record.distances){const map=document.createElement('canvas');map.width=map.height=16;const mc=map.getContext('2d'),pixels=mc.createImageData(16,16);record.distances.forEach((d,i)=>{pixels.data.set([40,100,73,Math.round(Math.min(1,d)*180)],i*4);});mc.putImageData(pixels,0,0);ctx.drawImage(map,0,0,224,224);}
    const bankVersion=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(state.frozen))).then(b=>Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join(''));
    window.dispatchEvent(new CustomEvent('visurex:inspection',{detail:{decision:record.decision,score:record.score??null,threshold:state.frozen.threshold,bankVersion,part:$('part').value==='own'?'':'Washer (generated sample)',photo:input.png,heatmap:canvas.toDataURL('image/png')}}));
  }
  return record;
}
$('teach').onclick=()=>onboard().catch(()=>{});
$('check').onclick=async()=>{
  if(state.busy)return;
  try{
    const source=$('sample').value==='own'?$('test-file').files[0]:sourceFor($('sample').value);
    if(!source)throw Error('Choose a test photo');
    if(!state.ready)await onboard();
    lock(true);
    await inspect(source);
  }catch(error){
    resetDecision();
    $('result').textContent='Inspection unavailable: '+error.message;
  }finally{lock(false);}
};
// Read-only diagnostic entry points for reproducible local acceptance tests.
window.visurex={onboard,inspect,sourceFor,snapshot:()=>({frozen:state.frozen,calibrationScores:state.calibrationScores,onboardingMs:state.onboardingMs,records:state.records,pixels:Object.fromEntries(state.pixels)}),manifest};
