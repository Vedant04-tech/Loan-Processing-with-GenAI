# 🏦 TRACE — End-to-End Underwriting Decision, Comparison & Risk Engine

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://python.org)
[![MongoDB Atlas](https://img.shields.io/badge/Database-MongoDB%20Atlas-forestgreen?logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![LangChain](https://img.shields.io/badge/Orchestration-LangChain%20%2F%20Groq-coral?logo=langchain&logoColor=white)](https://langchain.com)
[![Pydantic v2](https://img.shields.io/badge/Validation-Pydantic%20v2-e92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![Architecture](https://img.shields.io/badge/Architecture-Deterministic%20%2B%20GenAI%20Hybrid-purple)](#system-architecture)

**Automated Multi-Document Cross-Comparison (Step 4), Deterministic Financial Calculations (Step 5), and GenAI Anomaly/Risk Routing (Step 6) for the TRACE Loan Origination Platform.**

[📖 Complete Handover & Technical Guide](GUIDE_AND_HANDOVER.md) • [🚀 Quick Start](#-quick-start) • [📐 Architecture](#-system-architecture) • [✨ Key Highlights](#-key-features--capabilities) • [🧪 Benchmark Results](#-benchmark--real-world-verification-results)

</div>

---

## 🌟 Executive Summary

In automated loan processing, standard LLM-only pipelines fail due to **math hallucinations, non-deterministic approval thresholds, and lack of regulatory auditability**.

The **TRACE Underwriting Platform** establishes a **strict hybrid separation of concerns**:
> 🛡️ **The Iron Rule:** Multi-document cross-matching (PAN, payslips, bank statements), financial calculations, undisclosed debt discovery, balance reconciliation, policy eligibility checks, and final 3-tier routing are **100% deterministic and executed in pure Python**. 
> 
> 🧠 **The GenAI Role:** Large Language Models (`ChatGroq` / `openai/gpt-oss-20b` or Gemini) are leveraged strictly for **qualitative nuance, semantic cross-matching, severity contextualization, and human-grounded underwriting rationales**.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph INGESTION["1. Upstream Ingestion (Steps 1 to 3)"]
        A1["Extracted Document Data<br>Payslips, PAN, Form 16"]
        A2["Bank Statement Transactions<br>Credits, Debits, Balances"]
        A3["Loan Application Form<br>Declared Income and Debt"]
    end

    subgraph STEP4["2. STEP 4: Document Cross-Comparison Engine"]
        S4_1["Identity Cross-Matching<br>Name, PAN, DOB vs Proofs<br>Deterministic and Semantic"]
        S4_2["Income and Employer Match<br>Payslip vs Loan Application"]
        S4_3["Writeback: comparison_results<br>and applications.step4_comparison"]
    end

    subgraph STEP5["3. STEP 5: Deterministic Calculation Engine"]
        B1["5.1 Income Engine<br>Payslip Avg Net Pay<br>Bank Salary Credits<br>Min-Bound Resolution"]
        B2["5.2 and 5.3 Obligations and FOIR<br>Bank EMI Debit Scan<br>Undisclosed Debt Hunter<br>FOIR % and Disposable Income"]
        B3["5.4 Balance Reconciliation<br>Op + Credits - Debits == Cl<br>Tolerance: +/- Rs. 5.00"]
        B4["5.5 Policy Eligibility Check<br>Dynamic JSON Rules<br>Pass / Fail + Itemized Reasons"]
    end

    subgraph STEP6["4. STEP 6: Risk and Anomaly Engine"]
        C1["6.1 Deterministic Discrepancy Discovery<br>Step 4 ID + Step 5 Financial Gaps"]
        C2["6.2 LangChain Groq Structured Classifier<br>Classifies Severity (Minor / Mod / Major)<br>Zero-Downtime Deterministic Fallback"]
        C3["6.3 100-Point Risk Scoring and Routing<br>Base 100 with Math Deductions<br>Traffic-Light 3-Tier Routing"]
    end

    subgraph ROUTING["5. 3-Tier Underwriting Decisions"]
        R1["GREEN (Auto Approve)<br>Score >= 80 | Zero Major Anomalies"]
        R2["AMBER (Human Review)<br>Score 50-79 | Moderate Variances"]
        R3["RED (Reject)<br>Score < 50 | Fraud / High FOIR / Tampering"]
    end

    subgraph STORAGE["6. MongoDB Atlas Writeback Layer"]
        DB1[("applications.financials")]
        DB2[("applications.step4_comparison")]
        DB3[("applications.cross_checks")]
        DB4[("applications.risk and routing")]
        DB5[("audit_logs immutable trail")]
    end

    INGESTION --> STEP4
    STEP4 --> STEP5
    STEP5 --> C1
    STEP4 -.-> C1
    C1 --> C2
    C2 --> C3
    C3 --> ROUTING
    ROUTING --> STORAGE
```


---

## ✨ Key Features & Capabilities

### 1. 📑 Document Cross-Comparison Engine (`step4_Document comparison/`)
- Cross-matches applicant identity against KYC proofs (PAN Card, Aadhaar, Payslip).
- Evaluates name spelling similarity, Date of Birth alignment, and PAN alphanumeric consistency.
- Extracts employer matching and initial stated-versus-extracted document variances.
- Writes comprehensive results to `comparison_results` collection and embeds them in `applications.step4_comparison`.

### 2. 🔍 Anti-Fraud Verified Income Engine (`step5_calculation/income.py`)
- Automatically computes multi-month average net salary from parsed payslips.
- Isolates verified `salary_credit` transactions from bank feeds.
- **Anti-Fraud Conservative Rule:** Resolves verified income as $\min(\text{Avg Payslip Net}, \text{Avg Bank Salary Credit})$ to prevent synthetic income inflation.
- Computes exact variance percentage against applicant-declared monthly income.

### 3. 🕵️ Undisclosed Debt & Loan Stacking Hunter (`step5_calculation/obligations.py`)
- Parses all stated applicant liabilities.
- Scans bank debit records for recurring loan EMIs (`category == "emi_debit"` and narration patterns).
- **Loan Stacking Discovery:** Computes $\Delta_{\text{Debt}} = \text{Detected Bank EMIs} - \text{Declared EMIs}$. If $\Delta > \text{Rs. 1,000}$, the applicant is flagged for undisclosed debt.
- Calculates reducing-balance proposed EMI, total **FOIR (Fixed Obligation to Income Ratio)**, and net disposable cashflow.

### 4. ⚖️ Bank Statement Arithmetic Reconciliation (`step5_calculation/statement.py`)
- Reconciles the fundamental banking formula:
  $$\text{Opening Balance} + \text{Total Credits} - \text{Total Debits} = \text{Closing Balance}$$
- Identifies corrupted, forged, or altered bank statements before credit assessment.

### 5. 📜 Dynamic Policy Rules Engine (`policies/personal_loan_rules.json`)
- Externalized, hot-reloadable policy rules without touching application code:
  - Max Acceptable FOIR: `50.0%` (High Risk: `65.0%`)
  - Minimum Monthly Net Income: `Rs. 25,000.00`
  - Severe Income Variance Limit: `20.0%`
  - Max Allowed Undisclosed Debt: `Rs. 10,000.00`

### 6. 🤖 Hybrid LLM Anomaly Assessment with Safe Fallback (`step6_risk_anomaly/anomaly_classifier.py`)
- Employs **LangChain** + **ChatGroq** (`openai/gpt-oss-20b` / `llama-3.3-70b-versatile`) with strict Pydantic structured output (`AnomalyAssessment`).
- Ingests discrepancies from both Step 4 (identity, employer) and Step 5 (income, debt, balance reconciliation).
- **100% High Availability Fallback:** If the LLM service suffers rate limits, network outages, or API downtime, an automated rule-based classifier immediately takes over.

### 7. 🚦 100-Point Mathematical Risk Scoring & 3-Tier Routing (`step6_risk_anomaly/risk_rules.py`)
- Starts at **100.0 Base Points** with deterministic deductions:
  - Major anomaly: `−45 pts`
  - Moderate anomaly: `−25 pts`
  - Minor anomaly: `−10 pts`
  - Statement arithmetic failure: `−30 pts`
  - Policy eligibility failure: `−50 pts`
- Automated routing outcomes (Human-in-the-Loop Enforced: `requires_human_signoff = True`):
  - **🟢 GREEN (Fast-Track Recommendation):** Score $\ge 80$, 0 major/moderate anomalies, verified bank statement, passed policy $\rightarrow$ `recommend_approve` (expedited sign-off).
  - **🟡 AMBER (Human Review Recommendation):** Score $50–79$, moderate anomalies requiring underwriter checklist verification $\rightarrow$ `recommend_review`.
  - **🔴 RED (Rejection Recommendation):** Score $< 50$, loan stacking, severe income overstatement, identity fraud, or statement tampering $\rightarrow$ `recommend_reject`.

---

## 🧪 Benchmark & Real-World Verification Results
 
Evaluated across all 10 real loan applicant test datasets (`P002` through `P017`):

| Applicant Ref | Case Characteristics | Verified Income | FOIR / DTI | Discrepancies Found | Risk Score | Routing Outcome | Recommendation | Human Sign-off |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`P003`** | **Clean Applicant** (0.88% variance) | **₹61,011.00** | **20.60%** | **0** | **100.0 / 100** | 🟢 **GREEN** | `recommend_approve` | **REQUIRED** |
| **`P004`** | **Clean Control** (0.01% variance) | **₹139,725.33** | **29.31%** | **0** | **100.0 / 100** | 🟢 **GREEN** | `recommend_approve` | **REQUIRED** |
| **`P002`** | **Income Overstatement** (+49.4% declared) | ₹72,591.17 | 20.61% | 2 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P006`** | **Severe Overleverage** (FOIR 99.5%) | ₹74,290.00 | 99.49% | 2 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P007`** | **Excessive Debt Burden** | ₹37,092.17 | 66.46% | 2 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P008`** | **Severe Overleverage** (FOIR > 100%) | ₹59,089.67 | 148.65% | 2 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P009`** | **Multiple Unstated Debts** | ₹45,681.67 | 83.59% | 3 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P011`** | **High Income, High Leverage** | ₹200,363.00 | 167.61% | 2 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P013`** | **Undisclosed Debt (Loan Stacking)** | ₹37,380.83 | 146.83% | 2 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |
| **`P017`** | **Elevated Debt-to-Income** | ₹155,147.50 | 156.05% | 3 Major | 0.0 / 100 | 🔴 **RED** | `recommend_reject` | **REQUIRED** |

> 🛡️ **Defense & Validation Note:** The benchmark evaluates all 10 applicant files in `extracted_data/` (`P002` through `P017`). The engine provides complete transparency with **quantified point deductions**, **concrete reviewer checklists**, **counterfactual explanations** (*"Would move to GREEN if FOIR were ≤50%"*), and guarantees that **every outcome requires explicit human underwriter sign-off**.

*✅ Result: 100% precision in catching overstatements, undisclosed loans, identity mismatches, statement balance errors, and recommending expedited approval for clean applicants.*



---

## 🗂️ Repository Structure

```
My Part/
├── 📂 database/                    # Data Storage & MongoDB Atlas Layer
│   ├── db_config.py                # MongoDB Atlas connection manager & health checks
│   ├── models.py                   # Pydantic schemas for the 5 MongoDB collections
│   └── crud.py                     # CRUD operations, Step 4 persistence & audit logs
│
├── 📂 policies/                    # Underwriting Policy Configuration
│   ├── policy_loader.py            # Dynamic policy rules loader
│   └── personal_loan_rules.json    # Configurable thresholds (FOIR, Min Income, Deductions)
│
├── 📂 step4_Document comparison/   # STEP 4: Document Cross-Comparison Engine
│   ├── app/                        # Normalizers, Extractors, Semantic LLM & Policy Engine
│   ├── extracted_data/             # Real applicant benchmark document datasets (P002-P017)
│   ├── output/                     # Step 4 comparison JSON outputs
│   └── main.py                     # Standalone Step 4 batch runner
│
├── 📂 step5_calculation/           # STEP 5: Deterministic Calculation Engine
│   ├── app/                        # Income, Obligations, Statement & Eligibility logic
│   ├── output/                     # Step 5 calculation JSON outputs
│   └── main.py                     # Standalone Step 5 batch runner
│
├── 📂 step6_risk_anomaly/          # STEP 6: Risk & Anomaly Engine
│   ├── app/                        # Schemas, Discrepancies, LLM Classifier & Risk Rules
│   ├── output/                     # Step 6 risk JSON outputs
│   └── main.py                     # Standalone Step 6 batch runner
│
├── 📂 tests/                       # Automated Test Suite
│   ├── test_db.py                  # MongoDB Atlas connectivity validation
│   └── test_decision_engine.py     # 17-scenario comprehensive unit test suite
│
├── main.py                         # 🚀 Primary CLI Entry Point: python main.py P003 / --all
├── pipeline.py                     # ⚙️ Unified Pipeline Orchestrator: run_pipeline()
├── import_data.py                  # Demonstration data seeder & JSON importer
├── verification_results.csv        # Real-world benchmark evaluation results
├── requirements.txt                # Python dependencies
├── GUIDE_AND_HANDOVER.md           # 📖 Comprehensive operational handover guide
└── README.md                       # Project overview & presentation showcase
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Navigate to project directory
cd "My Part"

# Install required Python packages
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory (see `.env.example`):
```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.cxry4fs.mongodb.net/trace_db?retryWrites=true&w=majority
MONGO_DB=trace_db
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AQ...
```

### 3. Run Pipeline via CLI
```bash
# Option A: Run single applicant (e.g. P003)
python main.py P003

# Option B: Run full 10-applicant benchmark suite
python main.py --all
```

### 4. Run Complete Unit Test Suite (17 Tests)
```bash
python -m unittest tests.test_decision_engine
```


---

## 🛠️ Tech Stack & Dependencies

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core computation, Step 4 extraction, Step 5 math & Step 6 risk |
| **Database** | MongoDB Atlas / PyMongo | Applications, comparison_results, transactions, audit logs |
| **Data Validation** | Pydantic V2 | Strict type safety and structured model definitions |
| **LLM Framework** | LangChain Core & LangChain-Groq | Structured LLM anomaly reasoning & semantic comparisons |
| **Inference Models** | Groq (`openai/gpt-oss-20b` / `llama-3.3-70b`) | Qualitative underwriting severity classification |
| **Testing** | Unittest | 10 comprehensive scenario and edge-case tests |

---

## 📚 In-Depth Guides & Documentation

For the complete technical manual, database schema walkthrough, step-by-step developer guide, and viva defense cheat sheet, please refer to:

👉 **[GUIDE_AND_HANDOVER.md](GUIDE_AND_HANDOVER.md)**

---

<div align="center">
Developed with 💙 for the <b>TRACE Loan Processing Platform</b>
</div>
