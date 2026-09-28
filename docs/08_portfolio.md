# Phase 8 — Portfolio Materials

Ready-to-use text to present this project on GitHub, LinkedIn and your CV, plus
a guide for talking about it in interviews. Adjust the first-person voice to your
own.

## 8.1 GitHub — project description

**Short description (repo "About"):**
> End-to-end health informatics project: FHIR R4 → PostgreSQL → Power BI, plus
> predictive models, for an outpatient physiotherapy network. Models recovery,
> adherence, no-shows and drop-out risk on a realistic synthetic dataset (64k+
> appointments).

**Suggested topics/tags:** `health-informatics` `fhir` `hl7-fhir` `sql`
`postgresql` `power-bi` `dax` `healthcare-analytics` `interoperability`
`machine-learning` `scikit-learn` `gdpr` `eu-ai-act`

**One-paragraph summary (top of README):**
> The **Clinical Recovery Analytics Platform** simulates the work of a Health
> Informatics Analyst in a network of physiotherapy clinics. It takes clinical
> data modelled as **FHIR R4**, flattens it into a governed **PostgreSQL** star
> schema, answers real operational and clinical questions in **SQL** (window
> functions, CTEs, MCID-based outcome KPIs), presents the results in three
> **Power BI** dashboards, and adds two **predictive models** (no-show and early
> drop-out) — all under GDPR and EU AI Act governance.

## 8.2 LinkedIn — post

> 🏥📊 I built a Health Informatics Analyst portfolio project end to end:
> **Clinical Recovery Analytics Platform (FHIR · SQL · Power BI · ML).**
>
> Coming from physiotherapy, I wanted to show how the right data pipeline turns
> messy clinical reality into decisions. So I simulated an 8-clinic
> physiotherapy network and built the whole stack:
>
> 🔹 Modelled care as **FHIR R4** resources (Patient, Encounter, Appointment,
> Condition, Observation/PROMs, CarePlan)
> 🔹 Flattened them into a **PostgreSQL** star schema (64k+ appointments, 5.4k
> care episodes, 20k+ outcome measures)
> 🔹 Wrote **SQL** for the questions that matter — no-show drivers, treatment
> adherence, time-to-discharge, and a **drop-out risk register** using window
> functions
> 🔹 Designed **executive, clinical & operational Power BI dashboards** with a
> full DAX measure library
> 🔹 Trained **no-show & early drop-out models** (scikit-learn) — the drop-out
> model flags the riskiest 20% of patients, who drop out at ~1.6× the base rate
>
> A few findings from the (synthetic) data:
> ✅ 18% of capacity lost to no-shows/cancellations (~8,500 clinician-hours)
> ✅ Appointments booked 2+ weeks ahead are missed ~55% more often
> ✅ Recovery rises with adherence — patients reaching 90%+ of sessions hit their
> clinically-meaningful improvement ~94% of the time
>
> I also documented the bit people skip: **GDPR (Art. 9 health data)** and where
> the models sit under the **EU AI Act** (incl. the 2026 Digital Omnibus
> timeline).
>
> Repo + full write-up 👇 Feedback very welcome.
> #HealthInformatics #FHIR #SQL #PowerBI #MachineLearning #HealthcareAnalytics

## 8.3 CV — five impact bullets

Use these under a "Projects" (or relevant experience) heading. Each leads with an
impact verb and quantifies the work.

- **Engineered** an end-to-end clinical analytics pipeline (**FHIR R4 →
  PostgreSQL → Power BI**) over a realistic **64,000-appointment**,
  5,400-episode physiotherapy dataset, defining every KPI once from source to
  dashboard.
- **Designed** a normalized + star-schema data model (8 core tables, conformed
  dimensions and fact views) and authored **10 analytical SQL queries** using
  CTEs and window functions (`LAG`, `RANK`, running aggregates).
- **Built** an SQL **drop-out risk register** that flags **182 at-risk patients
  (~1,600 sessions in jeopardy)** and a **scikit-learn early-warning model**
  (AUROC 0.66) that catches 41% of drop-outs in its top-risk quintile.
- **Quantified 18% of lost clinical capacity (~8,500 clinician-hours/yr)** and
  identified booking lead time as the primary no-show driver (9.9% → 15.3%),
  with prioritised operational recommendations.
- **Measured recovery** with harmonised PROMs and **MCID** logic (93.9%
  functional MCID achievement) and **documented GDPR & EU AI Act governance**,
  incl. a DAX measure library for three role-based dashboards.

*(For ML-heavy roles, lead with the model bullet and add calibration/AUPRC
detail from `ml/README.md`.)*

## 8.4 Interview — how to present it

**The 90-second pitch (STAR):**
- **Situation:** "A physiotherapy network had no shared view of outcomes,
  no-shows or drop-out — managers worked from spreadsheets."
- **Task:** "As the analyst, build a single, governed pipeline from the EHR's
  FHIR data to dashboards that answer operational and clinical questions, and
  start the move to predictive analytics."
- **Action:** "I modelled the domain in FHIR R4, flattened it into a PostgreSQL
  star schema, wrote the KPI logic in SQL — including a drop-out risk query with
  window functions — designed three Power BI dashboards with a DAX library, and
  trained leakage-safe no-show and drop-out models, all under GDPR/EU-AI-Act
  governance."
- **Result:** "I quantified 18% lost capacity, showed adherence drives recovery,
  produced a weekly at-risk call list of 182 patients, and an early-warning model
  that concentrates drop-out risk — turning data into concrete action."

**What to demo, in order:** (1) the clinical-flow and ER diagrams (domain
understanding); (2) one FHIR resource and how it maps to a table
(interoperability); (3) the drop-out `LAG`/CTE query (SQL depth); (4) the
operational dashboard mock (business impact); (5) the model's calibration &
feature-importance plots (ML maturity); (6) the limitations slide (judgement).

**Likely questions & strong answers:**
- *"Is the adherence→recovery link causal?"* → No — observational; severity may
  confound; I'd validate with a controlled reminder/outreach trial.
- *"How did you avoid leakage in the models?"* → Time-based train/test split, and
  the drop-out model uses only intake + first-3-session features — never total
  attendance or discharge.
- *"Your no-show AUROC is ~0.59 — is that good?"* → No-show is hard from
  administrative data; the value is risk concentration (top decile ~1.5× base) to
  target reminders, plus good calibration. Honest framing beats an inflated metric.
- *"Is your risk model high-risk under the EU AI Act?"* → The scheduling model is
  operational/low-risk; a clinical-triage model could be high-risk or a medical
  device under MDR — I designed human-in-the-loop and a DPIA for that.
- *"What would you do next?"* → Operationalise the register, enrich features
  (distance, reminder responses, deprivation), add drift monitoring, then a
  controlled evaluation.

**Framing tips:** lead with the *business problem*, not the tech; be proud of the
**limitations** section — it signals seniority; tie every technical choice back
to a decision a stakeholder makes.

## 8.5 Honesty note (keep this credible)

Describe it accurately as a **portfolio project on synthetic data** that
*simulates* a real environment. Never imply it ran on real patients. The value
you're demonstrating is real: domain modelling, SQL, BI design, predictive
modelling and governance judgement.
