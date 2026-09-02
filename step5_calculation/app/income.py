from .models import IncomeMetrics


def calculate_verified_income(
    declared_income: float,
    payslips: list[dict],
    bank_transactions: list[dict],
    form16: dict | None = None,
) -> IncomeMetrics:
    # 1. Average payslip net salary
    payslip_nets = [float(p.get("extracted", p).get("net_pay", 0)) for p in payslips if p.get("extracted", p).get("net_pay")]
    avg_payslip = sum(payslip_nets) / len(payslip_nets) if payslip_nets else 0.0

    # 2. Average bank salary credits
    salary_credits = [float(tx.get("amount", 0)) for tx in bank_transactions if tx.get("category") == "salary_credit" or tx.get("is_salary_match")]
    avg_bank_salary = sum(salary_credits) / len(salary_credits) if salary_credits else 0.0

    # 3. Verified income resolution (conservative minimum anti-fraud resolution)
    if avg_payslip > 0 and avg_bank_salary > 0:
        verified = min(avg_payslip, avg_bank_salary)
    elif avg_payslip > 0:
        verified = avg_payslip
    elif avg_bank_salary > 0:
        verified = avg_bank_salary
    else:
        verified = float(declared_income)

    # 4. Income variance calculation
    declared = float(declared_income)
    var_amt = round(abs(declared - verified), 2)
    var_pct = round((var_amt / verified) * 100, 2) if verified > 0 else 0.0

    return IncomeMetrics(
        declared_monthly_income=round(declared, 2),
        avg_payslip_income=round(avg_payslip, 2),
        avg_salary_credit=round(avg_bank_salary, 2),
        verified_monthly_income=round(verified, 2),
        income_variance=var_amt,
        income_variance_percent=var_pct,
    )
