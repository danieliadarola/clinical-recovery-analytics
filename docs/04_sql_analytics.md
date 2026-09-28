# Phase 4 — SQL Analytics

Every business question from Phase 1 is answered with one query in
[`/sql/04_analytical_queries.sql`](../sql/04_analytical_queries.sql). The
techniques requested — `JOIN`, `GROUP BY`, `CASE WHEN`, CTEs and **window
functions** — are used where they are genuinely the right tool, not for show.

All result tables below are **actual output** from running the queries against
the synthetic dataset (verified with the harness in `/data`). They are
reproducible.

---

## Q1 — No-show & cancellation rate by clinic and month
*Technique: `JOIN`, `GROUP BY`, `CASE WHEN` (via `FILTER`).* Establishes the
operational baseline and the denominator discipline used everywhere: rates are
over **resolved** appointments (`fulfilled + noshow + cancelled`), never over
future `booked` slots.

```sql
SELECT c.name AS clinic, TO_CHAR(a.scheduled_date,'YYYY-MM') AS year_month,
       ROUND(100.0 * COUNT(*) FILTER (WHERE a.status='noshow')
             / NULLIF(COUNT(*) FILTER (WHERE a.status IN ('fulfilled','noshow','cancelled')),0),1) AS noshow_pct
FROM appointments a JOIN clinics c USING (clinic_id)
GROUP BY c.name, TO_CHAR(a.scheduled_date,'YYYY-MM');
```

## Q2 — No-show drivers: lead time × weekday
*Technique: `CASE WHEN` bucketing, `GROUP BY`.* The actionable diagnostic
finding of the whole project:

| lead_time_band | no-show % |
|----------------|-----------|
| 0–2 days | **9.9%** |
| 3–7 days | 10.0% |
| 8–13 days | 11.9% |
| 14+ days | **15.3%** |

Appointments booked **two weeks or more in advance are ~55% more likely to be
missed** than those booked within a week — and Mondays are worst of all. This
is a lever ARN can pull immediately (reminders, shorter booking horizons).

## Q3 — Treatment adherence by clinic
*Technique: CTE, `JOIN`, `GROUP BY`.* Share of closed episodes that completed
≥80% of planned sessions.

| clinic | mean adherence | % adherent episodes |
|--------|---------------|---------------------|
| ARN Barcelona Eixample | 87.5% | 78.2% |
| ARN Madrid Centro | 87.6% | 78.0% |
| … | … | … |
| ARN Barcelona Sants | 80.8% | 67.8% |

## Q4 — Mean time to discharge by diagnosis
*Technique: `JOIN`, `GROUP BY`, `PERCENTILE_CONT` (ordered-set aggregate).*
Length of stay is condition-specific, which matters for capacity planning:

| diagnosis | mean LOS (days) | mean sessions |
|-----------|-----------------|---------------|
| ACL reconstruction rehab | 95.7 | 21.4 |
| Adhesive capsulitis (frozen shoulder) | 76.0 | 17.1 |
| Lumbar radiculopathy (sciatica) | 63.3 | 14.5 |
| Low back pain | 50.9 | 11.7 |
| Carpal tunnel (conservative) | 35.2 | 8.7 |

## Q5 — Most frequent diagnoses (ranked)
*Technique: window functions `RANK()` and `SUM() OVER ()` for share and
cumulative %.* A clean Pareto: the **top 5 diagnoses account for ~62%** of all
episodes.

| rank | diagnosis | episodes | % of total | cumulative % |
|------|-----------|----------|-----------|--------------|
| 1 | Low back pain | 1,090 | 19.9% | 19.9% |
| 2 | Rotator cuff / impingement | 655 | 12.0% | 31.9% |
| 3 | Cervicalgia (neck) | 650 | 11.9% | 43.8% |
| 4 | Knee osteoarthritis | 570 | 10.4% | 54.2% |
| 5 | Sciatica | 428 | 7.8% | 62.0% |

## Q6 — ⭐ Patients at risk of drop-out (flagship)
*Technique: CTE + `LAG()` window function + `CASE WHEN` risk tiering + multi-table
`JOIN`.* This is the query that turns analytics into action. For every **active**
episode it finds the last attended visit (`MAX`), the typical gap between visits
(`LAG` then `AVG`), days since last contact, and remaining sessions — then tiers
the risk.

```sql
WITH visit_gaps AS (
  SELECT care_plan_id, period_start::date AS visit_date,
         LAG(period_start::date) OVER (PARTITION BY care_plan_id
                                       ORDER BY period_start) AS prev_visit
  FROM encounters WHERE status='finished'
),
episode_visits AS (
  SELECT care_plan_id, MAX(visit_date) AS last_visit_date,
         COUNT(*) AS visits_so_far, ROUND(AVG(visit_date - prev_visit),1) AS avg_gap_days
  FROM visit_gaps GROUP BY care_plan_id
)
SELECT p.mrn, c.name AS clinic, cn.display AS diagnosis,
       cp.planned_sessions - cp.attended_sessions AS remaining_sessions,
       (CURRENT_DATE - ev.last_visit_date) AS days_since_last_visit,
       CASE WHEN (CURRENT_DATE - ev.last_visit_date) >= 28 ... THEN 'High'
            WHEN (CURRENT_DATE - ev.last_visit_date) >= 14 ... THEN 'Medium'
            ELSE 'Low' END AS dropout_risk
FROM care_plans cp
JOIN episode_visits ev USING (care_plan_id)
JOIN patients p USING (patient_id)
JOIN clinics c USING (clinic_id)
JOIN conditions cn USING (condition_id)
WHERE cp.status='active' AND cp.attended_sessions < cp.planned_sessions
  AND (CURRENT_DATE - ev.last_visit_date) >= 14;
```

Result: **182 active episodes flagged at risk** — 67 *High* and 115 *Medium* —
representing **~1,600 remaining planned sessions** that are in jeopardy. The
worst cases are long courses (e.g. ACL or frozen-shoulder rehab) with 15+
sessions outstanding and more than two months since the last visit. This list is
the operational output a clinic manager works through every Monday morning. It is
also published as the view `v_dropout_risk`.

## Q7 — Clinical outcomes & MCID achievement by diagnosis
*Technique: CTE/view (`fact_outcome`), `CASE WHEN`, conditional aggregation.*
Reports honest, clinically-grounded recovery using the harmonised 0–100
disability scale and the MCID rule:

| diagnosis | disability in→out | pain in→out | % reach func MCID |
|-----------|-------------------|-------------|-------------------|
| Low back pain | 42.4 → 16.1 | 6.4 → 2.5 | 96.8% |
| Cervicalgia | 38.3 → 15.1 | 6.4 → 2.5 | 97.9% |
| Rotator cuff | 45.0 → 18.9 | 6.4 → 2.7 | 85.9% |
| Frozen shoulder | 46.1 → 23.7 | 6.1 → 3.2 | 81.6% |
| Carpal tunnel | 43.1 → 21.0 | 6.4 → 3.0 | 78.3% |

## Q8 — Therapist outcome scorecard (ranked within clinic)
*Technique: CTE, `RANK() OVER (PARTITION BY clinic …)`, `HAVING` for minimum
case volume.* Ranks each physiotherapist against their peers on MCID rate, with a
≥10-outcome floor so small samples are not over-interpreted — a fairness
safeguard, not a "league table".

## Q9 — Does adherence drive recovery?
*Technique: `CASE WHEN` banding, CTE, aggregation.* The insight that justifies
the entire drop-out workstream (the <50% band is negligible among *completed*
episodes — you have to attend to be discharged):

| adherence band | mean functional improvement | % reach MCID |
|----------------|-----------------------------|--------------|
| 50–69% | 18.9 | 83.3% |
| 70–89% | 22.3 | 91.2% |
| 90–100% | **24.5** | **94.1%** |

Recovery rises monotonically with adherence. Keeping patients engaged is not
just an operational nicety — it is **clinically decisive**.

## Q10 — Monthly new-episode cohorts with running totals
*Technique: window functions — cumulative `SUM() OVER (ORDER BY …)` and a
3-month moving average with `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`.* Used for
demand trend and capacity planning.

---

### SQL techniques coverage

| Technique | Where |
|-----------|-------|
| `JOIN` (multi-table) | Q1, Q3, Q4, Q6, Q8 |
| `GROUP BY` + aggregates | all |
| `CASE WHEN` | Q1, Q2, Q6, Q7, Q9 |
| `FILTER (WHERE …)` | Q1, Q7 |
| CTE (`WITH`) | Q3, Q6, Q8, Q9 |
| Window — `RANK()` | Q5, Q8 |
| Window — `LAG()` | Q6 |
| Window — running `SUM()/AVG()` | Q5, Q10 |
| Ordered-set aggregate (`PERCENTILE_CONT`) | Q4 |
