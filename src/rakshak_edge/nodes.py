from rakshak_edge.llm import get_llm
from rakshak_edge.prompts import final_prompt, verify_prompt
from rakshak_edge.schema import ParsedMessage, Priority, TriageOutput
from rakshak_edge.state import TriageState

llm = get_llm()


async def parse_node(state: TriageState) -> dict:
    chain = final_prompt | llm.with_structured_output(ParsedMessage)
    response: ParsedMessage = await chain.ainvoke({"input_text": state["message"]})
    return {"parsed": response}


async def verify_node(state: TriageState) -> dict:
    parsed = state["parsed"]

    hazards_str = (
        ", ".join(f"{h.name} (severity={h.severity.value})" for h in parsed.hazards)
        or "none"
    )
    resources_str = (
        ", ".join(f"{r.name} (severity={r.severity.value})" for r in parsed.resources)
        or "none"
    )
    extracted = (
        f"Intent: {parsed.intent}\nHazards: {hazards_str}\nResources: {resources_str}"
    )

    verify_chain = verify_prompt | llm
    r = await verify_chain.ainvoke(
        {
            "message": state["message"],
            "extracted": extracted,
        }
    )
    text = r.content.strip()
    errors = (
        []
        if text == "NONE"
        else [line.strip() for line in text.split("\n") if line.strip()]
    )

    return {"verification_errors": errors}


def prioritize_node(state: TriageState) -> dict:
    parsed = state["parsed"]
    max_hazard_severity = max((h.severity.value for h in parsed.hazards), default=0)
    max_resource_severity = max((r.severity.value for r in parsed.resources), default=0)

    if parsed.intent == "OFFER":
        priority = Priority.LOW
    elif max_hazard_severity >= 3 or max_resource_severity >= 3:
        priority = Priority.CRITICAL
    elif parsed.intent == "REQUEST" and (parsed.hazards or parsed.resources):
        priority = Priority.HIGH
    else:
        priority = Priority.LOW

    output = TriageOutput(
        intent=parsed.intent,
        hazards=parsed.hazards,
        resources=parsed.resources,
        priority_level=priority,
    )
    return {"output": output}
