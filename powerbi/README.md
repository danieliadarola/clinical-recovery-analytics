# Power BI — build notes

This folder documents the Power BI layer. (No `.pbix` binary is committed; the
model is reproducible from the SQL gold layer and the DAX library.)

> 🚀 **No PostgreSQL? Start here:** [`data/`](data) contains the gold-layer
> (star schema) already exported as CSVs, with the exact table/column names the
> DAX expects. Follow the step-by-step **[POWER_BI_GUIA.md](POWER_BI_GUIA.md)**
> (Spanish) to import them and build the 3 dashboards in minutes.

## Connect

1. Run the SQL pipeline (`/sql/01`→`05`) against PostgreSQL.
2. In Power BI Desktop: **Get Data → PostgreSQL**, import these views as tables:
   `dim_date`, `dim_clinic`, `dim_practitioner`, `dim_patient`, `dim_diagnosis`,
   `fact_appointment`, `fact_encounter`, `fact_outcome`, `v_dropout_risk`.
   *(For a quick demo without a server, import the CSVs in `/data` instead.)*
3. **Model view:** create 1→\* relationships from each dimension to the facts;
   mark `dim_date` as the date table (`date_key`).
4. **Measures:** paste the measures from [`dax_measures.dax`](./dax_measures.dax)
   into a dedicated `Measures` table.
5. Build the three report pages per [`/docs/05_powerbi.md`](../docs/05_powerbi.md).

## Suggested theme

Colour-blind-safe palette; green/amber/red reserved for RAG KPI states only;
data labels on; thousands separators; percentages to 1 decimal.

## Refresh & security

- Schedule a nightly refresh after the ETL + view refresh.
- Add an RLS role `Clinic Manager` with filter
  `dim_clinic[clinic_id] = LOOKUPVALUE(...)` mapped to the signed-in user.
