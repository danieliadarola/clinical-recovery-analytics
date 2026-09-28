"""Shared evaluation + plotting helpers for the predictive models."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (roc_auc_score, average_precision_score, brier_score_loss,
                             roc_curve, precision_recall_curve, confusion_matrix,
                             precision_score, recall_score, f1_score)
from sklearn.calibration import calibration_curve

BLUE, GREY, RED = "#2563eb", "#94a3b8", "#dc2626"


def evaluate_binary(y_true, y_prob, threshold=0.5):
    y_pred = (y_prob >= threshold).astype(int)
    base_rate = float(np.mean(y_true))
    return {
        "n": int(len(y_true)),
        "positive_rate": round(base_rate, 4),
        "threshold": threshold,
        "auroc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "auprc": round(float(average_precision_score(y_true, y_prob)), 4),
        "auprc_lift_vs_base": round(float(average_precision_score(y_true, y_prob)) / base_rate, 2),
        "brier": round(float(brier_score_loss(y_true, y_prob)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }


def plot_roc_pr(y_true, y_prob, path, title):
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    auroc = roc_auc_score(y_true, y_prob)
    auprc = average_precision_score(y_true, y_prob)
    base = np.mean(y_true)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    ax[0].plot(fpr, tpr, color=BLUE, lw=2, label=f"AUROC = {auroc:.3f}")
    ax[0].plot([0, 1], [0, 1], "--", color=GREY, lw=1)
    ax[0].set(xlabel="False positive rate", ylabel="True positive rate",
              title=f"{title} — ROC")
    ax[0].legend(loc="lower right")
    ax[1].plot(rec, prec, color=BLUE, lw=2, label=f"AUPRC = {auprc:.3f}")
    ax[1].axhline(base, ls="--", color=GREY, lw=1, label=f"baseline = {base:.3f}")
    ax[1].set(xlabel="Recall", ylabel="Precision", title=f"{title} — Precision-Recall")
    ax[1].legend(loc="upper right")
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def plot_calibration(y_true, y_prob, path, title):
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5.2, 5))
    ax.plot([0, 1], [0, 1], "--", color=GREY, lw=1, label="perfectly calibrated")
    ax.plot(mean_pred, frac_pos, "o-", color=BLUE, lw=2, label="model")
    ax.set(xlabel="Mean predicted probability", ylabel="Observed frequency",
           title=f"{title} — Calibration")
    ax.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def plot_importance(names, importances, path, title, top=15):
    order = np.argsort(importances)[::-1][:top]
    names = np.array(names)[order]; vals = np.array(importances)[order]
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.barh(range(len(names))[::-1], vals, color=BLUE)
    ax.set_yticks(range(len(names))[::-1]); ax.set_yticklabels(names, fontsize=8)
    ax.set(xlabel="Permutation importance (mean AUROC drop)", title=title)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def plot_confusion(y_true, y_prob, path, title, threshold=0.5):
    cm = confusion_matrix(y_true, (y_prob >= threshold).astype(int))
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    im = ax.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, f"{v:,}", ha="center", va="center",
                color="white" if v > cm.max() / 2 else "black", fontsize=11)
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["pred 0", "pred 1"],
           yticklabels=["true 0", "true 1"],
           title=f"{title} — Confusion @{threshold}")
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def save_json(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
