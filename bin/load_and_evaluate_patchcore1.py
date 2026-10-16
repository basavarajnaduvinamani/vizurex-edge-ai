'''
================================================================================
MULTI-VIEW PATCHCORE INFERENCE — load_and_evaluate_patchcore.py
================================================================================

OVERVIEW
--------
Loads pre-trained PatchCore models for three camera views (top, bottom, side)
and runs full anomaly detection on new test images. Each view runs its own
three-judge decision (PatchCore + Geometric + Defect Bank), and the results
are fused into one final GOOD/ANOMALY decision per physical part.

A part is flagged ANOMALY if ANY view from ANY judge raises an alarm.
A part is GOOD only if ALL views from ALL judges pass.

This script is inference-only — no training happens here. All thresholds,
calibrations, and memory banks were computed during training and are loaded
from disk.

──────────────────────────────────────────────────────────────────────────────
INPUTS
──────────────────────────────────────────────────────────────────────────────
Command-line arguments:
    --top_model     : path to saved Top view model folder
    --bottom_model  : path to saved Bottom view model folder
    --side_model    : path to saved Side view model folder
    --test_folder   : parent folder containing top/, bottom/, side/ subfolders
    --gpu           : GPU index (default 0)
    --already_masked: skip rembg if images already have black background
    --top/bottom/side_threshold : optional override of saved PC thresholds
    --output_csv    : where to save results (default: multiview_results.csv)

Test folder structure (two accepted formats):
    WITH ground truth labels:           WITHOUT labels (production):
        test_folder/                        test_folder/
            top/                                top/
                good/part_001.png                   part_001.png
                anomaly/part_002.png                part_002.png
            bottom/                             bottom/
                good/part_001.png                   part_001.png
            side/                               side/
                good/part_001.png                   part_001.png

Each model folder (saved by run_patchcore.py) must contain:
    patchcore_params.pkl      : PatchCore memory bank + backbone weights
    score_stats.npy           : PC threshold (p85 of good val scores)
    geo_calibration.npy       : geo mean, std, threshold (optional)
    defect_bank.pkl           : known defect embeddings + threshold (optional)

──────────────────────────────────────────────────────────────────────────────
PROCESSING PIPELINE
──────────────────────────────────────────────────────────────────────────────

STAGE 1 — Load Models (load_model × 3)
    For each view (top, bottom, side):
        ├─ Auto-detect single vs ensemble backbone from saved filenames
        ├─ Load PatchCore memory bank + backbone weights
        ├─ Load PC threshold from score_stats.npy
        ├─ Load geo calibration (good_mean, good_std, geo_threshold)
        │   from geo_calibration.npy  [optional — disabled if missing]
        └─ Load defect bank embeddings + db_threshold
            from defect_bank.pkl      [optional — disabled if missing]

STAGE 2 — Match Images (find_images + match_images)
    find_images():
        Scans each view folder, collects (image_path, gt_label) pairs.
        gt_label = 1 (anomaly subfolder), 0 (good subfolder), None (flat folder)

    match_images():
        Matches images across all three views by FILENAME.
        Same filename = same physical part photographed from three angles.
        Missing images for a view → that view scores None, others still run.
        Returns: [(fname, top_path, bottom_path, side_path, gt), ...]

STAGE 3 — Score Each Part (score_one × 3 per part)
    For each view of each part:

        Preprocessing:
            raw image
                ├─ mask_background()      rembg removes background → black bg
                ├─ auto_crop_part()       crop to part bounding box + 8% pad
                ├─ normalise_brightness() scale to TARGET_PART_MEAN = 110
                └─ Resize(448) → ToTensor → ImageNet normalize → tensor (1,3,448,448)

        Judge 1 — PatchCore:
            backbone forward pass → patch features → L2 distance to memory bank
            pc_score = average across ensemble backbones
            pc_pred  = ANOMALY if pc_score >= pc_threshold else GOOD

        Judge 2 — Geometric Checker (runs on every image):
            radial profile → mean z-score of outer ring (bins 160–187)
            geo_pred = ANOMALY if geo_score > geo_threshold else GOOD
            [skipped if geo_calibration.npy was not saved]

        Judge 3 — Defect Bank (ambiguous zone only):
            only consulted if:
                0.05 ≤ pc_score < pc_threshold  (uncertain zone)
                AND pc_pred == GOOD
                AND geo_pred == GOOD
            min L2 distance to known defect embeddings
            db_pred = ANOMALY if db_dist < db_threshold else GOOD
            [skipped if defect_bank.pkl was not saved]

        View-level decision:
            ANY of (pc_pred, geo_pred, db_pred) == ANOMALY → view_pred = ANOMALY
            ALL == GOOD                                     → view_pred = GOOD

STAGE 4 — Multi-View Fusion
    view_preds = [top_pred, bottom_pred, side_pred]
    final_pred = ANOMALY if ANY view_pred == ANOMALY else GOOD

    triggered  = list of which views flagged it  e.g. ["TOP", "SIDE"]
    needs_review = final_pred == GOOD but pc_score in ambiguous zone
                   (advisory only — prediction stays GOOD)

STAGE 5 — Metrics + Output (if ground truth available)
    Per-view:  F1, Precision, Recall, TP, FP, TN, FN
    Combined:  same metrics on final fused prediction
    Saved to:  --output_csv (one row per part, all scores and predictions)

──────────────────────────────────────────────────────────────────────────────
OUTPUTS
──────────────────────────────────────────────────────────────────────────────
Console:
    Per-part table showing GT / TOP / BOTTOM / SIDE / FINAL with tags:
        [by: TOP+SIDE]  — which view(s) triggered the ANOMALY call
        [review?]       — GOOD prediction but score in uncertain zone
        <<WRONG         — prediction does not match ground truth

CSV (one row per part):
    Image, GT, Final_Pred, Correct, Triggered_By, Needs_Review
    Top_Pred,    Top_PC_Score,    Top_Geo_Score,    Top_DB_Dist
    Bottom_Pred, Bottom_PC_Score, Bottom_Geo_Score, Bottom_DB_Dist
    Side_Pred,   Side_PC_Score,   Side_Geo_Score,   Side_DB_Dist

Metrics table (if GT available):
    Per-view and combined F1, Precision, Recall, TP, FP, TN, FN

──────────────────────────────────────────────────────────────────────────────
FUNCTION ROLES
──────────────────────────────────────────────────────────────────────────────
    get_rembg_session()     Load rembg model once, reuse for all images
    mask_background()       Remove background using rembg → black bg
    auto_crop_part()        Crop to part bounding box + 8% padding
    normalise_brightness()  Scale part brightness to TARGET_PART_MEAN=110
    preprocess()            Full pipeline from file path → backbone tensor
    preprocess_pil()        Same but from already-loaded PIL image
    geo_score_image()       Compute geo z-score for one PIL image
    _extract_embedding()    Run backbone → global avg pool → 1D vector
    db_score_image()        Min L2 distance to defect bank embeddings
    load_model()            Load all saved components for one view
    score_one()             Full three-judge pipeline for one image
    find_images()           Collect (path, gt) pairs from a view folder
    match_images()          Match top/bottom/side images by filename
    main()                  Orchestrate everything end-to-end

──────────────────────────────────────────────────────────────────────────────
KEY DESIGN DECISIONS
──────────────────────────────────────────────────────────────────────────────
    OR fusion across views:
        Any view catching a defect is enough → maximises recall.
        A defect visible from one angle is caught even if others look normal.

    Singleton rembg session:
        Heavy model loaded once → reused for every image → avoids reload cost.

    Preprocessing must match training exactly:
        BG_THRESHOLD, CROP_PADDING_FRAC, TARGET_PART_MEAN, IMAGE_SIZE,
        IMAGENET_MEAN/STD must be identical to selfds.py and run_patchcore.py.
        Any mismatch → backbone sees different images than memory bank → 
        scores become unreliable.

    Defect bank only in ambiguous zone:
        Too expensive to run on every image. Only consulted when PC score
        is uncertain (0.05 ≤ score < pc_threshold) and both other judges passed.

    Missing view graceful handling:
        If an image is missing for one view, that view returns None.
        The other two views still score normally — part is not skipped.
================================================================================
'''

import contextlib
import gc
import io
import logging
import os
import csv
import pickle
import argparse

import numpy as np
import torch
import PIL.Image
from torchvision import transforms
from tqdm import tqdm

import patchcore.common
import patchcore.metrics
import patchcore.patchcore

import warnings
warnings.filterwarnings("ignore")

LOGGER = logging.getLogger(__name__)

# ── Preprocessing constants — must match selfds.py exactly ──────────────────
IMAGENET_MEAN     = [0.485, 0.456, 0.406]
IMAGENET_STD      = [0.229, 0.224, 0.225]
BG_THRESHOLD      = 15
CROP_PADDING_FRAC = 0.08
TARGET_PART_MEAN  = 110.0
IMAGE_SIZE        = 448
RECHECK_LOW       = 0.05

# Geo checker constants — must match run_patchcore1.py
GEO_PROFILE_BINS  = 200
GEO_N_ANGLES      = 360
GEO_SCORE_BIN_START = 160
GEO_SCORE_BIN_END   = 187
# ────────────────────────────────────────────────────────────────────────────

# ── rembg session ────────────────────────────────────────────────────────────
# _REMBG_SESSION = None

# def get_rembg_session():
#     global _REMBG_SESSION
#     if _REMBG_SESSION is None:
#         from rembg import new_session
#         LOGGER.info("Loading rembg model (first call only)...")
#         _REMBG_SESSION = new_session("isnet-general-use")
#     return _REMBG_SESSION


# ── Preprocessing ─────────────────────────────────────────────────────────────

# def mask_background(pil_image):
#     '''
#     Background masking

#     Making the background to transparent
#     '''
#     from rembg import remove
#     import io as _io
#     buf = _io.BytesIO()
#     pil_image.save(buf, format="PNG")
#     out  = remove(buf.getvalue(), session=get_rembg_session())
#     bg = PIL.Image.open(_io.BytesIO(out)).convert("RGBA")
#     # bg   = PIL.Image.new("RGB", rgba.size, (0, 0, 0))
#     # bg.paste(rgba, mask=rgba.split()[3])
#     return bg

def mask_background(pil_image):
    '''
    Background masking using rembg default model (u2net).
    Matches background_removal.py which also uses the default session.
    Returns RGBA image with transparent background.
    '''
    from rembg import remove
    import io as _io
    buf = _io.BytesIO()
    pil_image.save(buf, format="PNG")
    out  = remove(buf.getvalue())           # default session = u2net
    bg = PIL.Image.open(_io.BytesIO(out)).convert("RGBA")
    return bg

def auto_crop_part(pil_image):
    """
    Crop to bounding box of non-background pixels. Preserves original mode (RGBA ok).

    Crop the background so that maximum focus is on the component.
    """
    arr  = np.array(pil_image.convert("RGB"))   # RGB copy for mask only
    gray = arr.mean(axis=2)
    mask = gray > BG_THRESHOLD
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any():
        return pil_image
    rmin = int(np.where(rows)[0][0]);  rmax = int(np.where(rows)[0][-1])
    cmin = int(np.where(cols)[0][0]);  cmax = int(np.where(cols)[0][-1])
    h, w = arr.shape[:2]
    pad_r = int((rmax - rmin) * CROP_PADDING_FRAC)
    pad_c = int((cmax - cmin) * CROP_PADDING_FRAC)
    # Crop the *original* image (not the RGB copy) so RGBA alpha is preserved
    return pil_image.crop((
        max(0, cmin - pad_c), max(0, rmin - pad_r),
        min(w, cmax + pad_c), min(h, rmax + pad_r)
    ))


def normalise_brightness(pil_image):
    """Normalise brightness on RGB channels only; preserves alpha channel if present."""
    has_alpha = pil_image.mode == "RGBA"
    
    if has_alpha:
        rgb  = pil_image.convert("RGB")
        alpha = pil_image.split()[3]           # keep alpha aside
    else:
        rgb  = pil_image
        alpha = None

    arr  = np.array(rgb, dtype=np.float32)
    gray = arr.mean(axis=2)
    mask = gray > BG_THRESHOLD
    if not mask.any():
        return pil_image
    current = float(arr[mask].mean())
    if current < 1.0:
        return pil_image

    arr        = arr * (TARGET_PART_MEAN / current)
    arr[~mask] = 0
    rgb_out = PIL.Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if has_alpha:
        # Re-attach the original alpha channel
        rgb_out.putalpha(alpha)

    return rgb_out

def save_stages(pil_raw, image_path, test_folder, already_masked=False):
    """
    Save intermediate preprocessing stages for inspection.
    Creates three subfolders next to test_folder:
        debug_masked/        — after rembg background removal
        debug_cropped/       — after auto_crop_part
        debug_normalised/    — after normalise_brightness
    Mirrors the view subfolder structure (Top/Bottom/Side).
    """
    # Build relative path from test_folder so folder structure is preserved
    # e.g. test/Top/WIN_001.jpg → debug_masked/Top/WIN_001.png
    rel      = os.path.relpath(image_path, test_folder)          # e.g. Top/WIN_001.jpg
    stem     = os.path.splitext(os.path.basename(rel))[0]        # e.g. WIN_001
    view_dir = os.path.dirname(rel)                               # e.g. Top

    base_dir = os.path.join(os.path.dirname(test_folder), "debug_stages")

    masked_dir     = os.path.join(base_dir, "debug_masked",     view_dir)
    cropped_dir    = os.path.join(base_dir, "debug_cropped",    view_dir)
    normalised_dir = os.path.join(base_dir, "debug_normalised", view_dir)

    for d in (masked_dir, cropped_dir, normalised_dir):
        os.makedirs(d, exist_ok=True)

    # Stage 1 — after masking
    if already_masked:
        stage1 = pil_raw.convert("RGB")
    else:
        stage1 = mask_background(pil_raw.copy())   # returns RGB with black bg
    stage1.save(os.path.join(masked_dir, stem + ".png"))

    # Stage 2 — after auto_crop
    stage2 = auto_crop_part(stage1)
    stage2.save(os.path.join(cropped_dir, stem + ".png"))

    # Stage 3 — after normalise_brightness
    stage3 = normalise_brightness(stage2)
    stage3.save(os.path.join(normalised_dir, stem + ".png"))

# Transform must exactly match selfds.py training transform: Resize(512, 512)
# Previously used int(IMAGE_SIZE*1.1) = 492 — mismatch caused score inflation on good parts
_transform = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.Lambda(lambda img: img.convert("RGB")),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])


def preprocess(image_path, already_masked=False):
    img = PIL.Image.open(image_path).convert("RGB")
    if not already_masked:
        img = mask_background(img)
    img = auto_crop_part(img)
    img = normalise_brightness(img)
    return _transform(img).unsqueeze(0)   # (1, 3, H, W)

# =============================================================
# The above written `preprocess` function is not getting used
# The below written `preprocess_pil` function is in use
# =============================================================

def preprocess_pil(pil_image):
    """Preprocess an already-loaded PIL image (already masked)."""
    '''
    Calling the functions:
    1. mask_background (already happening after loading image)
    2. auto_crop_part
    3. normalise_brightness
    and transforming all the images
    '''
    pil_image = auto_crop_part(pil_image)
    pil_image = normalise_brightness(pil_image)
    return _transform(pil_image).unsqueeze(0)


# ── Geo checker ───────────────────────────────────────────────────────────────

def _geo_gray(pil_image):
    return np.array(pil_image.convert("RGB"), dtype=np.float32).mean(axis=2)


def _geo_centre_radius(gray):
    mask = gray > BG_THRESHOLD
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        h, w = gray.shape
        return h//2, w//2, min(h,w)//2
    cy = (rows[0] + rows[-1]) / 2.0
    cx = (cols[0] + cols[-1]) / 2.0
    R  = min(rows[-1]-rows[0], cols[-1]-cols[0]) / 2.0
    return cy, cx, R


def _geo_radial_profile(gray, cy, cx, R):
    profile = np.zeros(GEO_PROFILE_BINS, dtype=np.float64)
    counts  = np.zeros(GEO_PROFILE_BINS, dtype=np.float64)
    h, w    = gray.shape
    for angle in np.linspace(0, 2*np.pi, GEO_N_ANGLES, endpoint=False):
        ca, sa = np.cos(angle), np.sin(angle)
        for b in range(GEO_PROFILE_BINS):
            r_px = (b / GEO_PROFILE_BINS) * R
            yi = int(round(cy + r_px * sa))
            xi = int(round(cx + r_px * ca))
            if 0 <= yi < h and 0 <= xi < w:
                profile[b] += gray[yi, xi]
                counts[b]  += 1
    profile[counts > 0] /= counts[counts > 0]
    return profile


def geo_score_image(pil_image, geo_mean, geo_std):
    """Compute geo anomaly score for a preprocessed PIL image."""
    # pil_image = auto_crop_part(pil_image)             # modified
    # pil_image = normalise_brightness(pil_image)       # modified
    gray      = _geo_gray(pil_image)
    cy, cx, R = _geo_centre_radius(gray)
    if R < 20:
        return None
    profile   = _geo_radial_profile(gray, cy, cx, R)
    seg       = profile[GEO_SCORE_BIN_START:GEO_SCORE_BIN_END]
    mean_seg  = geo_mean[GEO_SCORE_BIN_START:GEO_SCORE_BIN_END]
    std_seg   = geo_std[GEO_SCORE_BIN_START:GEO_SCORE_BIN_END]
    z         = np.abs(seg - mean_seg) / (std_seg + 1e-6)
    return float(z.mean())


# ── Defect bank ───────────────────────────────────────────────────────────────

def _extract_embedding(pil_image, pc_list, device):
    """Extract backbone embedding for one PIL image."""
    # pil = auto_crop_part(pil_image)                       # modified
    # pil = normalise_brightness(pil)                       # modified
    tensor = _transform(pil_image).unsqueeze(0).to(device)  # modified
    parts = []
    for PC in pc_list:
        try:
            with torch.no_grad():
                features = PC.forward_modules["feature_aggregator"](tensor)
                agg = []
                for feat in features.values():
                    agg.append(feat.mean(dim=[2,3]).squeeze(0).cpu().numpy())
                parts.append(np.concatenate(agg))
        except Exception:
            return None
    return np.concatenate(parts) if parts else None


def db_score_image(pil_image, db_matrix, pc_list, device):
    """Return min distance to defect bank. None if bank unavailable."""
    emb = _extract_embedding(pil_image, pc_list, device)
    if emb is None:
        return None
    diffs = db_matrix - emb
    dists = np.linalg.norm(diffs, axis=1)
    return float(dists.min())


# ── Model loading ─────────────────────────────────────────────────────────────

def load_model(model_path, device):
    """
    Load PatchCore + geo calibration + defect bank for one view.
    Automatically detects ensemble prepend (Ensemble-1-2_, etc).
    Returns dict with all components.
    """
    LOGGER.info("Loading model: {}".format(model_path))

    # Detect prepend prefix from saved files
    # Ensemble saves as "Ensemble-1-2_patchcore_params.pkl" etc.
    # Single model saves as "patchcore_params.pkl"
    files = os.listdir(model_path) if os.path.isdir(model_path) else []
    prepend = ""
    for f in files:
        if f.endswith("patchcore_params.pkl") and f != "patchcore_params.pkl":
            # e.g. "Ensemble-1-2_patchcore_params.pkl" -> prepend = "Ensemble-1-2_"
            prepend = f.replace("patchcore_params.pkl", "")
            break

    # For ensemble we need to load all backbones
    # Detect how many ensemble members exist
    ensemble_prepends = []
    for f in sorted(files):
        if f.endswith("patchcore_params.pkl"):
            ensemble_prepends.append(f.replace("patchcore_params.pkl", ""))

    if not ensemble_prepends:
        ensemble_prepends = [""]  # single model, no prepend

    LOGGER.info("  Found {} backbone(s): {}".format(
        len(ensemble_prepends), ensemble_prepends))

    # Load all PatchCore backbones
    pc_list = []
    for prep in ensemble_prepends:
        nn_method = patchcore.common.FaissNN(False, num_workers=8)
        pc = patchcore.patchcore.PatchCore(device)
        pc.load_from_path(load_path=model_path, device=device,
                          nn_method=nn_method, prepend=prep)
        pc_list.append(pc)

    # Score threshold
    stats_path = os.path.join(model_path, "score_stats.npy")
    if os.path.exists(stats_path):
        stats     = np.load(stats_path, allow_pickle=True).item()
        threshold = float(stats.get("pc_threshold") or stats.get("threshold", 0.5))
        LOGGER.info("  PC threshold: {:.4f}".format(threshold))
    else:
        threshold = 0.5
        LOGGER.warning("  score_stats.npy not found, using default threshold 0.5")

    # Geo calibration — DISABLED to reduce FP rate
    # Geo checker fires on good parts with slight orientation variation.
    # PatchCore handles texture/shape anomalies; geo adds more FPs than it saves.
    geo_mean = geo_std = geo_threshold = None
    LOGGER.info("  Geo checker disabled (suppressed to reduce FP rate)")

    # Defect bank
    db_matrix = db_threshold = None
    db_path   = os.path.join(model_path, "defect_bank.pkl")
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            db = pickle.load(f)
        db_matrix    = db["embeddings"]
        db_threshold = float(db["threshold"])
        LOGGER.info("  Defect bank: n={} threshold={:.2f}".format(
            len(db_matrix), db_threshold))
    else:
        LOGGER.info("  No defect_bank.pkl — defect bank disabled for this view")

    return {
        "pc_list":       pc_list,       # list of all backbones
        "pc":            pc_list[0],    # primary backbone (for score)
        "threshold":     threshold,
        "geo_mean":      geo_mean,
        "geo_std":       geo_std,
        "geo_threshold": geo_threshold,
        "db_matrix":     db_matrix,
        "db_threshold":  db_threshold,
    }


# ── Score one image against one model ─────────────────────────────────────────

def score_one(image_path, model, device, already_masked=False, test_folder=None,):
    """
    Run full pipeline (PC + geo + defect bank) for one image against one view model.
    Handles ensemble: averages scores across all backbones.
    """
    pil_raw = PIL.Image.open(image_path).convert("RGB")
    if not already_masked:
        pil = mask_background(pil_raw)
    else:
        pil = pil_raw
    pil = pil.convert("RGB")   # rembg returns RGBA — force back to RGB before preprocessing

        # Save intermediate stages for inspection
    save_stages(pil_raw, image_path, test_folder, already_masked)

    # PatchCore score — average across ensemble backbones
    tensor = preprocess_pil(pil).to(device)
    pc_scores = []
    for pc in model["pc_list"]:
        with torch.no_grad():
            score_raw, _ = pc.predict(tensor)
        pc_scores.append(float(score_raw[0]))
    pc_score = float(np.mean(pc_scores))
    pc_pred  = "ANOMALY" if pc_score >= model["threshold"] else "GOOD"

    # Geo score
    geo_score = geo_pred = None
    if model["geo_mean"] is not None:
        gs = geo_score_image(pil, model["geo_mean"], model["geo_std"])
        if gs is not None:
            geo_score = gs
            geo_pred  = "ANOMALY" if gs > model["geo_threshold"] else "GOOD"

    # Defect bank (ambiguous zone only)
    db_dist = db_pred = None
    in_ambiguous = (pc_score >= RECHECK_LOW and pc_score < model["threshold"])
    if (model["db_matrix"] is not None and in_ambiguous
            and pc_pred == "GOOD"
            and (geo_pred is None or geo_pred == "GOOD")):
        dd = db_score_image(pil, model["db_matrix"], model["pc_list"], device)
        if dd is not None:
            db_dist = dd
            db_pred = "ANOMALY" if dd < model["db_threshold"] else "GOOD"

    # View-level prediction
    view_pred = "ANOMALY" if (
        pc_pred == "ANOMALY"
        or geo_pred == "ANOMALY"
        or db_pred == "ANOMALY"
    ) else "GOOD"

    # needs_review = (view_pred == "GOOD" and in_ambiguous
    #                 and (geo_pred is None or geo_pred == "GOOD")
    #                 and (db_pred is None or db_pred == "GOOD"))
    needs_review = False

    return {
        "pc_score":      round(pc_score, 4),
        "pc_pred":       pc_pred,
        "geo_score":     round(geo_score, 3) if geo_score is not None else "",
        "geo_pred":      geo_pred or "N/A",
        "db_dist":       round(db_dist, 2)   if db_dist   is not None else "",
        "db_pred":       db_pred or "N/A",
        "view_pred":     view_pred,
        "needs_review":  needs_review,
    }


# ── Image discovery ───────────────────────────────────────────────────────────

def find_images(folder):
    """
    Returns list of (path, gt_label) where gt_label = 1/0/None.
    Accepts flat folder or good/anomaly subfolders.
    """
    exts  = ('.png', '.jpg', '.jpeg')
    items = []
    good_dir    = os.path.join(folder, "good")
    anomaly_dir = os.path.join(folder, "anomaly")
    if os.path.isdir(good_dir) or os.path.isdir(anomaly_dir):
        if os.path.isdir(good_dir):
            for f in sorted(os.listdir(good_dir)):
                if f.lower().endswith(exts):
                    items.append((os.path.join(good_dir, f), 0))
        if os.path.isdir(anomaly_dir):
            for f in sorted(os.listdir(anomaly_dir)):
                if f.lower().endswith(exts):
                    items.append((os.path.join(anomaly_dir, f), 1))
    else:
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith(exts):
                items.append((os.path.join(folder, f), None))
    return items


def match_images(top_items, bottom_items, side_items):
    """
    Match images across views by filename (stripping path).
    Returns list of (fname, top_path, bottom_path, side_path, gt)
    where any path can be None if image is missing for that view.
    """
    def to_dict(items):
        return {os.path.basename(p): (p, gt) for p, gt in items}

    top_d    = to_dict(top_items)
    bottom_d = to_dict(bottom_items)
    side_d   = to_dict(side_items)

    # Union of all filenames
    all_fnames = sorted(set(top_d) | set(bottom_d) | set(side_d))
    matched = []
    for fname in all_fnames:
        top_p,    top_gt    = top_d.get(fname,    (None, None))
        bottom_p, bottom_gt = bottom_d.get(fname, (None, None))
        side_p,   side_gt   = side_d.get(fname,   (None, None))
        # GT from whichever view has it
        gt = top_gt if top_gt is not None else (
             bottom_gt if bottom_gt is not None else side_gt)
        matched.append((fname, top_p, bottom_p, side_p, gt))
    return matched


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-view PatchCore inference — 3 views, 1 decision per part."
    )
    parser.add_argument("--top_model",    required=True,
        help="Path to saved Top view model folder")
    parser.add_argument("--bottom_model", required=True,
        help="Path to saved Bottom view model folder")
    parser.add_argument("--side_model",   required=True,
        help="Path to saved Side view model folder")
    parser.add_argument("--test_folder",  required=True,
        help="Parent folder containing top/, bottom/, side/ subfolders")
    parser.add_argument("--gpu",          type=int, default=0)
    parser.add_argument("--already_masked", action="store_true",
        help="Skip rembg — images already have black background")
    parser.add_argument("--top_threshold",    type=float, default=None)
    parser.add_argument("--bottom_threshold", type=float, default=None)
    parser.add_argument("--side_threshold",   type=float, default=None)
    parser.add_argument("--output_csv", default="multiview_results.csv",
        help="Where to save the results CSV")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    device = torch.device(
        "cuda:{}".format(args.gpu) if torch.cuda.is_available() else "cpu"
    )
    print("\nDevice: {}".format(device))

    # ── Load all three models ─────────────────────────────────────────────────
    print("\n" + "="*60)
    print("LOADING MODELS")
    print("="*60)
    top_model    = load_model(args.top_model,    device)
    bottom_model = load_model(args.bottom_model, device)
    side_model   = load_model(args.side_model,   device)

    # Apply threshold overrides
    if args.top_threshold:
        top_model["threshold"]    = args.top_threshold
        print("Top threshold overridden: {:.4f}".format(args.top_threshold))
    if args.bottom_threshold:
        bottom_model["threshold"] = args.bottom_threshold
        print("Bottom threshold overridden: {:.4f}".format(args.bottom_threshold))
    if args.side_threshold:
        side_model["threshold"]   = args.side_threshold
        print("Side threshold overridden: {:.4f}".format(args.side_threshold))

    # ── Find images ───────────────────────────────────────────────────────────
    top_dir    = os.path.join(args.test_folder, "Top")
    bottom_dir = os.path.join(args.test_folder, "Bottom")
    side_dir   = os.path.join(args.test_folder, "Side")

    top_items    = find_images(top_dir)    if os.path.isdir(top_dir)    else []
    bottom_items = find_images(bottom_dir) if os.path.isdir(bottom_dir) else []
    side_items   = find_images(side_dir)   if os.path.isdir(side_dir)   else []

    print("\nImages found:  top={} bottom={} side={}".format(
        len(top_items), len(bottom_items), len(side_items)))

    matched = match_images(top_items, bottom_items, side_items)
    print("Matched parts: {}".format(len(matched)))

    has_gt = any(gt is not None for _, _, _, _, gt in matched)

    # ── Score each part ───────────────────────────────────────────────────────
    print("\n" + "="*100)
    print("PER-PART PREDICTIONS  (FINAL = ANOMALY if ANY view says ANOMALY)")
    print("="*100)
    # print("  {:<45} {:>7} {:>10} {:>10} {:>10} {:>9}".format(
    #     "Image", "GT", "TOP", "BOTTOM", "SIDE", "FINAL"))
    print("  {:<45} {:>10} {:>10} {:>10} {:>9}".format(
    "Image", "TOP", "BOTTOM", "SIDE", "FINAL"))
    print("  " + "-"*96)

    rows = []
    ctx  = torch.cuda.device(args.gpu) if torch.cuda.is_available() else contextlib.suppress()

    with ctx:
        for fname, top_p, bottom_p, side_p, gt in tqdm(matched, desc="Scoring"):
            gt_str = "ANOMALY" if gt == 1 else ("GOOD" if gt == 0 else "-")

            # Score each view (skip if image missing for that view)
            # top_r = score_one(top_p, top_model, device, args.already_masked) \
            #         if top_p else None
            # bottom_r = score_one(bottom_p, bottom_model, device, args.already_masked) \
            #         if bottom_p else None
            # side_r = score_one(side_p, side_model, device, args.already_masked) \
            #         if side_p else None
            top_r = score_one(top_p, top_model, device, args.already_masked, args.test_folder) \
                if top_p else None
            bottom_r = score_one(bottom_p, bottom_model, device, args.already_masked, args.test_folder) \
                if bottom_p else None
            side_r = score_one(side_p, side_model, device, args.already_masked, args.test_folder) \
                if side_p else None

            # ── FUSION: ANY view says ANOMALY → part is ANOMALY ──────────────
            view_preds = [r["view_pred"] for r in [top_r, bottom_r, side_r] if r]
            final_pred = "ANOMALY" if "ANOMALY" in view_preds else "GOOD"

            # Which view(s) triggered?
            triggered = []
            if top_r    and top_r["view_pred"]    == "ANOMALY": triggered.append("TOP")
            if bottom_r and bottom_r["view_pred"] == "ANOMALY": triggered.append("BOTTOM")
            if side_r   and side_r["view_pred"]   == "ANOMALY": triggered.append("SIDE")

            # needs_review = (
            #     final_pred == "GOOD" and
            #     any(r["needs_review"] for r in [top_r, bottom_r, side_r] if r)
            # )
            needs_review = False

            correct = ("CORRECT" if final_pred == gt_str else "WRONG") \
                      if gt is not None else "-"

            tag = ""
            if triggered:   tag += " [by: {}]".format("+".join(triggered))
            # if needs_review: tag += " [review?]"
            if correct == "WRONG": tag += " <<WRONG"

            # print("  {:<45} {:>7} {:>10} {:>10} {:>10} {:>9}{}".format(
            #     fname[:44], gt_str,
            #     (top_r["view_pred"]    if top_r    else "N/A"),
            #     (bottom_r["view_pred"] if bottom_r else "N/A"),
            #     (side_r["view_pred"]   if side_r   else "N/A"),
            #     final_pred, tag
            # ))
            print("  {:<45} {:>10} {:>10} {:>10} {:>9}{}".format(
                fname[:44],
                (top_r["view_pred"]    if top_r    else "N/A"),
                (bottom_r["view_pred"] if bottom_r else "N/A"),
                (side_r["view_pred"]   if side_r   else "N/A"),
                final_pred, tag
            ))

            rows.append({
                "Image":           fname,
                "GT":              gt_str,
                "Final_Pred":      final_pred,
                "Correct":         correct,
                "Triggered_By":    "+".join(triggered) if triggered else "",
                # "Needs_Review":    "Yes" if needs_review else "No",
                # Top view
                "Top_Pred":        top_r["view_pred"]  if top_r else "",
                "Top_PC_Score":    top_r["pc_score"]   if top_r else "",
                "Top_Geo_Score":   top_r["geo_score"]  if top_r else "",
                "Top_DB_Dist":     top_r["db_dist"]    if top_r else "",
                # Bottom view
                "Bottom_Pred":     bottom_r["view_pred"] if bottom_r else "",
                "Bottom_PC_Score": bottom_r["pc_score"]  if bottom_r else "",
                "Bottom_Geo_Score":bottom_r["geo_score"] if bottom_r else "",
                "Bottom_DB_Dist":  bottom_r["db_dist"]   if bottom_r else "",
                # Side view
                "Side_Pred":       side_r["view_pred"]  if side_r else "",
                "Side_PC_Score":   side_r["pc_score"]   if side_r else "",
                "Side_Geo_Score":  side_r["geo_score"]  if side_r else "",
                "Side_DB_Dist":    side_r["db_dist"]    if side_r else "",
            })

    all_good = all(r["Final_Pred"] == "GOOD" for r in rows)
    overall_decision = "GOOD" if all_good else "DEFECTIVE"

    print("\n" + "="*60)
    print("FINAL OVERALL DECISION: {}".format(overall_decision))
    print("="*60)

    # ── Metrics ───────────────────────────────────────────────────────────────
    if has_gt:
        tp = sum(1 for r in rows if r["Final_Pred"]=="ANOMALY" and r["GT"]=="ANOMALY")
        fp = sum(1 for r in rows if r["Final_Pred"]=="ANOMALY" and r["GT"]=="GOOD")
        tn = sum(1 for r in rows if r["Final_Pred"]=="GOOD"    and r["GT"]=="GOOD")
        fn = sum(1 for r in rows if r["Final_Pred"]=="GOOD"    and r["GT"]=="ANOMALY")
        prec = tp / max(1, tp + fp)
        rec  = tp / max(1, tp + fn)
        f1   = 2 * prec * rec / max(1e-8, prec + rec)

        # Per-view metrics
        def view_metrics(pred_key):
            vtp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="ANOMALY")
            vfp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="GOOD")
            vtn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="GOOD")
            vfn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="ANOMALY")
            vp  = vtp / max(1, vtp+vfp)
            vr  = vtp / max(1, vtp+vfn)
            return vtp, vfp, vtn, vfn, vp, vr, 2*vp*vr/max(1e-8,vp+vr)

        print("\n" + "="*70)
        print("EVALUATION SUMMARY")
        print("="*70)
        print("  {:<20}  {:>6}  {:>6}  {:>6}  {:>4}  {:>4}  {:>4}  {:>4}".format(
            "View", "F1", "Prec", "Rec", "TP", "FP", "TN", "FN"))
        print("  " + "-"*66)
        for label, key in [("Top", "Top_Pred"), ("Bottom", "Bottom_Pred"),
                            ("Side", "Side_Pred")]:
            vtp,vfp,vtn,vfn,vp,vr,vf1 = view_metrics(key)
            print("  {:<20}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
                label, vf1, vp, vr, vtp, vfp, vtn, vfn))
        print("  " + "-"*66)
        print("  {:<20}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
            "COMBINED (final)", f1, prec, rec, tp, fp, tn, fn))
        print()
        nr = sum(1 for r in rows if r["Needs_Review"]=="Yes")
        print("  Needs_Review flagged: {}".format(nr))
        print("="*70)

    # ── Save CSV ──────────────────────────────────────────────────────────────
    # with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
    #     writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    #     writer.writeheader()
    #     writer.writerows(rows)
    if not rows:
        print("\nERROR: No images were scored. Check the errors above.")
    else:
        with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("\nResults saved -> {}".format(args.output_csv))

    # print("\nResults saved -> {}".format(args.output_csv))

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()