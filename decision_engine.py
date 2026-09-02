import os
import sys
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

from pipeline import run_pipeline, PipelineResult
from main import main as run_cli

# Alias for backward compatibility
run_decision_pipeline = run_pipeline

__all__ = [
    "run_decision_pipeline",
    "run_pipeline",
    "PipelineResult",
]

if __name__ == "__main__":
    run_cli()
