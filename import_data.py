import json
import os
import sys
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.database import Database
from database import get_db


def import_application_json(db: Database, filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    if raw.lstrip().startswith("//"):
        raw = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("//"))

    data = json.loads(raw)
    app_ref = data.get("_id") or data.get("application_ref") or "APP-1001"
    applicant = data.get("applicant", {})
    documents = data.get("documents", [])

    if db.applications.find_one({"application_ref": app_ref}):
        print(f"[SKIP] {app_ref} already exists.")
        return {"app_ref": app_ref, "skipped": True}

    now = datetime.now(timezone.utc)
    embedded_docs = []
    extracted_fields = []
    txn_docs = []

    for doc in documents:
        doc_id = ObjectId()
        doc_type = doc.get("doc_type", "OTHER")
        ext = doc.get("extracted", {})

        embedded_docs.append({
            "_id": doc_id,
            "original_filename": f"{doc_type.lower()}_{app_ref.lower()}.pdf",
            "stored_path": f"/uploads/{app_ref}/{doc_type.lower()}.pdf",
            "file_type": "pdf",
            "doc_type": doc_type,
            "trust_tier": 1,
            "trust_tier_reason": "Verified digital document",
            "processing_status": "done",
            "extracted": ext,
        })

        # Parse extracted fields
        for k, v in ext.items():
            if isinstance(v, (str, int, float)) and k != "transactions":
                extracted_fields.append({
                    "application_ref": app_ref,
                    "doc_type": doc_type,
                    "field_name": k,
                    "field_value": str(v),
                    "numeric_value": float(v) if isinstance(v, (int, float)) else None,
                    "source_type": "verified",
                    "evidence": {"page_number": 1, "quote_verified": True, "confidence": 0.95},
                    "created_at": now,
                })

        # Parse bank transactions
        for tx in ext.get("transactions", []):
            amt = float(tx.get("amount", 0.0))
            txn_docs.append({
                "application_ref": app_ref,
                "txn_date": tx.get("date"),
                "description": tx.get("narration", ""),
                "amount": abs(amt),
                "txn_type": "credit" if amt >= 0 else "debit",
                "category": tx.get("category", "other"),
                "is_salary_match": tx.get("category") == "salary_credit",
                "created_at": now,
            })

    # Master document
    loan_app = next((d.get("extracted", {}) for d in documents if d.get("doc_type") == "LOAN_APPLICATION"), {})
    payslip = next((d.get("extracted", {}) for d in documents if d.get("doc_type") == "PAYSLIP"), {})

    net_pay = float(payslip.get("net_pay") or loan_app.get("net_monthly") or 100000.0)

    application = {
        "application_ref": app_ref,
        "loan_type": "personal_loan",
        "status": "pending",
        "routing": {"color": None, "reason": None},
        "risk": {},
        "financials": {
            "verified_monthly_income": net_pay,
            "total_existing_emis": 15000.0,
            "proposed_emi": 10000.0,
            "foir_percentage": 25.0,
            "loan_request": loan_app,
        },
        "applicants": [{
            "role": "primary",
            "full_name": applicant.get("full_name"),
            "pan_number": applicant.get("pan_number"),
            "aadhaar_last4": applicant.get("aadhaar_last4"),
            "employer_name": payslip.get("employer_name") or "Tech Corp Ltd",
            "employment_type": "salaried",
        }],
        "documents": embedded_docs,
        "cross_checks": [],
        "entity_graph": [],
        "created_at": now,
        "updated_at": now,
    }

    db.applications.insert_one(application)
    if extracted_fields:
        db.extracted_fields.insert_many(extracted_fields)
    if txn_docs:
        db.bank_transactions.insert_many(txn_docs)

    return {"app_ref": app_ref, "applicant": applicant.get("full_name")}


def seed_demo_applications(db: Database):
    print("Loading sample applications...")
    demo_data = [
        {
            "_id": "APP-1001",
            "applicant": {"full_name": "Rahul Sharma", "pan_number": "ABCPS1234F", "dob": "1990-05-15", "aadhaar_last4": "4418"},
            "documents": [
                {"doc_type": "PAYSLIP", "extracted": {"employer_name": "Tech Corp Ltd", "net_pay": 105000, "gross_earnings": 120000}},
                {"doc_type": "PAN_CARD", "extracted": {"name": "Rahul Sharma", "pan_number": "ABCPS1234F"}},
                {"doc_type": "BANK_STATEMENT", "extracted": {
                    "opening_balance": 25000, "closing_balance": 95000, "total_credits": 105000, "total_debits": 35000,
                    "transactions": [
                        {"date": "2026-06-30", "narration": "ACH CR-TECH CORP-SALARY", "amount": 105000, "category": "salary_credit"},
                        {"date": "2026-06-05", "narration": "NACH DR-CAR LOAN EMI", "amount": -15000, "category": "emi_debit"},
                        {"date": "2026-06-10", "narration": "UPI-RENT PAYMENT", "amount": -20000, "category": "rent_debit"},
                    ]
                }},
                {"doc_type": "LOAN_APPLICATION", "extracted": {
                    "net_monthly": 105000, "gross_monthly": 120000, "loan_amount_requested": 500000, "tenure_months": 36,
                    "liabilities": [{"lender": "HDFC Bank", "loan_type": "Car Loan", "emi_amount": 15000}]
                }}
            ]
        },
        {
            "_id": "APP-1002",
            "applicant": {"full_name": "Priya Patel", "pan_number": "XYZPP5678K", "dob": "1993-11-20", "aadhaar_last4": "5694"},
            "documents": [
                {"doc_type": "PAYSLIP", "extracted": {"employer_name": "Global Analytics", "net_pay": 135000, "gross_earnings": 150000}},
                {"doc_type": "PAN_CARD", "extracted": {"name": "Priya Patel", "pan_number": "XYZPP5678K"}},
                {"doc_type": "BANK_STATEMENT", "extracted": {
                    "opening_balance": 40000, "closing_balance": 145000, "total_credits": 135000, "total_debits": 30000,
                    "transactions": [
                        {"date": "2026-06-30", "narration": "ACH CR-SALARY", "amount": 135000, "category": "salary_credit"},
                        {"date": "2026-06-10", "narration": "NACH DR-EMI", "amount": -20000, "category": "emi_debit"},
                    ]
                }},
                {"doc_type": "LOAN_APPLICATION", "extracted": {
                    "net_monthly": 135000, "gross_monthly": 150000, "loan_amount_requested": 800000, "tenure_months": 48,
                    "liabilities": [{"lender": "ICICI Bank", "loan_type": "Personal Loan", "emi_amount": 20000}]
                }}
            ]
        }
    ]

    for app in demo_data:
        if db.applications.find_one({"application_ref": app["_id"]}):
            print(f"[SKIP] {app['_id']} already loaded.")
            continue
        tmp = f"_tmp_{app['_id']}.json"
        with open(tmp, "w") as f:
            json.dump(app, f)
        res = import_application_json(db, tmp)
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"[OK] {res['app_ref']} ({res.get('applicant')}) loaded.")


if __name__ == "__main__":
    db = get_db()
    if len(sys.argv) > 1:
        import_application_json(db, sys.argv[1])
    else:
        seed_demo_applications(db)
