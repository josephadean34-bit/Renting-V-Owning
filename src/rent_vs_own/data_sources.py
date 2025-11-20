from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import requests
from google.cloud import bigquery

from .schemas import LocationFinancialDefaults


class CensusACSClient:
    """Thin wrapper around the Census API for ACS pulls."""

    BASE_URL = "https://api.census.gov/data"
    GEO_KEY = "metropolitan statistical area/micropolitan statistical area"

    # Column definitions and any transformations required to reach monthly dollars
    ACS_METRICS: Dict[str, Dict[str, float]] = {
        "median_income": {"column": "B19013_001E", "annual_divisor": 1},
        "median_rent": {"column": "B25064_001E", "annual_divisor": 1},
        "real_estate_taxes": {"column": "B25103_001E", "annual_divisor": 12},
        "home_insurance": {"column": "B25141_001E", "annual_divisor": 12},
        "electricity": {"column": "B25132_001E", "annual_divisor": 1},
        "gas": {"column": "B25133_001E", "annual_divisor": 1},
        "water_sewer": {"column": "B25134_001E", "annual_divisor": 12},
        "other_fuel": {"column": "B25135_001E", "annual_divisor": 12},
    }

    def __init__(
        self,
        api_key: Optional[str],
        dataset: str = "acs/acs5",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.dataset = dataset
        self.session = session or requests.Session()

    def fetch_housing_metrics(self, cbsa: str, *, year: int = 2023) -> Dict[str, float]:
        columns = ["NAME"] + sorted(
            spec["column"] for spec in self.ACS_METRICS.values()
        )
        params = {
            "get": ",".join(columns),
            "for": f"{self.GEO_KEY}:{cbsa}",
        }
        if self.api_key:
            params["key"] = self.api_key

        url = f"{self.BASE_URL}/{year}/{self.dataset}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if len(data) < 2:
            raise RuntimeError(f"ACS query returned no rows for CBSA {cbsa}")

        header = data[0]
        values = data[1]
        row = dict(zip(header, values))

        metrics: Dict[str, float] = {"name": row.get("NAME", f"CBSA {cbsa}")}
        for key, spec in self.ACS_METRICS.items():
            raw_value = _to_float(row.get(spec["column"]))
            divisor = spec.get("annual_divisor", 1) or 1
            metrics[key] = raw_value / divisor if raw_value is not None else 0.0

        return metrics


class HMDAClient:
    """Pull median property / loan metrics from the public HMDA BigQuery tables."""

    def __init__(
        self,
        *,
        table: str,
        client: Optional[bigquery.Client] = None,
        project: Optional[str] = None,
    ) -> None:
        if client is None:
            self.client = bigquery.Client(project=project)
        else:
            self.client = client
        self.table = table

    def fetch_cbsa_summary(self, cbsa: str, *, year: int = 2023) -> Dict[str, float]:
        query = f"""
            SELECT
              CAST(derived_msa_md AS STRING) AS cbsa,
              ANY_VALUE(derived_msa_md_name) AS cbsa_name,
              APPROX_QUANTILES(CAST(property_value AS FLOAT64), 2)[OFFSET(1)] AS median_property_value,
              APPROX_QUANTILES(CAST(loan_amount AS FLOAT64), 2)[OFFSET(1)] AS median_loan_amount,
              AVG(CAST(interest_rate AS FLOAT64)) AS avg_interest_rate
            FROM `{self.table}`
            WHERE as_of_year = @year
              AND CAST(derived_msa_md AS STRING) = @cbsa
              AND property_value IS NOT NULL
              AND loan_amount IS NOT NULL
              AND interest_rate IS NOT NULL
            GROUP BY cbsa
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("year", "INT64", year),
                bigquery.ScalarQueryParameter("cbsa", "STRING", cbsa),
            ]
        )
        query_job = self.client.query(query, job_config=job_config)
        result = list(query_job.result())
        if not result:
            raise RuntimeError(f"No HMDA results for CBSA {cbsa} in {self.table}")
        row = result[0]
        return {
            "cbsa": row["cbsa"],
            "name": row["cbsa_name"],
            "property_value": row["median_property_value"] or 0.0,
            "loan_amount": row["median_loan_amount"] or 0.0,
            "interest_rate": row["avg_interest_rate"] or 0.0,
        }


@dataclass
class LocationDataAssembler:
    """Combine ACS and HMDA pulls into a single defaults object."""

    acs_client: CensusACSClient
    hmda_client: HMDAClient

    def build_defaults(
        self,
        cbsa: str,
        *,
        acs_year: int = 2023,
        hmda_year: int = 2023,
        loan_term_months: int = 360,
    ) -> LocationFinancialDefaults:
        acs_metrics = self.acs_client.fetch_housing_metrics(cbsa, year=acs_year)
        hmda_metrics = self.hmda_client.fetch_cbsa_summary(cbsa, year=hmda_year)

        name = hmda_metrics.get("name") or acs_metrics.get("name") or f"CBSA {cbsa}"
        monthly_utilities = (
            acs_metrics.get("electricity", 0.0)
            + acs_metrics.get("gas", 0.0)
            + acs_metrics.get("water_sewer", 0.0)
            + acs_metrics.get("other_fuel", 0.0)
        )

        return LocationFinancialDefaults(
            cbsa=cbsa,
            name=name,
            median_income=acs_metrics.get("median_income", 0.0),
            median_rent=acs_metrics.get("median_rent", 0.0),
            property_value=hmda_metrics.get("property_value", 0.0),
            loan_amount=hmda_metrics.get("loan_amount", 0.0),
            interest_rate=hmda_metrics.get("interest_rate", 0.0),
            loan_term_months=loan_term_months,
            monthly_taxes=acs_metrics.get("real_estate_taxes", 0.0),
            monthly_insurance=acs_metrics.get("home_insurance", 0.0),
            monthly_utilities=monthly_utilities,
        )


def _to_float(value: Optional[str]) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Could not convert ACS value '{value}' to float") from exc
