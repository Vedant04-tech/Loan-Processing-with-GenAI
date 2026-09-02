from .models import ComparisonResult

try:
    from policies.policy_loader import load_policy
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    try:
        from policies.policy_loader import load_policy
    except ImportError:
        def load_policy(policy_name: str = "personal_loan") -> dict:
            return {}


def calculate_risk(result: ComparisonResult, policy_name: str = "personal_loan") -> ComparisonResult:
    policy = load_policy(policy_name)
    income_max_var = float(policy.get("income", {}).get("max_acceptable_variance_percent", 10.0))
    dti_standard_limit = float(policy.get("foir", {}).get("standard_threshold_percent", 50.0))

    score = 0
    reasons = []

    # Income discrepancy penalty
    if result.income_difference_percent > income_max_var:
        score += 35
        reasons.append(f"Declared income exceeds verified income by more than {income_max_var}%.")

    # Identity mismatch penalty
    if result.identity_status == "MISMATCH":
        score += 60
        reasons.append("Identity mismatch detected.")

    # Undisclosed liability penalty
    if result.liability_status == "MISMATCH":
        score += 30
        reasons.append("Potential undisclosed liability.")

    # Debt-to-income threshold penalty
    if result.dti_percent > dti_standard_limit:
        score += 35
        reasons.append(f"DTI exceeds standard policy threshold of {dti_standard_limit}%.")

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