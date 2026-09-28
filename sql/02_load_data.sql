-- =============================================================================
-- 02 - Load the synthetic dataset (PostgreSQL / psql)
-- -----------------------------------------------------------------------------
-- Run with:  psql -d arn_db -f sql/01_schema_ddl.sql
--            psql -d arn_db -f sql/02_load_data.sql
--
-- Uses client-side \copy so paths are relative to where psql is launched
-- (the repository root). The CSV files are produced by
-- data/generate_synthetic_data.py.
--
-- The circular FK conditions.encounter_id -> encounters is dropped before the
-- bulk load and recreated afterwards, so rows can be loaded in dependency order.
-- =============================================================================

SET search_path TO arn;

BEGIN;

ALTER TABLE conditions DROP CONSTRAINT IF EXISTS fk_condition_encounter;

\copy clinics       FROM 'data/clinics.csv'       WITH (FORMAT csv, HEADER true);
\copy practitioners FROM 'data/practitioners.csv' WITH (FORMAT csv, HEADER true);
\copy patients      FROM 'data/patients.csv'      WITH (FORMAT csv, HEADER true);
\copy conditions    FROM 'data/conditions.csv'    WITH (FORMAT csv, HEADER true, NULL '');
\copy care_plans    FROM 'data/care_plans.csv'    WITH (FORMAT csv, HEADER true, NULL '');
\copy appointments  FROM 'data/appointments.csv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy encounters    FROM 'data/encounters.csv'    WITH (FORMAT csv, HEADER true, NULL '');
\copy observations  FROM 'data/observations.csv'  WITH (FORMAT csv, HEADER true, NULL '');

ALTER TABLE conditions
    ADD CONSTRAINT fk_condition_encounter
    FOREIGN KEY (encounter_id) REFERENCES encounters(encounter_id);

COMMIT;

-- Quick row-count sanity check
SELECT 'clinics'       AS table_name, COUNT(*) FROM clinics
UNION ALL SELECT 'practitioners', COUNT(*) FROM practitioners
UNION ALL SELECT 'patients',      COUNT(*) FROM patients
UNION ALL SELECT 'conditions',    COUNT(*) FROM conditions
UNION ALL SELECT 'care_plans',    COUNT(*) FROM care_plans
UNION ALL SELECT 'appointments',  COUNT(*) FROM appointments
UNION ALL SELECT 'encounters',    COUNT(*) FROM encounters
UNION ALL SELECT 'observations',  COUNT(*) FROM observations;
