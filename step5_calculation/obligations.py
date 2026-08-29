from pydantic import BaseModel


class ObligationMetrics(BaseModel):
    declared_total_emi: float
    detected_bank_monthly_emi: float
    undisclosed_liability_gap: float
    total_existing_emis: float
    proposed_emi: float
    total_monthly_obligations: float
    foir_percentage: float
    disposable_income: float
    has_undisclosed_liabilities: bool


def calculate_obligations(
    declared_liabilities: list[dict],
    bank_transactions: list[dict],
    verified_monthly_income: float,
    proposed_emi: float = 0.0,
    loan_request: dict | None = None,
) -> ObligationMetrics:
    # 1. Sum declared EMIs
    declared_emi = sum(float(l.get("emi_amount", 0) or l.get("emi", 0)) for l in declared_liabilities)

    # 2. Extract recurring bank EMI debits
    bank_emis = [abs(float(tx.get("amount", 0))) for tx in bank_transactions if tx.get("category") == "emi_debit"]
    detected_emi = round(sum(bank_emis), 2)

    # 3. Detect undisclosed debt gap (loan stacking)
    undisclosed_gap = round(max(0.0, detected_emi - declared_emi), 2)
    has_undisclosed = undisclosed_gap > 1000.0

    # 4. Total EMIs & FOIR calculation
    total_existing = max(declared_emi, detected_emi)
    prop_emi = float(proposed_emi)
    if prop_emi <= 0 and loan_request:
        amt = float(loan_request.get("loan_amount_requested", 0))
        tenure = int(loan_request.get("tenure_months", 36))
        if amt > 0 and tenure > 0:
            r = 0.12 / 12  # Standard 12% annual interest estimation
            prop_emi = round((amt * r * ((1 + r) ** tenure)) / (((1 + r) ** tenure) - 1), 2)

    total_obligations = round(total_existing + prop_emi, 2)
    foir = round((total_obligations / verified_monthly_income) * 100, 2) if verified_monthly_income > 0 else 100.0
    disposable = round(max(0.0, verified_monthly_income - total_obligations), 2)

    return ObligationMetrics(
        declared_total_emi=round(declared_emi, 2),
        detected_bank_monthly_emi=round(detected_emi, 2),
        undisclosed_liability_gap=undisclosed_gap,
        total_existing_emis=round(total_existing, 2),
        proposed_emi=round(prop_emi, 2),
        total_monthly_obligations=total_obligations,
        foir_percentage=foir,
        disposable_income=disposable,
        has_undisclosed_liabilities=has_undisclosed,
    )
