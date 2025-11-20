# Rent vs. Own Comparison Toolkit

This project wires together American Community Survey (ACS) housing cost tables and HMDA lending data to build location-specific defaults for comparing the economic gain from renting (investing 5% of income) versus owning a home (building equity through mortgage amortization and appreciation).

## Data sources

- **Income**: `B19013_001E` (ACS, median household income by CBSA)
- **Rent**: `B25064_001E` (ACS, median gross rent)
- **Owner costs**:
  - Property taxes: `B25103_001E` (annual → monthly)
  - Homeowners insurance: `B25141_001E` (annual → monthly)
  - Utilities: `B25132` electricity, `B25133` gas, `B25134` water/sewer (annual), `B25135` other fuel (annual)
- **Loan & property assumptions**: HMDA BigQuery tables (median property value, median loan amount, average interest rate) aggregated by CBSA.

All ACS pulls default to the 2023 5‑year dataset; HMDA defaults to the 2023 public release but the table path is configurable.

## Project layout

- `rent_vs_own/data_sources.py` — ACS REST client, HMDA BigQuery client, and the assembler that merges them into a `LocationFinancialDefaults` record.
- `rent_vs_own/model.py` — mortgage math plus monthly simulations that compare home equity against the renter’s investment portfolio.
- `rent_vs_own/cli.py` — Typer-based interface, exposing parameters for CBSA, data vintages, appreciation, and investment returns.

## Setup

```bash
cd /workspace
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Environment variables (optional but recommended):

```
CENSUS_API_KEY=<your-census-api-key>
HMDA_TABLE=bigquery-public-data.hmda.hmda_2023
GOOGLE_CLOUD_PROJECT=<project-with-bigquery-access>
```

The BigQuery client uses Application Default Credentials (ADC), so authenticate with `gcloud auth application-default login` or set a service account key file via `GOOGLE_APPLICATION_CREDENTIALS`.

## Usage

Fetch defaults for Los Angeles (CBSA 31080) and compare 30-year gains:

```bash
rent-vs-own 31080 \
  --acs-year 2023 \
  --hmda-year 2023 \
  --appreciation-rate 0.03 \
  --investment-return 0.05 \
  --savings-rate 0.05 \
  --show-timeline
```

The CLI prints the ACS/HMDA defaults, monthly owner vs. renter costs, ending equity/portfolio balances, and the break-even month (if the renter overtakes the owner). With `--show-timeline`, it also emits month-by-month values as JSON for charting or further analysis.

## Extending

- Plug the data layer into a web API or UI to let users pick metros from a dropdown that calls the Census/HMDA clients.
- Add sensitivity sweeps by re-running `compare_scenarios` with different appreciation or investment assumptions.
- Cache ACS/HMDA responses locally (e.g., SQLite) if you anticipate heavy usage.
