from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field


class Discrepancy(BaseModel):
    discrepancy_type: str
    declared_value: Optional[str] = None
    verified_value: Optional[str] = None
    difference_amount: Optional[float] = None
    difference_percent: Optional[float] = None
    evidence_summary: str


class ClassifiedAnomaly(BaseModel):
    discrepancy_type: str = Field(description="Discrepancy identifier, e.g. INCOME_MISMATCH")
    severity: Literal["Minor", "Moderate", "Major"] = Field(description="Severity classification")
    reasoning: str = Field(description="Underwriting explanation for assigned severity")
    evidence_ids: List[str] = Field(default_factory=list, description="Referenced evidence keys")


class AnomalyAssessment(BaseModel):
    anomalies: List[ClassifiedAnomaly] = Field(default_factory=list, description="List of classified anomalies")
    underwriting_summary: str = Field(default="Automated underwriting assessment completed.", description="High-level underwriting synthesis")
    suggested_actions: List[str] = Field(default_factory=list, description="Concrete verification steps for reviewer")


class RiskResult(BaseModel):
    score: float
    grade: str
    routing_color: str
    recommendation: str  # "recommend_approve" | "recommend_review" | "recommend_reject"
    routing_reason: str
    requires_human_signoff: bool = True  # Every outcome strictly requires human underwriter sign-off
    factor_breakdown: dict[str, Any]
    reviewer_checklist: List[str] = Field(default_factory=list)
    counterfactual_note: Optional[str] = None


class Step6Result(BaseModel):
    applicant_id: str
    discrepancies: List[Discrepancy]
    anomaly_assessment: AnomalyAssessment
    risk_result: RiskResult
    is_llm_fallback: bool
