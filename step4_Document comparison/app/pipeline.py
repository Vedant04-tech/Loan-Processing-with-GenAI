from typing import Any, Dict
from .extractors import extract_declared, extract_verified, extract_liabilities
from .comparison import compare_identity, compare_income, compare_employer, compare_pan
from .llm_semantic import semantic_compare
from .discrepancy import classify_discrepancies
from .models import ComparisonResult, Evidence
from .policy_engine import calculate_risk


def build_pipeline_result(payload: Dict[str, Any]) -> ComparisonResult:
    # 1. Extraction & Normalization
    declared = extract_declared(payload)
    verified = extract_verified(payload)
    liabilities = extract_liabilities(payload)

    # 2. Deterministic Comparison
    identity_results = compare_identity(declared, verified)
    identity_results.append(compare_pan(payload, verified))

    income_result = compare_income(declared, verified)
    employer_result = compare_employer(declared, verified)

    deterministic_results = identity_results + [income_result, employer_result]

    # 3. LLM Semantic Text Comparison
    semantic_results = semantic_compare(declared, verified)

    # 4. Determine Composite Identity Status
    identity_statuses = [r.status for r in identity_results]
    if "MISMATCH" in identity_statuses:
        identity_status = "MISMATCH"
    elif "PARTIAL_MATCH" in identity_statuses:
        identity_status = "PARTIAL_MATCH"
    elif all(s == "MATCH" for s in identity_statuses):
        identity_status = "MATCH"
    else:
        identity_status = "NOT_AVAILABLE"

    # 5. Income Variance & Status
    declared_net = float(declared.get("net_monthly") or 0)
    verified_net = float(verified.get("payslip_net_monthly") or 0)
    income_difference = abs(declared_net - verified_net)
    income_difference_percent = round((income_difference / declared_net) * 100, 2) if declared_net > 0 else 0.0

    if income_result.status in ("MISMATCH", "PARTIAL_MATCH"):
        income_status = income_result.status
    else:
        income_status = income_result.status

    # 6. Liability Status
    declared_liabilities = liabilities["declared_liabilities"]
    detected_emi = liabilities["detected_emi"]

    if not declared_liabilities and detected_emi == 0:
        liability_status = "MATCH"
    elif not declared_liabilities and detected_emi > 0:
        liability_status = "MISMATCH"
    else:
        liability_status = "PARTIAL_MATCH"

    # 7. Overall Comparison Status
    statuses = [identity_status, income_status, liability_status]
    if "MISMATCH" in statuses:
        overall_status = "MISMATCH"
    elif "PARTIAL_MATCH" in statuses:
        overall_status = "PARTIAL_MATCH"
    else:
        overall_status = "MATCH"

    # 8. Debt-To-Income (DTI)
    dti = round((detected_emi / verified_net) * 100, 2) if verified_net > 0 else 0.0

    # 9. Classify Anomalies
    anomalies = classify_discrepancies(
        income_result=income_result,
        identity_status=identity_status,
        liability_status=liability_status,
        detected_emi=detected_emi,
        declared_net=declared_net,
        verified_net=verified_net,
    )

    # 10. Assemble Result
    result = ComparisonResult(
        applicant_id=str(payload.get("_id", payload.get("application_ref", ""))),
        identity_status=identity_status,
        income_status=income_status,
        liability_status=liability_status,
        overall_status=overall_status,
        declared_monthly_net=declared_net,
        verified_monthly_net=verified_net,
        income_difference=round(income_difference, 2),
        income_difference_percent=income_difference_percent,
        declared_emi=0.0,
        detected_emi=detected_emi,
        dti_percent=dti,
        discrepancies=deterministic_results,
        semantic_findings=semantic_results,
        anomalies=anomalies,
        evidence=[
            Evidence(
                source_document="BANK_STATEMENT",
                source_path="transactions[]",
                field="detected_emi",
                value=detected_emi,
                evidence_type="DERIVED",
                note="Only transactions classified as emi_debit are counted.",
            )
        ],
        risk_level="LOW",
        recommendation="REVIEW",
        audit_notes="",
    )

    # 11. Run Policy Evaluation
    return calculate_risk(result)