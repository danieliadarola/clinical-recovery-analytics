"""Tests for the HL7 v2 -> FHIR R4 mapper."""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hl7v2"))
import hl7v2_to_fhir as H  # noqa: E402

MSG = REPO / "hl7v2" / "messages"


def test_adt_maps_to_patient():
    r = H.convert_file(MSG / "adt_a04_register.hl7")
    assert r["resourceType"] == "Patient"
    assert r["identifier"][0]["value"] == "ARN101001"
    assert r["gender"] == "female"
    assert r["birthDate"] == "1979-04-12"
    assert r["name"][0]["family"] == "Garcia Lopez"


def test_siu_maps_to_appointment():
    r = H.convert_file(MSG / "siu_s12_new_appointment.hl7")
    assert r["resourceType"] == "Appointment"
    assert r["status"] == "booked"
    assert r["start"].startswith("2025-09-08T09:00")
    assert r["end"].startswith("2025-09-08T09:45")
    # patient + practitioner + location participants present
    assert len(r["participant"]) == 3
    assert any("Practitioner/pr-23" == p["actor"].get("reference") for p in r["participant"])


def test_oru_maps_to_observations():
    obs = H.convert_file(MSG / "oru_r01_prom_result.hl7")
    assert isinstance(obs, list) and len(obs) == 2
    codes = {o["code"]["coding"][0]["code"] for o in obs}
    assert codes == {"72514-3", "77564-3"}  # NPRS + ODI (LOINC)
    nprs = next(o for o in obs if o["code"]["coding"][0]["code"] == "72514-3")
    assert nprs["valueQuantity"]["value"] == 7.0
    assert nprs["resourceType"] == "Observation"


def test_gender_mapping():
    assert H.GENDER["F"] == "female" and H.GENDER["M"] == "male"


def test_datetime_helper():
    assert H.hl7_dt("20250908090000") == "2025-09-08T09:00:00+02:00"
    assert H.hl7_date("19790412") == "1979-04-12"
