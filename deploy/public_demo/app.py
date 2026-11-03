"""Sample-only public companion. No WCTE bundles, MVTec images or uploads."""
from collections import deque
from contextlib import asynccontextmanager
import io
from pathlib import Path
import sys
import threading
import time
from typing import Literal

import numpy as np
from PIL import Image,ImageDraw
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import HTMLResponse,Response

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'src' if (HERE/'src').exists() else HERE.parents[1]/'src'))
Sample=Literal['normal','scratch']


def drawing(seed, scratch=False):
    rng=np.random.default_rng(seed)
    image=Image.fromarray(np.clip(rng.normal(65,2,(224,224,3)),0,255).astype('uint8'))
    draw=ImageDraw.Draw(image)
    dx,dy=rng.integers(-3,4,size=2)
    draw.ellipse((40+dx,40+dy,184+dx,184+dy),fill=(174,177,180),outline=(220,220,220),width=3)
    draw.ellipse((89+dx,89+dy,135+dx,135+dy),fill=(62,62,62),outline=(120,120,120),width=2)
    if scratch:draw.line((55,70,100,165),fill=(245,245,245),width=7)
    return image


def sample_image(name):return drawing(200,scratch=name=='scratch')


class SyntheticBank:
    def __init__(self):
        import torch
        from torchvision import transforms
        from visurex_fewshot.backbones import PatchCoreBackbone
        from visurex_fewshot.detector import KShotPatchNN,DetectorConfig
        torch.set_num_threads(2);torch.manual_seed(0)
        self.transform=transforms.Compose([transforms.Resize(256),transforms.CenterCrop(224),transforms.ToTensor(),
                         transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
        self.backbone=PatchCoreBackbone(pretrained=True)
        features,grid=self.embed([drawing(s) for s in range(8)])
        self.detector=KShotPatchNN(DetectorConfig(metric='l2',aggregation='max'),num_workers=2).fit(features,grid)
        validation,_=self.embed([drawing(s) for s in range(100,108)])
        scores,_=self.detector.predict(validation)
        self.threshold=float(np.quantile(scores,.99))

    def embed(self,images):
        import torch
        features=[];grid=None
        for image in images:
            value,grid=self.backbone.embed(self.transform(image).unsqueeze(0));features.append(value)
        return np.concatenate(features),grid

    def inspect(self,name):
        features,_=self.embed([sample_image(name)])
        scores,_=self.detector.predict(features)
        score=float(scores[0])
        return dict(decision='ANOMALY' if score>=self.threshold else 'GOOD',score=score,threshold=self.threshold,
                    model='synthetic-reference WRN patch-NN',sample=name,
                    scope='Generated samples and a separate synthetic bank; not the industrial model or a benchmark result.')


def create_app(factory=SyntheticBank):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine=factory();yield
    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    lock=threading.Lock();recent=deque()
    @app.middleware('http')
    async def no_uploads(request:Request,call_next):
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:return Response(status_code=400)
        if length or request.headers.get('transfer-encoding'):return Response(status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'self' https://huggingface.co"
        return response
    @app.get('/',response_class=HTMLResponse)
    def home():return (HERE/'index.html').read_text(encoding='utf-8')
    @app.get('/health')
    def health():return {'ready':True,'mode':'synthetic-samples-only','uploads':False}
    @app.get('/sample/{name}')
    def sample(name:Sample):
        stream=io.BytesIO();sample_image(name).save(stream,format='PNG')
        return Response(stream.getvalue(),media_type='image/png')
    @app.post('/inspect/{name}')
    def inspect(name:Sample):
        if not lock.acquire(blocking=False):raise HTTPException(429,'Inspection busy; retry shortly')
        try:
            now=time.monotonic()
            while recent and now-recent[0]>60:recent.popleft()
            if len(recent)>=20:raise HTTPException(429,'Demo request limit; retry later')
            recent.append(now)
            return app.state.engine.inspect(name)
        finally:lock.release()
    return app


app=create_app()
