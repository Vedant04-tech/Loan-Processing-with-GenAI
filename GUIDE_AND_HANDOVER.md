# TRACE — Step 5 & Step 6 Underwriting Decision & Risk Engine
## Module Documentation and Handover Guide

---

## 1. System Architecture & Core Philosophy

This module implements **Step 5 (Calculation & Decision Engine)** and **Step 6 (Risk / Anomaly Engine)** of the TRACE Loan Document Processing Pipeline.

### Architectural Principle
> **"AI interprets nuanced context and classifies discrepancy severity, but financial math, obligation metrics, eligibility checks, risk scoring, and routing decisions are 100% deterministic and executed in plain Python."**

This ensures that financial decisions are mathematically verifiable, regulatory-compliant, explainable, and immune to LLM hallucination or calculation errors.

```
MongoDB Atlas (Application Data, Extracted Evidence, Bank Transactions)
   │
   ▼
STEP 5: Calculation Engine (Deterministic Python)
   ├── 5.1 Income Calculation (Verified payslips vs Bank salary credits)
   ├── 5.2 & 5.3 Obligations & Capacity (Declared vs Bank EMIs, FOIR/DTI)
   ├── 5.4 Statement Arithmetic Reconciliation (Opening + Credits - Debits == Closing)
   └── 5.5 Lender Policy Eligibility Checks (Evaluated against policies/personal_loan_rules.json)
   │
   ▼
STEP 6.1: Discrepancy Discovery Engine (Deterministic Python)
   └── Discovers and compiles evidence for all claim-vs-proof variances
   │
   ▼
STEP 6.2: LangChain Anomaly Classifier (ChatGroq / Gemini)
   └── Structured Pydantic severity classification (Minor / Moderate / Major) with safe fallback
   │
   ▼
STEP 6.3: Risk Scoring & 3-Tier Routing (Deterministic Python)
   ├── Mathematical point deductions (Base 100 -> Final Score 0-100)
   └── 3-Tier Routing: GREEN (Auto Approve) | AMBER (Human Review) | RED (Reject)
   │
   ▼
MongoDB Atlas Writeback
   ├── applications.financials (Verified Income, Total EMIs, FOIR, Eligibility)
   ├── applications.cross_checks (Itemized comparison records with severity & reasoning)
   ├── applications.risk (Score, Grade, Factor Breakdown)
   ├── applications.routing (Color & Routing Justification)
   └── audit_logs (Immutable timestamped audit trail)
```

---

## 2. Directory Structure & File Breakdown

The repository is modularized into step-based packages where each file is between 30 and 70 lines of clean, readable Python code:

```
My Part/
│
├── database/                    # Data Storage Layer
│   ├── db_config.py            # MongoDB Atlas connection manager with health check
│   ├── models.py               # Pydantic schemas for the 5 MongoDB collections
│   └── crud.py                 # Query and writeback functions
│
├── policies/                    # Underwriting Rules & Regulations
│   ├── policy_loader.py        # Dynamic JSON policy rules loader
│   └── personal_loan_rules.json # Policy specs (FOIR: 50%, Min Income: Rs. 25k, Variance: 10%)
│
├── step5_calculation/           # STEP 5: Calculation Engine (Deterministic Python)
│   ├── income.py               # 5.1 Payslip net pay averaging, bank salary credit resolution
│   ├── obligations.py          # 5.2 & 5.3 Declared vs bank EMIs, undisclosed debt, FOIR/DTI
│   ├── statement.py            # 5.4 Statement balance arithmetic (Opening + Credits - Debits == Closing)
│   └── eligibility.py          # 5.5 Policy threshold rule evaluations (Pass / Fail)
│
├── step6_risk_anomaly/          # STEP 6: Risk & Anomaly Engine
│   ├── schemas.py              # Pydantic models for LLM structured output
│   ├── discrepancy.py          # 6.1 Discrepancy discovery (Income, EMI, Statement, Identity, Employer)
│   ├── anomaly_classifier.py   # 6.2 LangChain ChatGroq structured classification with fallback
│   └── risk_rules.py           # 6.3 Mathematical risk scoring (0-100) and 3-tier routing
│
├── tests/                       # Test & Validation Suite
│   ├── test_db.py              # MongoDB Atlas query verification
│   └── test_decision_engine.py # 9-scenario unit & integration test suite
│
├── decision_engine.py           # Main Orchestrator: run_decision_pipeline(application_ref)
├── import_data.py               # Demonstration data loader for MongoDB Atlas
├── temp_verification_results.csv# Batch test results across Step 4 outputs
├── requirements.txt             # Python dependencies
└── .env & .gitignore            # Environment configuration & credential protection
```

---

## 3. Core Features Implemented

### Step 5: Calculation Engine
1. **Verified Income Calculation (`step5_calculation/income.py`)**:
   - Parses multiple payslips and calculates average net monthly salary.
   - Extracts verified `salary_credit` transactions from the bank statement.
   - Computes verified monthly income as the lower bound of payslip vs bank records to prevent income fraud.
   - Calculates exact income variance amount and percentage against declared figures.

2. **Obligations & FOIR / DTI (`step5_calculation/obligations.py`)**:
   - Aggregates declared monthly loan obligations.
   - Scans bank statement debits for recurring EMI / loan debits (`category == "emi_debit"` or narration patterns).
   - Detects **undisclosed liabilities** (loan stacking) when bank debits exceed declared debt.
   - Calculates proposed loan EMI (standard amortization math) and computes total Fixed Obligation to Income Ratio (FOIR).
   - Computes net disposable income.

3. **Bank Statement Arithmetic Reconciliation (`step5_calculation/statement.py`)**:
   - Reconciles the fundamental banking formula:
     $$\text{Opening Balance} + \text{Total Credits} - \text{Total Debits} == \text{Closing Balance}$$
   - Identifies corrupted, truncated, or tampered bank statements and flags arithmetic mismatches.

4. **Lender Policy Eligibility (`step5_calculation/eligibility.py`)**:
   - Evaluates applicant metrics against dynamic rules configured in `policies/personal_loan_rules.json`:
     - FOIR $\le 50.0\%$
     - Verified Monthly Net Income $\ge \text{Rs. } 25,000$
     - Income Variance $\le 20.0\%$
     - Undisclosed Debt Gap $< \text{Rs. } 10,000$
   - Returns a structured `PASS` or `FAIL` with itemized failure reasons.

---

### Step 6: Risk & Anomaly Engine
1. **Deterministic Discrepancy Discovery (`step6_risk_anomaly/discrepancy.py`)**:
   - Discovers claim-vs-proof variances before calling the LLM:
     - `INCOME_MISMATCH`
     - `UNDISCLOSED_LIABILITY`
     - `STATEMENT_ARITHMETIC_MISMATCH`
     - `EMPLOYMENT_MISMATCH`
     - `IDENTITY_MISMATCH`
     - `ELIGIBILITY_FAILURE`
     - `MISSING_EVIDENCE`

2. **LangChain Anomaly Classification (`step6_risk_anomaly/anomaly_classifier.py`)**:
   - Uses `ChatGroq` (`openai/gpt-oss-20b`) with `.with_structured_output(AnomalyAssessment)`.
   - Classifies each discrepancy into `Minor`, `Moderate`, or `Major` severity with underwriting reasoning grounded in evidence.
   - **Safe Fallback**: If the LLM call times out or network is unavailable, engages a deterministic rule fallback so the pipeline never fails.

3. **Mathematical Risk Scoring & 3-Tier Routing (`step6_risk_anomaly/risk_rules.py`)**:
   - Calculates risk score ($0–100$) starting from a base of 100 points:
     - Minor anomaly: $-10\text{ pts}$
     - Moderate anomaly: $-25\text{ pts}$
     - Major anomaly: $-45\text{ pts}$
     - Statement arithmetic failure: $-30\text{ pts}$
     - Policy eligibility failure: $-50\text{ pts}$
   - Deterministic 3-Tier Routing:
     - **GREEN (Auto Approve)**: Score $\ge 80$, eligibility passed, zero major/moderate anomalies, valid bank statement.
     - **AMBER (Human Review)**: Score $50–79$, or moderate anomalies, or minor variances flagged for manual verification.
     - **RED (Reject)**: Score $< 50$, or eligibility failed, or major anomalies detected (severe income overstatement, loan stacking, or statement failure).

---

## 4. How to Use the Pipeline

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure `.env`
Ensure your MongoDB Atlas URI and Groq / Gemini API keys are configured:
```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.cxry4fs.mongodb.net/trace_db?retryWrites=true&w=majority
MONGO_DB=trace_db
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AQ...
```

### Step 3: Seed Sample Applications (Optional)
```bash
python import_data.py
```

### Step 4: Run the Decision Pipeline (CLI)

You can run the decision pipeline by passing an application reference or a Step 4 comparison JSON file:

```bash
# Option A: Passing the Application ID
python decision_engine.py P002

# Option B: Passing a Step 4 JSON comparison file directly
python decision_engine.py "op by prachi/comparison_result_P003.json"
```

**Example Output:**
```
Ingesting Step 4 Comparison File: op by prachi/comparison_result_P003.json -> Applicant: P003
Running Decision Pipeline for: P003
Decision: GREEN (auto_approve)
Risk Score: 100.0/100 (Low)
Verified Income: Rs. 61,011.00
FOIR: 20.6%
Discrepancies: 0
Summary: All document checks and calculations verified without discrepancies.
```

### Step 5: Run Programmatically in Python

```python
from decision_engine import run_decision_pipeline

# Executes calculations, LLM anomaly classification, and writes to MongoDB
result = run_decision_pipeline("P003")

print("Routing Decision:", result.routing_color.upper())   # GREEN / AMBER / RED
print("Recommendation:", result.recommendation)           # auto_approve / human_review / reject
print("Risk Score:", result.risk_score)                   # 100.0
print("Verified Income:", result.income_metrics.verified_monthly_income)
print("FOIR:", result.obligation_metrics.foir_percentage)
print("Discrepancies:", len(result.discrepancies))
print("Underwriting Summary:", result.underwriting_summary)
```

---

## 5. Test Suite & Verification

The test suite covers **9 distinct underwriting scenarios**:

```bash
python -m unittest tests.test_decision_engine
```

### Test Coverage Breakdown
1. `test_1_verified_income_calculation`: Payslip averaging and bank salary credit resolution.
2. `test_2_obligations_and_foir`: Declared debt, proposed loan EMI, FOIR, and disposable income.
3. `test_3_undisclosed_liability_detection`: Detection of loan stacking / unstated bank EMIs.
4. `test_4_statement_arithmetic_matching`: Verified bank statement reconciliation.
5. `test_5_statement_arithmetic_mismatch`: Detection of corrupted / tampered statement balances.
6. `test_6_eligibility_check_pass_and_fail`: Evaluation of policy rules against applicant metrics.
7. `test_7_clean_applicant_routing_green`: Verified clean applicant routed to GREEN (Auto Approve).
8. `test_8_major_anomaly_routing_red`: Major income overstatement + undisclosed debt routed to RED (Reject).
9. `test_9_llm_fallback_resilience`: Validates safe deterministic execution when LLM is unavailable.

---

## 6. Panel Defense & Presentation Guide

When presenting this module to evaluators or the assessment panel, emphasize these points:

1. **Deterministic Separation**:
   *"We strictly avoid letting the LLM calculate numbers or assign arbitrary approval scores. Python performs all arithmetic and rule validations; the LLM is used exclusively for linguistic interpretation and severity explanation."*

2. **Defense Against Fraud & Tampering**:
   *"Our engine catches two of the most common loan fraud vectors: income inflation (via payslip vs bank salary reconciliation) and loan stacking (via recurring bank EMI debit discovery)."*

3. **Production-Ready Fallback**:
   *"If the LLM API is unreachable or rate-limited, the system falls back to rule-based classification and continues to function without downtime."*

4. **Auditable MongoDB Writeback**:
   *"Every decision generates verified financial records, itemized cross-checks, risk breakdowns, and an immutable audit log entry in MongoDB Atlas for regulatory compliance."*
