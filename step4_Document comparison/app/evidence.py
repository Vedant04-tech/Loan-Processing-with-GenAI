"""
Evidence collection models and utilities for Document Comparison.
"""
from typing import Any, Literal, Optional
from pydantic import BaseModel


class EvidenceItem(BaseModel):
    source_document: str
    source_path: str
    field: str
    value: Any
    evidence_type: Literal["DECLARED", "VERIFIED", "TRANSACTION", "DERIVED"]
    note: Optional[str] = None
