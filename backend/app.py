"""Local-only prototype. No cloud calls and no public-deployment authentication."""
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import threading
import time
import uuid
import warnings

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import CATEGORIES, ROOT, Registry

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000
ALLOWED_ORIGINS = {'http://localhost:8000', 'http://127.0.0.1:8000',
                   'http://localhost:5500', 'http://127.0.0.1:5500',
                   'http://localhost:8080', 'http://127.0.0.1:8080',
                   'http://localhost:5173', 'http://127.0.0.1:5173'}
LOG_LOCK = threading.Lock()


class UploadLimit:
    """Bound the entire multipart body before allowing the parser to see it."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST' or scope['path'] != '/api/inspect':
            return await self.app(scope, receive, send)
        origin = dict(scope.get('headers', [])).get(b'origin')
        if origin and origin.decode() not in ALLOWED_ORIGINS:
            return await JSONResponse({'detail': 'Origin is not allowed'}, 403)(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > MAX_FILE_BYTES + 65536:
                return await JSONResponse({'detail': 'Upload exceeds 10 MiB limit'}, 413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        consumed = False

        async def buffered_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()

        await self.app(scope, buffered_receive, send)


def decode_image(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in ('PNG', 'JPEG'):
                    raise HTTPException(415, 'Only PNG and JPEG images are supported')
                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(413, 'Image exceeds 16 megapixels')
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                return ImageOps.exif_transpose(image).convert('RGB')
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning,
            Image.DecompressionBombError):
        raise HTTPException(400, 'Invalid or damaged image')


def create_app(registry=None, log_path=None):
    app = FastAPI(title='VisureX Local Inspection', version='0.1.0', docs_url='/api/docs')
    app.state.registry = registry if registry is not None else Registry()
    app.state.log_path = Path(log_path) if log_path else ROOT / 'artifacts/inspections/inspections.jsonl'
    app.add_middleware(UploadLimit)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]'])
    app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS),
                       allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': 'local-research-prototype', 'api_version': '0.1.0'}

    @app.get('/api/models')
    def models():
        return {'models': app.state.registry.available(), 'max_upload_bytes': MAX_FILE_BYTES,
                'supported_formats': ['PNG', 'JPEG'], 'max_pixels': MAX_PIXELS,
                'warning': 'Select the model matching the product. This is not a universal detector.'}

    @app.post('/api/inspect')
    def inspect(category: str = Form(...), image: UploadFile = File(...)):
        started = time.perf_counter()
        if category not in CATEGORIES:
            raise HTTPException(400, 'Unsupported category; choose bottle, grid or transistor')
        content = image.file.read(MAX_FILE_BYTES + 1)
        if not content:
            raise HTTPException(400, 'Image is empty')
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, 'Upload exceeds 10 MiB limit')
        decoded = decode_image(content)
        try:
            result = app.state.registry.inspect(category, decoded)
        except (FileNotFoundError, ValueError, RuntimeError):
            raise HTTPException(503, 'Model unavailable or incompatible. Check local artifacts and heatmap calibration.')
        result['inspection_id'] = str(uuid.uuid4())
        result['timestamp'] = datetime.now(timezone.utc).isoformat()
        result['timing'] = {'model_inference_ms': result.pop('model_inference_ms'),
                            'server_processing_ms': (time.perf_counter() - started) * 1000}
        result['warnings'] = ['Research prototype; not validated for safety-critical inspection.',
                              'Anomaly scores and heatmap colours are not confidence probabilities.',
                              'Benchmark-category models do not establish factory or glasses reliability.']
        # No image bytes, filenames or client identifiers are retained by default.
        record = {k: result[k] for k in ('inspection_id', 'timestamp', 'category', 'decision',
                                         'anomaly_score', 'threshold', 'model_version', 'timing')}
        if os.environ.get('VISUREX_SAVE_IMAGES', '0') == '1':
            raise HTTPException(503, 'Image retention is not implemented; remove VISUREX_SAVE_IMAGES=1')
        try:
            with LOG_LOCK:
                app.state.log_path.parent.mkdir(parents=True, exist_ok=True)
                with app.state.log_path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(record) + '\n')
        except OSError:
            raise HTTPException(503, 'Inspection could not be recorded locally')
        return result

    frontend = ROOT / 'frontend-prototype'
    if frontend.is_dir() and (frontend / 'index.html').is_file():
        app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')
    return app


app = create_app()
