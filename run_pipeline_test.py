import os
import sys
import json
from database.db_config import get_db
from database import crud
from import_data import import_application_json
from decision_engine import run_decision_pipeline

def run_test():
    print("=" * 60)
    print("INTEGRATION PIPELINE TEST RUNNER")
    print("=" * 60)
    
    db = get_db()
    app_ref = "P002"
    json_path = os.path.join("step4_Document comparison", "extracted_data", f"{app_ref}.json")
    
    if not os.path.exists(json_path):
        print(f"Error: Could not find source file at '{json_path}'")
        return
        
    print(f"1. Seeding database with application '{app_ref}' if not present...")
    app = crud.get_application(db, app_ref)
    if not app:
        import_application_json(db, json_path)
        print(f"[OK] Application '{app_ref}' imported successfully.")
    else:
        print(f"[OK] Application '{app_ref}' already exists in database.")

    print(f"\n2. Executing Integrated Decision Pipeline for '{app_ref}'...")
    print("   (This runs Step 4, stores result, executes Step 5 & Step 6...)")
    pipeline_res = run_decision_pipeline(app_ref, db=db)
    
    print("\n3. Verifying database writeback for Step 4 comparison...")
    db_comparison = db.comparison_results.find_one({"application_ref": app_ref})
    if db_comparison:
        print("[OK] SUCCESS: Step 4 comparison results found in separate 'comparison_results' collection.")
        print(f"   Identity Status: {db_comparison.get('identity_status')}")
        print(f"   Income Status:   {db_comparison.get('income_status')}")
        print(f"   Overall Status:  {db_comparison.get('overall_status')}")
    else:
        print("[FAIL] FAILED: Step 4 comparison results not found in 'comparison_results' collection.")

    updated_app = crud.get_application(db, app_ref)
    if updated_app and "step4_comparison" in updated_app:
        print("[OK] SUCCESS: Step 4 comparison results found embedded inside application document.")
    else:
        print("[FAIL] FAILED: Step 4 comparison results not found inside application document.")

    print("\n4. Final Underwriting & Risk Engine Outcomes:")
    print(f"   Routing Color:  {pipeline_res.routing_color.upper()}")
    print(f"   Recommendation: {pipeline_res.recommendation.upper()}")
    print(f"   Risk Score:     {pipeline_res.risk_score}/100 ({pipeline_res.risk_grade})")
    print(f"   Underwriting:   {pipeline_res.underwriting_summary}")
    
    print("\n5. Discrepancies processed by Step 6 (including Step 4):")
    for disc in pipeline_res.discrepancies:
        print(f"   - [{disc.discrepancy_type}] Declared: {disc.declared_value} | Verified: {disc.verified_value}")
        print(f"     Evidence: {disc.evidence_summary}")
        
    print("=" * 60)

if __name__ == "__main__":
    run_test()
