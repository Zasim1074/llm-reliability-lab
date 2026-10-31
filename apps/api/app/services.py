import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CacheEntry, Experiment
from app.providers import EmbeddingProvider, JudgeProvider


def normalize(text: str) -> str:
    return " ".join(text.lower().split()).strip()


def cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return -1.0
    if any(not math.isfinite(value) for value in left + right):
        return -1.0
    return sum(a * b for a, b in zip(left, right))


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def create_experiment(db: Session, kind: str, name: str, config: dict, metrics: dict, results: dict, dataset_ref: Optional[str] = None) -> Experiment:
    record = Experiment(type=kind, name=name, configuration=config, metrics=metrics, results=results, dataset_ref=dataset_ref)
    db.add(record)
    db.flush()
    return record


def cache_lookup(db: Session, query: str, namespace: str, embedding_provider: Optional[EmbeddingProvider] = None) -> dict:
    started = time.perf_counter()
    norm_query = normalize(query)
    if not norm_query:
        return {"hit": False, "match_type": None, "score": 0, "response": None, "latency_ms": 0}
    now = datetime.now(timezone.utc)
    entries = db.scalars(
        select(CacheEntry)
        .where(CacheEntry.namespace == namespace, CacheEntry.invalidated.is_(False), CacheEntry.expires_at > now)
        .order_by(CacheEntry.created_at.desc())
        .limit(settings.cache_scan_limit)
    ).all()
    entries = [entry for entry in entries if _as_utc(entry.expires_at) > now]
    exact = next((entry for entry in reversed(entries) if entry.normalized_query == norm_query), None)
    if exact:
        match, score = exact, 1.0
        match_type = "exact"
    elif embedding_provider and any(entry.embedding is not None and entry.embedding_model == embedding_provider.model_id for entry in entries):
        query_vec = embedding_provider.embed(norm_query)
        scored = [(cosine(query_vec, entry.embedding), entry) for entry in entries
                  if entry.embedding is not None and entry.embedding_model == embedding_provider.model_id]
        score, match = max(scored, default=(-1.0, None), key=lambda item: item[0])
        match_type = "similarity"
        if match is None or score < settings.cache_similarity_threshold:
            match = None
    else:
        score, match, match_type = 0.0, None, None
    return {
        "hit": match is not None,
        "match_type": match_type if match else None,
        "score": round(score, 4) if match else max(0, round(score, 4)),
        "response": match.response if match else None,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def cache_store(db: Session, query: str, response: str, namespace: str, ttl_seconds: Optional[int] = None,
                embedding_provider: Optional[EmbeddingProvider] = None) -> CacheEntry:
    if not normalize(query) or not response.strip():
        raise ValueError("Query and response must not be empty")
    ttl = ttl_seconds or settings.cache_ttl_seconds
    vector = embedding_provider.embed(query) if embedding_provider else None
    record = CacheEntry(namespace=namespace, query=query, normalized_query=normalize(query), response=response,
                        embedding=vector, embedding_model=embedding_provider.model_id if embedding_provider else None,
                        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl))
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def evaluate(prompt: str, candidate: str, reference: Optional[str], judge_provider: Optional[JudgeProvider] = None) -> dict:
    if judge_provider:
        return judge_provider.judge_response(prompt, candidate, reference)
    candidate_words = set(re.findall(r"[a-z0-9]+", candidate.lower()))
    prompt_words = set(re.findall(r"[a-z0-9]+", prompt.lower()))
    reference_words = set(re.findall(r"[a-z0-9]+", (reference or "").lower()))
    relevance = len(candidate_words & prompt_words) / max(1, len(prompt_words))
    groundedness = len(candidate_words & reference_words) / max(1, len(reference_words)) if reference else 0.5
    completeness = min(1.0, len(candidate_words) / max(10, len(prompt_words) * 2))
    instruction = 1.0 if candidate.strip() else 0.0
    correctness = groundedness if reference else 0.5
    scores = {"relevance": relevance, "correctness": correctness, "completeness": completeness,
              "instruction_following": instruction, "groundedness": groundedness}
    return {"scores": {key: round(value * 100, 1) for key, value in scores.items()},
            "overall": round(sum(scores.values()) / len(scores) * 100, 1),
            "judge": "deterministic_heuristic", "limitations": "Lexical demo rubric; not an LLM judgment or factuality guarantee."}


def compare_pair(prompt: str, candidate_a: str, candidate_b: str,
                 judge_provider: Optional[JudgeProvider] = None) -> dict:
    if judge_provider:
        return judge_provider.compare_pair(prompt, candidate_a, candidate_b)
    score_a = evaluate(prompt, candidate_a, None)
    score_b = evaluate(prompt, candidate_b, None)
    if score_a["overall"] == score_b["overall"]:
        winner = "tie"
    else:
        winner = "A" if score_a["overall"] > score_b["overall"] else "B"
    return {"winner": winner, "confidence": 100 if winner != "tie" else 0,
            "scores": {"A": score_a["overall"], "B": score_b["overall"]},
            "judge": "deterministic_heuristic",
            "rationale": "Rule-based lexical scores were compared; this is not an LLM judgment."}


INJECTION_PATTERNS = [r"ignore (all )?(previous|prior|system) instructions", r"reveal (the )?(system prompt|hidden instructions)",
                      r"override (the )?(system|safety) instructions", r"send .* (password|secret|api key)",
                      r"run (this|the) (command|code)"]


def detect_injection(text: str) -> bool:
    return any(re.search(pattern, text.lower()) for pattern in INJECTION_PATTERNS)


def run_security(cases: list[dict], mitigation: bool) -> dict:
    results, blocked, successful, fp, fn = [], 0, 0, 0, 0
    for index, case in enumerate(cases, 1):
        detected = detect_injection(case["input"])
        is_blocked = detected and mitigation
        if case["malicious"] and is_blocked: blocked += 1
        if case["malicious"] and not is_blocked: successful += 1
        if not case["malicious"] and detected: fp += 1
        if case["malicious"] and not detected: fn += 1
        results.append({"case": index, "kind": case["kind"], "detected": detected, "blocked": is_blocked,
                        "outcome": "blocked" if is_blocked else "allowed", "input": case["input"]})
    malicious_count = sum(1 for case in cases if case["malicious"])
    return {"results": results, "metrics": {"total_cases": len(cases), "blocked_attacks": blocked,
            "successful_attacks": successful, "false_positives": fp, "false_negatives": fn,
            "attack_success_rate": round(successful / max(1, malicious_count) * 100, 1), "mitigation_enabled": mitigation},
            "limitation": "Pattern-based evaluation harness only; it does not guarantee application security."}
