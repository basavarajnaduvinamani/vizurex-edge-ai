import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),dist=path.join(root,'artifacts/onboarding/dist');
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.png':'image/png','.css':'text/css'};
const config=JSON.parse(await readFile(path.join(dist,'vercel.json'),'utf8'));
const server=createServer(async(req,res)=>{try{const name=new URL(req.url,'http://localhost').pathname;const file=path.resolve(dist,name==='/'?'index.html':name.slice(1));if(!file.startsWith(dist+path.sep))throw Error('path');res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');for(const header of config.headers[0].headers)res.setHeader(header.key,header.value);res.end(await readFile(file));}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const chrome=await chromeLauncher.launch({chromeFlags:['--headless=new','--no-first-run']});
try{
  const result=await lighthouse(`http://127.0.0.1:${server.address().port}`,{port:chrome.port,output:'json',logLevel:'error',onlyCategories:['performance','accessibility','best-practices','seo'],formFactor:'mobile'});
  const folder=path.join(root,'artifacts/onboarding/verification');await mkdir(folder,{recursive:true});
  await writeFile(path.join(folder,'lighthouse.json'),result.report);
  const summary={date:'2026-11-04',version:result.lhr.lighthouseVersion,scope:'Mobile simulated-throttling initial page load; lazy model loading excluded. Not inference performance.',scores:Object.fromEntries(Object.entries(result.lhr.categories).map(([k,v])=>[k,v.score*100])),runWarnings:result.lhr.runWarnings};
  await mkdir(path.join(root,'docs/step1'),{recursive:true});
  await writeFile(path.join(root,'docs/step1/lighthouse.json'),JSON.stringify(summary,null,2));console.log(JSON.stringify(summary));
}finally{await chrome.kill();await new Promise(resolve=>server.close(resolve));}
