# VisureX Industrial Inspection Prototype — Frontend

A lightweight, accessible, high-contrast visual inspection dashboard connected to the local PatchCore inference service. Built strictly with vanilla HTML5, CSS3, and ES6 JavaScript (zero build step, zero external frameworks, and zero CDN dependencies).

Compliant with **VisureX API Contract v0.1.0** (`docs/API_CONTRACT.md` and `docs/ANTIGRAVITY_PHASE2_CONNECT.md`).

---

## 1. Directory Structure

All frontend files are located inside:
```
development/frontend-prototype/
├── index.html     # Semantic, accessible HTML5 dashboard structure
├── styles.css     # Light theme, responsive layout and keyboard focus styling
├── app.js         # UI controller, drag-and-drop, state machine, centre-crop viewer, stale result safety
├── api.js         # API interface & adapter (HttpInspectionClient vs MockInspectionClient)
└── README.md      # Preview instructions, contract specification, and integration documentation
```

---

## 2. How to Preview Locally

### Option A: Unified Backend Serving (Recommended)
When the FastAPI backend starts, it automatically mounts `frontend-prototype/` at `/` (same-origin):

1. Start the backend service from `development/`:
   ```powershell
   cd C:\Users\Viraj\OneDrive\Desktop\vizurex-edge-ai\development

   # (Optional) Verify heatmap calibration if model files changed
   .\.venv-phase1\Scripts\python.exe scripts\calibrate_heatmaps.py

   # Start the uvicorn service on 127.0.0.1:8000
   .\.venv-phase1\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
   ```
2. Open your browser to:
   **`http://127.0.0.1:8000/`** (or `http://localhost:8000/`)

All API calls (`/api/inspect`, `/api/health`, `/api/models`) run same-origin without CORS overhead.

### Option B: Separate Frontend Server (Port 8080)
If running a standalone static file server:

```powershell
cd C:\Users\Viraj\OneDrive\Desktop\vizurex-edge-ai\development\frontend-prototype
python -m http.server 8080
```
Open your browser to:
**`http://localhost:8080`**

*Note: The backend allows CORS requests from `http://localhost:8080`, `http://127.0.0.1:8080`, `5500`, and `5173`. Direct `file://` opening is not supported for live API calls due to browser origin security restrictions.*

---

## 3. Connected Backend Specification & Verification

### Endpoints
- **Health Check**: `GET /api/health`
- **Model Capabilities**: `GET /api/models`
- **Inspection**: `POST /api/inspect`

### Request Format
- **Content-Type**: `multipart/form-data` (browser automatically generates multipart boundary; no manual header set).
- **Form Fields**:
  - `category`: String enum (`bottle`, `grid`, or `transistor`).
  - `image`: Binary image file (PNG or JPEG only, at most 10 MiB, max 16 megapixels).

### Response Mapping
The frontend strictly maps and validates the verified backend contract:
- `decision`: `"GOOD"` or `"ANOMALY"` (never defaulted or assumed).
- `inspection_id`: Unique UUID audit trace.
- `model_version`: Real model version string (e.g., `phase1-bottle-modelhash`).
- `anomaly_score`: Normalized PatchCore feature distance.
- `threshold`: Real calibrated operating threshold (~`1.0000`).
- `cold_start`: Boolean indicating whether initial model load occurred.
- `timing`:
  - `timing.model_inference_ms`: Pure PyTorch model inference latency.
  - `timing.server_processing_ms`: Backend total processing time.
  - `timing.clientRoundTripMs`: Client round-trip latency measured after reading and parsing the JSON response body.
- `images`:
  - `images.processed`: 224×224 centre crop preprocessed image (`data:image/png;base64,...`).
  - `images.heatmap`: 224×224 thermal anomaly heatmap (`data:image/png;base64,...`).
  - `images.overlay`: 224×224 pre-blended overlay image (`data:image/png;base64,...`).
- `heatmap_scale`: Lower/upper display bounds and calibration method (`normal-validation-pixel-p99`).
- `warnings`: Advisory notices from backend rendered in alert box.

---

## 4. Visual Inspection & Crop Alignment

### 224×224 Centre Crop Alignment
The PatchCore model resizes the short edge to 256px and evaluates a 224×224 centre crop.
- The **Original Source Image** preview is preserved separately in the left capture card.
- In the Inspection Viewer, the heatmap is aligned 1:1 against the **224×224 processed centre crop** (`images.processed`), preventing geometric distortion or misleading stretches across the full image.
- View modes supported:
  - **Blended Overlay**: Blends `images.processed` with `images.heatmap` at user-selected opacity (0% to 100%).
  - **Processed Crop**: Displays the exact 224×224 image patch evaluated by the backbone.
  - **Heatmap Only**: Displays the pure thermal activation map.
  - **Full Upload Preview**: Allows inspecting the uncropped raw source image.

---

## 5. Live Mode vs Demo Mode Switcher

The dashboard includes a prominent, unmistakable mode switcher in the header:
- **Live Backend**: Connects directly to `POST /api/inspect`. Checks `GET /api/health` on startup. If the backend is offline, an explicit notification banner informs the operator and displays the command to launch uvicorn. If a real request fails, the exact backend error is shown (never falling back silently to mock data).
- **Demo Mode**: Explicitly displays **"Demo mode — simulated results"** with UI-only fixture values and synthetic heatmaps for visual design review without a running backend.
  Demo Mode opens on a complete simulated ANOMALY example without any upload, and the
  *Simulated walkthrough* buttons switch between ANOMALY, GOOD and RETAKE examples.
  Every simulated result carries a "SIMULATED EXAMPLE" notice, a "(SIMULATED)" verdict
  label and a fixture model version. Example scores (1.4200 / 0.4200 against threshold
  1.0000) are fixed UI values, not measurements. Open `/?mode=demo` to start in Demo Mode.
- **RETAKE**: a rejected capture is shown as its own result state with the capture-check
  reasons and no score, threshold comparison or heatmap.

---

## 6. Defensive Safety Measures

- **No Stale Results**: Any previously displayed inspection result is immediately purged whenever the user changes the image, changes the target category model, or switches execution mode.
- **Client-Side Validation**:
  - Format validation intercepts non-PNG/JPEG files before network transmission.
  - 10 MiB upload cap is enforced on client side.
  - 16 megapixel ceiling (`width * height <= 16_000_000`) is verified on image decode.
- **Duplicate Submission Guard**: All interactive inputs and submission buttons are disabled while an inspection request is in flight.
- **XSS Prevention**: Dynamic text strings (e.g. IDs, warnings, error details, categories) are injected exclusively through `textContent` and safe DOM manipulation.
- **Clear Disclaimers**: Clarifies that anomaly scores are normalized distance metrics relative to the normal coreset, **not percentage confidences**, and that category models cannot inspect arbitrary components.
