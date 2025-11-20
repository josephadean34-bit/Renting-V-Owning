from __future__ import annotations

import json
import os
from typing import Optional

import typer

from .data_sources import CensusACSClient, HMDAClient, LocationDataAssembler
from .model import compare_scenarios
from .schemas import ScenarioAssumptions

app = typer.Typer(help="Compare economic gains from renting versus owning.")


def _default_census_key() -> Optional[str]:
    return os.environ.get("CENSUS_API_KEY")


def _default_hmda_table() -> str:
    return os.environ.get("HMDA_TABLE", "bigquery-public-data.hmda.hmda_2023")


@app.command()
def run(
    cbsa: str = typer.Argument(..., help="CBSA code, e.g., 31080 for Los Angeles."),
    acs_year: int = typer.Option(2023, help="ACS vintage to query."),
    hmda_year: int = typer.Option(2023, help="HMDA filing year to query."),
    census_api_key: Optional[str] = typer.Option(
        default_factory=_default_census_key,
        help="Census API key (env CENSUS_API_KEY if omitted).",
    ),
    hmda_table: str = typer.Option(
        default_factory=_default_hmda_table,
        help="Fully-qualified HMDA BigQuery table.",
    ),
    gcp_project: Optional[str] = typer.Option(
        None, help="GCP project for the BigQuery client (defaults to env)."
    ),
    appreciation_rate: float = typer.Option(
        0.03, help="Annual home price appreciation assumption (e.g., 0.03 for 3%)."
    ),
    investment_return: float = typer.Option(
        0.05, help="Annual investment return for renter savings."
    ),
    savings_rate: float = typer.Option(
        0.05, help="Share of income invested monthly by the renter."
    ),
    horizon_years: int = typer.Option(30, help="Projection horizon in years."),
    show_timeline: bool = typer.Option(
        False, help="If set, dump the monthly timeline as JSON."
    ),
) -> None:
    """
    Fetch ACS + HMDA data for the CBSA, build defaults, and compare scenarios.
    """
    acs_client = CensusACSClient(api_key=census_api_key)
    hmda_client = HMDAClient(table=hmda_table, project=gcp_project)
    assembler = LocationDataAssembler(acs_client=acs_client, hmda_client=hmda_client)
    defaults = assembler.build_defaults(
        cbsa, acs_year=acs_year, hmda_year=hmda_year, loan_term_months=360
    )

    assumptions = ScenarioAssumptions(
        horizon_years=horizon_years,
        appreciation_rate=appreciation_rate,
        investment_return=investment_return,
        savings_rate_of_income=savings_rate,
    )
    result = compare_scenarios(defaults, assumptions)

    typer.echo(f"Location: {defaults.name} (CBSA {defaults.cbsa})")
    typer.echo(f"Median income: ${defaults.median_income:,.0f}")
    typer.echo(f"Median rent: ${defaults.median_rent:,.0f}")
    typer.echo(f"Median property value: ${defaults.property_value:,.0f}")
    typer.echo(f"Median loan amount: ${defaults.loan_amount:,.0f}")
    typer.echo(f"Mortgage rate: {defaults.interest_rate:.2f}%")
    typer.echo("")
    typer.echo(
        f"Monthly homeowner cost (PITI+utilities): ${result.owner_monthly_cost:,.0f}"
    )
    typer.echo(f"Monthly rent: ${result.renter_monthly_cost:,.0f}")
    typer.echo("")
    typer.echo(f"Owner ending equity: ${result.owner_equity:,.0f}")
    typer.echo(f"Renter ending portfolio: ${result.renter_portfolio:,.0f}")
    typer.echo(f"Better outcome: {result.better_option}")
    if result.break_even_month:
        years = result.break_even_month / 12
        typer.echo(f"Break-even month: {result.break_even_month} (~{years:.1f} years)")

    if show_timeline:
        payload = [
            {
                "month": snap.month,
                "home_value": snap.home_value,
                "equity": snap.equity,
                "loan_balance": snap.loan_balance,
                "renter_portfolio": snap.renter_portfolio,
            }
            for snap in result.timeline
        ]
        typer.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    app()
