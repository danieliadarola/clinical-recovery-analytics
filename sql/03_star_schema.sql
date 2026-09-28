-- =============================================================================
-- 03 - Dimensional (star-schema) analytical layer
-- -----------------------------------------------------------------------------
-- The normalised tables in 01 are the operational truth. Power BI, however,
-- performs best on a star schema, so this script exposes conformed dimensions
-- and fact views on top of the core tables. They are defined as VIEWS for
-- portability; in production each would be a MATERIALIZED VIEW (or dbt model)
-- refreshed nightly.
--
-- Grain:
--   fact_appointment  : one row per scheduled appointment
--   fact_encounter    : one row per completed visit
--   fact_outcome      : one row per episode of care (CarePlan) with paired PROMs
-- =============================================================================

SET search_path TO arn;

-- -----------------------------------------------------------------------------
-- DIM_DATE  (calendar spine)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS dim_date CASCADE;
CREATE VIEW dim_date AS
SELECT  d::date                                   AS date_key,
        EXTRACT(YEAR    FROM d)::int              AS year,
        EXTRACT(QUARTER FROM d)::int              AS quarter,
        EXTRACT(MONTH   FROM d)::int              AS month_num,
        TO_CHAR(d, 'YYYY-MM')                     AS year_month,
        TO_CHAR(d, 'Mon')                         AS month_name,
        EXTRACT(ISODOW  FROM d)::int              AS iso_weekday,   -- 1=Mon..7=Sun
        TO_CHAR(d, 'Dy')                          AS weekday_name,
        CASE WHEN EXTRACT(ISODOW FROM d) IN (6,7)
             THEN TRUE ELSE FALSE END             AS is_weekend
FROM generate_series(DATE '2024-01-01', DATE '2026-12-31', INTERVAL '1 day') AS g(d);

-- -----------------------------------------------------------------------------
-- DIM_CLINIC
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS dim_clinic CASCADE;
CREATE VIEW dim_clinic AS
SELECT clinic_id, name AS clinic_name, city, region, postal_code
FROM clinics;

-- -----------------------------------------------------------------------------
-- DIM_PRACTITIONER
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS dim_practitioner CASCADE;
CREATE VIEW dim_practitioner AS
SELECT  p.practitioner_id,
        p.given_name || ' ' || p.family_name      AS practitioner_name,
        p.specialty,
        p.seniority,
        p.clinic_id,
        c.name                                     AS clinic_name,
        p.active
FROM practitioners p
JOIN clinics c USING (clinic_id);

-- -----------------------------------------------------------------------------
-- DIM_PATIENT  (with age band derived from birth_date)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS dim_patient CASCADE;
CREATE VIEW dim_patient AS
SELECT  patient_id,
        mrn,
        gender,
        birth_date,
        DATE_PART('year', AGE(CURRENT_DATE, birth_date))::int AS age,
        CASE
            WHEN DATE_PART('year', AGE(CURRENT_DATE, birth_date)) < 30 THEN '<30'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, birth_date)) < 45 THEN '30-44'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, birth_date)) < 60 THEN '45-59'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, birth_date)) < 75 THEN '60-74'
            ELSE '75+'
        END                                        AS age_band,
        city,
        insurance_type,
        registration_date
FROM patients;

-- -----------------------------------------------------------------------------
-- DIM_DIAGNOSIS  (one row per distinct coded diagnosis + its PROM instrument)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS dim_diagnosis CASCADE;
CREATE VIEW dim_diagnosis AS
SELECT DISTINCT
       icd10_code,
       snomed_code,
       display                                     AS diagnosis_name,
       body_site,
       CASE
           WHEN icd10_code IN ('M54.5','M54.3') THEN 'ODI'
           WHEN icd10_code  = 'M54.2'            THEN 'NDI'
           WHEN icd10_code IN ('M75.1','M75.0','M77.1','G56.0') THEN 'QuickDASH'
           ELSE 'LEFS'
       END                                         AS primary_instrument,
       CASE
           WHEN body_site IN ('Lumbar spine','Cervical spine') THEN 'Spine'
           WHEN body_site IN ('Shoulder','Elbow','Wrist')      THEN 'Upper limb'
           WHEN body_site IN ('Knee','Hip','Ankle','Foot')     THEN 'Lower limb'
           ELSE 'Other'
       END                                         AS body_region
FROM conditions;

-- -----------------------------------------------------------------------------
-- FACT_APPOINTMENT  (scheduling grain, with operational flags)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS fact_appointment CASCADE;
CREATE VIEW fact_appointment AS
SELECT  a.appointment_id,
        a.patient_id,
        a.practitioner_id,
        a.clinic_id,
        a.care_plan_id,
        a.appointment_type,
        a.status,
        a.scheduled_date,
        EXTRACT(ISODOW FROM a.scheduled_date)::int AS iso_weekday,
        EXTRACT(HOUR FROM a.scheduled_start)::int  AS hour_of_day,
        a.lead_time_days,
        CASE
            WHEN a.lead_time_days <= 2  THEN '0-2 days'
            WHEN a.lead_time_days <= 7  THEN '3-7 days'
            WHEN a.lead_time_days <= 13 THEN '8-13 days'
            ELSE '14+ days'
        END                                        AS lead_time_band,
        a.session_number,
        a.cancellation_reason,
        CASE WHEN a.status = 'fulfilled' THEN 1 ELSE 0 END AS is_attended,
        CASE WHEN a.status = 'noshow'    THEN 1 ELSE 0 END AS is_noshow,
        CASE WHEN a.status = 'cancelled' THEN 1 ELSE 0 END AS is_cancelled,
        -- "completed" = appointment that reached a resolution (not future-booked)
        CASE WHEN a.status IN ('fulfilled','noshow','cancelled') THEN 1 ELSE 0 END AS is_resolved
FROM appointments a;

-- -----------------------------------------------------------------------------
-- FACT_ENCOUNTER  (delivered-care grain)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS fact_encounter CASCADE;
CREATE VIEW fact_encounter AS
SELECT  e.encounter_id,
        e.patient_id,
        e.practitioner_id,
        e.clinic_id,
        e.care_plan_id,
        e.condition_id,
        e.encounter_type,
        e.period_start::date                       AS encounter_date,
        e.duration_min
FROM encounters e
WHERE e.status = 'finished';

-- -----------------------------------------------------------------------------
-- FACT_OUTCOME  (episode grain: paired baseline/discharge PROMs + adherence)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS fact_outcome CASCADE;
CREATE VIEW fact_outcome AS
WITH proms AS (   -- pivot the long observation table to one row per episode
    SELECT
        care_plan_id,
        MAX(instrument) FILTER (WHERE instrument <> 'NPRS')                          AS func_instrument,
        MAX(value_numeric) FILTER (WHERE instrument <> 'NPRS' AND measure_point='baseline')  AS func_baseline,
        MAX(value_numeric) FILTER (WHERE instrument <> 'NPRS' AND measure_point='discharge') AS func_discharge,
        MAX(value_numeric) FILTER (WHERE instrument = 'NPRS' AND measure_point='baseline')   AS pain_baseline,
        MAX(value_numeric) FILTER (WHERE instrument = 'NPRS' AND measure_point='discharge')  AS pain_discharge
    FROM observations
    GROUP BY care_plan_id
)
SELECT
    cp.care_plan_id,
    cp.patient_id,
    cp.clinic_id,
    cp.lead_practitioner_id                         AS practitioner_id,
    cp.condition_id,
    cn.icd10_code,
    cn.display                                       AS diagnosis_name,
    cp.status                                        AS episode_status,
    cp.period_start                                  AS episode_start,
    cp.discharge_date,
    cp.planned_sessions,
    cp.attended_sessions,
    -- adherence = attended / planned, capped at 100%
    ROUND(LEAST(cp.attended_sessions::numeric / NULLIF(cp.planned_sessions,0), 1.0), 3) AS adherence_ratio,
    -- length of stay in days (discharge - start) for completed episodes
    CASE WHEN cp.discharge_date IS NOT NULL
         THEN (cp.discharge_date - cp.period_start) END AS los_days,
    pr.func_instrument,
    pr.func_baseline,
    pr.func_discharge,
    -- harmonise every instrument to a 0-100 "disability" scale (higher = worse)
    CASE WHEN pr.func_instrument = 'LEFS'
         THEN ROUND((80 - pr.func_baseline)  / 80 * 100, 1)
         ELSE pr.func_baseline END                   AS disability_baseline,
    CASE WHEN pr.func_instrument = 'LEFS'
         THEN ROUND((80 - pr.func_discharge) / 80 * 100, 1)
         ELSE pr.func_discharge END                  AS disability_discharge,
    pr.pain_baseline,
    pr.pain_discharge,
    -- raw improvement in the instrument's own clinically-meaningful direction
    CASE
        WHEN pr.func_instrument = 'LEFS' THEN pr.func_discharge - pr.func_baseline
        ELSE pr.func_baseline - pr.func_discharge
    END                                              AS func_improvement,
    (pr.pain_baseline - pr.pain_discharge)           AS pain_improvement,
    -- Minimal Clinically Important Difference (MCID) per instrument
    CASE pr.func_instrument
        WHEN 'ODI' THEN 10 WHEN 'NDI' THEN 7
        WHEN 'QuickDASH' THEN 15 WHEN 'LEFS' THEN 9
    END                                              AS func_mcid,
    CASE
        WHEN pr.func_discharge IS NULL THEN NULL
        WHEN (CASE WHEN pr.func_instrument='LEFS'
                   THEN pr.func_discharge - pr.func_baseline
                   ELSE pr.func_baseline - pr.func_discharge END)
             >= (CASE pr.func_instrument WHEN 'ODI' THEN 10 WHEN 'NDI' THEN 7
                      WHEN 'QuickDASH' THEN 15 WHEN 'LEFS' THEN 9 END)
        THEN 1 ELSE 0
    END                                              AS func_mcid_achieved,
    CASE
        WHEN pr.pain_discharge IS NULL THEN NULL
        WHEN (pr.pain_baseline - pr.pain_discharge) >= 2 THEN 1 ELSE 0
    END                                              AS pain_mcid_achieved
FROM care_plans cp
JOIN conditions cn ON cn.condition_id = cp.condition_id
LEFT JOIN proms pr ON pr.care_plan_id = cp.care_plan_id;

COMMENT ON VIEW fact_outcome IS
  'Episode-level outcomes: adherence, length of stay, paired PROMs harmonised to a 0-100 disability scale, and MCID achievement flags.';
