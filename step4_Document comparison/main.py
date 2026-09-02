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
    target_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if target_arg and target_arg != "--all":
        if target_arg.endswith(".json"):
            input_files = [Path(target_arg)]
        else:
            input_files = [INPUT_DIR / f"{target_arg}.json"]
    else:
        input_files = sorted(INPUT_DIR.glob("P*.json"))

    if not input_files:
        print(f"No JSON input files found in '{INPUT_DIR}'")
        return

    print(f"Found {len(input_files)} document extraction files to compare.\n")

    successful, failed = 0, 0

    for input_file in input_files:
        print(f"--> Processing {input_file.name}...")
        try:
            payload = load_clean_json(input_file)
            result = build_pipeline_result(payload)
            case_id = payload.get("_id", input_file.stem)

            output_file = OUTPUT_DIR / f"comparison_result_{case_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))

            print(f"    [OK] Status: {result.overall_status} | Risk: {result.risk_level} | Rec: {result.recommendation}")
            print(f"    Saved: {output_file}\n")
            successful += 1

        except Exception as e:
            print(f"    [ERROR] Failed to process {input_file.name}: {e}\n")
            failed += 1

    print(f"Completed: {successful} processed successfully, {failed} failed.")


if __name__ == "__main__":
    main()
