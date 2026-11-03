// Benchmarked AnomalyDINO-style scoring, not a new method.
// https://arxiv.org/abs/2405.14529 ; https://arxiv.org/abs/2106.08265
export function quantile(values, p) {
  if (!values.length || values.some(v => !Number.isFinite(v))) throw Error('Invalid calibration');
  const a = [...values].sort((a,b)=>a-b), x=(a.length-1)*p, i=Math.floor(x);
  return a[i]+(a[Math.ceil(x)]-a[i])*(x-i);
}
export function freezeCalibration(scores, referenceIds, calibrationIds) {
  if(referenceIds.length!==8 || calibrationIds.length<2) throw Error('Use eight references and at least two calibration photos');
  if(scores.length!==calibrationIds.length)throw Error('Every calibration image needs a normal-only score');
  const ids=[...referenceIds,...calibrationIds];
  if(new Set(ids).size!==ids.length) throw Error('Reference and calibration photos must be distinct');
  return Object.freeze({threshold:quantile(scores,.99), referenceIds:Object.freeze([...referenceIds]),
    calibrationIds:Object.freeze([...calibrationIds]), rule:'p99 normal-only; frozen before test'});
}
export function verdict(score, frozen, quality) {
  if(!quality.passed) return {decision:'RETAKE', score:null, reasons:quality.reasons};
  if(!frozen || !Number.isFinite(score)) throw Error('Onboard before testing');
  return {decision:score>=frozen.threshold?'ANOMALY':'GOOD',score,threshold:frozen.threshold};
}
export function qualityFromGray(gray, width, height, sourceWidth=width, sourceHeight=height) {
  const n=gray.length; let dark=0, bright=0, sum=0, squares=0;
  // OpenCV CV_64F Laplacian ksize=1 with BORDER_REFLECT_101.
  const reflect=(i,limit)=>i<0?-i:i>=limit?2*limit-i-2:i;
  for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
    const g=gray[y*width+x]; dark+=g<12; bright+=g>248;
    const value=gray[y*width+reflect(x-1,width)]+gray[y*width+reflect(x+1,width)]+
      gray[reflect(y-1,height)*width+x]+gray[reflect(y+1,height)*width+x]-4*g;
    sum+=value;squares+=value*value;
  }
  const metrics={laplacian_variance:squares/n-(sum/n)**2,dark_fraction:dark/n,bright_fraction:bright/n};
  const reasons=[];
  if(Math.min(sourceWidth,sourceHeight)<224) reasons.push('Image is too small.');
  if(metrics.dark_fraction>.70) reasons.push('Most of the inspection region is too dark.');
  if(metrics.bright_fraction>.70) reasons.push('Most of the inspection region is overexposed.');
  if(metrics.laplacian_variance<12) reasons.push('Insufficient visible detail; check focus and framing.');
  return {passed:!reasons.length,reasons,metrics,policy_version:'capture-heuristic-v1-browser',
    limitation:'Heuristic only. The earlier benchmark blur study passed blurred captures and produced false alarms.'};
}
