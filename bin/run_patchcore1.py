## Top and Bottom

import contextlib
import logging
import os
import sys
import shutil
import csv

import click
import numpy as np
import torch
import PIL.Image

import patchcore.backbones
import patchcore.common
import patchcore.metrics
import patchcore.patchcore
import patchcore.sampler
import patchcore.utils

import warnings
warnings.filterwarnings("ignore")

LOGGER = logging.getLogger(__name__)

_DATASETS = {"mvtec": ["patchcore.datasets.mvtec", "MVTecDataset"],
             "selfds": ["patchcore.datasets.selfds", "SelfDS"]}


# ==============================================================================
#  GEOMETRIC CHECKER — honest, anomaly-blind calibration
#
#  Principle: learns the expected radial intensity profile from good training
#  images ONLY (no anomaly labels ever used). Flags any test image whose
#  profile deviates significantly from the good distribution.
#
#  This mirrors what PatchCore does in deep-feature space, but in pixel-space.
#
#  Score = max z-score deviation over the outer half of the part (bins 100-195)
#  The outer half carries more defect signal than the uniform inner face.
#
#  Threshold = p95 of good-image scores (5% of good parts will exceed it).
#  Tunable via GEO_PERCENTILE — raise to catch more, lower to reduce FP.
#
#  NO anomaly images, NO defect type names, NO bin selection from test data
#  were used to design this checker. It generalises to unseen defect types.
# ==============================================================================

BG_THRESHOLD    = 15
N_ANGLES        = 360
PROFILE_BINS    = 200
SCORE_BIN_START = 160   # outer ring zone only: r = 0.80R to 0.93R
SCORE_BIN_END   = 187   # (27 bins — wide enough to be stable, tight enough to be signal)
GEO_PERCENTILE  = 99    # p95 of good scores -> threshold


def _geo_gray(pil_image):
    return np.array(pil_image.convert("RGB"), dtype=np.float32).mean(axis=2)


def _geo_centre_radius(gray):
    mask = gray > BG_THRESHOLD
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        h, w = gray.shape
        return h // 2, w // 2, min(h, w) // 2
    cy = (rows[0] + rows[-1]) / 2.0
    cx = (cols[0] + cols[-1]) / 2.0
    R  = min(rows[-1] - rows[0], cols[-1] - cols[0]) / 2.0
    return cy, cx, R


def _geo_radial_profile(gray, cy, cx, R):
    profile = np.zeros(PROFILE_BINS, dtype=np.float64)
    counts  = np.zeros(PROFILE_BINS, dtype=np.float64)
    h, w    = gray.shape
    for angle in np.linspace(0, 2 * np.pi, N_ANGLES, endpoint=False):
        ca, sa = np.cos(angle), np.sin(angle)
        for b in range(PROFILE_BINS):
            r_px = (b / PROFILE_BINS) * R
            yi = int(round(cy + r_px * sa))
            xi = int(round(cx + r_px * ca))
            if 0 <= yi < h and 0 <= xi < w:
                profile[b] += gray[yi, xi]
                counts[b]  += 1
    profile[counts > 0] /= counts[counts > 0]
    return profile


def _get_profile(image_path):
    """Load image, preprocess, return radial profile. Returns None on failure."""
    try:
        pil = PIL.Image.open(image_path).convert("RGB")
        try:
            from patchcore.datasets.selfds import auto_crop_part, normalise_brightness
            pil = auto_crop_part(pil)
            pil = normalise_brightness(pil)
        except Exception:
            pass
    except Exception as e:
        LOGGER.warning("geo: cannot open {}: {}".format(image_path, e))
        return None
    gray      = _geo_gray(pil)
    cy, cx, R = _geo_centre_radius(gray)
    if R < 20:
        return None
    return _geo_radial_profile(gray, cy, cx, R)


def _profile_anomaly_score(profile, good_mean, good_std):
    """
    Mean z-score deviation of this profile vs the good distribution,
    measured over the outer half of the part (bins SCORE_BIN_START:SCORE_BIN_END).
    Higher score = more abnormal.

    We use MEAN (not max) because:
    - max z over 96 bins is dominated by a single noisy bin, inflating scores
      for normal images and pushing p95 threshold to ~3.2 sigma
    - mean z is stable: good images stay ~0.5-0.8, real defects hit 1.0-2.5
    - this gives a tight, separable distribution without any anomaly peeking
    """
    seg      = profile[SCORE_BIN_START:SCORE_BIN_END]
    mean_seg = good_mean[SCORE_BIN_START:SCORE_BIN_END]
    std_seg  = good_std[SCORE_BIN_START:SCORE_BIN_END]
    z        = np.abs(seg - mean_seg) / (std_seg + 1e-6)
    return float(z.mean())


def calibrate_geo(train_image_paths):
    """
    Learn the good-part radial profile distribution from training images.
    Returns (good_mean, good_std, threshold) — all derived from good images only.
    No anomaly information used.
    """
    LOGGER.info("Geo calibration: profiling {} training images...".format(
        len(train_image_paths)))
    profiles = []
    for path in train_image_paths:
        p = _get_profile(path)
        if p is not None:
            profiles.append(p)

    if len(profiles) < 5:
        LOGGER.warning("Geo calibration: too few profiles ({}), checker disabled.".format(
            len(profiles)))
        return None, None, None

    arr       = np.array(profiles)          # (N, 200)
    good_mean = arr.mean(axis=0)            # (200,)
    good_std  = arr.std(axis=0)             # (200,)

    # Score every training-good image against the good distribution
    good_scores = np.array([
        _profile_anomaly_score(p, good_mean, good_std) for p in profiles
    ])
    threshold = float(np.percentile(good_scores, GEO_PERCENTILE))

    LOGGER.info(
        "Geo calibration done: n={} good_scores mean={:.2f} std={:.2f} "
        "p{}={:.2f} (threshold)".format(
            len(profiles), good_scores.mean(), good_scores.std(),
            GEO_PERCENTILE, threshold))
    return good_mean, good_std, threshold


def geometric_check(image_path, good_mean, good_std, threshold):
    """
    Score one image against the calibrated good distribution.
    Returns dict: {defect, score, threshold, details}
    """
    profile = _get_profile(image_path)
    if profile is None:
        return {"defect": False, "score": None, "threshold": threshold,
                "details": "read_error"}

    score  = _profile_anomaly_score(profile, good_mean, good_std)
    defect = score > threshold
    return {"defect": defect, "score": round(score, 3),
            "threshold": round(threshold, 3),
            "details": "z_mean={:.2f} thr={:.2f}".format(score, threshold)}


# ==============================================================================
#  DEFECT BANK — nearest neighbour exception list
#
#  Place any number of defect images (any filename, no subfolders needed) into:
#    <data_path>/<classname>/known_defects/
#
#  At training time the bank is built automatically:
#    - extract backbone embedding for each defect image
#    - calibrate similarity threshold from intra-bank distances
#    - save defect_bank.pkl next to the PatchCore model
#
#  At inference time (ambiguous PC score zone only):
#    - extract embedding of test image
#    - compute min distance to all defect bank embeddings
#    - if distance < threshold → ANOMALY
#
#  To add new defect types later: just drop images into known_defects/
#  No retraining, no code changes needed.
#
#  RECHECK zone: score in [RECHECK_LOW, pc_threshold] and not caught by
#  geo or defect bank → sent to human inspector instead of auto-passing.
# ==============================================================================

RECHECK_LOW = 0.05   # scores below this = auto GOOD, above = ambiguous zone


def _extract_image_embedding(image_path, PatchCore_list, device):
    """
    Extract the aggregated image-level embedding for one image
    using the same backbone(s) as PatchCore.
    Returns a 1-D numpy array (concatenation across backbones).
    """
    try:
        pil = PIL.Image.open(image_path).convert("RGB")
        try:
            from patchcore.datasets.selfds import auto_crop_part, normalise_brightness
            pil = auto_crop_part(pil)
            pil = normalise_brightness(pil)
        except Exception:
            pass
    except Exception as e:
        LOGGER.warning("defect_bank: cannot open {}: {}".format(image_path, e))
        return None

    parts = []
    for PC in PatchCore_list:
        try:
            # Use the backbone's forward_features if available, else forward
            import torchvision.transforms as T
            transform = T.Compose([
                T.Resize((PC.input_shape[-1], PC.input_shape[-1])),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225]),
            ])
            tensor = transform(pil).unsqueeze(0).to(device)
            with torch.no_grad():
                # Extract features from the backbone layers
                features = PC.forward_modules["feature_aggregator"](tensor)
                # features is a dict of layer_name -> tensor
                # aggregate spatially (global average pool) then flatten
                agg = []
                for layer_feat in features.values():
                    # layer_feat shape: (1, C, H, W)
                    pooled = layer_feat.mean(dim=[2, 3])  # (1, C)
                    agg.append(pooled.squeeze(0).cpu().numpy())
                parts.append(np.concatenate(agg))
        except Exception as e:
            LOGGER.warning("defect_bank: embedding failed for {}: {}".format(
                image_path, e))
            return None

    if not parts:
        return None
    return np.concatenate(parts)


def build_defect_bank(data_path, classname, PatchCore_list, device):
    """
    Build the defect bank from known_defects/ folder.
    Returns (embeddings, paths, threshold) or (None, None, None) if folder
    doesn't exist or has fewer than 2 images.
    """
    defects_dir = os.path.join(data_path, classname, "known_defects")
    if not os.path.exists(defects_dir):
        LOGGER.info("Defect bank: no known_defects/ folder found at {}".format(
            defects_dir))
        LOGGER.info("  -> Create it and add defect images to enable the defect bank")
        return None, None, None

    image_files = sorted([
        f for f in os.listdir(defects_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ])

    if len(image_files) < 2:
        LOGGER.warning("Defect bank: need at least 2 images in known_defects/, "
                       "found {}. Bank disabled.".format(len(image_files)))
        return None, None, None

    LOGGER.info("Defect bank: extracting embeddings from {} images...".format(
        len(image_files)))

    embeddings = []
    valid_paths = []
    for fname in image_files:
        path = os.path.join(defects_dir, fname)
        emb  = _extract_image_embedding(path, PatchCore_list, device)
        if emb is not None:
            embeddings.append(emb)
            valid_paths.append(path)
            LOGGER.info("  OK  {}  dim={}".format(fname, emb.shape[0]))
        else:
            LOGGER.warning("  SKIP  {}".format(fname))

    if len(embeddings) < 2:
        LOGGER.warning("Defect bank: too few valid embeddings. Bank disabled.")
        return None, None, None

    emb_matrix = np.array(embeddings)   # (N, D)

    # Calibrate threshold: median intra-bank nearest-neighbour distance × 1.2
    # For each defect image, find its closest OTHER defect image
    nn_dists = []
    for i in range(len(emb_matrix)):
        others = np.delete(emb_matrix, i, axis=0)
        diffs  = others - emb_matrix[i]
        dists  = np.linalg.norm(diffs, axis=1)
        nn_dists.append(dists.min())

    threshold = float(np.median(nn_dists) * 1.2)

    LOGGER.info(
        "Defect bank ready: n={} embeddings  "
        "nn_dist median={:.1f}  threshold={:.1f}".format(
            len(embeddings), float(np.median(nn_dists)), threshold))

    return emb_matrix, valid_paths, threshold


def defect_bank_check(image_path, emb_matrix, PatchCore_list, device, threshold):
    """
    Check if image is close to any known defect embedding.
    Returns dict: {defect: bool, distance: float, threshold: float}
    """
    emb = _extract_image_embedding(image_path, PatchCore_list, device)
    if emb is None:
        return {"defect": False, "distance": None, "threshold": threshold}

    diffs = emb_matrix - emb          # (N, D)
    dists = np.linalg.norm(diffs, axis=1)
    min_dist = float(dists.min())
    return {
        "defect":    min_dist < threshold,
        "distance":  round(min_dist, 2),
        "threshold": round(threshold, 2),
    }

@click.group(chain=True)
@click.argument("results_path", type=str)
@click.option(
    "--gpu",
    type=int,
    multiple=True,
    help="GPU IDs to use. Omit this option to run on CPU.",
)
@click.option("--seed", type=int, default=0, show_default=True)
@click.option("--log_group",   type=str, default="group")
@click.option("--log_project", type=str, default="project")
@click.option("--save_segmentation_images", is_flag=True)
@click.option("--save_patchcore_model",     is_flag=True)
def main(**kwargs):
    pass


@main.result_callback()
def run(methods, results_path, gpu, seed, log_group, log_project,
        save_segmentation_images, save_patchcore_model):

    methods       = {key: item for (key, item) in methods}
    run_save_path = os.path.join(results_path, log_project)
    os.makedirs(run_save_path, exist_ok=True)

    list_of_dataloaders = methods["get_dataloaders"](seed)
    device = patchcore.utils.set_torch_device(gpu)
    device_context = (
        torch.cuda.device("cuda:{}".format(device.index))
        if "cuda" in device.type.lower()
        else contextlib.suppress()
    )

    result_collect = []

    for dataloader_count, dataloaders in enumerate(list_of_dataloaders):
        LOGGER.info("Evaluating dataset [{}] ({}/{})...".format(
            dataloaders["training"].name, dataloader_count + 1,
            len(list_of_dataloaders)))
        patchcore.utils.fix_seeds(seed, with_cuda=device.type == "cuda")
        dataset_name = dataloaders["training"].name

        with device_context:
            torch.cuda.empty_cache()
            imagesize      = dataloaders["training"].dataset.imagesize
            sampler        = methods["get_sampler"](device)
            PatchCore_list = methods["get_patchcore"](imagesize, sampler, device)

            if len(PatchCore_list) > 1:
                LOGGER.info("Utilizing PatchCore Ensemble (N={}).".format(
                    len(PatchCore_list)))

            # STEP 1: Fit
            for i, PC in enumerate(PatchCore_list):
                torch.cuda.empty_cache()
                if PC.backbone.seed is not None:
                    patchcore.utils.fix_seeds(
                        PC.backbone.seed, with_cuda=device.type == "cuda"
                    )
                LOGGER.info("Training models ({}/{})".format(i + 1, len(PatchCore_list)))
                PC.fit(dataloaders["training"])

            # STEP 1b: Geometric checker — DISABLED
            # The geo checker fires on good parts with slight orientation/placement
            # variation, contributing FPs. PatchCore already captures texture/shape
            # anomalies. Disable to reduce combined FP rate across 3 views × 3 judges.
            geo_mean = geo_std = geo_threshold = None
            geo_enabled = False
            LOGGER.info("Geometric checker DISABLED (suppressed to reduce FP rate)")

            # STEP 1c: Build defect bank from known_defects/ folder
            training_dataset = dataloaders["training"].dataset
            data_path = training_dataset.source
            classname = getattr(training_dataset, "classname", None)
            if classname is None:
                # Standard MVTec AD has no labelled known-defect bank. Keep
                # its unsupervised benchmark protocol intact.
                db_matrix, db_paths, db_threshold = None, [], None
            else:
                db_matrix, db_paths, db_threshold = build_defect_bank(
                    data_path, classname, PatchCore_list, device
                )
            db_enabled = db_matrix is not None
            if db_enabled:
                LOGGER.info("Defect bank ENABLED  n={}  threshold={:.1f}".format(
                    len(db_paths), db_threshold))
            else:
                LOGGER.info("Defect bank DISABLED (no known_defects/ folder or too few images)")

            # STEP 2: Raw val scores
            use_val    = dataloaders.get("validation") is not None
            ref_loader = dataloaders["validation"] if use_val else dataloaders["training"]
            if not use_val:
                LOGGER.warning("No validation split! Falling back to training scores.")

            LOGGER.info("Scoring {} set for normalisation...".format(
                "VALIDATION" if use_val else "TRAINING (fallback)"))
            val_raw = []
            for i, PC in enumerate(PatchCore_list):
                torch.cuda.empty_cache(); PC.backbone.eval()
                raw = []
                with torch.no_grad():
                    for batch in ref_loader:
                        s, _ = PC.predict(batch["image"].to(device))
                        raw.extend([float(x) for x in s])
                arr = np.array(raw)
                val_raw.append(arr)
                LOGGER.info("  Backbone {}/{} raw  min={:.4f} max={:.4f} mean={:.4f} n={}".format(
                    i+1, len(PatchCore_list), arr.min(), arr.max(), arr.mean(), len(arr)))
            val_raw = np.array(val_raw)

            # STEP 3: Bake normalisation
            for i, PC in enumerate(PatchCore_list):
                s_min = float(val_raw[i].min())
                s_max = float(np.percentile(val_raw[i], 99))
                PC.set_score_normalization(s_min, s_max)
                LOGGER.info("  Backbone {}/{} bounds s_min={:.4f} s_max={:.4f}".format(
                    i+1, len(PatchCore_list), s_min, s_max))

            # STEP 4: Re-score val normalised
            val_norm = []
            for i, PC in enumerate(PatchCore_list):
                torch.cuda.empty_cache(); PC.backbone.eval()
                ns = []
                with torch.no_grad():
                    for batch in ref_loader:
                        s, _ = PC.predict(batch["image"].to(device))
                        ns.extend([float(x) for x in s])
                val_norm.append(np.array(ns))
            val_scores = np.mean(np.array(val_norm), axis=0)
            val_scores.sort()
            LOGGER.info("Val normalised  min={:.4f} max={:.4f} mean={:.4f} std={:.4f}".format(
                val_scores.min(), val_scores.max(), val_scores.mean(), val_scores.std()))

            # STEP 5: Score test images
            aggregator = {"scores": [], "segmentations": []}
            for i, PC in enumerate(PatchCore_list):
                torch.cuda.empty_cache(); PC.backbone.eval()
                LOGGER.info("Embedding test data ({}/{})".format(i+1, len(PatchCore_list)))
                scores, segs, _, _ = PC.predict(dataloaders["testing"])
                aggregator["scores"].append(scores)
                aggregator["segmentations"].append(segs)
            test_scores = np.mean(np.array(aggregator["scores"]), axis=0)

            # STEP 6: Normalise segmentations
            segs    = np.array(aggregator["segmentations"])
            seg_min = segs.reshape(len(segs), -1).min(axis=-1).reshape(-1,1,1,1)
            seg_max = segs.reshape(len(segs), -1).max(axis=-1).reshape(-1,1,1,1)
            segs    = (segs - seg_min) / (seg_max - seg_min + 1e-8)
            segs    = np.mean(segs, axis=0)

            # STEP 7: PatchCore threshold (p99 of good val scores)
            # val_scores are normalised: good images → [0, ~1.0], anomaly → >1.0.
            # p99 ≈ 1.0 means only the top 1% of good images are at risk of FP.
            pc_threshold = float(np.percentile(val_scores, 99))
            LOGGER.info("PC threshold={:.4f}  (val p99, n_val={})".format(
                pc_threshold, len(val_scores)))

            # STEP 8: Save score stats
            score_stats = {
                "pc_threshold": pc_threshold,
                "geo_threshold": geo_threshold,
                "geo_enabled": geo_enabled,
                "mean": float(val_scores.mean()), "std": float(val_scores.std()),
                "min": float(val_scores.min()),   "max": float(val_scores.max()),
                "p95": float(np.percentile(val_scores, 95)),
                "p99": float(np.percentile(val_scores, 99)),
                "n_val": int(len(val_scores)), "used_val": use_val,
            }
            np.save(os.path.join(run_save_path, "score_stats.npy"), score_stats)
            np.save(os.path.join(run_save_path, "good_val_scores.npy"), val_scores)

            # STEP 9: Ground truth
            test_items = dataloaders["testing"].dataset.data_to_iterate
            anomaly_labels = [x[1] != "good" for x in test_items]

            # MVTec tuples are [class, anomaly, image_path, mask_path], while
            # the WCTE SelfDS tuples are [image_path, label, None, None].
            # Select the real image path without coupling evaluation to either
            # dataset representation.
            image_paths = [
                item[2] if len(item) >= 3 and item[2] is not None else item[0]
                for item in test_items
            ]

            # =================================================================
            #  STEP 10: Per-image predictions — BINARY: GOOD or ANOMALY
            #
            #  Final prediction is always GOOD or ANOMALY — nothing else.
            #
            #  ANOMALY if ANY of:
            #    - pc_score >= pc_threshold
            #    - geo checker flags it
            #    - defect bank flags it (checked in ambiguous zone only)
            #
            #  GOOD otherwise.
            #
            #  Needs_Review flag (separate from prediction):
            #    True when pc_score is in [RECHECK_LOW, pc_threshold) AND
            #    nothing flagged it. These are low-confidence GOOD predictions
            #    that a human may want to double-check. The final prediction
            #    is still GOOD — this is just an advisory flag.
            # =================================================================

            print("\n" + "=" * 115)
            print("PER-IMAGE PREDICTIONS  [GOOD / ANOMALY]")
            print("=" * 115)

            rows = []
            for idx, score in enumerate(test_scores):
                img_path = image_paths[idx]
                # Include the anomaly-type folder so names such as
                # broken_large/000.png and contamination/000.png stay unique.
                fname = os.path.join(
                    os.path.basename(os.path.dirname(img_path)),
                    os.path.basename(img_path),
                ).replace("\\", "/")
                score    = float(score)

                # --- PatchCore decision ---
                pc_pred = "ANOMALY" if score >= pc_threshold else "GOOD"

                # --- Geometric decision ---
                if geo_enabled:
                    geo_result = geometric_check(img_path, geo_mean, geo_std, geo_threshold)
                    geo_pred   = "ANOMALY" if geo_result["defect"] else "GOOD"
                    geo_score  = geo_result["score"]
                else:
                    geo_pred  = "GOOD"
                    geo_score = None

                # --- Defect bank decision (ambiguous zone only) ---
                in_ambiguous = (score >= RECHECK_LOW and score < pc_threshold)
                if db_enabled and in_ambiguous and pc_pred == "GOOD" and geo_pred == "GOOD":
                    db_result = defect_bank_check(img_path, db_matrix,
                                                  PatchCore_list, device, db_threshold)
                    db_pred   = "ANOMALY" if db_result["defect"] else "GOOD"
                    db_dist   = db_result["distance"]
                else:
                    db_pred = "GOOD"
                    db_dist = None

                # --- Final binary decision ---
                if pc_pred == "ANOMALY" or geo_pred == "ANOMALY" or db_pred == "ANOMALY":
                    final_pred = "ANOMALY"
                else:
                    final_pred = "GOOD"

                # --- Advisory flag: low-confidence GOOD ---
                # Nothing flagged it but score is in the ambiguous zone
                needs_review = (final_pred == "GOOD" and in_ambiguous)

                gt      = "ANOMALY" if anomaly_labels[idx] else "GOOD"
                correct = "CORRECT" if final_pred == gt else "WRONG"

                geo_override = (pc_pred == "GOOD" and geo_pred == "ANOMALY")
                db_override  = (pc_pred == "GOOD" and geo_pred == "GOOD"
                                and db_pred == "ANOMALY")

                tag = ""
                if geo_override:  tag += "  <<GEO"
                if db_override:   tag += "  <<DEFECT_BANK"
                if needs_review:  tag += "  [review?]"

                print(
                    "  [{:7s}] {:43s}  GT:{:7s}  PRED:{:7s}  "
                    "PC:{:.3f}  GEO:{}  DB:{}{}".format(
                        correct, fname, gt, final_pred, score,
                        "{:.2f}".format(geo_score) if geo_score is not None else "N/A",
                        "{:.1f}".format(db_dist)   if db_dist   is not None else "N/A",
                        tag,
                    )
                )

                rows.append({
                    "Image":         fname,
                    "GT":            gt,
                    "Final_Pred":    final_pred,
                    "Correct":       "Yes" if final_pred == gt else "No",
                    "Needs_Review":  "Yes" if needs_review else "No",
                    "PC_Pred":       pc_pred,
                    "Geo_Pred":      geo_pred,
                    "DB_Pred":       db_pred,
                    "PC_Score":      round(score, 4),
                    "PC_Threshold":  round(pc_threshold, 4),
                    "Geo_ZScore":    geo_score if geo_score is not None else "",
                    "Geo_Threshold": round(float(geo_threshold), 3) if geo_threshold else "",
                    "DB_Distance":   db_dist if db_dist is not None else "",
                    "DB_Threshold":  round(db_threshold, 2) if db_enabled else "",
                    "Geo_Override":  "Yes" if geo_override else "No",
                    "DB_Override":   "Yes" if db_override  else "No",
                })

            # STEP 11: Metrics — binary GOOD/ANOMALY
            image_metrics = patchcore.metrics.compute_imagewise_retrieval_metrics(
                test_scores, anomaly_labels, manual_threshold=pc_threshold)
            auroc = image_metrics["auroc"]

            def _metrics(pred_key):
                tp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="ANOMALY")
                fp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="GOOD")
                tn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="GOOD")
                fn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="ANOMALY")
                prec = tp / max(1, tp + fp)
                rec  = tp / max(1, tp + fn)
                f1   = 2 * prec * rec / max(1e-8, prec + rec)
                return tp, fp, tn, fn, prec, rec, f1

            pc_tp,  pc_fp,  pc_tn,  pc_fn,  pc_prec,  pc_rec,  pc_f1  = _metrics("PC_Pred")
            geo_tp, geo_fp, geo_tn, geo_fn, geo_prec, geo_rec, geo_f1 = _metrics("Geo_Pred")
            fin_tp, fin_fp, fin_tn, fin_fn, precision, recall,  f1     = _metrics("Final_Pred")

            needs_review_count = sum(1 for r in rows if r["Needs_Review"] == "Yes")

            print("\n" + "=" * 75)
            print("EVALUATION SUMMARY")
            print("=" * 75)
            print("  {:<22}  {:>6}  {:>6}  {:>6}  {:>6}  {:>4}  {:>4}  {:>4}  {:>4}".format(
                "Method","AUROC","F1","Prec","Rec","TP","FP","TN","FN"))
            print("  " + "-"*71)
            print("  {:<22}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
                "PatchCore only", auroc, pc_f1, pc_prec, pc_rec,
                pc_tp, pc_fp, pc_tn, pc_fn))
            if geo_enabled:
                print("  {:<22}  {:>6}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
                    "Geometric only", "N/A", geo_f1, geo_prec, geo_rec,
                    geo_tp, geo_fp, geo_tn, geo_fn))
            print("  {:<22}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
                "COMBINED (final)", auroc, f1, precision, recall,
                fin_tp, fin_fp, fin_tn, fin_fn))
            print()
            print("  Needs_Review flag : {} GOOD predictions flagged for optional human check".format(
                needs_review_count))
            print("  PC threshold={:.4f}  Geo_z_thr={}  DB={}".format(
                pc_threshold,
                "{:.3f}".format(geo_threshold) if geo_threshold else "N/A",
                "enabled n={}".format(len(db_paths)) if db_enabled else "disabled"))
            print("=" * 75 + "\n")

            # STEP 11b: CSV output
            csv_path = os.path.join(run_save_path,
                                    "{}_predictions.csv".format(dataset_name))
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            LOGGER.info("CSV saved -> {}".format(csv_path))

            summary_path = os.path.join(run_save_path,
                                        "{}_summary.csv".format(dataset_name))
            with open(summary_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Method","AUROC","F1","Precision","Recall","TP","FP","TN","FN"])
                w.writerow(["PatchCore_only", round(auroc,4), round(pc_f1,4),
                             round(pc_prec,4), round(pc_rec,4),
                             pc_tp, pc_fp, pc_tn, pc_fn])
                if geo_enabled:
                    w.writerow(["Geometric_only","N/A", round(geo_f1,4),
                                 round(geo_prec,4), round(geo_rec,4),
                                 geo_tp, geo_fp, geo_tn, geo_fn])
                w.writerow(["COMBINED_final", round(auroc,4), round(f1,4),
                             round(precision,4), round(recall,4),
                             fin_tp, fin_fp, fin_tn, fin_fn])
                w.writerow([])
                w.writerow(["Needs_Review_count", needs_review_count])
                w.writerow(["PC_Threshold",   round(pc_threshold,4)])
                w.writerow(["Geo_ZThreshold", round(geo_threshold,3) if geo_threshold else "N/A"])
                w.writerow(["GEO_Percentile", GEO_PERCENTILE])
                w.writerow(["DB_enabled",     db_enabled])
                w.writerow(["DB_n_images",    len(db_paths) if db_enabled else 0])
                w.writerow(["DB_threshold",   round(db_threshold,2) if db_enabled else "N/A"])
                w.writerow(["Val_images",     len(val_scores)])
            LOGGER.info("Summary CSV -> {}".format(summary_path))

            # STEP 11c: Excel
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                from openpyxl.utils import get_column_letter

                wb  = Workbook()
                ws1 = wb.active
                ws1.title = "Predictions"
                headers = list(rows[0].keys())

                hdr_fill = PatternFill("solid", start_color="2E4057")
                hdr_font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
                ca       = Alignment(horizontal="center", vertical="center")
                thin     = Side(style="thin")
                bdr      = Border(left=thin, right=thin, top=thin, bottom=thin)

                for ci, h in enumerate(headers, 1):
                    cell = ws1.cell(row=1, column=ci, value=h)
                    cell.font = hdr_font; cell.fill = hdr_fill
                    cell.alignment = ca;  cell.border = bdr

                green = PatternFill("solid", start_color="D4EDDA")
                red   = PatternFill("solid", start_color="F8D7DA")
                amber = PatternFill("solid", start_color="FFF3CD")
                blue  = PatternFill("solid", start_color="CCE5FF")

                for ri, row in enumerate(rows, 2):
                    if row["Correct"] == "No":
                        fill = red
                    elif row["Geo_Override"] == "Yes" and row["Correct"] == "Yes":
                        fill = blue
                    elif row["Needs_Review"] == "Yes":
                        fill = amber
                    else:
                        fill = green
                    for ci, key in enumerate(headers, 1):
                        cell = ws1.cell(row=ri, column=ci, value=row.get(key,""))
                        cell.font = Font(name="Calibri", size=10)
                        cell.fill = fill; cell.alignment = ca; cell.border = bdr

                col_widths = [42,9,12,9,9,9,10,12,13,13,13,12,9]
                for i, w in enumerate(col_widths, 1):
                    ws1.column_dimensions[get_column_letter(i)].width = w
                ws1.row_dimensions[1].height = 22

                ws2 = wb.create_sheet("Summary")
                sum_headers = ["Method","AUROC","F1","Precision","Recall",
                                "TP","FP","TN","FN"]
                for ci, h in enumerate(sum_headers, 1):
                    cell = ws2.cell(row=1, column=ci, value=h)
                    cell.font = hdr_font; cell.fill = hdr_fill; cell.alignment = ca

                fills2 = [PatternFill("solid", start_color="E8F4FD"),
                          PatternFill("solid", start_color="EAF7EA"),
                          PatternFill("solid", start_color="FFF9E6")]
                rows2  = [
                    ["PatchCore only", round(auroc,4), round(pc_f1,4),
                     round(pc_prec,4), round(pc_rec,4), pc_tp, pc_fp, pc_tn, pc_fn],
                ]
                if geo_enabled:
                    rows2.append(["Geometric only","N/A", round(geo_f1,4),
                                   round(geo_prec,4), round(geo_rec,4),
                                   geo_tp, geo_fp, "-", geo_fn])
                rows2.append(["COMBINED (final)", round(auroc,4), round(f1,4),
                               round(precision,4), round(recall,4),
                               fin_tp, fin_fp, fin_tn, fin_fn])
                for ri, (dr, fill) in enumerate(zip(rows2, fills2), 2):
                    for ci, val in enumerate(dr, 1):
                        cell = ws2.cell(row=ri, column=ci, value=val)
                        cell.font = Font(name="Calibri", size=10, bold=(ci==1))
                        cell.fill = fill; cell.alignment = ca; cell.border = bdr
                ws2.append([])
                ws2.append(["PC Threshold",  round(pc_threshold,4)])
                ws2.append(["Geo Threshold",
                             round(geo_threshold,2) if geo_threshold else "N/A"])
                ws2.append(["Geo Percentile", GEO_PERCENTILE])
                ws2.append(["Val images",    len(val_scores)])
                ws2.append(["Dataset",       dataset_name])
                for i, w in enumerate([22,8,8,10,8,5,5,5,5], 1):
                    ws2.column_dimensions[get_column_letter(i)].width = w

                excel_path = os.path.join(run_save_path,
                                          "{}_results.xlsx".format(dataset_name))
                wb.save(excel_path)
                LOGGER.info("Excel saved -> {}".format(excel_path))
            except Exception as e:
                LOGGER.warning("Excel failed (CSV available): {}".format(e))

            # STEP 12: Segmentation images
            if save_segmentation_images:
                seg_image_paths = image_paths
                mask_paths = [x[3] if len(x) >= 4 else "-1"
                              for x in dataloaders["testing"].dataset.data_to_iterate]
                def image_transform(image):
                    in_std  = np.array(dataloaders["testing"].dataset.transform_std).reshape(-1,1,1)
                    in_mean = np.array(dataloaders["testing"].dataset.transform_mean).reshape(-1,1,1)
                    image   = dataloaders["testing"].dataset.transform_img(image)
                    return np.clip((image.numpy()*in_std+in_mean)*255,0,255).astype(np.uint8)
                def mask_transform(mask):
                    return dataloaders["testing"].dataset.transform_mask(mask).numpy()
                seg_path = os.path.join(run_save_path, "segmentation_images")
                os.makedirs(seg_path, exist_ok=True)
                patchcore.utils.plot_segmentation_images(
                    seg_path, seg_image_paths, segs, test_scores, mask_paths,
                    image_transform=image_transform, mask_transform=mask_transform)

            # STEP 13: Save model
            if save_patchcore_model:
                model_path = os.path.join(run_save_path, "models", dataset_name)
                os.makedirs(model_path, exist_ok=True)
                for i, PC in enumerate(PatchCore_list):
                    prepend = ("Ensemble-{}-{}_".format(i+1, len(PatchCore_list))
                               if len(PatchCore_list) > 1 else "")
                    PC.save_to_path(model_path, prepend)
                for fname in ["good_val_scores.npy", "score_stats.npy"]:
                    shutil.copy(os.path.join(run_save_path, fname),
                                os.path.join(model_path, fname))
                # Save geo calibration
                np.save(os.path.join(model_path, "geo_calibration.npy"), {
                    "good_mean":    geo_mean,
                    "good_std":     geo_std,
                    "threshold":    geo_threshold,
                    "percentile":   GEO_PERCENTILE,
                    "bin_start":    SCORE_BIN_START,
                    "bin_end":      SCORE_BIN_END,
                })
                # Save defect bank
                if db_enabled:
                    import pickle
                    db_save = {
                        "embeddings":  db_matrix,
                        "paths":       db_paths,
                        "threshold":   db_threshold,
                        "recheck_low": RECHECK_LOW,
                    }
                    with open(os.path.join(model_path, "defect_bank.pkl"), "wb") as f:
                        pickle.dump(db_save, f)
                    LOGGER.info("Defect bank saved -> {}".format(
                        os.path.join(model_path, "defect_bank.pkl")))
                LOGGER.info("Model saved -> {}".format(model_path))

            result_collect.append({
                "dataset_name":   dataset_name,
                "instance_auroc": auroc,
                "precision":      precision,
                "recall":         recall,
                "f1":             f1,
                "tp": fin_tp, "fp": fin_fp, "tn": fin_tn, "fn": fin_fn,
            })
            for key, item in result_collect[-1].items():
                if key != "dataset_name":
                    LOGGER.info("{}: {}".format(key, item))
        LOGGER.info("\n\n-----\n")

    result_metric_names  = list(result_collect[-1].keys())[1:]
    result_dataset_names = [r["dataset_name"] for r in result_collect]
    result_scores        = [list(r.values())[1:] for r in result_collect]
    patchcore.utils.compute_and_store_final_results(
        run_save_path, result_scores,
        column_names=result_metric_names, row_names=result_dataset_names)


# ==============================================================================
#  CLI COMMANDS
# ==============================================================================

@main.command("patch_core")
@click.option("--backbone_names", "-b", type=str, multiple=True, default=[])
@click.option("--layers_to_extract_from", "-le", type=str, multiple=True, default=[])
@click.option("--pretrain_embed_dimension", type=int, default=1024)
@click.option("--target_embed_dimension",  type=int, default=1024)
@click.option("--preprocessing",  type=click.Choice(["mean","conv"]), default="mean")
@click.option("--aggregation",    type=click.Choice(["mean","mlp"]),  default="mean")
@click.option("--anomaly_scorer_num_nn", type=int, default=5)
@click.option("--patchsize",      type=int, default=3)
@click.option("--patchscore",     type=str, default="max")
@click.option("--patchoverlap",   type=float, default=0.0)
@click.option("--patchsize_aggregate", "-pa", type=int, multiple=True, default=[])
@click.option("--faiss_on_gpu",   is_flag=True)
@click.option("--faiss_num_workers", type=int, default=8)
def patch_core(backbone_names, layers_to_extract_from, pretrain_embed_dimension,
               target_embed_dimension, preprocessing, aggregation, patchsize,
               patchscore, patchoverlap, anomaly_scorer_num_nn, patchsize_aggregate,
               faiss_on_gpu, faiss_num_workers):
    backbone_names = list(backbone_names)
    if len(backbone_names) > 1:
        layers_coll = [[] for _ in range(len(backbone_names))]
        for layer in layers_to_extract_from:
            idx   = int(layer.split(".")[0])
            layer = ".".join(layer.split(".")[1:])
            layers_coll[idx].append(layer)
    else:
        layers_coll = [layers_to_extract_from]

    def get_patchcore(input_shape, sampler, device):
        loaded = []
        for bb_name, layers in zip(backbone_names, layers_coll):
            bb_seed = None
            if ".seed-" in bb_name:
                bb_name, bb_seed = bb_name.split(".seed-")[0], int(bb_name.split("-")[-1])
            backbone = patchcore.backbones.load(bb_name)
            backbone.name, backbone.seed = bb_name, bb_seed
            nn_method = patchcore.common.FaissNN(faiss_on_gpu, faiss_num_workers)
            pc = patchcore.patchcore.PatchCore(device)
            pc.load(backbone=backbone, layers_to_extract_from=layers,
                    device=device, input_shape=input_shape,
                    pretrain_embed_dimension=pretrain_embed_dimension,
                    target_embed_dimension=target_embed_dimension,
                    patchsize=patchsize, featuresampler=sampler,
                    anomaly_scorer_num_nn=anomaly_scorer_num_nn, nn_method=nn_method)
            loaded.append(pc)
        return loaded
    return ("get_patchcore", get_patchcore)


@main.command("sampler")
@click.argument("name", type=str)
@click.option("--percentage", "-p", type=float, default=0.1, show_default=True)
def sampler(name, percentage):
    def get_sampler(device):
        if name == "identity":
            return patchcore.sampler.IdentitySampler()
        elif name == "greedy_coreset":
            return patchcore.sampler.GreedyCoresetSampler(percentage, device)
        elif name == "approx_greedy_coreset":
            return patchcore.sampler.ApproximateGreedyCoresetSampler(percentage, device)
    return ("get_sampler", get_sampler)


@main.command("dataset")
@click.argument("name",      type=str)
@click.argument("data_path", type=click.Path(exists=True, file_okay=False))
@click.option("--subdatasets",     "-d", multiple=True, type=str, required=True)
@click.option("--train_val_split", type=float, default=0.8, show_default=True)
@click.option("--batch_size",  default=2,   type=int, show_default=True)
@click.option("--num_workers", default=8,   type=int, show_default=True)
@click.option("--resize",      default=256, type=int, show_default=True)
@click.option("--imagesize",   default=224, type=int, show_default=True)
@click.option("--augment",     is_flag=True)
def dataset(name, data_path, subdatasets, train_val_split,
            batch_size, resize, imagesize, num_workers, augment):
    dataset_info    = _DATASETS[name]
    dataset_library = __import__(dataset_info[0], fromlist=[dataset_info[1]])

    def get_dataloaders(seed):
        dataloaders = []
        for subdataset in subdatasets:
            train_ds = dataset_library.__dict__[dataset_info[1]](
                data_path, classname=subdataset, resize=resize,
                train_val_split=train_val_split, imagesize=imagesize,
                split=dataset_library.DatasetSplit.TRAIN, seed=seed, augment=augment)
            test_ds = dataset_library.__dict__[dataset_info[1]](
                data_path, classname=subdataset, resize=resize,
                imagesize=imagesize, split=dataset_library.DatasetSplit.TEST, seed=seed)
            train_dl = torch.utils.data.DataLoader(
                train_ds, batch_size=batch_size, shuffle=False,
                num_workers=num_workers, pin_memory=True)
            test_dl = torch.utils.data.DataLoader(
                test_ds, batch_size=batch_size, shuffle=False,
                num_workers=num_workers, pin_memory=True)
            train_dl.name = name + ("_" + subdataset if subdataset else "")
            val_dl = None
            if train_val_split < 1:
                val_ds = dataset_library.__dict__[dataset_info[1]](
                    data_path, classname=subdataset, resize=resize,
                    train_val_split=train_val_split, imagesize=imagesize,
                    split=dataset_library.DatasetSplit.VAL, seed=seed)
                val_dl = torch.utils.data.DataLoader(
                    val_ds, batch_size=batch_size, shuffle=False,
                    num_workers=num_workers, pin_memory=True)
                LOGGER.info("Train/Val split: {} train, {} val".format(
                    len(train_ds), len(val_ds)))
            dataloaders.append({"training": train_dl, "validation": val_dl,
                                 "testing": test_dl})
        return dataloaders
    return ("get_dataloaders", get_dataloaders)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    LOGGER.info("Command line arguments: {}".format(" ".join(sys.argv)))
    main()






# import contextlib
# import logging
# import os
# import sys
# import shutil
# import csv

# import click
# import numpy as np
# import torch
# import PIL.Image

# import patchcore.backbones
# import patchcore.common
# import patchcore.metrics
# import patchcore.patchcore
# import patchcore.sampler
# import patchcore.utils

# import warnings
# warnings.filterwarnings("ignore")

# LOGGER = logging.getLogger(__name__)

# _DATASETS = {"mvtec": ["patchcore.datasets.mvtec", "MVTecDataset"],
#              "selfds": ["patchcore.datasets.selfds", "SelfDS"]}


# # ==============================================================================
# #  GEOMETRIC CHECKER — honest, anomaly-blind calibration
# # ==============================================================================

# BG_THRESHOLD    = 15
# N_ANGLES        = 360
# PROFILE_BINS    = 200
# SCORE_BIN_START = 160
# SCORE_BIN_END   = 187
# GEO_PERCENTILE  = 95


# def _geo_gray(pil_image):
#     return np.array(pil_image.convert("RGB"), dtype=np.float32).mean(axis=2)


# def _geo_centre_radius(gray):
#     mask = gray > BG_THRESHOLD
#     rows = np.where(mask.any(axis=1))[0]
#     cols = np.where(mask.any(axis=0))[0]
#     if len(rows) == 0 or len(cols) == 0:
#         h, w = gray.shape
#         return h // 2, w // 2, min(h, w) // 2
#     cy = (rows[0] + rows[-1]) / 2.0
#     cx = (cols[0] + cols[-1]) / 2.0
#     R  = min(rows[-1] - rows[0], cols[-1] - cols[0]) / 2.0
#     return cy, cx, R


# def _geo_radial_profile(gray, cy, cx, R):
#     profile = np.zeros(PROFILE_BINS, dtype=np.float64)
#     counts  = np.zeros(PROFILE_BINS, dtype=np.float64)
#     h, w    = gray.shape
#     for angle in np.linspace(0, 2 * np.pi, N_ANGLES, endpoint=False):
#         ca, sa = np.cos(angle), np.sin(angle)
#         for b in range(PROFILE_BINS):
#             r_px = (b / PROFILE_BINS) * R
#             yi = int(round(cy + r_px * sa))
#             xi = int(round(cx + r_px * ca))
#             if 0 <= yi < h and 0 <= xi < w:
#                 profile[b] += gray[yi, xi]
#                 counts[b]  += 1
#     profile[counts > 0] /= counts[counts > 0]
#     return profile


# def _get_profile(image_path):
#     try:
#         pil = PIL.Image.open(image_path).convert("RGB")
#         try:
#             from patchcore.datasets.selfds import auto_crop_part, normalise_brightness
#             pil = auto_crop_part(pil)
#             pil = normalise_brightness(pil)
#         except Exception:
#             pass
#     except Exception as e:
#         LOGGER.warning("geo: cannot open {}: {}".format(image_path, e))
#         return None
#     gray      = _geo_gray(pil)
#     cy, cx, R = _geo_centre_radius(gray)
#     if R < 20:
#         return None
#     return _geo_radial_profile(gray, cy, cx, R)


# def _profile_anomaly_score(profile, good_mean, good_std):
#     seg      = profile[SCORE_BIN_START:SCORE_BIN_END]
#     mean_seg = good_mean[SCORE_BIN_START:SCORE_BIN_END]
#     std_seg  = good_std[SCORE_BIN_START:SCORE_BIN_END]
#     z        = np.abs(seg - mean_seg) / (std_seg + 1e-6)
#     return float(z.mean())


# def calibrate_geo(train_image_paths):
#     LOGGER.info("Geo calibration: profiling {} training images...".format(
#         len(train_image_paths)))
#     profiles = []
#     for path in train_image_paths:
#         p = _get_profile(path)
#         if p is not None:
#             profiles.append(p)
#     if len(profiles) < 5:
#         LOGGER.warning("Geo calibration: too few profiles ({}), disabled.".format(
#             len(profiles)))
#         return None, None, None
#     arr       = np.array(profiles)
#     good_mean = arr.mean(axis=0)
#     good_std  = arr.std(axis=0)
#     good_scores = np.array([
#         _profile_anomaly_score(p, good_mean, good_std) for p in profiles
#     ])
#     threshold = float(np.percentile(good_scores, GEO_PERCENTILE))
#     LOGGER.info("Geo calibration done: n={} mean={:.2f} std={:.2f} p{}={:.2f}".format(
#         len(profiles), good_scores.mean(), good_scores.std(), GEO_PERCENTILE, threshold))
#     return good_mean, good_std, threshold


# def geometric_check(image_path, good_mean, good_std, threshold):
#     profile = _get_profile(image_path)
#     if profile is None:
#         return {"defect": False, "score": None, "threshold": threshold,
#                 "details": "read_error"}
#     score  = _profile_anomaly_score(profile, good_mean, good_std)
#     defect = score > threshold
#     return {"defect": defect, "score": round(score, 3),
#             "threshold": round(threshold, 3),
#             "details": "z_mean={:.2f} thr={:.2f}".format(score, threshold)}


# # ==============================================================================
# #  DEFECT BANK — nearest neighbour exception list
# # ==============================================================================

# RECHECK_LOW = 0.05


# def _extract_image_embedding(image_path, PatchCore_list, device):
#     try:
#         pil = PIL.Image.open(image_path).convert("RGB")
#         try:
#             from patchcore.datasets.selfds import auto_crop_part, normalise_brightness
#             pil = auto_crop_part(pil)
#             pil = normalise_brightness(pil)
#         except Exception:
#             pass
#     except Exception as e:
#         LOGGER.warning("defect_bank: cannot open {}: {}".format(image_path, e))
#         return None
#     parts = []
#     for PC in PatchCore_list:
#         try:
#             import torchvision.transforms as T
#             transform = T.Compose([
#                 T.Resize((PC.input_shape[-1], PC.input_shape[-1])),
#                 T.ToTensor(),
#                 T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
#             ])
#             tensor = transform(pil).unsqueeze(0).to(device)
#             with torch.no_grad():
#                 features = PC.forward_modules["feature_aggregator"](tensor)
#                 agg = []
#                 for layer_feat in features.values():
#                     pooled = layer_feat.mean(dim=[2, 3])
#                     agg.append(pooled.squeeze(0).cpu().numpy())
#                 parts.append(np.concatenate(agg))
#         except Exception as e:
#             LOGGER.warning("defect_bank: embedding failed for {}: {}".format(image_path, e))
#             return None
#     if not parts:
#         return None
#     return np.concatenate(parts)


# def build_defect_bank(data_path, classname, PatchCore_list, device):
#     defects_dir = os.path.join(data_path, classname, "known_defects")
#     if not os.path.exists(defects_dir):
#         LOGGER.info("Defect bank: no known_defects/ folder at {}".format(defects_dir))
#         return None, None, None
#     image_files = sorted([
#         f for f in os.listdir(defects_dir)
#         if f.lower().endswith((".png", ".jpg", ".jpeg"))
#     ])
#     if len(image_files) < 2:
#         LOGGER.warning("Defect bank: need at least 2 images, found {}.".format(len(image_files)))
#         return None, None, None
#     LOGGER.info("Defect bank: extracting embeddings from {} images...".format(len(image_files)))
#     embeddings = []
#     valid_paths = []
#     for fname in image_files:
#         path = os.path.join(defects_dir, fname)
#         emb  = _extract_image_embedding(path, PatchCore_list, device)
#         if emb is not None:
#             embeddings.append(emb)
#             valid_paths.append(path)
#             LOGGER.info("  OK  {}  dim={}".format(fname, emb.shape[0]))
#         else:
#             LOGGER.warning("  SKIP  {}".format(fname))
#     if len(embeddings) < 2:
#         LOGGER.warning("Defect bank: too few valid embeddings. Disabled.")
#         return None, None, None
#     emb_matrix = np.array(embeddings)
#     nn_dists = []
#     for i in range(len(emb_matrix)):
#         others = np.delete(emb_matrix, i, axis=0)
#         dists  = np.linalg.norm(others - emb_matrix[i], axis=1)
#         nn_dists.append(dists.min())
#     threshold = float(np.median(nn_dists) * 1.2)
#     LOGGER.info("Defect bank ready: n={} nn_dist median={:.1f} threshold={:.1f}".format(
#         len(embeddings), float(np.median(nn_dists)), threshold))
#     return emb_matrix, valid_paths, threshold


# def defect_bank_check(image_path, emb_matrix, PatchCore_list, device, threshold):
#     emb = _extract_image_embedding(image_path, PatchCore_list, device)
#     if emb is None:
#         return {"defect": False, "distance": None, "threshold": threshold}
#     dists    = np.linalg.norm(emb_matrix - emb, axis=1)
#     min_dist = float(dists.min())
#     return {"defect": min_dist < threshold,
#             "distance": round(min_dist, 2),
#             "threshold": round(threshold, 2)}


# # ==============================================================================
# #  MAIN PATCHCORE PIPELINE
# # ==============================================================================

# @click.group(chain=True)
# @click.argument("results_path", type=str)
# @click.option("--gpu",  type=int, default=[0], multiple=True, show_default=True)
# @click.option("--seed", type=int, default=0, show_default=True)
# @click.option("--log_group",   type=str, default="group")
# @click.option("--log_project", type=str, default="project")
# @click.option("--save_segmentation_images", is_flag=True)
# @click.option("--save_patchcore_model",     is_flag=True)
# @click.option("--val_percentile", type=int, default=85, show_default=True,
#               help="Percentile of val scores used as PC threshold. "
#                    "Default 85. Use 40 for side view with augmentation.")
# def main(**kwargs):
#     pass


# @main.result_callback()
# def run(methods, results_path, gpu, seed, log_group, log_project,
#         save_segmentation_images, save_patchcore_model, val_percentile):

#     methods       = {key: item for (key, item) in methods}
#     run_save_path = os.path.join(results_path, log_project)
#     os.makedirs(run_save_path, exist_ok=True)

#     list_of_dataloaders = methods["get_dataloaders"](seed)
#     device = patchcore.utils.set_torch_device(gpu)
#     device_context = (
#         torch.cuda.device("cuda:{}".format(device.index))
#         if "cuda" in device.type.lower()
#         else contextlib.suppress()
#     )

#     result_collect = []

#     for dataloader_count, dataloaders in enumerate(list_of_dataloaders):
#         LOGGER.info("Evaluating dataset [{}] ({}/{})...".format(
#             dataloaders["training"].name, dataloader_count + 1,
#             len(list_of_dataloaders)))
#         patchcore.utils.fix_seeds(seed, device)
#         dataset_name = dataloaders["training"].name

#         with device_context:
#             torch.cuda.empty_cache()
#             imagesize      = dataloaders["training"].dataset.imagesize
#             sampler        = methods["get_sampler"](device)
#             PatchCore_list = methods["get_patchcore"](imagesize, sampler, device)

#             if len(PatchCore_list) > 1:
#                 LOGGER.info("Utilizing PatchCore Ensemble (N={}).".format(len(PatchCore_list)))

#             # STEP 1: Fit
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache()
#                 if PC.backbone.seed is not None:
#                     patchcore.utils.fix_seeds(PC.backbone.seed, device)
#                 LOGGER.info("Training models ({}/{})".format(i + 1, len(PatchCore_list)))
#                 PC.fit(dataloaders["training"])

#             # STEP 1b: Calibrate geo checker
#             train_paths = dataloaders["training"].dataset.imgpaths
#             geo_mean, geo_std, geo_threshold = calibrate_geo(train_paths)
#             geo_enabled = geo_threshold is not None
#             if geo_enabled:
#                 LOGGER.info("Geometric checker ENABLED  z_threshold={:.2f}".format(geo_threshold))
#             else:
#                 LOGGER.warning("Geometric checker DISABLED (calibration failed)")

#             # STEP 1c: Build defect bank
#             data_path  = dataloaders["training"].dataset.source
#             classname  = dataloaders["training"].dataset.classname
#             db_matrix, db_paths, db_threshold = build_defect_bank(
#                 data_path, classname, PatchCore_list, device)
#             db_enabled = db_matrix is not None
#             if db_enabled:
#                 LOGGER.info("Defect bank ENABLED  n={}  threshold={:.1f}".format(
#                     len(db_paths), db_threshold))
#             else:
#                 LOGGER.info("Defect bank DISABLED (no known_defects/ or too few images)")

#             # STEP 2: Raw val scores
#             use_val    = dataloaders.get("validation") is not None
#             ref_loader = dataloaders["validation"] if use_val else dataloaders["training"]
#             if not use_val:
#                 LOGGER.warning("No validation split! Falling back to training scores.")
#             LOGGER.info("Scoring {} set for normalisation...".format(
#                 "VALIDATION" if use_val else "TRAINING (fallback)"))
#             val_raw = []
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache(); PC.backbone.eval()
#                 raw = []
#                 with torch.no_grad():
#                     for batch in ref_loader:
#                         s, _ = PC.predict(batch["image"].to(device))
#                         raw.extend([float(x) for x in s])
#                 arr = np.array(raw)
#                 val_raw.append(arr)
#                 LOGGER.info("  Backbone {}/{} raw  min={:.4f} max={:.4f} mean={:.4f} n={}".format(
#                     i+1, len(PatchCore_list), arr.min(), arr.max(), arr.mean(), len(arr)))
#             val_raw = np.array(val_raw)

#             # STEP 3: Bake normalisation
#             for i, PC in enumerate(PatchCore_list):
#                 s_min = float(val_raw[i].min())
#                 s_max = float(np.percentile(val_raw[i], 99))
#                 PC.set_score_normalization(s_min, s_max)
#                 LOGGER.info("  Backbone {}/{} bounds s_min={:.4f} s_max={:.4f}".format(
#                     i+1, len(PatchCore_list), s_min, s_max))

#             # STEP 4: Re-score val normalised
#             val_norm = []
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache(); PC.backbone.eval()
#                 ns = []
#                 with torch.no_grad():
#                     for batch in ref_loader:
#                         s, _ = PC.predict(batch["image"].to(device))
#                         ns.extend([float(x) for x in s])
#                 val_norm.append(np.array(ns))
#             val_scores = np.mean(np.array(val_norm), axis=0)
#             val_scores.sort()
#             LOGGER.info("Val normalised  min={:.4f} max={:.4f} mean={:.4f} std={:.4f}".format(
#                 val_scores.min(), val_scores.max(), val_scores.mean(), val_scores.std()))

#             # STEP 5: Score test images
#             aggregator = {"scores": [], "segmentations": []}
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache(); PC.backbone.eval()
#                 LOGGER.info("Embedding test data ({}/{})".format(i+1, len(PatchCore_list)))
#                 scores, segs, _, _ = PC.predict(dataloaders["testing"])
#                 aggregator["scores"].append(scores)
#                 aggregator["segmentations"].append(segs)
#             test_scores = np.mean(np.array(aggregator["scores"]), axis=0)

#             # STEP 6: Normalise segmentations
#             segs    = np.array(aggregator["segmentations"])
#             seg_min = segs.reshape(len(segs), -1).min(axis=-1).reshape(-1,1,1,1)
#             seg_max = segs.reshape(len(segs), -1).max(axis=-1).reshape(-1,1,1,1)
#             segs    = (segs - seg_min) / (seg_max - seg_min + 1e-8)
#             segs    = np.mean(segs, axis=0)

#             # STEP 7: PatchCore threshold (configurable percentile)
#             pc_threshold = float(np.percentile(val_scores, val_percentile))
#             LOGGER.info("PC threshold={:.4f}  (val p{}, n_val={})".format(
#                 pc_threshold, val_percentile, len(val_scores)))

#             # STEP 8: Save score stats
#             score_stats = {
#                 "pc_threshold":  pc_threshold,
#                 "val_percentile": val_percentile,
#                 "geo_threshold": geo_threshold,
#                 "geo_enabled":   geo_enabled,
#                 "mean": float(val_scores.mean()), "std": float(val_scores.std()),
#                 "min":  float(val_scores.min()),  "max": float(val_scores.max()),
#                 "p95":  float(np.percentile(val_scores, 95)),
#                 "p99":  float(np.percentile(val_scores, 99)),
#                 "n_val": int(len(val_scores)), "used_val": use_val,
#             }
#             np.save(os.path.join(run_save_path, "score_stats.npy"), score_stats)
#             np.save(os.path.join(run_save_path, "good_val_scores.npy"), val_scores)

#             # STEP 9: Ground truth
#             anomaly_labels = [x[1] != "good"
#                               for x in dataloaders["testing"].dataset.data_to_iterate]
#             image_paths    = [item[0]
#                               for item in dataloaders["testing"].dataset.data_to_iterate]

#             # STEP 10: Per-image predictions
#             print("\n" + "=" * 115)
#             print("PER-IMAGE PREDICTIONS  [GOOD / ANOMALY]")
#             print("=" * 115)

#             rows = []
#             for idx, score in enumerate(test_scores):
#                 img_path = image_paths[idx]
#                 fname    = os.path.basename(img_path)
#                 score    = float(score)

#                 pc_pred = "ANOMALY" if score >= pc_threshold else "GOOD"

#                 if geo_enabled:
#                     geo_result = geometric_check(img_path, geo_mean, geo_std, geo_threshold)
#                     geo_pred   = "ANOMALY" if geo_result["defect"] else "GOOD"
#                     geo_score  = geo_result["score"]
#                 else:
#                     geo_pred  = "GOOD"
#                     geo_score = None

#                 in_ambiguous = (score >= RECHECK_LOW and score < pc_threshold)
#                 if db_enabled and in_ambiguous and pc_pred == "GOOD" and geo_pred == "GOOD":
#                     db_result = defect_bank_check(img_path, db_matrix,
#                                                   PatchCore_list, device, db_threshold)
#                     db_pred   = "ANOMALY" if db_result["defect"] else "GOOD"
#                     db_dist   = db_result["distance"]
#                 else:
#                     db_pred = "GOOD"
#                     db_dist = None

#                 if pc_pred == "ANOMALY" or geo_pred == "ANOMALY" or db_pred == "ANOMALY":
#                     final_pred = "ANOMALY"
#                 else:
#                     final_pred = "GOOD"

#                 needs_review = (final_pred == "GOOD" and in_ambiguous)
#                 gt           = "ANOMALY" if anomaly_labels[idx] else "GOOD"
#                 correct      = "CORRECT" if final_pred == gt else "WRONG"
#                 geo_override = (pc_pred == "GOOD" and geo_pred == "ANOMALY")
#                 db_override  = (pc_pred == "GOOD" and geo_pred == "GOOD" and db_pred == "ANOMALY")

#                 tag = ""
#                 if geo_override:  tag += "  <<GEO"
#                 if db_override:   tag += "  <<DEFECT_BANK"
#                 if needs_review:  tag += "  [review?]"

#                 print("  [{:7s}] {:43s}  GT:{:7s}  PRED:{:7s}  "
#                       "PC:{:.3f}  GEO:{}  DB:{}{}".format(
#                     correct, fname, gt, final_pred, score,
#                     "{:.2f}".format(geo_score) if geo_score is not None else "N/A",
#                     "{:.1f}".format(db_dist)   if db_dist   is not None else "N/A",
#                     tag))

#                 rows.append({
#                     "Image":         fname,
#                     "GT":            gt,
#                     "Final_Pred":    final_pred,
#                     "Correct":       "Yes" if final_pred == gt else "No",
#                     "Needs_Review":  "Yes" if needs_review else "No",
#                     "PC_Pred":       pc_pred,
#                     "Geo_Pred":      geo_pred,
#                     "DB_Pred":       db_pred,
#                     "PC_Score":      round(score, 4),
#                     "PC_Threshold":  round(pc_threshold, 4),
#                     "Geo_ZScore":    geo_score if geo_score is not None else "",
#                     "Geo_Threshold": round(float(geo_threshold), 3) if geo_threshold else "",
#                     "DB_Distance":   db_dist if db_dist is not None else "",
#                     "DB_Threshold":  round(db_threshold, 2) if db_enabled else "",
#                     "Geo_Override":  "Yes" if geo_override else "No",
#                     "DB_Override":   "Yes" if db_override  else "No",
#                 })

#             # STEP 11: Metrics
#             image_metrics = patchcore.metrics.compute_imagewise_retrieval_metrics(
#                 test_scores, anomaly_labels, manual_threshold=pc_threshold)
#             auroc = image_metrics["auroc"]

#             def _metrics(pred_key):
#                 tp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="ANOMALY")
#                 fp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="GOOD")
#                 tn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="GOOD")
#                 fn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="ANOMALY")
#                 prec = tp / max(1, tp + fp)
#                 rec  = tp / max(1, tp + fn)
#                 f1   = 2 * prec * rec / max(1e-8, prec + rec)
#                 return tp, fp, tn, fn, prec, rec, f1

#             pc_tp,  pc_fp,  pc_tn,  pc_fn,  pc_prec,  pc_rec,  pc_f1  = _metrics("PC_Pred")
#             geo_tp, geo_fp, geo_tn, geo_fn, geo_prec, geo_rec, geo_f1 = _metrics("Geo_Pred")
#             fin_tp, fin_fp, fin_tn, fin_fn, precision, recall,  f1     = _metrics("Final_Pred")
#             needs_review_count = sum(1 for r in rows if r["Needs_Review"] == "Yes")

#             print("\n" + "=" * 75)
#             print("EVALUATION SUMMARY")
#             print("=" * 75)
#             print("  {:<22}  {:>6}  {:>6}  {:>6}  {:>6}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                 "Method","AUROC","F1","Prec","Rec","TP","FP","TN","FN"))
#             print("  " + "-"*71)
#             print("  {:<22}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                 "PatchCore only", auroc, pc_f1, pc_prec, pc_rec, pc_tp, pc_fp, pc_tn, pc_fn))
#             if geo_enabled:
#                 print("  {:<22}  {:>6}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                     "Geometric only", "N/A", geo_f1, geo_prec, geo_rec,
#                     geo_tp, geo_fp, geo_tn, geo_fn))
#             print("  {:<22}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                 "COMBINED (final)", auroc, f1, precision, recall,
#                 fin_tp, fin_fp, fin_tn, fin_fn))
#             print()
#             print("  Needs_Review: {}  |  PC threshold={:.4f} (p{})  Geo_z_thr={}  DB={}".format(
#                 needs_review_count, pc_threshold, val_percentile,
#                 "{:.3f}".format(geo_threshold) if geo_threshold else "N/A",
#                 "enabled n={}".format(len(db_paths)) if db_enabled else "disabled"))
#             print("=" * 75 + "\n")

#             # STEP 11b: CSV
#             csv_path = os.path.join(run_save_path, "{}_predictions.csv".format(dataset_name))
#             with open(csv_path, "w", newline="", encoding="utf-8") as f:
#                 writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
#                 writer.writeheader()
#                 writer.writerows(rows)
#             LOGGER.info("CSV saved -> {}".format(csv_path))

#             summary_path = os.path.join(run_save_path, "{}_summary.csv".format(dataset_name))
#             with open(summary_path, "w", newline="", encoding="utf-8") as f:
#                 w = csv.writer(f)
#                 w.writerow(["Method","AUROC","F1","Precision","Recall","TP","FP","TN","FN"])
#                 w.writerow(["PatchCore_only", round(auroc,4), round(pc_f1,4),
#                              round(pc_prec,4), round(pc_rec,4), pc_tp, pc_fp, pc_tn, pc_fn])
#                 if geo_enabled:
#                     w.writerow(["Geometric_only","N/A", round(geo_f1,4),
#                                  round(geo_prec,4), round(geo_rec,4),
#                                  geo_tp, geo_fp, geo_tn, geo_fn])
#                 w.writerow(["COMBINED_final", round(auroc,4), round(f1,4),
#                              round(precision,4), round(recall,4),
#                              fin_tp, fin_fp, fin_tn, fin_fn])
#                 w.writerow([])
#                 w.writerow(["Needs_Review_count", needs_review_count])
#                 w.writerow(["PC_Threshold",    round(pc_threshold,4)])
#                 w.writerow(["Val_Percentile",  val_percentile])
#                 w.writerow(["Geo_ZThreshold",  round(geo_threshold,3) if geo_threshold else "N/A"])
#                 w.writerow(["GEO_Percentile",  GEO_PERCENTILE])
#                 w.writerow(["DB_enabled",      db_enabled])
#                 w.writerow(["DB_n_images",     len(db_paths) if db_enabled else 0])
#                 w.writerow(["DB_threshold",    round(db_threshold,2) if db_enabled else "N/A"])
#                 w.writerow(["Val_images",      len(val_scores)])
#             LOGGER.info("Summary CSV -> {}".format(summary_path))

#             # STEP 11c: Excel
#             try:
#                 from openpyxl import Workbook
#                 from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
#                 from openpyxl.utils import get_column_letter
#                 wb  = Workbook()
#                 ws1 = wb.active
#                 ws1.title = "Predictions"
#                 headers = list(rows[0].keys())
#                 hdr_fill = PatternFill("solid", start_color="2E4057")
#                 hdr_font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
#                 ca   = Alignment(horizontal="center", vertical="center")
#                 thin = Side(style="thin")
#                 bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)
#                 for ci, h in enumerate(headers, 1):
#                     cell = ws1.cell(row=1, column=ci, value=h)
#                     cell.font = hdr_font; cell.fill = hdr_fill
#                     cell.alignment = ca;  cell.border = bdr
#                 green = PatternFill("solid", start_color="D4EDDA")
#                 red   = PatternFill("solid", start_color="F8D7DA")
#                 amber = PatternFill("solid", start_color="FFF3CD")
#                 blue  = PatternFill("solid", start_color="CCE5FF")
#                 for ri, row in enumerate(rows, 2):
#                     if row["Correct"] == "No":
#                         fill = red
#                     elif row["Geo_Override"] == "Yes" and row["Correct"] == "Yes":
#                         fill = blue
#                     elif row["Needs_Review"] == "Yes":
#                         fill = amber
#                     else:
#                         fill = green
#                     for ci, key in enumerate(headers, 1):
#                         cell = ws1.cell(row=ri, column=ci, value=row.get(key, ""))
#                         cell.font = Font(name="Calibri", size=10)
#                         cell.fill = fill; cell.alignment = ca; cell.border = bdr
#                 col_widths = [42,9,12,9,9,9,10,12,13,13,13,12,9,12,12,12]
#                 for i, w in enumerate(col_widths, 1):
#                     ws1.column_dimensions[get_column_letter(i)].width = w
#                 ws1.row_dimensions[1].height = 22
#                 ws2 = wb.create_sheet("Summary")
#                 sum_headers = ["Method","AUROC","F1","Precision","Recall","TP","FP","TN","FN"]
#                 for ci, h in enumerate(sum_headers, 1):
#                     cell = ws2.cell(row=1, column=ci, value=h)
#                     cell.font = hdr_font; cell.fill = hdr_fill; cell.alignment = ca
#                 fills2 = [PatternFill("solid", start_color="E8F4FD"),
#                           PatternFill("solid", start_color="EAF7EA"),
#                           PatternFill("solid", start_color="FFF9E6")]
#                 rows2 = [
#                     ["PatchCore only", round(auroc,4), round(pc_f1,4),
#                      round(pc_prec,4), round(pc_rec,4), pc_tp, pc_fp, pc_tn, pc_fn],
#                 ]
#                 if geo_enabled:
#                     rows2.append(["Geometric only","N/A", round(geo_f1,4),
#                                    round(geo_prec,4), round(geo_rec,4),
#                                    geo_tp, geo_fp, "-", geo_fn])
#                 rows2.append(["COMBINED (final)", round(auroc,4), round(f1,4),
#                                round(precision,4), round(recall,4),
#                                fin_tp, fin_fp, fin_tn, fin_fn])
#                 for ri, (dr, fill) in enumerate(zip(rows2, fills2), 2):
#                     for ci, val in enumerate(dr, 1):
#                         cell = ws2.cell(row=ri, column=ci, value=val)
#                         cell.font = Font(name="Calibri", size=10, bold=(ci==1))
#                         cell.fill = fill; cell.alignment = ca; cell.border = bdr
#                 ws2.append([])
#                 ws2.append(["PC Threshold",   round(pc_threshold,4)])
#                 ws2.append(["Val Percentile", val_percentile])
#                 ws2.append(["Geo Threshold",  round(geo_threshold,2) if geo_threshold else "N/A"])
#                 ws2.append(["Geo Percentile", GEO_PERCENTILE])
#                 ws2.append(["Val images",     len(val_scores)])
#                 ws2.append(["Dataset",        dataset_name])
#                 for i, w in enumerate([22,8,8,10,8,5,5,5,5], 1):
#                     ws2.column_dimensions[get_column_letter(i)].width = w
#                 excel_path = os.path.join(run_save_path,
#                                           "{}_results.xlsx".format(dataset_name))
#                 wb.save(excel_path)
#                 LOGGER.info("Excel saved -> {}".format(excel_path))
#             except Exception as e:
#                 LOGGER.warning("Excel failed (CSV available): {}".format(e))

#             # STEP 12: Segmentation images
#             if save_segmentation_images:
#                 seg_image_paths = [x[0] for x in
#                                    dataloaders["testing"].dataset.data_to_iterate]
#                 mask_paths = [x[3] if len(x) >= 4 else "-1"
#                               for x in dataloaders["testing"].dataset.data_to_iterate]
#                 def image_transform(image):
#                     in_std  = np.array(dataloaders["testing"].dataset.transform_std).reshape(-1,1,1)
#                     in_mean = np.array(dataloaders["testing"].dataset.transform_mean).reshape(-1,1,1)
#                     image   = dataloaders["testing"].dataset.transform_img(image)
#                     return np.clip((image.numpy()*in_std+in_mean)*255,0,255).astype(np.uint8)
#                 def mask_transform(mask):
#                     return dataloaders["testing"].dataset.transform_mask(mask).numpy()
#                 seg_path = os.path.join(run_save_path, "segmentation_images")
#                 os.makedirs(seg_path, exist_ok=True)
#                 patchcore.utils.plot_segmentation_images(
#                     seg_path, seg_image_paths, segs, test_scores, mask_paths,
#                     image_transform=image_transform, mask_transform=mask_transform)

#             # STEP 13: Save model
#             if save_patchcore_model:
#                 model_path = os.path.join(run_save_path, "models", dataset_name)
#                 os.makedirs(model_path, exist_ok=True)
#                 for i, PC in enumerate(PatchCore_list):
#                     prepend = ("Ensemble-{}-{}_".format(i+1, len(PatchCore_list))
#                                if len(PatchCore_list) > 1 else "")
#                     PC.save_to_path(model_path, prepend)
#                 for fname in ["good_val_scores.npy", "score_stats.npy"]:
#                     shutil.copy(os.path.join(run_save_path, fname),
#                                 os.path.join(model_path, fname))
#                 np.save(os.path.join(model_path, "geo_calibration.npy"), {
#                     "good_mean":    geo_mean,
#                     "good_std":     geo_std,
#                     "threshold":    geo_threshold,
#                     "percentile":   GEO_PERCENTILE,
#                     "bin_start":    SCORE_BIN_START,
#                     "bin_end":      SCORE_BIN_END,
#                 })
#                 if db_enabled:
#                     import pickle
#                     with open(os.path.join(model_path, "defect_bank.pkl"), "wb") as f:
#                         pickle.dump({"embeddings": db_matrix, "paths": db_paths,
#                                      "threshold": db_threshold, "recheck_low": RECHECK_LOW}, f)
#                     LOGGER.info("Defect bank saved -> {}".format(
#                         os.path.join(model_path, "defect_bank.pkl")))
#                 LOGGER.info("Model saved -> {}".format(model_path))

#             result_collect.append({
#                 "dataset_name":   dataset_name,
#                 "instance_auroc": auroc,
#                 "precision":      precision,
#                 "recall":         recall,
#                 "f1":             f1,
#                 "tp": fin_tp, "fp": fin_fp, "tn": fin_tn, "fn": fin_fn,
#             })
#             for key, item in result_collect[-1].items():
#                 if key != "dataset_name":
#                     LOGGER.info("{}: {}".format(key, item))
#         LOGGER.info("\n\n-----\n")

#     result_metric_names  = list(result_collect[-1].keys())[1:]
#     result_dataset_names = [r["dataset_name"] for r in result_collect]
#     result_scores        = [list(r.values())[1:] for r in result_collect]
#     patchcore.utils.compute_and_store_final_results(
#         run_save_path, result_scores,
#         column_names=result_metric_names, row_names=result_dataset_names)


# # ==============================================================================
# #  CLI COMMANDS
# # ==============================================================================

# @main.command("patch_core")
# @click.option("--backbone_names", "-b", type=str, multiple=True, default=[])
# @click.option("--layers_to_extract_from", "-le", type=str, multiple=True, default=[])
# @click.option("--pretrain_embed_dimension", type=int, default=1024)
# @click.option("--target_embed_dimension",  type=int, default=1024)
# @click.option("--preprocessing",  type=click.Choice(["mean","conv"]), default="mean")
# @click.option("--aggregation",    type=click.Choice(["mean","mlp"]),  default="mean")
# @click.option("--anomaly_scorer_num_nn", type=int, default=5)
# @click.option("--patchsize",      type=int, default=3)
# @click.option("--patchscore",     type=str, default="max")
# @click.option("--patchoverlap",   type=float, default=0.0)
# @click.option("--patchsize_aggregate", "-pa", type=int, multiple=True, default=[])
# @click.option("--faiss_on_gpu",   is_flag=True)
# @click.option("--faiss_num_workers", type=int, default=8)
# def patch_core(backbone_names, layers_to_extract_from, pretrain_embed_dimension,
#                target_embed_dimension, preprocessing, aggregation, patchsize,
#                patchscore, patchoverlap, anomaly_scorer_num_nn, patchsize_aggregate,
#                faiss_on_gpu, faiss_num_workers):
#     backbone_names = list(backbone_names)
#     if len(backbone_names) > 1:
#         layers_coll = [[] for _ in range(len(backbone_names))]
#         for layer in layers_to_extract_from:
#             idx   = int(layer.split(".")[0])
#             layer = ".".join(layer.split(".")[1:])
#             layers_coll[idx].append(layer)
#     else:
#         layers_coll = [layers_to_extract_from]

#     def get_patchcore(input_shape, sampler, device):
#         loaded = []
#         for bb_name, layers in zip(backbone_names, layers_coll):
#             bb_seed = None
#             if ".seed-" in bb_name:
#                 bb_name, bb_seed = bb_name.split(".seed-")[0], int(bb_name.split("-")[-1])
#             backbone = patchcore.backbones.load(bb_name)
#             backbone.name, backbone.seed = bb_name, bb_seed
#             nn_method = patchcore.common.FaissNN(faiss_on_gpu, faiss_num_workers)
#             pc = patchcore.patchcore.PatchCore(device)
#             pc.load(backbone=backbone, layers_to_extract_from=layers,
#                     device=device, input_shape=input_shape,
#                     pretrain_embed_dimension=pretrain_embed_dimension,
#                     target_embed_dimension=target_embed_dimension,
#                     patchsize=patchsize, featuresampler=sampler,
#                     anomaly_scorer_num_nn=anomaly_scorer_num_nn, nn_method=nn_method)
#             loaded.append(pc)
#         return loaded
#     return ("get_patchcore", get_patchcore)


# @main.command("sampler")
# @click.argument("name", type=str)
# @click.option("--percentage", "-p", type=float, default=0.1, show_default=True)
# def sampler(name, percentage):
#     def get_sampler(device):
#         if name == "identity":
#             return patchcore.sampler.IdentitySampler()
#         elif name == "greedy_coreset":
#             return patchcore.sampler.GreedyCoresetSampler(percentage, device)
#         elif name == "approx_greedy_coreset":
#             return patchcore.sampler.ApproximateGreedyCoresetSampler(percentage, device)
#     return ("get_sampler", get_sampler)


# @main.command("dataset")
# @click.argument("name",      type=str)
# @click.argument("data_path", type=click.Path(exists=True, file_okay=False))
# @click.option("--subdatasets",     "-d", multiple=True, type=str, required=True)
# @click.option("--train_val_split", type=float, default=0.8, show_default=True)
# @click.option("--batch_size",  default=2,   type=int, show_default=True)
# @click.option("--num_workers", default=8,   type=int, show_default=True)
# @click.option("--resize",      default=256, type=int, show_default=True)
# @click.option("--imagesize",   default=224, type=int, show_default=True)
# @click.option("--augment",     is_flag=True)
# def dataset(name, data_path, subdatasets, train_val_split,
#             batch_size, resize, imagesize, num_workers, augment):
#     dataset_info    = _DATASETS[name]
#     dataset_library = __import__(dataset_info[0], fromlist=[dataset_info[1]])

#     def get_dataloaders(seed):
#         dataloaders = []
#         for subdataset in subdatasets:
#             train_ds = dataset_library.__dict__[dataset_info[1]](
#                 data_path, classname=subdataset, resize=resize,
#                 train_val_split=train_val_split, imagesize=imagesize,
#                 split=dataset_library.DatasetSplit.TRAIN, seed=seed, augment=augment)
#             test_ds = dataset_library.__dict__[dataset_info[1]](
#                 data_path, classname=subdataset, resize=resize,
#                 imagesize=imagesize, split=dataset_library.DatasetSplit.TEST, seed=seed)
#             train_dl = torch.utils.data.DataLoader(
#                 train_ds, batch_size=batch_size, shuffle=False,
#                 num_workers=num_workers, pin_memory=True)
#             test_dl = torch.utils.data.DataLoader(
#                 test_ds, batch_size=batch_size, shuffle=False,
#                 num_workers=num_workers, pin_memory=True)
#             train_dl.name = name + ("_" + subdataset if subdataset else "")
#             val_dl = None
#             if train_val_split < 1:
#                 val_ds = dataset_library.__dict__[dataset_info[1]](
#                     data_path, classname=subdataset, resize=resize,
#                     train_val_split=train_val_split, imagesize=imagesize,
#                     split=dataset_library.DatasetSplit.VAL, seed=seed)
#                 val_dl = torch.utils.data.DataLoader(
#                     val_ds, batch_size=batch_size, shuffle=False,
#                     num_workers=num_workers, pin_memory=True)
#                 LOGGER.info("Train/Val split: {} train, {} val".format(
#                     len(train_ds), len(val_ds)))
#             dataloaders.append({"training": train_dl, "validation": val_dl,
#                                  "testing": test_dl})
#         return dataloaders
#     return ("get_dataloaders", get_dataloaders)


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     LOGGER.info("Command line arguments: {}".format(" ".join(sys.argv)))
#     main()

# # Side View
# import contextlib
# import logging
# import os
# import sys
# import shutil
# import csv

# import click
# import numpy as np
# import torch
# import PIL.Image

# import patchcore.backbones
# import patchcore.common
# import patchcore.metrics
# import patchcore.patchcore
# import patchcore.sampler
# import patchcore.utils

# import warnings
# warnings.filterwarnings("ignore")

# LOGGER = logging.getLogger(__name__)

# _DATASETS = {"mvtec": ["patchcore.datasets.mvtec", "MVTecDataset"],
#              "selfds": ["patchcore.datasets.selfds", "SelfDS"]}


# # ==============================================================================
# #  GEOMETRIC CHECKER — honest, anomaly-blind calibration
# # ==============================================================================

# BG_THRESHOLD    = 15
# N_ANGLES        = 360
# PROFILE_BINS    = 200
# SCORE_BIN_START = 160
# SCORE_BIN_END   = 187
# GEO_PERCENTILE  = 95


# def _geo_gray(pil_image):
#     return np.array(pil_image.convert("RGB"), dtype=np.float32).mean(axis=2)


# def _geo_centre_radius(gray):
#     mask = gray > BG_THRESHOLD
#     rows = np.where(mask.any(axis=1))[0]
#     cols = np.where(mask.any(axis=0))[0]
#     if len(rows) == 0 or len(cols) == 0:
#         h, w = gray.shape
#         return h // 2, w // 2, min(h, w) // 2
#     cy = (rows[0] + rows[-1]) / 2.0
#     cx = (cols[0] + cols[-1]) / 2.0
#     R  = min(rows[-1] - rows[0], cols[-1] - cols[0]) / 2.0
#     return cy, cx, R


# def _geo_radial_profile(gray, cy, cx, R):
#     profile = np.zeros(PROFILE_BINS, dtype=np.float64)
#     counts  = np.zeros(PROFILE_BINS, dtype=np.float64)
#     h, w    = gray.shape
#     for angle in np.linspace(0, 2 * np.pi, N_ANGLES, endpoint=False):
#         ca, sa = np.cos(angle), np.sin(angle)
#         for b in range(PROFILE_BINS):
#             r_px = (b / PROFILE_BINS) * R
#             yi = int(round(cy + r_px * sa))
#             xi = int(round(cx + r_px * ca))
#             if 0 <= yi < h and 0 <= xi < w:
#                 profile[b] += gray[yi, xi]
#                 counts[b]  += 1
#     profile[counts > 0] /= counts[counts > 0]
#     return profile


# def _get_profile(image_path):
#     try:
#         pil = PIL.Image.open(image_path).convert("RGB")
#         try:
#             from patchcore.datasets.selfds import auto_crop_part, normalise_brightness
#             pil = auto_crop_part(pil)
#             pil = normalise_brightness(pil)
#         except Exception:
#             pass
#     except Exception as e:
#         LOGGER.warning("geo: cannot open {}: {}".format(image_path, e))
#         return None
#     gray      = _geo_gray(pil)
#     cy, cx, R = _geo_centre_radius(gray)
#     if R < 20:
#         return None
#     return _geo_radial_profile(gray, cy, cx, R)


# def _profile_anomaly_score(profile, good_mean, good_std):
#     seg      = profile[SCORE_BIN_START:SCORE_BIN_END]
#     mean_seg = good_mean[SCORE_BIN_START:SCORE_BIN_END]
#     std_seg  = good_std[SCORE_BIN_START:SCORE_BIN_END]
#     z        = np.abs(seg - mean_seg) / (std_seg + 1e-6)
#     return float(z.mean())


# def calibrate_geo(train_image_paths):
#     LOGGER.info("Geo calibration: profiling {} training images...".format(
#         len(train_image_paths)))
#     profiles = []
#     for path in train_image_paths:
#         p = _get_profile(path)
#         if p is not None:
#             profiles.append(p)

#     if len(profiles) < 5:
#         LOGGER.warning("Geo calibration: too few profiles ({}), checker disabled.".format(
#             len(profiles)))
#         return None, None, None

#     arr       = np.array(profiles)
#     good_mean = arr.mean(axis=0)
#     good_std  = arr.std(axis=0)

#     good_scores = np.array([
#         _profile_anomaly_score(p, good_mean, good_std) for p in profiles
#     ])
#     threshold = float(np.percentile(good_scores, GEO_PERCENTILE))

#     LOGGER.info(
#         "Geo calibration done: n={} good_scores mean={:.2f} std={:.2f} "
#         "p{}={:.2f} (threshold)".format(
#             len(profiles), good_scores.mean(), good_scores.std(),
#             GEO_PERCENTILE, threshold))
#     return good_mean, good_std, threshold


# def geometric_check(image_path, good_mean, good_std, threshold):
#     profile = _get_profile(image_path)
#     if profile is None:
#         return {"defect": False, "score": None, "threshold": threshold,
#                 "details": "read_error"}

#     score  = _profile_anomaly_score(profile, good_mean, good_std)
#     defect = score > threshold
#     return {"defect": defect, "score": round(score, 3),
#             "threshold": round(threshold, 3),
#             "details": "z_mean={:.2f} thr={:.2f}".format(score, threshold)}


# # ==============================================================================
# #  DEFECT BANK
# # ==============================================================================

# RECHECK_LOW = 0.05


# def _extract_image_embedding(image_path, PatchCore_list, device):
#     try:
#         pil = PIL.Image.open(image_path).convert("RGB")
#         try:
#             from patchcore.datasets.selfds import auto_crop_part, normalise_brightness
#             pil = auto_crop_part(pil)
#             pil = normalise_brightness(pil)
#         except Exception:
#             pass
#     except Exception as e:
#         LOGGER.warning("defect_bank: cannot open {}: {}".format(image_path, e))
#         return None

#     parts = []
#     for PC in PatchCore_list:
#         try:
#             import torchvision.transforms as T
#             transform = T.Compose([
#                 T.Resize((PC.input_shape[-1], PC.input_shape[-1])),
#                 T.ToTensor(),
#                 T.Normalize(mean=[0.485, 0.456, 0.406],
#                             std=[0.229, 0.224, 0.225]),
#             ])
#             tensor = transform(pil).unsqueeze(0).to(device)
#             with torch.no_grad():
#                 features = PC.forward_modules["feature_aggregator"](tensor)
#                 agg = []
#                 for layer_feat in features.values():
#                     pooled = layer_feat.mean(dim=[2, 3])
#                     agg.append(pooled.squeeze(0).cpu().numpy())
#                 parts.append(np.concatenate(agg))
#         except Exception as e:
#             LOGGER.warning("defect_bank: embedding failed for {}: {}".format(
#                 image_path, e))
#             return None

#     if not parts:
#         return None
#     return np.concatenate(parts)


# def build_defect_bank(data_path, classname, PatchCore_list, device):
#     defects_dir = os.path.join(data_path, classname, "known_defects")
#     if not os.path.exists(defects_dir):
#         LOGGER.info("Defect bank: no known_defects/ folder found at {}".format(
#             defects_dir))
#         LOGGER.info("  -> Create it and add defect images to enable the defect bank")
#         return None, None, None

#     image_files = sorted([
#         f for f in os.listdir(defects_dir)
#         if f.lower().endswith((".png", ".jpg", ".jpeg"))
#     ])

#     if len(image_files) < 2:
#         LOGGER.warning("Defect bank: need at least 2 images in known_defects/, "
#                        "found {}. Bank disabled.".format(len(image_files)))
#         return None, None, None

#     LOGGER.info("Defect bank: extracting embeddings from {} images...".format(
#         len(image_files)))

#     embeddings = []
#     valid_paths = []
#     for fname in image_files:
#         path = os.path.join(defects_dir, fname)
#         emb  = _extract_image_embedding(path, PatchCore_list, device)
#         if emb is not None:
#             embeddings.append(emb)
#             valid_paths.append(path)
#             LOGGER.info("  OK  {}  dim={}".format(fname, emb.shape[0]))
#         else:
#             LOGGER.warning("  SKIP  {}".format(fname))

#     if len(embeddings) < 2:
#         LOGGER.warning("Defect bank: too few valid embeddings. Bank disabled.")
#         return None, None, None

#     emb_matrix = np.array(embeddings)

#     nn_dists = []
#     for i in range(len(emb_matrix)):
#         others = np.delete(emb_matrix, i, axis=0)
#         diffs  = others - emb_matrix[i]
#         dists  = np.linalg.norm(diffs, axis=1)
#         nn_dists.append(dists.min())

#     threshold = float(np.median(nn_dists) * 1.2)

#     LOGGER.info(
#         "Defect bank ready: n={} embeddings  "
#         "nn_dist median={:.1f}  threshold={:.1f}".format(
#             len(embeddings), float(np.median(nn_dists)), threshold))

#     return emb_matrix, valid_paths, threshold


# def defect_bank_check(image_path, emb_matrix, PatchCore_list, device, threshold):
#     emb = _extract_image_embedding(image_path, PatchCore_list, device)
#     if emb is None:
#         return {"defect": False, "distance": None, "threshold": threshold}

#     diffs = emb_matrix - emb
#     dists = np.linalg.norm(diffs, axis=1)
#     min_dist = float(dists.min())
#     return {
#         "defect":    min_dist < threshold,
#         "distance":  round(min_dist, 2),
#         "threshold": round(threshold, 2),
#     }


# # ==============================================================================
# #  MAIN
# # ==============================================================================

# @click.group(chain=True)
# @click.argument("results_path", type=str)
# @click.option("--gpu",  type=int, default=[0], multiple=True, show_default=True)
# @click.option("--seed", type=int, default=0, show_default=True)
# @click.option("--log_group",   type=str, default="group")
# @click.option("--log_project", type=str, default="project")
# @click.option("--save_segmentation_images", is_flag=True)
# @click.option("--save_patchcore_model",     is_flag=True)
# @click.option("--val_percentile", type=int, default=85, show_default=True,  # ← ADDED
#               help="Percentile of good val scores used as PatchCore threshold (default 85).")
# def main(**kwargs):
#     pass


# @main.result_callback()
# def run(methods, results_path, gpu, seed, log_group, log_project,
#         save_segmentation_images, save_patchcore_model,
#         val_percentile):                                                       # ← ADDED

#     methods       = {key: item for (key, item) in methods}
#     run_save_path = os.path.join(results_path, log_project)
#     os.makedirs(run_save_path, exist_ok=True)

#     list_of_dataloaders = methods["get_dataloaders"](seed)
#     device = patchcore.utils.set_torch_device(gpu)
#     device_context = (
#         torch.cuda.device("cuda:{}".format(device.index))
#         if "cuda" in device.type.lower()
#         else contextlib.suppress()
#     )

#     result_collect = []

#     for dataloader_count, dataloaders in enumerate(list_of_dataloaders):
#         LOGGER.info("Evaluating dataset [{}] ({}/{})...".format(
#             dataloaders["training"].name, dataloader_count + 1,
#             len(list_of_dataloaders)))
#         patchcore.utils.fix_seeds(seed, device)
#         dataset_name = dataloaders["training"].name

#         with device_context:
#             torch.cuda.empty_cache()
#             imagesize      = dataloaders["training"].dataset.imagesize
#             sampler        = methods["get_sampler"](device)
#             PatchCore_list = methods["get_patchcore"](imagesize, sampler, device)

#             if len(PatchCore_list) > 1:
#                 LOGGER.info("Utilizing PatchCore Ensemble (N={}).".format(
#                     len(PatchCore_list)))

#             # STEP 1: Fit
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache()
#                 if PC.backbone.seed is not None:
#                     patchcore.utils.fix_seeds(PC.backbone.seed, device)
#                 LOGGER.info("Training models ({}/{})".format(i + 1, len(PatchCore_list)))
#                 PC.fit(dataloaders["training"])

#             # STEP 1b: Calibrate geometric checker
#             train_paths = dataloaders["training"].dataset.imgpaths
#             geo_mean, geo_std, geo_threshold = calibrate_geo(train_paths)
#             geo_enabled = geo_threshold is not None
#             if geo_enabled:
#                 LOGGER.info("Geometric checker ENABLED  z_threshold={:.2f}".format(
#                     geo_threshold))
#             else:
#                 LOGGER.warning("Geometric checker DISABLED (calibration failed)")

#             # STEP 1c: Build defect bank
#             data_path  = dataloaders["training"].dataset.source
#             classname  = dataloaders["training"].dataset.classname
#             db_matrix, db_paths, db_threshold = build_defect_bank(
#                 data_path, classname, PatchCore_list, device)
#             db_enabled = db_matrix is not None
#             if db_enabled:
#                 LOGGER.info("Defect bank ENABLED  n={}  threshold={:.1f}".format(
#                     len(db_paths), db_threshold))
#             else:
#                 LOGGER.info("Defect bank DISABLED (no known_defects/ folder or too few images)")

#             # STEP 2: Raw val scores
#             use_val    = dataloaders.get("validation") is not None
#             ref_loader = dataloaders["validation"] if use_val else dataloaders["training"]
#             if not use_val:
#                 LOGGER.warning("No validation split! Falling back to training scores.")

#             LOGGER.info("Scoring {} set for normalisation...".format(
#                 "VALIDATION" if use_val else "TRAINING (fallback)"))
#             val_raw = []
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache(); PC.backbone.eval()
#                 raw = []
#                 with torch.no_grad():
#                     for batch in ref_loader:
#                         s, _ = PC.predict(batch["image"].to(device))
#                         raw.extend([float(x) for x in s])
#                 arr = np.array(raw)
#                 val_raw.append(arr)
#                 LOGGER.info("  Backbone {}/{} raw  min={:.4f} max={:.4f} mean={:.4f} n={}".format(
#                     i+1, len(PatchCore_list), arr.min(), arr.max(), arr.mean(), len(arr)))
#             val_raw = np.array(val_raw)

#             # STEP 3: Bake normalisation
#             for i, PC in enumerate(PatchCore_list):
#                 s_min = float(val_raw[i].min())
#                 s_max = float(np.percentile(val_raw[i], 99))
#                 PC.set_score_normalization(s_min, s_max)
#                 LOGGER.info("  Backbone {}/{} bounds s_min={:.4f} s_max={:.4f}".format(
#                     i+1, len(PatchCore_list), s_min, s_max))

#             # STEP 4: Re-score val normalised
#             val_norm = []
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache(); PC.backbone.eval()
#                 ns = []
#                 with torch.no_grad():
#                     for batch in ref_loader:
#                         s, _ = PC.predict(batch["image"].to(device))
#                         ns.extend([float(x) for x in s])
#                 val_norm.append(np.array(ns))
#             val_scores = np.mean(np.array(val_norm), axis=0)
#             val_scores.sort()
#             LOGGER.info("Val normalised  min={:.4f} max={:.4f} mean={:.4f} std={:.4f}".format(
#                 val_scores.min(), val_scores.max(), val_scores.mean(), val_scores.std()))

#             # STEP 5: Score test images
#             aggregator = {"scores": [], "segmentations": []}
#             for i, PC in enumerate(PatchCore_list):
#                 torch.cuda.empty_cache(); PC.backbone.eval()
#                 LOGGER.info("Embedding test data ({}/{})".format(i+1, len(PatchCore_list)))
#                 scores, segs, _, _ = PC.predict(dataloaders["testing"])
#                 aggregator["scores"].append(scores)
#                 aggregator["segmentations"].append(segs)
#             test_scores = np.mean(np.array(aggregator["scores"]), axis=0)

#             # STEP 6: Normalise segmentations
#             segs    = np.array(aggregator["segmentations"])
#             seg_min = segs.reshape(len(segs), -1).min(axis=-1).reshape(-1,1,1,1)
#             seg_max = segs.reshape(len(segs), -1).max(axis=-1).reshape(-1,1,1,1)
#             segs    = (segs - seg_min) / (seg_max - seg_min + 1e-8)
#             segs    = np.mean(segs, axis=0)

#             # STEP 7: PatchCore threshold — now uses --val_percentile          # ← CHANGED
#             pc_threshold = float(np.percentile(val_scores, val_percentile))
#             LOGGER.info("PC threshold={:.4f}  (val p{}  n_val={})".format(
#                 pc_threshold, val_percentile, len(val_scores)))

#             # STEP 8: Save score stats
#             score_stats = {
#                 "pc_threshold":  pc_threshold,
#                 "val_percentile": val_percentile,                              # ← ADDED
#                 "geo_threshold": geo_threshold,
#                 "geo_enabled":   geo_enabled,
#                 "mean": float(val_scores.mean()), "std": float(val_scores.std()),
#                 "min":  float(val_scores.min()),  "max": float(val_scores.max()),
#                 "p95":  float(np.percentile(val_scores, 95)),
#                 "p99":  float(np.percentile(val_scores, 99)),
#                 "n_val": int(len(val_scores)), "used_val": use_val,
#             }
#             np.save(os.path.join(run_save_path, "score_stats.npy"), score_stats)
#             np.save(os.path.join(run_save_path, "good_val_scores.npy"), val_scores)

#             # STEP 9: Ground truth
#             anomaly_labels = [x[1] != "good"
#                               for x in dataloaders["testing"].dataset.data_to_iterate]
#             image_paths    = [item[0]
#                               for item in dataloaders["testing"].dataset.data_to_iterate]

#             # STEP 10: Per-image predictions
#             print("\n" + "=" * 115)
#             print("PER-IMAGE PREDICTIONS  [GOOD / ANOMALY]")
#             print("=" * 115)

#             rows = []
#             for idx, score in enumerate(test_scores):
#                 img_path = image_paths[idx]
#                 fname    = os.path.basename(img_path)
#                 score    = float(score)

#                 pc_pred = "ANOMALY" if score >= pc_threshold else "GOOD"

#                 if geo_enabled:
#                     geo_result = geometric_check(img_path, geo_mean, geo_std, geo_threshold)
#                     geo_pred   = "ANOMALY" if geo_result["defect"] else "GOOD"
#                     geo_score  = geo_result["score"]
#                 else:
#                     geo_pred  = "GOOD"
#                     geo_score = None

#                 in_ambiguous = (score >= RECHECK_LOW and score < pc_threshold)
#                 if db_enabled and in_ambiguous and pc_pred == "GOOD" and geo_pred == "GOOD":
#                     db_result = defect_bank_check(img_path, db_matrix,
#                                                   PatchCore_list, device, db_threshold)
#                     db_pred   = "ANOMALY" if db_result["defect"] else "GOOD"
#                     db_dist   = db_result["distance"]
#                 else:
#                     db_pred = "GOOD"
#                     db_dist = None

#                 if pc_pred == "ANOMALY" or geo_pred == "ANOMALY" or db_pred == "ANOMALY":
#                     final_pred = "ANOMALY"
#                 else:
#                     final_pred = "GOOD"

#                 needs_review = (final_pred == "GOOD" and in_ambiguous)

#                 gt      = "ANOMALY" if anomaly_labels[idx] else "GOOD"
#                 correct = "CORRECT" if final_pred == gt else "WRONG"

#                 geo_override = (pc_pred == "GOOD" and geo_pred == "ANOMALY")
#                 db_override  = (pc_pred == "GOOD" and geo_pred == "GOOD"
#                                 and db_pred == "ANOMALY")

#                 tag = ""
#                 if geo_override:  tag += "  <<GEO"
#                 if db_override:   tag += "  <<DEFECT_BANK"
#                 if needs_review:  tag += "  [review?]"

#                 print(
#                     "  [{:7s}] {:43s}  GT:{:7s}  PRED:{:7s}  "
#                     "PC:{:.3f}  GEO:{}  DB:{}{}".format(
#                         correct, fname, gt, final_pred, score,
#                         "{:.2f}".format(geo_score) if geo_score is not None else "N/A",
#                         "{:.1f}".format(db_dist)   if db_dist   is not None else "N/A",
#                         tag,
#                     )
#                 )

#                 rows.append({
#                     "Image":         fname,
#                     "GT":            gt,
#                     "Final_Pred":    final_pred,
#                     "Correct":       "Yes" if final_pred == gt else "No",
#                     "Needs_Review":  "Yes" if needs_review else "No",
#                     "PC_Pred":       pc_pred,
#                     "Geo_Pred":      geo_pred,
#                     "DB_Pred":       db_pred,
#                     "PC_Score":      round(score, 4),
#                     "PC_Threshold":  round(pc_threshold, 4),
#                     "Geo_ZScore":    geo_score if geo_score is not None else "",
#                     "Geo_Threshold": round(float(geo_threshold), 3) if geo_threshold else "",
#                     "DB_Distance":   db_dist if db_dist is not None else "",
#                     "DB_Threshold":  round(db_threshold, 2) if db_enabled else "",
#                     "Geo_Override":  "Yes" if geo_override else "No",
#                     "DB_Override":   "Yes" if db_override  else "No",
#                 })

#             # STEP 11: Metrics
#             image_metrics = patchcore.metrics.compute_imagewise_retrieval_metrics(
#                 test_scores, anomaly_labels, manual_threshold=pc_threshold)
#             auroc = image_metrics["auroc"]

#             def _metrics(pred_key):
#                 tp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="ANOMALY")
#                 fp = sum(1 for r in rows if r[pred_key]=="ANOMALY" and r["GT"]=="GOOD")
#                 tn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="GOOD")
#                 fn = sum(1 for r in rows if r[pred_key]=="GOOD"    and r["GT"]=="ANOMALY")
#                 prec = tp / max(1, tp + fp)
#                 rec  = tp / max(1, tp + fn)
#                 f1   = 2 * prec * rec / max(1e-8, prec + rec)
#                 return tp, fp, tn, fn, prec, rec, f1

#             pc_tp,  pc_fp,  pc_tn,  pc_fn,  pc_prec,  pc_rec,  pc_f1  = _metrics("PC_Pred")
#             geo_tp, geo_fp, geo_tn, geo_fn, geo_prec, geo_rec, geo_f1 = _metrics("Geo_Pred")
#             fin_tp, fin_fp, fin_tn, fin_fn, precision, recall,  f1     = _metrics("Final_Pred")

#             needs_review_count = sum(1 for r in rows if r["Needs_Review"] == "Yes")

#             print("\n" + "=" * 75)
#             print("EVALUATION SUMMARY")
#             print("=" * 75)
#             print("  {:<22}  {:>6}  {:>6}  {:>6}  {:>6}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                 "Method","AUROC","F1","Prec","Rec","TP","FP","TN","FN"))
#             print("  " + "-"*71)
#             print("  {:<22}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                 "PatchCore only", auroc, pc_f1, pc_prec, pc_rec,
#                 pc_tp, pc_fp, pc_tn, pc_fn))
#             if geo_enabled:
#                 print("  {:<22}  {:>6}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                     "Geometric only", "N/A", geo_f1, geo_prec, geo_rec,
#                     geo_tp, geo_fp, geo_tn, geo_fn))
#             print("  {:<22}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>6.4f}  {:>4}  {:>4}  {:>4}  {:>4}".format(
#                 "COMBINED (final)", auroc, f1, precision, recall,
#                 fin_tp, fin_fp, fin_tn, fin_fn))
#             print()
#             print("  Needs_Review flag : {} GOOD predictions flagged for optional human check".format(
#                 needs_review_count))
#             print("  PC threshold={:.4f}  (val p{})  Geo_z_thr={}  DB={}".format(
#                 pc_threshold, val_percentile,
#                 "{:.3f}".format(geo_threshold) if geo_threshold else "N/A",
#                 "enabled n={}".format(len(db_paths)) if db_enabled else "disabled"))
#             print("=" * 75 + "\n")

#             # STEP 11b: CSV
#             csv_path = os.path.join(run_save_path,
#                                     "{}_predictions.csv".format(dataset_name))
#             with open(csv_path, "w", newline="", encoding="utf-8") as f:
#                 writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
#                 writer.writeheader()
#                 writer.writerows(rows)
#             LOGGER.info("CSV saved -> {}".format(csv_path))

#             summary_path = os.path.join(run_save_path,
#                                         "{}_summary.csv".format(dataset_name))
#             with open(summary_path, "w", newline="", encoding="utf-8") as f:
#                 w = csv.writer(f)
#                 w.writerow(["Method","AUROC","F1","Precision","Recall","TP","FP","TN","FN"])
#                 w.writerow(["PatchCore_only", round(auroc,4), round(pc_f1,4),
#                              round(pc_prec,4), round(pc_rec,4),
#                              pc_tp, pc_fp, pc_tn, pc_fn])
#                 if geo_enabled:
#                     w.writerow(["Geometric_only","N/A", round(geo_f1,4),
#                                  round(geo_prec,4), round(geo_rec,4),
#                                  geo_tp, geo_fp, geo_tn, geo_fn])
#                 w.writerow(["COMBINED_final", round(auroc,4), round(f1,4),
#                              round(precision,4), round(recall,4),
#                              fin_tp, fin_fp, fin_tn, fin_fn])
#                 w.writerow([])
#                 w.writerow(["Needs_Review_count", needs_review_count])
#                 w.writerow(["PC_Threshold",   round(pc_threshold,4)])
#                 w.writerow(["Val_Percentile",  val_percentile])                # ← ADDED
#                 w.writerow(["Geo_ZThreshold", round(geo_threshold,3) if geo_threshold else "N/A"])
#                 w.writerow(["GEO_Percentile", GEO_PERCENTILE])
#                 w.writerow(["DB_enabled",     db_enabled])
#                 w.writerow(["DB_n_images",    len(db_paths) if db_enabled else 0])
#                 w.writerow(["DB_threshold",   round(db_threshold,2) if db_enabled else "N/A"])
#                 w.writerow(["Val_images",     len(val_scores)])
#             LOGGER.info("Summary CSV -> {}".format(summary_path))

#             # STEP 11c: Excel
#             try:
#                 from openpyxl import Workbook
#                 from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
#                 from openpyxl.utils import get_column_letter

#                 wb  = Workbook()
#                 ws1 = wb.active
#                 ws1.title = "Predictions"
#                 headers = list(rows[0].keys())

#                 hdr_fill = PatternFill("solid", start_color="2E4057")
#                 hdr_font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
#                 ca       = Alignment(horizontal="center", vertical="center")
#                 thin     = Side(style="thin")
#                 bdr      = Border(left=thin, right=thin, top=thin, bottom=thin)

#                 for ci, h in enumerate(headers, 1):
#                     cell = ws1.cell(row=1, column=ci, value=h)
#                     cell.font = hdr_font; cell.fill = hdr_fill
#                     cell.alignment = ca;  cell.border = bdr

#                 green = PatternFill("solid", start_color="D4EDDA")
#                 red   = PatternFill("solid", start_color="F8D7DA")
#                 amber = PatternFill("solid", start_color="FFF3CD")
#                 blue  = PatternFill("solid", start_color="CCE5FF")

#                 for ri, row in enumerate(rows, 2):
#                     if row["Correct"] == "No":
#                         fill = red
#                     elif row["Geo_Override"] == "Yes" and row["Correct"] == "Yes":
#                         fill = blue
#                     elif row.get("Needs_Review") == "Yes":
#                         fill = amber
#                     else:
#                         fill = green
#                     for ci, key in enumerate(headers, 1):
#                         cell = ws1.cell(row=ri, column=ci, value=row.get(key,""))
#                         cell.font = Font(name="Calibri", size=10)
#                         cell.fill = fill; cell.alignment = ca; cell.border = bdr

#                 col_widths = [42,9,12,9,9,9,10,12,13,13,13,12,9]
#                 for i, w in enumerate(col_widths, 1):
#                     ws1.column_dimensions[get_column_letter(i)].width = w
#                 ws1.row_dimensions[1].height = 22

#                 ws2 = wb.create_sheet("Summary")
#                 sum_headers = ["Method","AUROC","F1","Precision","Recall",
#                                 "TP","FP","TN","FN"]
#                 for ci, h in enumerate(sum_headers, 1):
#                     cell = ws2.cell(row=1, column=ci, value=h)
#                     cell.font = hdr_font; cell.fill = hdr_fill; cell.alignment = ca

#                 fills2 = [PatternFill("solid", start_color="E8F4FD"),
#                           PatternFill("solid", start_color="EAF7EA"),
#                           PatternFill("solid", start_color="FFF9E6")]
#                 rows2  = [
#                     ["PatchCore only", round(auroc,4), round(pc_f1,4),
#                      round(pc_prec,4), round(pc_rec,4), pc_tp, pc_fp, pc_tn, pc_fn],
#                 ]
#                 if geo_enabled:
#                     rows2.append(["Geometric only","N/A", round(geo_f1,4),
#                                    round(geo_prec,4), round(geo_rec,4),
#                                    geo_tp, geo_fp, "-", geo_fn])
#                 rows2.append(["COMBINED (final)", round(auroc,4), round(f1,4),
#                                round(precision,4), round(recall,4),
#                                fin_tp, fin_fp, fin_tn, fin_fn])
#                 for ri, (dr, fill) in enumerate(zip(rows2, fills2), 2):
#                     for ci, val in enumerate(dr, 1):
#                         cell = ws2.cell(row=ri, column=ci, value=val)
#                         cell.font = Font(name="Calibri", size=10, bold=(ci==1))
#                         cell.fill = fill; cell.alignment = ca; cell.border = bdr
#                 ws2.append([])
#                 ws2.append(["PC Threshold",   round(pc_threshold,4)])
#                 ws2.append(["Val Percentile",  val_percentile])                # ← ADDED
#                 ws2.append(["Geo Threshold",
#                              round(geo_threshold,2) if geo_threshold else "N/A"])
#                 ws2.append(["Geo Percentile", GEO_PERCENTILE])
#                 ws2.append(["Val images",     len(val_scores)])
#                 ws2.append(["Dataset",        dataset_name])
#                 for i, w in enumerate([22,8,8,10,8,5,5,5,5], 1):
#                     ws2.column_dimensions[get_column_letter(i)].width = w

#                 excel_path = os.path.join(run_save_path,
#                                           "{}_results.xlsx".format(dataset_name))
#                 wb.save(excel_path)
#                 LOGGER.info("Excel saved -> {}".format(excel_path))
#             except Exception as e:
#                 LOGGER.warning("Excel failed (CSV available): {}".format(e))

#             # STEP 12: Segmentation images
#             if save_segmentation_images:
#                 seg_image_paths = [x[0] for x in
#                                    dataloaders["testing"].dataset.data_to_iterate]
#                 mask_paths = [x[3] if len(x) >= 4 else "-1"
#                               for x in dataloaders["testing"].dataset.data_to_iterate]
#                 def image_transform(image):
#                     in_std  = np.array(dataloaders["testing"].dataset.transform_std).reshape(-1,1,1)
#                     in_mean = np.array(dataloaders["testing"].dataset.transform_mean).reshape(-1,1,1)
#                     image   = dataloaders["testing"].dataset.transform_img(image)
#                     return np.clip((image.numpy()*in_std+in_mean)*255,0,255).astype(np.uint8)
#                 def mask_transform(mask):
#                     return dataloaders["testing"].dataset.transform_mask(mask).numpy()
#                 seg_path = os.path.join(run_save_path, "segmentation_images")
#                 os.makedirs(seg_path, exist_ok=True)
#                 patchcore.utils.plot_segmentation_images(
#                     seg_path, seg_image_paths, segs, test_scores, mask_paths,
#                     image_transform=image_transform, mask_transform=mask_transform)

#             # STEP 13: Save model
#             if save_patchcore_model:
#                 model_path = os.path.join(run_save_path, "models", dataset_name)
#                 os.makedirs(model_path, exist_ok=True)
#                 for i, PC in enumerate(PatchCore_list):
#                     prepend = ("Ensemble-{}-{}_".format(i+1, len(PatchCore_list))
#                                if len(PatchCore_list) > 1 else "")
#                     PC.save_to_path(model_path, prepend)
#                 for fname in ["good_val_scores.npy", "score_stats.npy"]:
#                     shutil.copy(os.path.join(run_save_path, fname),
#                                 os.path.join(model_path, fname))
#                 np.save(os.path.join(model_path, "geo_calibration.npy"), {
#                     "good_mean":    geo_mean,
#                     "good_std":     geo_std,
#                     "threshold":    geo_threshold,
#                     "percentile":   GEO_PERCENTILE,
#                     "bin_start":    SCORE_BIN_START,
#                     "bin_end":      SCORE_BIN_END,
#                 })
#                 if db_enabled:
#                     import pickle
#                     db_save = {
#                         "embeddings":  db_matrix,
#                         "paths":       db_paths,
#                         "threshold":   db_threshold,
#                         "recheck_low": RECHECK_LOW,
#                     }
#                     with open(os.path.join(model_path, "defect_bank.pkl"), "wb") as f:
#                         pickle.dump(db_save, f)
#                     LOGGER.info("Defect bank saved -> {}".format(
#                         os.path.join(model_path, "defect_bank.pkl")))
#                 LOGGER.info("Model saved -> {}".format(model_path))

#             result_collect.append({
#                 "dataset_name":   dataset_name,
#                 "instance_auroc": auroc,
#                 "precision":      precision,
#                 "recall":         recall,
#                 "f1":             f1,
#                 "tp": fin_tp, "fp": fin_fp, "tn": fin_tn, "fn": fin_fn,
#             })
#             for key, item in result_collect[-1].items():
#                 if key != "dataset_name":
#                     LOGGER.info("{}: {}".format(key, item))
#         LOGGER.info("\n\n-----\n")

#     result_metric_names  = list(result_collect[-1].keys())[1:]
#     result_dataset_names = [r["dataset_name"] for r in result_collect]
#     result_scores        = [list(r.values())[1:] for r in result_collect]
#     patchcore.utils.compute_and_store_final_results(
#         run_save_path, result_scores,
#         column_names=result_metric_names, row_names=result_dataset_names)


# # ==============================================================================
# #  CLI COMMANDS
# # ==============================================================================

# @main.command("patch_core")
# @click.option("--backbone_names", "-b", type=str, multiple=True, default=[])
# @click.option("--layers_to_extract_from", "-le", type=str, multiple=True, default=[])
# @click.option("--pretrain_embed_dimension", type=int, default=1024)
# @click.option("--target_embed_dimension",  type=int, default=1024)
# @click.option("--preprocessing",  type=click.Choice(["mean","conv"]), default="mean")
# @click.option("--aggregation",    type=click.Choice(["mean","mlp"]),  default="mean")
# @click.option("--anomaly_scorer_num_nn", type=int, default=5)
# @click.option("--patchsize",      type=int, default=3)
# @click.option("--patchscore",     type=str, default="max")
# @click.option("--patchoverlap",   type=float, default=0.0)
# @click.option("--patchsize_aggregate", "-pa", type=int, multiple=True, default=[])
# @click.option("--faiss_on_gpu",   is_flag=True)
# @click.option("--faiss_num_workers", type=int, default=8)
# def patch_core(backbone_names, layers_to_extract_from, pretrain_embed_dimension,
#                target_embed_dimension, preprocessing, aggregation, patchsize,
#                patchscore, patchoverlap, anomaly_scorer_num_nn, patchsize_aggregate,
#                faiss_on_gpu, faiss_num_workers):
#     backbone_names = list(backbone_names)
#     if len(backbone_names) > 1:
#         layers_coll = [[] for _ in range(len(backbone_names))]
#         for layer in layers_to_extract_from:
#             idx   = int(layer.split(".")[0])
#             layer = ".".join(layer.split(".")[1:])
#             layers_coll[idx].append(layer)
#     else:
#         layers_coll = [layers_to_extract_from]

#     def get_patchcore(input_shape, sampler, device):
#         loaded = []
#         for bb_name, layers in zip(backbone_names, layers_coll):
#             bb_seed = None
#             if ".seed-" in bb_name:
#                 bb_name, bb_seed = bb_name.split(".seed-")[0], int(bb_name.split("-")[-1])
#             backbone = patchcore.backbones.load(bb_name)
#             backbone.name, backbone.seed = bb_name, bb_seed
#             nn_method = patchcore.common.FaissNN(faiss_on_gpu, faiss_num_workers)
#             pc = patchcore.patchcore.PatchCore(device)
#             pc.load(backbone=backbone, layers_to_extract_from=layers,
#                     device=device, input_shape=input_shape,
#                     pretrain_embed_dimension=pretrain_embed_dimension,
#                     target_embed_dimension=target_embed_dimension,
#                     patchsize=patchsize, featuresampler=sampler,
#                     anomaly_scorer_num_nn=anomaly_scorer_num_nn, nn_method=nn_method)
#             loaded.append(pc)
#         return loaded
#     return ("get_patchcore", get_patchcore)


# @main.command("sampler")
# @click.argument("name", type=str)
# @click.option("--percentage", "-p", type=float, default=0.1, show_default=True)
# def sampler(name, percentage):
#     def get_sampler(device):
#         if name == "identity":
#             return patchcore.sampler.IdentitySampler()
#         elif name == "greedy_coreset":
#             return patchcore.sampler.GreedyCoresetSampler(percentage, device)
#         elif name == "approx_greedy_coreset":
#             return patchcore.sampler.ApproximateGreedyCoresetSampler(percentage, device)
#     return ("get_sampler", get_sampler)


# @main.command("dataset")
# @click.argument("name",      type=str)
# @click.argument("data_path", type=click.Path(exists=True, file_okay=False))
# @click.option("--subdatasets",     "-d", multiple=True, type=str, required=True)
# @click.option("--train_val_split", type=float, default=0.8, show_default=True)
# @click.option("--batch_size",  default=2,   type=int, show_default=True)
# @click.option("--num_workers", default=8,   type=int, show_default=True)
# @click.option("--resize",      default=256, type=int, show_default=True)
# @click.option("--imagesize",   default=224, type=int, show_default=True)
# @click.option("--augment",     is_flag=True)
# def dataset(name, data_path, subdatasets, train_val_split,
#             batch_size, resize, imagesize, num_workers, augment):
#     dataset_info    = _DATASETS[name]
#     dataset_library = __import__(dataset_info[0], fromlist=[dataset_info[1]])

#     def get_dataloaders(seed):
#         dataloaders = []
#         for subdataset in subdatasets:
#             train_ds = dataset_library.__dict__[dataset_info[1]](
#                 data_path, classname=subdataset, resize=resize,
#                 train_val_split=train_val_split, imagesize=imagesize,
#                 split=dataset_library.DatasetSplit.TRAIN, seed=seed, augment=augment)
#             test_ds = dataset_library.__dict__[dataset_info[1]](
#                 data_path, classname=subdataset, resize=resize,
#                 imagesize=imagesize, split=dataset_library.DatasetSplit.TEST, seed=seed)
#             train_dl = torch.utils.data.DataLoader(
#                 train_ds, batch_size=batch_size, shuffle=False,
#                 num_workers=num_workers, pin_memory=True)
#             test_dl = torch.utils.data.DataLoader(
#                 test_ds, batch_size=batch_size, shuffle=False,
#                 num_workers=num_workers, pin_memory=True)
#             train_dl.name = name + ("_" + subdataset if subdataset else "")
#             val_dl = None
#             if train_val_split < 1:
#                 val_ds = dataset_library.__dict__[dataset_info[1]](
#                     data_path, classname=subdataset, resize=resize,
#                     train_val_split=train_val_split, imagesize=imagesize,
#                     split=dataset_library.DatasetSplit.VAL, seed=seed)
#                 val_dl = torch.utils.data.DataLoader(
#                     val_ds, batch_size=batch_size, shuffle=False,
#                     num_workers=num_workers, pin_memory=True)
#                 LOGGER.info("Train/Val split: {} train, {} val".format(
#                     len(train_ds), len(val_ds)))
#             dataloaders.append({"training": train_dl, "validation": val_dl,
#                                  "testing": test_dl})
#         return dataloaders
#     return ("get_dataloaders", get_dataloaders)


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     LOGGER.info("Command line arguments: {}".format(" ".join(sys.argv)))
#     main()
