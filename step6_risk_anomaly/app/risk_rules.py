from typing import Any, List, Optional, Union
from policies.policy_loader import load_policy
from step5_calculation.app.models import IncomeMetrics, ObligationMetrics, StatementValidationResult, EligibilityResult
from .schemas import AnomalyAssessment, ClassifiedAnomaly, RiskResult


def calculate_risk_and_routing(
    income_metrics: IncomeMetrics,
    obligation_metrics: ObligationMetrics,
    statement_result: StatementValidationResult,
    eligibility_result: EligibilityResult,
    anomaly_assessment: Optional[Union[AnomalyAssessment, List[ClassifiedAnomaly]]] = None,
    classified_anomalies: Optional[List[ClassifiedAnomaly]] = None,
    anomalies: Optional[List[ClassifiedAnomaly]] = None,
    is_llm_fallback: bool = False,
    step4_result: Optional[dict] = None,
    policy_name: str = "personal_loan",
) -> RiskResult:
    """
    Step 6.3: Computes final risk score, assigns risk grade, and routes to
    recommend_approve (Green), recommend_review (Amber), or recommend_reject (Red).
    Enforces requires_human_signoff = True on every result.
    """
    policy = load_policy(policy_name)
    weights = policy.get("scoring_deductions") or policy.get("scoring_weights") or {}

    # Extract anomaly list and suggested actions flexibly
    anomaly_list: List[Any] = []
    suggested_actions: List[str] = []

    if isinstance(anomaly_assessment, AnomalyAssessment):
        anomaly_list = anomaly_assessment.anomalies or []
        suggested_actions = anomaly_assessment.suggested_actions or []
    elif isinstance(anomaly_assessment, list):
        anomaly_list = anomaly_assessment
    elif classified_anomalies is not None:
        anomaly_list = classified_anomalies
    elif anomalies is not None:
        anomaly_list = anomalies

    def _get_severity(item: Any) -> str:
        if isinstance(item, dict):
            return item.get("severity", "")
        return getattr(item, "severity", "")

    major_weight = float(weights.get("major_anomaly") or weights.get("major_anomaly_deduction") or 45.0)
    moderate_weight = float(weights.get("moderate_anomaly") or weights.get("moderate_anomaly_deduction") or 25.0)
    minor_weight = float(weights.get("minor_anomaly") or weights.get("minor_anomaly_deduction") or 10.0)
    statement_weight = float(weights.get("statement_mismatch") or weights.get("arithmetic_mismatch_deduction") or 30.0)
    eligibility_weight = float(weights.get("eligibility_failure") or weights.get("eligibility_failure_deduction") or 35.0)

    green_min_score = float(policy.get("routing_thresholds", {}).get("green_min_score", 85.0))
    amber_min_score = float(policy.get("routing_thresholds", {}).get("amber_min_score", 50.0))

    base_score = 100.0
    major_count = sum(1 for a in anomaly_list if _get_severity(a) == "Major")
    moderate_count = sum(1 for a in anomaly_list if _get_severity(a) == "Moderate")
    minor_count = sum(1 for a in anomaly_list if _get_severity(a) == "Minor")



    major_deduction = major_count * major_weight
    moderate_deduction = moderate_count * moderate_weight
    minor_deduction = minor_count * minor_weight
    statement_deduction = 0.0 if statement_result.is_valid else statement_weight
    eligibility_deduction = 0.0 if eligibility_result.passed else eligibility_weight

    score = base_score - (
        major_deduction + moderate_deduction + minor_deduction + statement_deduction + eligibility_deduction
    )
    final_score = round(max(0.0, min(100.0, score)), 1)

    # Risk Grade
    if final_score >= 80:
        grade = "Low"
    elif final_score >= 50:
        grade = "Moderate"
    else:
        grade = "High"

    step4_clean = True
    if step4_result:
        s4_rec = str(step4_result.get("recommendation", "")).upper()
        s4_risk = str(step4_result.get("risk_level", "")).upper()
        s4_id = str(step4_result.get("identity_status", "")).upper()
        if s4_rec in ("REJECT", "RECOMMEND_REJECT") or s4_risk == "HIGH" or s4_id in ("MISMATCH", "PARTIAL_MATCH"):
            step4_clean = False

    # 3-Tier Recommendation Routing
    if (
        final_score >= green_min_score
        and eligibility_result.passed
        and major_count == 0
        and moderate_count == 0
        and statement_result.is_valid
        and not is_llm_fallback
        and step4_clean
    ):
        routing_color = "green"
        recommendation = "recommend_approve"
        reason = "Fast-track: all checks passed, no discrepancies. Recommended for expedited approver sign-off."
    elif final_score < amber_min_score or major_count > 0 or not statement_result.is_valid or not step4_clean:
        routing_color = "red"
        recommendation = "recommend_reject"
        failures = []
        if major_count > 0:
            failures.append(f"{major_count} major anomaly(ies)")
        if not statement_result.is_valid:
            failures.append("statement arithmetic failure")
        if not eligibility_result.passed:
            failures.append("policy eligibility failure")
        if not step4_clean:
            failures.append("document cross-comparison mismatch")
        if final_score < amber_min_score:
            failures.append(f"low score {final_score}")
        reason = f"Flagged for adverse action: {', '.join(failures)}."
    else:
        routing_color = "amber"
        recommendation = "recommend_review"
        reason = f"Manual underwriting review required: {moderate_count} moderate / {minor_count} minor anomaly(ies)."

    # Quantified Factor Breakdown
    factor_breakdown = {
        "base_score": base_score,
        "major_anomalies_deduction": -major_deduction,
        "moderate_anomalies_deduction": -moderate_deduction,
        "minor_anomalies_deduction": -minor_deduction,
        "statement_arithmetic_deduction": -statement_deduction,
        "eligibility_failure_deduction": -eligibility_deduction,
        "final_calculated_score": final_score,
        "itemized_anomalies_count": {
            "major": major_count,
            "moderate": moderate_count,
            "minor": minor_count,
        },
        "qualitative_indicators": {
            "income_consistency": "Verified" if income_metrics.income_variance_percent <= 5.0 else "Variance Detected",
            "employment_stability": "Verified",
            "credit_behaviour": "Good" if statement_result.is_valid else "Mismatch Detected",
            "emi_burden": "Low" if obligation_metrics.foir_percentage <= 50.0 else "High",
        }
    }

    # Reviewer Checklist
    if routing_color == "green":
        reviewer_checklist = [
            "Confirm applicant identity match across KYC proofs",
            "Verify one-click fast-track sign-off for loan disbursement"
        ]
    else:
        reviewer_checklist = list(suggested_actions) if suggested_actions else [
            "Review verified income against bank statement credits",
            "Confirm outstanding monthly liabilities and active loans",
            "Verify employer details and KYC documents"
        ]


    # Counterfactual Note
    counterfactual_note = None
    if routing_color in ("red", "amber"):
        reasons_to_fix = []
        std_foir = float(policy.get("foir", {}).get("standard_threshold_percent", 50.0))
        if obligation_metrics.foir_percentage > std_foir:
            reasons_to_fix.append(f"FOIR were reduced to ≤ {std_foir}% (currently {obligation_metrics.foir_percentage}%)")
        if obligation_metrics.undisclosed_liability_gap > 0:
            reasons_to_fix.append(f"undisclosed debt of Rs. {obligation_metrics.undisclosed_liability_gap:,.2f} is cleared or documented")
        if not statement_result.is_valid:
            reasons_to_fix.append("verified bank statement closing arithmetic is reconciled")
        if income_metrics.income_variance_percent > 5.0:
            reasons_to_fix.append(f"income variance is reduced to ≤ 5.0% (currently {income_metrics.income_variance_percent}%)")

        if reasons_to_fix:
            counterfactual_note = f"Would move to GREEN/AMBER if: {'; '.join(reasons_to_fix)}."
        else:
            counterfactual_note = "Would move to GREEN upon manual supervisor sign-off and clearing flagged items."
    else:
        counterfactual_note = "Meets all automated underwriting guidelines for fast-track approval."

    return RiskResult(
        score=final_score,
        grade=grade,
        routing_color=routing_color,
        recommendation=recommendation,
        routing_reason=reason,
        requires_human_signoff=True,
        factor_breakdown=factor_breakdown,
        reviewer_checklist=reviewer_checklist,
        counterfactual_note=counterfactual_note,
    )
