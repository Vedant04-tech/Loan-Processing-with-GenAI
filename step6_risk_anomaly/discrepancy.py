from pydantic import BaseModel, Field
from step5_calculation.income import IncomeMetrics
from step5_calculation.obligations import ObligationMetrics
from step5_calculation.statement import StatementValidationResult
from step5_calculation.eligibility import EligibilityResult


class Discrepancy(BaseModel):
    discrepancy_type: str
    declared_value: str | None = None
    verified_value: str | None = None
    difference_amount: float | None = None
    difference_percent: float | None = None
    evidence_summary: str


def detect_discrepancies(
    application_data: dict,
    income_metrics: IncomeMetrics,
    obligation_metrics: ObligationMetrics,
    statement_result: StatementValidationResult,
    eligibility_result: EligibilityResult,
    extracted_fields: list[dict] = None,
) -> list[Discrepancy]:
    discrepancies = []

    # 1. Income Mismatch
    if income_metrics.income_variance_percent > 5.0:
        discrepancies.append(
            Discrepancy(
                discrepancy_type="INCOME_MISMATCH",
                declared_value=f"Rs. {income_metrics.declared_monthly_income:,.2f}",
                verified_value=f"Rs. {income_metrics.verified_monthly_income:,.2f}",
                difference_amount=income_metrics.income_variance,
                difference_percent=income_metrics.income_variance_percent,
                evidence_summary=f"Declared net income Rs. {income_metrics.declared_monthly_income:,.2f} differs from verified Rs. {income_metrics.verified_monthly_income:,.2f} by {income_metrics.income_variance_percent}%",
            )
        )

    # 2. Undisclosed Debt (Loan Stacking)
    if obligation_metrics.has_undisclosed_liabilities:
        discrepancies.append(
            Discrepancy(
                discrepancy_type="UNDISCLOSED_LIABILITY",
                declared_value=f"Rs. {obligation_metrics.declared_total_emi:,.2f}",
                verified_value=f"Rs. {obligation_metrics.detected_bank_monthly_emi:,.2f}",
                difference_amount=obligation_metrics.undisclosed_liability_gap,
                difference_percent=round((obligation_metrics.undisclosed_liability_gap / (obligation_metrics.declared_total_emi or 1.0)) * 100, 2),
                evidence_summary=f"Active recurring bank EMI debits of Rs. {obligation_metrics.detected_bank_monthly_emi:,.2f} exceed declared debt by Rs. {obligation_metrics.undisclosed_liability_gap:,.2f}",
            )
        )

    # 3. Bank Statement Balance Arithmetic Mismatch
    if not statement_result.is_valid:
        discrepancies.append(
            Discrepancy(
                discrepancy_type="STATEMENT_ARITHMETIC_MISMATCH",
                declared_value=f"Stated: Rs. {statement_result.actual_closing_balance:,.2f}",
                verified_value=f"Expected: Rs. {statement_result.expected_closing_balance:,.2f}",
                difference_amount=statement_result.difference_amount,
                evidence_summary=statement_result.message,
            )
        )

    # 4. Employer Mismatch
    applicant = (application_data.get("applicants") or [{}])[0]
    dec_emp = (applicant.get("employer_name") or "").strip().lower()
    docs = application_data.get("documents") or []
    pay_emps = [d.get("extracted", {}).get("employer_name", "").strip().lower() for d in docs if "PAYSLIP" in d.get("doc_type", "").upper() and d.get("extracted", {}).get("employer_name")]

    if dec_emp and pay_emps and dec_emp not in pay_emps[0] and pay_emps[0] not in dec_emp:
        discrepancies.append(
            Discrepancy(
                discrepancy_type="EMPLOYMENT_MISMATCH",
                declared_value=applicant.get("employer_name"),
                verified_value=pay_emps[0],
                evidence_summary=f"Declared employer '{applicant.get('employer_name')}' differs from payslip employer '{pay_emps[0]}'",
            )
        )

    # 5. Policy Eligibility Failure
    if not eligibility_result.passed:
        discrepancies.append(
            Discrepancy(
                discrepancy_type="ELIGIBILITY_FAILURE",
                declared_value="Policy Criteria",
                verified_value="Failed",
                evidence_summary="; ".join(eligibility_result.reasons),
            )
        )

    return discrepancies
