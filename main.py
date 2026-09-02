import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from database.db_config import get_db
from pipeline import run_pipeline, PipelineResult


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


BENCHMARK_APPLICANTS = ["P002", "P003", "P004", "P006", "P007", "P008", "P009", "P011", "P013", "P017"]


def print_banner():
    print("=" * 70)
    print("  [TRACE] UNDERWRITING & DECISION INTELLIGENCE PLATFORM")
    print("=" * 70)


def print_result(res: PipelineResult):
    color_tag = {"green": "[GREEN]", "amber": "[AMBER]", "red": "[RED]"}.get(res.routing_color, "[INFO]")

    print(f"\n{color_tag} ROUTING OUTCOME: {res.routing_color.upper()} -- Case: {res.application_ref}")
    print("-" * 70)
    print(f"  Recommendation:      {res.recommendation.upper()}")
    print(f"  Human Sign-off:      {'REQUIRED (Strictly Enforced)' if res.requires_human_signoff else 'None'}")
    print(f"  Application Status:  {res.status.upper()}")
    print(f"  Risk Score:          {res.risk_score} / 100 ({res.risk_grade} Risk)")
    print(f"  Decision Reason:     {res.routing_reason}")
    print(f"  LLM Fallback Active: {res.is_llm_fallback}")

    print("\n  QUANTIFIED FACTOR BREAKDOWN:")
    fb = res.factor_breakdown
    print(f"    - Base Score:                  {fb.get('base_score', 100.0)}")
    print(f"    - Major Anomalies Deduction:   {fb.get('major_anomalies_deduction', 0.0)}")
    print(f"    - Moderate Deduction:          {fb.get('moderate_anomalies_deduction', 0.0)}")
    print(f"    - Statement Math Deduction:    {fb.get('statement_arithmetic_deduction', 0.0)}")
    print(f"    - Eligibility Deduction:       {fb.get('eligibility_failure_deduction', 0.0)}")
    print(f"    - Final Calculated Score:      {fb.get('final_calculated_score', res.risk_score)}")

    print("\n  DETERMINISTIC FINANCIAL METRICS:")
    print(f"    - Verified Monthly Income:     Rs. {res.income_metrics.verified_monthly_income:,.2f} (Variance: {res.income_metrics.income_variance_percent}%)")
    print(f"    - Existing EMIs:               Rs. {res.obligation_metrics.total_existing_emis:,.2f}")
    print(f"    - Proposed EMI:                Rs. {res.obligation_metrics.proposed_emi:,.2f}")
    print(f"    - Total Monthly Obligations:   Rs. {res.obligation_metrics.total_monthly_obligations:,.2f}")
    print(f"    - FOIR / DTI:                  {res.obligation_metrics.foir_percentage}%")
    print(f"    - Disposable Income:           Rs. {res.obligation_metrics.disposable_income:,.2f}")

    print("\n  VERIFICATION & AUDIT:")
    print(f"    - Statement Arithmetic:        {res.statement_validation.status} ({res.statement_validation.message})")
    print(f"    - Policy Eligibility:          {res.eligibility_result.status}")
    print(f"    - Discrepancies Count:         {len(res.discrepancies)}")

    if res.discrepancies:
        for i, d in enumerate(res.discrepancies, 1):
            print(f"      {i}. [{d.discrepancy_type}] {d.evidence_summary}")

    print("\n  UNDERWRITER REVIEW CHECKLIST:")
    for step in res.reviewer_checklist:
        print(f"    [ ] {step}")

    if res.counterfactual_note:
        print(f"\n  COUNTERFACTUAL REASONING:\n    {res.counterfactual_note}")

    print("-" * 70)



def main():
    print_banner()

    db = None
    try:
        db = get_db()
        print("Connected to MongoDB Atlas.")
    except Exception as e:
        print(f"Running in standalone local mode (DB unavailable: {e})")

    target = sys.argv[1] if len(sys.argv) > 1 else "P003"

    if target in ("--all", "all"):
        print(f"\nRunning full underwriting benchmark across {len(BENCHMARK_APPLICANTS)} applicants...\n")
        results = []
        for ref in BENCHMARK_APPLICANTS:
            try:
                res = run_pipeline(ref, db=db)
                results.append(res)
                color_tag = {"green": "[GREEN]", "amber": "[AMBER]", "red": "[RED]"}.get(res.routing_color, "[INFO]")
                print(f"  {color_tag:<7} {res.application_ref:<6} | {res.routing_color.upper():<6} | {res.recommendation:<18} | Score: {res.risk_score:>5.1f} | FOIR: {res.obligation_metrics.foir_percentage:>5.1f}% | Discrepancies: {len(res.discrepancies)}")
            except Exception as e:
                print(f"  [FAIL]  {ref:<6} | FAILED: {e}")


        print(f"\nBenchmark run complete: {len(results)}/{len(BENCHMARK_APPLICANTS)} evaluated successfully.")
        print("=" * 70)
        return

    # Single application run
    if target.endswith(".json"):
        # Handle file paths like step4 output comparison_result_P003.json
        base = os.path.splitext(os.path.basename(target))[0]
        target = base.replace("comparison_result_", "").replace("calculation_result_", "").replace("risk_result_", "")

    print(f"\nProcessing Application Reference: {target}...")
    try:
        res = run_pipeline(target, db=db)
        print_result(res)
    except Exception as e:
        print(f"\nPipeline execution failed for '{target}': {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
