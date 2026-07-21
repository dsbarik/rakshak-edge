import logging

from langgraph.graph import StateGraph, START, END

from rakshak_edge.config import settings
from rakshak_edge.nodes import parse_node, verify_node, prioritize_node
from rakshak_edge.state import TriageState

logger = logging.getLogger(__name__)

MAX_RETRIES = settings["nodes"]["max_retries"]


def increment_retry(state: TriageState) -> dict:
    return {"retry_count": state["retry_count"] + 1}


def route_verify(state: TriageState) -> str:
    errors = state.get("verification_errors", [])
    if errors:
        if state["retry_count"] < MAX_RETRIES:
            return "increment"
        logger.warning("Retries exhausted: %s", errors)
    return "prioritize"


builder = StateGraph(TriageState)
builder.add_node("parse", parse_node)
builder.add_node("verify", verify_node)
builder.add_node("prioritize", prioritize_node)
builder.add_node("increment", increment_retry)

builder.add_edge(START, "parse")
builder.add_edge("parse", "verify")
builder.add_conditional_edges(
    "verify",
    route_verify,
    {"increment": "increment", "prioritize": "prioritize"},
)
builder.add_edge("increment", "parse")
builder.add_edge("prioritize", END)

graph = builder.compile()
