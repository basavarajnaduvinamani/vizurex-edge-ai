/**
 * VisureX Edge AI - Inspection API Client & Adapter
 * File: api.js
 * 
 * Compliant with API Contract v0.1.0 (docs/API_CONTRACT.md & docs/ANTIGRAVITY_PHASE2_CONNECT.md).
 * 
 * Provides:
 * 1. HttpInspectionClient: Production client connecting to the real local backend
 *    at POST /api/inspect with strict response schema validation.
 * 2. MockInspectionClient: Explicit UI-only demonstration fixture mode for testing
 *    the frontend without a running backend.
 * 
 * Crucial Integration Rules:
 * - Real endpoints: POST /api/inspect, GET /api/health, GET /api/models.
 * - Send FormData with 'category' and 'image'. Do NOT set manual Content-Type header.
 * - Strictly validate response fields: decision, anomaly_score, threshold, model_version,
 *   timing.model_inference_ms, images.processed, images.heatmap, images.overlay.
 * - Never default a missing decision to GOOD or missing score to zero.
 * - Never fall back silently to mock results on real request failure.
 * - Aligns 224x224 heatmap with images.processed centre crop.
 */

export const CATEGORY_SPECS = {
  bottle: {
    id: "bottle",
    displayName: "Bottle (MVTec AD)",
    description: "Glass containers; surface contamination, broken neck, cracks",
    scopeWarning: "Category-specific model: Trained strictly on MVTec Bottle normal geometry. Cannot be used to inspect other components."
  },
  grid: {
    id: "grid",
    displayName: "Grid (MVTec AD)",
    description: "Wire mesh; bent wire, broken wire, glue, metal debris",
    scopeWarning: "Category-specific model: Trained strictly on MVTec Grid mesh normal geometry. Cannot be used to inspect other components."
  },
  transistor: {
    id: "transistor",
    displayName: "Transistor (MVTec AD)",
    description: "Semiconductor package; bent leads, cut lead, damaged casing",
    scopeWarning: "Category-specific model: Trained strictly on MVTec Transistor packaging normal geometry. Cannot be used to inspect other components."
  }
};

/**
 * Determine default backend base URL based on browser execution environment.
 * If served on port 8000, relative same-origin paths work directly.
 * If served on a separate dev server (e.g. port 8080, 5500, 5173), target port 8000.
 */
function getDefaultBaseUrl() {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }
  if (window.location.port === "8000") {
    return "";
  }
  const hostname = window.location.hostname || "127.0.0.1";
  const protocol = window.location.protocol || "http:";
  return `${protocol}//${hostname}:8000`;
}

/**
 * Generates synthetic 224x224 images for Demo/UI-fixture mode.
 */
function generateDemoFixtures(isAnomaly) {
  const canvas = document.createElement("canvas");
  canvas.width = 224;
  canvas.height = 224;
  const ctx = canvas.getContext("2d");

  // 1. Processed crop fixture (simulated 224x224 grayscale part)
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(0, 0, 224, 224);
  ctx.fillStyle = "#475569";
  ctx.beginPath();
  ctx.arc(112, 112, 70, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#94a3b8";
  ctx.beginPath();
  ctx.arc(112, 112, 35, 0, Math.PI * 2);
  ctx.fill();
  const processedDataUri = canvas.toDataURL("image/png");

  // 2. Heatmap fixture (224x224 thermal map)
  const imgData = ctx.createImageData(224, 224);
  const data = imgData.data;
  const cx = isAnomaly ? 135 : 112;
  const cy = isAnomaly ? 95 : 112;
  const sigma = isAnomaly ? 24 : 80;

  for (let y = 0; y < 224; y++) {
    for (let x = 0; x < 224; x++) {
      const idx = (y * 224 + x) * 4;
      const dx = x - cx;
      const dy = y - cy;
      const distSq = (dx * dx + dy * dy) / (2 * sigma * sigma);
      let intensity = 0;

      if (isAnomaly) {
        intensity = Math.min(1.0, Math.exp(-distSq) * 1.1);
      } else {
        intensity = Math.min(0.2, (Math.sin(x * 0.1) + Math.cos(y * 0.1) + 2) * 0.05);
      }

      // Colormap: blue -> cyan -> yellow -> red
      if (intensity < 0.15) {
        data[idx] = 20; data[idx + 1] = 45; data[idx + 2] = 100; data[idx + 3] = 255;
      } else if (intensity < 0.45) {
        data[idx] = 0; data[idx + 1] = 170; data[idx + 2] = 210; data[idx + 3] = 255;
      } else if (intensity < 0.75) {
        data[idx] = 255; data[idx + 1] = 210; data[idx + 2] = 55; data[idx + 3] = 255;
      } else {
        data[idx] = 220; data[idx + 1] = 35; data[idx + 2] = 40; data[idx + 3] = 255;
      }
    }
  }
  ctx.putImageData(imgData, 0, 0);
  const heatmapDataUri = canvas.toDataURL("image/png");

  // 3. Overlay fixture (blend)
  ctx.globalAlpha = 0.45;
  const imgProc = new Image();
  imgProc.src = processedDataUri;
  ctx.drawImage(imgProc, 0, 0);
  ctx.globalAlpha = 1.0;
  const overlayDataUri = canvas.toDataURL("image/png");

  return {
    processed: processedDataUri,
    heatmap: heatmapDataUri,
    overlay: overlayDataUri
  };
}

/**
 * Real HTTP Inspection Client connecting to POST /api/inspect.
 */
export class HttpInspectionClient {
  constructor(baseUrl = getDefaultBaseUrl()) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.name = "HttpInspectionClient";
    this.timeoutMs = 30000;
  }

  /**
   * Health probe checking GET /api/health
   */
  async checkHealth() {
    try {
      const endpoint = `${this.baseUrl}/api/health`;
      const response = await fetch(endpoint, {
        method: "GET",
        signal: AbortSignal.timeout ? AbortSignal.timeout(4000) : undefined
      });
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }

  /**
   * Model metadata probe checking GET /api/models
   */
  async getModels() {
    try {
      const endpoint = `${this.baseUrl}/api/models`;
      const response = await fetch(endpoint, {
        method: "GET",
        signal: AbortSignal.timeout ? AbortSignal.timeout(4000) : undefined
      });
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }

  /**
   * Run real image inspection against backend POST /api/inspect.
   * Sends FormData with 'category' and 'image'.
   * Does NOT set manual Content-Type header.
   */
  async inspectImage({ file, category, signal }) {
    if (!file) {
      throw new Error("No image file provided for inspection.");
    }
    if (!["bottle", "grid", "transistor"].includes(category)) {
      throw new Error(`Invalid category "${category}". Must be bottle, grid, or transistor.`);
    }

    const endpoint = `${this.baseUrl}/api/inspect`;
    const formData = new FormData();
    formData.append("category", category);
    formData.append("image", file);

    const startTime = performance.now();
    let response;

    try {
      response = await fetch(endpoint, {
        method: "POST",
        body: formData,
        signal: signal || (AbortSignal.timeout ? AbortSignal.timeout(this.timeoutMs) : undefined)
      });
    } catch (err) {
      if (err.name === "AbortError" || err.name === "TimeoutError") {
        throw new Error(`Inspection request timed out after ${this.timeoutMs}ms. Verify backend is running.`);
      }
      throw new Error(`Network failure connecting to backend (${this.baseUrl || "same-origin"}): ${err.message}`);
    }

    // Capture round-trip timing after parsing response body
    let rawBody;
    try {
      rawBody = await response.text();
    } catch (err) {
      throw new Error(`Failed to read response stream from backend: ${err.message}`);
    }

    // Handle non-2xx HTTP errors
    if (!response.ok) {
      let errorDetail = `Backend returned HTTP ${response.status} (${response.statusText})`;
      try {
        const errorJson = JSON.parse(rawBody);
        if (errorJson && errorJson.detail) {
          if (Array.isArray(errorJson.detail)) {
            errorDetail = errorJson.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
          } else {
            errorDetail = errorJson.detail;
          }
        }
      } catch (_) {
        if (rawBody && rawBody.length < 250) {
          errorDetail = rawBody;
        }
      }

      // Friendly context mapping for status codes
      if (response.status === 403) {
        errorDetail = `CORS Origin Rejected (403): ${errorDetail}. Ensure frontend runs on an allowed origin (ports 8000, 8080, 5500, 5173).`;
      } else if (response.status === 413) {
        errorDetail = `Upload Limit Exceeded (413): ${errorDetail}. Max file size is 10 MiB, max resolution 16 megapixels.`;
      } else if (response.status === 415) {
        errorDetail = `Unsupported Media Type (415): ${errorDetail}. Only PNG and JPEG formats are supported.`;
      } else if (response.status === 503) {
        errorDetail = `Model Service Unavailable (503): ${errorDetail}. Verify Phase 1 model artifacts and calibration existence.`;
      }

      const error = new Error(errorDetail);
      error.status = response.status;
      error.isMock = false;
      throw error;
    }

    // Parse JSON
    let data;
    try {
      data = JSON.parse(rawBody);
    } catch (err) {
      throw new Error(`Malformed backend response: Expected JSON, received: ${rawBody.slice(0, 100)}...`);
    }
    const clientRoundTripMs = Math.round(performance.now() - startTime);

    // Strict validation of actual response contract
    if (!data || typeof data !== "object") {
      throw new Error("Malformed response: Backend payload is not an object.");
    }
    if (typeof data.decision !== "string" || !["GOOD", "ANOMALY"].includes(data.decision)) {
      throw new Error(`Malformed response: Missing or invalid 'decision' field: ${JSON.stringify(data.decision)}`);
    }
    if (typeof data.anomaly_score !== "number" || !Number.isFinite(data.anomaly_score)) {
      throw new Error(`Malformed response: Missing or non-finite 'anomaly_score': ${JSON.stringify(data.anomaly_score)}`);
    }
    if (typeof data.threshold !== "number" || !Number.isFinite(data.threshold)) {
      throw new Error(`Malformed response: Missing or non-finite 'threshold': ${JSON.stringify(data.threshold)}`);
    }
    for (const field of ['inspection_id', 'timestamp', 'model_version']) {
      if (typeof data[field] !== 'string' || !data[field].trim()) {
        throw new Error(`Malformed response: Missing or invalid '${field}'.`);
      }
    }
    if (data.category !== category) {
      throw new Error('Malformed response: Result category does not match the requested model.');
    }
    if (!Number.isFinite(Date.parse(data.timestamp)) || typeof data.cold_start !== 'boolean') {
      throw new Error('Malformed response: Invalid timestamp or cold_start.');
    }
    if (!data.images || typeof data.images !== "object") {
      throw new Error("Malformed response: Missing 'images' object.");
    }
    if (!data.images.processed || !data.images.heatmap || !data.images.overlay) {
      throw new Error("Malformed response: 'images' must contain 'processed', 'heatmap', and 'overlay'.");
    }
    if (!data.timing || typeof data.timing.model_inference_ms !== "number") {
      throw new Error("Malformed response: Missing 'timing.model_inference_ms'.");
    }
    for (const field of ['model_inference_ms', 'server_processing_ms']) {
      if (!Number.isFinite(data.timing[field]) || data.timing[field] < 0) {
        throw new Error(`Malformed response: Invalid timing.${field}.`);
      }
    }
    for (const field of ['processed', 'heatmap', 'overlay']) {
      if (typeof data.images[field] !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(data.images[field])) {
        throw new Error(`Malformed response: Invalid images.${field}.`);
      }
    }

    const spec = CATEGORY_SPECS[data.category] || CATEGORY_SPECS[category] || CATEGORY_SPECS.bottle;
    const isAnomaly = data.decision === "ANOMALY";

    return {
      inspectionId: String(data.inspection_id || "N/A"),
      timestamp: String(data.timestamp || new Date().toISOString()),
      category: data.category || category,
      categoryDisplayName: spec.displayName,
      categoryScopeWarning: spec.scopeWarning,
      decision: data.decision,
      status: data.decision,
      isAnomaly: isAnomaly,
      anomalyScore: data.anomaly_score,
      threshold: data.threshold,
      modelVersion: String(data.model_version || "unknown"),
      coldStart: Boolean(data.cold_start),
      timing: {
        modelInferenceMs: Math.round(data.timing.model_inference_ms * 10) / 10,
        serverProcessingMs: data.timing.server_processing_ms != null ? Math.round(data.timing.server_processing_ms * 10) / 10 : null,
        clientRoundTripMs: clientRoundTripMs
      },
      images: {
        processed: data.images.processed, // 224x224 centre crop
        heatmap: data.images.heatmap,     // 224x224 heatmap
        overlay: data.images.overlay      // 224x224 pre-blended overlay
      },
      heatmapScale: data.heatmap_scale || null,
      preprocessing: data.preprocessing || null,
      warnings: Array.isArray(data.warnings) ? data.warnings : [],
      isMock: false,
      demoNotice: null,
      scoreExplanation: "Anomaly score represents normalized PatchCore feature distance relative to normal validation baseline, NOT a confidence percentage. Scores at or exceeding the threshold indicate anomalous feature deviation."
    };
  }
}

/**
 * Mock Inspection Client: Explicit UI-Only Fixture Mode.
 * Fabricated values are explicitly labelled as UI-only fixtures.
 */
export class MockInspectionClient {
  constructor() {
    this.name = "MockInspectionClient";
  }

  async checkHealth() {
    return { status: "ok", mode: "mock-ui-fixture", api_version: "0.1.0-mock" };
  }

  async getModels() {
    return {
      models: [
        { category: "bottle", artifacts_present: true, calibrated: true, cached: false },
        { category: "grid", artifacts_present: true, calibrated: true, cached: false },
        { category: "transistor", artifacts_present: true, calibrated: true, cached: false }
      ],
      max_upload_bytes: 10 * 1024 * 1024,
      supported_formats: ["PNG", "JPEG"],
      max_pixels: 16000000,
      warning: "UI-only demonstration fixtures."
    };
  }

  async inspectImage({ file, category, simulationType = "auto" }) {
    const spec = CATEGORY_SPECS[category] || CATEGORY_SPECS.bottle;

    // Simulate realistic UI latency (~240ms)
    await new Promise((resolve) => setTimeout(resolve, 240));

    if (simulationType === "error") {
      const error = new Error("Simulated backend fault: Model coreset buffer timeout (DEMO_FAULT_500).");
      error.status = 500;
      error.isMock = true;
      throw error;
    }

    let isAnomaly = false;
    if (simulationType === "anomaly") {
      isAnomaly = true;
    } else if (simulationType === "good") {
      isAnomaly = false;
    } else {
      const name = (file && file.name ? file.name.toLowerCase() : "");
      if (name.includes("good") || name.includes("pass") || name.includes("normal")) {
        isAnomaly = false;
      } else {
        isAnomaly = true;
      }
    }

    // Operating threshold is approximately 1.0 (UI fixture)
    const threshold = 1.0000;
    const score = isAnomaly
      ? parseFloat((1.15 + Math.random() * 0.45).toFixed(4))
      : parseFloat((0.25 + Math.random() * 0.35).toFixed(4));

    const decision = isAnomaly ? "ANOMALY" : "GOOD";
    const fixtures = generateDemoFixtures(isAnomaly);

    return {
      inspectionId: `INSP-DEMO-${Date.now().toString(36).toUpperCase()}`,
      timestamp: new Date().toISOString(),
      category: category,
      categoryDisplayName: spec.displayName,
      categoryScopeWarning: spec.scopeWarning,
      decision: decision,
      status: decision,
      isAnomaly: isAnomaly,
      anomalyScore: score,
      threshold: threshold,
      modelVersion: `demo-fixture-${category}-v1.0 (Simulated)`,
      coldStart: false,
      timing: {
        modelInferenceMs: 165.0,
        serverProcessingMs: 190.0,
        clientRoundTripMs: 240
      },
      images: fixtures,
      heatmapScale: {
        lower: 0.0,
        upper: 10.0,
        method: "normal-validation-pixel-p99",
        is_probability: false
      },
      preprocessing: {
        resize_short_edge: 256,
        center_crop: 224,
        display_region: "processed image and overlays show only the centre crop"
      },
      warnings: [
        "Demo mode: Simulated UI fixture results.",
        "Anomaly scores and heatmap colours are not confidence probabilities."
      ],
      isMock: true,
      demoNotice: "Demo mode — simulated results",
      scoreExplanation: "Anomaly score represents normalized PatchCore feature distance relative to normal validation baseline, NOT a confidence percentage. Scores at or exceeding the threshold indicate anomalous feature deviation."
    };
  }
}

/**
 * Inspection API Facade with Live / Mock Mode management.
 */
class InspectionApi {
  constructor() {
    this.httpClient = new HttpInspectionClient();
    this.mockClient = new MockInspectionClient();
    // Default to 'live' mode as per Phase 2 handoff; fallback to mock selectable in UI
    this.activeMode = "live";
  }

  getMode() {
    return this.activeMode;
  }

  setMode(mode) {
    if (mode !== "live" && mode !== "mock") {
      throw new Error(`Invalid mode "${mode}". Expected 'live' or 'mock'.`);
    }
    this.activeMode = mode;
  }

  getBaseUrl() {
    return this.httpClient.baseUrl;
  }

  setBaseUrl(url) {
    this.httpClient = new HttpInspectionClient(url);
  }

  async checkBackendHealth() {
    return this.httpClient.checkHealth();
  }

  async getBackendModels() {
    return this.httpClient.getModels();
  }

  async inspect(params) {
    if (this.activeMode === "live") {
      return this.httpClient.inspectImage(params);
    }
    return this.mockClient.inspectImage(params);
  }
}

export const api = new InspectionApi();
