from typing import Any, Optional
from pydantic import BaseModel, Field
from policies.policy_loader import load_policy
from step5_calculation import IncomeMetrics, ObligationMetrics, StatementValidationResult, EligibilityResult


class RiskResult(BaseModel):
    score: float
    grade: str
    routing_color: str
    recommendation: str  # "recommend_approve" | "recommend_review" | "recommend_reject"
    routing_reason: str
    requires_human_signoff: bool = True  # Every outcome strictly requires human underwriter sign-off
    factor_breakdown: dict[str, Any]
    reviewer_checklist: list[str] = Field(default_factory=list)
    counterfactual_note: Optional[str] = None


def calculate_risk_and_routing(
    income_metrics: IncomeMetrics,
    obligation_metrics: ObligationMetrics,
    statement_result: StatementValidationResult,
    eligibility_result: EligibilityResult,
    classified_anomalies: list[dict],
    is_llm_fallback: bool = False,
    policy_name: str = "personal_loan",
    step4_result: Any = None,
    suggested_actions: list[str] | None = None,
) -> RiskResult:
    policy = load_policy(policy_name)
    weights = policy.get("scoring_weights", {})
    thresholds = policy.get("routing_thresholds", {})
    foir_rules = policy.get("foir", {})
    income_rules = policy.get("income", {})

    base_score_initial = float(weights.get("base_score", 100.0))
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
        if str(step4_rec).upper() in ("REJECT", "RECOMMEND_REJECT") or str(step4_risk).upper() == "HIGH" or str(step4_status).upper() == "MISMATCH":
            step4_clean = False

    major_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "major")
    moderate_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "moderate")
    minor_count = sum(1 for a in classified_anomalies if a.get("severity", "").lower() == "minor")

    # Point Deductions (Dynamic from policy)
    running_score = base_score_initial
    major_pts = major_count * major_deduction
    mod_pts = moderate_count * moderate_deduction
    min_pts = minor_count * minor_deduction
    running_score -= (major_pts + mod_pts + min_pts)

    stmt_pts = arithmetic_deduction if not statement_result.is_valid else 0.0
    running_score -= stmt_pts

    elig_pts = eligibility_deduction if not eligibility_result.passed else 0.0
    running_score -= elig_pts

    final_score = max(0.0, min(100.0, round(running_score, 1)))
    grade = "Low" if final_score >= green_min_score else ("Moderate" if final_score >= amber_min_score else "High")

    # 3-Tier Routing Decision: GREEN / AMBER / RED (Reframed as Underwriter Recommendations)
    checklist: list[str] = []
    counterfactual: Optional[str] = None

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
        routing_reason = "Fast-track: all checks passed, no discrepancies. Recommended for expedited approver sign-off."
        counterfactual = "Meets all automated underwriting guidelines for fast-track approval."
        checklist = [
            "Confirm applicant identity match across KYC proofs",
            "Verify one-click fast-track sign-off for loan disbursement"
        ]
    elif (
        final_score < amber_min_score
        or not eligibility_result.passed
        or major_count > 0
        or obligation_metrics.foir_percentage > foir_high_risk
        or (step4_rec and str(step4_rec).upper() in ("REJECT", "RECOMMEND_REJECT") and str(step4_risk).upper() == "HIGH")
    ):
        routing_color = "red"
        recommendation = "recommend_reject"
        reason_parts = []
        if final_score < amber_min_score:
            reason_parts.append(f"risk score {final_score}/100 below threshold ({amber_min_score})")
        if major_count > 0:
            reason_parts.append(f"{major_count} major anomaly(ies) found")
        if not eligibility_result.passed:
            reason_parts.append("policy eligibility failure")
        if obligation_metrics.foir_percentage > foir_high_risk:
            reason_parts.append(f"FOIR {obligation_metrics.foir_percentage}% exceeds limit {foir_high_risk}%")
        if not step4_clean and step4_rec and str(step4_rec).upper() in ("REJECT", "RECOMMEND_REJECT"):
            reason_parts.append("document cross-comparison rejected in Step 4")

        routing_reason = f"Application flagged for rejection: {', '.join(reason_parts)}." if reason_parts else f"Application flagged for rejection: risk score {final_score}/100, {major_count} major anomaly(ies) found."
        
        # Build Counterfactual note
        cf_items = []
        if obligation_metrics.foir_percentage > foir_standard:
            cf_items.append(f"FOIR were reduced to ≤ {foir_standard}% (currently {obligation_metrics.foir_percentage}%)")
        if income_metrics.income_variance_percent > max_acceptable_income_var:
            cf_items.append(f"income variance was within {max_acceptable_income_var}% (currently {income_metrics.income_variance_percent}%)")
        if obligation_metrics.undisclosed_liability_gap > 1000.0:
            cf_items.append(f"undisclosed debt of Rs. {obligation_metrics.undisclosed_liability_gap:,.2f} is cleared or documented")
        if not statement_result.is_valid:
            cf_items.append("bank statement reconciliation discrepancies are resolved with verified e-statement")
        
        counterfactual = f"Would move to GREEN/AMBER if: {'; and '.join(cf_items)}." if cf_items else "Would require complete re-submission of verified identity and financial documents."

        checklist = suggested_actions or [
            "Issue formal adverse action notice specifying policy breach items",
            "Verify whether applicant qualifies under collateralized credit programs"
        ]
    else:
        routing_color = "amber"
        recommendation = "recommend_review"
        if not step4_clean:
            routing_reason = "Routed for manual underwriting: document comparison flagged variances in Step 4."
        elif is_llm_fallback:
            routing_reason = "Routed for manual underwriting: automated LLM fallback engaged."
        else:
            routing_reason = f"Routed for manual underwriting: {moderate_count + minor_count} anomaly(ies) flagged."

        # Build Counterfactual note for Amber
        cf_items = []
        if income_metrics.income_variance_percent > max_acceptable_income_var:
            cf_items.append(f"income variance ({income_metrics.income_variance_percent}%) is verified via Form 16 / ITR")
        if obligation_metrics.undisclosed_liability_gap > 0:
            cf_items.append(f"unstated EMI gap of Rs. {obligation_metrics.undisclosed_liability_gap:,.2f} is explained")
        counterfactual = f"Would move to fast-track GREEN approval if: {'; and '.join(cf_items)}." if cf_items else "Would move to GREEN once manual verification of flagged items is completed."

        checklist = suggested_actions or [
            "Review flagged moderate discrepancies against secondary KYC documents",
            "Obtain underwriter managerial sign-off for policy deviation"
        ]

    # Quantified Factor Breakdown ("Show your work" for compliance auditing)
    factor_breakdown = {
        "base_score": base_score_initial,
        "major_anomalies_deduction": -round(major_pts, 1),
        "moderate_anomalies_deduction": -round(mod_pts, 1),
        "minor_anomalies_deduction": -round(min_pts, 1),
        "statement_arithmetic_deduction": -round(stmt_pts, 1),
        "eligibility_failure_deduction": -round(elig_pts, 1),
        "final_calculated_score": final_score,
        "itemized_anomalies_count": {
            "major": major_count,
            "moderate": moderate_count,
            "minor": minor_count,
        },
        "qualitative_indicators": {
            "income_consistency": "Verified" if income_metrics.income_variance_percent <= max_acceptable_income_var else "Variance Flagged",
            "employment_stability": "Stable" if eligibility_result.passed else "Review Needed",
            "credit_behaviour": "Good" if statement_result.is_valid else "Statement Variance",
            "emi_burden": "Low" if obligation_metrics.foir_percentage <= foir_standard else "High",
        }
    }

    return RiskResult(
        score=final_score,
        grade=grade,
        routing_color=routing_color,
        recommendation=recommendation,
        routing_reason=routing_reason,
        requires_human_signoff=True,
        factor_breakdown=factor_breakdown,
        reviewer_checklist=checklist,
        counterfactual_note=counterfactual,
    )


