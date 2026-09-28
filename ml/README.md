# Predictive models — no-show & early drop-out

This module operationalises Phase 7: two scikit-learn models that turn the
descriptive analytics into *forward-looking* decision support. Both are built
to be **honest and leakage-free** — the point is to demonstrate correct method
and governance, not to chase an impressive-looking metric on synthetic data.

```
ml/
├── features.py        leakage-safe feature engineering (shared)
├── _eval.py           metrics + plotting helpers
├── train_noshow.py    no-show model: train, evaluate, save
├── train_dropout.py   early drop-out model: train, evaluate, save
├── requirements.txt
└── outputs/           metrics JSON + plots (models are git-ignored)
```

Run:

```bash
pip install -r ml/requirements.txt
python ml/train_noshow.py
python ml/train_dropout.py
```

## Design choices (why this is credible)

- **Time-based train/test split**, never random — the test set is the *future*
  relative to the training set, exactly as in deployment. (No-show split at
  2026-01-01; drop-out split at 2025-10-01 on episode start.)
- **No data leakage.** No-show features use only what is known *at booking time*
  plus the patient's history of *prior* appointments (`shift`-style cumulative
  counts). The drop-out model is an **early-warning** design: it uses only
  intake data and behaviour in the **first 3 scheduled sessions** — never total
  attendance, discharge or adherence (which would leak the outcome).
- **Right metrics for imbalanced data.** AUROC *and* AUPRC (with lift over base
  rate), **Brier score** and a **calibration curve** — because a risk score that
  drives outreach must be calibrated, not just rank-ordered. Plain accuracy is
  not reported (it is misleading at a 12–26% positive rate).
- **Two model families** per task (HistGradientBoosting + Logistic Regression)
  so a simple, interpretable baseline keeps the gradient-boosting model honest.
- **Explainability** via permutation importance (impact on test AUROC).

## Results (synthetic data, held-out future test set)

### No-show model
| Metric | Gradient Boosting | Logistic |
|--------|------------------:|---------:|
| AUROC | 0.59 | 0.59 |
| AUPRC (base 0.12) | 0.16 (×1.3) | 0.16 |
| Brier | 0.107 | 0.107 |
| **Top-decile no-show rate** | **18.2%** vs 12.3% base (**×1.48 lift**) | — |

No-show is **inherently hard to predict** from administrative data, and an
AUROC near 0.6 is consistent with the literature. What matters operationally is
that the model **concentrates risk**: the riskiest 10% of appointments miss at
~1.5× the base rate, which is enough to **target reminders and controlled
overbooking** where they pay off. Top drivers: booking **lead time**, **prior
no-show history**, clinic, weekday/hour.

### Early drop-out model
| Metric | Gradient Boosting | Logistic |
|--------|------------------:|---------:|
| AUROC | 0.63 | **0.66** |
| AUPRC (base 0.26) | 0.43 (×1.65) | **0.47 (×1.78)** |
| Brier | 0.192 | **0.177** |
| **Top-quintile drop-out rate** | **41%** vs 26% base (**×1.57 lift**) | — |

Predicting drop-out *at intake* is more tractable: the model flags a high-risk
group (top 20%) that drops out at ~1.6× the base rate, **before treatment even
gathers momentum**. The interpretable **logistic model is competitive/better**
here, so it is the recommended choice (simpler, easier to govern). Top drivers
(permutation importance): **early attendance behaviour**, **age**,
**planned course length**, **payer type**, **baseline disability** and clinic —
all clinically plausible.

Plots for both models are in [`outputs/`](outputs): ROC/PR, calibration,
permutation importance and confusion matrix.

## How this fits the platform

These models are **decision support, not automation**. They feed the same
operational surfaces built earlier:

- the no-show score → **reminder/overbooking** policy (Operational dashboard);
- the drop-out score → an *earlier* signal feeding the **drop-out risk register**
  (`sql/v_dropout_risk`, Phase 6). The SQL register catches patients who are
  *already* drifting (mid-episode gaps); the ML model flags likely drop-outs
  **from the first sessions**, so outreach can start sooner.

## Governance (see `docs/07_ai_future.md`)

Scored at patient level, these are special-category health data (GDPR Art. 9) and
require a DPIA, human-in-the-loop use, calibration/bias monitoring by subgroup,
and full logging. Under the EU AI Act the no-show model is operational/low-risk;
a drop-out model used to direct clinical care could be high-risk (or a medical
device under MDR) and is designed accordingly. **Guiding principle: use the
scores to give *more* support to at-risk patients, never to ration their care.**

> All results come from synthetic data and are illustrative. On real ARN data,
> richer features (travel distance, reminder responses, deprivation index,
> deeper history) would be expected to improve performance.
