"""
Clinical Recovery Analytics Platform
Synthetic data generator for the Atlas Rehabilitation Network (ARN)
--------------------------------------------------------------------
Generates a realistic, internally-consistent outpatient physiotherapy
dataset (clinics, practitioners, patients, care plans, conditions,
appointments, encounters and PROMs/observations) as CSV files.

The data is engineered to contain genuine, analysable signal:
  * inter-clinic and inter-therapist variation in outcomes and no-shows
  * lead-time, weekday, time-of-day and session-fatigue effects on no-shows
  * adherence -> outcome relationship
  * a population of active episodes "at risk of drop-out"

All identifiers, names and figures are fictitious. No real patient data
is used. Reproducible via a fixed random seed.

Usage:  python generate_synthetic_data.py
Output: CSV files written next to this script (the /data folder).
"""

import csv
import math
import os
import random
from datetime import date, timedelta

random.seed(42)

OUT = os.path.dirname(os.path.abspath(__file__))
AS_OF = date(2026, 6, 14)          # "today" for the analysis
START = date(2024, 1, 1)
END = AS_OF                          # appointments are scheduled up to "today"

# ---------------------------------------------------------------------------
# Reference catalogues
# ---------------------------------------------------------------------------

# clinic_id, name, city, region, postal_code, quality_factor, ops_factor
# quality_factor  > 1.0  -> better clinical outcomes
# ops_factor      > 1.0  -> worse operational behaviour (more no-shows/cancels)
CLINICS = [
    (1, "ARN Madrid Centro",      "Madrid",    "Comunidad de Madrid",  "28013", 1.08, 0.95),
    (2, "ARN Madrid Norte",       "Madrid",    "Comunidad de Madrid",  "28036", 1.02, 1.10),
    (3, "ARN Barcelona Eixample", "Barcelona", "Cataluna",             "08009", 1.10, 0.90),
    (4, "ARN Barcelona Sants",    "Barcelona", "Cataluna",             "08014", 0.95, 1.20),
    (5, "ARN Valencia",           "Valencia",  "Comunidad Valenciana", "46004", 1.00, 1.05),
    (6, "ARN Sevilla",            "Sevilla",   "Andalucia",            "41001", 0.92, 1.25),
    (7, "ARN Bilbao",             "Bilbao",    "Pais Vasco",           "48001", 1.05, 0.98),
    (8, "ARN Malaga",             "Malaga",    "Andalucia",            "29015", 0.98, 1.12),
]

SPECIALTIES = [
    ("Musculoskeletal physiotherapy", 0.40),
    ("Sports physiotherapy",          0.20),
    ("Orthopaedic / post-surgical",   0.18),
    ("Geriatric physiotherapy",       0.12),
    ("Neurological physiotherapy",    0.10),
]

# Diagnosis catalogue: realistic outpatient MSK conditions.
# key, display, icd10, snomed, body_site, instrument, planned_min, planned_max,
#   base_recovery (0-1 expected improvement fraction at full adherence), weight
DIAGNOSES = [
    ("lbp",    "Low back pain, non-specific",           "M54.5",  "279039007", "Lumbar spine",   "ODI",        8, 16, 0.62, 0.20),
    ("neck",   "Cervicalgia (neck pain)",               "M54.2",  "81680005",  "Cervical spine", "NDI",        6, 14, 0.60, 0.13),
    ("sciat",  "Lumbar radiculopathy (sciatica)",       "M54.3",  "23056005",  "Lumbar spine",   "ODI",       10, 20, 0.52, 0.08),
    ("rcuff",  "Rotator cuff / shoulder impingement",   "M75.1",  "45780003",  "Shoulder",       "QuickDASH",  8, 18, 0.58, 0.12),
    ("frozen", "Adhesive capsulitis (frozen shoulder)", "M75.0",  "399114009", "Shoulder",       "QuickDASH", 12, 24, 0.50, 0.05),
    ("epicon", "Lateral epicondylitis (tennis elbow)",  "M77.1",  "202855006", "Elbow",          "QuickDASH",  6, 12, 0.64, 0.06),
    ("ctun",   "Carpal tunnel syndrome (conservative)", "G56.0",  "57406009",  "Wrist",          "QuickDASH",  6, 12, 0.48, 0.04),
    ("knee_oa","Knee osteoarthritis",                   "M17.9",  "239873007", "Knee",           "LEFS",       8, 18, 0.46, 0.10),
    ("acl",    "ACL reconstruction rehabilitation",     "Z47.89", "239201008", "Knee",           "LEFS",      16, 30, 0.66, 0.05),
    ("hip_oa", "Hip osteoarthritis",                    "M16.9",  "239872002", "Hip",            "LEFS",       8, 16, 0.44, 0.05),
    ("ankle",  "Lateral ankle sprain",                  "S93.4",  "44465007",  "Ankle",          "LEFS",       6, 12, 0.70, 0.07),
    ("plant",  "Plantar fasciitis",                     "M72.2",  "202882003", "Foot",           "LEFS",       6, 14, 0.58, 0.05),
]

# Instrument metadata: loinc, unit, higher_is_worse, baseline_mean, baseline_sd,
#                       scale_max, mcid
INSTRUMENTS = {
    "NPRS":      ("72514-3", "{score}", True,   6.4, 1.5,  10,  2.0),
    "ODI":       ("77564-3", "%",       True,  42.0, 13.0, 100, 10.0),
    "NDI":       ("75438-2", "%",       True,  38.0, 12.0, 100, 7.0),
    "QuickDASH": ("78005-6", "%",       True,  45.0, 14.0, 100, 15.0),
    "LEFS":      ("77522-1", "{score}", False, 38.0, 11.0, 80,  9.0),
}

INSURANCE = [("Public (SNS)", 0.55), ("Private insurance", 0.33), ("Self-pay", 0.12)]
GENDERS = [("female", 0.54), ("male", 0.45), ("other", 0.01)]
CANCEL_REASONS = ["Patient request", "Patient illness", "Work conflict",
                  "Clinic rescheduling", "Therapist unavailable", "Adverse weather"]

GIVEN_F = ["Maria", "Carmen", "Laura", "Ana", "Marta", "Lucia", "Elena", "Sara",
           "Paula", "Cristina", "Nuria", "Andrea", "Beatriz", "Rocio", "Alba"]
GIVEN_M = ["Antonio", "Manuel", "Jose", "Francisco", "David", "Javier", "Daniel",
           "Carlos", "Jesus", "Alejandro", "Miguel", "Pablo", "Sergio", "Adrian", "Ivan"]
FAMILY = ["Garcia", "Martinez", "Lopez", "Sanchez", "Perez", "Gomez", "Fernandez",
          "Rodriguez", "Gonzalez", "Ruiz", "Diaz", "Moreno", "Alvarez", "Romero",
          "Torres", "Navarro", "Gil", "Vazquez", "Serrano", "Ramos", "Castro", "Ortega"]


def weighted(choices):
    vals, w = zip(*choices)
    return random.choices(vals, weights=w, k=1)[0]


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def rand_date(d0, d1):
    span = (d1 - d0).days
    return d0 + timedelta(days=random.randint(0, max(0, span)))


def appt_row(aid, patient, lead, clinic_id, cp, dxname, status, when, created,
             lead_time, session, hour, cancel_reason):
    return {
        "appointment_id": aid,
        "patient_id": patient["patient_id"],
        "practitioner_id": lead["practitioner_id"],
        "clinic_id": clinic_id,
        "care_plan_id": cp,
        "appointment_type": "initial" if session == 1 else "follow-up",
        "service_type": dxname,
        "status": status,
        "scheduled_date": when.isoformat(),
        "scheduled_start": f"{when.isoformat()}T{hour:02d}:00:00+02:00",
        "created_date": created.isoformat(),
        "lead_time_days": lead_time,
        "session_number": session,
        "cancellation_reason": cancel_reason or "",
    }


def make_proms(instrument, adherence_ratio, clinic_q, skill, dx_recovery):
    """Return (baseline_func, discharge_func, baseline_pain, discharge_pain)."""
    loinc, unit, hiw, b_mean, b_sd, scale_max, mcid = INSTRUMENTS[instrument]
    base = clamp(random.gauss(b_mean, b_sd), 5, scale_max if hiw else scale_max - 3)
    imp = dx_recovery * (0.45 + 0.55 * adherence_ratio) * clinic_q * skill
    imp = clamp(imp * random.gauss(1.0, 0.18), 0.02, 0.95)
    if hiw:
        disch = clamp(base * (1 - imp), 0, scale_max)
    else:
        disch = clamp(base + (scale_max - base) * imp, 0, scale_max)
    _, _, _, pm, psd, _, _ = INSTRUMENTS["NPRS"]
    pain_b = clamp(random.gauss(pm, psd), 2, 10)
    pain_imp = clamp(imp * random.gauss(1.0, 0.15), 0.02, 0.95)
    pain_d = clamp(pain_b * (1 - pain_imp), 0, 10)
    return round(base, 1), round(disch, 1), round(pain_b, 1), round(pain_d, 1)


# ---------------------------------------------------------------------------
# 1. Practitioners
# ---------------------------------------------------------------------------
practitioners = []
pid = 0
for c in CLINICS:
    clinic_id = c[0]
    for _ in range(random.randint(11, 16)):
        pid += 1
        gender = weighted(GENDERS) if random.random() > 0.02 else "female"
        given = random.choice(GIVEN_F if gender == "female" else GIVEN_M)
        family = f"{random.choice(FAMILY)} {random.choice(FAMILY)}"
        practitioners.append({
            "practitioner_id": pid,
            "license_number": f"COL-{10000 + pid}",
            "given_name": given,
            "family_name": family,
            "gender": gender,
            "specialty": weighted(SPECIALTIES),
            "seniority": random.choice(["Junior", "Junior", "Senior", "Senior", "Lead"]),
            "clinic_id": clinic_id,
            "active": "true",
            "_skill": clamp(round(random.gauss(1.0, 0.07), 3), 0.82, 1.18),
        })

prac_by_clinic = {}
for p in practitioners:
    prac_by_clinic.setdefault(p["clinic_id"], []).append(p)

# ---------------------------------------------------------------------------
# 2. Patients
# ---------------------------------------------------------------------------
N_PATIENTS = 4500
patients = []
for i in range(1, N_PATIENTS + 1):
    gender = weighted(GENDERS)
    given = random.choice(GIVEN_F if gender == "female" else GIVEN_M)
    family = f"{random.choice(FAMILY)} {random.choice(FAMILY)}"
    age = int(clamp(random.gauss(48, 17), 16, 92))
    birth = date(AS_OF.year - age, random.randint(1, 12), random.randint(1, 28))
    home_clinic = weighted([(c[0], 1) for c in CLINICS])
    reg = rand_date(START, END - timedelta(days=10))
    patients.append({
        "patient_id": i,
        "mrn": f"ARN{100000 + i}",
        "given_name": given,
        "family_name": family,
        "gender": gender,
        "birth_date": birth.isoformat(),
        "postal_code": next(c[4] for c in CLINICS if c[0] == home_clinic),
        "city": next(c[2] for c in CLINICS if c[0] == home_clinic),
        "insurance_type": weighted(INSURANCE),
        "registration_date": reg.isoformat(),
        "_home_clinic": home_clinic,
        "_age": age,
    })

# ---------------------------------------------------------------------------
# 3. Episodes -> care plans, conditions, appointments, encounters, observations
# ---------------------------------------------------------------------------
care_plans, conditions, appointments, encounters, observations = [], [], [], [], []
cp_id = appt_id = enc_id = cond_id = obs_id = 0

for p in patients:
    n_ep = random.choices([1, 2, 3], weights=[0.82, 0.15, 0.03])[0]
    for _ in range(n_ep):
        dx = random.choices(DIAGNOSES, weights=[d[9] for d in DIAGNOSES], k=1)[0]
        (dxkey, dxname, icd10, snomed, bodysite, instrument,
         pmin, pmax, base_recovery, _w) = dx

        clinic_id = p["_home_clinic"]
        clinic = next(c for c in CLINICS if c[0] == clinic_id)
        clinic_q, clinic_ops = clinic[5], clinic[6]
        lead = random.choice(prac_by_clinic[clinic_id])
        skill = lead["_skill"]

        eval_date = rand_date(max(START, date.fromisoformat(p["registration_date"])),
                              AS_OF - timedelta(days=7))
        planned = random.randint(pmin, pmax)

        # Episode lifecycle is tied to how much time has elapsed relative to the
        # expected treatment duration (~2 sessions/week). This keeps "completed"
        # episodes ones that actually had time to finish, and "active" episodes
        # genuinely recent (so drop-out gaps are realistic, not years long).
        expected_days = planned * 3.5
        days_since_eval = (AS_OF - eval_date).days
        completable = days_since_eval >= expected_days

        # Latent drop-out propensity from intake factors. This creates a
        # realistic but NOISY intake -> drop-out relationship (younger patients,
        # self-pay/public payers, longer courses, harder-recovering diagnoses and
        # weaker-ops clinics drop out more) so the early-warning ML model has
        # genuine signal to learn without being trivially predictable.
        z = -1.78
        z += 0.8 if p["_age"] < 30 else (-0.5 if p["_age"] > 65 else 0.0)
        ins = p["insurance_type"]
        z += 0.5 if ins == "Self-pay" else (0.15 if ins == "Public (SNS)" else -0.3)
        z += 0.7 * ((planned - 6) / 24.0)
        z += (0.60 - base_recovery) * 1.3
        z += (clinic_ops - 1.0) * 1.4
        z += 0.5 * random.gauss(0, 1)
        p_drop = 1.0 / (1.0 + math.exp(-z))

        if days_since_eval <= expected_days * 1.3:
            if completable:
                if random.random() < 0.28:
                    status = "active"
                else:
                    status = "dropped" if random.random() < p_drop else "completed"
            else:
                status = "dropped" if random.random() < p_drop * 0.6 else "active"
        else:
            status = "dropped" if random.random() < p_drop else "completed"

        if status == "completed":
            adherence_ratio = clamp(random.gauss(0.94, 0.06), 0.7, 1.0)
        elif status == "dropped":
            adherence_ratio = clamp(random.gauss(0.55 - 0.35 * p_drop, 0.16), 0.05, 0.8)
        else:
            adherence_ratio = clamp(random.gauss(0.55, 0.2), 0.1, 0.95)
        attended_target = max(1, round(planned * adherence_ratio))

        cp_id += 1
        cond_id += 1
        this_cp, this_cond = cp_id, cond_id

        cur = eval_date
        attended = 0
        last_attended_date = None
        session = 0
        booked_future = 0
        ep_encs = []          # encounters for THIS episode (avoids O(n^2) scans)

        for slot in range(planned + 6):
            if status != "completed" and attended >= attended_target:
                break
            if status == "completed" and attended >= planned:
                break
            if slot > 0:
                cur = cur + timedelta(days=random.choice([2, 3, 3, 4, 7]))
            lead_time = random.choices([1, 2, 3, 5, 7, 10, 14, 21],
                                       weights=[10, 14, 16, 14, 12, 12, 10, 12], k=1)[0]
            created = cur - timedelta(days=lead_time)
            session += 1
            hour = random.choices([8, 9, 10, 11, 12, 16, 17, 18, 19],
                                  weights=[6, 9, 12, 12, 8, 10, 14, 14, 7], k=1)[0]

            # future appointment (after AS_OF) -> booked, outcome unknown.
            # Only active episodes have upcoming visits; closed episodes stop.
            if cur > AS_OF:
                if status == "active" and booked_future < 3:
                    appt_id += 1
                    booked_future += 1
                    appointments.append(appt_row(
                        appt_id, p, lead, clinic_id, this_cp, dxname,
                        "booked", cur, created, lead_time, session, hour, None))
                    continue
                else:
                    break

            p_noshow = 0.075 + (clinic_ops - 1.0) * 0.18
            if cur.weekday() == 0:
                p_noshow += 0.025
            if hour < 10:
                p_noshow += 0.02
            if lead_time >= 14:
                p_noshow += 0.05
            elif lead_time >= 10:
                p_noshow += 0.025
            if p["_age"] < 30:
                p_noshow += 0.03
            elif p["_age"] > 65:
                p_noshow -= 0.02
            if session > 6:
                p_noshow += 0.02
            if p["insurance_type"] == "Self-pay":
                p_noshow -= 0.02
            p_noshow += 0.06 * (p_drop - 0.3)
            p_noshow = clamp(p_noshow, 0.01, 0.4)
            p_cancel = clamp(0.06 + (clinic_ops - 1.0) * 0.10, 0.02, 0.22)

            start_dt = f"{cur.isoformat()}T{hour:02d}:00:00+02:00"
            roll = random.random()
            if roll < p_noshow:
                st = "noshow"
            elif roll < p_noshow + p_cancel:
                st = "cancelled"
            else:
                st = "fulfilled"

            appt_id += 1
            appointments.append(appt_row(
                appt_id, p, lead, clinic_id, this_cp, dxname, st, cur, created,
                lead_time, session, hour,
                random.choice(CANCEL_REASONS) if st == "cancelled" else None))

            if st == "fulfilled":
                attended += 1
                last_attended_date = cur
                enc_id += 1
                if attended == 1:
                    etype = "initial-evaluation"
                elif status == "completed" and attended >= planned:
                    etype = "discharge"
                else:
                    etype = "treatment"
                enc_obj = {
                    "encounter_id": enc_id,
                    "appointment_id": appt_id,
                    "patient_id": p["patient_id"],
                    "practitioner_id": lead["practitioner_id"],
                    "clinic_id": clinic_id,
                    "care_plan_id": this_cp,
                    "condition_id": this_cond,
                    "encounter_class": "AMB",
                    "encounter_type": etype,
                    "status": "finished",
                    "period_start": start_dt,
                    "period_end": f"{cur.isoformat()}T{hour:02d}:45:00+02:00",
                    "duration_min": 45,
                }
                encounters.append(enc_obj)
                ep_encs.append(enc_obj)

        # ---- condition ----
        onset = eval_date - timedelta(days=random.randint(7, 120))
        conditions.append({
            "condition_id": this_cond,
            "patient_id": p["patient_id"],
            "encounter_id": "",
            "icd10_code": icd10,
            "snomed_code": snomed,
            "display": dxname,
            "body_site": bodysite,
            "category": "encounter-diagnosis",
            "clinical_status": "resolved" if status == "completed" else "active",
            "onset_date": onset.isoformat(),
            "recorded_date": eval_date.isoformat(),
        })

        # ---- care plan ----
        if status == "completed":
            cp_status = "completed"
            discharge_date = last_attended_date.isoformat() if last_attended_date else ""
            discharge_reason = "Goals achieved / discharged"
        elif status == "dropped":
            cp_status = "revoked"
            discharge_date = ""
            discharge_reason = "Lost to follow-up"
        else:
            cp_status = "active"
            discharge_date = ""
            discharge_reason = ""

        care_plans.append({
            "care_plan_id": this_cp,
            "patient_id": p["patient_id"],
            "condition_id": this_cond,
            "lead_practitioner_id": lead["practitioner_id"],
            "clinic_id": clinic_id,
            "status": cp_status,
            "intent": "plan",
            "title": f"Rehabilitation plan - {dxname}",
            "goal_description": f"Reduce pain and restore function for {dxname.lower()}",
            "planned_sessions": planned,
            "attended_sessions": attended,
            "period_start": eval_date.isoformat(),
            "period_end": discharge_date,
            "discharge_date": discharge_date,
            "discharge_reason": discharge_reason,
        })

        first_enc = ep_encs[0] if ep_encs else None
        if first_enc:
            conditions[-1]["encounter_id"] = first_enc["encounter_id"]

        # ---- observations (PROMs) ----
        if attended >= 1 and first_enc:
            adherence_real = clamp(attended / planned if planned else 0, 0, 1)
            base_f, disch_f, pain_b, pain_d = make_proms(
                instrument, adherence_real, clinic_q, skill, base_recovery)
            loinc_f = INSTRUMENTS[instrument][0]
            unit_f = INSTRUMENTS[instrument][1]
            loinc_p = INSTRUMENTS["NPRS"][0]
            unit_p = INSTRUMENTS["NPRS"][1]

            def add_obs(loinc, instr, point, val, unit, enc_row):
                global obs_id
                obs_id += 1
                observations.append({
                    "observation_id": obs_id,
                    "patient_id": p["patient_id"],
                    "encounter_id": enc_row["encounter_id"],
                    "care_plan_id": this_cp,
                    "loinc_code": loinc,
                    "instrument": instr,
                    "measure_point": point,
                    "value_numeric": val,
                    "unit": unit,
                    "status": "final",
                    "effective_datetime": enc_row["period_start"],
                })

            add_obs(loinc_f, instrument, "baseline", base_f, unit_f, first_enc)
            add_obs(loinc_p, "NPRS", "baseline", pain_b, unit_p, first_enc)

            if len(ep_encs) >= 4 and random.random() < 0.3:
                mid = ep_encs[len(ep_encs) // 2]
                mid_f = round(clamp((base_f + disch_f) / 2 + random.gauss(0, 2), 0, 100), 1)
                mid_p = round(clamp((pain_b + pain_d) / 2 + random.gauss(0, 0.5), 0, 10), 1)
                add_obs(loinc_f, instrument, "interim", mid_f, unit_f, mid)
                add_obs(loinc_p, "NPRS", "interim", mid_p, unit_p, mid)

            if status == "completed":
                disc_enc = ep_encs[-1]
                add_obs(loinc_f, instrument, "discharge", disch_f, unit_f, disc_enc)
                add_obs(loinc_p, "NPRS", "discharge", pain_d, unit_p, disc_enc)

# ---------------------------------------------------------------------------
# 4. Write CSVs
# ---------------------------------------------------------------------------
def write_csv(name, rows, fields):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {name:<22} {len(rows):>7,} rows")


clinic_rows = [{"clinic_id": c[0], "name": c[1], "city": c[2],
                "region": c[3], "postal_code": c[4]} for c in CLINICS]

print("Writing CSV files to:", OUT)
write_csv("clinics.csv", clinic_rows,
          ["clinic_id", "name", "city", "region", "postal_code"])
write_csv("practitioners.csv", practitioners,
          ["practitioner_id", "license_number", "given_name", "family_name",
           "gender", "specialty", "seniority", "clinic_id", "active"])
write_csv("patients.csv", patients,
          ["patient_id", "mrn", "given_name", "family_name", "gender",
           "birth_date", "postal_code", "city", "insurance_type", "registration_date"])
write_csv("conditions.csv", conditions,
          ["condition_id", "patient_id", "encounter_id", "icd10_code", "snomed_code",
           "display", "body_site", "category", "clinical_status", "onset_date",
           "recorded_date"])
write_csv("care_plans.csv", care_plans,
          ["care_plan_id", "patient_id", "condition_id", "lead_practitioner_id",
           "clinic_id", "status", "intent", "title", "goal_description",
           "planned_sessions", "attended_sessions", "period_start", "period_end",
           "discharge_date", "discharge_reason"])
write_csv("appointments.csv", appointments,
          ["appointment_id", "patient_id", "practitioner_id", "clinic_id",
           "care_plan_id", "appointment_type", "service_type", "status",
           "scheduled_date", "scheduled_start", "created_date", "lead_time_days",
           "session_number", "cancellation_reason"])
write_csv("encounters.csv", encounters,
          ["encounter_id", "appointment_id", "patient_id", "practitioner_id",
           "clinic_id", "care_plan_id", "condition_id", "encounter_class",
           "encounter_type", "status", "period_start", "period_end", "duration_min"])
write_csv("observations.csv", observations,
          ["observation_id", "patient_id", "encounter_id", "care_plan_id",
           "loinc_code", "instrument", "measure_point", "value_numeric", "unit",
           "status", "effective_datetime"])

print("\nDone. Summary:")
for label, n in [("clinics", len(clinic_rows)), ("practitioners", len(practitioners)),
                 ("patients", len(patients)), ("care_plans", len(care_plans)),
                 ("conditions", len(conditions)), ("appointments", len(appointments)),
                 ("encounters", len(encounters)), ("observations", len(observations))]:
    print(f"  {label:<14} {n:>8,}")
