"""Structured-output schema, prompts, and response parsing."""

from __future__ import annotations

import json
from typing import Any

from src.prompts import (
    PROMPT_REVIEW_SYSTEM_ROOT,
    PROMPT_REVIEW_USER_TEMPLATE,
    compose_with_optional_append,
    render_template,
)
from src.themes import ThemePath, ThemeTaxonomy

# Fallback schema when taxonomy is unavailable (tests / legacy). Prefer
# build_assignment_schema(taxonomy) so paths are enum-constrained.
ASSIGNMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        }
    },
    "required": ["assignments"],
}


def build_assignment_schema(taxonomy: ThemeTaxonomy) -> dict[str, Any]:
    """JSON schema with an enum of full taxonomy path labels."""
    labels = [path.label for path in taxonomy.paths]
    if not labels:
        raise ValueError("taxonomy has no paths; cannot build assignment schema")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "path": {"type": "string", "enum": labels},
                    },
                    "required": ["path"],
                },
            }
        },
        "required": ["assignments"],
    }


def build_messages(review: dict[str, Any], taxonomy: ThemeTaxonomy) -> list[dict[str, str]]:
    taxonomy_block = taxonomy.prompt_block()
    system = compose_with_optional_append(
        PROMPT_REVIEW_SYSTEM_ROOT,
        placeholder="taxonomy_block",
        injected=taxonomy_block,
        append_header="Allowed theme paths (copy path strings exactly):",
    )
    # Ensure schema reminder if the env root omitted both placeholder and trailing hint
    if "Omit review_id" not in system and "review_id" not in system.lower():
        system = system.rstrip() + "\n\nReturn JSON matching the schema. Omit review_id.\n"

    user = render_template(
        PROMPT_REVIEW_USER_TEMPLATE,
        rating=review.get("rating"),
        title=review.get("title") or "(none)",
        content_en=review.get("content_en") or "",
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_assignments(
    content: str,
    review: dict[str, Any],
    taxonomy: ThemeTaxonomy,
) -> tuple[list[dict[str, str]], list[str]]:
    """Parse model JSON, inject review_id, validate against taxonomy, dedupe."""
    warnings: list[str] = []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model returned non-JSON: {exc}") from exc

    raw_items = payload.get("assignments") if isinstance(payload, dict) else None
    if raw_items is None:
        raise ValueError("missing assignments array in model response")
    if not isinstance(raw_items, list):
        raise ValueError("assignments must be a list")

    review_id = str(review["id"])
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            warnings.append("skipped non-object assignment")
            continue

        path_label = str(item.get("path") or "").strip()
        strategic = str(item.get("strategic_theme") or "").strip()
        midlevel = str(item.get("midlevel_theme") or "").strip()
        specific = str(item.get("specific_theme") or "").strip()

        if path_label:
            path = taxonomy.resolve_path_label(path_label)
            display = path_label
        else:
            path = taxonomy.resolve_assignment(strategic, midlevel, specific)
            display = f"{strategic} > {midlevel} > {specific}"

        if path is None:
            warnings.append(f"rejected unknown path: {display}")
            continue
        if path.key in seen:
            continue
        seen.add(path.key)
        rows.append(_row(review_id, path))
    return rows, warnings


def _row(review_id: str, path: ThemePath) -> dict[str, str]:
    return {
        "review_id": review_id,
        "strategic_theme": path.strategic,
        "midlevel_theme": path.midlevel,
        "specific_theme": path.specific,
    }
