"""Anomaly metrics."""
import numpy as np
from sklearn import metrics

def compute_imagewise_retrieval_metrics(
    anomaly_prediction_weights, anomaly_ground_truth_labels, manual_threshold=None
):
    """
    Computes retrieval statistics (AUROC, FPR, TPR).
    """
    from sklearn.metrics import precision_recall_curve, confusion_matrix

    # Check how many classes are present
    unique_classes = np.unique(anomaly_ground_truth_labels)
    
    # 1. Handle AUROC: requires both classes to work.
    if len(unique_classes) > 1:
        fpr, tpr, thresholds = metrics.roc_curve(
            anomaly_ground_truth_labels, anomaly_prediction_weights, pos_label=1
        )
        auroc = metrics.roc_auc_score(
            anomaly_ground_truth_labels, anomaly_prediction_weights
        )
    else:
        # If only one class is present, AUROC/ROC is mathematically undefined.
        # We provide dummy values to prevent crashing.
        fpr, tpr, thresholds = np.array([0]), np.array([0]), np.array([0])
        auroc = 0.0

    # 2. Handle Thresholding
    if manual_threshold is not None:
        best_threshold = manual_threshold
        preds = (np.array(anomaly_prediction_weights) >= best_threshold).astype(int)
        precision_score = metrics.precision_score(anomaly_ground_truth_labels, preds, pos_label=1, zero_division=0)
        recall_score = metrics.recall_score(anomaly_ground_truth_labels, preds, pos_label=1, zero_division=0)
        f1_score_val = metrics.f1_score(anomaly_ground_truth_labels, preds, pos_label=1, zero_division=0)
    else:
        if len(unique_classes) > 1:
            precision, recall, pr_thresholds = precision_recall_curve(
                anomaly_ground_truth_labels, anomaly_prediction_weights, pos_label=1
            )
            f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
            best_idx = np.argmax(f1_scores)
            best_threshold = pr_thresholds[best_idx] if best_idx < len(pr_thresholds) else 0.5
            preds = (np.array(anomaly_prediction_weights) >= best_threshold).astype(int)
            precision_score = precision[best_idx]
            recall_score = recall[best_idx]
            f1_score_val = f1_scores[best_idx]
        else:
            # Default threshold if only one class is uploaded
            best_threshold = 0.5 
            preds = (np.array(anomaly_prediction_weights) >= best_threshold).astype(int)
            precision_score, recall_score, f1_score_val = 0.0, 0.0, 0.0

    # 3. Handle Confusion Matrix (The Crash Fix)
    # labels=[0, 1] ensures we always get tn, fp, fn, tp even if a class is missing
    conf_matrix = confusion_matrix(anomaly_ground_truth_labels, preds, labels=[0, 1])
    tn, fp, fn, tp = conf_matrix.ravel()


    return {
        "auroc": auroc,
        "fpr": fpr,
        "tpr": tpr,
        "threshold": best_threshold,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision_score,
        "recall": recall_score,
        "f1": f1_score_val,
    }