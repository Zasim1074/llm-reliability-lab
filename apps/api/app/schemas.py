from typing import Literal, Optional

import math

from pydantic import BaseModel, Field, model_validator


class CacheLookupRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    namespace: str = Field(default="default", min_length=1, max_length=100)


class CacheStoreRequest(CacheLookupRequest):
    response: str = Field(min_length=1, max_length=20000)
    ttl_seconds: Optional[int] = Field(default=None, ge=60, le=2592000)


class EvaluationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    candidate: str = Field(min_length=1, max_length=20000)
    alternative_candidate: Optional[str] = Field(default=None, max_length=20000)
    reference: Optional[str] = Field(default=None, max_length=20000)
    criteria_weights: dict[Literal["relevance", "correctness", "completeness", "instruction_following", "groundedness"], float] = Field(default_factory=dict, max_length=5)

    @model_validator(mode="after")
    def validate_criteria_weights(self):
        if any(not math.isfinite(weight) or weight < 0 or weight > 10 for weight in self.criteria_weights.values()):
            raise ValueError("Criterion weights must be finite numbers from 0 to 10")
        if self.criteria_weights and sum(self.criteria_weights.values()) <= 0:
            raise ValueError("At least one criterion weight must be greater than zero")
        return self


class SecurityCase(BaseModel):
    input: str = Field(min_length=1, max_length=4000)
    kind: Literal["benign", "direct", "indirect", "unauthorized_action", "data_exfiltration", "jailbreak", "other"] = "direct"
    malicious: bool = True


class SecurityRunRequest(BaseModel):
    name: str = Field(default="Prompt injection baseline", max_length=200)
    cases: list[SecurityCase] = Field(min_length=1, max_length=100)
    mitigation: bool = True


class ExperimentResponse(BaseModel):
    id: str
    type: str
    name: str
    status: str
    configuration: dict
    dataset_ref: Optional[str]
    metrics: dict
    results: dict
    error: Optional[str]
    started_at: str
    completed_at: str
