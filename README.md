# TRACE - Database Layer

MongoDB data storage layer for the TRACE loan document processing platform.

---

## Project Structure

- `db_config.py` - MongoDB client and connection handling.
- `models.py` - Pydantic data schemas for collections.
- `crud.py` - Helper functions for reading and writing data across pipeline steps.
- `import_data.py` - Ingestion and sample data loader.
- `test_db.py` - Script to verify database connectivity and basic queries.

---

## Collections

1. `applications`: Stores application details, applicant info, uploaded document metadata, financial metrics, risk assessment, cross-check comparisons, and entity relationship graphs.
2. `extracted_fields`: Stores individual extracted key-value pairs along with page numbers, quoted text, and bounding box coordinates for source verification.
3. `bank_transactions`: Stores parsed transaction rows categorized into salary credits, EMI debits, rent, UPI spends, etc.
4. `audit_logs`: Append-only event history tracking pipeline execution.
5. `policy_embeddings`: Text chunks of lender underwriting guidelines for policy retrieval.

---

## Setup & Running

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
Create a `.env` file with your MongoDB connection string:
```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.cxry4fs.mongodb.net/trace_db?retryWrites=true&w=majority
MONGO_DB=trace_db
```

3. Load sample applications:
```bash
python import_data.py
```

4. Run verification test:
```bash
python test_db.py
```

---

## Integration Guide for Team

### Backend / Pipeline

Import helper functions from `crud.py`:

```python
from db_config import get_db
from crud import (
    create_application,
    insert_extracted_fields,
    insert_bank_transactions,
    add_cross_check,
    update_risk,
    update_routing,
    log_audit_event,
    get_bank_statement_summary
)

db = get_db()

# Save extracted fields
insert_extracted_fields(db, fields_list)

# Save parsed bank transactions
insert_bank_transactions(db, transactions_list)

# Check statement arithmetic
summary = get_bank_statement_summary(db, "APP-1001")

# Add cross-document comparison check
add_cross_check(db, "APP-1001", check_data)

# Update risk score and routing
update_risk(db, "APP-1001", score=65.0, grade="Moderate", recommendation="human_review", factors={...})
update_routing(db, "APP-1001", color="amber", reason="Salary credit variance flagged")

# Log pipeline event
log_audit_event(db, "APP-1001", actor="pipeline", action="processing_complete")
```

### Frontend / Dashboard

Read queries return formatted dictionaries for direct UI rendering:

```python
from db_config import get_db
from crud import (
    get_application_summary,
    get_extracted_evidence,
    get_cross_check_results,
    get_entity_graph,
    get_bank_transactions,
    get_spending_summary,
    get_audit_trail
)

db = get_db()

summary = get_application_summary(db, "APP-1001")
evidence = get_extracted_evidence(db, "APP-1001")
cross_checks = get_cross_check_results(db, "APP-1001")
entity_graph = get_entity_graph(db, "APP-1001")
transactions = get_bank_transactions(db, "APP-1001")
spending = get_spending_summary(db, "APP-1001")
audit_trail = get_audit_trail(db, "APP-1001")
```

### Policy RAG

```python
from db_config import get_db
from crud import insert_policy_embeddings_bulk, search_policy_chunks

db = get_db()

insert_policy_embeddings_bulk(db, chunks_list)
matches = search_policy_chunks(db, loan_type="personal_loan", text_search="FOIR")
```
