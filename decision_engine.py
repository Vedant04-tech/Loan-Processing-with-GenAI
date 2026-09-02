from datetime import datetime, timezone
from typing import Any
import importlib
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from database.db_config import get_db
from database import crud
from step5_calculation import (
    calculate_verified_income,
    IncomeMetrics,
    calculate_obligations,
    ObligationMetrics,
    validate_statement_arithmetic,
    StatementValidationResult,
    check_eligibility,
    EligibilityResult,
)
from step6_risk_anomaly import (
    detect_discrepancies,
    Discrepancy,
    classify_anomalies_with_llm,
    AnomalyAssessment,
    calculate_risk_and_routing,
    RiskResult,
)


class PipelineResult(BaseModel):
    application_ref: str
    status: str
    routing_color: str
    recommendation: str
    requires_human_signoff: bool = True
    risk_score: float
    risk_grade: str
    income_metrics: IncomeMetrics
    obligation_metrics: ObligationMetrics
    statement_validation: StatementValidationResult
    eligibility_result: EligibilityResult
    discrepancies: list[Discrepancy]
    anomaly_assessment: AnomalyAssessment
    reviewer_checklist: list[str] = Field(default_factory=list)
    counterfactual_note: Optional[str] = None
    is_llm_fallback: bool
    underwriting_summary: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



def run_decision_pipeline(
    application_ref: str,
    policy_name: str = "personal_loan",
    db: Any = None,
) -> PipelineResult:
    if db is None:
        db = get_db()

    # 1. Fetch data from MongoDB
    application = crud.get_application(db, application_ref)
    if not application:
        raise ValueError(f"Application '{application_ref}' not found in database.")

    evidence = crud.get_extracted_evidence(db, application_ref)
    bank_txns = crud.get_bank_transactions(db, application_ref)

    # 1.1 Run Step 4 Comparison Engine using DB data
    primary_applicant = application.get("applicants", [{}])[0] if application.get("applicants") else {}
    step4_payload = {
        "_id": application.get("application_ref"),
        "applicant": {
            "full_name": primary_applicant.get("full_name"),
            "pan_number": primary_applicant.get("pan_number"),
            "dob": primary_applicant.get("date_of_birth") or primary_applicant.get("dob"),
            "aadhaar_last4": primary_applicant.get("aadhaar_last4"),
        },
        "documents": application.get("documents", [])
    }

    try:
        step4_pipeline = importlib.import_module("step4_Document comparison.app.pipeline")
        step4_result = step4_pipeline.build_pipeline_result(step4_payload)
        crud.update_step4_comparison(db, application_ref, step4_result.model_dump())
    except Exception as e:
        print(f"[WARN] Step 4 Document comparison failed: {e}")
        step4_result = None

    documents = application.get("documents") or []
    payslips = [d for d in documents if d.get("doc_type") in ("PAYSLIP", "payslip")]
    bank_stmts = [d for d in documents if d.get("doc_type") in ("BANK_STATEMENT", "bank_statement")]
    loan_apps = [d for d in documents if d.get("doc_type") in ("LOAN_APPLICATION", "loan_application")]
    form16s = [d for d in documents if d.get("doc_type") in ("FORM16", "form16")]

    loan_ext = (loan_apps[0].get("extracted") or {}) if loan_apps else {}
    financials = application.get("financials") or {}
    loan_req = financials.get("loan_request") or {}

    # Extract declared income: Priority is given to LOAN_APPLICATION net_monthly,
    # then gross_monthly, then top-level application financial claims.
    # If entirely omitted in a malformed or partial mock payload, defaults to 0.0
    # so variance checks can explicitly flag the missing declaration.
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

    # 2. Step 5 Calculations (Deterministic Python)
    income_metrics = calculate_verified_income(
        declared_income=declared_inc,
        payslips=payslips,
        bank_transactions=bank_txns,
        form16=(form16s[0].get("extracted") if form16s else None),
    )

    obligation_metrics = calculate_obligations(
        declared_liabilities=declared_libs,
        bank_transactions=bank_txns,
        verified_monthly_income=income_metrics.verified_monthly_income,
        proposed_emi=proposed_emi,
        loan_request=loan_req or loan_ext,
    )

    statement_result = validate_statement_arithmetic(
        opening_balance=float(bank_ext.get("opening_balance") or 0.0),
        total_credits=float(bank_ext.get("total_credits") or 0.0),
        total_debits=float(bank_ext.get("total_debits") or 0.0),
        closing_balance=float(bank_ext.get("closing_balance") or 0.0),
        is_provided=bool(bank_stmts),
    )

    eligibility_result = check_eligibility(
        verified_income=income_metrics.verified_monthly_income,
        foir_percentage=obligation_metrics.foir_percentage,
        income_variance_percent=income_metrics.income_variance_percent,
        undisclosed_liability_gap=obligation_metrics.undisclosed_liability_gap,
        policy_name=policy_name,
    )

    # 3. Step 6 Risk & Anomaly Engine
    discrepancies = detect_discrepancies(
        application_data=application,
        income_metrics=income_metrics,
        obligation_metrics=obligation_metrics,
        statement_result=statement_result,
        eligibility_result=eligibility_result,
        extracted_fields=evidence,
        step4_result=step4_result,
        policy_name=policy_name,
    )

    anomaly_assessment, is_fallback = classify_anomalies_with_llm(
        applicant_data=application,
        income_metrics=income_metrics,
        obligation_metrics=obligation_metrics,
        statement_result=statement_result,
        eligibility_result=eligibility_result,
        discrepancies=discrepancies,
    )

    classified_list = [a.model_dump() for a in anomaly_assessment.anomalies]

    risk_result = calculate_risk_and_routing(
        income_metrics=income_metrics,
        obligation_metrics=obligation_metrics,
        statement_result=statement_result,
        eligibility_result=eligibility_result,
        classified_anomalies=classified_list,
        is_llm_fallback=is_fallback,
        policy_name=policy_name,
        step4_result=step4_result,
        suggested_actions=anomaly_assessment.suggested_actions,
    )

    # 4. MongoDB Writeback
    crud.update_financials(db, application_ref, {
        "verified_monthly_income": income_metrics.verified_monthly_income,
        "total_existing_emis": obligation_metrics.total_existing_emis,
        "proposed_emi": obligation_metrics.proposed_emi,
        "foir_percentage": obligation_metrics.foir_percentage,
        "foir_threshold": 50.0,
        "disposable_income": obligation_metrics.disposable_income,
        "eligibility_passed": eligibility_result.passed,
        "eligibility_reasons": eligibility_result.reasons,
        "loan_request": loan_req,
    })

    crud.clear_cross_checks(db, application_ref)
    for disc in discrepancies:
        matching = next((a for a in classified_list if a.get("discrepancy_type") == disc.discrepancy_type), {})
        sev = matching.get("severity", "minor").lower()
        crud.add_cross_check(db, application_ref, {
            "check_type": disc.discrepancy_type,
            "declared_value": disc.declared_value,
            "verified_value": disc.verified_value,
            "match_result": "mismatch" if sev == "major" else ("partial_match" if sev == "moderate" else "match"),
            "discrepancy_amount": disc.difference_amount,
            "severity": sev,
            "explanation": matching.get("reasoning") or disc.evidence_summary,
            "checked_at": datetime.now(timezone.utc),
        })

    crud.update_risk(
        db,
        application_ref,
        score=risk_result.score,
        grade=risk_result.grade,
        recommendation=risk_result.recommendation,
        factors=risk_result.factor_breakdown,
        requires_human_signoff=risk_result.requires_human_signoff,
        reviewer_checklist=risk_result.reviewer_checklist,
        counterfactual_note=risk_result.counterfactual_note,
    )
    crud.update_routing(db, application_ref, color=risk_result.routing_color, reason=risk_result.routing_reason)

    crud.log_audit_event(db, application_ref=application_ref, actor="pipeline:decision_engine", action=f"routed_{risk_result.routing_color}", detail={
        "risk_score": risk_result.score,
        "risk_grade": risk_result.grade,
        "foir": obligation_metrics.foir_percentage,
        "recommendation": risk_result.recommendation,
        "requires_human_signoff": True,
        "anomalies_count": len(classified_list),
        "discrepancies_count": len(discrepancies),
        "is_llm_fallback": is_fallback,
    })

    return PipelineResult(
        application_ref=application_ref,
        status="approved" if risk_result.routing_color == "green" else ("review" if risk_result.routing_color == "amber" else "rejected"),
        routing_color=risk_result.routing_color,
        recommendation=risk_result.recommendation,
        requires_human_signoff=risk_result.requires_human_signoff,
        risk_score=risk_result.score,
        risk_grade=risk_result.grade,
        income_metrics=income_metrics,
        obligation_metrics=obligation_metrics,
        statement_validation=statement_result,
        eligibility_result=eligibility_result,
        discrepancies=discrepancies,
        anomaly_assessment=anomaly_assessment,
        reviewer_checklist=risk_result.reviewer_checklist,
        counterfactual_note=risk_result.counterfactual_note,
        is_llm_fallback=is_fallback,
        underwriting_summary=anomaly_assessment.underwriting_summary,
    )


if __name__ == "__main__":
    import sys, os, json
    arg = sys.argv[1] if len(sys.argv) > 1 else "P002"

    # If a Step 4 comparison result JSON file is passed directly
    if arg.endswith(".json") and os.path.exists(arg):
        with open(arg, "r", encoding="utf-8") as f:
            step4_data = json.load(f)
        app_id = step4_data.get("applicant_id") or os.path.splitext(os.path.basename(arg))[0].replace("comparison_result_", "")
        print(f"Ingesting Step 4 Comparison File: {arg} -> Applicant: {app_id}")
    else:
        app_id = arg

    print(f"Running Decision Pipeline for: {app_id}")
    res = run_decision_pipeline(app_id)
    print(f"Decision: {res.routing_color.upper()} ({res.recommendation})")
    print(f"Requires Human Sign-off: {res.requires_human_signoff}")
    print(f"Risk Score: {res.risk_score}/100 ({res.risk_grade})")
    print(f"Verified Income: Rs. {res.income_metrics.verified_monthly_income:,.2f}")
    print(f"FOIR: {res.obligation_metrics.foir_percentage}%")
    print(f"Discrepancies: {len(res.discrepancies)}")
    print(f"Checklist: {res.reviewer_checklist}")
    print(f"Counterfactual Note: {res.counterfactual_note}")
    print(f"Summary: {res.underwriting_summary}")


