-- =============================================================================
-- 05 - KPI views consumed by Power BI
-- -----------------------------------------------------------------------------
-- Thin, BI-friendly views. Power BI imports these (or the fact/dim views in 03)
-- and the DAX layer in /powerbi adds time-intelligence on top. Run after 01-03.
-- =============================================================================

SET search_path TO arn;

-- -----------------------------------------------------------------------------
-- Executive KPI trend (one row per month)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_kpi_executive_monthly CASCADE;
CREATE VIEW v_kpi_executive_monthly AS
WITH appt AS (
    SELECT TO_CHAR(scheduled_date,'YYYY-MM') AS ym,
           COUNT(*) FILTER (WHERE status IN ('fulfilled','noshow','cancelled')) AS resolved,
           COUNT(*) FILTER (WHERE status='noshow')    AS noshow,
           COUNT(*) FILTER (WHERE status='cancelled') AS cancelled,
           COUNT(*) FILTER (WHERE status='fulfilled') AS attended
    FROM appointments GROUP BY 1
),
eps AS (
    SELECT TO_CHAR(period_start,'YYYY-MM') AS ym,
           COUNT(*) AS new_episodes
    FROM care_plans GROUP BY 1
),
disch AS (
    SELECT TO_CHAR(discharge_date,'YYYY-MM') AS ym,
           COUNT(*) AS discharges,
           ROUND(AVG(func_mcid_achieved)*100,1) AS mcid_pct
    FROM fact_outcome WHERE discharge_date IS NOT NULL GROUP BY 1
)
SELECT
    COALESCE(appt.ym, eps.ym, disch.ym)                       AS year_month,
    appt.attended, appt.noshow, appt.cancelled,
    ROUND(100.0*appt.noshow   /NULLIF(appt.resolved,0),1)     AS noshow_pct,
    ROUND(100.0*appt.cancelled/NULLIF(appt.resolved,0),1)     AS cancel_pct,
    eps.new_episodes,
    disch.discharges,
    disch.mcid_pct
FROM appt
FULL JOIN eps   ON eps.ym   = appt.ym
FULL JOIN disch ON disch.ym = appt.ym
ORDER BY 1;

-- -----------------------------------------------------------------------------
-- Clinic scorecard (one row per clinic)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_kpi_clinic_scorecard CASCADE;
CREATE VIEW v_kpi_clinic_scorecard AS
SELECT
    c.clinic_id,
    c.name AS clinic,
    c.city,
    ROUND(100.0 * SUM(fa.is_noshow)   / NULLIF(SUM(fa.is_resolved),0),1) AS noshow_pct,
    ROUND(100.0 * SUM(fa.is_cancelled)/ NULLIF(SUM(fa.is_resolved),0),1) AS cancel_pct,
    (SELECT ROUND(AVG(adherence_ratio)*100,1) FROM fact_outcome fo
       WHERE fo.clinic_id=c.clinic_id AND fo.episode_status IN ('completed','revoked')) AS mean_adherence_pct,
    (SELECT ROUND(AVG(func_mcid_achieved)*100,1) FROM fact_outcome fo
       WHERE fo.clinic_id=c.clinic_id) AS mcid_pct,
    (SELECT ROUND(AVG(discharge_date - episode_start),1) FROM fact_outcome fo
       WHERE fo.clinic_id=c.clinic_id AND fo.discharge_date IS NOT NULL) AS mean_los_days
FROM clinics c
JOIN fact_appointment fa ON fa.clinic_id = c.clinic_id
GROUP BY c.clinic_id, c.name, c.city
ORDER BY noshow_pct DESC;

-- -----------------------------------------------------------------------------
-- Outcomes by diagnosis (clinical dashboard)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_outcomes_by_diagnosis CASCADE;
CREATE VIEW v_outcomes_by_diagnosis AS
SELECT
    icd10_code,
    diagnosis_name,
    COUNT(*)                                              AS episodes,
    COUNT(*) FILTER (WHERE func_discharge IS NOT NULL)    AS episodes_with_outcome,
    ROUND(AVG(disability_baseline)  FILTER (WHERE func_discharge IS NOT NULL),1) AS disability_in,
    ROUND(AVG(disability_discharge) FILTER (WHERE func_discharge IS NOT NULL),1) AS disability_out,
    ROUND(AVG(pain_baseline)  FILTER (WHERE pain_discharge IS NOT NULL),1)       AS pain_in,
    ROUND(AVG(pain_discharge) FILTER (WHERE pain_discharge IS NOT NULL),1)       AS pain_out,
    ROUND(100.0*AVG(func_mcid_achieved),1)               AS func_mcid_pct,
    ROUND(AVG(discharge_date - episode_start) FILTER (WHERE discharge_date IS NOT NULL),1) AS mean_los_days
FROM fact_outcome
GROUP BY icd10_code, diagnosis_name
ORDER BY episodes DESC;

-- -----------------------------------------------------------------------------
-- Drop-out risk register (operational dashboard) - reusable view of Q6
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_dropout_risk CASCADE;
CREATE VIEW v_dropout_risk AS
WITH episode_visits AS (
    SELECT care_plan_id,
           MAX(period_start::date) AS last_visit_date,
           COUNT(*)                AS visits_so_far
    FROM encounters WHERE status='finished'
    GROUP BY care_plan_id
)
SELECT
    cp.care_plan_id, p.mrn, c.name AS clinic, cn.display AS diagnosis,
    dp.practitioner_name,
    cp.planned_sessions, cp.attended_sessions,
    cp.planned_sessions - cp.attended_sessions           AS remaining_sessions,
    ev.last_visit_date,
    (CURRENT_DATE - ev.last_visit_date)                  AS days_since_last_visit,
    CASE
        WHEN (CURRENT_DATE - ev.last_visit_date) >= 28 THEN 'High'
        WHEN (CURRENT_DATE - ev.last_visit_date) >= 14 THEN 'Medium'
        ELSE 'Low'
    END                                                  AS dropout_risk
FROM care_plans cp
JOIN episode_visits ev ON ev.care_plan_id = cp.care_plan_id
JOIN patients p   ON p.patient_id = cp.patient_id
JOIN clinics  c   ON c.clinic_id  = cp.clinic_id
JOIN conditions cn ON cn.condition_id = cp.condition_id
LEFT JOIN dim_practitioner dp ON dp.practitioner_id = cp.lead_practitioner_id
WHERE cp.status='active' AND cp.attended_sessions < cp.planned_sessions;
