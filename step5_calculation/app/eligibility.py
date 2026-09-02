from policies.policy_loader import load_policy
from .models import EligibilityResult


def check_eligibility(
    verified_income: float,
    foir_percentage: float,
    income_variance_percent: float,
    undisclosed_liability_gap: float,
    policy_name: str = "personal_loan",
) -> EligibilityResult:
    policy = load_policy(policy_name)
    reasons = []

    # 1. FOIR limit check
    foir_limit = float(policy.get("foir", {}).get("standard_threshold_percent", 50.0))
    if foir_percentage > foir_limit:
        reasons.append(f"FOIR {foir_percentage}% exceeds policy threshold of {foir_limit}%")

    # 2. Minimum Income check
    min_inc = float(policy.get("income", {}).get("min_monthly_net_income", 25000.0))
    if verified_income < min_inc:
        reasons.append(f"Income Rs. {verified_income:,.2f} is below minimum Rs. {min_inc:,.2f}")

    # 3. Severe Income variance check
    max_var = float(policy.get("income", {}).get("severe_variance_percent", 20.0))
    if income_variance_percent > max_var:
        reasons.append(f"Income overstatement ({income_variance_percent}%) exceeds {max_var}% limit")

    # 4. Undisclosed liability limit check
    max_undisc = float(policy.get("liabilities", {}).get("major_undisclosed_threshold", 10000.0))
    if undisclosed_liability_gap >= max_undisc:
        reasons.append(f"Undisclosed debt of Rs. {undisclosed_liability_gap:,.2f} exceeds tolerance")

    passed = len(reasons) == 0
    return EligibilityResult(
        passed=passed,
        status="PASS" if passed else "FAIL",
        reasons=reasons if not passed else ["All policy criteria satisfied."],
    )
