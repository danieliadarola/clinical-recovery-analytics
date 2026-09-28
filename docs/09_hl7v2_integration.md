# Phase 9 — HL7 v2 Integration (the real-world feed)

FHIR R4 is the modern, analytics-friendly standard the rest of this project is
built on. But in a real European hospital network, the *source* events almost
always arrive first as **HL7 v2.x** messages — the pipe-delimited format that has
run hospital interfaces since the 1990s and is still dominant for ADT,
scheduling and results. A credible Health Informatics Analyst has to read v2 and
bridge it to FHIR. This phase adds that bridge.

## 9.1 Why HL7 v2 still matters

- It is the **incumbent**: ADT (admission/registration), SIU (scheduling) and
  ORU (results) feeds between an EHR, a RIS/LIS, a scheduler and downstream
  systems are overwhelmingly v2, exchanged over **MLLP** through an interface
  engine (Mirth, Rhapsody, Cloverleaf).
- FHIR adoption is growing but typically sits *alongside* v2, often fed **by** a
  v2→FHIR conversion. So the realistic data flow for ARN is:
  **EHR v2 feeds → interface engine → v2→FHIR mapping → FHIR R4 → analytics.**

## 9.2 Message types relevant to ARN

| v2 message | Trigger | Meaning | Maps to FHIR |
|------------|---------|---------|--------------|
| **ADT^A04** | register a patient | new outpatient registration | `Patient` |
| **SIU^S12** | new appointment booking | a scheduled physiotherapy slot | `Appointment` |
| **ORU^R01** | observation result | a PROM score (NPRS, ODI, …) | `Observation` |

(ADT also covers A08 update, A03 discharge, etc.; SIU covers S13 reschedule,
S15 cancel, S26 no-show — the same segments, different triggers.)

## 9.3 Anatomy of a v2 message

Segments are separated by a carriage return; fields by `|`; components by `^`.
The **MSH** (Message Header) declares the encoding characters (`^~\&`) and the
message type in MSH-9.

```
MSH|^~\&|ARN_EHR|ARN|ANALYTICS|ARN|20250908093000||ADT^A04^ADT_A01|MSG00001|P|2.5
EVN|A04|20250908093000
PID|1||ARN101001^^^ARN^MR||Garcia Lopez^Ana||19790412|F|||Carrer Example 10^^Barcelona^^08009^ES
PV1|1|O|EIXAMPLE^^^ARN||||pr-23^Fernandez Gil^Paula^^^PT
```

## 9.4 Field-level mapping (v2 → FHIR R4)

### ADT → Patient
| v2 location | FHIR path |
|-------------|-----------|
| PID-3 (CX) | `Patient.identifier` (MRN) |
| PID-5 (XPN) | `Patient.name.family` / `.given` |
| PID-7 | `Patient.birthDate` |
| PID-8 | `Patient.gender` (F/M/O/U → female/male/other/unknown) |
| PID-11 (XAD) | `Patient.address` (line, city, postalCode, country) |

### SIU → Appointment
| v2 location | FHIR path |
|-------------|-----------|
| SCH-1/2 | `Appointment.identifier` |
| SCH-25 (status) | `Appointment.status` (booked/fulfilled/cancelled/noshow) |
| SCH-11 (TQ) comps 4–5 | `Appointment.start` / `.end` |
| AIS-3 | `Appointment.serviceType` (SNOMED) |
| PID-3 | participant → Patient |
| AIP-3 | participant → Practitioner |
| AIL-3 | participant → Location (clinic) |

### ORU → Observation
| v2 location | FHIR path |
|-------------|-----------|
| OBX-3 (CE) | `Observation.code` (LOINC/SNOMED via the 3rd component) |
| OBX-5 | `Observation.valueQuantity.value` |
| OBX-6 | `Observation.valueQuantity.unit` (UCUM) |
| OBX-11 | `Observation.status` (F → final) |
| OBX-14 | `Observation.effectiveDateTime` |
| PID-3 | `Observation.subject` (by MRN) |

## 9.5 The implementation

[`/hl7v2/hl7v2_to_fhir.py`](../hl7v2/hl7v2_to_fhir.py) parses a v2 message into
segments/fields/components and emits the FHIR resource. It is **standard-library
only** to make the segment structure explicit; the converted resources match the
hand-written examples in [`/fhir`](../fhir) (same patient, practitioner and
clinic). Example — `ORU^R01` yields two `Observation` resources (NPRS pain and
the Oswestry Disability Index), exactly the PROMs the analytics layer expects.

```bash
python hl7v2/hl7v2_to_fhir.py
```

## 9.6 Production considerations (called out, not built here)

- **Transport & acknowledgements:** v2 over **MLLP**, each message answered with
  an **ACK/NAK**; an interface engine handles queuing, retries and routing.
- **Robust parsing & validation:** use a validated library (hl7apy / python-hl7),
  handle repetitions (`~`), escape sequences, Z-segments and version differences
  (v2.3–v2.8) — and reject malformed messages with a NAK.
- **Terminology:** map local code systems to LOINC/SNOMED/ICD-10 via a managed
  terminology service; the v2 feed often carries local codes only.
- **Idempotency & ordering:** dedupe on message control id (MSH-10); apply ADT
  updates in order; reconcile patients by MRN (matching the FHIR conditional
  upsert in Phase 2).
- **PHI in transit:** v2 carries identifiers in clear text — encrypt the channel
  (TLS/VPN) and minimise/pseudonymise on the analytics side (Phase 7).

With this bridge, the platform reflects how data *actually* moves in a hospital:
**HL7 v2 events in, governed FHIR R4 out, analytics and ML on top.**
