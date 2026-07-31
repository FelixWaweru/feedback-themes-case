"""
Kvist Bank feedback theme extraction pipeline.

Usage:
    python pipeline.py
    python pipeline.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from openrouter import OpenRouter

from src import config
from src.fsutil import configure_stdio
from src.io_run import RunState, create_run_dir
from src.openrouter_client import ExtractResult, extract_review
from src.themes import ThemeTaxonomy

# Static concurrency knobs (also mirrored in src.config for the client).
MAX_WORKERS = config.MAX_WORKERS
REQUEST_TIMEOUT_S = config.REQUEST_TIMEOUT_S
MAX_RETRIES = config.MAX_RETRIES


def load_reviews(path=config.REVIEWS_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("reviews.json must be a JSON array")
    return data


def _process_one(
    review: dict[str, Any],
    taxonomy: ThemeTaxonomy,
    model: str,
    api_key: str,
) -> ExtractResult:
    # One client per task avoids sharing HTTP sessions across threads.
    with OpenRouter(api_key=api_key) as client:
        return extract_review(client, review, taxonomy, model)


def run(
    limit: int | None = None,
    themes_path: Path | None = None,
) -> dict[str, Any]:
    configure_stdio()
    if not config.OPENROUTER_API_KEY:
        raise SystemExit(
            "OPENROUTER_API_KEY is missing. Copy .env.example to .env and set your key."
        )

    from discover_themes import ensure_themes_file

    path = themes_path or ensure_themes_file()
    taxonomy = ThemeTaxonomy.load(path)
    reviews = load_reviews()
    if limit is not None:
        reviews = reviews[:limit]

    run_dir = create_run_dir()
    state = RunState(
        taxonomy=taxonomy,
        model=config.OPENROUTER_MODEL,
        reviews_total=len(reviews),
        run_dir=run_dir,
    )
    state.initialize()

    print(
        f"Run dir: {config.relative_output_path(run_dir)}\n"
        f"Themes: {config.relative_output_path(path)}\n"
        f"Model: {config.OPENROUTER_MODEL}\n"
        f"Reviews: {len(reviews)} | workers: {MAX_WORKERS}",
        flush=True,
    )

    summary: dict[str, Any] | None = None
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(
                    _process_one,
                    review,
                    taxonomy,
                    config.OPENROUTER_MODEL,
                    config.OPENROUTER_API_KEY,
                ): review["id"]
                for review in reviews
            }
            done = 0
            for future in as_completed(futures):
                result = future.result()
                state.commit(result)
                done += 1
                status = "ERR" if result.error else f"{len(result.rows)} themes"
                print(
                    f"[{done}/{len(reviews)}] {result.review_id} -> {status}",
                    flush=True,
                )
        summary = state.finalize("completed")
    except BaseException:
        try:
            state.finalize("failed")
        except Exception:  # noqa: BLE001 — still re-raise the original failure
            pass
        raise

    assert summary is not None
    print(
        f"Done in {summary['wall_clock_seconds']}s | "
        f"cost=${summary['cost_usd']} | "
        f"rows={summary['assignment_rows']} | "
        f"failed={summary['reviews_failed']}",
        flush=True,
    )
    print("Score with: python score.py --pred out/flat.json", flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Extract three-tier themes from reviews")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N reviews (smoke tests)",
    )
    parser.add_argument(
        "--themes-dir",
        type=str,
        default=None,
        help="Optional out/themes/theme-YYYYMMDD_HHMMSS directory (uses themes.json inside)",
    )
    args = parser.parse_args(argv)
    themes_path = None
    if args.themes_dir:
        from discover_themes import resolve_themes_path

        themes_path = resolve_themes_path(args.themes_dir)
    run(limit=args.limit, themes_path=themes_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
