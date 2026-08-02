"""OpenRouter client using the official Python SDK."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from openrouter import OpenRouter

from src import config
from src.extract import build_assignment_schema, build_messages, parse_assignments
from src.themes import ThemeTaxonomy


@dataclass(slots=True)
class UsageStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class ExtractResult:
    review_id: str
    rating: int | None
    rows: list[dict[str, str]]
    warnings: list[str]
    usage: UsageStats
    error: str | None = None


def usage_from_response(res: Any) -> UsageStats:
    usage = getattr(res, "usage", None)
    if usage is None:
        return UsageStats()
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    cost_raw = getattr(usage, "cost", None)
    cost = float(cost_raw) if cost_raw is not None else 0.0
    return UsageStats(prompt_tokens=prompt, completion_tokens=completion, cost_usd=cost)


def message_content(res: Any) -> str:
    choices = getattr(res, "choices", None) or []
    if not choices:
        raise ValueError("empty choices in OpenRouter response")
    message = choices[0].message
    content = getattr(message, "content", None)
    if content is None:
        raise ValueError("empty message content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            else:
                text = getattr(part, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def extract_review(
    client: OpenRouter,
    review: dict[str, Any],
    taxonomy: ThemeTaxonomy,
    model: str,
) -> ExtractResult:
    review_id = str(review["id"])
    rating = review.get("rating")
    messages = build_messages(review, taxonomy)
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "theme_assignments",
            "strict": True,
            "schema": build_assignment_schema(taxonomy),
        },
    }

    last_error: Exception | None = None
    usage = UsageStats()
    for attempt in range(config.MAX_RETRIES):
        try:
            res = client.chat.send(
                model=model,
                messages=messages,
                response_format=response_format,
                stream=False,
                temperature=0,
                timeout_ms=config.REQUEST_TIMEOUT_S * 1000,
                provider={"require_parameters": True},
            )
            usage = usage_from_response(res)
            content = message_content(res)
            rows, warnings = parse_assignments(content, review, taxonomy)
            return ExtractResult(
                review_id=review_id,
                rating=int(rating) if rating is not None else None,
                rows=rows,
                warnings=warnings,
                usage=usage,
            )
        except Exception as exc:  # noqa: BLE001 — retry then surface
            last_error = exc
            if attempt + 1 >= config.MAX_RETRIES:
                break
            delay = config.RETRY_BASE_DELAY_S * (2**attempt)
            time.sleep(delay)

    return ExtractResult(
        review_id=review_id,
        rating=int(rating) if rating is not None else None,
        rows=[],
        warnings=[],
        usage=usage,
        error=str(last_error) if last_error else "unknown extraction error",
    )


def chat_json(
    client: OpenRouter,
    *,
    model: str,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict[str, Any],
    temperature: float = 0,
) -> tuple[dict[str, Any], UsageStats]:
    """Send a structured JSON-schema chat request with retries."""
    import json

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": schema,
        },
    }
    last_error: Exception | None = None
    usage = UsageStats()
    for attempt in range(config.MAX_RETRIES):
        try:
            res = client.chat.send(
                model=model,
                messages=messages,
                response_format=response_format,
                stream=False,
                temperature=temperature,
                timeout_ms=config.REQUEST_TIMEOUT_S * 1000,
                provider={"require_parameters": True},
            )
            usage = usage_from_response(res)
            content = message_content(res)
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("structured output was not a JSON object")
            return payload, usage
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt + 1 >= config.MAX_RETRIES:
                break
            time.sleep(config.RETRY_BASE_DELAY_S * (2**attempt))
    raise RuntimeError(f"OpenRouter structured call failed: {last_error}")
