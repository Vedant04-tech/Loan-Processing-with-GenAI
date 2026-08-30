import json
from pathlib import Path
from dotenv import load_dotenv
from app.pipeline import build_pipeline_result

load_dotenv()

INPUT_DIR = Path("extracted_data")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_clean_json(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if raw.startswith("//"):
        raw = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("//"))
    return json.loads(raw)


def main():
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
