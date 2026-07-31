"""Prompt roots loaded from env, with injectable dynamic sections.

Env vars hold the editable core instructions. Dynamic content is injected via
placeholders (preferred) or appended when a placeholder is omitted.

Placeholders
------------
Review assignment (system):
  {taxonomy_block}  — allowed theme paths + definitions

Review assignment (user):
  {rating} {title} {content_en}

Theme discovery (user):
  {batch_size} {batch_reviews}

Theme synthesis (user):
  {candidates_json} {repair_section}
"""

from __future__ import annotations

import os
from string import Formatter

from src import config

# ---------------------------------------------------------------------------
# Defaults (used when env vars are unset)
# ---------------------------------------------------------------------------

DEFAULT_REVIEW_SYSTEM_ROOT = """You extract recurring customer-feedback themes for a Norwegian SME bank (invoice financing and business banking).
A theme is a subject many customers could mention — not a one-off summary and not a restatement of sentiment alone.
Return only path values copied exactly from the allowed list; do not invent or reorder tiers.

{taxonomy_block}

Return JSON matching the schema. Omit review_id."""

DEFAULT_REVIEW_USER_TEMPLATE = """Rating: {rating}
Title: {title}
Feedback (English): {content_en}
"""

DEFAULT_THEME_DISCOVERY_SYSTEM_ROOT = """You invent recurring customer-feedback themes for a Norwegian SME bank (invoice financing and business banking).
A theme is a subject many customers could mention — not a one-off summary and not sentiment polarity alone.
Name midlevel and specific themes as polarity-neutral subjects so both praise and pain can attach (e.g. "Support reply speed", not only "Communication delays").
Cover recurring positives in the batch (speed, rates, staff helpfulness, easy onboarding) as well as frictions.
Return up to five distinct three-tier themes that appear in THIS batch.
Prioritize coverage of distinct subjects over five near-duplicate complaints.
Use theme_one..theme_five; set unused slots to null.
Each non-null theme needs strategic_theme, midlevel_theme, specific_theme, and a one-line definition.
Prefer reusable labels; keep midlevel and specific names globally distinctive."""

DEFAULT_THEME_DISCOVERY_USER_TEMPLATE = """Batch of {batch_size} reviews:

{batch_reviews}

Propose up to 5 themes covering the main distinct subjects in this batch (praise and friction)."""

DEFAULT_THEME_SYNTHESIS_SYSTEM_ROOT = """You merge candidate three-tier feedback themes into one consistent taxonomy.
Rules:
- Output nested strategic > midlevel > specific with a one-line definition each.
- Every midlevel name must appear under exactly one strategic.
- Every specific name must appear under exactly one midlevel.
- Merge synonyms; drop true one-off descriptions; keep themes that can recur across reviews.
- Prefer polarity-neutral specific names; definitions may mention both positive and negative manifestations when both appear in candidates.
- Do not drop a praise/speed candidate by folding it only into a delay/failure theme — keep subject coverage.
- Target roughly 40–60 specifics when candidates support it for labeling ~200 SME bank reviews; compact must not mean complaint-only.
- If a recurring candidate's subject is not represented after merge, keep it (or a renamed neutral form) rather than discard."""

DEFAULT_THEME_SYNTHESIS_USER_TEMPLATE = """Candidate themes from batch discovery:
{candidates_json}

Synthesize the final taxonomy JSON.
{repair_section}"""


def _unescape_env(value: str) -> str:
    """Interpret common escape sequences from single-line .env values."""
    return (
        value.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
    )


def _env_prompt(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return _unescape_env(raw.strip())


def _field_names(template: str) -> set[str]:
    names: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            names.add(field_name.split(".")[0])
    return names


def render_template(template: str, **kwargs: object) -> str:
    """Format template; unknown placeholders are left alone via safe subset."""
    fields = _field_names(template)
    payload = {k: kwargs.get(k, "") for k in fields}
    # Also accept extras only if present in template
    try:
        return template.format(**payload)
    except (KeyError, ValueError):
        # Fallback: manual replace for simple {name} tokens
        out = template
        for key, value in kwargs.items():
            out = out.replace("{" + key + "}", str(value))
        return out


def compose_with_optional_append(
    root: str,
    *,
    placeholder: str,
    injected: str,
    append_header: str | None = None,
) -> str:
    """If ``{placeholder}`` is in root, substitute it; otherwise append injected."""
    token = "{" + placeholder + "}"
    if token in root:
        return render_template(root, **{placeholder: injected})
    parts = [root.rstrip(), ""]
    if append_header:
        parts.append(append_header)
    parts.append(injected)
    return "\n".join(parts).rstrip() + "\n"


# Loaded once at import (after dotenv in config)
PROMPT_REVIEW_SYSTEM_ROOT = _env_prompt(
    "PROMPT_REVIEW_SYSTEM_ROOT", DEFAULT_REVIEW_SYSTEM_ROOT
)
PROMPT_REVIEW_USER_TEMPLATE = _env_prompt(
    "PROMPT_REVIEW_USER_TEMPLATE", DEFAULT_REVIEW_USER_TEMPLATE
)
PROMPT_THEME_DISCOVERY_SYSTEM_ROOT = _env_prompt(
    "PROMPT_THEME_DISCOVERY_SYSTEM_ROOT", DEFAULT_THEME_DISCOVERY_SYSTEM_ROOT
)
PROMPT_THEME_DISCOVERY_USER_TEMPLATE = _env_prompt(
    "PROMPT_THEME_DISCOVERY_USER_TEMPLATE", DEFAULT_THEME_DISCOVERY_USER_TEMPLATE
)
PROMPT_THEME_SYNTHESIS_SYSTEM_ROOT = _env_prompt(
    "PROMPT_THEME_SYNTHESIS_SYSTEM_ROOT", DEFAULT_THEME_SYNTHESIS_SYSTEM_ROOT
)
PROMPT_THEME_SYNTHESIS_USER_TEMPLATE = _env_prompt(
    "PROMPT_THEME_SYNTHESIS_USER_TEMPLATE", DEFAULT_THEME_SYNTHESIS_USER_TEMPLATE
)

# Re-export config root for callers that only import prompts
ROOT = config.ROOT
