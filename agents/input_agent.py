import json
import os
import uuid
from datetime import datetime

from langchain_core.runnables import RunnableLambda


def _validate(inputs: dict) -> dict:
    input_path = inputs["input_path"]
    pipeline_id = inputs.get(
        "pipeline_id",
        f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
    )

    print(f"[input-agent] Reading: {input_path}")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    validation_errors = []
    if not isinstance(data, (dict, list)):
        validation_errors.append("Root element must be object or array")
    if isinstance(data, list) and len(data) == 0:
        validation_errors.append("Input array is empty")

    if validation_errors:
        print(f"[input-agent] Warnings: {validation_errors}")
    else:
        print("[input-agent] Validation passed")

    return {
        "pipeline_id": pipeline_id,
        "source_file": os.path.basename(input_path),
        "validated_input": data,
        "validation_errors": validation_errors,
    }


input_agent = RunnableLambda(_validate)
