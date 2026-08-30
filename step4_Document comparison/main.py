
import json
from pathlib import Path

from dotenv import load_dotenv

from app.pipeline import build_pipeline_result


# ------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ------------------------------------

load_dotenv()


# ------------------------------------
# INPUT / OUTPUT DIRECTORIES
# ------------------------------------

INPUT_DIR = Path("extracted_data")
OUTPUT_DIR = Path("output")

# Create output folder if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------
# FIND ALL JSON FILES
# ------------------------------------

input_files = sorted(
    INPUT_DIR.glob("P*.json")
)

print("=" * 60)
print(f"Found {len(input_files)} JSON files.")
print("=" * 60)


# ------------------------------------
# PROCESS EACH JSON FILE
# ------------------------------------

successful = 0
failed = 0

for input_file in input_files:

    print("\n" + "=" * 60)
    print(f"Processing: {input_file.name}")
    print("=" * 60)

    try:

        # ------------------------------------
        # READ INPUT
        # ------------------------------------

        print(f"Reading file: {input_file}")

        with open(
            input_file,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read()

        print("First 200 characters:")
        print(repr(content[:200]))

        # Parse JSON
        payload = json.loads(content)


        # ------------------------------------
        # RUN PIPELINE
        # ------------------------------------

        result = build_pipeline_result(
            payload
        )


        # ------------------------------------
        # CREATE OUTPUT FILE NAME
        # ------------------------------------

        case_id = payload.get(
            "_id",
            input_file.stem
        )

        output_file = (
            OUTPUT_DIR /
            f"comparison_result_{case_id}.json"
        )


        # ------------------------------------
        # WRITE RESULT
        # ------------------------------------

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                result.model_dump_json(
                    indent=2
                )
            )


        # ------------------------------------
        # DISPLAY RESULT
        # ------------------------------------

        print("\n✓ Comparison pipeline completed.")

        print(
            f"Result saved to: {output_file}"
        )

        print(
            f"Overall Status: "
            f"{result.overall_status}"
        )

        print(
            f"Risk Level: "
            f"{result.risk_level}"
        )

        print(
            f"Recommendation: "
            f"{result.recommendation}"
        )

        successful += 1


    except Exception as e:

        # ------------------------------------
        # HANDLE ERROR
        # ------------------------------------

        print(
            f"\n✗ ERROR processing "
            f"{input_file.name}"
        )

        print(f"Error: {e}")

        failed += 1




print("=" * 60)
