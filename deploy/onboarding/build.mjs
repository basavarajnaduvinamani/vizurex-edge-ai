import { mkdir, cp, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
await import('./platform/compile-schemas.mjs');
export const output = path.join(root, 'artifacts/onboarding/dist');
await mkdir(output, { recursive: true });
for (const file of ['index.html', 'app.mjs', 'core.mjs', 'style.css', 'icon.svg', 'README.md', 'vercel.json','THIRD_PARTY_NOTICES.md']) {
  await cp(path.join(here, file), path.join(output, file));
}
await cp(path.join(here,'licenses'),path.join(output,'licenses'),{recursive:true});
await cp(path.join(here,'fonts'),path.join(output,'fonts'),{recursive:true});
await cp(path.join(here,'platform'),path.join(output,'platform'),{recursive:true});
await mkdir(path.join(output,'face'),{recursive:true});
await cp(path.join(here,'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs'),path.join(output,'face/vision_bundle.mjs'));
await cp(path.join(here,'node_modules/@mediapipe/tasks-vision/wasm'),path.join(output,'face/wasm'),{recursive:true});
await cp(path.join(root,'artifacts/platform/face/blaze_face_short_range.tflite'),path.join(output,'face/blaze_face_short_range.tflite'));
await cp(path.join(root, 'artifacts/onboarding/assets'), output, {recursive:true});
await mkdir(path.join(output, 'ort'), {recursive:true});
await cp(path.join(here,'node_modules/onnxruntime-web/dist/ort.wasm.min.js'),path.join(output,'ort/ort.min.js'));
for (const file of ['ort-wasm-simd-threaded.wasm', 'ort-wasm-simd-threaded.mjs']) {
  await cp(path.join(here, 'node_modules/onnxruntime-web/dist', file), path.join(output, 'ort', file));
}
const raw = JSON.parse(await readFile(path.join(root, 'docs/sprint/S2_RESULTS/summary.json'), 'utf8'));
// Extract existing measurements, never recompute benchmark numbers in the demo.
const router=JSON.parse(await readFile(path.join(root,'docs/sprint/S3_RESULTS/summary.json'),'utf8'));
const onnx=JSON.parse(await readFile(path.join(root,'docs/sprint/S4_RESULTS/summary.json'),'utf8'));
await writeFile(path.join(output, 'research.json'), JSON.stringify({macro:raw.macro,router,onnx}));
await cp(path.join(root, 'LICENSE'), path.join(output, 'LICENSE'));
await cp(path.join(root, 'NOTICE'), path.join(output, 'NOTICE'));
console.log(JSON.stringify({output, scope:'allowlisted static assets; no deployment'}));
