import {chromium} from '@playwright/test';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const dist=path.join(root,'artifacts/onboarding/dist'),out=path.join(root,'artifacts/onboarding/verification');
await mkdir(path.join(out,'screenshots'),{recursive:true});
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.png':'image/png','.css':'text/css'};
const config=JSON.parse(await readFile(path.join(dist,'vercel.json'),'utf8'));
const server=createServer(async(req,res)=>{
  try{const url=new URL(req.url,'http://localhost');const name=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));
    const file=path.resolve(dist,name);if(!file.startsWith(dist+path.sep)){res.writeHead(403);res.end();return;}
    if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405);res.end();return;}
    const body=await readFile(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store',...Object.fromEntries(config.headers[0].headers.map(h=>[h.key,h.value]))});res.end(body);
  }catch{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({channel:'chrome',headless:true});
let checks=0;const errors=[],external=[];
try{
  const page=await browser.newPage({viewport:{width:1280,height:1000},colorScheme:'light'});
  page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});page.on('console',m=>{if(m.type()==='error')console.log('BROWSER',m.text());});page.on('request',r=>{if(!r.url().startsWith(origin)&&!r.url().startsWith('data:'))external.push(r.url());});
  await page.goto(origin);await page.waitForFunction(()=>!!window.visurex);
  await page.locator('#teach').click();
  const progress=setInterval(()=>{page.locator('#status').innerText().then(x=>console.log(x)).catch(()=>{});},15000);
  await page.waitForFunction(()=>window.visurex.snapshot().frozen!==null||document.querySelector('#status').textContent.includes('Unable to onboard'),{},{timeout:240000});
  clearInterval(progress);
  if(!(await page.evaluate(()=>window.visurex.snapshot().frozen)))throw Error(await page.locator('#status').innerText());checks++;
  const before=await page.evaluate(()=>window.visurex.snapshot().frozen.threshold);
  // Actual warm-up, then every fixed generated check. No replayed predictions.
  await page.evaluate(async()=>{await window.visurex.inspect(window.visurex.sourceFor('normal'),false);await window.visurex.inspect(window.visurex.sourceFor('scratch'),false);});
  const measured=[];
  for(const item of await page.evaluate(()=>window.visurex.manifest.tests)){
    const result=await page.evaluate(p=>window.visurex.inspect(p,false),item.path);
    measured.push({...result,label:item.label});
  }
  for(const [width,theme]of [[1280,'light'],[1280,'dark'],[390,'light'],[390,'dark']]){
    await page.setViewportSize({width,height:1000});await page.emulateMedia({colorScheme:theme});
    for(const kind of ['normal','scratch','dark','blur']){
      await page.selectOption('#sample',kind);await page.locator('#check').click();
      await page.waitForFunction(()=>!document.querySelector('#check').disabled,{},{timeout:60000});
      const text=await page.locator('#result').innerText();
      if(kind==='dark'&&!text.includes('RETAKE'))throw Error('Dark RETAKE missing');
      if(!/GOOD|ANOMALY|RETAKE/.test(text))throw Error(text);
      await page.screenshot({path:path.join(out,`screenshots/${width}-${theme}-${kind}.png`),fullPage:true});checks++;
    }
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error(`Overflow at ${width}`);checks++;
  }
  const snapshot=await page.evaluate(()=>window.visurex.snapshot());
  if(before!==snapshot.frozen.threshold)throw Error('Threshold changed after tests');checks++;
  // Upload path: identical reference/calibration byte content must fail.
  await page.selectOption('#part','own');
  const refs=Array.from({length:8},(_,i)=>path.join(dist,`samples/references-${String(i).padStart(3,'0')}.png`));
  await page.locator('#references').setInputFiles(refs);
  await page.locator('#calibration').setInputFiles([refs[0],refs[1]]);
  await page.locator('#teach').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Duplicate photos'));checks++;
  const calibration=Array.from({length:8},(_,i)=>path.join(dist,`samples/calibration-${100+i}.png`));
  await page.locator('#calibration').setInputFiles(calibration);await page.locator('#teach').click();
  await page.waitForFunction(()=>window.visurex.snapshot().frozen!==null,{},{timeout:240000});
  await page.selectOption('#sample','own');await page.locator('#test-file').setInputFiles(path.join(dist,'samples/test-scratch-200.png'));
  await page.locator('#check').click();await page.waitForFunction(()=>!document.querySelector('#check').disabled,{},{timeout:60000});
  if(!/GOOD|ANOMALY/.test(await page.locator('#result').innerText()))throw Error('Upload inference missing');checks++;
  if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));checks++;
  await writeFile(path.join(out,'browser.json'),JSON.stringify({date:'2026-11-04',browser:browser.version(),provider:'wasm',threads:1,checks,errors,external,measured,snapshot,scope:'20 generated functional examples; same browser-preprocessed tensors compared separately in Python'},null,2));
  console.log(JSON.stringify({checks,measured:measured.length,screenshots:path.join(out,'screenshots'),browser:browser.version()}));
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
