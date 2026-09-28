# Guía completa — cómo funciona todo (manual paso a paso)

Manual en español para entender el proyecto de principio a fin: qué hace, qué
programa se usa para cada cosa, cómo ponerlo en marcha y cómo explicarlo. Está
pensado para alguien con conocimientos básicos de datos.

> Todos los datos son **sintéticos** (inventados por un script). No hay ningún
> dato real de pacientes.

## Índice
1. [Qué es el proyecto, en una frase](#1)
2. [El flujo completo de un vistazo](#2)
3. [Los programas que se usan (y para qué)](#3)
4. [Estructura del repositorio (carpeta por carpeta)](#4)
5. [Puesta en marcha paso a paso](#5)
6. [Cómo funciona cada parte por dentro](#6)
7. [Glosario de términos](#7)
8. [Cómo publicarlo y enseñarlo](#8)
9. [Problemas frecuentes (troubleshooting)](#9)

---

<a name="1"></a>
## 1. Qué es el proyecto, en una frase

Una **plataforma de analítica clínica** para una red ficticia de 8 clínicas de
fisioterapia (Atlas Rehabilitation Network). Coge los datos clínicos, los
ordena, y responde a preguntas de negocio reales: *¿cuántas citas se pierden?,
¿qué pacientes van a abandonar el tratamiento?, ¿se recuperan de verdad?* — y lo
presenta en cuadros de mando y modelos predictivos. Es el trabajo típico de un
**Health Informatics Analyst**.

<a name="2"></a>
## 2. El flujo completo de un vistazo

```
Mensajes HL7 v2  →  FHIR R4  →  PostgreSQL  →  SQL / Power BI / Machine Learning
 (lo que emite       (estándar    (base de       (análisis, cuadros de mando
  el hospital)        moderno)     datos)          y modelos predictivos)
```

Analogía: el hospital "habla" en **HL7 v2** (un formato antiguo de mensajes).
Lo traducimos a **FHIR R4** (un formato moderno y ordenado), lo guardamos en una
**base de datos SQL** (como una hoja de cálculo gigante y relacionada), y sobre
esa base hacemos **análisis** (SQL), **gráficos** (Power BI / dashboard) y
**predicciones** (machine learning).

<a name="3"></a>
## 3. Los programas que se usan (y para qué)

| Programa / herramienta | Qué es | Para qué se usa aquí | Cómo se instala |
|------------------------|--------|----------------------|-----------------|
| **Python 3** | Lenguaje de programación | Generar los datos, los modelos de ML, el notebook | [python.org/downloads](https://www.python.org/downloads/) (marca "Add to PATH") |
| **pip** | Instalador de librerías de Python | Instalar pandas, scikit-learn, etc. | Viene con Python |
| **PostgreSQL** | Base de datos SQL profesional | Guardar las tablas y ejecutar las consultas/KPIs | [postgresql.org/download](https://www.postgresql.org/download/) |
| **DuckDB** | Base de datos SQL "sin servidor" (un archivo) | Probar el mismo SQL sin instalar PostgreSQL | `pip install duckdb` |
| **Power BI Desktop** | Herramienta de cuadros de mando de Microsoft | Construir los 3 dashboards ejecutivo/clínico/operativo | [powerbi.microsoft.com](https://powerbi.microsoft.com/desktop/) (gratis, solo Windows) |
| **Jupyter** | Cuadernos de código + resultados | El recorrido reproducible (`notebooks/`) | `pip install jupyterlab` |
| **Git** | Control de versiones | Guardar la historia del proyecto y subirlo a GitHub | [git-scm.com](https://git-scm.com/) |
| **Navegador web** | Chrome / Edge / Firefox | Abrir el dashboard `index.html` | Ya lo tienes |

**Librerías de Python que usa el proyecto** (se instalan con pip):

| Librería | Para qué |
|----------|----------|
| `pandas` | Manejar tablas de datos en Python |
| `numpy` | Cálculos numéricos |
| `duckdb` | Ejecutar SQL desde Python sin servidor |
| `scikit-learn` | Entrenar los modelos de machine learning |
| `matplotlib` | Dibujar gráficos (ROC, importancia de variables…) |
| `jupyterlab`, `nbconvert` | Crear y ejecutar el notebook |
| `pytest` | Ejecutar los tests de calidad de datos |

**Estándares / vocabularios** (no son programas, son "idiomas" sanitarios):

- **HL7 v2.x**: formato de mensajes que usan casi todos los hospitales (citas,
  altas, resultados).
- **FHIR R4**: estándar moderno de interoperabilidad sanitaria (datos como
  "recursos": Patient, Appointment, Observation…).
- **LOINC / SNOMED CT / ICD-10**: códigos estándar para medir cosas (LOINC para
  pruebas/escala de dolor), diagnosticar (SNOMED clínico, ICD-10 administrativo).

<a name="4"></a>
## 4. Estructura del repositorio (carpeta por carpeta)

```
data/        Generador de datos sintéticos (Python) + los CSV que produce
hl7v2/       Mensajes HL7 v2 de ejemplo + parser que los convierte a FHIR
fhir/        Recursos FHIR R4 de ejemplo (Patient, Appointment, …) + un Bundle
sql/         Esquema PostgreSQL, modelo estrella, consultas y vistas KPI
powerbi/     Librería de medidas DAX + diseño de los 3 dashboards
ml/          Modelos predictivos (no-show y abandono) + gráficos de resultados
notebooks/   Cuaderno Jupyter ejecutado (recorrido de todo el proyecto)
tests/       Tests automáticos de calidad de datos y de HL7 (pytest)
assets/      Diagrama de arquitectura (SVG/PNG)
docs/        Documentación: las 9 fases + este manual + diccionario de datos
index.html   Dashboard interactivo (se abre en el navegador)
.github/     Configuración de CI (se ejecuta solo en GitHub)
README.md    Portada del proyecto
```

<a name="5"></a>
## 5. Puesta en marcha paso a paso

> Necesitas: **Python 3** instalado. PostgreSQL y Power BI son **opcionales**
> (el dashboard y el notebook funcionan sin ellos).

### 5.1 Abrir una terminal en la carpeta del proyecto
- Windows: abre la carpeta del proyecto, escribe `cmd` en la barra de dirección
  y pulsa Enter.

### 5.2 Instalar las librerías de Python
```bash
pip install pandas numpy duckdb scikit-learn matplotlib jupyterlab pytest
```

### 5.3 Generar los datos (≈4 segundos)
```bash
python data/generate_synthetic_data.py
```
Esto crea los 8 archivos CSV en la carpeta `data/`.

### 5.4 Ver el dashboard (lo más rápido)
Haz **doble clic en `index.html`**. Se abre en el navegador con KPIs y gráficos.
No necesita nada más.

### 5.5 Probar el análisis SQL sin instalar nada (DuckDB)
```bash
pip install duckdb
python - <<'FIN'
import duckdb, glob, os
con = duckdb.connect()
for f in glob.glob("data/*.csv"):
    t = os.path.splitext(os.path.basename(f))[0]
    con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv_auto('{f}', header=true)")
print(con.execute("SELECT status, COUNT(*) FROM appointments GROUP BY 1").df())
FIN
```

### 5.6 (Opcional) Cargar en PostgreSQL y ejecutar el SQL real
```bash
createdb arn_db
psql -d arn_db -f sql/01_schema_ddl.sql
psql -d arn_db -f sql/02_load_data.sql      # ejecuta desde la raíz del repo
psql -d arn_db -f sql/03_star_schema.sql
psql -d arn_db -f sql/05_kpi_views.sql
psql -d arn_db -f sql/04_analytical_queries.sql   # ver los resultados
```

### 5.7 Ejecutar el notebook (recorrido completo)
```bash
jupyter lab notebooks/clinical_recovery_walkthrough.ipynb
```
Pulsa "Run all" para volver a ejecutarlo, o ábrelo para ver los resultados ya
guardados.

### 5.8 Entrenar los modelos de machine learning
```bash
python ml/train_noshow.py
python ml/train_dropout.py
```
Crea métricas y gráficos en `ml/outputs/`.

### 5.9 Ejecutar los tests de calidad
```bash
pytest -q
```
Deben salir **33 passed**.

### 5.10 Power BI (opcional, solo Windows)
1. Abre Power BI Desktop → **Obtener datos → PostgreSQL** (o importa los CSV de
   `data/`).
2. Carga las vistas `fact_*`, `dim_*`, `v_*`.
3. Crea las relaciones (de cada dimensión a los hechos) y marca `dim_date` como
   tabla de fechas.
4. Pega las medidas de `powerbi/dax_measures.dax`.
5. Construye las páginas siguiendo `docs/05_powerbi.md`.

<a name="6"></a>
## 6. Cómo funciona cada parte por dentro

1. **Generación de datos** (`data/generate_synthetic_data.py`): inventa pacientes,
   citas, sesiones y cuestionarios de recuperación (PROMs) de forma realista, con
   patrones reales (más no-shows si reservas con mucha antelación, más abandono en
   ciertos perfiles…). Por eso los análisis luego "tienen sentido".

2. **HL7 v2 → FHIR** (`hl7v2/`): los hospitales emiten mensajes como `ADT` (alta),
   `SIU` (cita) y `ORU` (resultado). El parser los traduce a recursos FHIR
   (Patient, Appointment, Observation). Es la "puerta de entrada" realista.

3. **FHIR → SQL** (`sql/01`–`03`): FHIR es JSON anidado (bueno para intercambiar,
   malo para analizar). Lo "aplanamos" a tablas SQL: una tabla por tipo de
   recurso (capa *core*) y encima un **modelo estrella** (dimensiones + hechos)
   que es como Power BI trabaja mejor.

4. **Análisis SQL** (`sql/04`): 10 consultas que responden a las preguntas de
   negocio (tasa de no-show, adherencia, tiempo hasta el alta, diagnósticos más
   frecuentes, y la "lista de pacientes en riesgo de abandono").

5. **Power BI** (`powerbi/`): 3 cuadros de mando (ejecutivo, clínico, operativo)
   con medidas DAX que calculan los KPIs en tiempo real al filtrar.

6. **Machine Learning** (`ml/`): dos modelos que *predicen* el futuro — quién
   faltará a una cita (no-show) y quién abandonará pronto el tratamiento — para
   poder actuar antes. Están hechos "sin trampas" (sin fugas de datos) y se
   evalúan con métricas honestas (AUROC, AUPRC, calibración).

7. **Notebook** (`notebooks/`): une todo lo anterior en un único documento
   navegable con código + resultados + gráficos ya ejecutados.

8. **Tests y CI** (`tests/`, `.github/`): comprueban automáticamente que los datos
   son correctos (claves únicas, integridad, rangos plausibles). En GitHub se
   ejecutan solos en cada cambio.

<a name="7"></a>
## 7. Glosario de términos

- **HL7 v2**: formato veterano de mensajes hospitalarios (separado por `|`).
- **FHIR R4**: estándar moderno; los datos son "recursos" (Patient, Encounter…).
- **Recurso FHIR**: una pieza de información clínica con estructura estándar.
- **PROM** (Patient-Reported Outcome Measure): cuestionario que rellena el
  paciente para medir su estado (dolor, función).
- **NPRS**: escala de dolor 0–10. **ODI / NDI / QuickDASH / LEFS**: cuestionarios
  de función para espalda, cuello, brazo y pierna.
- **MCID** (Minimal Clinically Important Difference): la mejora mínima que el
  paciente *nota*. Medir "% que alcanza la MCID" es más honesto que una media.
- **Episodio de cuidado / CarePlan**: el tratamiento completo de un problema, de
  la evaluación inicial al alta.
- **No-show**: el paciente no acude y no avisa. **Cancelación**: avisa.
- **Adherencia**: % de sesiones planificadas que el paciente realmente asiste.
- **Abandono (drop-out)**: dejar el tratamiento antes de terminarlo.
- **Modelo estrella (star schema)**: forma de organizar tablas (dimensiones +
  hechos) ideal para analítica y BI.
- **KPI**: indicador clave de rendimiento (p. ej. tasa de no-show).
- **DAX**: lenguaje de fórmulas de Power BI.
- **AUROC / AUPRC**: métricas de calidad de un modelo predictivo (1.0 perfecto;
  0.5 azar). **Calibración**: que un "30% de riesgo" signifique de verdad 30%.
- **GDPR / RGPD**: ley europea de protección de datos. **EU AI Act**: reglamento
  europeo de inteligencia artificial.

<a name="8"></a>
## 8. Cómo publicarlo y enseñarlo

1. **Subirlo a GitHub** (desde el bundle que te entregué, o desde la carpeta):
   ```bash
   git clone clinical-recovery-analytics-repo.bundle "Clinical Recovery Analytics Platform"
   cd "Clinical Recovery Analytics Platform"
   git remote add origin https://github.com/TU_USUARIO/clinical-recovery-analytics-platform.git
   git push -u origin main
   ```
2. **Activar GitHub Pages** (para tener el dashboard como página web):
   en el repo → **Settings → Pages → Source: Deploy from a branch → `main` /
   root → Save**. En ~1 min tendrás una URL pública.
3. **En una entrevista**: enseña primero el `index.html` o la página de Pages
   (impacto visual), luego el diagrama de arquitectura, una consulta SQL y los
   gráficos de los modelos. La guía de discurso está en `docs/08_portfolio.md`.

<a name="9"></a>
## 9. Problemas frecuentes (troubleshooting)

- **"python no se reconoce"**: no marcaste "Add Python to PATH" al instalar.
  Reinstala Python marcando esa casilla, o usa `py` en vez de `python`.
- **`pip install` falla**: actualiza pip con `python -m pip install --upgrade pip`.
- **El dashboard no muestra gráficos**: necesita conexión a internet la primera
  vez (carga la librería Chart.js). Con internet, recarga la página.
- **`psql` no existe**: no tienes PostgreSQL instalado; usa la opción DuckDB
  (paso 5.5) para probar el SQL.
- **El SQL falla en DuckDB por `to_char`**: DuckDB no tiene `to_char`; el
  notebook y el harness ya definen un "macro" de compatibilidad. En PostgreSQL
  funciona tal cual.
- **Los tests fallan diciendo "dataset not generated"**: ejecuta primero
  `python data/generate_synthetic_data.py`.

---

*Si algo no te queda claro, cada fase tiene su documento detallado en `docs/`
(01 a 09), y el `README.md` es el resumen general.*
