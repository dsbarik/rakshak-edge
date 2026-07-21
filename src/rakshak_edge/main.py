import json
import logging
from pathlib import Path

from rakshak_edge.graph import graph
from rakshak_edge.schema import TriageOutput
from rakshak_edge.state import TriageState
from rakshak_edge.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = (
    ROOT_DIR / "data" / "structured" / "disaster_response_messages_training.json"
)


def triage(message: str) -> TriageOutput:
    initial: TriageState = {"message": message, "retry_count": 0}
    result = graph.invoke(initial)
    return result["output"]


if __name__ == "__main__":
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File not found: {DATA_PATH}")

    messages = json.loads(DATA_PATH.read_text())

    for msg in messages[:10]:
        output = triage(msg["input_text"])

        output_dict = {
            "intent": output.intent,
            "priority_level": output.priority_level.name,
            "hazards_identified": [h.name for h in output.hazards],
            "resources": [r.name for r in output.resources],
        }

        logger.info("Input: %s", msg["input_text"])
        logger.info("Output: %s\n\n", output_dict)
        # logger.info("Expected: %s\n\n", msg["expected_output"])
