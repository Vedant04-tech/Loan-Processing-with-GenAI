from .models import ComparisonResult


def calculate_risk(result: ComparisonResult) -> ComparisonResult:
    score = 0
    reasons = []

    # Income discrepancy penalty
    if result.income_difference_percent > 10:
        score += 35
        reasons.append("Declared income exceeds verified income by more than 10%.")

    # Identity mismatch penalty
    if result.identity_status == "MISMATCH":
        score += 60
        reasons.append("Identity mismatch detected.")

    # Undisclosed liability penalty
    if result.liability_status == "MISMATCH":
        score += 30
        reasons.append("Potential undisclosed liability.")

    # Debt-to-income threshold penalty
    if result.dti_percent > 50:
        score += 35
        reasons.append("DTI exceeds standard policy threshold.")

    # Final risk level & recommendation
    if score >= 70:
        result.risk_level = "HIGH"
        result.recommendation = "REJECT"
    elif score >= 30:
        result.risk_level = "MEDIUM"
        result.recommendation = "REVIEW"
    else:
        result.risk_level = "LOW"
        result.recommendation = "AUTO_APPROVE"

    result.audit_notes = " ".join(reasons) if reasons else "No major risk triggers detected."
    return result