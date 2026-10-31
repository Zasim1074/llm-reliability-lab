import json

import httpx
import pytest

from app.providers import OpenAIProvider, ProviderError, ProviderInvalidResponse, ProviderRateLimited, ProviderTimeout


def _provider(handler, dimensions=2):
    client = httpx.Client(
        base_url="https://api.openai.com/v1/",
        transport=httpx.MockTransport(handler),
    )
    provider = OpenAIProvider(
        api_key="test-only",
        base_url="https://api.openai.com/v1",
        chat_model="test-chat",
        embedding_model="test-embedding",
        embedding_dimensions=dimensions,
        timeout_seconds=1,
        client=client,
    )
    return provider, client


def test_openai_embedding_uses_configured_model_and_checks_vector_dimensions():
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path.endswith("/embeddings")
        assert payload["model"] == "test-embedding"
        assert payload["dimensions"] == 2
        return httpx.Response(200, json={"data": [{"embedding": [0.2, 0.8]}]})

    provider, client = _provider(handler)
    try:
        assert provider.embed("phrase") == [0.2, 0.8]
        assert provider.model_id == "test-embedding:2"
    finally:
        provider.close()
        client.close()


def test_openai_embedding_returns_usage_from_provider_response():
    def handler(_request):
        return httpx.Response(200, json={"data": [{"embedding": [0.2, 0.8]}], "usage": {"prompt_tokens": 9, "total_tokens": 9}})

    provider, client = _provider(handler)
    try:
        vector, tokens = provider.embed_with_usage("phrase")
        assert vector == [0.2, 0.8]
        assert tokens == 9
    finally:
        provider.close()
        client.close()


def test_openai_judge_validates_structured_scores_and_captures_usage():
    content = {"relevance": 80, "correctness": 70, "completeness": 60,
               "instruction_following": 90, "groundedness": 50, "rationale": "Based on supplied reference."}

    def handler(request):
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
                                       "usage": {"prompt_tokens": 11, "completion_tokens": 7}})

    provider, client = _provider(handler)
    try:
        result = provider.judge_response("question", "candidate", "reference")
        assert result["overall"] == 70
        assert result["usage"] == {"input_tokens": 11, "output_tokens": 7}
    finally:
        provider.close()
        client.close()


def test_openai_provider_timeout_and_http_failure_are_safe_errors():
    def timeout_handler(_request):
        raise httpx.ReadTimeout("private request details")

    provider, client = _provider(timeout_handler)
    try:
        with pytest.raises(ProviderTimeout, match="timed out"):
            provider.embed("sensitive text")
    finally:
        provider.close()
        client.close()

    provider, client = _provider(lambda request: httpx.Response(503, json={"error": {"message": "private detail"}}))
    try:
        with pytest.raises(ProviderError, match="unavailable") as error:
            provider.embed("sensitive text")
        assert "private detail" not in str(error.value)
    finally:
        provider.close()
        client.close()


def test_openai_provider_rejects_invalid_structured_output():
    provider, client = _provider(lambda request: httpx.Response(200, json={"data": [{"embedding": [float("nan"), 0.1]}]}))
    try:
        with pytest.raises(ProviderInvalidResponse):
            provider.embed("query")
    finally:
        provider.close()
        client.close()


def test_openai_provider_exposes_safe_rate_limit_retry_after():
    provider, client = _provider(lambda request: httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "secret"}))
    try:
        with pytest.raises(ProviderRateLimited) as limited:
            provider.embed("private input")
        assert limited.value.retry_after_seconds == 7
        assert "secret" not in str(limited.value)
    finally:
        provider.close()
        client.close()
