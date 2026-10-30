// Node-only regression tests; no browser automation or external requests.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
const apiSource = await fs.readFile(new URL('../frontend-prototype/api.js', import.meta.url), 'utf8');
const { HttpInspectionClient, MockInspectionClient } = await import('data:text/javascript;base64,' + Buffer.from(apiSource).toString('base64'));
const valid = {
  inspection_id: 'test-id', timestamp: new Date().toISOString(), category: 'bottle',
  model_version: 'test-only', cold_start: false, decision: 'GOOD', anomaly_score: 0.3, threshold: 1,
  timing: { model_inference_ms: 2, server_processing_ms: 3 },
  images: { processed: 'data:image/png;base64,AA==', heatmap: 'data:image/png;base64,AA==', overlay: 'data:image/png;base64,AA==' },
};
const client = new HttpInspectionClient('http://localhost:8000');
const params = { file: new File(['fixture'], 'fixture.png', { type: 'image/png' }), category: 'bottle' };
let payload = valid;
const originalFetch = globalThis.fetch;
globalThis.fetch = async () => new Response(JSON.stringify(payload), { status: 200 });
assert.equal((await client.inspectImage(params)).isMock, false);
let checks = 1;
client.accessKey = 'test-only-key';
globalThis.fetch = async (url, options) => {
  assert.equal(options.headers['X-Visurex-Key'], 'test-only-key');
  assert.ok(!url.includes('test-only-key'));
  return new Response(JSON.stringify(payload), {status: 200});
};
await client.inspectImage(params); checks++;
await client.getModels(); checks++;
client.accessKey = '';
globalThis.fetch = async () => new Response(JSON.stringify(payload), {status: 200});
for (const field of ['inspection_id', 'timestamp', 'model_version', 'decision', 'anomaly_score', 'threshold', 'category', 'cold_start']) {
  payload = structuredClone(valid); delete payload[field];
  await assert.rejects(client.inspectImage(params), /Malformed/); checks++;
}
for (const mutate of [
  p => { p.timing.server_processing_ms = -1; },
  p => { p.images.overlay = 'https://external.example/image.png'; },
  p => { p.category = 'grid'; },
]) {
  payload = structuredClone(valid); mutate(payload);
  await assert.rejects(client.inspectImage(params), /Malformed/); checks++;
}
globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Model offline' }), { status: 503 });
await assert.rejects(client.inspectImage(params), /Model offline/); checks++;
payload = { ...valid, decision: 'RETAKE', quality: { passed: false, reasons: ['Too dark'] } };
delete payload.anomaly_score; delete payload.images;
globalThis.fetch = async () => new Response(JSON.stringify(payload), { status: 200 });
assert.equal((await client.inspectImage(params)).decision, 'RETAKE'); checks++;
payload.quality.reasons = [];
await assert.rejects(client.inspectImage(params), /Malformed/); checks++;
globalThis.fetch = originalFetch;
const mockRetake = await new MockInspectionClient().inspectImage({ file: null, category: 'bottle', simulationType: 'retake' });
assert.equal(mockRetake.decision, 'RETAKE'); assert.equal(mockRetake.isMock, true);
assert.match(mockRetake.quality.reasons[0], /^Simulated/); checks++;

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, { disabled: false, style: {}, value: '',
    classList: { add() {}, remove() {}, toggle() {} }, setAttribute() {}, addEventListener() {},
    textContent: '', appendChild() {} });
  return elements.get(id);
};
const images = [];
class TestImage { constructor() { this.naturalWidth = 32; this.naturalHeight = 32; images.push(this); } }
const context = vm.createContext({
  document: { readyState: 'loading', addEventListener() {}, getElementById: element,
    querySelectorAll: () => [], createElement: () => element('new') },
  URL: { createObjectURL: () => 'blob:fixture', revokeObjectURL() {} },
  Image: TestImage, console, api: {}, CATEGORY_SPECS: { bottle: { displayName: 'Bottle' } },
});
let appSource = await fs.readFile(new URL('../frontend-prototype/app.js', import.meta.url), 'utf8');
appSource = appSource.replace(/^import .*?;\s*$/m, '');
vm.runInContext(appSource, context);
vm.runInContext("state.isInspecting=true; state.selectedFile={name:'original.png'}; handleFileSelection({name:'new.png',type:'image/png',size:10});", context);
assert.equal(vm.runInContext('state.selectedFile.name', context), 'original.png'); checks++;
vm.runInContext("state.isInspecting=false; handleFileSelection({name:'a.png',type:'image/png',size:10}); handleFileSelection({name:'b.png',type:'image/png',size:10});", context);
images[0].onload();
assert.equal(element('btnRunInspection').disabled, true); checks++;
images[1].onload();
assert.equal(element('btnRunInspection').disabled, false); checks++;
assert.equal(vm.runInContext('state.selectedFile.name', context), 'b.png'); checks++;
context.api.inspect = async () => ({decision: 'RETAKE', quality: {reasons: ['Too dark']}});
vm.runInContext("state.selectedCategory='bottle'; state.executionMode='live';", context);
await vm.runInContext('runInspection()', context);
assert.match(element('notificationMessage').textContent, /RETAKE.*No defect decision/); checks++;
assert.equal(vm.runInContext('state.isInspecting', context), false); checks++;
context.api.inspect = async () => ({ decision: 'ANOMALY', isMock: true, anomalyScore: 1.42, threshold: 1,
  inspectionId: 'INSP-DEMO-X', timestamp: new Date().toISOString(), warnings: [],
  timing: { modelInferenceMs: 1, serverProcessingMs: 1, clientRoundTripMs: 1 }, images: { processed: 'p', heatmap: 'h' } });
vm.runInContext("state.executionMode='live'; state.selectedFile=null;", context);
element('statusText').textContent = '';
await vm.runInContext("showDemoExample('anomaly')", context);
assert.equal(element('statusText').textContent, '', 'examples must not render in Live mode'); checks++;
vm.runInContext("state.executionMode='demo';", context);
await vm.runInContext("showDemoExample('anomaly')", context);
assert.equal(element('statusText').textContent, 'ANOMALY (SIMULATED)'); checks++;
assert.match(element('decisionRule').textContent, /1\.4200 ≥ threshold 1\.0000 → ANOMALY/); checks++;
context.api.inspect = async () => ({ decision: 'RETAKE', isMock: true, inspectionId: 'INSP-DEMO-Y', quality: { reasons: ['Simulated: too dark.'] } });
await vm.runInContext("showDemoExample('retake')", context);
assert.match(element('notificationMessage').textContent, /^SIMULATED RETAKE.*No defect decision/); checks++;
console.log(`${checks} frontend regression checks passed.`);
