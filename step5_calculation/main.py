import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from step5_calculation.app import build_step5_result

load_dotenv()

INPUT_DIR = root_dir / "step4_Document comparison" / "extracted_data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_clean_json(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if raw.startswith("//"):
        raw = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("//"))
    return json.loads(raw)


def main():
    target_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if target_arg and target_arg != "--all":
        # Process single applicant file
        if target_arg.endswith(".json"):
            input_files = [Path(target_arg)]
        else:
            input_files = [INPUT_DIR / f"{target_arg}.json"]
    else:
        # Process all applicant files
        input_files = sorted(INPUT_DIR.glob("P*.json"))

    if not input_files:
        print(f"No JSON input files found in '{INPUT_DIR}'")
        return

    print("=" * 65)
    print("STEP 5: DETERMINISTIC FINANCIAL & ELIGIBILITY CALCULATION RUNNER")
    print("=" * 65)
    print(f"Found {len(input_files)} document extraction file(s) to process.\n")

    successful, failed = 0, 0

    for input_file in input_files:
        if not input_file.exists():
            print(f"File not found: {input_file}")
            continue

        print(f"--> Processing {input_file.name}...")
        try:
            payload = load_clean_json(input_file)
            result = build_step5_result(payload)
            case_id = payload.get("_id", input_file.stem)

            output_file = OUTPUT_DIR / f"calculation_result_{case_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))

            # Persist to MongoDB
            try:
                from datetime import datetime, timezone
                from database.db_config import get_db
                db = get_db()
                db.applications.update_one(
                    {"application_ref": case_id},
                    {"$set": {"step5_calculation": result.model_dump(), "updated_at": datetime.now(timezone.utc)}}
                )
                print(f"    [DB] Saved to MongoDB (applications.step5_calculation)")
            except Exception as db_err:
                print(f"    [DB NOTE] MongoDB writeback skipped/failed: {db_err}")

            print(f"    [OK] Verified Income: Rs. {result.income_metrics.verified_monthly_income:,.2f} (Variance: {result.income_metrics.income_variance_percent}%)")
            print(f"         FOIR / DTI:      {result.obligation_metrics.foir_percentage}% | Statement Math: {result.statement_validation.status}")
            print(f"         Eligibility:     {result.eligibility_result.status} ({', '.join(result.eligibility_result.reasons)})")
            print(f"         Saved: {output_file.name}\n")
            successful += 1

        except Exception as e:
            print(f"    [ERROR] Failed to process {input_file.name}: {e}\n")
            failed += 1

    print(f"Completed Step 5: {successful} processed successfully, {failed} failed.")
    print("=" * 65)


if __name__ == "__main__":
    main()
