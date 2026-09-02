from typing import Any, Dict, List, Optional
from .models import Step5Result, IncomeMetrics, ObligationMetrics, StatementValidationResult, EligibilityResult
from .income import calculate_verified_income
from .obligations import calculate_obligations
from .statement import validate_statement_arithmetic
from .eligibility import check_eligibility


def build_step5_result(
    application_data: Dict[str, Any],
    bank_transactions: Optional[List[Dict[str, Any]]] = None,
    policy_name: str = "personal_loan",
) -> Step5Result:
    """
    Step 5 Orchestrator:
    Extracts raw figures from application/documents and runs deterministic
    calculations for income, debt obligations, statement arithmetic, and policy eligibility.
    """
    app_id = application_data.get("_id") or application_data.get("application_ref") or "UNKNOWN"
    documents = application_data.get("documents") or []

    payslips = [d for d in documents if (d.get("doc_type") or "").upper() in ("PAYSLIP", "SALARY_SLIP")]
    bank_stmts = [d for d in documents if (d.get("doc_type") or "").upper() in ("BANK_STATEMENT",)]
    loan_apps = [d for d in documents if (d.get("doc_type") or "").upper() in ("LOAN_APPLICATION",)]
    form16s = [d for d in documents if (d.get("doc_type") or "").upper() in ("FORM16", "FORM_16")]

    loan_ext = (loan_apps[0].get("extracted") or {}) if loan_apps else {}
    financials = application_data.get("financials") or {}
    loan_req = financials.get("loan_request") or {}

    declared_inc_val = (
        loan_ext.get("net_monthly")
        or loan_ext.get("gross_monthly")
        or loan_req.get("declared_net_monthly")
        or financials.get("declared_net_monthly")
        or 0.0
    )
    declared_inc = float(declared_inc_val)
    declared_libs = loan_ext.get("liabilities") or loan_req.get("declared_liabilities") or []
    proposed_emi = float(financials.get("proposed_emi") or 0.0)

    bank_ext = (bank_stmts[0].get("extracted") or {}) if bank_stmts else {}
    txns = bank_transactions or bank_ext.get("transactions") or []

    # 1. Verified Income Calculation
    income_metrics = calculate_verified_income(
        declared_income=declared_inc,
        payslips=payslips,
        bank_transactions=txns,
        form16=(form16s[0].get("extracted") if form16s else None),
    )

    # 2. Obligation & Debt Math
    obligation_metrics = calculate_obligations(
        declared_liabilities=declared_libs,
        bank_transactions=txns,
        verified_monthly_income=income_metrics.verified_monthly_income,
        proposed_emi=proposed_emi,
        loan_request=loan_req or loan_ext,
    )

    # 3. Bank Statement Balance Arithmetic Reconciliation
    statement_result = validate_statement_arithmetic(
        opening_balance=float(bank_ext.get("opening_balance") or 0.0),
        total_credits=float(bank_ext.get("total_credits") or 0.0),
        total_debits=float(bank_ext.get("total_debits") or 0.0),
        closing_balance=float(bank_ext.get("closing_balance") or 0.0),
        is_provided=bool(bank_stmts),
    )

    # 4. Multi-Rule Policy Eligibility Check
    eligibility_result = check_eligibility(
        verified_income=income_metrics.verified_monthly_income,
        foir_percentage=obligation_metrics.foir_percentage,
        income_variance_percent=income_metrics.income_variance_percent,
        undisclosed_liability_gap=obligation_metrics.undisclosed_liability_gap,
        policy_name=policy_name,
    )

    return Step5Result(
        applicant_id=str(app_id),
        income_metrics=income_metrics,
        obligation_metrics=obligation_metrics,
        statement_validation=statement_result,
        eligibility_result=eligibility_result,
    )
