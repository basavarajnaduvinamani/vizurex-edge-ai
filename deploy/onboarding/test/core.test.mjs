import test from 'node:test';
import assert from 'node:assert/strict';
import {freezeCalibration,quantile,qualityFromGray,verdict,isLocalResource} from '../core.mjs';
const ids=Array.from({length:8},(_,i)=>`reference-${i}`);
test('local upload thumbnails are local blobs; remote traffic stays rejected',()=>{
  const origin='http://127.0.0.1:8000';
  assert.equal(isLocalResource(`blob:${origin}/upload`,origin),true);
  assert.equal(isLocalResource('https://external.example/upload',origin),false);
  assert.equal(isLocalResource('blob:https://external.example/upload',origin),false);
  assert.equal(isLocalResource(origin+'.attacker.example/upload',origin),false);
});
test('p99 calibration is frozen before test and cannot learn from test',()=>{
  const frozen=freezeCalibration([.1,.2,.3],ids,['a','b','c']);
  const original=frozen.threshold;
  for(const score of [0,10,-1])verdict(score,frozen,{passed:true});
  assert.equal(frozen.threshold,original);assert.ok(Object.isFrozen(frozen));
  assert.throws(()=>{frozen.threshold=100;});assert.equal(quantile([0,1],.99),.99);
});
test('separate calibration images are mandatory',()=>{
  assert.throws(()=>freezeCalibration([.1,.2],ids,['a','reference-0']));
  assert.throws(()=>freezeCalibration([.1],ids,['a']));
});
test('dark capture gives RETAKE and no invented score',()=>{
  const quality=qualityFromGray(new Uint8Array(224*224),224,224);
  assert.equal(quality.passed,false);assert.ok(quality.reasons.some(x=>x.includes('dark')));
  const result=verdict(null,null,quality);assert.equal(result.decision,'RETAKE');assert.equal(result.score,null);
});
test('threshold equality is anomaly; missing bank is error',()=>{
  const frozen=freezeCalibration([.5,.5],ids,['a','b']);
  assert.equal(verdict(.5,frozen,{passed:true}).decision,'ANOMALY');
  assert.throws(()=>verdict(0,null,{passed:true}));
});
