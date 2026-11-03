import test from 'node:test';
import assert from 'node:assert/strict';
import {decodePhotoDataURL} from '../platform/privacy.mjs';
test('encoded inspection photos are decoded without a data-URL fetch blocked by CSP',async()=>{
  const original=globalThis.fetch;globalThis.fetch=()=>{throw Error('No network allowed');};
  try{const blob=decodePhotoDataURL('data:image/png;base64,AQID');assert.equal(blob.type,'image/png');assert.deepEqual([...new Uint8Array(await blob.arrayBuffer())],[1,2,3]);}finally{globalThis.fetch=original;}
});
test('HTML/SVG and remote URLs cannot enter the photo persistence path',()=>{
  for(const input of ['data:text/html;base64,AQID','data:image/svg+xml;base64,AQID','https://example.com/photo.png'])assert.throws(()=>decodePhotoDataURL(input));
});
