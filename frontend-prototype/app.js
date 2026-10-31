/**
 * VisureX Industrial Inspection Prototype - Application Controller
 * File: app.js
 *
 * Compliant with API Contract v0.1.0 and ANTIGRAVITY_PHASE2_CONNECT.md.
 *
 * Controls UI interactions, file validation (PNG/JPEG <= 10 MiB, <= 16 MP),
 * live backend communication (POST /api/inspect) and explicit UI demo fixtures,
 * centre-crop (224x224) viewer alignment, stale result clearing, and safe DOM rendering.
 */

import { api, CATEGORY_SPECS } from "./api.js?v=phase3-3";

document.getElementById('refreshInspectionLog').addEventListener('click', async () => {
  const output = document.getElementById('recentInspectionLog');
  output.textContent = 'Reading local metadata…';
  try {
    const key = document.getElementById('sessionAccessKey')?.value || '';
    const response = await fetch('/api/inspections/recent', {
      headers: key ? {'X-Visurex-Key': key} : {}
    });
    if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
    const result = await response.json();
    output.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    output.textContent = `Log unavailable: ${error.message}`;
  }
});

// Validation Constants per backend specification
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MiB limit
const MAX_PIXEL_COUNT = 16_000_000;          // 16 Megapixels limit
const ALLOWED_MIME_TYPES = new Set(["image/png", "image/jpeg"]);
const ALLOWED_EXTENSIONS = new Set(["png", "jpg", "jpeg"]);

/**
 * Application State
 */
const state = {
  selectedCategory: "bottle",
  selectedFile: null,
  previewObjectUrl: null,
  currentResult: null,
  isInspecting: false,
  selectionVersion: 0,
  viewMode: "overlay", // "overlay" | "processed" | "heatmap" | "original"
  heatmapOpacity: 0.45, // Aligned with backend default blend ratio
  executionMode: "live", // "live" | "demo"
  backendOnline: false
};

// DOM Element Cache
const elements = {
  // Mode Switcher & Status
  btnModeLive: document.getElementById("btnModeLive"),
  btnModeDemo: document.getElementById("btnModeDemo"),
  connectionBadge: document.getElementById("connectionBadge"),
  connectionDot: document.getElementById("connectionDot"),
  connectionText: document.getElementById("connectionText"),
  activeModeLabel: document.getElementById("activeModeLabel"),
  resultModeTag: document.getElementById("resultModeTag"),
  demoControlsBox: document.getElementById("demoControlsBox"),
  simulationTypeSelect: document.getElementById("simulationTypeSelect"),
  footerBackendStatus: document.getElementById("footerBackendStatus"),

  // Notification Banner
  notificationBanner: document.getElementById("notificationBanner"),
  notificationMessage: document.getElementById("notificationMessage"),
  notificationCloseBtn: document.getElementById("notificationCloseBtn"),

  // Category Selector Cards
  categoryCards: {
    bottle: document.getElementById("cardBottle"),
    grid: document.getElementById("cardGrid"),
    transistor: document.getElementById("cardTransistor")
  },
  categoryRadios: document.querySelectorAll('input[name="categoryModel"]'),

  // Dropzone & File Input
  dropzone: document.getElementById("dropzone"),
  imageFileInput: document.getElementById("imageFileInput"),
  previewCard: document.getElementById("previewCard"),
  previewThumbnail: document.getElementById("previewThumbnail"),
  previewFilename: document.getElementById("previewFilename"),
  previewMeta: document.getElementById("previewMeta"),
  btnRemoveImage: document.getElementById("btnRemoveImage"),

  // Inspect CTA
  btnRunInspection: document.getElementById("btnRunInspection"),
  btnIcon: document.getElementById("btnIcon"),
  btnLabel: document.getElementById("btnLabel"),

  // Result Panel States
  stateEmpty: document.getElementById("stateEmpty"),
  stateLoading: document.getElementById("stateLoading"),
  loadingSubtext: document.getElementById("loadingSubtext"),
  stateResult: document.getElementById("stateResult"),
  stateRetake: document.getElementById("stateRetake"),
  retakeInspectionId: document.getElementById("retakeInspectionId"),
  retakeReasons: document.getElementById("retakeReasons"),
  retakeSimulatedRibbon: document.getElementById("retakeSimulatedRibbon"),
  simulatedRibbon: document.getElementById("simulatedRibbon"),
  decisionRule: document.getElementById("decisionRule"),

  // Demo walkthrough buttons (Demo Mode only)
  btnExampleAnomaly: document.getElementById("btnExampleAnomaly"),
  btnExampleGood: document.getElementById("btnExampleGood"),
  btnExampleRetake: document.getElementById("btnExampleRetake"),

  // Result Presentation
  resultHeaderCard: document.getElementById("resultHeaderCard"),
  statusBadge: document.getElementById("statusBadge"),
  statusIcon: document.getElementById("statusIcon"),
  statusText: document.getElementById("statusText"),
  resInspectionId: document.getElementById("resInspectionId"),
  resTimestamp: document.getElementById("resTimestamp"),
  coldStartPill: document.getElementById("coldStartPill"),

  // Metric Cards & Gauge
  metricScoreValue: document.getElementById("metricScoreValue"),
  metricThresholdValue: document.getElementById("metricThresholdValue"),
  scoreGaugeFill: document.getElementById("scoreGaugeFill"),
  scoreGaugeMarker: document.getElementById("scoreGaugeMarker"),
  captionThresholdVal: document.getElementById("captionThresholdVal"),

  // Viewer
  tabOverlay: document.getElementById("tabOverlay"),
  tabProcessed: document.getElementById("tabProcessed"),
  tabHeatmap: document.getElementById("tabHeatmap"),
  tabOriginal: document.getElementById("tabOriginal"),
  opacityWrap: document.getElementById("opacityWrap"),
  opacitySlider: document.getElementById("opacitySlider"),
  opacityLabel: document.getElementById("opacityLabel"),
  viewerProcessedImg: document.getElementById("viewerProcessedImg"),
  viewerHeatmapImg: document.getElementById("viewerHeatmapImg"),
  viewerOriginalFullImg: document.getElementById("viewerOriginalFullImg"),

  // Telemetry Table
  tableCategory: document.getElementById("tableCategory"),
  tableModel: document.getElementById("tableModel"),
  tableInferenceLatency: document.getElementById("tableInferenceLatency"),
  tableServerLatency: document.getElementById("tableServerLatency"),
  tableTotalLatency: document.getElementById("tableTotalLatency"),
  tableHeatmapScale: document.getElementById("tableHeatmapScale"),

  // Warnings & Scope
  backendWarningsBox: document.getElementById("backendWarningsBox"),
  backendWarningsList: document.getElementById("backendWarningsList"),
  scopeAdvisory: document.getElementById("scopeAdvisory")
};

/**
 * Display notification banner safely using textContent.
 */
function showNotification(message, isError = true) {
  elements.notificationMessage.textContent = message;
  elements.notificationBanner.classList.remove("is-hidden");
  if (isError) {
    elements.notificationBanner.classList.add("is-error");
  } else {
    elements.notificationBanner.classList.remove("is-error");
  }
}

/**
 * Hide notification banner.
 */
function hideNotification() {
  elements.notificationBanner.classList.add("is-hidden");
  elements.notificationMessage.textContent = "";
}

/**
 * Format bytes to human readable format (e.g. 2.45 MB).
 */
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Revoke object URL to avoid client memory leaks.
 */
function cleanupPreviewUrl() {
  if (state.previewObjectUrl) {
    URL.revokeObjectURL(state.previewObjectUrl);
    state.previewObjectUrl = null;
  }
}

/**
 * Resets the inspection result panel to Empty state.
 * CRITICAL RULE: Clears state whenever category, image, or mode changes to prevent stale results.
 */
function clearInspectionResult() {
  state.currentResult = null;
  elements.stateResult.classList.add("is-hidden");
  elements.stateRetake.classList.add("is-hidden");
  elements.stateLoading.classList.add("is-hidden");
  elements.stateEmpty.classList.remove("is-hidden");

  // Reset viewer image sources
  elements.viewerProcessedImg.src = "";
  elements.viewerHeatmapImg.src = "";
  elements.viewerOriginalFullImg.src = "";
}

/**
 * Check backend connectivity via GET /api/health.
 */
async function checkBackendConnectivity() {
  const health = await api.checkBackendHealth();
  if (health && health.status === "ok") {
    state.backendOnline = true;
    if (state.executionMode === "live") {
      elements.connectionBadge.className = "badge badge-live";
      elements.connectionDot.className = "pulse-dot green";
      elements.connectionText.textContent = "Backend Online";
      elements.footerBackendStatus.textContent = `Backend: ${api.getBaseUrl() || 'same-origin'} (Connected)`;
    }
    return true;
  } else {
    state.backendOnline = false;
    if (state.executionMode === "live") {
      elements.connectionBadge.className = "badge badge-offline";
      elements.connectionDot.className = "pulse-dot red";
      elements.connectionText.textContent = "Backend Offline (Port 8000)";
      elements.footerBackendStatus.textContent = `Backend: ${api.getBaseUrl() || 'same-origin'} (Offline)`;
      showNotification(
        "Backend unreachable. Check the laptop service and USB/Wi-Fi connection. Demo Mode shows simulated results only.",
        false
      );
    }
    return false;
  }
}

/**
 * Switch Execution Mode between Live Backend and Demo Mode.
 */
function setExecutionMode(mode) {
  if (mode !== "live" && mode !== "demo") return;
  state.executionMode = mode;
  api.setMode(mode === "live" ? "live" : "mock");

  elements.btnModeLive.classList.toggle("is-active", mode === "live");
  elements.btnModeDemo.classList.toggle("is-active", mode === "demo");

  if (mode === "live") {
    elements.activeModeLabel.textContent = "Live Mode";
    elements.resultModeTag.textContent = "Live Backend";
    elements.resultModeTag.className = "badge badge-baseline";
    elements.demoControlsBox.classList.add("is-hidden");
    checkBackendConnectivity();
  } else {
    elements.activeModeLabel.textContent = "Demo Mode";
    elements.resultModeTag.textContent = "Simulated Fixture";
    elements.resultModeTag.className = "badge badge-demo";
    elements.demoControlsBox.classList.remove("is-hidden");
    elements.connectionBadge.className = "badge badge-demo";
    elements.connectionDot.className = "pulse-dot";
    elements.connectionText.textContent = "Demo mode — simulated results";
    hideNotification();
  }

  // Stale result safety: switching execution mode invalidates prior result
  clearInspectionResult();

  // Demo Mode opens on a complete, clearly labelled simulated example.
  if (mode === "demo" && !state.selectedFile) {
    showDemoExample("anomaly");
  }
}

/**
 * Set active model category and update radio card styling.
 */
function setCategory(category) {
  if (!CATEGORY_SPECS[category]) return;
  state.selectedCategory = category;

  elements.categoryRadios.forEach((radio) => {
    radio.checked = radio.value === category;
  });

  Object.keys(elements.categoryCards).forEach((catKey) => {
    const card = elements.categoryCards[catKey];
    if (catKey === category) {
      card.classList.add("is-selected");
    } else {
      card.classList.remove("is-selected");
    }
  });

  // Stale result safety: changing category immediately clears prior result
  clearInspectionResult();
  hideNotification();
}

/**
 * Handle and validate uploaded image file.
 * Enforces PNG and JPEG only, max 10 MiB, max 16 MP.
 */
function handleFileSelection(file) {
  if (state.isInspecting) return;
  hideNotification();

  if (!file) return;

  // 1. Format validation (PNG/JPEG only)
  const fileType = file.type ? file.type.toLowerCase() : "";
  const ext = file.name ? file.name.split(".").pop().toLowerCase() : "";
  const isAllowedMime = ALLOWED_MIME_TYPES.has(fileType);
  const isAllowedExt = ALLOWED_EXTENSIONS.has(ext);

  if (!isAllowedMime && !isAllowedExt) {
    showNotification(
      `Unsupported format "${file.name}". The inspection backend strictly supports PNG and JPEG images.`,
      true
    );
    return;
  }

  // 2. File size validation (10 MiB cap)
  if (file.size > MAX_FILE_SIZE_BYTES) {
    showNotification(
      `File "${file.name}" is too large (${formatFileSize(file.size)}). Maximum allowed upload size is 10 MiB.`,
      true
    );
    return;
  }

  // Clean previous preview URL
  cleanupPreviewUrl();

  state.selectedFile = file;
  const selectionVersion = ++state.selectionVersion;
  elements.btnRunInspection.disabled = true;
  state.previewObjectUrl = URL.createObjectURL(file);

  // Stale result safety: changing image clears previous inspection result
  clearInspectionResult();

  // Populate preview card
  elements.previewFilename.textContent = file.name;
  elements.previewThumbnail.src = state.previewObjectUrl;

  // 3. Pixel count validation (16 megapixels cap)
  const tempImg = new Image();
  tempImg.onload = () => {
    if (selectionVersion !== state.selectionVersion) return;
    const pixels = tempImg.naturalWidth * tempImg.naturalHeight;
    if (pixels > MAX_PIXEL_COUNT) {
      removeSelectedFile();
      showNotification(
        `Image exceeds 16 megapixels limit (${tempImg.naturalWidth} × ${tempImg.naturalHeight} = ${(pixels / 1e6).toFixed(1)} MP). Please resize before inspecting.`,
        true
      );
      return;
    }
    elements.previewMeta.textContent = `${formatFileSize(file.size)} • ${tempImg.naturalWidth} × ${tempImg.naturalHeight} px`;
    elements.previewCard.classList.remove("is-hidden");
    elements.dropzone.classList.add("is-hidden");
    elements.btnRunInspection.disabled = false;
  };
  tempImg.onerror = () => {
    if (selectionVersion !== state.selectionVersion) return;
    removeSelectedFile();
    showNotification(`Could not decode image "${file.name}". File may be damaged.`, true);
  };
  tempImg.src = state.previewObjectUrl;
}

/**
 * Remove selected image file and reset input.
 */
function removeSelectedFile() {
  if (state.isInspecting) return;
  state.selectionVersion++;
  cleanupPreviewUrl();
  state.selectedFile = null;
  elements.imageFileInput.value = "";

  elements.previewCard.classList.add("is-hidden");
  elements.dropzone.classList.remove("is-hidden");
  elements.btnRunInspection.disabled = true;

  clearInspectionResult();
  hideNotification();
}

/**
 * Update Viewer tabs and image visibility.
 * Implements strict crop alignment: processed 224x224 crop aligned 1:1 with heatmap.
 */
function updateViewMode(mode) {
  state.viewMode = mode;

  elements.tabOverlay.classList.toggle("is-active", mode === "overlay");
  elements.tabProcessed.classList.toggle("is-active", mode === "processed");
  elements.tabHeatmap.classList.toggle("is-active", mode === "heatmap");
  elements.tabOriginal.classList.toggle("is-active", mode === "original");

  elements.tabOverlay.setAttribute("aria-selected", mode === "overlay");
  elements.tabProcessed.setAttribute("aria-selected", mode === "processed");
  elements.tabHeatmap.setAttribute("aria-selected", mode === "heatmap");
  elements.tabOriginal.setAttribute("aria-selected", mode === "original");

  if (mode === "overlay") {
    elements.viewerProcessedImg.classList.remove("is-hidden");
    elements.viewerProcessedImg.style.opacity = "1";
    elements.viewerHeatmapImg.style.display = "block";
    elements.viewerHeatmapImg.style.opacity = state.heatmapOpacity.toString();
    elements.viewerOriginalFullImg.classList.add("is-hidden");
    elements.opacityWrap.classList.remove("is-hidden");
    elements.opacitySlider.disabled = false;
  } else if (mode === "processed") {
    elements.viewerProcessedImg.classList.remove("is-hidden");
    elements.viewerProcessedImg.style.opacity = "1";
    elements.viewerHeatmapImg.style.display = "none";
    elements.viewerOriginalFullImg.classList.add("is-hidden");
    elements.opacityWrap.classList.add("is-hidden");
  } else if (mode === "heatmap") {
    elements.viewerProcessedImg.classList.add("is-hidden");
    elements.viewerHeatmapImg.style.display = "block";
    elements.viewerHeatmapImg.style.opacity = "1";
    elements.viewerOriginalFullImg.classList.add("is-hidden");
    elements.opacityWrap.classList.add("is-hidden");
  } else if (mode === "original") {
    elements.viewerProcessedImg.classList.add("is-hidden");
    elements.viewerHeatmapImg.style.display = "none";
    elements.viewerOriginalFullImg.classList.remove("is-hidden");
    elements.opacityWrap.classList.add("is-hidden");
  }
}

/**
 * Render the verified inspection result in the UI.
 */
function renderInspectionResult(result) {
  state.currentResult = result;

  // 1. Verdict header styling
  const isAnomaly = result.decision === "ANOMALY";
  if (isAnomaly) {
    elements.resultHeaderCard.className = "result-header-card is-anomaly";
    elements.statusBadge.className = "status-badge-lg is-anomaly";
    elements.statusIcon.textContent = "✕";
    elements.statusText.textContent = result.isMock ? "ANOMALY (SIMULATED)" : "ANOMALY DETECTED";
    elements.metricScoreValue.className = "metric-value highlight-anomaly";
    elements.scoreGaugeFill.className = "score-gauge-fill is-anomaly";
  } else {
    elements.resultHeaderCard.className = "result-header-card is-good";
    elements.statusBadge.className = "status-badge-lg is-good";
    elements.statusIcon.textContent = "✓";
    elements.statusText.textContent = result.isMock ? "GOOD (SIMULATED)" : "PASS — NORMAL (GOOD)";
    elements.metricScoreValue.className = "metric-value highlight-good";
    elements.scoreGaugeFill.className = "score-gauge-fill is-good";
  }

  // 2. Inspection ID & timestamp
  elements.resInspectionId.textContent = result.inspectionId || "N/A";
  elements.resTimestamp.textContent = new Date(result.timestamp).toLocaleTimeString();

  // Cold start pill
  if (result.coldStart) {
    elements.coldStartPill.classList.remove("is-hidden");
  } else {
    elements.coldStartPill.classList.add("is-hidden");
  }

  // 3. Metric cards
  elements.metricScoreValue.textContent = result.anomalyScore.toFixed(4);
  elements.metricThresholdValue.textContent = result.threshold.toFixed(4);
  elements.captionThresholdVal.textContent = result.threshold.toFixed(2);

  // 4. Gauge bar calculation
  const maxScale = Math.max(2.0, result.anomalyScore * 1.15);
  const scorePercent = Math.min(100, Math.max(0, (result.anomalyScore / maxScale) * 100));
  const thresholdPercent = Math.min(100, Math.max(0, (result.threshold / maxScale) * 100));

  elements.scoreGaugeFill.style.width = `${scorePercent.toFixed(1)}%`;
  elements.scoreGaugeMarker.style.left = `${thresholdPercent.toFixed(1)}%`;
  const comparison = result.anomalyScore >= result.threshold ? "≥" : "<";
  elements.decisionRule.textContent = `Decision rule: score ${result.anomalyScore.toFixed(4)} ${comparison} threshold ${result.threshold.toFixed(4)} → ${result.decision}`;
  elements.simulatedRibbon.classList.toggle("is-hidden", !result.isMock);

  // 5. Image & Heatmap viewer:
  // Crucial: Use result.images.processed (224x224 crop) aligned 1:1 with heatmap
  elements.viewerProcessedImg.src = result.images.processed;
  elements.viewerHeatmapImg.src = result.images.heatmap;
  elements.viewerOriginalFullImg.src = state.previewObjectUrl || result.images.processed;
  updateViewMode("overlay");

  // 6. Traceability & Latency table
  elements.tableCategory.textContent = result.categoryDisplayName || result.category;
  elements.tableModel.textContent = result.modelVersion || "unknown";
  elements.tableInferenceLatency.textContent = `${result.timing.modelInferenceMs.toFixed(1)} ms (PyTorch CPU)`;
  elements.tableServerLatency.textContent = result.timing.serverProcessingMs != null
    ? `${result.timing.serverProcessingMs.toFixed(1)} ms (Server Processing)`
    : "N/A";
  elements.tableTotalLatency.textContent = `${result.timing.clientRoundTripMs} ms (Client Round-Trip)`;

  // Heatmap scale
  if (result.heatmapScale) {
    elements.tableHeatmapScale.textContent = `[${result.heatmapScale.lower}, ${result.heatmapScale.upper}] (${result.heatmapScale.method})`;
  } else {
    elements.tableHeatmapScale.textContent = "N/A";
  }

  // 7. Backend Warnings Box
  if (result.warnings && result.warnings.length > 0) {
    elements.backendWarningsList.innerHTML = "";
    result.warnings.forEach((warn) => {
      const li = document.createElement("li");
      li.textContent = warn;
      elements.backendWarningsList.appendChild(li);
    });
    elements.backendWarningsBox.classList.remove("is-hidden");
  } else {
    elements.backendWarningsBox.classList.add("is-hidden");
  }

  // 8. Scope warning
  elements.scopeAdvisory.textContent = result.categoryScopeWarning || "Category-specific model. Do not use on other components.";

  // Mode tag
  if (result.isMock) {
    elements.resultModeTag.textContent = "Simulated Fixture";
    elements.resultModeTag.className = "badge badge-demo";
  } else {
    elements.resultModeTag.textContent = "Live Backend";
    elements.resultModeTag.className = "badge badge-baseline";
  }

  // Switch states
  elements.stateEmpty.classList.add("is-hidden");
  elements.stateLoading.classList.add("is-hidden");
  elements.stateRetake.classList.add("is-hidden");
  elements.stateResult.classList.remove("is-hidden");
}

/**
 * Render a RETAKE outcome: the capture was rejected before the detector ran,
 * so there is deliberately no score, threshold comparison or heatmap.
 */
function renderRetakeResult(result) {
  state.currentResult = result;
  elements.retakeInspectionId.textContent = result.inspectionId || "N/A";
  elements.retakeReasons.innerHTML = "";
  result.quality.reasons.forEach((reason) => {
    const li = document.createElement("li");
    li.textContent = reason;
    elements.retakeReasons.appendChild(li);
  });
  elements.retakeSimulatedRibbon.classList.toggle("is-hidden", !result.isMock);
  elements.stateEmpty.classList.add("is-hidden");
  elements.stateLoading.classList.add("is-hidden");
  elements.stateResult.classList.add("is-hidden");
  elements.stateRetake.classList.remove("is-hidden");
  showNotification((result.isMock ? "SIMULATED " : "") + "RETAKE — " + result.quality.reasons.join(" ") + " No defect decision was made.", true);
}

/**
 * Demo Mode only: show a complete simulated example without an upload, so the
 * whole flow (decision, score vs threshold, heatmap, RETAKE) can be reviewed.
 */
async function showDemoExample(kind) {
  if (state.executionMode !== "demo" || state.isInspecting) return;
  const category = state.selectedCategory;
  const version = state.selectionVersion;
  hideNotification();
  try {
    const result = await api.inspect({ file: null, category, simulationType: kind });
    // Discard if the user changed mode, category or image meanwhile.
    if (state.executionMode !== "demo" || category !== state.selectedCategory || version !== state.selectionVersion) return;
    if (result.decision === "RETAKE") {
      renderRetakeResult(result);
    } else {
      renderInspectionResult(result);
    }
  } catch (err) {
    showNotification(err.message || "Could not build the simulated example.", true);
  }
}

/**
 * Execute the inspection workflow.
 */
async function runInspection() {
  if (state.isInspecting || !state.selectedFile) return;

  state.isInspecting = true;
  const inspectedFile = state.selectedFile;
  const inspectedCategory = state.selectedCategory;
  const inspectedVersion = state.selectionVersion;
  hideNotification();

  // Prevent duplicate submissions while in-flight
  elements.btnRunInspection.disabled = true;
  elements.btnRemoveImage.disabled = true;
  elements.imageFileInput.disabled = true;
  elements.dropzone.setAttribute('aria-disabled', 'true');
  elements.categoryRadios.forEach((r) => (r.disabled = true));
  elements.btnModeLive.disabled = true;
  elements.btnModeDemo.disabled = true;
  [elements.btnExampleAnomaly, elements.btnExampleGood, elements.btnExampleRetake].forEach((b) => (b.disabled = true));
  document.getElementById('qualityModeSelect').disabled = true;
  document.getElementById('sessionAccessKey').disabled = true;
  document.getElementById('applyAccessKey').disabled = true;
  elements.btnLabel.textContent = "Evaluating...";
  elements.btnIcon.textContent = "⏳";

  // Show loading state
  elements.stateEmpty.classList.add("is-hidden");
  elements.stateResult.classList.add("is-hidden");
  elements.stateLoading.classList.remove("is-hidden");

  const spec = CATEGORY_SPECS[state.selectedCategory];
  if (state.executionMode === "live") {
    elements.loadingSubtext.textContent = `Sending image to backend POST /api/inspect (${spec.displayName})...`;
  } else {
    elements.loadingSubtext.textContent = `Generating simulated fixture for ${spec.displayName}...`;
  }

  try {
    const simulationType = elements.simulationTypeSelect.value;
    const result = await api.inspect({
      file: inspectedFile,
      category: inspectedCategory,
      simulationType: simulationType,
      qualityMode: document.getElementById('qualityModeSelect').value
    });

    if (inspectedVersion === state.selectionVersion && inspectedFile === state.selectedFile && inspectedCategory === state.selectedCategory) {
      if (result.decision === 'RETAKE') {
        renderRetakeResult(result);
      } else {
        renderInspectionResult(result);
      }
    }
  } catch (err) {
    // Show exact real error without falling back silently to mock results
    showNotification(err.message || "An error occurred during inspection.", true);
    elements.stateLoading.classList.add("is-hidden");
    elements.stateEmpty.classList.remove("is-hidden");
  } finally {
    state.isInspecting = false;
    elements.btnRunInspection.disabled = !state.selectedFile;
    elements.btnRemoveImage.disabled = false;
    elements.imageFileInput.disabled = false;
    elements.dropzone.setAttribute('aria-disabled', 'false');
    elements.categoryRadios.forEach((r) => (r.disabled = false));
    elements.btnModeLive.disabled = false;
    elements.btnModeDemo.disabled = false;
    [elements.btnExampleAnomaly, elements.btnExampleGood, elements.btnExampleRetake].forEach((b) => (b.disabled = false));
    document.getElementById('qualityModeSelect').disabled = false;
    document.getElementById('sessionAccessKey').disabled = false;
    document.getElementById('applyAccessKey').disabled = false;
    elements.btnLabel.textContent = "Run Inspection";
    elements.btnIcon.textContent = "▶";
  }
}

/**
 * Initialize event listeners and startup health check.
 */
function init() {
  document.getElementById('qualityModeSelect').addEventListener('change', () => {
    if (!state.isInspecting) clearInspectionResult();
  });
  document.getElementById('applyAccessKey').addEventListener('click', async () => {
    if (state.isInspecting) return;
    api.setAccessKey(document.getElementById('sessionAccessKey').value.trim());
    document.getElementById('sessionAccessKey').value = '';
    clearInspectionResult();
    const models = await api.getBackendModels();
    showNotification(models ? 'Connection accepted for this tab.' : 'Access not accepted. Check the session key and backend.', !models);
  });
  // 1. Mode selector buttons
  elements.btnModeLive.addEventListener("click", () => setExecutionMode("live"));
  elements.btnModeDemo.addEventListener("click", () => setExecutionMode("demo"));

  // 2. Category selector change
  elements.categoryRadios.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      setCategory(e.target.value);
    });
  });

  // 3. Dropzone click & keyboard activation
  elements.dropzone.addEventListener("click", () => {
    elements.imageFileInput.click();
  });

  elements.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      elements.imageFileInput.click();
    }
  });

  // 4. Native file input change
  elements.imageFileInput.addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) {
      handleFileSelection(file);
    }
  });

  // 5. Drag & Drop events
  const dragEvents = ["dragenter", "dragover"];
  dragEvents.forEach((eventName) => {
    elements.dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      elements.dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    elements.dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      elements.dropzone.classList.remove("is-dragover");
    });
  });

  elements.dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt && dt.files;
    if (files && files.length > 0) {
      handleFileSelection(files[0]);
    }
  });

  // 6. Remove/Change image button
  elements.btnRemoveImage.addEventListener("click", () => {
    removeSelectedFile();
  });

  // 7. Run Inspection CTA
  elements.btnRunInspection.addEventListener("click", () => {
    runInspection();
  });

  // 8. Notification banner dismiss
  elements.notificationCloseBtn.addEventListener("click", () => {
    hideNotification();
  });

  // 9. Viewer tabs
  elements.tabOverlay.addEventListener("click", () => updateViewMode("overlay"));
  elements.tabProcessed.addEventListener("click", () => updateViewMode("processed"));
  elements.tabHeatmap.addEventListener("click", () => updateViewMode("heatmap"));
  elements.tabOriginal.addEventListener("click", () => updateViewMode("original"));

  // 10. Opacity Slider
  elements.opacitySlider.addEventListener("input", (e) => {
    const val = parseInt(e.target.value, 10);
    state.heatmapOpacity = val / 100;
    elements.opacityLabel.textContent = `${val}%`;
    if (state.viewMode === "overlay") {
      elements.viewerHeatmapImg.style.opacity = state.heatmapOpacity.toString();
    }
  });

  // 11. Demo walkthrough examples
  elements.btnExampleAnomaly.addEventListener("click", () => showDemoExample("anomaly"));
  elements.btnExampleGood.addEventListener("click", () => showDemoExample("good"));
  elements.btnExampleRetake.addEventListener("click", () => showDemoExample("retake"));

  // Set initial category and default to Live Mode. `?mode=demo` opens the
  // simulated walkthrough directly (for sharing a demo without a backend).
  setCategory("bottle");
  const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  setExecutionMode(params && params.get("mode") === "demo" ? "demo" : "live");
}

// Start application when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
