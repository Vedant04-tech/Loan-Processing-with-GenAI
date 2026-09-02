from .models import StatementValidationResult


def validate_statement_arithmetic(
    opening_balance: float = 0.0,
    total_credits: float = 0.0,
    total_debits: float = 0.0,
    closing_balance: float = 0.0,
    max_error: float = 5.0,
    is_provided: bool = True,
) -> StatementValidationResult:
    if not is_provided:
        return StatementValidationResult(
            is_valid=False,
            status="MISSING",
            expected_closing_balance=0.0,
            actual_closing_balance=0.0,
            difference_amount=0.0,
            message="Bank statement document not provided in application package.",
        )

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
