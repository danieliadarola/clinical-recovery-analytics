# Guía paso a paso para montar el dashboard en Power BI

Esta guía te lleva de cero a tener los **3 cuadros de mando** (ejecutivo, clínico
y operativo) en **Power BI Desktop**, sin necesidad de instalar PostgreSQL.
Usaremos los CSV ya preparados en [`powerbi/data/`](data) (son el modelo en
estrella, con los **nombres exactos** que esperan las medidas DAX).

> Requisito: Power BI Desktop (gratis, solo Windows):
> https://powerbi.microsoft.com/desktop/

## 1. Importar los datos

1. Abre Power BI Desktop → **Inicio → Obtener datos → Texto/CSV** (o
   **Carpeta** para cargar todos a la vez).
2. Importa estas 9 tablas desde `powerbi/data/`:
   `dim_date`, `dim_clinic`, `dim_practitioner`, `dim_patient`, `dim_diagnosis`,
   `fact_appointment`, `fact_encounter`, `fact_outcome`, `v_dropout_risk`.
3. En la vista previa, pulsa **Cargar** (o **Transformar datos** si quieres
   revisar tipos).

## 2. Revisar los tipos de columna

En **Transformar datos** (Power Query), confirma:

- `dim_date[date_key]`, `fact_appointment[scheduled_date]`,
  `fact_outcome[episode_start]`, `fact_outcome[discharge_date]`,
  `fact_encounter[encounter_date]`, `v_dropout_risk[last_visit_date]` → tipo
  **Fecha**.
- Las columnas `is_*`, `*_sessions`, `*_mcid_achieved`, `adherence_ratio`,
  `value`/`pain`/`func`… → **Número entero/decimal**.
- El resto, **Texto**. Pulsa **Cerrar y aplicar**.

## 3. Crear el modelo (relaciones)

Ve a la vista **Modelo** y crea estas relaciones (todas **1 a varios**, dirección
de filtro **única**, de la dimensión al hecho):

| Desde (dimensión) | Hacia (hecho) |
|---|---|
| `dim_date[date_key]` | `fact_appointment[scheduled_date]` (activa) |
| `dim_date[date_key]` | `fact_outcome[episode_start]` |
| `dim_clinic[clinic_id]` | `fact_appointment[clinic_id]`, `fact_outcome[clinic_id]`, `fact_encounter[clinic_id]` |
| `dim_practitioner[practitioner_id]` | `fact_appointment`, `fact_outcome`, `fact_encounter` |
| `dim_patient[patient_id]` | `fact_appointment`, `fact_outcome`, `fact_encounter` |
| `dim_diagnosis[icd10_code]` | `fact_outcome[icd10_code]` |

`v_dropout_risk` se queda **sin relacionar** (es una tabla operativa que alimenta
las medidas “Patients At Risk”).

Luego selecciona la tabla `dim_date` → pestaña **Herramientas de tabla** →
**Marcar como tabla de fechas** → columna `date_key`.

## 4. Pegar las medidas DAX

1. Crea una tabla vacía para las medidas: **Inicio → Especificar datos**, nómbrala
   `Measures` y carga.
2. Abre [`dax_measures.dax`](dax_measures.dax). Por cada medida, en Power BI haz
   **Nueva medida** y pega el bloque (desde el nombre hasta el cierre del
   `RETURN`/paréntesis). Empieza por las básicas:
   - `Resolved Appointments`, `No-Shows`, `No-Show Rate %`, `Lost Capacity %`
   - `Episodes`, `Completion Rate %`, `Drop-out Rate %`, `Mean Adherence %`
   - `Func MCID Achievement %`, `Mean Pain Reduction`, `Mean Time to Discharge`
   - `Patients At Risk`, `High Risk Patients`, `Sessions At Risk`
3. Formatea cada medida `%` como **Porcentaje** (Herramientas de medida → Formato).

## 5. Construir las 3 páginas

Sigue el diseño detallado en [`/docs/05_powerbi.md`](../docs/05_powerbi.md).
Resumen rápido:

**Página 1 — Ejecutivo:** tarjetas KPI (`Episodes`, `No-Show Rate %`,
`Completion Rate %`, `Func MCID Achievement %`), gráfico de líneas de
`No-Show Rate %` por `dim_date[year_month]`, barras de `No-Show Rate %` por
`dim_clinic[clinic_name]`, y segmentadores de fecha y clínica.

**Página 2 — Clínico:** barras de `Func MCID Achievement %` por
`dim_diagnosis[diagnosis_name]` (con línea de objetivo 80%), columnas de
`Mean Pain Reduction`/`Mean Disability Reduction`, dispersión de
`Mean Adherence %` vs `Func MCID Achievement %`, y tabla de
`dim_practitioner[practitioner_name]` con su MCID.

**Página 3 — Operativo:** embudo de citas (`Resolved`, `Attended`, `No-Shows`,
`Cancellations`), matriz (mapa de calor) de `No-Show Rate %` por
`lead_time_band` × `iso_weekday`, y la **tabla de registro de abandono** desde
`v_dropout_risk` (mrn, clínica, diagnóstico, sesiones restantes, días sin venir,
riesgo), filtrable por clínica.

## 6. Tema, seguridad y guardado

- Aplica un tema accesible (Ver → Temas) con verde/ámbar/rojo solo para estados
  RAG de los KPI.
- (Opcional) **Seguridad por filas (RLS):** crea un rol “Clinic Manager” que
  filtre `dim_clinic[clinic_id]` por el usuario, para que cada responsable vea
  solo su clínica.
- Guarda como **`.pbix`**. Para compartir online, **Publicar** en Power BI
  Service (requiere cuenta de trabajo) y programa el refresco.

## 7. ¿Y cuando tengas PostgreSQL?

Estos CSV son una copia exacta de las vistas SQL. El día que cargues el proyecto
en PostgreSQL (`sql/01`–`05`), solo tienes que cambiar el origen de datos
(**Obtener datos → PostgreSQL** y elegir las vistas `dim_*`, `fact_*`,
`v_dropout_risk`): el modelo, las medidas y los visuales siguen funcionando sin
tocar nada más.
