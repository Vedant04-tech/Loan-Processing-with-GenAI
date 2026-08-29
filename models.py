from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
#  Sub-models (Embedded inside applications document)
# ─────────────────────────────────────────────────────────────

class Applicant(BaseModel):
    role: str = "primary"                           # primary / co_applicant
    full_name: Optional[str] = None
    pan_number: Optional[str] = None
    aadhaar_last4: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    employer_name: Optional[str] = None
    designation: Optional[str] = None
    employment_type: str = "salaried"


class DocumentMetadata(BaseModel):
    original_filename: str
    doc_type: str                                   # PAYSLIP, BANK_STATEMENT, FORM16, etc.
    doc_month: Optional[str] = None
    trust_tier: int = 1                             # 0: Signed, 1: Digital, 2: Scanned, 3: Photo
    trust_tier_reason: Optional[str] = None
    processing_status: str = "done"
    extracted: Optional[dict[str, Any]] = None      # Raw pipeline output


class CrossCheck(BaseModel):
    check_type: str                                 # e.g., income_payslip_vs_bank
    declared_value: Optional[str] = None
    verified_value: Optional[str] = None
    match_result: str                               # match / partial_match / mismatch
    discrepancy_amount: Optional[float] = None
    severity: str = "minor"                         # minor / moderate / major
    explanation: Optional[str] = None


class EntityRelationship(BaseModel):
    source: dict[str, str]                          # {"type": "applicant", "label": "Rahul"}
    relationship: str                               # works_at, has_account, has_liability
    target: dict[str, str]                          # {"type": "employer", "label": "ABC Ltd"}
    properties: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
#  Top-Level Collection Models (5 Collections Total)
# ─────────────────────────────────────────────────────────────

# 1. Master Applications Collection
class Application(BaseModel):
    application_ref: str                            # e.g., APP-1001 or P002
    loan_type: str = "personal_loan"
    status: str = "pending"                         # pending, review, approved, rejected
    
    # Step 8: Routing Decision
    routing: dict[str, Any] = Field(default_factory=lambda: {"color": None, "reason": None})
    
    # Step 5.5: Risk Score & Grades
    risk: dict[str, Any] = Field(default_factory=dict)
    
    # Step 5.1 - 5.4: Income, EMIs & FOIR
    financials: dict[str, Any] = Field(default_factory=dict)
    
    # Embedded data (1:few relationships)
    applicants: list[Applicant] = Field(default_factory=list)
    documents: list[DocumentMetadata] = Field(default_factory=list)
    cross_checks: list[CrossCheck] = Field(default_factory=list)
    entity_graph: list[EntityRelationship] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# 2. Extracted Fields with Evidence (Traceability USP)
class ExtractedField(BaseModel):
    application_ref: str
    doc_type: str
    field_name: str
    field_value: str
    numeric_value: Optional[float] = None
    source_type: str = "verified"                  # declared / verified
    evidence: dict[str, Any] = Field(default_factory=lambda: {
        "page_number": 1,
        "bounding_box": None,                       # {"x": 340, "y": 210, "w": 100, "h": 20}
        "quoted_text": None,
        "quote_verified": True,
        "confidence": 0.95
    })
    created_at: datetime = Field(default_factory=datetime.utcnow)


# 3. Bank Statement Transactions
class BankTransaction(BaseModel):
    application_ref: str
    txn_date: Optional[str] = None
    description: str
    amount: float
    txn_type: str                                  # credit / debit
    category: str = "other"                        # salary_credit, emi_debit, upi_spend, etc.
    is_salary_match: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# 4. Immutable Audit Logs
class AuditLog(BaseModel):
    application_ref: str
    actor: str                                     # pipeline:step_7, system, officer
    action: str                                    # e.g., cross_check_completed
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# 5. Policy Embeddings (RAG)
class PolicyEmbedding(BaseModel):
    policy_name: str
    loan_type: str = "personal_loan"
    chunk_index: int
    chunk_text: str
    embedding: Optional[list[float]] = None        # 1024-dim float array
    section_title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
