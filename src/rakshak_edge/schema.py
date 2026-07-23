import enum
from typing import List, Literal

from pydantic import AliasChoices, BaseModel, Field


class Priority(enum.Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Severity(enum.IntEnum):
    MILD = 1
    MODERATE = 2
    SEVERE = 3
    EXTREME = 4


class Hazard(BaseModel):
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
