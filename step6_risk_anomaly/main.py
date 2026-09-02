import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import importlib

step4_module = importlib.import_module("step4_Document comparison.app.pipeline")
build_step4_result = getattr(step4_module, "build_pipeline_result")
from step5_calculation.app.pipeline import build_step5_result
from step6_risk_anomaly.app.pipeline import build_step6_result


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
    print("STEP 6: RISK SCORING, ANOMALY CLASSIFICATION & ROUTING RUNNER")
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
            case_id = payload.get("_id", input_file.stem)

            # Step 4 execution
            step4_res = build_step4_result(payload)

            # Step 5 execution
            step5_res = build_step5_result(payload)

            # Step 6 execution
            step6_res = build_step6_result(
                application_data=payload,
                step5_result=step5_res,
                step4_result=step4_res,
            )

            output_file = OUTPUT_DIR / f"risk_result_{case_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(step6_res.model_dump_json(indent=2))

            r = step6_res.risk_result
            print(f"    [OK] Routing:        {r.routing_color.upper()} ({r.recommendation})")
            print(f"         Score:          {r.score}/100 ({r.grade}) | Human Sign-off: {r.requires_human_signoff}")
            print(f"         Discrepancies:  {len(step6_res.discrepancies)} detected")
            print(f"         Reason:         {r.routing_reason}")
            print(f"         Saved: {output_file.name}\n")
            successful += 1

        except Exception as e:
            print(f"    [ERROR] Failed to process {input_file.name}: {e}\n")
            failed += 1

    print(f"Completed Step 6: {successful} processed successfully, {failed} failed.")
    print("=" * 65)


if __name__ == "__main__":
    main()
