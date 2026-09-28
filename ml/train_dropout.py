"""
Train & evaluate the DROP-OUT early-warning model.
Target: will a *closed* episode end as drop-out (revoked) vs completed?
Design: EARLY WARNING — only intake data + behaviour in the first 3 sessions.
Split:  time-based on episode start date.
Run:    python train_dropout.py
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
CUTOFF = pd.Timestamp("2025-10-01")
RNG = 42
THR = 0.40   # operating threshold favouring recall of drop-outs


def main():
    data = F.load_data(DATA)
    X, y, meta, num, cat = F.build_dropout_features(data)

    train = meta["period_start"] < CUTOFF
    test = ~train
    Xtr, Xte, ytr, yte = X[train], X[test], y[train], y[test]
    print(f"Train: {len(Xtr):,} (dropout {ytr.mean():.3f}) | "
          f"Test: {len(Xte):,} (dropout {yte.mean():.3f})")

    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    pre_gb = ColumnTransformer([("cat", ohe, cat)], remainder="passthrough")
    gb = Pipeline([("pre", pre_gb),
                   ("clf", HistGradientBoostingClassifier(
                       max_iter=300, learning_rate=0.06, max_depth=5,
                       l2_regularization=1.0, random_state=RNG))])
    gb.fit(Xtr, ytr)
    p_gb = gb.predict_proba(Xte)[:, 1]

    pre_lr = ColumnTransformer([("cat", ohe, cat), ("num", StandardScaler(), num)])
    lr = Pipeline([("pre", pre_lr),
                   ("clf", LogisticRegression(max_iter=1000, C=1.0))])
    lr.fit(Xtr, ytr)
    p_lr = lr.predict_proba(Xte)[:, 1]

    m_gb = E.evaluate_binary(yte.values, p_gb, threshold=THR)
    m_lr = E.evaluate_binary(yte.values, p_lr, threshold=THR)
    print("GradientBoosting:", m_gb)
    print("Logistic       :", m_lr)

    pi = permutation_importance(gb, Xte, yte, scoring="roc_auc",
                                n_repeats=10, random_state=RNG)

    E.plot_roc_pr(yte.values, p_gb, os.path.join(OUT, "dropout_roc_pr.png"), "Drop-out")
    E.plot_calibration(yte.values, p_gb, os.path.join(OUT, "dropout_calibration.png"), "Drop-out")
    E.plot_importance(list(X.columns), pi.importances_mean,
                      os.path.join(OUT, "dropout_importance.png"), "Drop-out — feature importance")
    E.plot_confusion(yte.values, p_gb, os.path.join(OUT, "dropout_confusion.png"),
                     "Drop-out", threshold=THR)

    df = pd.DataFrame({"y": yte.values, "p": p_gb}).sort_values("p", ascending=False)
    top20 = df.head(int(0.20 * len(df)))
    lift = top20["y"].mean() / df["y"].mean()
    print(f"Top-quintile dropout rate {top20['y'].mean():.3f} vs base {df['y'].mean():.3f} "
          f"(lift x{lift:.2f})")

    importances = sorted(zip(X.columns, [round(float(v), 4) for v in pi.importances_mean]),
                         key=lambda t: t[1], reverse=True)
    E.save_json({
        "model": "HistGradientBoostingClassifier",
        "task": "early drop-out prediction (binary)",
        "design": "early warning — intake + first-3-session features only (no leakage)",
        "split": f"time-based at {CUTOFF.date()}",
        "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "operating_threshold": THR,
        "metrics_gradient_boosting": m_gb,
        "metrics_logistic_baseline": m_lr,
        "top_quintile_dropout_rate": round(float(top20["y"].mean()), 4),
        "top_quintile_lift": round(float(lift), 2),
        "permutation_importance_auroc_drop": importances,
    }, os.path.join(OUT, "dropout_metrics.json"))
    joblib.dump(gb, os.path.join(OUT, "dropout_model.joblib"))
    print("Saved dropout_model.joblib, dropout_metrics.json and 4 plots ->", OUT)


if __name__ == "__main__":
    main()
