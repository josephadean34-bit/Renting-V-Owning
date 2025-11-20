from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LocationFinancialDefaults:
    """Holds CBSA-level financial defaults assembled from ACS + HMDA."""

    cbsa: str
    name: str
    median_income: float
    median_rent: float
    property_value: float
    loan_amount: float
    interest_rate: float  # annual percentage, e.g., 6.25
    loan_term_months: int = 360
    monthly_taxes: float = 0.0
    monthly_insurance: float = 0.0
    monthly_utilities: float = 0.0

    @property
    def down_payment(self) -> float:
        return max(self.property_value - self.loan_amount, 0.0)

    @property
    def loan_to_value(self) -> float:
        if self.property_value == 0:
            return 0.0
        return self.loan_amount / self.property_value

    @property
    def owner_non_pi_costs(self) -> float:
        return self.monthly_taxes + self.monthly_insurance + self.monthly_utilities


@dataclass
class ScenarioAssumptions:
    """User-configurable knobs for the projection."""

    horizon_years: int = 30
    appreciation_rate: float = 0.03  # annual
    investment_return: float = 0.05  # annual
    savings_rate_of_income: float = 0.05  # renter investment contribution

    def __post_init__(self) -> None:
        if self.horizon_years <= 0:
            raise ValueError("horizon_years must be positive")
        if not 0 <= self.savings_rate_of_income <= 1:
            raise ValueError("savings_rate_of_income must be between 0 and 1")


@dataclass
class MonthlySnapshot:
    month: int
    home_value: Optional[float] = None
    equity: Optional[float] = None
    loan_balance: Optional[float] = None
    renter_portfolio: Optional[float] = None


@dataclass
class ComparisonResult:
    defaults: LocationFinancialDefaults
    assumptions: ScenarioAssumptions
    owner_monthly_cost: float
    renter_monthly_cost: float
    owner_equity: float
    renter_portfolio: float
    break_even_month: Optional[int]
    timeline: List[MonthlySnapshot] = field(default_factory=list)

    @property
    def better_option(self) -> str:
        if self.owner_equity > self.renter_portfolio:
            return "owning"
        if self.renter_portfolio > self.owner_equity:
            return "renting"
        return "tie"
