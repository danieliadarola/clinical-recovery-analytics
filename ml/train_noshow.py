"""
Train & evaluate the NO-SHOW prediction model.
Target: will a booked appointment become a no-show?
Split: time-based (train < 2026-01-01, test >= 2026-01-01) to mimic deployment.
Run:   python train_noshow.py
"""
import os
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.inspection import permutation_importance

import features as F
import _eval as E

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
DATA = os.path.join(HERE, "..", "data")
CUTOFF = pd.Timestamp("2026-01-01")
RNG = 42


def main():
    data = F.load_data(DATA)
    X, y, meta, num, cat = F.build_noshow_features(data)

    train = meta["scheduled_date"] < CUTOFF
    test = ~train
    Xtr, Xte, ytr, yte = X[train], X[test], y[train], y[test]
    print(f"Train: {len(Xtr):,} (no-show {ytr.mean():.3f}) | "
          f"Test: {len(Xte):,} (no-show {yte.mean():.3f})")

    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    # Primary: gradient boosting (one-hot cats, numerics passthrough)
    pre_gb = ColumnTransformer([("cat", ohe, cat)], remainder="passthrough")
    gb = Pipeline([("pre", pre_gb),
                   ("clf", HistGradientBoostingClassifier(
                       max_iter=300, learning_rate=0.06, max_depth=6,
                       l2_regularization=1.0, random_state=RNG))])
    gb.fit(Xtr, ytr)
    p_gb = gb.predict_proba(Xte)[:, 1]

    # Baseline: logistic regression (scaled numerics + one-hot cats)
    pre_lr = ColumnTransformer([("cat", ohe, cat),
                                ("num", StandardScaler(), num)])
    lr = Pipeline([("pre", pre_lr),
                   ("clf", LogisticRegression(max_iter=1000, C=1.0))])
    lr.fit(Xtr, ytr)
    p_lr = lr.predict_proba(Xte)[:, 1]

    m_gb = E.evaluate_binary(yte.values, p_gb)
    m_lr = E.evaluate_binary(yte.values, p_lr)
    print("GradientBoosting:", m_gb)
    print("Logistic       :", m_lr)

    # Permutation importance on a test sample (per raw feature)
    samp = np.random.RandomState(RNG).choice(len(Xte), size=min(6000, len(Xte)), replace=False)
    pi = permutation_importance(gb, Xte.iloc[samp], yte.iloc[samp],
                                scoring="roc_auc", n_repeats=5, random_state=RNG)

    # Plots
    E.plot_roc_pr(yte.values, p_gb, os.path.join(OUT, "noshow_roc_pr.png"), "No-show")
    E.plot_calibration(yte.values, p_gb, os.path.join(OUT, "noshow_calibration.png"), "No-show")
    E.plot_importance(list(X.columns), pi.importances_mean,
                      os.path.join(OUT, "noshow_importance.png"), "No-show — feature importance")
    E.plot_confusion(yte.values, p_gb, os.path.join(OUT, "noshow_confusion.png"), "No-show",
                     threshold=0.30)

    # Top decile lift — the operational metric (where do reminders go?)
    df = pd.DataFrame({"y": yte.values, "p": p_gb}).sort_values("p", ascending=False)
    top10 = df.head(int(0.10 * len(df)))
    lift = (top10["y"].mean()) / df["y"].mean()
    print(f"Top-decile no-show rate {top10['y'].mean():.3f} vs base {df['y'].mean():.3f} "
          f"(lift x{lift:.2f})")

    importances = sorted(zip(X.columns, [round(float(v), 4) for v in pi.importances_mean]),
                         key=lambda t: t[1], reverse=True)
    E.save_json({
        "model": "HistGradientBoostingClassifier",
        "task": "no-show prediction (binary)",
        "split": f"time-based at {CUTOFF.date()}",
        "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "metrics_gradient_boosting": m_gb,
        "metrics_logistic_baseline": m_lr,
        "top_decile_noshow_rate": round(float(top10["y"].mean()), 4),
        "top_decile_lift": round(float(lift), 2),
        "permutation_importance_auroc_drop": importances,
    }, os.path.join(OUT, "noshow_metrics.json"))
    joblib.dump(gb, os.path.join(OUT, "noshow_model.joblib"))
    print("Saved noshow_model.joblib, noshow_metrics.json and 4 plots ->", OUT)


if __name__ == "__main__":
    main()
