"""LLM theme discovery: batch extraction of candidates and taxonomy synthesis."""

from __future__ import annotations

import json
from typing import Any

from openrouter import OpenRouter

from src.openrouter_client import UsageStats, chat_json
from src.themes import ThemeTaxonomy

THEME_SLOT_NAMES = (
    "theme_one",
    "theme_two",
    "theme_three",
    "theme_four",
    "theme_five",
)

_THEME_OBJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "strategic_theme": {"type": "string"},
        "midlevel_theme": {"type": "string"},
        "specific_theme": {"type": "string"},
        "definition": {"type": "string"},
    },
    "required": [
        "strategic_theme",
        "midlevel_theme",
        "specific_theme",
        "definition",
    ],
}

_NULLABLE_THEME: dict[str, Any] = {
    "anyOf": [_THEME_OBJECT_SCHEMA, {"type": "null"}]
}

BATCH_DISCOVERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {name: _NULLABLE_THEME for name in THEME_SLOT_NAMES},
    "required": list(THEME_SLOT_NAMES),
}

_SPECIFIC_NODE: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "definition": {"type": "string"},
    },
    "required": ["name", "definition"],
}

_MIDLEVEL_NODE: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "definition": {"type": "string"},
        "specific": {"type": "array", "items": _SPECIFIC_NODE},
    },
    "required": ["name", "definition", "specific"],
}

_STRATEGIC_NODE: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "definition": {"type": "string"},
        "midlevel": {"type": "array", "items": _MIDLEVEL_NODE},
    },
    "required": ["name", "definition", "midlevel"],
}

TAXONOMY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string"},
        "strategic": {"type": "array", "items": _STRATEGIC_NODE},
    },
    "required": ["version", "strategic"],
}


def chunk_reviews(
    reviews: list[dict[str, Any]], batch_size: int
) -> list[list[dict[str, Any]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    return [reviews[i : i + batch_size] for i in range(0, len(reviews), batch_size)]


def _format_reviews_for_prompt(reviews: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for review in reviews:
        lines.append(
            f"- id={review.get('id')} | rating={review.get('rating')} | "
            f"title={review.get('title') or '(none)'} | "
            f"content_en={review.get('content_en') or ''}"
        )
    return "\n".join(lines)


def discover_batch(
    client: OpenRouter,
    reviews_slice: list[dict[str, Any]],
    model: str,
) -> tuple[dict[str, Any], UsageStats]:
    from src.prompts import (
        PROMPT_THEME_DISCOVERY_SYSTEM_ROOT,
        PROMPT_THEME_DISCOVERY_USER_TEMPLATE,
        render_template,
    )

    system = PROMPT_THEME_DISCOVERY_SYSTEM_ROOT
    user = render_template(
        PROMPT_THEME_DISCOVERY_USER_TEMPLATE,
        batch_size=len(reviews_slice),
        batch_reviews=_format_reviews_for_prompt(reviews_slice),
    )
    return chat_json(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema_name="batch_theme_discovery",
        schema=BATCH_DISCOVERY_SCHEMA,
    )


def flatten_theme_candidates(batches_doc: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for batch in batches_doc.get("batches", []):
        for slot in THEME_SLOT_NAMES:
            theme = batch.get(slot)
            if not isinstance(theme, dict):
                continue
            strategic = str(theme.get("strategic_theme") or "").strip()
            midlevel = str(theme.get("midlevel_theme") or "").strip()
            specific = str(theme.get("specific_theme") or "").strip()
            definition = str(theme.get("definition") or "").strip()
            if not (strategic and midlevel and specific):
                continue
            key = (strategic, midlevel, specific)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "strategic_theme": strategic,
                    "midlevel_theme": midlevel,
                    "specific_theme": specific,
                    "definition": definition,
                }
            )
    return candidates


def synthesize_taxonomy(
    client: OpenRouter,
    theme_candidates: list[dict[str, str]],
    model: str,
    *,
    repair_error: str | None = None,
) -> tuple[dict[str, Any], UsageStats]:
    from src.prompts import (
        PROMPT_THEME_SYNTHESIS_SYSTEM_ROOT,
        PROMPT_THEME_SYNTHESIS_USER_TEMPLATE,
        render_template,
    )

    if repair_error:
        repair_section = (
            "\nPrevious output failed validation:\n"
            f"{repair_error}\n"
            "Fix the taxonomy so midlevel and specific names are globally unique parents."
        )
    else:
        repair_section = ""

    system = PROMPT_THEME_SYNTHESIS_SYSTEM_ROOT
    user = render_template(
        PROMPT_THEME_SYNTHESIS_USER_TEMPLATE,
        candidates_json=json.dumps(theme_candidates, ensure_ascii=False, indent=2),
        repair_section=repair_section,
    )
    return chat_json(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema_name="theme_taxonomy",
        schema=TAXONOMY_SCHEMA,
    )


def validate_taxonomy_dict(data: dict[str, Any]) -> ThemeTaxonomy:
    """Load through ThemeTaxonomy; raises ValueError on hierarchy faults."""
    return ThemeTaxonomy(data)


def synthesize_taxonomy_validated(
    client: OpenRouter,
    theme_candidates: list[dict[str, str]],
    model: str,
) -> tuple[dict[str, Any], UsageStats, UsageStats | None]:
    """Synthesize once; on validation failure, one repair retry."""
    payload, usage = synthesize_taxonomy(client, theme_candidates, model)
    repair_usage: UsageStats | None = None
    try:
        validate_taxonomy_dict(payload)
        return payload, usage, None
    except ValueError as exc:
        repaired, repair_usage = synthesize_taxonomy(
            client,
            theme_candidates,
            model,
            repair_error=str(exc),
        )
        validate_taxonomy_dict(repaired)
        return repaired, usage, repair_usage


def render_theme_set_md(taxonomy: dict[str, Any]) -> str:
    lines = [
        "# Kvist Bank theme set",
        "",
        "Three-tier hierarchy used by the extraction pipeline. Every assignment must be",
        "exactly one path from this set. Names are globally unique at each midlevel and",
        "specific tier so the flat projection forms a consistent tree.",
        "",
        f"_Version: {taxonomy.get('version', 'unknown')}_",
        "",
    ]
    for strategic in taxonomy.get("strategic", []):
        lines.append(f"## {strategic['name']}")
        lines.append("")
        lines.append(str(strategic.get("definition") or "").strip())
        lines.append("")
        for midlevel in strategic.get("midlevel", []):
            lines.append(f"### {midlevel['name']}")
            lines.append("")
            lines.append(str(midlevel.get("definition") or "").strip())
            lines.append("")
            for specific in midlevel.get("specific", []):
                name = specific["name"]
                definition = str(specific.get("definition") or "").strip()
                lines.append(f"- **{name}** — {definition}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def count_taxonomy_nodes(taxonomy: dict[str, Any]) -> dict[str, int]:
    strategic_n = 0
    midlevel_n = 0
    specific_n = 0
    for strategic in taxonomy.get("strategic", []):
        strategic_n += 1
        for midlevel in strategic.get("midlevel", []):
            midlevel_n += 1
            specific_n += len(midlevel.get("specific") or [])
    return {
        "strategic": strategic_n,
        "midlevel": midlevel_n,
        "specific": specific_n,
    }
