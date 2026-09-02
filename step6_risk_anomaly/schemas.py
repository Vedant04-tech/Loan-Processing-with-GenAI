from typing import Literal
from pydantic import BaseModel, Field


class ClassifiedAnomaly(BaseModel):
    discrepancy_type: str = Field(description="Discrepancy identifier, e.g. INCOME_MISMATCH")
    severity: Literal["Minor", "Moderate", "Major"] = Field(description="Severity classification")
    reasoning: str = Field(description="Underwriting explanation for assigned severity")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence keys")


class AnomalyAssessment(BaseModel):
    anomalies: list[ClassifiedAnomaly] = Field(description="List of classified anomalies")
    underwriting_summary: str = Field(description="High-level underwriting synthesis")
    suggested_actions: list[str] = Field(default_factory=list, description="Concrete verification steps for reviewer")

