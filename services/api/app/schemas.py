from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ParamValue(BaseModel):
    value: float
    unit: str = Field(min_length=1, max_length=20)


class ChangeRequest(BaseModel):
    """Either a parameter change (parameter + proposed_value + unit) or a part swap (replacement_id)."""
    target_entity_id: str = Field(min_length=1, max_length=100)
    parameter: Optional[str] = Field(default=None, max_length=100)
    proposed_value: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=20)
    replacement_id: Optional[str] = Field(default=None, max_length=100)
    parameter_overrides: dict[str, ParamValue] = Field(default_factory=dict)
    change_description: Optional[str] = Field(default=None, max_length=2000)
    reason: Optional[str] = Field(default=None, max_length=1000)
    kind: Literal["analysis", "whatif"] = "analysis"

    @model_validator(mode="after")
    def _one_kind_of_change(self):
        has_param = self.parameter is not None and self.proposed_value is not None and bool(self.unit)
        if not has_param and not self.replacement_id:
            raise ValueError("Give either parameter, proposed_value and unit, or a replacement_id.")
        return self


class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected", "needs_revision"]
    reviewer: str = Field(min_length=1, max_length=120)
    comments: str = Field(default="", max_length=3000)


class ParameterSupply(BaseModel):
    entity_id: str = Field(min_length=1, max_length=100)
    parameter: str = Field(min_length=1, max_length=100)
    value: float
    unit: str = Field(min_length=1, max_length=20)
    source_note: str = Field(default="", max_length=500)
    author: str = Field(default="", max_length=120)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    analysis_id: Optional[str] = None
    context_entity_id: Optional[str] = None
    history: list[ChatTurn] = Field(default_factory=list)
