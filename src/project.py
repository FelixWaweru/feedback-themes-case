"""Build categorisation and flat projection structures from run state."""

from __future__ import annotations

from typing import Any


def build_flat(reviews: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for review in reviews:
        for theme in review.get("themes", []):
            rows.append(
                {
                    "review_id": review["review_id"],
                    "strategic_theme": theme["strategic_theme"],
                    "midlevel_theme": theme["midlevel_theme"],
                    "specific_theme": theme["specific_theme"],
                }
            )
    return rows


def build_categorisation(
    *,
    model: str,
    theme_set_version: str,
    theme_registry: dict[str, Any],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "theme_set_version": theme_set_version,
        "model": model,
        "reviews": reviews,
        "theme_registry": theme_registry,
    }


def review_record(
    review_id: str,
    rating: int | None,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    themes = [
        {
            "strategic_theme": row["strategic_theme"],
            "midlevel_theme": row["midlevel_theme"],
            "specific_theme": row["specific_theme"],
            "path": (
                f"{row['strategic_theme']} > "
                f"{row['midlevel_theme']} > "
                f"{row['specific_theme']}"
            ),
        }
        for row in rows
    ]
    return {
        "review_id": review_id,
        "rating": rating,
        "themes": themes,
    }
