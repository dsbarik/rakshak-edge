import enum
from typing import List, Literal

from pydantic import BaseModel, Field, AliasChoices


class Priority(enum.IntEnum):
    LOW = 1
    HIGH = 2
    CRITICAL = 3


class Severity(enum.IntEnum):
    MILD = 1
    MODERATE = 2
    SEVERE = 3
    EXTREME = 4


class Hazard(BaseModel):
    # ponytail: accept type/hazard/name — Gemma uses different field names per message
    name: str = Field(
        serialization_alias="type",
        validation_alias=AliasChoices("type", "hazard", "name"),
    )
    severity: Severity


class Resource(BaseModel):
    name: str = Field(
        serialization_alias="type",
        validation_alias=AliasChoices("type", "resource", "name"),
    )
    severity: Severity


class ParsedMessage(BaseModel):
    intent: Literal["REQUEST", "OFFER", "OTHER"]
    hazards: List[Hazard]
    resources: List[Resource]


class TriageOutput(ParsedMessage):
    priority_level: Priority
