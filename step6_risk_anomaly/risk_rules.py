from typing import Any
from pydantic import BaseModel
from policies.policy_loader import load_policy
from step5_calculation import IncomeMetrics, ObligationMetrics, StatementValidationResult, EligibilityResult


class RiskResult(BaseModel):
    score: float
    grade: str
    routing_color: str
    recommendation: str
    routing_reason: str
    factor_breakdown: dict[str, Any]


def calculate_risk_and_routing(
    income_metrics: IncomeMetrics,
    obligation_metrics: ObligationMetrics,
    statement_result: StatementValidationResult,
    eligibility_result: EligibilityResult,
    classified_anomalies: list[dict],
    is_llm_fallback: bool = False,
    policy_name: str = "personal_loan",
    step4_result: Any = None,
) -> RiskResult:
    policy = load_policy(policy_name)
    weights = policy.get("scoring_weights", {})
    thresholds = policy.get("routing_thresholds", {})
    foir_rules = policy.get("foir", {})
    income_rules = policy.get("income", {})

    base_score = float(weights.get("base_score", 100.0))
    major_deduction = float(weights.get("major_anomaly_deduction", 45.0))
    moderate_deduction = float(weights.get("moderate_anomaly_deduction", 25.0))
    minor_deduction = float(weights.get("minor_anomaly_deduction", 10.0))
    arithmetic_deduction = float(weights.get("arithmetic_mismatch_deduction", 30.0))
    eligibility_deduction = float(weights.get("eligibility_failure_deduction", 50.0))

    green_min_score = float(thresholds.get("green_min_score", 80.0))
    amber_min_score = float(thresholds.get("amber_min_score", 50.0))
    foir_high_risk = float(foir_rules.get("high_risk_threshold_percent", 65.0))
    foir_standard = float(foir_rules.get("standard_threshold_percent", 50.0))
    max_acceptable_income_var = float(income_rules.get("max_acceptable_variance_percent", 5.0))

    # Step 4 comparison consistency check
    step4_rec = None
    step4_risk = None
    step4_status = None
    if step4_result is not None:
        if isinstance(step4_result, dict):
            step4_rec = step4_result.get("recommendation")
            step4_risk = step4_result.get("risk_level")
            step4_status = step4_result.get("overall_status")
        else:
            step4_rec = getattr(step4_result, "recommendation", None)
            step4_risk = getattr(step4_result, "risk_level", None)
            step4_status = getattr(step4_result, "overall_status", None)

    step4_clean = True
    if step4_rec or step4_risk or step4_status:
        if str(step4_rec).upper() == "REJECT" or str(step4_risk).upper() == "HIGH" or str(step4_status).upper() == "MISMATCH":
            step4_clean = False

    major_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "major")
    moderate_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "moderate")
    minor_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "minor")

    # Point Deductions (Dynamic from policy)
    base_score -= (major_count * major_deduction) + (moderate_count * moderate_deduction) + (minor_count * minor_deduction)
    if not statement_result.is_valid:
        base_score -= arithmetic_deduction
    if not eligibility_result.passed:
        base_score -= eligibility_deduction

    final_score = max(0.0, min(100.0, round(base_score, 1)))
    grade = "Low" if final_score >= green_min_score else ("Moderate" if final_score >= amber_min_score else "High")

    # 3-Tier Routing Decision: GREEN / AMBER / RED
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
        recommendation = "auto_approve"
        routing_reason = "Application verified across all documents with low debt-to-income ratio and zero policy violations."
    elif (
        final_score < amber_min_score
        or not eligibility_result.passed
        or major_count > 0
        or obligation_metrics.foir_percentage > foir_high_risk
        or (step4_rec and str(step4_rec).upper() == "REJECT" and str(step4_risk).upper() == "HIGH")
    ):
        routing_color = "red"
        recommendation = "reject"
        reason_parts = []
        if final_score < amber_min_score:
            reason_parts.append(f"risk score {final_score}/100 below threshold ({amber_min_score})")
        if major_count > 0:
            reason_parts.append(f"{major_count} major anomaly(ies) found")
        if not eligibility_result.passed:
            reason_parts.append("policy eligibility failure")
        if obligation_metrics.foir_percentage > foir_high_risk:
            reason_parts.append(f"FOIR {obligation_metrics.foir_percentage}% exceeds limit {foir_high_risk}%")
        if not step4_clean and step4_rec and str(step4_rec).upper() == "REJECT":
            reason_parts.append("document cross-comparison rejected in Step 4")

        routing_reason = f"Application rejected: {', '.join(reason_parts)}." if reason_parts else f"Application rejected: risk score {final_score}/100, {major_count} major anomaly(ies) found."
    else:
        routing_color = "amber"
        recommendation = "human_review"
        if not step4_clean:
            routing_reason = "Routed for manual underwriting: document comparison flagged variances in Step 4."
        elif is_llm_fallback:
            routing_reason = "Routed for manual underwriting: automated LLM fallback engaged."
        else:
            routing_reason = f"Routed for manual underwriting: {moderate_count + minor_count} anomaly(ies) flagged."

    factors = {
        "income_consistency": "Verified" if income_metrics.income_variance_percent <= max_acceptable_income_var else "Variance Flagged",
        "employment_stability": "Stable" if eligibility_result.passed else "Review Needed",
        "credit_behaviour": "Good" if statement_result.is_valid else "Statement Variance",
        "emi_burden": "Low" if obligation_metrics.foir_percentage <= foir_standard else "High",
    }

    return RiskResult(
        score=final_score,
        grade=grade,
        routing_color=routing_color,
        recommendation=recommendation,
        routing_reason=routing_reason,
        factor_breakdown=factors,
    )

