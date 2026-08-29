# TRACE — Step 5 & Step 6 Underwriting Decision & Risk Engine

Deterministic Financial Calculation, Policy Eligibility, and Risk/Anomaly Engine for the TRACE loan processing platform.

For full technical documentation, architecture walkthrough, and panel defense guide, see **[GUIDE_AND_HANDOVER.md](GUIDE_AND_HANDOVER.md)**.

---

## Directory Layout (By Pipeline Step)

```
My Part/
│
├── database/                    # Data Storage Layer (MongoDB Atlas)
│   ├── db_config.py            # MongoDB connection client & health check
│   ├── models.py               # Pydantic schemas for the 5 collections
│   └── crud.py                 # Query and writeback helper functions
│
├── policies/                    # Underwriting Rules & Regulations
│   ├── policy_loader.py        # Dynamic policy rules loader
│   └── personal_loan_rules.json # Policy specs (FOIR: 50%, Min Income: Rs. 25k, Variance: 10%)
│
├── step5_calculation/           # STEP 5: Calculation Engine (Deterministic Python)
│   ├── income.py               # 5.1 Verified payslips, bank salary credits, variance
│   ├── obligations.py          # 5.2 & 5.3 Declared vs bank EMIs, FOIR, disposable income
│   ├── statement.py            # 5.4 Statement arithmetic validation (Op + Cr - Dr == Cl)
│   └── eligibility.py          # 5.5 Policy eligibility evaluations (Pass / Fail)
│
├── step6_risk_anomaly/          # STEP 6: Risk & Anomaly Engine
│   ├── schemas.py              # Pydantic schemas for structured anomaly output
│   ├── discrepancy.py          # 6.1 Deterministic discrepancy discovery & evidence linking
│   ├── anomaly_classifier.py   # 6.2 LangChain ChatGroq structured classification with fallback
│   └── risk_rules.py           # 6.3 Mathematical risk scoring (0-100) & 3-tier routing
│
├── tests/                       # Test & Validation Suite
│   ├── test_db.py              # Database connectivity test
│   └── test_decision_engine.py # 9-scenario unit & integration test suite
│
├── decision_engine.py           # Main Orchestrator: run_decision_pipeline(application_ref)
├── import_data.py               # Demonstration data loader
├── temp_verification_results.csv# Batch test results across Step 4 outputs
├── GUIDE_AND_HANDOVER.md        # Comprehensive technical guide & presentation sheet
├── requirements.txt             # Project dependencies
└── README.md                    # System overview
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Set your MongoDB Atlas connection and LLM API keys in `.env`:
```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.cxry4fs.mongodb.net/trace_db?retryWrites=true&w=majority
MONGO_DB=trace_db
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AQ...
```

### 3. Run Pipeline via CLI

```bash
# Run for an application:
python decision_engine.py P002

# Or pass a Step 4 JSON comparison file directly:
python decision_engine.py "op by prachi/comparison_result_P003.json"
```

### 4. Run Unit Test Suite
```bash
python -m unittest tests.test_decision_engine
```
