from typing import List


def classify_discrepancies(
    income_result,
    identity_status: str,
    liability_status: str,
    detected_emi: float,
    declared_net: float,
    verified_net: float,
) -> List[str]:
    anomalies = []

    # Income discrepancy check (> 10% threshold)
    if declared_net > 0 and verified_net > 0:
        diff_pct = (abs(declared_net - verified_net) / declared_net) * 100
        if diff_pct > 10:
            anomalies.append("INCOME_OVERSTATED")

    # Identity mismatch
    if identity_status == "MISMATCH":
        anomalies.append("IDENTITY_MISMATCH")

    # Undisclosed debt
    if liability_status == "MISMATCH" and detected_emi > 0:
        anomalies.append("UNDISCLOSED_LIABILITY")

    return anomalies