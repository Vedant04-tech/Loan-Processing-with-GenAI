from typing import List, Optional
from pydantic import BaseModel, Field


class IncomeMetrics(BaseModel):
    declared_monthly_income: float
    avg_payslip_income: float
    avg_salary_credit: float
    verified_monthly_income: float
    income_variance: float
    income_variance_percent: float


class ObligationMetrics(BaseModel):
    declared_total_emi: float
    detected_bank_monthly_emi: float
    undisclosed_liability_gap: float
    total_existing_emis: float
    proposed_emi: float
    total_monthly_obligations: float
    foir_percentage: float
    disposable_income: float
    has_undisclosed_liabilities: bool


class StatementValidationResult(BaseModel):
    is_valid: bool
    status: str
    expected_closing_balance: float
    actual_closing_balance: float
    difference_amount: float
    message: str


class EligibilityResult(BaseModel):
    passed: bool
    status: str
    reasons: List[str] = Field(default_factory=list)


class Step5Result(BaseModel):
    applicant_id: str
    income_metrics: IncomeMetrics
    obligation_metrics: ObligationMetrics
    statement_validation: StatementValidationResult
    eligibility_result: EligibilityResult
