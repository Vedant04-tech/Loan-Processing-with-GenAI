from .models import (
    Evidence,
    FieldComparison
)

from .normalizer import (
    normalize_name,
    normalize_text,
    normalize_pan,
    normalize_dob,
    to_float
)


def compare_identity(
    declared,
    verified
):

    results = []

    # --------------------------
    # NAME
    # --------------------------

    declared_name = declared.get(
        "name"
    )

    verified_name = verified.get(
        "name"
    )

    d = normalize_name(
        declared_name
    )

    v = normalize_name(
        verified_name
    )

    if d == v:

        status = "MATCH"

    elif d in v or v in d:

        status = "PARTIAL_MATCH"

    else:

        status = "MISMATCH"

    results.append(

        FieldComparison(

            field="name",

            declared_value=declared_name,

            verified_value=verified_name,

            normalized_declared=d,

            normalized_verified=v,

            status=status,

            comparison_method=
                "DETERMINISTIC",

            evidence=[

                Evidence(

                    source_document=
                        "LOAN_APPLICATION",

                    source_path=
                        "documents[].extracted.name",

                    field="name",

                    value=declared_name,

                    evidence_type=
                        "DECLARED"
                ),

                Evidence(

                    source_document=
                        "PAN/AADHAAR",

                    source_path=
                        "documents[].extracted.name",

                    field="name",

                    value=verified_name,

                    evidence_type=
                        "VERIFIED"
                )
            ],

            reason=
                f"Normalized comparison: "
                f"'{d}' vs '{v}'."
        )
    )

    # --------------------------
    # DOB
    # --------------------------

    declared_dob = normalize_dob(
        declared.get("dob")
    )

    verified_dob = normalize_dob(
        verified.get("dob")
    )

    if not declared_dob or not verified_dob:

        status = "NOT_AVAILABLE"

    elif declared_dob == verified_dob:

        status = "MATCH"

    else:

        status = "MISMATCH"

    results.append(

        FieldComparison(

            field="dob",

            declared_value=
                declared.get("dob"),

            verified_value=
                verified.get("dob"),

            normalized_declared=
                declared_dob,

            normalized_verified=
                verified_dob,

            status=status,

            comparison_method=
                "DETERMINISTIC",

            evidence=[],

            reason=
                "Exact DOB comparison."
        )
    )

    return results


# --------------------------------------------------
# INCOME
# --------------------------------------------------

def compare_income(
    declared,
    verified
):

    declared_income = to_float(
        declared.get(
            "net_monthly"
        )
    )

    verified_income = to_float(
        verified.get(
            "payslip_net_monthly"
        )
    )

    if (
        declared_income == 0
        or
        verified_income == 0
    ):

        status = "NOT_AVAILABLE"

        percentage = None

    else:

        difference = abs(
            declared_income
            -
            verified_income
        )

        percentage = round(
            difference
            /
            declared_income
            *
            100,
            2
        )

        if percentage <= 5:

            status = "MATCH"

        elif percentage <= 10:

            status = "PARTIAL_MATCH"

        else:

            status = "MISMATCH"

    difference = abs(
        declared_income
        -
        verified_income
    )

    return FieldComparison(

        field="net_monthly_income",

        declared_value=
            declared_income,

        verified_value=
            verified_income,

        normalized_declared=
            declared_income,

        normalized_verified=
            verified_income,

        status=status,

        discrepancy_amount=
            round(
                difference,
                2
            ),

        discrepancy_percent=
            percentage,

        comparison_method=
            "DETERMINISTIC",

        evidence=[

            Evidence(

                source_document=
                    "LOAN_APPLICATION",

                source_path=
                    "documents[].extracted.net_monthly",

                field=
                    "net_monthly_income",

                value=
                    declared_income,

                evidence_type=
                    "DECLARED"
            ),

            Evidence(

                source_document=
                    "PAYSLIP",

                source_path=
                    "documents[].extracted.net_pay",

                field=
                    "net_monthly_income",

                value=
                    verified_income,

                evidence_type=
                    "VERIFIED"
            )
        ],

        reason=
            f"Difference = ₹{difference:.2f}, "
            f"percentage difference = "
            f"{percentage}%."
    )
def compare_employer(
    declared,
    verified
):

    declared_employer = normalize_text(
        declared.get("employer")
    )

    verified_employer = normalize_text(
        verified.get("employer")
    )

    if not declared_employer or not verified_employer:

        status = "NOT_AVAILABLE"

    elif declared_employer == verified_employer:

        status = "MATCH"

    elif (
        declared_employer in verified_employer
        or
        verified_employer in declared_employer
    ):

        status = "PARTIAL_MATCH"

    else:

        status = "MISMATCH"

    return FieldComparison(

        field="employer",

        declared_value=
            declared.get("employer"),

        verified_value=
            verified.get("employer"),

        normalized_declared=
            declared_employer,

        normalized_verified=
            verified_employer,

        status=status,

        comparison_method=
            "DETERMINISTIC",

        evidence=[

            Evidence(

                source_document=
                    "LOAN_APPLICATION",

                source_path=
                    "documents[].extracted.employer",

                field="employer",

                value=
                    declared.get("employer"),

                evidence_type=
                    "DECLARED"
            ),

            Evidence(

                source_document=
                    "PAYSLIP/FORM16",

                source_path=
                    "documents[].extracted.employer_name",

                field="employer",

                value=
                    verified.get("employer"),

                evidence_type=
                    "VERIFIED"
            )
        ],

        reason=
            "Normalized employer comparison."
    )


def compare_pan(
    payload,
    verified
):

    applicant = payload.get(
        "applicant",
        {}
    )

    declared_pan = normalize_pan(
        applicant.get(
            "pan_number"
        )
    )

    verified_pan = normalize_pan(
        verified.get(
            "pan_number"
        )
    )

    if not declared_pan or not verified_pan:

        status = "NOT_AVAILABLE"

    elif declared_pan == verified_pan:

        status = "MATCH"

    else:

        status = "MISMATCH"

    return FieldComparison(

        field="pan_number",

        declared_value=
            declared_pan,

        verified_value=
            verified_pan,

        normalized_declared=
            declared_pan,

        normalized_verified=
            verified_pan,

        status=status,

        comparison_method=
            "DETERMINISTIC",

        evidence=[],

        reason=
            "Exact PAN comparison."
    )