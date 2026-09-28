"""
Data-quality tests for the synthetic dataset.
Run:  pytest -q            (from the repo root, after generating the data)

These assert referential integrity, valid code sets and plausible KPI ranges —
the kind of automated checks an analyst puts around a data pipeline so that a
bad refresh fails loudly instead of silently corrupting a dashboard.
"""
import pathlib
import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
DATA = REPO / "data"


@pytest.fixture(scope="session")
def t():
    if not (DATA / "patients.csv").exists():
        pytest.skip("dataset not generated — run data/generate_synthetic_data.py")
    return {f.stem: pd.read_csv(f) for f in DATA.glob("*.csv")}


# ---- volumes -------------------------------------------------------------
def test_tables_present_and_nonempty(t):
    for name in ["clinics", "practitioners", "patients", "conditions",
                 "care_plans", "appointments", "encounters", "observations"]:
        assert name in t, f"missing table {name}"
        assert len(t[name]) > 0, f"empty table {name}"


# ---- primary-key uniqueness ---------------------------------------------
@pytest.mark.parametrize("table,key", [
    ("patients", "patient_id"), ("practitioners", "practitioner_id"),
    ("clinics", "clinic_id"), ("conditions", "condition_id"),
    ("care_plans", "care_plan_id"), ("appointments", "appointment_id"),
    ("encounters", "encounter_id"), ("observations", "observation_id"),
])
def test_primary_key_unique(t, table, key):
    assert t[table][key].is_unique, f"{table}.{key} not unique"
    assert t[table][key].notna().all(), f"{table}.{key} has nulls"


# ---- referential integrity ----------------------------------------------
@pytest.mark.parametrize("child,fk,parent,pk", [
    ("appointments", "patient_id", "patients", "patient_id"),
    ("appointments", "clinic_id", "clinics", "clinic_id"),
    ("appointments", "care_plan_id", "care_plans", "care_plan_id"),
    ("encounters", "patient_id", "patients", "patient_id"),
    ("encounters", "care_plan_id", "care_plans", "care_plan_id"),
    ("care_plans", "condition_id", "conditions", "condition_id"),
    ("care_plans", "patient_id", "patients", "patient_id"),
    ("observations", "encounter_id", "encounters", "encounter_id"),
    ("observations", "care_plan_id", "care_plans", "care_plan_id"),
    ("practitioners", "clinic_id", "clinics", "clinic_id"),
])
def test_foreign_key_integrity(t, child, fk, parent, pk):
    orphans = set(t[child][fk].dropna()) - set(t[parent][pk])
    assert not orphans, f"{child}.{fk} has {len(orphans)} orphan refs to {parent}"


# ---- valid code sets / enums --------------------------------------------
def test_appointment_status_valueset(t):
    allowed = {"booked", "fulfilled", "cancelled", "noshow"}
    assert set(t["appointments"]["status"]) <= allowed


def test_patient_gender_valueset(t):
    allowed = {"male", "female", "other", "unknown"}
    assert set(t["patients"]["gender"]) <= allowed


def test_observation_measure_points(t):
    allowed = {"baseline", "interim", "discharge"}
    assert set(t["observations"]["measure_point"]) <= allowed


def test_careplan_status_valueset(t):
    allowed = {"active", "completed", "revoked"}
    assert set(t["care_plans"]["status"]) <= allowed


# ---- business-rule sanity -----------------------------------------------
def test_attended_not_exceeding_planned(t):
    cp = t["care_plans"]
    # allow rare equality; attended must never exceed planned
    assert (cp["attended_sessions"] <= cp["planned_sessions"]).all()


def test_noshow_rate_plausible(t):
    a = t["appointments"]
    resolved = a[a["status"].isin(["fulfilled", "noshow", "cancelled"])]
    rate = (resolved["status"] == "noshow").mean()
    assert 0.05 <= rate <= 0.25, f"implausible no-show rate {rate:.3f}"


def test_dropout_rate_plausible(t):
    cp = t["care_plans"]
    closed = cp[cp["status"].isin(["completed", "revoked"])]
    rate = (closed["status"] == "revoked").mean()
    assert 0.10 <= rate <= 0.40, f"implausible drop-out rate {rate:.3f}"


def test_completed_episodes_have_discharge_proms(t):
    """Most completed episodes should carry a discharge PROM."""
    cp = t["care_plans"]; obs = t["observations"]
    completed = set(cp.loc[cp["status"] == "completed", "care_plan_id"])
    with_discharge = set(obs.loc[obs["measure_point"] == "discharge", "care_plan_id"])
    coverage = len(completed & with_discharge) / max(len(completed), 1)
    assert coverage > 0.9, f"only {coverage:.2%} of completed episodes have discharge PROMs"


def test_prom_values_in_range(t):
    obs = t["observations"]
    nprs = obs[obs["instrument"] == "NPRS"]["value_numeric"]
    assert nprs.between(0, 10).all(), "NPRS outside 0-10"
    pct = obs[obs["instrument"].isin(["ODI", "NDI", "QuickDASH"])]["value_numeric"]
    assert pct.between(0, 100).all(), "percentage index outside 0-100"
