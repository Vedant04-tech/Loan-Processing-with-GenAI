import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db_config import check_health, get_db
from database.crud import (
    get_application_summary,
    get_extracted_evidence,
    get_cross_check_results,
    get_entity_graph,
    get_bank_transactions,
    get_spending_summary,
)


def run():
    print("----------------------------------------")
    print("TRACE Database Connection & Query Test")
    print("----------------------------------------")

    health = check_health()
    if health["status"] != "connected":
        print(f"Connection failed: {health.get('message')}")
        return

    print(f"MongoDB Atlas Status: Connected (DB: {health.get('database')})")
    db = get_db()

    app = db.applications.find_one({}, {"application_ref": 1})
    if not app:
        print("No applications found in database. Run 'python import_data.py' first.")
        return

    ref = app["application_ref"]
    print(f"\nQuerying Application: {ref}")

    summary = get_application_summary(db, ref)
    if summary:
        print(f"  Applicant: {summary.get('full_name')} ({summary.get('employer_name')})")
        print(f"  Verified Monthly Income: Rs. {summary.get('verified_monthly_income', 0):,.2f}")
        print(f"  Routing Status: {summary.get('routing_color') or 'Pending'}")

    evidence = get_extracted_evidence(db, ref)
    print(f"  Extracted Evidence Records: {len(evidence)}")

    txns = get_bank_transactions(db, ref)
    spending = get_spending_summary(db, ref)
    print(f"  Bank Transactions: {len(txns)}")
    if spending:
        top_cat = list(spending.keys())[0]
        print(f"  Top Debit Category: {top_cat} (Rs. {spending[top_cat]['total']:,.2f})")

    checks = get_cross_check_results(db, ref)
    graph = get_entity_graph(db, ref)
    print(f"  Cross-Document Checks: {len(checks)}")
    print(f"  Entity Graph Edges: {len(graph)}")

    print("\nDatabase verification complete.")


if __name__ == "__main__":
    run()
