# 🗄️ TRACE — MongoDB Data Layer

A clean, document-oriented data storage layer for the **TRACE GenAI Loan Document Processing** platform, connected to **MongoDB Atlas**.

---

## 📁 5 Core Files

```
├── db_config.py      # Atlas connection & database client (20 lines)
├── models.py         # Data schemas for all 5 collections
├── crud.py           # Core read/write helper functions for the pipeline & frontend
├── import_data.py    # Loads sample loan applications into MongoDB Atlas
└── test_db.py        # 1-command verification script
```

---

## 🗃️ 5 MongoDB Collections

1. **`applications`** (Master document): Stores applicant profiles, uploaded documents metadata, financial metrics, risk scores, cross-check comparisons, and entity relationship graph.
2. **`extracted_fields`** (Traceability USP): Stores each extracted value with its **page number, quoted text, and bounding box coordinates** for click-to-source proof.
3. **`bank_transactions`**: Categorized statement rows (`salary_credit`, `emi_debit`, `upi_spend`, `rent_debit`, etc.).
4. **`audit_logs`**: Immutable, append-only history of pipeline events.
5. **`policy_embeddings`**: Text chunks of lender underwriting guidelines for RAG.

---

## 🚀 How to Run & Verify

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Populate Atlas with demonstration applications (APP-1001 & APP-1002)
python import_data.py

# 3. Test database queries
python test_db.py
```

---

## 🤝 Team Hand-off Notes

### 1. Backend & Pipeline Orchestration
Import directly from `crud.py`:
- `insert_extracted_fields(db, fields)`: Save fields extracted by AI.
- `insert_bank_transactions(db, txns)`: Save parsed bank transactions.
- `get_bank_statement_summary(db, ref)`: Check `opening + credits - debits == closing`.
- `add_cross_check(db, ref, check_data)`: Record declared vs verified mismatches.
- `update_risk(db, ref, ...)` & `update_routing(db, ref, "amber", reason)`: Save decisions.
- `log_audit_event(db, ref, actor, action, detail)`: Log audit timeline events.

### 2. Frontend & Dashboard UI
Call read helpers from `crud.py` — all return clean JSON ready for UI:
- `get_application_summary(db, ref)`: Header metrics & risk score.
- `get_extracted_evidence(db, ref)`: Bounding boxes for clickable PDF proof.
- `get_cross_check_results(db, ref)`: Declared vs verified discrepancy table.
- `get_entity_graph(db, ref)`: Applicant relationship graph.
- `get_bank_transactions(db, ref)` & `get_spending_summary(db, ref)`: Transactions & category charts.
- `get_audit_trail(db, ref)`: Timeline of events.

### 3. RAG Policy Engine
- `insert_policy_embeddings_bulk(db, chunks)`: Store policy chunks.
- `search_policy_chunks(db, loan_type, text_search)`: Query policy rules.
