from __future__ import annotations

from typing import Optional

from .schemas import (
    ComparisonResult,
    LocationFinancialDefaults,
    MonthlySnapshot,
    ScenarioAssumptions,
)


def compare_scenarios(
    defaults: LocationFinancialDefaults,
    assumptions: Optional[ScenarioAssumptions] = None,
) -> ComparisonResult:
    assumptions = assumptions or ScenarioAssumptions()
    months = assumptions.horizon_years * 12

    mortgage_payment = monthly_mortgage_payment(
        defaults.loan_amount, defaults.interest_rate, defaults.loan_term_months
    )
    mortgage_rate_monthly = annual_to_monthly_rate(defaults.interest_rate)
    appreciation_monthly = annual_to_monthly_growth(assumptions.appreciation_rate)
    investment_monthly = annual_to_monthly_growth(assumptions.investment_return)

    owner_monthly_cost = mortgage_payment + defaults.owner_non_pi_costs
    renter_monthly_cost = defaults.median_rent
    monthly_investment = (
        defaults.median_income / 12.0 * assumptions.savings_rate_of_income
    )

    balance = defaults.loan_amount
    home_value = defaults.property_value
    portfolio = 0.0
    break_even = None
    timeline: list[MonthlySnapshot] = []

    for month in range(1, months + 1):
        interest_payment = balance * mortgage_rate_monthly if balance > 0 else 0.0
        principal_payment = 0.0
        if balance > 0 and mortgage_payment > 0 and month <= defaults.loan_term_months:
            principal_portion = max(mortgage_payment - interest_payment, 0.0)
            principal_payment = min(principal_portion, balance)
            balance = max(balance - principal_payment, 0.0)

        home_value *= 1 + appreciation_monthly
        equity = max(home_value - balance, 0.0)

        portfolio = portfolio * (1 + investment_monthly) + monthly_investment

        if break_even is None and portfolio >= equity:
            break_even = month

        timeline.append(
            MonthlySnapshot(
                month=month,
                home_value=home_value,
                equity=equity,
                loan_balance=balance,
                renter_portfolio=portfolio,
            )
        )

    return ComparisonResult(
        defaults=defaults,
        assumptions=assumptions,
        owner_monthly_cost=owner_monthly_cost,
        renter_monthly_cost=renter_monthly_cost,
        owner_equity=timeline[-1].equity if timeline else 0.0,
        renter_portfolio=timeline[-1].renter_portfolio if timeline else 0.0,
        break_even_month=break_even,
        timeline=timeline,
    )


def monthly_mortgage_payment(
    principal: float, annual_rate_pct: float, term_months: int
) -> float:
    if principal <= 0 or term_months <= 0:
        return 0.0
    monthly_rate = annual_to_monthly_rate(annual_rate_pct)
    if monthly_rate == 0:
        return principal / term_months
    discount = (1 + monthly_rate) ** (-term_months)
    return principal * monthly_rate / (1 - discount)


def annual_to_monthly_rate(annual_rate_pct: float) -> float:
    if annual_rate_pct <= 0:
        return 0.0
    return annual_rate_pct / 100.0 / 12.0


def annual_to_monthly_growth(annual_rate: float) -> float:
    if annual_rate <= -1:
        raise ValueError("annual rate must be greater than -100%")
    return (1 + annual_rate) ** (1 / 12.0) - 1
