-- =============================================================================
-- 04 - Analytical queries (the business questions)
-- -----------------------------------------------------------------------------
-- Each query answers a real operational or clinical question for the ARN.
-- Techniques are flagged in the header: [JOIN] [GROUP BY] [CASE WHEN] [CTE]
-- [WINDOW]. Written for PostgreSQL 14+. Run after 01-03.
-- =============================================================================

SET search_path TO arn;

-- -----------------------------------------------------------------------------
-- Q1. No-show and cancellation rate by clinic and month
--     "Where and when are we losing capacity?"          [JOIN][GROUP BY][CASE]
-- -----------------------------------------------------------------------------
SELECT
    c.name                                                   AS clinic,
    TO_CHAR(a.scheduled_date, 'YYYY-MM')                     AS year_month,
    COUNT(*) FILTER (WHERE a.status IN ('fulfilled','noshow','cancelled')) AS booked_resolved,
    ROUND(100.0 * COUNT(*) FILTER (WHERE a.status = 'noshow')
          / NULLIF(COUNT(*) FILTER (WHERE a.status IN ('fulfilled','noshow','cancelled')),0), 1) AS noshow_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE a.status = 'cancelled')
          / NULLIF(COUNT(*) FILTER (WHERE a.status IN ('fulfilled','noshow','cancelled')),0), 1) AS cancel_pct
FROM appointments a
JOIN clinics c ON c.clinic_id = a.clinic_id
GROUP BY c.name, TO_CHAR(a.scheduled_date, 'YYYY-MM')
ORDER BY clinic, year_month;

-- -----------------------------------------------------------------------------
-- Q2. No-show drivers: lead-time band x weekday
--     "Do appointments booked far ahead get missed more?"   [CASE][GROUP BY]
-- -----------------------------------------------------------------------------
SELECT
    CASE
        WHEN lead_time_days <= 2  THEN '0-2 days'
        WHEN lead_time_days <= 7  THEN '3-7 days'
        WHEN lead_time_days <= 13 THEN '8-13 days'
        ELSE '14+ days'
    END                                                      AS lead_time_band,
    TO_CHAR(scheduled_date, 'Dy')                            AS weekday,
    COUNT(*)                                                 AS appts,
    ROUND(100.0 * SUM(CASE WHEN status='noshow' THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*),0), 1)                           AS noshow_pct
FROM appointments
WHERE status IN ('fulfilled','noshow','cancelled')
GROUP BY 1, 2, EXTRACT(ISODOW FROM scheduled_date)
ORDER BY lead_time_band, EXTRACT(ISODOW FROM scheduled_date);

-- -----------------------------------------------------------------------------
-- Q3. Treatment adherence by clinic
--     "What share of episodes complete >= 80% of planned sessions?"  [CTE][JOIN]
-- -----------------------------------------------------------------------------
WITH episode_adherence AS (
    SELECT cp.clinic_id,
           cp.care_plan_id,
           cp.attended_sessions::numeric
               / NULLIF(cp.planned_sessions,0)              AS adherence_ratio
    FROM care_plans cp
    WHERE cp.status IN ('completed','revoked')               -- closed episodes only
)
SELECT
    c.name                                                   AS clinic,
    COUNT(*)                                                 AS closed_episodes,
    ROUND(AVG(adherence_ratio) * 100, 1)                     AS mean_adherence_pct,
    ROUND(100.0 * SUM(CASE WHEN adherence_ratio >= 0.80 THEN 1 ELSE 0 END)
          / COUNT(*), 1)                                     AS pct_adherent_episodes
FROM episode_adherence ea
JOIN clinics c ON c.clinic_id = ea.clinic_id
GROUP BY c.name
ORDER BY pct_adherent_episodes DESC;

-- -----------------------------------------------------------------------------
-- Q4. Mean time to discharge by diagnosis (length of stay)
--     "How long does each condition take to resolve?"  [JOIN][GROUP BY][WINDOW]
-- -----------------------------------------------------------------------------
SELECT
    cn.display                                               AS diagnosis,
    COUNT(*)                                                 AS discharged_episodes,
    ROUND(AVG(cp.discharge_date - cp.period_start), 1)       AS mean_los_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP
        (ORDER BY (cp.discharge_date - cp.period_start))     AS median_los_days,
    ROUND(AVG(cp.attended_sessions), 1)                      AS mean_sessions
FROM care_plans cp
JOIN conditions cn ON cn.condition_id = cp.condition_id
WHERE cp.status = 'completed' AND cp.discharge_date IS NOT NULL
GROUP BY cn.display
ORDER BY mean_los_days DESC;

-- -----------------------------------------------------------------------------
-- Q5. Most frequent diagnoses, ranked, with share of total   [WINDOW][GROUP BY]
-- -----------------------------------------------------------------------------
SELECT
    icd10_code,
    display                                                  AS diagnosis,
    COUNT(*)                                                 AS episodes,
    RANK() OVER (ORDER BY COUNT(*) DESC)                     AS frequency_rank,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)       AS pct_of_total,
    ROUND(100.0 * SUM(COUNT(*)) OVER (ORDER BY COUNT(*) DESC) -- cumulative %
          / SUM(COUNT(*)) OVER (), 1)                        AS cumulative_pct
FROM conditions
GROUP BY icd10_code, display
ORDER BY episodes DESC;

-- -----------------------------------------------------------------------------
-- Q6. *** Patients at risk of drop-out ***  (the flagship operational query)
--     Active episodes whose last attended visit is long past while planned
--     sessions remain.                                  [CTE][WINDOW][CASE][JOIN]
-- -----------------------------------------------------------------------------
WITH visit_gaps AS (
    SELECT  care_plan_id,
            period_start::date                              AS visit_date,
            LAG(period_start::date) OVER (PARTITION BY care_plan_id
                                          ORDER BY period_start) AS prev_visit
    FROM encounters
    WHERE status = 'finished'
),
episode_visits AS (
    SELECT  care_plan_id,
            MAX(visit_date)                                  AS last_visit_date,
            COUNT(*)                                         AS visits_so_far,
            ROUND(AVG(visit_date - prev_visit), 1)           AS avg_gap_days
    FROM visit_gaps
    GROUP BY care_plan_id
)
SELECT
    cp.care_plan_id,
    p.mrn,
    c.name                                                   AS clinic,
    cn.display                                               AS diagnosis,
    cp.planned_sessions,
    cp.attended_sessions,
    cp.planned_sessions - cp.attended_sessions              AS remaining_sessions,
    ev.last_visit_date,
    (CURRENT_DATE - ev.last_visit_date)                     AS days_since_last_visit,
    ev.avg_gap_days,
    CASE
        WHEN (CURRENT_DATE - ev.last_visit_date) >= 28
             AND cp.attended_sessions < cp.planned_sessions THEN 'High'
        WHEN (CURRENT_DATE - ev.last_visit_date) >= 14
             AND cp.attended_sessions < cp.planned_sessions THEN 'Medium'
        ELSE 'Low'
    END                                                      AS dropout_risk
FROM care_plans cp
JOIN episode_visits ev ON ev.care_plan_id = cp.care_plan_id
JOIN patients p   ON p.patient_id = cp.patient_id
JOIN clinics  c   ON c.clinic_id  = cp.clinic_id
JOIN conditions cn ON cn.condition_id = cp.condition_id
WHERE cp.status = 'active'
  AND (CURRENT_DATE - ev.last_visit_date) >= 14
  AND cp.attended_sessions < cp.planned_sessions
ORDER BY days_since_last_visit DESC, remaining_sessions DESC;

-- -----------------------------------------------------------------------------
-- Q7. Clinical outcomes & MCID achievement by diagnosis    [CTE][CASE][GROUP BY]
--     Uses the harmonised 0-100 disability scale from fact_outcome.
-- -----------------------------------------------------------------------------
SELECT
    diagnosis_name                                           AS diagnosis,
    COUNT(*) FILTER (WHERE func_discharge IS NOT NULL)       AS episodes_with_outcome,
    ROUND(AVG(disability_baseline)  FILTER (WHERE func_discharge IS NOT NULL), 1) AS mean_disability_in,
    ROUND(AVG(disability_discharge) FILTER (WHERE func_discharge IS NOT NULL), 1) AS mean_disability_out,
    ROUND(AVG(pain_baseline)  FILTER (WHERE pain_discharge IS NOT NULL), 1)       AS mean_pain_in,
    ROUND(AVG(pain_discharge) FILTER (WHERE pain_discharge IS NOT NULL), 1)       AS mean_pain_out,
    ROUND(100.0 * AVG(func_mcid_achieved), 1)               AS pct_reaching_func_mcid,
    ROUND(100.0 * AVG(pain_mcid_achieved), 1)               AS pct_reaching_pain_mcid
FROM fact_outcome
GROUP BY diagnosis_name
ORDER BY episodes_with_outcome DESC;

-- -----------------------------------------------------------------------------
-- Q8. Therapist outcome scorecard, ranked within each clinic   [WINDOW][CTE]
-- -----------------------------------------------------------------------------
WITH therapist_stats AS (
    SELECT
        fo.practitioner_id,
        fo.clinic_id,
        COUNT(*) FILTER (WHERE fo.func_discharge IS NOT NULL) AS outcomes,
        AVG(fo.func_mcid_achieved)                            AS mcid_rate,
        AVG(fo.adherence_ratio)                               AS adherence
    FROM fact_outcome fo
    GROUP BY fo.practitioner_id, fo.clinic_id
    HAVING COUNT(*) FILTER (WHERE fo.func_discharge IS NOT NULL) >= 10
)
SELECT
    dp.practitioner_name,
    dp.clinic_name,
    ts.outcomes,
    ROUND(100.0 * ts.mcid_rate, 1)                           AS mcid_pct,
    ROUND(100.0 * ts.adherence, 1)                           AS adherence_pct,
    RANK() OVER (PARTITION BY ts.clinic_id
                 ORDER BY ts.mcid_rate DESC)                 AS rank_in_clinic
FROM therapist_stats ts
JOIN dim_practitioner dp ON dp.practitioner_id = ts.practitioner_id
ORDER BY dp.clinic_name, rank_in_clinic;

-- -----------------------------------------------------------------------------
-- Q9. Does adherence drive recovery?  (actionable relationship)   [CASE][CTE]
-- -----------------------------------------------------------------------------
WITH banded AS (
    SELECT
        CASE
            WHEN adherence_ratio < 0.50 THEN '1. <50%'
            WHEN adherence_ratio < 0.70 THEN '2. 50-69%'
            WHEN adherence_ratio < 0.90 THEN '3. 70-89%'
            ELSE '4. 90-100%'
        END                                                  AS adherence_band,
        func_mcid_achieved,
        func_improvement
    FROM fact_outcome
    WHERE func_discharge IS NOT NULL
)
SELECT
    adherence_band,
    COUNT(*)                                                 AS episodes,
    ROUND(AVG(func_improvement), 1)                          AS mean_func_improvement,
    ROUND(100.0 * AVG(func_mcid_achieved), 1)               AS pct_reaching_mcid
FROM banded
GROUP BY adherence_band
ORDER BY adherence_band;

-- -----------------------------------------------------------------------------
-- Q10. Monthly new episodes with running cumulative total      [WINDOW]
-- -----------------------------------------------------------------------------
SELECT
    TO_CHAR(period_start, 'YYYY-MM')                         AS cohort_month,
    COUNT(*)                                                 AS new_episodes,
    SUM(COUNT(*)) OVER (ORDER BY TO_CHAR(period_start, 'YYYY-MM')) AS cumulative_episodes,
    ROUND(AVG(COUNT(*)) OVER (ORDER BY TO_CHAR(period_start, 'YYYY-MM')
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0)  AS rolling_3m_avg
FROM care_plans
GROUP BY TO_CHAR(period_start, 'YYYY-MM')
ORDER BY cohort_month;
