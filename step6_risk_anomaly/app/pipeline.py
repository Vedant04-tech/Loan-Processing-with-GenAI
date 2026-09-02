from typing import Any, Dict, List, Optional
from step5_calculation.app.models import Step5Result, IncomeMetrics, ObligationMetrics, StatementValidationResult, EligibilityResult
from .schemas import Step6Result, Discrepancy, AnomalyAssessment, RiskResult
from .discrepancy import detect_discrepancies
from .anomaly_classifier import classify_anomalies_with_llm
from .risk_rules import calculate_risk_and_routing


def build_step6_result(
    application_data: Dict[str, Any],
    step5_result: Step5Result,
    step4_result: Optional[Any] = None,
    extracted_fields: Optional[List[Dict[str, Any]]] = None,
    policy_name: str = "personal_loan",
) -> Step6Result:
    """
    Step 6 Orchestrator:
    Aggregates discrepancies from Step 4 and Step 5, classifies severity using LLM/rules,
    computes quantitative risk score, factor breakdown, checklist, and routing recommendations.
    """
    app_id = application_data.get("_id") or application_data.get("application_ref") or "UNKNOWN"

    # 1. Detect multi-document & policy discrepancies
    discrepancies = detect_discrepancies(
        application_data=application_data,
        income_metrics=step5_result.income_metrics,
        obligation_metrics=step5_result.obligation_metrics,
        statement_result=step5_result.statement_validation,
        eligibility_result=step5_result.eligibility_result,
        extracted_fields=extracted_fields,
        step4_result=step4_result,
        policy_name=policy_name,
    )

    # 2. LLM anomaly classification with safe deterministic fallback
    anomaly_assessment, is_fallback = classify_anomalies_with_llm(
        applicant_data=application_data,
        income_metrics=step5_result.income_metrics,
        obligation_metrics=step5_result.obligation_metrics,
        statement_result=step5_result.statement_validation,
        eligibility_result=step5_result.eligibility_result,
        discrepancies=discrepancies,
    )

    # 3. Dynamic Policy Scoring and Routing
    risk_result = calculate_risk_and_routing(
        income_metrics=step5_result.income_metrics,
        obligation_metrics=step5_result.obligation_metrics,
        statement_result=step5_result.statement_validation,
        eligibility_result=step5_result.eligibility_result,
        anomaly_assessment=anomaly_assessment,
        is_llm_fallback=is_fallback,
        step4_result=(step4_result if isinstance(step4_result, dict) else (step4_result.model_dump() if step4_result else None)),
        policy_name=policy_name,
    )

    return Step6Result(
        applicant_id=str(app_id),
        discrepancies=discrepancies,
        anomaly_assessment=anomaly_assessment,
        risk_result=risk_result,
        is_llm_fallback=is_fallback,
    )
