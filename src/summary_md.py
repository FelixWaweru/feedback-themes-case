"""Render human-readable run_summary.md from run_summary.json."""

from __future__ import annotations

from typing import Any

from src import config


def render_summary_md(summary: dict[str, Any]) -> str:
    errors = summary.get("errors") or []
    files = summary.get("files") or {}
    default_flat = config.relative_output_path(config.OUT_DIR / "flat.json")
    lines = [
        "# Run summary",
        "",
        f"- **Status:** {summary.get('status', 'unknown')}",
        f"- **Model:** {summary.get('model', '')}",
        f"- **Wall clock:** {summary.get('wall_clock_seconds', 0)}s",
        f"- **Cost (OpenRouter usage.cost):** ${summary.get('cost_usd', 0)}",
        (
            f"- **Tokens:** {summary.get('prompt_tokens', 0)} prompt / "
            f"{summary.get('completion_tokens', 0)} completion"
        ),
        (
            f"- **Reviews:** {summary.get('reviews_processed', 0)} processed / "
            f"{summary.get('reviews_failed', 0)} failed / "
            f"{summary.get('reviews_total', 0)} total"
        ),
        f"- **Assignment rows:** {summary.get('assignment_rows', 0)}",
        f"- **Output dir:** {summary.get('output_dir', '')}",
        f"- **Stable flat:** {files.get('stable_flat', default_flat)}",
        "",
        "## Files",
        "",
    ]
    for key in (
        "run_categorisation",
        "run_flat",
        "run_summary_json",
        "run_summary_md",
        "stable_flat",
        "stable_categorisation",
        "stable_summary_json",
        "stable_summary_md",
    ):
        if key in files:
            lines.append(f"- `{key}`: `{files[key]}`")

    lines.extend(["", "## Errors", ""])
    if not errors:
        lines.append("_None._")
    else:
        for err in errors:
            rid = err.get("review_id", "?")
            msg = err.get("error", "")
            lines.append(f"- `{rid}`: {msg}")

    warnings = summary.get("warnings") or []
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("_None._")
    else:
        for warn in warnings[:50]:
            rid = warn.get("review_id", "?")
            msg = warn.get("warning", "")
            lines.append(f"- `{rid}`: {msg}")
        if len(warnings) > 50:
            lines.append(f"- … and {len(warnings) - 50} more")

    lines.append("")
    return "\n".join(lines)
