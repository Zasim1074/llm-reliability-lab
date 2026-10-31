from pydantic import BaseModel, Field


class CacheLookupRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    namespace: str = Field(default="default", min_length=1, max_length=100)


class CacheStoreRequest(CacheLookupRequest):
    response: str = Field(min_length=1, max_length=20000)
    ttl_seconds: int | None = Field(default=None, ge=60, le=2592000)


class EvaluationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    candidate: str = Field(min_length=1, max_length=20000)
    reference: str | None = Field(default=None, max_length=20000)


class SecurityCase(BaseModel):
    input: str = Field(min_length=1, max_length=4000)
    kind: str = "direct"
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
    dataset_ref: str | None
    metrics: dict
    results: dict
    error: str | None
    started_at: str
    completed_at: str
