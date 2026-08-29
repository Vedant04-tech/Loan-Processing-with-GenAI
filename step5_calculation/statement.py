from pydantic import BaseModel


class StatementValidationResult(BaseModel):
    is_valid: bool
    status: str
    expected_closing_balance: float
    actual_closing_balance: float
    difference_amount: float
    message: str


def validate_statement_arithmetic(
    opening_balance: float,
    total_credits: float,
    total_debits: float,
    closing_balance: float,
    max_error: float = 5.0,
) -> StatementValidationResult:
    # Opening + Credits - Debits == Closing Balance
    op = float(opening_balance or 0)
    cr = float(total_credits or 0)
    dr = float(total_debits or 0)
    cl = float(closing_balance or 0)

    expected = round(op + cr - dr, 2)
    diff = round(abs(expected - cl), 2)
    is_valid = diff <= max_error

    return StatementValidationResult(
        is_valid=is_valid,
        status="MATCH" if is_valid else "MISMATCH",
        expected_closing_balance=expected,
        actual_closing_balance=cl,
        difference_amount=diff,
        message="Reconciled accurately" if is_valid else f"Arithmetic error: Expected Rs. {expected:,.2f} vs Actual Rs. {cl:,.2f} (diff: Rs. {diff:,.2f})",
    )
