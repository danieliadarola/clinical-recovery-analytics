"""
HL7 v2.x  ->  FHIR R4 mapper
--------------------------------------------------------------------
Most hospitals still exchange clinical events as HL7 v2 pipe-delimited
messages. This module parses the v2 message types relevant to the ARN
platform and maps them to the FHIR R4 resources used downstream:

    ADT^A04  (patient registration)  ->  Patient
    SIU^S12  (new appointment)       ->  Appointment
    ORU^R01  (observation result)    ->  Observation[]

It is intentionally dependency-free (standard library only) to show the
segment / field / component structure explicitly. In production you would
use a validating library such as hl7apy or python-hl7 and an interface
engine (Mirth / Rhapsody), but the mapping logic is the same.

Run:  python hl7v2_to_fhir.py
"""
import json
import os
import sys

GENDER = {"F": "female", "M": "male", "O": "other", "U": "unknown", "A": "other"}


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------
def parse_segments(raw):
    """Return list of (segment_name, [fields]). Segments end with \\r or \\n."""
    segs = []
    for line in raw.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
        line = line.strip()
        if not line:
            continue
        fields = line.split("|")
        segs.append((fields[0], fields))
    return segs


def first(segs, name):
    for n, f in segs:
        if n == name:
            return f
    return None


def all_of(segs, name):
    return [f for n, f in segs if n == name]


def comp(field, i, default=""):
    """Component i (0-based) of an HL7 field (split on ^)."""
    if field is None:
        return default
    parts = field.split("^")
    return parts[i] if i < len(parts) and parts[i] != "" else default


def hl7_date(s):
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else None


def hl7_dt(s):
    if len(s) < 8:
        return None
    out = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 14:
        out += f"T{s[8:10]}:{s[10:12]}:{s[12:14]}+02:00"
    return out


def message_type(segs):
    msh = first(segs, "MSH")
    return tuple((msh[8].split("^") + ["", ""])[:2]) if msh and len(msh) > 8 else ("", "")


# --------------------------------------------------------------------------
# Mappers (v2 -> FHIR R4)
# --------------------------------------------------------------------------
def map_patient(segs):
    pid = first(segs, "PID")
    mrn = comp(pid[3], 0)
    name = pid[5] if len(pid) > 5 else ""
    addr = pid[11] if len(pid) > 11 else ""
    res = {
        "resourceType": "Patient",
        "identifier": [{"system": "http://atlas-rehab.example.org/mrn", "value": mrn}],
        "name": [{"family": comp(name, 0), "given": [comp(name, 1)]}],
        "gender": GENDER.get(comp(pid[8], 0) if len(pid) > 8 else "", "unknown"),
        "birthDate": hl7_date(pid[7]) if len(pid) > 7 else None,
    }
    if addr:
        res["address"] = [{"line": [comp(addr, 0)], "city": comp(addr, 2),
                           "postalCode": comp(addr, 4), "country": comp(addr, 5)}]
    return res


def map_appointment(segs):
    sch = first(segs, "SCH")
    pid = first(segs, "PID")
    aip = first(segs, "AIP")
    ail = first(segs, "AIL")
    # appointment id = SCH-1 / SCH-2 (placer/filler), first component
    appt_id = comp(sch[1], 0) or comp(sch[2], 0)
    # status = last non-empty SCH field (SCH-25 in this profile)
    status = next((v for v in reversed(sch) if v.strip()), "booked")
    # timing field: the one containing ^^^start^end
    timing = next((v for v in sch if v.count("^") >= 4 and any(ch.isdigit() for ch in v)), "")
    tparts = timing.split("^")
    start = hl7_dt(tparts[3]) if len(tparts) > 3 else None
    end = hl7_dt(tparts[4]) if len(tparts) > 4 else None
    res = {
        "resourceType": "Appointment",
        "identifier": [{"system": "http://atlas-rehab.example.org/appointment", "value": appt_id}],
        "status": status,
        "start": start,
        "end": end,
        "participant": [],
    }
    ais = first(segs, "AIS")
    if ais:
        res["serviceType"] = [{"coding": [{"system": "http://snomed.info/sct",
                              "code": comp(ais[3], 0), "display": comp(ais[3], 1)}]}]
    if pid:
        res["participant"].append({"actor": {
            "identifier": {"value": comp(pid[3], 0)},
            "display": f"{comp(pid[5],1)} {comp(pid[5],0)}"}, "status": "accepted"})
    if aip:
        res["participant"].append({"actor": {
            "reference": f"Practitioner/{comp(aip[3],0)}",
            "display": f"{comp(aip[3],2)} {comp(aip[3],1)}"}, "status": "accepted"})
    if ail:
        res["participant"].append({"actor": {"display": comp(ail[3], 1)}, "status": "accepted"})
    return res


def map_observations(segs):
    pid = first(segs, "PID")
    mrn = comp(pid[3], 0) if pid else ""
    out = []
    for obx in all_of(segs, "OBX"):
        code = obx[3] if len(obx) > 3 else ""
        value = obx[5] if len(obx) > 5 else ""
        unit = obx[6] if len(obx) > 6 else ""
        dt = hl7_dt(obx[14]) if len(obx) > 14 else None
        sysmap = {"LN": "http://loinc.org", "SCT": "http://snomed.info/sct"}
        out.append({
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                      "code": "survey"}]}],
            "code": {"coding": [{"system": sysmap.get(comp(code, 2), "http://loinc.org"),
                                 "code": comp(code, 0), "display": comp(code, 1)}]},
            "subject": {"identifier": {"system": "http://atlas-rehab.example.org/mrn", "value": mrn}},
            "effectiveDateTime": dt,
            "valueQuantity": {"value": float(value) if value.replace(".", "").isdigit() else value,
                              "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
        })
    return out


def convert(raw):
    segs = parse_segments(raw)
    code, _ = message_type(segs)
    if code == "ADT":
        return map_patient(segs)
    if code == "SIU":
        return map_appointment(segs)
    if code == "ORU":
        return map_observations(segs)
    raise ValueError(f"Unsupported message type: {code}")


def convert_file(path):
    with open(path, encoding="utf-8") as f:
        return convert(f.read())


if __name__ == "__main__":
    msg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages")
    files = sys.argv[1:] or [os.path.join(msg_dir, n) for n in sorted(os.listdir(msg_dir))]
    for path in files:
        print("=" * 70)
        print("HL7 v2 message:", os.path.basename(path))
        result = convert_file(path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
