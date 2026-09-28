# HL7 v2 ingestion

Most hospitals still emit clinical events as **HL7 v2.x** pipe-delimited
messages. This folder shows the ARN platform ingesting v2 feeds and mapping them
to the **FHIR R4** resources used by the rest of the pipeline.

```
hl7v2/
├── messages/
│   ├── adt_a04_register.hl7        ADT^A04  → Patient
│   ├── siu_s12_new_appointment.hl7 SIU^S12  → Appointment
│   └── oru_r01_prom_result.hl7     ORU^R01  → Observation[]
└── hl7v2_to_fhir.py                dependency-free v2 → FHIR R4 mapper
```

Run:

```bash
python hl7v2/hl7v2_to_fhir.py            # converts all sample messages
python hl7v2/hl7v2_to_fhir.py path.hl7   # convert a specific message
```

The mapping is documented in
[`docs/09_hl7v2_integration.md`](../docs/09_hl7v2_integration.md) and tested in
[`tests/test_hl7v2.py`](../tests/test_hl7v2.py). The converted resources line up
with the hand-written examples in [`/fhir`](../fhir) (same patient ARN101001,
practitioner pr-23, clinic Barcelona Eixample).
