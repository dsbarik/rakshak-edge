"""
Annotate synthetic disaster SMS messages using a cloud LLM.

Loads synthetic_messages_*.json, sends each through the cloud annotation
pipeline (same prompt as the triage pipeline), and saves the result as a
golden dataset for comparison.

Processes samples concurrently via asyncio.Semaphore for speed.

Usage:
    uv run python scripts/annotate_synthetic.py [--limit N] [--model minimax-m3:cloud] [--concurrency 4]
"""

import asyncio
import json
import logging
import time
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from rakshak_edge.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT_DIR / "data" / "golden"

DEFAULT_CONCURRENCY = 4

# ── Annotation prompt (mirrors prompts.py → keep in sync) ─────────────

ANNOTATION_PROMPT = """You are an expert disaster response triage AI. Extract structured data from emergency messages.

## Instructions
Analyze the message step by step, then extract the required fields.

### 1. Intent Classification
- **REQUEST**: Sender is asking for help, rescue, supplies, or assistance. An active life-threatening situation (flooding, fire, building collapse, trapped people, severe injury, etc.) is an implicit REQUEST even without "help" or "please" language.
- **OFFER**: Sender is offering to provide help, resources, or volunteer.
- **OTHER**: Purely informational updates, news reports, or casual conversation. Do NOT use OTHER for messages describing an active disaster or life-threatening situation.

### 2. Severity Levels (used for both hazards and resources)
- **1 (MILD)**: Mentioned but no immediate urgency
- **2 (MODERATE)**: Actively occurring but manageable
- **3 (SEVERE)**: Significant damage or urgent need
- **4 (EXTREME)**: Life-threatening, catastrophic

### 3. Hazard Extraction
Identify the external disaster or danger causing the situation. Hazards are the *cause*, not the consequence.
Allowed types:
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
Do NOT use types outside this list. If no hazard fits, return an empty list.

Important: Hunger, thirst, injury, illness, and dying people are NOT hazards. These are consequences that should be reflected in resource needs and their severity.

If intent is OFFER, hazards list must be empty.

### 4. Resource Extraction
Identify what is needed or offered. For each resource, assign severity (1-4) based on urgency.
Allowed types:
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
Do NOT use types outside this list. If no resource fits, return an empty list.

### Examples

Message: "I was hit in the stomach. Need a doctor."
Output: {{"intent": "REQUEST", "hazards": [], "resources": [{{"type": "MEDICAL_HELP", "severity": 3}}]}}

Message: "Looking for my daughter, haven't heard from her since the earthquake."
Output: {{"intent": "REQUEST", "hazards": [{{"type": "EARTHQUAKE", "severity": 2}}], "resources": [{{"type": "SEARCH_AND_RESCUE", "severity": 3}}]}}

Message: "We are dying of hunger and thirst, please send help."
Output: {{"intent": "REQUEST", "hazards": [], "resources": [{{"type": "WATER", "severity": 4}}, {{"type": "FOOD", "severity": 4}}]}}

Message: "People are trapped under collapsed buildings after the earthquake."
Output: {{"intent": "REQUEST", "hazards": [{{"type": "EARTHQUAKE", "severity": 4}}, {{"type": "STRUCTURAL_DAMAGE", "severity": 4}}], "resources": [{{"type": "SEARCH_AND_RESCUE", "severity": 4}}, {{"type": "MEDICAL_HELP", "severity": 4}}]}}

### Output Format
Respond with ONLY a JSON object. No markdown, no backticks, no explanation.

Rules:
- severity is an integer 1-4, not a word
- empty arrays if no hazards or resources: []
- OTHER messages still extract any hazards/resources mentioned
- Respond with NOTHING except the JSON object"""

# ── Prompt template (same pattern as nodes.py) ──────────────────────

ANNOTATION_CHAIN = ChatPromptTemplate.from_messages(
    [
        ("system", ANNOTATION_PROMPT),
        ("user", "Message: {message}"),
    ]
)


# ── File services ────────────────────────────────────────────────────


def find_latest_synthetic(directory: Path = GOLDEN_DIR) -> Path:
    """Find the latest synthetic_messages_*.json in the golden dir."""
    candidates = sorted(directory.glob("synthetic_messages_*.json"))
    if not candidates:
        raise FileNotFoundError(
            "No synthetic_messages_*.json found in golden/. Run generate_synthetic.py first."
        )
    return candidates[-1]


def load_samples(path: Path) -> list[dict]:
    """Load synthetic message samples from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data["samples"]


# ── Annotation functions ─────────────────────────────────────────────


def parse_annotation(raw: str) -> dict:
    """Parse the model's raw response into a structured annotation dict."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Non-JSON response: %s", raw[:200])
        parsed = {"intent": "OTHER", "hazards": [], "resources": []}
    return parsed


async def annotate_one(llm: ChatOllama, message: str, sem: asyncio.Semaphore) -> dict:
    """Annotate a single message. Returns the structured annotation dict."""
    async with sem:
        chain = ANNOTATION_CHAIN | llm
        response = await chain.ainvoke({"message": message})
    return parse_annotation(response.content)


async def annotate_batch(
    llm: ChatOllama,
    samples: list[dict],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[list[dict], list[dict]]:
    """Annotate a batch of messages concurrently. Returns (results, errors)."""
    sem = asyncio.Semaphore(concurrency)
    gathered: list[tuple[int, dict | None]] = [None] * len(samples)
    errors: list[dict] = []
    start = time.time()

    async def annotate_one_with_index(sample: dict, idx: int) -> None:
        text = sample["input_text"]
        hints = sample.get("reference_hints", {})
        try:
            logger.info("[%d/%d] %s", idx, len(samples), text[:80])
            annotation = await annotate_one(llm, text, sem)
            gathered[idx - 1] = (
                idx,
                {
                    "input_text": text,
                    "reference": annotation,
                    "reference_hints": hints,
                },
            )
        except Exception as e:
            logger.error("[%d/%d] Failed: %s", idx, len(samples), e)
            gathered[idx - 1] = None
            errors.append({"index": idx - 1, "message": text, "error": str(e)})

    tasks = [annotate_one_with_index(s, i) for i, s in enumerate(samples, 1)]
    await asyncio.gather(*tasks)

    # Reconstruct in input order
    results = [entry for entry in gathered if entry is not None]
    results.sort(key=lambda x: x[0])
    results = [r for _, r in results]

    elapsed = time.time() - start
    logger.info(
        "Finished: %d annotated, %d errors in %.1fs", len(results), len(errors), elapsed
    )
    return results, errors


# ── Golden dataset formatting & IO ───────────────────────────────────


def to_golden_json(
    results: list[dict], errors: list[dict], model: str = "minimax-m3:cloud"
) -> dict:
    """Convert annotation results into golden dataset format (pure)."""
    return {
        "model": model,
        "split": "synthetic_validation",
        "count": len(results),
        "errors": len(errors),
        "source": "Synthetic messages from scripts/generate_synthetic.py",
        "samples": results,
    }


def save_golden(data: dict, directory: Path = GOLDEN_DIR) -> Path:
    """Write golden dataset JSON to disk. Returns the path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"golden_synthetic_{data['count']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d annotated samples to %s", data["count"], path)
    return path


# ── LLM factory (delegates to project's shared get_llm) ─────────────


def create_llm(model: str, temperature: float = 0.0) -> ChatOllama:
    """Create a ChatOllama instance. Delegates to the project's shared get_llm()."""
    from rakshak_edge.llm import get_llm

    return get_llm(model=model, temperature=temperature)


# ── Entry point ─────────────────────────────────────────────────────


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate synthetic messages concurrently"
    )
    parser.add_argument(
        "--limit", type=int, help="Number of messages to annotate (default: all)"
    )
    parser.add_argument(
        "--model",
        default="minimax-m3:cloud",
        help="Ollama model (default: minimax-m3:cloud)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="Concurrent API calls (default: 4)",
    )
    args = parser.parse_args()

    llm = create_llm(args.model)
    synthetic_path = find_latest_synthetic()
    samples = load_samples(synthetic_path)

    if args.limit:
        samples = samples[: args.limit]

    print(f"Starting annotation of {len(samples)} messages with {args.model}...")
    print(
        f"Concurrency: {args.concurrency} — this will be ~{args.concurrency}x faster than sequential."
    )
    print("Make sure you are signed in: ollama signin")

    results, errors = await annotate_batch(llm, samples, concurrency=args.concurrency)
    golden = to_golden_json(results, errors, model=args.model)
    path = save_golden(golden)
    print(f"Done: {len(results)} annotated, {len(errors)} errors → {path}")


if __name__ == "__main__":
    asyncio.run(main())
