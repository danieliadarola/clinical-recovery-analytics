# Data Dictionary

The core (silver) tables produced by flattening FHIR R4 resources, plus the
analytical (gold) views. Types are PostgreSQL; `PK` = primary key, `FK` = foreign
key. Source DDL: [`/sql/01_schema_ddl.sql`](../sql/01_schema_ddl.sql);
gold layer: [`/sql/03_star_schema.sql`](../sql/03_star_schema.sql).

## Core tables (one per FHIR resource)

### `clinics`  (FHIR Organization / Location)
| column | type | notes |
|--------|------|-------|
| clinic_id | INTEGER `PK` | surrogate id |
| name | TEXT | clinic name |
| city, region | TEXT | location |
| postal_code | TEXT | |

### `practitioners`  (FHIR Practitioner / PractitionerRole)
| column | type | notes |
|--------|------|-------|
| practitioner_id | INTEGER `PK` | |
| license_number | TEXT | professional college number |
| given_name, family_name | TEXT | |
| gender | TEXT | |
| specialty | TEXT | MSK / sports / orthopaedic / geriatric / neuro |
| seniority | TEXT | Junior / Senior / Lead |
| clinic_id | INTEGER `FK`→clinics | base clinic |
| active | BOOLEAN | |

### `patients`  (FHIR Patient)
| column | type | notes |
|--------|------|-------|
| patient_id | INTEGER `PK` | |
| mrn | TEXT `UNIQUE` | medical record number (business key) |
| given_name, family_name | TEXT | synthetic |
| gender | TEXT | male / female / other / unknown |
| birth_date | DATE | |
| postal_code, city | TEXT | minimised address |
| insurance_type | TEXT | Public (SNS) / Private insurance / Self-pay |
| registration_date | DATE | |

### `conditions`  (FHIR Condition)
| column | type | notes |
|--------|------|-------|
| condition_id | INTEGER `PK` | |
| patient_id | INTEGER `FK`→patients | |
| encounter_id | INTEGER `FK`→encounters | encounter where recorded (added post-load) |
| icd10_code | TEXT | billing/administrative code |
| snomed_code | TEXT | clinical code |
| display | TEXT | diagnosis name |
| body_site | TEXT | anatomical site |
| category | TEXT | encounter-diagnosis |
| clinical_status | TEXT | active / resolved / inactive |
| onset_date, recorded_date | DATE | |

### `care_plans`  (FHIR CarePlan — the episode of care)
| column | type | notes |
|--------|------|-------|
| care_plan_id | INTEGER `PK` | |
| patient_id | INTEGER `FK`→patients | |
| condition_id | INTEGER `FK`→conditions | diagnosis addressed |
| lead_practitioner_id | INTEGER `FK`→practitioners | |
| clinic_id | INTEGER `FK`→clinics | |
| status | TEXT | active / completed / revoked (revoked = drop-out) |
| intent | TEXT | plan |
| title, goal_description | TEXT | |
| planned_sessions | INTEGER | planned dose |
| attended_sessions | INTEGER | derived (fulfilled encounters) |
| period_start | DATE | episode start (initial evaluation) |
| period_end, discharge_date | DATE | populated for completed episodes |
| discharge_reason | TEXT | goals achieved / lost to follow-up |

### `appointments`  (FHIR Appointment — scheduling layer)
| column | type | notes |
|--------|------|-------|
| appointment_id | INTEGER `PK` | |
| patient_id, practitioner_id, clinic_id, care_plan_id | INTEGER `FK` | |
| appointment_type | TEXT | initial / follow-up |
| service_type | TEXT | |
| status | TEXT | booked / fulfilled / cancelled / noshow |
| scheduled_date | DATE | |
| scheduled_start | TIMESTAMPTZ | |
| created_date | DATE | when the booking was made |
| lead_time_days | INTEGER | scheduled_date − created_date (no-show driver) |
| session_number | INTEGER | nth session in the episode |
| cancellation_reason | TEXT | |

### `encounters`  (FHIR Encounter — delivered care)
| column | type | notes |
|--------|------|-------|
| encounter_id | INTEGER `PK` | |
| appointment_id | INTEGER `FK`→appointments | the fulfilled booking |
| patient_id, practitioner_id, clinic_id, care_plan_id, condition_id | INTEGER `FK` | |
| encounter_class | TEXT | AMB (ambulatory) |
| encounter_type | TEXT | initial-evaluation / treatment / discharge |
| status | TEXT | finished |
| period_start, period_end | TIMESTAMPTZ | |
| duration_min | INTEGER | |

### `observations`  (FHIR Observation — PROMs)
| column | type | notes |
|--------|------|-------|
| observation_id | INTEGER `PK` | |
| patient_id, encounter_id, care_plan_id | INTEGER `FK` | |
| loinc_code | TEXT | instrument LOINC code |
| instrument | TEXT | NPRS / ODI / NDI / QuickDASH / LEFS |
| measure_point | TEXT | baseline / interim / discharge |
| value_numeric | NUMERIC(6,2) | score |
| unit | TEXT | UCUM (`%`, `{score}`) |
| status | TEXT | final |
| effective_datetime | TIMESTAMPTZ | |

## Gold layer (analytical views)

| object | grain | purpose |
|--------|-------|---------|
| `dim_date` | one row per calendar day | time intelligence spine |
| `dim_patient` | patient | adds `age`, `age_band` |
| `dim_practitioner` | practitioner | + clinic name |
| `dim_clinic` | clinic | conformed |
| `dim_diagnosis` | distinct diagnosis | + body region, primary PROM instrument |
| `fact_appointment` | appointment | flags: `is_noshow`, `is_cancelled`, `is_attended`, `lead_time_band` |
| `fact_encounter` | delivered visit | finished encounters |
| `fact_outcome` | **episode** | paired baseline/discharge PROMs, harmonised 0–100 disability, adherence, LOS, **MCID flags** |
| `v_kpi_executive_monthly` | month | executive KPI trend |
| `v_kpi_clinic_scorecard` | clinic | no-show, adherence, MCID, LOS |
| `v_outcomes_by_diagnosis` | diagnosis | clinical outcomes |
| `v_dropout_risk` | active episode | the drop-out risk register |

## Derived feature tables (ML)

Built in-memory by [`/ml/features.py`](../ml/features.py) — not persisted:

- **no-show features** (per resolved appointment): booking-time calendar fields,
  `lead_time_days`, and time-aware `prior_noshows` / `prior_noshow_rate`.
- **drop-out features** (per closed episode): intake demographics, baseline
  PROMs, `planned_sessions`, and first-3-session behaviour only (leakage-safe).
