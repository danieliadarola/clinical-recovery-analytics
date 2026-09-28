"""
Feature engineering for the predictive models.
--------------------------------------------------------------------
Two leakage-safe feature sets are built from the synthetic CSVs in /data:

  build_noshow_features()  -> one row per *resolved* appointment, using ONLY
                              information available at booking time, plus the
                              patient's no-show history *prior* to that
                              appointment (time-ordered, shift(1) — no leakage).

  build_dropout_features() -> one row per *closed* episode (completed/revoked),
                              an EARLY-WARNING design that uses only intake data
                              and behaviour in the first 3 scheduled sessions.
                              It never sees total attendance, discharge or
                              adherence (those would leak the outcome).

Both return (X dataframe, y series, meta dataframe with dates for splitting).
"""
import os
import numpy as np
import pandas as pd

AS_OF = pd.Timestamp("2026-06-14")


def load_data(data_dir):
    f = lambda n: pd.read_csv(os.path.join(data_dir, n))
    return {
        "patients": f("patients.csv"),
        "appointments": f("appointments.csv"),
        "encounters": f("encounters.csv"),
        "care_plans": f("care_plans.csv"),
        "conditions": f("conditions.csv"),
        "observations": f("observations.csv"),
    }


def _patient_attrs(patients):
    p = patients.copy()
    p["birth_date"] = pd.to_datetime(p["birth_date"])
    p["age"] = ((AS_OF - p["birth_date"]).dt.days / 365.25).round().astype(int)
    return p[["patient_id", "age", "gender", "insurance_type"]]


# ---------------------------------------------------------------------------
# NO-SHOW FEATURES  (target: appointment is a no-show)
# ---------------------------------------------------------------------------
def build_noshow_features(data):
    appt = data["appointments"].copy()
    # Keep only resolved attendance outcomes; no-show is defined vs attended.
    # Cancellations are a different administrative process -> excluded here.
    appt = appt[appt["status"].isin(["fulfilled", "noshow"])].copy()
    appt["scheduled_date"] = pd.to_datetime(appt["scheduled_date"])
    appt["scheduled_start"] = pd.to_datetime(appt["scheduled_start"], utc=True)
    appt["is_noshow"] = (appt["status"] == "noshow").astype(int)

    # Booking-time calendar features
    appt["weekday"] = appt["scheduled_date"].dt.weekday          # 0=Mon
    appt["month"] = appt["scheduled_date"].dt.month
    appt["hour"] = appt["scheduled_start"].dt.hour
    appt["is_initial"] = (appt["appointment_type"] == "initial").astype(int)

    # Time-aware patient history (STRICTLY prior appointments -> no leakage)
    appt = appt.sort_values(["patient_id", "scheduled_start"]).reset_index(drop=True)
    g = appt.groupby("patient_id", sort=False)
    appt["prior_appts"] = g.cumcount()                            # # before this one
    prior_noshows = g["is_noshow"].cumsum() - appt["is_noshow"]   # exclude current
    appt["prior_noshows"] = prior_noshows
    appt["prior_noshow_rate"] = np.where(
        appt["prior_appts"] > 0, appt["prior_noshows"] / appt["prior_appts"], 0.0)

    # Patient demographics
    pa = _patient_attrs(data["patients"])
    appt = appt.merge(pa, on="patient_id", how="left")

    feature_cols_num = ["lead_time_days", "weekday", "month", "hour",
                        "session_number", "is_initial", "age",
                        "prior_appts", "prior_noshows", "prior_noshow_rate"]
    feature_cols_cat = ["clinic_id", "service_type", "insurance_type", "gender"]

    X = appt[feature_cols_num + feature_cols_cat].copy()
    X["clinic_id"] = X["clinic_id"].astype(str)
    y = appt["is_noshow"]
    meta = appt[["appointment_id", "scheduled_date"]].copy()
    return X, y, meta, feature_cols_num, feature_cols_cat


# ---------------------------------------------------------------------------
# DROP-OUT FEATURES  (target: episode ends as drop-out)  — EARLY WARNING
# ---------------------------------------------------------------------------
def build_dropout_features(data, early_window=3):
    cp = data["care_plans"].copy()
    cp = cp[cp["status"].isin(["completed", "revoked"])].copy()   # closed only
    cp["period_start"] = pd.to_datetime(cp["period_start"])
    cp["is_dropout"] = (cp["status"] == "revoked").astype(int)

    # Diagnosis (icd10) for case-mix
    cond = data["conditions"][["condition_id", "icd10_code", "body_site"]]
    cp = cp.merge(cond, on="condition_id", how="left")

    # Baseline PROMs ONLY (known at intake)
    obs = data["observations"]
    base = obs[obs["measure_point"] == "baseline"]
    pain = (base[base["instrument"] == "NPRS"]
            .groupby("care_plan_id")["value_numeric"].max()
            .rename("baseline_pain"))
    func = (base[base["instrument"] != "NPRS"]
            .groupby("care_plan_id")["value_numeric"].max()
            .rename("baseline_func"))
    cp = cp.merge(pain, on="care_plan_id", how="left").merge(func, on="care_plan_id", how="left")

    # Early behaviour: ONLY the first `early_window` scheduled sessions
    appt = data["appointments"].copy()
    early = appt[appt["session_number"] <= early_window]
    agg = early.groupby("care_plan_id").agg(
        early_appts=("appointment_id", "count"),
        early_noshows=("status", lambda s: (s == "noshow").sum()),
        early_cancels=("status", lambda s: (s == "cancelled").sum()),
        early_attended=("status", lambda s: (s == "fulfilled").sum()),
        early_mean_lead=("lead_time_days", "mean"),
    ).reset_index()
    agg["early_attend_rate"] = np.where(
        agg["early_appts"] > 0, agg["early_attended"] / agg["early_appts"], 0.0)
    cp = cp.merge(agg, on="care_plan_id", how="left")

    # Patient demographics
    pa = _patient_attrs(data["patients"])
    cp = cp.merge(pa, on="patient_id", how="left")

    # Fill PROM/early gaps (a patient with no early appt is itself a strong signal)
    for c in ["baseline_pain", "baseline_func"]:
        cp[c] = cp[c].fillna(cp[c].median())
    for c in ["early_appts", "early_noshows", "early_cancels", "early_attended",
              "early_attend_rate"]:
        cp[c] = cp[c].fillna(0)
    cp["early_mean_lead"] = cp["early_mean_lead"].fillna(cp["early_mean_lead"].median())

    feature_cols_num = ["planned_sessions", "baseline_pain", "baseline_func",
                        "early_appts", "early_noshows", "early_cancels",
                        "early_attend_rate", "early_mean_lead", "age"]
    feature_cols_cat = ["clinic_id", "icd10_code", "insurance_type", "gender"]

    X = cp[feature_cols_num + feature_cols_cat].copy()
    X["clinic_id"] = X["clinic_id"].astype(str)
    y = cp["is_dropout"]
    meta = cp[["care_plan_id", "period_start"]].copy()
    return X, y, meta, feature_cols_num, feature_cols_cat


if __name__ == "__main__":
    import sys
    d = load_data(sys.argv[1] if len(sys.argv) > 1 else "../data")
    Xn, yn, mn, *_ = build_noshow_features(d)
    Xd, yd, md, *_ = build_dropout_features(d)
    print(f"no-show: {Xn.shape[0]:,} rows, {Xn.shape[1]} features, "
          f"no-show rate {yn.mean():.3f}")
    print(f"dropout: {Xd.shape[0]:,} rows, {Xd.shape[1]} features, "
          f"dropout rate {yd.mean():.3f}")
