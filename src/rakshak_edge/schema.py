from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


class TriageOutput(BaseModel):
    intent: Literal["OFFER", "REQUEST", "OTHER"] = Field(
        description="The primary purpose of the message. 'REQUEST' for seeking help, 'OFFER' for providing help, or 'OTHER'."
    )
    priority_level: Literal["CRITICAL", "HIGH", "LOW"] = Field(
        description="Urgency level. Use 'CRITICAL' for search/rescue or medical help. Use 'HIGH' if any hazards or basic resources are mentioned. Default to 'LOW'."
    )
    hazards_identified: List[
        Literal["FLOODS", "STORM", "EARTHQUAKE", "FIRE", "COLD"]
    ] = Field(
        default_factory=list,
        description="Identify any hazards mentioned in the text. Must exactly match the provided categories. Leave empty if none.",
    )
    resources: List[Literal["WATER", "FOOD", "SHELTER", "MEDICAL_HELP", "CLOTHING"]] = (
        Field(
            default_factory=list,
            description="Identify specific resources mentioned. Must exactly match the provided categories. Leave empty if none.",
        )
    )

    @model_validator(mode="after")
    def enforce_intent_logic(self) -> "TriageOutput":

        if self.intent == "OFFER":
            self.hazards_identified = []

        return self
