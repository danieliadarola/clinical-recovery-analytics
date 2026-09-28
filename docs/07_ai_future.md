# Phase 7 — AI & Future Direction

The platform's clean, modelled data is the foundation for moving up the
analytics maturity ladder: **descriptive** (what happened) → **diagnostic** (why)
→ **predictive** (what will happen) → **prescriptive** (what to do). Phases 4–6
delivered the first two. This phase scopes the next, *with the governance that
European healthcare AI now requires*.

> 🔧 The two starting use cases below (no-show and early drop-out prediction)
> are **implemented** in [`/ml`](../ml) — see [`ml/README.md`](../ml/README.md)
> for the leakage-safe method, results and evaluation plots. The rest of this
> phase covers the wider roadmap and the governance every model must satisfy.

## 7.1 Predictive use cases

| Use case | Target (label) | Example features | Model class | Value |
|----------|----------------|------------------|-------------|-------|
| **No-show prediction** | Will this booked appointment be a no-show? | lead time, weekday, hour, prior no-shows, session number, distance, insurance | Gradient boosting / logistic regression | Smart reminders & overbooking |
| **Drop-out early warning** | Will this active episode be abandoned? | attendance in first 3 sessions, gap pattern, baseline pain/disability, diagnosis, age | Survival model / gradient boosting | Proactive outreach *before* drop-out |
| **Recovery trajectory** | Expected discharge PROM / time-to-discharge | baseline PROMs, diagnosis, age, comorbidity, early response | Regression / mixed-effects | Set expectations, triage non-responders |
| **Demand & capacity forecast** | Episodes/visits per clinic per week | history, seasonality, referrals | Time-series (Prophet/ARIMA) | Staffing & rota planning |
| **Notes enrichment (NLP)** | Structured severity/function from free text | clinical note text | Clinical NLP / LLM extraction | Fill PROM gaps, reduce admin |

The two highest-value, lowest-risk starting points are **no-show prediction**
and **drop-out early warning** — both are operational, both have a clear action,
and both build directly on features already in the model
(`fact_appointment`, `v_dropout_risk`).

## 7.2 How they would be built (responsibly)

- **Data split & leakage:** train/validation/test split *by time* (and never
  leak post-outcome fields such as `discharge_date` into a predictor).
- **Validation:** AUROC/AUPRC and **calibration** (a 30% predicted risk should
  mean 30% observed) — calibration matters more than raw accuracy when the score
  drives outreach.
- **Class imbalance:** no-shows/drop-outs are minorities; use AUPRC, threshold
  tuning, and cost-sensitive learning, not plain accuracy.
- **Explainability:** SHAP-style per-prediction reasons so a clinic manager sees
  *why* a patient is flagged.
- **Deployment:** score nightly, surface in the existing Power BI risk register —
  **decision support, not decision automation**.
- **Monitoring:** track data drift and performance over time; retrain on a
  schedule; log every score for audit.

## 7.3 Regulatory landscape (GDPR + EU AI Act)

### GDPR (the data layer)
Physiotherapy data is **special-category health data (Art. 9)**, so:

- **Lawful basis:** Art. 6 *and* an Art. 9 condition (e.g. health-care provision,
  Art. 9(2)(h)); analytics/secondary use needs its own basis.
- **DPIA** is effectively mandatory for risk-scoring of patients.
- **Data minimisation & pseudonymisation:** the model already drops names and
  reduces address to postal code; dashboards show MRN only, with RLS by clinic.
- **Automated decisions (Art. 22):** keep a human in the loop — outreach is
  *suggested*, never automatically denying or deprioritising care.
- **Transparency & rights:** patients informed of analytic use; access/erasure
  honoured; documented **retention** limits.

### EU AI Act (the model layer) — status as of June 2026
The EU AI Act is in force and being phased in. On **7 May 2026** the EU reached a
provisional agreement on the **"Digital Omnibus on AI"**, the first set of
amendments, which **relaxed the timeline** for high-risk systems:

- **Annex III (use-based) high-risk** obligations are postponed from **2 Aug 2026
  to 2 Dec 2027**.
- **Annex I (product-regulated, incl. medical devices)** high-risk obligations
  are postponed from **2 Aug 2027 to 2 Aug 2028**, with an **extra transition
  year** for AI that is already a medical device under **MDR/IVDR** requiring a
  Notified Body.
- The Commission's **February 2026 guidelines** clarify high-risk classification
  with practical examples. (Prohibited-practice rules and GPAI obligations are
  already in effect from earlier phases.)

**Where this project sits:**

- A **no-show / scheduling** model is an *administrative/operational* tool and is
  generally **not** high-risk under Annex III — but ARN must avoid it becoming a
  tool that **denies or deprioritises access to care** (which can pull it toward
  high-risk and Art. 22 territory).
- A **drop-out / recovery** model used to *prioritise clinical outreach* sits in
  a grey zone; if it is given an **intended medical purpose** (e.g. diagnosing,
  predicting, or directing treatment), it can qualify as a **medical device
  (SaMD)** under MDR — triggering **both** MDR conformity assessment **and** the
  AI Act's high-risk obligations.

**High-risk obligations to design for (if/when applicable):** a risk-management
system; **data governance** (representative, bias-checked data); technical
documentation; **logging/record-keeping**; transparency to users;
**human oversight**; and accuracy, robustness & cybersecurity — verified through
conformity assessment.

## 7.4 Ethical risks specific to this project

- **Automation bias:** staff may over-trust the score. Mitigate with
  explanations, a "this is a suggestion" framing, and training.
- **Equity / feedback loops:** if "likely to no-show" patients are quietly
  deprioritised, the model can entrench disadvantage (these patients are often
  the most vulnerable). The intended use must be **more support for high-risk
  patients, never less access** — and outcomes should be monitored by subgroup.
- **Fairness:** test performance across age, sex, language, insurance and
  deprivation proxies; document and remediate disparities.
- **Drift & safety:** clinical patterns change; un-monitored models decay.
  Scheduled revalidation and a clear "switch-off" path are part of the design.

## 7.5 A responsible-AI checklist for ARN

1. DPIA completed and signed off by the DPO before any patient scoring.
2. Clear **intended purpose** statement (decides MDR/AI-Act classification).
3. Human-in-the-loop on every patient-level action.
4. Bias & calibration testing by subgroup, repeated on each retrain.
5. Full logging of inputs, scores and overrides for auditability.
6. Patient-facing transparency and honoured data-subject rights.
7. Monitoring dashboard for drift, performance and equity.

The guiding principle: **AI should help ARN give more attention to the patients
most at risk of a poor recovery — not ration care to them.**
