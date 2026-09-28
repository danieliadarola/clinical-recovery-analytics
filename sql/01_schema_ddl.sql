-- =============================================================================
-- Clinical Recovery Analytics Platform  |  Atlas Rehabilitation Network (ARN)
-- 01 - Core relational schema (PostgreSQL 14+)
-- -----------------------------------------------------------------------------
-- This is the normalised "silver" layer produced by flattening FHIR R4
-- resources (see /docs/03_extraction_normalization.md for the mapping).
-- Each table corresponds to one FHIR resource type. Surrogate integer keys
-- mirror the FHIR logical id; business identifiers (MRN, licence, codes) are
-- kept as attributes.
--
-- Load order matters because of foreign keys. The cross-reference between
-- conditions and encounters is circular (a Condition is recorded *during* an
-- Encounter, while an Encounter references the Condition it addresses), so that
-- single FK is added at the end with ALTER TABLE.
-- =============================================================================

DROP SCHEMA IF EXISTS arn CASCADE;
CREATE SCHEMA arn;
SET search_path TO arn;

-- -----------------------------------------------------------------------------
-- ORGANIZATION / LOCATION  (FHIR: Organization + Location)
-- -----------------------------------------------------------------------------
CREATE TABLE clinics (
    clinic_id     INTEGER     PRIMARY KEY,
    name          TEXT        NOT NULL,
    city          TEXT        NOT NULL,
    region        TEXT        NOT NULL,
    postal_code   TEXT
);
COMMENT ON TABLE  clinics IS 'Physiotherapy clinics in the ARN network (FHIR Organization/Location).';

-- -----------------------------------------------------------------------------
-- PRACTITIONER  (FHIR: Practitioner + PractitionerRole)
-- -----------------------------------------------------------------------------
CREATE TABLE practitioners (
    practitioner_id INTEGER   PRIMARY KEY,
    license_number  TEXT      NOT NULL,          -- professional college number
    given_name      TEXT      NOT NULL,
    family_name     TEXT      NOT NULL,
    gender          TEXT,
    specialty       TEXT,                         -- PractitionerRole.specialty
    seniority       TEXT,
    clinic_id       INTEGER   NOT NULL REFERENCES clinics(clinic_id),
    active          BOOLEAN   DEFAULT TRUE
);
COMMENT ON TABLE practitioners IS 'Physiotherapists (FHIR Practitioner + PractitionerRole).';

-- -----------------------------------------------------------------------------
-- PATIENT  (FHIR: Patient)
-- -----------------------------------------------------------------------------
CREATE TABLE patients (
    patient_id        INTEGER PRIMARY KEY,
    mrn               TEXT    NOT NULL UNIQUE,    -- medical record number
    given_name        TEXT,
    family_name       TEXT,
    gender            TEXT,                        -- male | female | other | unknown
    birth_date        DATE,
    postal_code       TEXT,
    city              TEXT,
    insurance_type    TEXT,
    registration_date DATE
);
COMMENT ON TABLE patients IS 'Patients (FHIR Patient). MRN is the business identifier.';

-- -----------------------------------------------------------------------------
-- CONDITION  (FHIR: Condition)  - the clinical diagnosis driving the episode
-- -----------------------------------------------------------------------------
CREATE TABLE conditions (
    condition_id    INTEGER   PRIMARY KEY,
    patient_id      INTEGER   NOT NULL REFERENCES patients(patient_id),
    encounter_id    INTEGER,                       -- FK added after load (circular)
    icd10_code      TEXT,
    snomed_code     TEXT,
    display         TEXT      NOT NULL,
    body_site       TEXT,
    category        TEXT,                          -- encounter-diagnosis | problem-list-item
    clinical_status TEXT,                          -- active | resolved | inactive
    onset_date      DATE,
    recorded_date   DATE
);
COMMENT ON TABLE conditions IS 'Diagnoses (FHIR Condition), ICD-10 + SNOMED CT coded.';

-- -----------------------------------------------------------------------------
-- CARE PLAN  (FHIR: CarePlan)  - the rehabilitation episode
-- -----------------------------------------------------------------------------
CREATE TABLE care_plans (
    care_plan_id        INTEGER PRIMARY KEY,
    patient_id          INTEGER NOT NULL REFERENCES patients(patient_id),
    condition_id        INTEGER NOT NULL REFERENCES conditions(condition_id),
    lead_practitioner_id INTEGER REFERENCES practitioners(practitioner_id),
    clinic_id           INTEGER REFERENCES clinics(clinic_id),
    status              TEXT,                       -- active | completed | revoked
    intent              TEXT,                       -- plan | order
    title               TEXT,
    goal_description    TEXT,                       -- CarePlan.goal
    planned_sessions    INTEGER,                    -- planned activity count
    attended_sessions   INTEGER,                    -- derived (attended encounters)
    period_start        DATE,
    period_end          DATE,
    discharge_date      DATE,
    discharge_reason    TEXT
);
COMMENT ON TABLE care_plans IS 'Rehabilitation episode of care (FHIR CarePlan). One per Condition treated.';

-- -----------------------------------------------------------------------------
-- APPOINTMENT  (FHIR: Appointment)  - scheduling / demand layer
-- -----------------------------------------------------------------------------
CREATE TABLE appointments (
    appointment_id      INTEGER PRIMARY KEY,
    patient_id          INTEGER NOT NULL REFERENCES patients(patient_id),
    practitioner_id     INTEGER REFERENCES practitioners(practitioner_id),
    clinic_id           INTEGER REFERENCES clinics(clinic_id),
    care_plan_id        INTEGER REFERENCES care_plans(care_plan_id),
    appointment_type    TEXT,                       -- initial | follow-up
    service_type        TEXT,
    status              TEXT,                       -- booked|fulfilled|cancelled|noshow
    scheduled_date      DATE,
    scheduled_start     TIMESTAMPTZ,
    created_date        DATE,                        -- when the booking was made
    lead_time_days      INTEGER,                     -- scheduled_date - created_date
    session_number      INTEGER,                     -- nth session in the episode
    cancellation_reason TEXT
);
COMMENT ON TABLE appointments IS 'Scheduled visits (FHIR Appointment). Status drives no-show/cancellation KPIs.';

-- -----------------------------------------------------------------------------
-- ENCOUNTER  (FHIR: Encounter)  - the visit that actually happened
-- -----------------------------------------------------------------------------
CREATE TABLE encounters (
    encounter_id    INTEGER   PRIMARY KEY,
    appointment_id  INTEGER   REFERENCES appointments(appointment_id),
    patient_id      INTEGER   NOT NULL REFERENCES patients(patient_id),
    practitioner_id INTEGER   REFERENCES practitioners(practitioner_id),
    clinic_id       INTEGER   REFERENCES clinics(clinic_id),
    care_plan_id    INTEGER   REFERENCES care_plans(care_plan_id),
    condition_id    INTEGER   REFERENCES conditions(condition_id),
    encounter_class TEXT,                            -- AMB (ambulatory)
    encounter_type  TEXT,                            -- initial-evaluation|treatment|discharge
    status          TEXT,                            -- finished | cancelled | in-progress
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    duration_min    INTEGER
);
COMMENT ON TABLE encounters IS 'Completed clinical visits (FHIR Encounter). One per fulfilled Appointment.';

-- -----------------------------------------------------------------------------
-- OBSERVATION  (FHIR: Observation)  - PROMs / standardized outcome measures
-- -----------------------------------------------------------------------------
CREATE TABLE observations (
    observation_id      INTEGER  PRIMARY KEY,
    patient_id          INTEGER  NOT NULL REFERENCES patients(patient_id),
    encounter_id        INTEGER  REFERENCES encounters(encounter_id),
    care_plan_id        INTEGER  REFERENCES care_plans(care_plan_id),
    loinc_code          TEXT,                        -- LOINC code of the instrument
    instrument          TEXT,                        -- NPRS|ODI|NDI|QuickDASH|LEFS
    measure_point       TEXT,                        -- baseline | interim | discharge
    value_numeric       NUMERIC(6,2),
    unit                TEXT,                         -- UCUM
    status              TEXT,                         -- final | preliminary | amended
    effective_datetime  TIMESTAMPTZ
);
COMMENT ON TABLE observations IS 'Patient-Reported Outcome Measures (FHIR Observation), LOINC coded.';

-- -----------------------------------------------------------------------------
-- Deferred / circular foreign key: Condition recorded during an Encounter
-- -----------------------------------------------------------------------------
ALTER TABLE conditions
    ADD CONSTRAINT fk_condition_encounter
    FOREIGN KEY (encounter_id) REFERENCES encounters(encounter_id);

-- -----------------------------------------------------------------------------
-- Indexes for analytical workloads (joins + filters used by the dashboards)
-- -----------------------------------------------------------------------------
CREATE INDEX idx_appt_clinic_date   ON appointments (clinic_id, scheduled_date);
CREATE INDEX idx_appt_status        ON appointments (status);
CREATE INDEX idx_appt_careplan      ON appointments (care_plan_id);
CREATE INDEX idx_enc_clinic_date    ON encounters (clinic_id, period_start);
CREATE INDEX idx_enc_careplan       ON encounters (care_plan_id);
CREATE INDEX idx_enc_practitioner   ON encounters (practitioner_id);
CREATE INDEX idx_obs_careplan_point ON observations (care_plan_id, measure_point);
CREATE INDEX idx_cp_clinic_status   ON care_plans (clinic_id, status);
CREATE INDEX idx_cond_codes         ON conditions (icd10_code, snomed_code);
