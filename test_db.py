"""
TRACE — Simple Database Smoke Test
Runs a quick check on Atlas connection and queries.
"""

from db_config import check_health, get_db
from crud import (
    get_application_summary,
    get_extracted_evidence,
    get_cross_check_results,
    get_entity_graph,
    get_bank_transactions,
    get_spending_summary,
)

def run():
    print("=" * 50)
    print("  TRACE Database Smoke Test")
    print("=" * 50)

    # 1. Health Check
    health = check_health()
    if health["status"] != "connected":
        print(f"❌ Connection Failed: {health.get('message')}")
        print("💡 Ensure you whitelisted IP in MongoDB Atlas (0.0.0.0/0).")
        return
    print(f"✅ MongoDB Atlas Connected! (Database: {health.get('database')})")

    db = get_db()
    
    # 2. Check Applications in DB
    app = db.applications.find_one({}, {"application_ref": 1})
    if not app:
        print("⚠️ No data in database yet.")
        print("👉 Run: python import_data.py")
        return

    ref = app["application_ref"]
    print(f"\n📂 Testing Sample Application: {ref}")

    # Summary
    summary = get_application_summary(db, ref)
    if summary:
        print(f"   👤 Applicant: {summary.get('full_name')} ({summary.get('employer_name')})")
        print(f"   💰 Verified Monthly Income: ₹{summary.get('verified_monthly_income', 0):,.2f}")
        print(f"   🚦 Routing Decision: {summary.get('routing_color') or 'Pending'}")

    # Evidence Count
    evidence = get_extracted_evidence(db, ref)
    print(f"   🔍 Extracted Evidence Fields: {len(evidence)} fields (with bounding boxes)")

    # Transactions & Spending
    txns = get_bank_transactions(db, ref)
    spending = get_spending_summary(db, ref)
    print(f"   🏦 Bank Transactions: {len(txns)} rows")
    if spending:
        top_cat = list(spending.keys())[0]
        print(f"   📊 Top Debit Category: {top_cat} (₹{spending[top_cat]['total']:,.2f})")

    # Cross Checks & Graph
    checks = get_cross_check_results(db, ref)
    graph = get_entity_graph(db, ref)
    print(f"   ⚖️ Cross-Document Checks: {len(checks)} checks")
    print(f"   🕸️ Entity Graph Edges: {len(graph)} connections")

    print("\n🎉 All 5 collections tested and operational!\n")

if __name__ == "__main__":
    run()
