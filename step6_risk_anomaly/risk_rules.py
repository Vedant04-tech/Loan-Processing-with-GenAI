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
) -> RiskResult:
    policy = load_policy(policy_name)
    weights = policy.get("scoring_weights", {})
    base_score = float(weights.get("base_score", 100.0))

    major_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "major")
    moderate_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "moderate")
    minor_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "minor")

    # Point Deductions
    base_score -= (major_count * 45.0) + (moderate_count * 25.0) + (minor_count * 10.0)
    if not statement_result.is_valid:
        base_score -= 30.0
    if not eligibility_result.passed:
        base_score -= 50.0

    final_score = max(0.0, min(100.0, round(base_score, 1)))
    grade = "Low" if final_score >= 80.0 else ("Moderate" if final_score >= 50.0 else "High")

    # 3-Tier Routing Decision: GREEN / AMBER / RED
    if final_score >= 80.0 and eligibility_result.passed and major_count == 0 and moderate_count == 0 and statement_result.is_valid and not is_llm_fallback:
        routing_color = "green"
        recommendation = "auto_approve"
        routing_reason = "Application verified across all documents with low debt-to-income ratio and zero policy violations."
    elif final_score < 50.0 or not eligibility_result.passed or major_count > 0 or obligation_metrics.foir_percentage > 65.0:
        routing_color = "red"
        recommendation = "reject"
        routing_reason = f"Application rejected: risk score {final_score}/100, {major_count} major anomaly(ies) found."
    else:
        routing_color = "amber"
        recommendation = "human_review"
        routing_reason = f"Routed for manual underwriting: {moderate_count + minor_count} anomaly(ies) flagged."

    factors = {
        "income_consistency": "Verified" if income_metrics.income_variance_percent <= 5.0 else "Variance Flagged",
        "employment_stability": "Stable" if eligibility_result.passed else "Review Needed",
        "credit_behaviour": "Good" if statement_result.is_valid else "Statement Variance",
        "emi_burden": "Low" if obligation_metrics.foir_percentage <= 40.0 else "High",
    }

    return RiskResult(
        score=final_score,
        grade=grade,
        routing_color=routing_color,
        recommendation=recommendation,
        routing_reason=routing_reason,
        factor_breakdown=factors,
    )
