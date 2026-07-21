"""
Generate a golden dataset by annotating messages with a large cloud model.

Uses minimax-m3 (428B) via the Ollama cloud API to produce independent
reference labels for evaluating the phi4-mini triage pipeline.
"""

import json
import logging
import time
import urllib.request
import urllib.error
from pathlib import Path

from rakshak_edge.utils.logger import setup_logger

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

setup_logger()
logger = logging.getLogger(__name__)

ANNOTATION_PROMPT = """You are an expert disaster response triage AI. Extract structured data from emergency messages.
Respond with ONLY a JSON object. No markdown, no backticks, no explanation.

## Fields
- **intent**: REQUEST (asking for help), OFFER (offering help), or OTHER (information/update)
- **hazards**: list of {type, severity} objects.
  - FLOODS: Flooding, rising water, inundation
  - STORM: Hurricanes, cyclones, severe weather, heavy rain, wind
  - EARTHQUAKE: Seismic activity, tremors, ground shaking
  - FIRE: Burning, wildfires, structure fires
  - COLD: Freezing temperatures, hypothermia risk, cold exposure
  - GAS_LEAK: Gas line damage, gas odor, explosion risk
  - STRUCTURAL_DAMAGE: Building collapse, damaged infrastructure, falling debris
  - POWER_OUTAGE: Electrical grid failure, no electricity, blackout
  - SECURITY_THREAT: Violence, looting, gangs, armed conflict, civil unrest
  - COMMUNICATION_FAILURE: No phone service, no internet, no radio, can't reach help
  - If intent is OFFER, hazards list must be empty.
  - IMPORTANT: Injuries, illness, hunger, thirst, and dying people are NOT hazards. They are consequences reflected in resource needs (MEDICAL_HELP, FOOD, WATER) with appropriate severity.
- **resources**: list of {type, severity} objects.
  - WATER: Drinking water, clean water, hydration
  - FOOD: Food, meals, nutrition, hunger relief
  - SHELTER: Housing, roof, protection from elements, tents
  - MEDICAL_HELP: Doctors, hospitals, medicine, first aid, ambulance
  - CLOTHING: Clothes, blankets, warm garments
  - TRANSPORT: Vehicles, transportation, evacuation, moving people/supplies
  - ELECTRICITY: Power, electrical grid, generators, batteries, lighting
  - SECURITY_PERSONNEL: Police, security guards, military, protection from violence
  - SEARCH_AND_RESCUE: Finding missing people, rescue operations, saving trapped people
  - HEATING: Warmth, heating fuel, firewood, staying warm
- **severity**: 1 (MILD), 2 (MODERATE), 3 (SEVERE), 4 (EXTREME)

## Rules
- severity is an integer 1-4, not a word.
- Empty arrays if none: [].
- OTHER messages still extract any hazards/resources mentioned.
- Only use the allowed types listed above.

## Examples

Message: "I was hit in the stomach. Need a doctor."
Output: {"intent": "REQUEST", "hazards": [], "resources": [{"type": "MEDICAL_HELP", "severity": 3}]}

Message: "Looking for my daughter, haven't heard from her since the earthquake."
Output: {"intent": "REQUEST", "hazards": [{"type": "EARTHQUAKE", "severity": 2}], "resources": [{"type": "SEARCH_AND_RESCUE", "severity": 3}]}

Message: "We are dying of hunger and thirst, please send help."
Output: {"intent": "REQUEST", "hazards": [], "resources": [{"type": "WATER", "severity": 4}, {"type": "FOOD", "severity": 4}]}

Message: "People are trapped under collapsed buildings after the earthquake."
Output: {"intent": "REQUEST", "hazards": [{"type": "EARTHQUAKE", "severity": 4}, {"type": "STRUCTURAL_DAMAGE", "severity": 4}], "resources": [{"type": "SEARCH_AND_RESCUE", "severity": 4}, {"type": "MEDICAL_HELP", "severity": 4}]}

## Output Format
{"intent": "REQUEST", "hazards": [{"type": "EARTHQUAKE", "severity": 4}], "resources": [{"type": "MEDICAL_HELP", "severity": 4}]}"""


def load_messages(split: str = "validation", limit: int = 50) -> list[dict]:
    """Load messages from a structured JSON file."""
    path = DATA_DIR / "structured" / f"disaster_response_messages_{split}.json"
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path) as f:
        messages = json.load(f)

    logger.info("Loaded %s messages from %s", len(messages), path.name)
    return messages[:limit]


def get_api_key() -> str | None:
    """Read OLLAMA_API_KEY from .env file."""
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("OLLAMA_API_KEY="):
            return line.split("=", 1)[1].strip("\"'")
    return None


def annotate_message(message: str, model: str = "minimax-m3:cloud") -> dict:
    """Send a message through the cloud model and return structured annotation.

    Uses the local Ollama endpoint (http://localhost:11434) which proxies
    to the cloud when the user is signed in via `ollama signin`.
    """
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": ANNOTATION_PROMPT},
            {"role": "user", "content": f"Message: {message}"},
        ],
        "stream": False,
        "format": "json",
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}")

    content = data["message"]["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Non-JSON response: %s", content[:200])
        parsed = {"intent": "OTHER", "hazards": [], "resources": []}

    return parsed


def process(
    split: str = "validation",
    limit: int = 50,
    model: str = "minimax-m3",
    output_name: str | None = None,
):
    """Process messages and save golden dataset."""
    messages = load_messages(split, limit)

    results = []
    errors = []
    start = time.time()

    for i, msg in enumerate(messages, 1):
        text = msg["input_text"]
        original_expected = msg.get("expected_output", {})

        try:
            logger.info("[%d/%d] %s", i, limit, text[:80])
            annotation = annotate_message(text, model)
        except Exception as e:
            logger.error("[%d/%d] Failed: %s", i, limit, e)
            errors.append({"index": i - 1, "message": text, "error": str(e)})
            continue

        results.append({
            "input_text": text,
            "reference": annotation,
            "original_label": original_expected,
        })

        if i < limit:
            time.sleep(0.5)

    elapsed = time.time() - start

    golden = {
        "model": model,
        "split": split,
        "count": len(results),
        "errors": len(errors),
        "time_seconds": round(elapsed, 2),
        "samples": results,
    }

    output_dir = DATA_DIR / "golden"
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_name is None:
        output_name = f"golden_{split}_{limit}.json"

    output_path = output_dir / output_name
    with open(output_path, "w") as f:
        json.dump(golden, f, indent=2, ensure_ascii=False)

    logger.info(
        "Done: %d annotated, %d errors in %.1fs → %s",
        len(results),
        len(errors),
        elapsed,
        output_path,
    )
    return results, errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate golden dataset")
    parser.add_argument(
        "--split", default="validation", help="Data split (test/validation/training)"
    )
    parser.add_argument("--limit", type=int, default=50, help="Number of messages")
    parser.add_argument(
        "--model", default="minimax-m3:cloud", help="Cloud model to use (add :cloud suffix)"
    )
    parser.add_argument("--output", help="Output filename (optional)")
    args = parser.parse_args()

    process(
        split=args.split,
        limit=args.limit,
        model=args.model,
        output_name=args.output,
    )
