import importlib
import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from database.db_config import get_db
from database import crud
from step5_calculation.app import (
    build_step5_result,
    Step5Result,
    IncomeMetrics,
    ObligationMetrics,
    StatementValidationResult,
    EligibilityResult,
)
from step6_risk_anomaly.app import (
    build_step6_result,
    Step6Result,
    Discrepancy,
    AnomalyAssessment,
    RiskResult,
)

# Dynamically import Step 4 pipeline
_step4_pipeline = importlib.import_module("step4_Document comparison.app.pipeline")
build_step4_result = getattr(_step4_pipeline, "build_pipeline_result")


class PipelineResult(BaseModel):
    application_ref: str
    status: str
    routing_color: str
    recommendation: str
    requires_human_signoff: bool = True
    risk_score: float
    risk_grade: str
    routing_reason: str
    factor_breakdown: dict[str, Any]
    reviewer_checklist: List[str] = Field(default_factory=list)
    counterfactual_note: Optional[str] = None
    income_metrics: IncomeMetrics
    obligation_metrics: ObligationMetrics
    statement_validation: StatementValidationResult
    eligibility_result: EligibilityResult
    discrepancies: List[Discrepancy]
    is_llm_fallback: bool
    underwriting_summary: str


def run_pipeline(
    application_ref: str,
    policy_name: str = "personal_loan",
    db: Any = None,
) -> PipelineResult:
    """
    TRACE Unified Orchestration Pipeline:
    Coordinates Step 4 (Document Cross-Comparison) ->
                Step 5 (Financial Math & Eligibility) ->
                Step 6 (Risk Scoring, Checklist & Routing) ->
                MongoDB Atlas Writeback & Audit Logging
    """
    if db is None:
        try:
            db = get_db()
        except Exception:
            db = None

    application = None
    if db is not None:
        application = crud.get_application(db, application_ref)

    if not application:
        # Fallback to local test json files
        local_path = os.path.join("step4_Document comparison", "extracted_data", f"{application_ref}.json")
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                import json
                raw = f.read().strip()
                if raw.startswith("//"):
                    raw = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("//"))
                application = json.loads(raw)
        else:
            raise ValueError(f"Application reference '{application_ref}' not found in database or local test data.")

    # -------------------------------------------------------------
    # 1. Step 4: Cross-Document Comparison Engine
    # -------------------------------------------------------------
    step4_result = build_step4_result(application)

    if db is not None:
        try:
            crud.update_step4_comparison(
                db,
                application_ref=application_ref,
                comparison_data=step4_result.model_dump(),
            )
        except Exception as e:
            print(f"[WARN] Failed to write Step 4 results to database: {e}")


    # -------------------------------------------------------------
    # 2. Step 5: Deterministic Financial & Eligibility Engine
    # -------------------------------------------------------------
    bank_txns = None
    if db is not None:
        try:
            bank_txns = crud.get_bank_transactions(db, application_ref)
        except Exception:
            pass

    step5_result: Step5Result = build_step5_result(
        application_data=application,
        bank_transactions=bank_txns,
        policy_name=policy_name,
    )

    inc = step5_result.income_metrics
    ob = step5_result.obligation_metrics
    stmt = step5_result.statement_validation
    elig = step5_result.eligibility_result

    # -------------------------------------------------------------
    # 3. Step 6: Risk Scoring, Anomaly Classification & Routing
    # -------------------------------------------------------------
    evidence = None
    if db is not None:
        try:
            evidence = crud.get_extracted_evidence(db, application_ref)
        except Exception:
            pass

    step6_result: Step6Result = build_step6_result(
        application_data=application,
        step5_result=step5_result,
        step4_result=step4_result,
        extracted_fields=evidence,
        policy_name=policy_name,
    )

    risk = step6_result.risk_result
    discrepancies = step6_result.discrepancies
    anomaly_assessment = step6_result.anomaly_assessment
    is_fallback = step6_result.is_llm_fallback

    # -------------------------------------------------------------
    # 4. MongoDB Atlas Writeback & Audit Logging
    # -------------------------------------------------------------
    step5_data = step5_result.model_dump()
    step6_data = step6_result.model_dump()
    step4_data = step4_result.model_dump()

    status_map = {"green": "approved", "amber": "review", "red": "rejected"}
    pipeline_res = PipelineResult(
        application_ref=application_ref,
        status=status_map.get(risk.routing_color, "review"),
        routing_color=risk.routing_color,
        recommendation=risk.recommendation,
        requires_human_signoff=risk.requires_human_signoff,
        risk_score=risk.score,
        risk_grade=risk.grade,
        routing_reason=risk.routing_reason,
        factor_breakdown=risk.factor_breakdown,
        reviewer_checklist=risk.reviewer_checklist,
        counterfactual_note=risk.counterfactual_note,
        income_metrics=inc,
        obligation_metrics=ob,
        statement_validation=stmt,
        eligibility_result=elig,
        discrepancies=discrepancies,
        is_llm_fallback=is_fallback,
        underwriting_summary=anomaly_assessment.underwriting_summary,
    )

    if db is not None:
        try:
            # 4.1 Save Step 5 & 6 Combined Results
            step5_and_6_summary = {
                "verified_monthly_income": inc.verified_monthly_income,
                "total_existing_emis": ob.total_existing_emis,
                "proposed_emi": ob.proposed_emi,
                "foir_percentage": ob.foir_percentage,
                "disposable_income": ob.disposable_income,
                "statement_validation_status": stmt.status,
                "eligibility_passed": elig.passed,
                "eligibility_reasons": elig.reasons,
                "risk_score": risk.score,
                "risk_grade": risk.grade,
                "recommendation": risk.recommendation,
                "routing_color": risk.routing_color,
                "routing_reason": risk.routing_reason,
                "requires_human_signoff": risk.requires_human_signoff,
                "discrepancies_count": len(discrepancies),
                "is_llm_fallback": is_fallback,
            }
            crud.save_step5_and_6_combined(
                db,
                application_ref=application_ref,
                step5_data=step5_data,
                step6_data=step6_data,
                summary_data=step5_and_6_summary,
            )

            # 4.2 Save Full Pipeline Combined Result
            full_pipeline_payload = {
                "application_ref": application_ref,
                "status": pipeline_res.status,
                "routing_color": pipeline_res.routing_color,
                "recommendation": pipeline_res.recommendation,
                "requires_human_signoff": pipeline_res.requires_human_signoff,
                "risk_score": pipeline_res.risk_score,
                "risk_grade": pipeline_res.risk_grade,
                "routing_reason": pipeline_res.routing_reason,
                "factor_breakdown": pipeline_res.factor_breakdown,
                "reviewer_checklist": pipeline_res.reviewer_checklist,
                "counterfactual_note": pipeline_res.counterfactual_note,
                "step4_comparison": step4_data,
                "step5_calculation": step5_data,
                "step6_risk_anomaly": step6_data,
                "pipeline_result": pipeline_res.model_dump(),
                "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            crud.save_full_pipeline_result(
                db,
                application_ref=application_ref,
                pipeline_payload=full_pipeline_payload,
            )

            # 4.3 Update Financials (legacy / UI compatibility)
            fin_payload = {
                "verified_monthly_income": inc.verified_monthly_income,
                "total_existing_emis": ob.total_existing_emis,
                "proposed_emi": ob.proposed_emi,
                "foir_percentage": ob.foir_percentage,
                "foir_threshold": 50.0,
                "disposable_income": ob.disposable_income,
                "eligibility_passed": elig.passed,
                "eligibility_reasons": elig.reasons,
            }
            crud.update_financials(db, application_ref, fin_payload)

            # 4.4 Save Cross-Check records
            db.applications.update_one({"application_ref": application_ref}, {"$set": {"cross_checks": []}})
            for disc in discrepancies:
                sev = "minor"
                for anom in anomaly_assessment.anomalies:
                    if anom.discrepancy_type == disc.discrepancy_type:
                        sev = anom.severity.lower()
                        break

                crud.add_cross_check(
                    db,
                    application_ref=application_ref,
                    check_data={
                        "check_type": disc.discrepancy_type.lower(),
                        "status": "FAIL" if sev == "major" else "REVIEW",
                        "severity": sev,
                        "declared_value": disc.declared_value,
                        "verified_value": disc.verified_value,
                        "variance_amount": disc.difference_amount,
                        "variance_percent": disc.difference_percent,
                        "grounding_evidence": [{"description": disc.evidence_summary}],
                    },
                )

            # 4.5 Update Risk & Factors
            crud.update_risk(
                db,
                application_ref,
                score=risk.score,
                grade=risk.grade,
                recommendation=risk.recommendation,
                factors=risk.factor_breakdown,
                requires_human_signoff=risk.requires_human_signoff,
                reviewer_checklist=risk.reviewer_checklist,
                counterfactual_note=risk.counterfactual_note,
            )

            # 4.6 Update Routing
            crud.update_routing(
                db,
                application_ref,
                color=risk.routing_color,
                reason=risk.routing_reason,
            )

            # 4.7 Audit Log Entry
            now = datetime.now(timezone.utc)
            db.audit_logs.insert_one({
                "application_ref": application_ref,
                "actor": "pipeline:unified_orchestrator",
                "action": f"routed_{risk.routing_color}",
                "timestamp": now,
                "details": {
                    "score": risk.score,
                    "grade": risk.grade,
                    "recommendation": risk.recommendation,
                    "requires_human_signoff": risk.requires_human_signoff,
                    "routing_color": risk.routing_color,
                    "anomalies_count": len(discrepancies),
                    "is_llm_fallback": is_fallback,
                },
            })

        except Exception as e:
            print(f"[WARN] Database writeback encountered an error: {e}")

    return pipeline_res


# Backward-compatible alias
run_decision_pipeline = run_pipeline

__all__ = [
    "run_pipeline",
    "run_decision_pipeline",
    "PipelineResult",
]

