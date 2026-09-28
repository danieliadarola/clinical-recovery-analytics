# Phase 6 — Clinical & Operational Insights

This phase interprets the analytics: what the data shows, what is likely
driving it, what ARN should *do*, and — just as important — what the analysis
**cannot** tell us. All figures are computed from the synthetic dataset.

## 6.1 Headline picture

| KPI | Value | Read |
|-----|-------|------|
| No-show rate | **11.4%** | above a 10% target |
| Cancellation rate | 6.7% | typical |
| Lost capacity (no-show + cancel) | **18.0%** (~11,322 slots ≈ **8,492 clinician-hours**) | large, partly addressable |
| Treatment completion (closed episodes) | **75.7%** | drop-out is ~24% |
| Mean adherence | 85.1% | good but uneven |
| Pain (NPRS) baseline → discharge | **6.4 → 2.7** (Δ 3.7) | well above the 2-point MCID |
| Functional MCID achievement | **93.9%** | strong overall |
| Active patients at risk of drop-out | **182** (67 high) | actionable now |

## 6.2 Insight 1 — A large slice of capacity is lost, and some of it is winnable

Nearly **one in five resolved appointments is missed or cancelled**, ≈8,492
clinician-hours a year. The pattern is not random:

- No-show rate climbs with **booking lead time**: 9.9% for slots booked within
  2 days vs **15.3%** for slots booked ≥14 days ahead (Q2).
- **Mondays** and early-morning slots are worst.
- It concentrates by **site**: ARN Sevilla 14.9% vs ARN Barcelona Eixample 8.1%.

**Why:** long lead times mean more life gets in the way and the appointment feels
less salient; weak reminder workflows at some clinics amplify it.

**Actions:** (1) tiered **reminders** (SMS + call) triggered by lead-time risk —
now also informable by the **no-show model** (`/ml`); (2) cap routine booking
horizons and offer earlier slots; (3) **controlled overbooking** on
statistically high-no-show slots; (4) share Eixample's scheduling practice with
Sevilla and Barcelona Sants. Even a 3-point reduction in no-shows recovers on the
order of ~1,500 slots/year.

## 6.3 Insight 2 — Drop-out is the biggest *clinical* opportunity

About a quarter of closed episodes end as drop-out, and the data shows this is
not benign: recovery **rises monotonically with adherence** (Q9) —

| adherence | mean functional improvement | % reaching MCID |
|-----------|-----------------------------|-----------------|
| 50–69% | 18.9 | 83.3% |
| 90–100% | **24.5** | **94.1%** |

Patients who stop early recover materially less. Right now **182 active patients**
are already drifting (≥14 days since last visit with sessions remaining), with
**~1,600 planned sessions at risk**.

**Actions:** operationalise the **drop-out risk register** (`v_dropout_risk`,
Q6) as a weekly per-clinic call list, and feed it the **early-warning drop-out
model** (`/ml`) so patients can be flagged from their first sessions, not just
once a gap has opened. Trigger outreach at the first missed-visit gap; consider
tele-rehab check-ins to keep momentum. This is where analytics most directly
improves *patient outcomes*, not just utilisation.

## 6.4 Insight 3 — Outcomes are strong overall but uneven by condition

Aggregate recovery is excellent (93.9% reach functional MCID; pain roughly
halves). But some conditions lag:

- **Conservative carpal tunnel** 78.3% and **frozen shoulder** 81.6% reach MCID,
  well below low back pain (96.8%) and neck pain (97.9%).
- These are also among the **longest / hardest** episodes (frozen shoulder ~76
  days, 17 sessions).

**Why:** these conditions have genuinely slower natural histories and may be
under-dosed or better served by onward referral in non-responders.

**Actions:** review and standardise protocols for the lagging conditions; set
condition-specific expectations for length of stay; define a "non-responder"
checkpoint (e.g. re-assess at session 8) for referral.

## 6.5 Insight 4 — Operational and clinical performance tend to travel together

The strongest operational clinics also tend to post the best outcomes:
**Barcelona Eixample** (no-show 8.1%, functional MCID 95.0%), **Madrid Centro**
(8.6%, 94.2%) and **Bilbao** (9.8%, **96.3%** — the highest) sit at the top on
both, while the weakest operational sites — **Sevilla** (14.9%, 92.8%) and
**Barcelona Sants** (13.8%) — sit at or below average on MCID.

The association is **positive but imperfect** (e.g. Madrid Norte combines a
mid no-show rate with the lowest MCID, 91.3% — a site worth a closer look). Still,
the direction is clear and consistent with Insight 2: **keeping patients in the
chair tends to protect their recovery.** The no-show, adherence and outcome
agendas are largely one agenda.

**Action:** treat the lowest-performing sites (Sevilla, Sants, and Madrid Norte
on outcomes) as an improvement programme with a single owner, tracking all three
KPI families together.

## 6.6 Prioritised recommendations

| Priority | Action | Expected effect | Effort |
|----------|--------|-----------------|--------|
| 1 | Weekly drop-out risk register + early-warning model outreach | ↑ completion, ↑ outcomes | Low |
| 2 | Lead-time-tiered reminders + Monday focus (+ no-show model) | ↓ no-shows ~2–4 pts | Low |
| 3 | Standardise protocols for carpal tunnel / frozen shoulder | ↑ MCID in laggards | Medium |
| 4 | Eixample/Bilbao → Sevilla/Sants best-practice transfer | ↓ variation | Medium |
| 5 | Controlled overbooking on high-risk slots | ↑ utilisation | Medium |

## 6.7 Limitations (read before acting)

A credible analyst is explicit about what the numbers do **not** prove:

1. **Synthetic data.** The dataset is *engineered* to contain clean signal. Real
   ARN data would be noisier, with missingness, coding errors and confounding —
   effect sizes here are illustrative, not predictions.
2. **Correlation, not causation.** The adherence→recovery relationship (Q9) is
   observational. Sicker or less-motivated patients may both adhere less *and*
   recover less; adherence is partly a *marker* of recovery, not only a cause. A
   randomised reminder/outreach trial would be needed to prove the effect.
3. **Survivorship bias in outcomes.** Discharge PROMs exist mainly for
   *completed* episodes, so outcome KPIs (MCID %) describe patients who finished
   — they overstate recovery for the whole intake. Drop-outs' missing outcomes
   are informative missingness.
4. **No case-mix adjustment.** Clinic and therapist comparisons are not
   risk-adjusted for age, severity or diagnosis mix; the scorecard uses a
   minimum-volume floor but is for improvement, not judgement.
5. **Terminology to validate.** Disability-index LOINC codes are representative
   and must be confirmed against LOINC before production.
6. **Cost figures are estimates.** "Hours lost" assumes 45-minute slots and
   says nothing about fixed vs variable cost; Finance should refine it.

These limitations define the natural next step: move from descriptive/diagnostic
analytics to **predictive** models (implemented in `/ml`, see Phase 7) and,
eventually, a controlled evaluation.
