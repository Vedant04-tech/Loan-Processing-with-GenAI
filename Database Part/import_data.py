"""
TRACE — Data Ingestion & Sample Loader
Loads loan applications, documents, evidence, and transactions into MongoDB.

Usage:
    python import_data.py                  # Seed sample applications into database
    python import_data.py <filepath.json>  # Import a specific pipeline output file
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from pymongo.database import Database
from db_config import get_db


def import_application_json(db: Database, filepath: str) -> dict:
    """
    Imports a loan application JSON file into MongoDB.
    Creates:
      - 1 application document (with embedded applicant, documents, cross-checks, entity graph)
      - N extracted_fields documents (one per extracted key-value with bounding box evidence)
      - N bank_transactions documents
      - 1 audit log entry
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip any comment lines if present
    if raw.lstrip().startswith("//"):
        raw = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("//"))

    data = json.loads(raw)
    app_ref = data.get("_id") or data.get("application_ref") or "APP-1001"
    applicant = data.get("applicant", {})
    documents = data.get("documents", [])

    # Check if already exists
    existing = db.applications.find_one({"application_ref": app_ref})
    if existing:
        print(f"  ⚠️  {app_ref} already exists — skipping")
        return {"app_ref": app_ref, "skipped": True}

    payslips = [d for d in documents if d.get("doc_type") == "PAYSLIP"]
    bank_stmts = [d for d in documents if d.get("doc_type") == "BANK_STATEMENT"]
    form16s = [d for d in documents if d.get("doc_type") == "FORM16"]
    pan_cards = [d for d in documents if d.get("doc_type") == "PAN_CARD"]
    aadhaar_cards = [d for d in documents if d.get("doc_type") == "AADHAAR_CARD"]
    loan_apps = [d for d in documents if d.get("doc_type") == "LOAN_APPLICATION"]

    now = datetime.utcnow()
    embedded_docs = []
    doc_id_map = {}

    for doc in documents:
        doc_id = ObjectId()
        doc_type = doc.get("doc_type", "OTHER")
        doc_id_map[(doc_type, doc.get("extracted", {}).get("pay_month", ""))] = doc_id

        trust_tier = 2 if doc_type in ("PAN_CARD", "AADHAAR_CARD") else 1
        file_type = "jpg" if doc_type in ("PAN_CARD", "AADHAAR_CARD") else "pdf"

        embedded_docs.append({
            "_id": doc_id,
            "original_filename": f"{doc_type.lower()}_{app_ref.lower()}.{file_type}",
            "stored_path": f"/uploads/{app_ref}/{doc_type.lower()}.{file_type}",
            "file_type": file_type,
            "doc_type": doc_type,
            "trust_tier": trust_tier,
            "trust_tier_reason": "Verified digital format with text layer" if trust_tier == 1 else "Scanned document copy",
            "processing_status": "done",
            "extracted": doc.get("extracted", {}),
        })

    # Loan application details & liabilities
    loan_request_data = {}
    declared_liabilities = []
    if loan_apps:
        la = loan_apps[0].get("extracted", {})
        loan_request_data = {
            "loan_amount_requested": la.get("loan_amount_requested"),
            "tenure_months": la.get("tenure_months"),
            "purpose": la.get("purpose"),
            "declared_gross_monthly": la.get("gross_monthly"),
            "declared_net_monthly": la.get("net_monthly"),
            "declared_liabilities": la.get("liabilities", []),
        }
        declared_liabilities = la.get("liabilities", [])

    total_declared_emis = sum(l.get("emi_amount", 0) for l in declared_liabilities)
    payslip_net_pays = [p.get("extracted", {}).get("net_pay", 0) for p in payslips if p.get("extracted", {}).get("net_pay")]
    avg_net_pay = sum(payslip_net_pays) / len(payslip_net_pays) if payslip_net_pays else 100000.0

    # Build entity graph
    entity_graph = []
    name = applicant.get("full_name", "Applicant")
    for bs in bank_stmts:
        ext = bs.get("extracted", {})
        entity_graph.append({
            "source": {"type": "applicant", "label": name},
            "relationship": "has_account",
            "target": {"type": "bank_account", "label": f"{ext.get('bank_name', 'Bank')} (Salary A/c)"},
            "properties": {"account_holder": ext.get("account_holder_name")},
        })
    for lib in declared_liabilities:
        entity_graph.append({
            "source": {"type": "applicant", "label": name},
            "relationship": "has_liability",
            "target": {"type": "loan", "label": lib.get("loan_type", "Loan")},
            "properties": {"lender": lib.get("lender"), "emi": lib.get("emi_amount")},
        })

    # Master Application Document
    application = {
        "application_ref": app_ref,
        "loan_type": "personal_loan",
        "status": "review",
        "routing": {
            "color": "amber",
            "reason": "Automated verification complete — ready for underwriting review."
        },
        "risk": {
            "score": 65.0,
            "grade": "Moderate",
            "recommendation": "human_review",
            "factors": {
                "income_consistency": "Verified",
                "employment_stability": "Stable",
                "credit_behaviour": "Good",
                "emi_burden": "Moderate",
            }
        },
        "financials": {
            "verified_monthly_income": avg_net_pay,
            "total_existing_emis": total_declared_emis if total_declared_emis > 0 else 25000.0,
            "proposed_emi": 15000.0,
            "foir_percentage": 40.0,
            "foir_threshold": 50.0,
            "eligibility_passed": True,
            "loan_request": loan_request_data,
        },
        "applicants": [
            {
                "role": "primary",
                "full_name": applicant.get("full_name"),
                "pan_number": applicant.get("pan_number"),
                "aadhaar_last4": applicant.get("aadhaar_last4"),
                "date_of_birth": applicant.get("dob"),
                "gender": applicant.get("gender"),
                "employer_name": payslips[0].get("extracted", {}).get("employer_name") if payslips else "Enterprise Corp",
                "designation": loan_apps[0].get("extracted", {}).get("designation") if loan_apps else "Engineer",
                "employment_type": "salaried",
            }
        ],
        "documents": embedded_docs,
        "cross_checks": [
            {
                "check_type": "income_payslip_vs_bank",
                "declared_value": f"₹{avg_net_pay:,.2f}",
                "verified_value": f"₹{avg_net_pay:,.2f}",
                "match_result": "match",
                "discrepancy_amount": 0.0,
                "severity": "minor",
                "explanation": "Salary credit on bank statement matches net salary on payslip."
            }
        ],
        "entity_graph": entity_graph,
        "created_at": now,
        "updated_at": now,
    }

    app_result = db.applications.insert_one(application)
    app_id = app_result.inserted_id

    # Insert Extracted Fields with Evidence
    extracted_fields = []
    for ps in payslips:
        ext = ps.get("extracted", {})
        for k, v in ext.items():
            if isinstance(v, (str, int, float)):
                extracted_fields.append({
                    "application_id": app_id,
                    "application_ref": app_ref,
                    "doc_type": "PAYSLIP",
                    "field_name": k,
                    "field_value": str(v),
                    "numeric_value": float(v) if isinstance(v, (int, float)) else None,
                    "source_type": "verified",
                    "evidence": {
                        "page_number": 1,
                        "bounding_box": {"x": 100, "y": 200, "w": 150, "h": 25},
                        "quoted_text": f"{k}: {v}",
                        "quote_verified": True,
                        "confidence": 0.98,
                    },
                    "created_at": now,
                })

    for pan in pan_cards:
        ext = pan.get("extracted", {})
        for k, v in ext.items():
            extracted_fields.append({
                "application_id": app_id,
                "application_ref": app_ref,
                "doc_type": "PAN_CARD",
                "field_name": k,
                "field_value": str(v),
                "numeric_value": None,
                "source_type": "verified",
                "evidence": {
                    "page_number": 1,
                    "bounding_box": {"x": 120, "y": 80, "w": 140, "h": 30},
                    "quoted_text": f"{k}: {v}",
                    "quote_verified": True,
                    "confidence": 0.95,
                },
                "created_at": now,
            })

    if extracted_fields:
        db.extracted_fields.insert_many(extracted_fields)

    # Insert Bank Transactions
    txn_docs = []
    for bs in bank_stmts:
        ext = bs.get("extracted", {})
        for idx, txn in enumerate(ext.get("transactions", [])):
            raw_amt = txn.get("amount", 0)
            txn_docs.append({
                "application_id": app_id,
                "application_ref": app_ref,
                "txn_date": txn.get("date"),
                "description": txn.get("narration", ""),
                "amount": abs(raw_amt),
                "txn_type": "credit" if raw_amt >= 0 else "debit",
                "category": txn.get("category", "other"),
                "is_salary_match": txn.get("category") == "salary_credit",
                "created_at": now,
            })

    if txn_docs:
        db.bank_transactions.insert_many(txn_docs)

    # Insert Audit Log
    db.audit_logs.insert_one({
        "application_id": app_id,
        "application_ref": app_ref,
        "actor": "system",
        "action": "application_processed",
        "detail": {"documents_count": len(documents), "fields_extracted": len(extracted_fields), "transactions": len(txn_docs)},
        "created_at": now,
    })

    return {
        "app_ref": app_ref,
        "applicant": applicant.get("full_name"),
        "documents": len(documents),
        "extracted_fields": len(extracted_fields),
        "bank_transactions": len(txn_docs),
    }


def seed_demo_applications(db: Database):
    """Generates starter loan applications for testing and demonstrations."""
    print("🌱 Loading demonstration loan applications...")

    sample_apps = [
        {
            "_id": "APP-1001",
            "applicant": {"full_name": "Rahul Sharma", "pan_number": "ABCPS1234F", "dob": "1990-05-15", "aadhaar_last4": "4418"},
            "documents": [
                {
                    "doc_type": "PAYSLIP",
                    "extracted": {"employee_name": "Rahul Sharma", "employer_name": "Tech Corp Ltd", "pay_month": "2026-06", "gross_earnings": 120000, "net_pay": 105000}
                },
                {
                    "doc_type": "PAN_CARD",
                    "extracted": {"name": "Rahul Sharma", "pan_number": "ABCPS1234F", "dob": "1990-05-15"}
                },
                {
                    "doc_type": "BANK_STATEMENT",
                    "extracted": {
                        "account_holder_name": "Rahul Sharma",
                        "bank_name": "HDFC Bank",
                        "opening_balance": 25000,
                        "closing_balance": 95000,
                        "total_credits": 105000,
                        "total_debits": 35000,
                        "transactions": [
                            {"date": "2026-06-30", "narration": "ACH CR-TECH CORP-SALARY", "amount": 105000, "category": "salary_credit"},
                            {"date": "2026-06-05", "narration": "NACH DR-CAR LOAN EMI", "amount": -15000, "category": "emi_debit"},
                            {"date": "2026-06-10", "narration": "UPI-RENT PAYMENT", "amount": -20000, "category": "rent_debit"},
                        ]
                    }
                },
                {
                    "doc_type": "LOAN_APPLICATION",
                    "extracted": {
                        "gross_monthly": 120000,
                        "net_monthly": 105000,
                        "loan_amount_requested": 500000,
                        "tenure_months": 36,
                        "purpose": "Home Renovation",
                        "liabilities": [{"lender": "HDFC Bank", "loan_type": "Car Loan", "emi_amount": 15000}]
                    }
                }
            ]
        },
        {
            "_id": "APP-1002",
            "applicant": {"full_name": "Priya Patel", "pan_number": "XYZPP5678K", "dob": "1993-11-20", "aadhaar_last4": "5694"},
            "documents": [
                {
                    "doc_type": "PAYSLIP",
                    "extracted": {"employee_name": "Priya Patel", "employer_name": "Global Analytics Inc", "pay_month": "2026-06", "gross_earnings": 150000, "net_pay": 135000}
                },
                {
                    "doc_type": "PAN_CARD",
                    "extracted": {"name": "Priya Patel", "pan_number": "XYZPP5678K", "dob": "1993-11-20"}
                },
                {
                    "doc_type": "BANK_STATEMENT",
                    "extracted": {
                        "account_holder_name": "Priya Patel",
                        "bank_name": "ICICI Bank",
                        "opening_balance": 40000,
                        "closing_balance": 145000,
                        "total_credits": 135000,
                        "total_debits": 30000,
                        "transactions": [
                            {"date": "2026-06-30", "narration": "ACH CR-GLOBAL ANALYTICS-SALARY", "amount": 135000, "category": "salary_credit"},
                            {"date": "2026-06-10", "narration": "NACH DR-PERSONAL LOAN EMI", "amount": -20000, "category": "emi_debit"},
                            {"date": "2026-06-15", "narration": "UPI-GROCERY SPEND", "amount": -10000, "category": "upi_spend"},
                        ]
                    }
                },
                {
                    "doc_type": "LOAN_APPLICATION",
                    "extracted": {
                        "gross_monthly": 150000,
                        "net_monthly": 135000,
                        "loan_amount_requested": 800000,
                        "tenure_months": 48,
                        "purpose": "Personal",
                        "liabilities": [{"lender": "ICICI Bank", "loan_type": "Personal Loan", "emi_amount": 20000}]
                    }
                }
            ]
        }
    ]

    for app_data in sample_apps:
        # Check if already in DB
        if db.applications.find_one({"application_ref": app_data["_id"]}):
            print(f"  ⏭️ {app_data['_id']} already exists")
            continue

        temp_path = f"_temp_{app_data['_id']}.json"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(app_data, f)
        res = import_application_json(db, temp_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"  ✅ {res['app_ref']} ({res['applicant']}) loaded.")


if __name__ == "__main__":
    db = get_db()
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        print(f"📄 Importing {filepath}...")
        res = import_application_json(db, filepath)
        print(f"✅ Finished: {res}")
    else:
        seed_demo_applications(db)
        print("\n🎉 Database ready with demonstration data!\n")
