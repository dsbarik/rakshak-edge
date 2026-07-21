from typing import List, NotRequired, TypedDict

from rakshak_edge.schema import ParsedMessage, TriageOutput


class TriageState(TypedDict):
    message: str
    parsed: NotRequired[ParsedMessage]
    output: NotRequired[TriageOutput]
    verification_errors: NotRequired[List[str]]
    retry_count: int
