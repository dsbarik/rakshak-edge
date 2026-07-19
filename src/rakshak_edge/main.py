import json
import logging
from pathlib import Path

from rakshak_edge.llm import get_llm
from rakshak_edge.prompts import final_prompt
from rakshak_edge.schema import TriageOutput
from rakshak_edge.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_PATH = DATA_DIR / "structured" / "disaster_response_messages_training.json"


llm = get_llm()

structured_llm = llm.with_structured_output(schema=TriageOutput)


if not DATA_PATH.exists():
    logger.error(f"File does not exist at: {DATA_PATH.absolute()}")
    raise FileNotFoundError(f"Error: Filde does not exist at: {DATA_PATH.absolute()}")

with open(DATA_PATH, "r") as file:
    messages = json.load(file)

input_text = messages[0]["input_text"]

chain = final_prompt | structured_llm

response: TriageOutput = chain.invoke({"input_text": input_text})  # type: ignore

print()
logger.info(f"{input_text=}")
logger.info("Actual Output:")
logger.info(response.model_dump())
logger.info("Expected Output:")
logger.info(messages[0]["expected_output"])
