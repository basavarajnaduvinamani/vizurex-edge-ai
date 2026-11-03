import test from 'node:test';
import assert from 'node:assert/strict';
import {readdir,readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
async function files(folder){return (await Promise.all((await readdir(folder,{withFileTypes:true})).map(async e=>e.isDirectory()?files(path.join(folder,e.name)):[path.join(folder,e.name)]))).flat();}
test('build excludes all benchmark/industrial paths and non-allowlisted images',async()=>{
  const out=path.join(root,'artifacts/onboarding/dist');
  const manifest=JSON.parse(await readFile(path.join(out,'samples.json'),'utf8'));
  const names=await files(out);
  for(const name of names){
    const relative=path.relative(out,name).replaceAll('\\','/');
    assert.doesNotMatch(relative,/mvtec|selfds|delivery_valve|industrial|test_data|\.faiss|\.pkl/i);
    if(/\.(png|jpg|jpeg|webp)$/i.test(relative)){
      assert.match(relative,/^samples\/(references-00[0-7]|calibration-10[0-7]|test-(normal|scratch)-20[0-9]|dark|blur)\.png$/);
      assert.equal(createHash('sha256').update(await readFile(name)).digest('hex'),manifest.image_sha256[path.basename(name)]);
    }
    if(/\.(html|mjs|css|json|md)$/.test(relative)){
      const text=await readFile(name,'utf8');assert.doesNotMatch(text,/[A-Z]:[\\/]|data[\\/]raw|SelfDS|test_data[\\/]|train[\\/]good/i);
    }
  }
  assert.ok(names.some(x=>x.endsWith('dinov2-vits14.onnx')));
});
test('page and README credit established methods and generated examples',async()=>{
  for(const name of ['index.html','README.md']){
    const text=await readFile(path.join(root,'deploy/onboarding',name),'utf8');
    assert.match(text,/AnomalyDINO/);assert.match(text,/PatchCore/);assert.match(text,/generated/i);
  }
});
