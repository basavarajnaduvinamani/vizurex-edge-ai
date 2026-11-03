let detectorPromise;
export async function faceDetector(){
  if(!detectorPromise)detectorPromise=(async()=>{
    const {FaceDetector,FilesetResolver}=await import('../face/vision_bundle.mjs');
    const files=await FilesetResolver.forVisionTasks(new URL('../face/wasm/',import.meta.url).href);
    return FaceDetector.createFromOptions(files,{baseOptions:{modelAssetPath:new URL('../face/blaze_face_short_range.tflite',import.meta.url).href,delegate:'CPU'},runningMode:'IMAGE',minDetectionConfidence:.5});
  })();return detectorPromise;
}
export function blurBoxes(canvas,boxes){
  const ctx=canvas.getContext('2d');
  for(const box of boxes){
    const pad=Math.max(box.width,box.height)*.25,x=Math.max(0,Math.floor(box.originX-pad)),y=Math.max(0,Math.floor(box.originY-pad));
    const width=Math.min(canvas.width-x,Math.ceil(box.width+pad*2)),height=Math.min(canvas.height-y,Math.ceil(box.height+pad*2));
    if(width<=0||height<=0)continue;
    const tiny=document.createElement('canvas');tiny.width=Math.max(1,Math.round(width/24));tiny.height=Math.max(1,Math.round(height/24));
    tiny.getContext('2d').drawImage(canvas,x,y,width,height,0,0,tiny.width,tiny.height);
    ctx.save();ctx.imageSmoothingEnabled=false;ctx.drawImage(tiny,0,0,tiny.width,tiny.height,x,y,width,height);ctx.restore();
    // Pixelation remains effective even on browsers without canvas filters.
    if('filter'in ctx){const patch=document.createElement('canvas');patch.width=width;patch.height=height;patch.getContext('2d').drawImage(canvas,x,y,width,height,0,0,width,height);ctx.save();ctx.filter='blur(12px)';ctx.drawImage(patch,x,y);ctx.restore();}
  }
  return canvas;
}
export async function sanitizePhoto(input,{detect=null}={}){
  let blob;
  if(input instanceof Blob){if(input.size>20*1024*1024||!['image/jpeg','image/png','image/webp'].includes(input.type))throw Error('Use JPEG, PNG or WebP up to 20 MB');blob=input;}
  else if(typeof input==='string'&&/^data:image\/(png|jpeg|webp);base64,/.test(input))blob=await fetch(input).then(r=>r.blob());
  else throw Error('Choose a photo of your own object');
  const bitmap=await createImageBitmap(blob);if(bitmap.width*bitmap.height>24000000){bitmap.close();throw Error('Use an image up to 24 megapixels');}
  const scale=Math.min(1,960/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
  let boxes=[],checked=false,method=detect?'Synthetic test detector':'MediaPipe BlazeFace, on-device';
  try{
    const run=detect||((image)=>faceDetector().then(d=>d.detect(image)));
    const result=await run(canvas);boxes=(result.detections||[]).map(d=>d.boundingBox).filter(Boolean);blurBoxes(canvas,boxes);checked=true;
  }catch{
    // No unreviewed photo is persisted when the privacy model cannot run.
    boxes=[{originX:0,originY:0,width:canvas.width,height:canvas.height}];blurBoxes(canvas,boxes);method='Face check unavailable; entire image obscured';
  }
  return {dataUrl:canvas.toDataURL('image/jpeg',.82),width:canvas.width,height:canvas.height,privacy:{method,faces:checked?boxes.length:null,fullyObscured:!checked}};
}
