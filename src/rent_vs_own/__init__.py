"""
Rent vs. Own comparison toolkit.

This package combines American Community Survey (ACS) and HMDA data to
generate default assumptions for housing and investment scenarios, then
simulates long-term wealth outcomes for renting versus owning.
"""

from .schemas import (
    LocationFinancialDefaults,
    ScenarioAssumptions,
    ComparisonResult,
    MonthlySnapshot,
)
from .model import compare_scenarios

__all__ = [
    "LocationFinancialDefaults",
    "ScenarioAssumptions",
    "ComparisonResult",
    "MonthlySnapshot",
    "compare_scenarios",
]
