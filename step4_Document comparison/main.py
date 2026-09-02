import json
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.pipeline import build_pipeline_result
from app.database import (
    get_all_applications,
    get_application,
    update_comparison_result,
)

load_dotenv()

INPUT_DIR = BASE_DIR / "extracted_data"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_clean_json(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if raw.startswith("//"):
        raw = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("//"))
    return json.loads(raw)


def main():
    print("=" * 60)
    print("LOAN APPLICATION COMPARISON ENGINE (STEP 4)")
    print("=" * 60)

    target_arg = sys.argv[1] if len(sys.argv) > 1 else None

    # Option 1: Process from MongoDB if requested or if no argument is passed
    use_mongo = target_arg in ["--mongo", "-m"] or (target_arg is None)

    applications = []
    if use_mongo:
        try:
            print("\nFetching applications from MongoDB...")
            applications = get_all_applications()
            print(f"Found {len(applications)} applications in MongoDB.")
        except Exception as db_err:
            print(f"MongoDB connection note: {db_err}")
            applications = []

    successful, failed = 0, 0

    if applications and target_arg != "--local":
        for payload in applications:
            app_id = str(payload.get("_id", payload.get("application_id", "UNKNOWN")))
            print("\n" + "=" * 60)
            print(f"Processing MongoDB application: {app_id}")
            print("=" * 60)

            try:
                result = build_pipeline_result(payload)
                result_dict = result.model_dump()

                try:
                    update_comparison_result(app_id, result_dict)
                    print("  [DB] Comparison result stored in MongoDB.")
                except Exception as db_save_err:
                    print(f"  [DB NOTE] Could not update MongoDB: {db_save_err}")

                output_file = OUTPUT_DIR / f"comparison_result_{app_id}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result.model_dump_json(indent=2))

                print(f"  [OK] Saved locally: {output_file.name}")
                print(f"  Overall Status: {result.overall_status} | Risk: {result.risk_level} | Recommendation: {result.recommendation}")
                successful += 1
            except Exception as e:
                print(f"  [ERROR] Failed to process application {app_id}: {e}")
                failed += 1

    else:
        # Option 2: Process local JSON files
        if target_arg and target_arg not in ["--all", "--local", "--mongo"]:
            if target_arg.endswith(".json"):
                input_files = [Path(target_arg)]
            else:
                input_files = [INPUT_DIR / f"{target_arg}.json"]
        else:
            input_files = sorted(INPUT_DIR.glob("P*.json"))

        if not input_files:
            print(f"No JSON input files found in '{INPUT_DIR}'")
            return

        print(f"\nProcessing {len(input_files)} local document extraction file(s)...\n")

        for input_file in input_files:
            print(f"--> Processing {input_file.name}...")
            try:
                payload = load_clean_json(input_file)
                result = build_pipeline_result(payload)
                case_id = str(payload.get("_id", input_file.stem))

                output_file = OUTPUT_DIR / f"comparison_result_{case_id}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result.model_dump_json(indent=2))

                # Also attempt update to MongoDB if configured
                try:
                    update_comparison_result(case_id, result.model_dump())
                    print("    [DB] Synced to MongoDB.")
                except Exception:
                    pass

                print(f"    [OK] Status: {result.overall_status} | Risk: {result.risk_level} | Rec: {result.recommendation}")
                print(f"    Saved: {output_file.name}\n")
                successful += 1

            except Exception as e:
                print(f"    [ERROR] Failed to process {input_file.name}: {e}\n")
                failed += 1

    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print(f"Successful: {successful} | Failed: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
