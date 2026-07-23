import asyncio
import json
import logging
from asyncio import Semaphore
from pathlib import Path

from rakshak_edge.pipeline import triage
from rakshak_edge.schema import TriageOutput
from rakshak_edge.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = ROOT_DIR / "data" / "golden" / "synthetic_messages_53.json"


def format_output(index: int, output: TriageOutput):
    return {
        "index": index,
        "intent": output.intent,
        "priority_level": output.priority_level.name,
        "hazards_identified": [h.name for h in output.hazards],
        "resources": [r.name for r in output.resources],
    }


async def triage_one(idx: int, msg: dict, semaphore: Semaphore):
    async with semaphore:
        output = await triage(msg["input_text"])
        return idx, msg, output


async def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File not found: {DATA_PATH}")

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("samples", [])[:10]
    semaphore = Semaphore(3)
    tasks = [triage_one(i, msg, semaphore) for i, msg in enumerate(messages)]

    for coroutine in asyncio.as_completed(tasks):
        # output = await triage(msg["input_text"])
        idx, msg, output = await coroutine
        output_dict = format_output(idx, output)

        logger.info("Input: %s", msg["input_text"])
        logger.info("Output: %s\n", output_dict)


if __name__ == "__main__":
    asyncio.run(main())
