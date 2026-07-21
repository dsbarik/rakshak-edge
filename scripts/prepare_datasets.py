import json
import logging
import time
from pathlib import Path
from typing import Union

import pandas as pd

from rakshak_edge.utils.logger import setup_logger

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


setup_logger()
logger = logging.getLogger(__name__)


def process_file(
    csv_path: Union[Path, str], output_json_path: Union[Path, str, None] = None
):
    start_time = time.time()

    # 1. Path Normalization & Pre-checks
    if isinstance(csv_path, str):
        csv_path = Path(csv_path)

    if not csv_path.exists():
        logger.error(
            f"Execution halted: Input file does not exist at {csv_path.absolute()}"
        )
        raise FileNotFoundError(f"Error: File does not exist at: {csv_path.absolute()}")

    if output_json_path is None:
        output_json_path = csv_path.with_suffix(".jsonl")
    elif isinstance(output_json_path, str):
        output_json_path = Path(output_json_path)

    logger.info(f"Starting processing for target file: {csv_path.name}")

    # 2. Data Ingestion & Filtering Metrics
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        total_rows = len(df)
        logger.info(f"Successfully loaded CSV. Total initial records: {total_rows}")
    except Exception as e:
        logger.error(f"Failed to read CSV file {csv_path.name}: {str(e)}")
        raise

    df_related = df[df["related"] == 1]
    filtered_rows = len(df_related)
    dropped_rows = total_rows - filtered_rows

    logger.info(
        f"Filtered dataset: Retained {filtered_rows} rows where 'related == 1'. "
        f"Dropped {dropped_rows} non-disaster or ambiguous rows."
    )

    formatted_data = []

    # 3. Processing Loop
    for index, row in df_related.iterrows():
        raw_msg = row.get("message")

        # Guard clause against empty/NaN messages in the dataset
        if pd.isna(raw_msg) or str(raw_msg).strip() == "":
            logger.debug(
                f"Row index {index}: Skipped due to missing or empty message text."
            )
            continue

        hazards = []
        resources = []

        intent = "OTHER"
        if row.get("offer") == 1:
            intent = "OFFER"
        elif row.get("request") == 1:
            intent = "REQUEST"

        # Hazard Mapping (core + expanded)
        hazard_map = {
            "floods": "FLOODS",
            "storm": "STORM",
            "earthquake": "EARTHQUAKE",
            "fire": "FIRE",
            "cold": "COLD",
            "security": "SECURITY_THREAT",
            "buildings": "STRUCTURAL_DAMAGE",
            "electricity": "POWER_OUTAGE",
        }
        for col, label in hazard_map.items():
            if row.get(col) == 1:
                hazards.append(label)

        # Resource Mapping (core + expanded)
        resource_map = {
            "water": "WATER",
            "food": "FOOD",
            "shelter": "SHELTER",
            "medical_help": "MEDICAL_HELP",
            "clothing": "CLOTHING",
            "search_and_rescue": "SEARCH_AND_RESCUE",
            "transport": "TRANSPORT",
            "money": "OTHER",
            "tools": "OTHER",
        }
        for col, label in resource_map.items():
            if row.get(col) == 1:
                resources.append(label)

        # Priority Derivation
        priority = "LOW"
        if row.get("search_and_rescue") == 1 or row.get("medical_help") == 1:
            priority = "CRITICAL"
        elif len(hazards) > 0 or len(resources) > 0:
            priority = "HIGH"

        structured_record = {
            "input_text": str(raw_msg),
            "expected_output": {
                "intent": intent,
                "priority_level": priority,
                "hazards_identified": hazards,
                "resources": resources,
            },
        }
        formatted_data.append(structured_record)

    # 4. File Export & Performance Analytics
    logger.info(
        f"Compilation complete. Preparing to write {len(formatted_data)} records to disk."
    )

    try:
        # Ensure output directory exists before writing
        output_json_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(formatted_data, f, indent=4, ensure_ascii=False)

        elapsed_time = time.time() - start_time
        logger.info(
            f"Success: Wrote processed dataset cleanly into {output_json_path.absolute()} "
            f"| Time taken: {elapsed_time:.2f} seconds."
        )
    except IOError as e:
        logger.error(
            f"File I/O Error writing to destination {output_json_path}: {str(e)}"
        )
        raise


if __name__ == "__main__":
    csv_file_paths = list((DATA_DIR / "raw").glob("*.csv"))

    if not csv_file_paths:
        logger.warning(f"No CSV files found in {DATA_DIR.absolute()}")

    for p in csv_file_paths:
        output_json_path = DATA_DIR / "structured" / f"{p.stem}.json"

        logger.info(f"Starting processing for: {p.name}")
        process_file(csv_path=p, output_json_path=output_json_path)
        logger.info(f"Successfully saved to: {output_json_path.name}\n")
