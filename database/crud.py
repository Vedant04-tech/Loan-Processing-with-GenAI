from datetime import datetime
from typing import Any, Optional
from pymongo.database import Database


def get_application(db: Database, application_ref: str) -> dict | None:
    """Fetches the complete application document from MongoDB."""
    return db.applications.find_one({"application_ref": application_ref})


def get_application_summary(db: Database, application_ref: str) -> dict | None:
    """Fetches high-level applicant, risk, and financial summary."""
    doc = db.applications.find_one({"application_ref": application_ref})
    if not doc:
        return None

    primary = (doc.get("applicants") or [{}])[0]
    routing = doc.get("routing") or {}
    risk = doc.get("risk") or {}
    financials = doc.get("financials") or {}
    factors = risk.get("factors") or {}

    return {
        "id": str(doc["_id"]),
        "application_ref": doc.get("application_ref"),
        "loan_type": doc.get("loan_type"),
        "status": doc.get("status"),
        "routing_color": routing.get("color"),
        "routing_reason": routing.get("reason"),
        "risk_score": risk.get("score"),
        "risk_grade": risk.get("grade"),
        "recommendation": risk.get("recommendation"),
        "verified_monthly_income": financials.get("verified_monthly_income"),
        "total_existing_emis": financials.get("total_existing_emis"),
        "proposed_emi": financials.get("proposed_emi"),
        "foir_percentage": financials.get("foir_percentage"),
        "disposable_income": financials.get("disposable_income"),
        "eligibility_passed": financials.get("eligibility_passed"),
        "full_name": primary.get("full_name"),
        "employer_name": primary.get("employer_name"),
        "pan_number": primary.get("pan_number"),
        "income_consistency": factors.get("income_consistency"),
        "employment_stability": factors.get("employment_stability"),
        "credit_behaviour": factors.get("credit_behaviour"),
        "emi_burden": factors.get("emi_burden"),
    }


def update_financials(db: Database, application_ref: str, financials_data: dict):
    """Updates calculated financial metrics in applications.financials."""
    return db.applications.update_one(
        {"application_ref": application_ref},
        {"$set": {"financials": financials_data, "updated_at": datetime.utcnow()}}
    )


def update_step4_comparison(db: Database, application_ref: str, comparison_data: dict):
    """Saves Step 4 comparison results to application document and a separate comparison_results collection."""
    db.applications.update_one(
        {"application_ref": application_ref},
        {"$set": {"step4_comparison": comparison_data, "updated_at": datetime.utcnow()}}
    )
    return db.comparison_results.update_one(
        {"application_ref": application_ref},
        {"$set": {**comparison_data, "updated_at": datetime.utcnow()}},
        upsert=True
    )


def get_step4_comparison(db: Database, application_ref: str) -> dict | None:
    """Fetches Step 4 comparison results for the given application."""
    doc = db.applications.find_one({"application_ref": application_ref}, {"step4_comparison": 1})
    return doc.get("step4_comparison") if doc else None


def update_routing(db: Database, application_ref: str, color: str, reason: str):
    """Updates final routing outcome (green / amber / red)."""
    status = "approved" if color == "green" else ("review" if color == "amber" else "rejected")
    return db.applications.update_one(
        {"application_ref": application_ref},
        {"$set": {"routing.color": color, "routing.reason": reason, "status": status, "updated_at": datetime.utcnow()}}
    )


def update_risk(db: Database, application_ref: str, score: float, grade: str, recommendation: str, factors: dict):
    """Saves calculated risk score and factor ratings."""
    return db.applications.update_one(
        {"application_ref": application_ref},
        {"$set": {"risk": {"score": score, "grade": grade, "recommendation": recommendation, "factors": factors}, "updated_at": datetime.utcnow()}}
    )


def insert_extracted_fields(db: Database, fields: list[dict]):
    if fields:
        return db.extracted_fields.insert_many(fields)


def get_extracted_evidence(db: Database, application_ref: str) -> list[dict]:
    """Fetches extracted fields with bounding box evidence."""
    cursor = db.extracted_fields.find({"application_ref": application_ref}).sort("created_at", 1)
    results = []
    for f in cursor:
        evidence = f.get("evidence") or {}
        results.append({
            "field_name": f.get("field_name"),
            "field_value": f.get("field_value"),
            "numeric_value": f.get("numeric_value"),
            "source_type": f.get("source_type"),
            "doc_type": f.get("doc_type"),
            "page_number": evidence.get("page_number"),
            "bounding_box": evidence.get("bounding_box"),
            "quoted_text": evidence.get("quoted_text"),
            "quote_verified": evidence.get("quote_verified", False),
            "confidence": evidence.get("confidence"),
        })
    return results


def insert_bank_transactions(db: Database, txns: list[dict]):
    if txns:
        return db.bank_transactions.insert_many(txns)


def get_bank_transactions(db: Database, application_ref: str, category: str | None = None) -> list[dict]:
    query: dict[str, Any] = {"application_ref": application_ref}
    if category:
        query["category"] = category
    cursor = db.bank_transactions.find(query).sort("txn_date", 1)
    return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]


def get_spending_summary(db: Database, application_ref: str) -> dict:
    pipeline = [
        {"$match": {"application_ref": application_ref, "txn_type": "debit"}},
        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}}
    ]
    return {doc["_id"]: {"total": doc["total"], "count": doc["count"]} for doc in db.bank_transactions.aggregate(pipeline)}


def get_bank_statement_summary(db: Database, application_ref: str) -> dict:
    fields = db.extracted_fields.find({
        "application_ref": application_ref,
        "doc_type": "BANK_STATEMENT",
        "field_name": {"$in": ["opening_balance", "closing_balance", "total_credits", "total_debits", "bank_name"]}
    })
    return {f["field_name"]: f.get("numeric_value") or f.get("field_value") for f in fields}


def add_cross_check(db: Database, application_ref: str, check_data: dict):
    return db.applications.update_one(
        {"application_ref": application_ref},
        {"$push": {"cross_checks": check_data}, "$set": {"updated_at": datetime.utcnow()}}
    )


def clear_cross_checks(db: Database, application_ref: str):
    """Clears cross checks before a fresh pipeline evaluation run."""
    return db.applications.update_one(
        {"application_ref": application_ref},
        {"$set": {"cross_checks": [], "updated_at": datetime.utcnow()}}
    )


def get_cross_check_results(db: Database, application_ref: str) -> list[dict]:
    doc = db.applications.find_one({"application_ref": application_ref}, {"cross_checks": 1})
    return (doc.get("cross_checks") or []) if doc else []


def get_entity_graph(db: Database, application_ref: str) -> list[dict]:
    doc = db.applications.find_one({"application_ref": application_ref}, {"entity_graph": 1})
    if not doc:
        return []
    return [
        {
            "source_type": e.get("source", {}).get("type"),
            "source_label": e.get("source", {}).get("label"),
            "relationship": e.get("relationship"),
            "target_type": e.get("target", {}).get("type"),
            "target_label": e.get("target", {}).get("label"),
            "properties": e.get("properties", {}),
        }
        for e in doc.get("entity_graph", [])
    ]


def log_audit_event(db: Database, application_ref: str, actor: str, action: str, detail: dict | None = None):
    return db.audit_logs.insert_one({
        "application_ref": application_ref,
        "actor": actor,
        "action": action,
        "detail": detail or {},
        "created_at": datetime.utcnow(),
    })


def get_audit_trail(db: Database, application_ref: str) -> list[dict]:
    cursor = db.audit_logs.find({"application_ref": application_ref}).sort("created_at", 1)
    return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]


def insert_policy_embeddings_bulk(db: Database, embeddings: list[dict]):
    if embeddings:
        return db.policy_embeddings.insert_many(embeddings)


def search_policy_chunks(db: Database, loan_type: str | None = None, text_search: str | None = None, limit: int = 10) -> list[dict]:
    query: dict[str, Any] = {}
    if loan_type:
        query["loan_type"] = loan_type
    if text_search:
        query["chunk_text"] = {"$regex": text_search, "$options": "i"}
    cursor = db.policy_embeddings.find(query).limit(limit)
    return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
