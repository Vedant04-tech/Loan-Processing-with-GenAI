import json
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from step6_risk_anomaly.schemas import AnomalyAssessment, ClassifiedAnomaly
from step6_risk_anomaly.discrepancy import Discrepancy
from step5_calculation import IncomeMetrics, ObligationMetrics, StatementValidationResult, EligibilityResult

load_dotenv()


def classify_anomalies_with_llm(
    applicant_data: dict,
    income_metrics: IncomeMetrics,
    obligation_metrics: ObligationMetrics,
    statement_result: StatementValidationResult,
    eligibility_result: EligibilityResult,
    discrepancies: list[Discrepancy],
) -> tuple[AnomalyAssessment, bool]:
    """
    Step 6.2: Uses LangChain ChatGroq with structured Pydantic output to evaluate
    severity (Minor / Moderate / Major) of pre-detected discrepancies.
    Includes deterministic fallback.
    """
    if not discrepancies:
        return AnomalyAssessment(anomalies=[], underwriting_summary="All document checks and calculations verified without discrepancies."), False

    groq_api_key = os.getenv("GROQ_API_KEY")

    # 1. ChatGroq Structured LLM call
    if groq_api_key and groq_api_key != "your_groq_api_key_here":
        try:
            llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0, groq_api_key=groq_api_key, max_retries=1)
            structured_llm = llm.with_structured_output(AnomalyAssessment)

            prompt = f"""
You are an Underwriting Anomaly Classifier. Classify the severity of each pre-detected discrepancy into Minor, Moderate, or Major.
Do NOT calculate numbers.

APPLICANT CONTEXT:
- Name: {(applicant_data.get('applicants') or [{}])[0].get('full_name')}
- Verified Monthly Income: Rs. {income_metrics.verified_monthly_income:,.2f}
- FOIR: {obligation_metrics.foir_percentage}%
- Statement Status: {statement_result.status}
- Eligibility: {eligibility_result.status}

DISCREPANCIES DETECTED:
{json.dumps([d.model_dump() for d in discrepancies], indent=2)}
"""
            result = structured_llm.invoke(prompt)
            if isinstance(result, AnomalyAssessment):
                return result, False
        except Exception as e:
            print(f"[WARN] LLM fallback active: {e}")

    # 2. Deterministic Safe Fallback
    fallback_items = []
    for d in discrepancies:
        t = d.discrepancy_type
        if t == "INCOME_MISMATCH":
            sev = "Major" if (d.difference_percent or 0) > 15.0 else ("Moderate" if (d.difference_percent or 0) > 5.0 else "Minor")
            reason = f"Income variance of {d.difference_percent}% between application and salary documents."
        elif t == "UNDISCLOSED_LIABILITY":
            sev = "Major" if (d.difference_amount or 0) > 10000.0 else "Moderate"
            reason = f"Undisclosed monthly EMI of Rs. {d.difference_amount:,.2f} found in bank transactions."
        elif t in ("STATEMENT_ARITHMETIC_MISMATCH", "ELIGIBILITY_FAILURE"):
            sev = "Major"
            reason = d.evidence_summary
        else:
            sev = "Moderate"
            reason = d.evidence_summary

        fallback_items.append(ClassifiedAnomaly(discrepancy_type=t, severity=sev, reasoning=reason))

    return AnomalyAssessment(anomalies=fallback_items, underwriting_summary=f"Evaluated {len(fallback_items)} discrepancy(ies) via deterministic underwriting rules."), True
