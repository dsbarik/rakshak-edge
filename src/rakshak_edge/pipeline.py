from rakshak_edge.graph import graph
from rakshak_edge.schema import TriageOutput
from rakshak_edge.state import TriageState


async def triage(message: str) -> TriageOutput:
    initial: TriageState = {"message": message, "retry_count": 0}
    result = await graph.ainvoke(initial)
    return result["output"]
