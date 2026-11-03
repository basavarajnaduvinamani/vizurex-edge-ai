import {chromium} from '@playwright/test';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),dist=path.join(root,'artifacts/onboarding/dist'),out=path.join(root,'artifacts/platform/final');
await mkdir(path.join(out,'screenshots'),{recursive:true});
const config=JSON.parse(await readFile(path.join(dist,'vercel.json'),'utf8'));
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.css':'text/css','.wasm':'application/wasm','.png':'image/png'};
const server=createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;const file=path.resolve(dist,name==='/'?'index.html':name.slice(1));if(!file.startsWith(dist+path.sep))throw Error('path');for(const h of config.headers[0].headers)res.setHeader(h.key,h.value);res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');res.end(await readFile(file));}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({channel:'chrome',headless:true});
const results=[],pageErrors=[];let activeCase='';
async function run(width,theme){
  const name=`${width}-${theme}`,context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,permissions:['clipboard-read','clipboard-write'],acceptDownloads:true});
  const page=await context.newPage(),checks=[];page.on('pageerror',e=>pageErrors.push({case:name,message:e.message}));
  const check=(name,value)=>{checks.push({name,passed:Boolean(value)});if(!value)throw Error(name);};
  async function until(fn,timeout=90000){const start=Date.now();while(!(await page.evaluate(fn))){if(Date.now()-start>timeout)throw Error(`Timed out: ${activeCase}`);await new Promise(r=>setTimeout(r,150));}}
  const shot=async label=>page.screenshot({path:path.join(out,`screenshots/${name}-${label}.png`),fullPage:true});
  const capture=path.join(dist,'samples/test-normal-200.png');
  async function route(view){await page.locator(`[data-route="${view}"]`).click();await until(()=>!document.querySelector(`[data-view="${location.hash.slice(1)}"]`).hidden);}
  try{
    activeCase=`${name} home`;await page.goto(origin);await until(()=>Boolean(window.visurexPlatform)&&document.querySelector('#context-plant').options.length===2);
    check('home has WIP, affiliation, honest pilot status',await page.locator('#view-home').innerText().then(t=>t.includes('work in progress')&&t.includes('IIT Madras')&&t.includes('No factory pilot')));
    check('home exposes five prototype module routes',await page.locator('#view-home .module-list a').count()===5);await shot('home');
    activeCase=`${name} walk`;await route('walk');await page.selectOption('#walk-template','Gemba');await page.locator('#start-walk').click();await until(()=>!!document.querySelector('#finding-note'));
    await page.locator('#finding-photo').setInputFiles(capture);await page.fill('#finding-note','Quality scratch on generated washer');await page.locator('#structure-finding').click();await until(()=>!!document.querySelector('#save-finding'),180000);
    check('rule fields visibly unconfirmed',await page.locator('#finding-draft .suggested').count()>0);
    await page.locator('#save-finding').click();await until(()=>document.querySelector('#platform-message').textContent.includes('Confirm'));
    check('cannot save unconfirmed rule fields',await page.locator('#finding-draft').isVisible());
    await page.locator('#confirm-finding').click();await page.locator('#save-finding').click();await until(()=>!document.querySelector('#save-finding'));
    await page.fill('#finding-note','Unsafe guard needs attention');await page.locator('#structure-finding').click();await until(()=>!!document.querySelector('#save-finding'));await page.locator('#confirm-finding').click();await page.locator('#save-finding').click();await until(()=>!document.querySelector('#save-finding'));
    await page.locator('#end-walk').click();await until(()=>!!document.querySelector('#walk-report'));
    check('walk report contains two captured findings',await page.locator('#walk-report .record-row').count()===2);await shot('walk-report');
    await page.locator('#copy-walk').click();check('WhatsApp summary copied without sending',await page.evaluate(()=>navigator.clipboard.readText()).then(t=>t.includes('2 findings')));
    const [walkDownload]=await Promise.all([page.waitForEvent('download'),page.locator('#walk-csv').click()]);check('walk CSV exported',walkDownload.suggestedFilename().endsWith('.csv'));
    activeCase=`${name} ncr`;await page.getByRole('button',{name:'Create NCR',exact:true}).click();await until(()=>!!document.querySelector('#ncr-qtyInspected'));
    check('human quantity fields start empty',await page.inputValue('#ncr-qtyInspected')===''&&await page.inputValue('#ncr-qtyRejected')==='');
    await page.fill('#ncr-part','Generated washer demo');await page.fill('#ncr-qtyInspected','3');await page.fill('#ncr-qtyRejected','1');await page.selectOption('#ncr-defectCode','Surface mark');await page.fill('#ncr-suspectedSource','Handling example');
    await page.locator('#confirm-ncr').click();await page.locator('#ncr-submitted').click();await until(()=>document.querySelector('#ncr-state')?.textContent.includes('Status: submitted'));
    await page.selectOption('#ncr-disposition','rework');await page.locator('#ncr-dispositioned').click();await until(()=>document.querySelector('#platform-message').textContent.includes('QA lead or plant manager'));
    check('inspector cannot disposition',await page.locator('#ncr-state').innerText().then(t=>t.includes('submitted')));
    await page.selectOption('#context-role','qa_lead');await page.selectOption('#ncr-disposition','rework');await page.locator('#ncr-dispositioned').click();await until(()=>!!document.querySelector('#ncr-rootCause'));
    await page.fill('#ncr-rootCause','Example handling cause, not a plant investigation');await page.fill('#ncr-capaAction','Use a protective tray');await page.fill('#ncr-capaDueDate','2026-11-10');await page.locator('#ncr-capa_open').click();await until(()=>!!document.querySelector('#close-linked-actions'));
    await page.locator('#ncr-closed').click();await until(()=>document.querySelector('#platform-message').textContent.includes('open CAPA'));
    check('NCR cannot close with open CAPA',await page.locator('#ncr-state').innerText().then(t=>t.includes('capa_open')));
    await page.locator('#close-linked-actions').click();await until(()=>document.querySelector('#platform-message').textContent.includes('after photo'));
    check('closure requires after photo',await page.locator('#ncr-state').innerText().then(t=>t.includes('capa_open')));
    await page.locator('#ncr-after-photo').setInputFiles(capture);await page.locator('#close-linked-actions').click();await until(()=>document.querySelector('#platform-message').textContent.includes('Linked actions closed'));
    await page.locator('#complete-capa').click();await until(()=>document.querySelector('#ncr-state')?.textContent.includes('CAPA: closed'));
    await page.locator('#ncr-closed').click();await until(()=>document.querySelector('#ncr-state')?.textContent.includes('Status: closed'));
    check('walk-to-NCR disposition and closure complete',await page.locator('#ncr-state').innerText().then(t=>t.includes('closed')));await shot('ncr-closed');
    const [ncrDownload]=await Promise.all([page.waitForEvent('download'),page.locator('#ncr-json').click()]);check('NcrRecord v1 JSON exported',ncrDownload.suggestedFilename().endsWith('.json'));
    const audit=await page.evaluate(async()=>{const d=await window.visurexPlatform.snapshot();const n=d.ncrs.find(x=>x.fields.status.value==='closed');const rows=d.audit.filter(e=>e.fields.recordId.value===n.id);const store=await import('/platform/store.mjs');let rejected=false;try{await store.saveMany([{store:'audit',record:rows[0]}]);}catch{rejected=true;}const after=await store.snapshot();return {states:rows.map(r=>r.fields.to.value),duplicateRejected:rejected,countUnchanged:after.audit.length===d.audit.length};});
    check('audit includes lifecycle and rejects overwriting an event',audit.duplicateRejected&&audit.countUnchanged&&['draft','submitted','dispositioned','capa_open','capa_complete','closed'].every(s=>audit.states.includes(s)));
    activeCase=`${name} next walk`;await route('walk');await page.locator('#start-walk').click();await until(()=>!!document.querySelector('#station-open'));
    check('next walk lists previous open station item',await page.locator('#station-open').innerText().then(t=>t.includes('Unsafe guard')));
    activeCase=`${name} inspect`;await route('inspect');await page.locator('#teach').click();await until(()=>window.visurex?.snapshot().frozen!==null,240000);
    await page.selectOption('#sample','scratch');await page.locator('#check').click();await until(()=>!!document.querySelector('#inspect-create-ncr')&&!document.querySelector('#inspect-create-ncr').hidden);
    check('real generated anomaly offers NCR creation',await page.locator('#result').innerText().then(t=>t.includes('ANOMALY')));await shot('inspect-anomaly');
    await page.locator('#inspect-create-ncr').click();await until(()=>location.hash==='#ncr'&&!!document.querySelector('#ncr-state'));
    const transferred=await page.evaluate(async()=>{const d=await window.visurexPlatform.snapshot();const n=d.ncrs.find(x=>x.fields.modelDecision.value==='ANOMALY');return {decision:n?.fields.modelDecision.value,score:n?.fields.modelScore.value,bank:n?.fields.bankVersion.value,empty:n?.fields.qtyInspected.value===null,photo:!!n?.fields.photo.value?.dataUrl,heatmap:!!n?.fields.heatmap.value};});
    check('Inspect transfers score/bank/evidence and leaves quantities blank',transferred.decision==='ANOMALY'&&Number.isFinite(transferred.score)&&transferred.bank?.length===64&&transferred.empty&&transferred.photo&&transferred.heatmap);await shot('ncr-from-inspect');
    activeCase=`${name} dashboard`;await route('actions');await shot('actions');await route('dashboard');await page.selectOption('#dashboard-scope','network');
    check('network view is aggregate-only with n labels',await page.locator('#dashboard-results img').count()===0&&await page.locator('#dashboard-results').innerText().then(t=>t.includes('n=')&&!t.includes('Unsafe guard needs attention')));await shot('dashboard');
    const countBefore=await page.evaluate(async()=>{const d=await window.visurexPlatform.snapshot();return d.findings.length;});await page.reload();await until(()=>!!window.visurexPlatform&&!!document.querySelector('#dashboard-results'));
    check('IndexedDB records survive reload',await page.evaluate(async()=>{const d=await window.visurexPlatform.snapshot();return d.findings.length;})===countBefore);
    check('no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(width===1280&&theme==='light'){
      const privacy=await page.evaluate(async()=>{
        const {sanitizePhoto,faceDetector}=await import('/platform/privacy.mjs');
        const canvas=document.createElement('canvas');canvas.width=canvas.height=256;const ctx=canvas.getContext('2d');
        ctx.fillStyle='#888';ctx.fillRect(0,0,256,256);ctx.fillStyle='#dcb986';ctx.beginPath();ctx.ellipse(128,128,70,90,0,0,Math.PI*2);ctx.fill();
        for(let y=60;y<200;y+=4){ctx.fillStyle=y%8?'#222':'#eee';ctx.fillRect(80,y,96,2);}ctx.fillStyle='#111';ctx.fillRect(95,100,12,12);ctx.fillRect(150,100,12,12);ctx.fillRect(110,160,40,5);
        const before=ctx.getImageData(0,0,256,256).data.slice();const photo=await sanitizePhoto(canvas.toDataURL('image/png'),{detect:async()=>({detections:[{boundingBox:{originX:55,originY:30,width:146,height:196}}]})});
        const decoded=await createImageBitmap(await fetch(photo.dataUrl).then(r=>r.blob()));ctx.drawImage(decoded,0,0);const after=ctx.getImageData(0,0,256,256).data;let changed=0;for(let i=0;i<before.length;i++)changed+=Math.abs(before[i]-after[i])>20;
        let modelReady=false,modelError=null;try{const detector=await faceDetector();const result=detector.detect(canvas);modelReady=Array.isArray(result.detections);}catch(e){modelError=String(e.message||e);}
        const fallback=await sanitizePhoto(canvas.toDataURL('image/png'),{detect:async()=>{throw Error('Fixture unavailable');}});
        return {changedPixels:changed,fixtureFaces:photo.privacy.faces,fixtureObscured:photo.privacy.fullyObscured,fallbackObscured:fallback.privacy.fullyObscured,modelReady,modelError,scope:'Synthetic face redaction with injected box; real model startup check is separate, not face-detection accuracy'};
      });
      check('synthetic face blur changes pixels and fallback obscures whole image',privacy.changedPixels>1000&&privacy.fixtureFaces===1&&!privacy.fixtureObscured&&privacy.fallbackObscured);
      check('real on-device face detector loads and executes',privacy.modelReady);
      await writeFile(path.join(out,'face-redaction.json'),JSON.stringify(privacy,null,2));
    }
    check('no uncaught page error',!pageErrors.some(e=>e.case===name));
    results.push({case:name,checks,passed:true});console.log(`${name}: ${checks.length} acceptance checks passed`);
  }catch(error){await shot('failure');results.push({case:name,checks,passed:false,error:error.message,activeCase});throw error;}
  finally{await writeFile(path.join(out,'browser.json'),JSON.stringify({date:'2026-11-04',results,pageErrors,screenshots:path.relative(root,path.join(out,'screenshots')),browser:browser.version()},null,2));await context.close();}
}
try{for(const [width,theme]of [[1280,'light'],[1280,'dark'],[390,'light'],[390,'dark']])await run(width,theme);console.log('Platform final browser gate passed.');}
finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
