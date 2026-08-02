"""
Discover a three-tier theme taxonomy from reviews via batched LLM calls,
write artefacts to out/themes/theme-YYYYMMDD_HHMMSS/, refresh stable data/,
then optionally run the extraction pipeline.

Usage:
    python discover_themes.py
    python discover_themes.py --discover-only
    python discover_themes.py --discover-only --limit-batches 1
    python discover_themes.py --extract-only
    python discover_themes.py --extract-only --themes-dir out/themes/theme-20260731_175600
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from openrouter import OpenRouter

from src import config
from src.discover import (
    THEME_SLOT_NAMES,
    chunk_reviews,
    count_taxonomy_nodes,
    discover_batch,
    flatten_theme_candidates,
    render_theme_set_md,
    synthesize_taxonomy_validated,
)
from src.fsutil import (
    atomic_copy_file,
    atomic_write_json,
    atomic_write_text,
    configure_stdio,
    resolve_under_repo,
    unique_dir,
)
from src.openrouter_client import UsageStats

# Static discovery knobs
BATCH_SIZE = config.DISCOVERY_BATCH_SIZE
MAX_THEMES_PER_BATCH = config.DISCOVERY_MAX_THEMES_PER_BATCH
MAX_WORKERS = config.DISCOVERY_MAX_WORKERS


def create_theme_dir(base: Path | None = None) -> Path:
    root = base or config.THEMES_OUT_DIR
    return unique_dir(root, prefix="theme-")


def _empty_batches_doc(model: str, batch_size: int) -> dict[str, Any]:
    return {
        "model": model,
        "batch_size": batch_size,
        "batches": [],
        "cost_usd": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }


def _normalize_batch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in THEME_SLOT_NAMES:
        value = payload.get(name)
        if value is None:
            out[name] = None
        elif isinstance(value, dict):
            out[name] = {
                "strategic_theme": str(value.get("strategic_theme") or "").strip(),
                "midlevel_theme": str(value.get("midlevel_theme") or "").strip(),
                "specific_theme": str(value.get("specific_theme") or "").strip(),
                "definition": str(value.get("definition") or "").strip(),
            }
        else:
            out[name] = None
    return out


def _checkpoint_batches(doc: dict[str, Any], theme_dir: Path) -> None:
    atomic_write_json(theme_dir / "discovery_batches.json", doc)
    atomic_write_json(config.ROOT / "data" / "discovery_batches.json", doc)


def _run_one_batch(
    batch_index: int,
    reviews_slice: list[dict[str, Any]],
    model: str,
    api_key: str,
) -> tuple[int, dict[str, Any], UsageStats, str | None]:
    try:
        with OpenRouter(api_key=api_key) as client:
            payload, usage = discover_batch(client, reviews_slice, model)
        record = {
            "batch_index": batch_index,
            "review_ids": [str(r["id"]) for r in reviews_slice],
            **_normalize_batch_payload(payload),
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "cost": usage.cost_usd,
            },
        }
        return batch_index, record, usage, None
    except Exception as exc:  # noqa: BLE001
        empty = {name: None for name in THEME_SLOT_NAMES}
        record = {
            "batch_index": batch_index,
            "review_ids": [str(r["id"]) for r in reviews_slice],
            **empty,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0},
            "error": str(exc),
        }
        return batch_index, record, UsageStats(), str(exc)


def discover(
    *,
    limit_batches: int | None = None,
    batch_size: int = BATCH_SIZE,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Run batch discovery + synthesis. Returns (theme_dir, taxonomy, summary)."""
    if not config.OPENROUTER_API_KEY:
        raise SystemExit(
            "OPENROUTER_API_KEY is missing. Copy .env.example to .env and set your key."
        )

    from pipeline import load_reviews

    reviews = load_reviews()
    batches = chunk_reviews(reviews, batch_size)
    if limit_batches is not None:
        batches = batches[:limit_batches]

    theme_dir = create_theme_dir()
    model = config.OPENROUTER_THEME_MODEL
    doc = _empty_batches_doc(model, batch_size)
    _checkpoint_batches(doc, theme_dir)

    print(
        f"Theme dir: {config.relative_output_path(theme_dir)}\n"
        f"Model: {model}\n"
        f"Batches: {len(batches)} x up to {batch_size} | workers: {MAX_WORKERS}",
        flush=True,
    )

    started = time.perf_counter()
    results: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                _run_one_batch,
                idx,
                slice_,
                model,
                config.OPENROUTER_API_KEY,
            ): idx
            for idx, slice_ in enumerate(batches)
        }
        done = 0
        for future in as_completed(futures):
            batch_index, record, usage, error = future.result()
            results[batch_index] = record
            doc["cost_usd"] = round(float(doc["cost_usd"]) + usage.cost_usd, 8)
            doc["prompt_tokens"] = int(doc["prompt_tokens"]) + usage.prompt_tokens
            doc["completion_tokens"] = (
                int(doc["completion_tokens"]) + usage.completion_tokens
            )
            # Rebuild batches list in order for stable checkpoints
            doc["batches"] = [results[i] for i in sorted(results)]
            _checkpoint_batches(doc, theme_dir)
            done += 1
            non_null = sum(
                1 for name in THEME_SLOT_NAMES if record.get(name) is not None
            )
            status = f"ERR {error}" if error else f"{non_null} themes"
            print(f"[batch {done}/{len(batches)}] #{batch_index} -> {status}", flush=True)

    candidates = flatten_theme_candidates(doc)
    print(f"Unique candidate themes: {len(candidates)}", flush=True)
    if not candidates:
        raise SystemExit("No theme candidates discovered; aborting synthesis.")

    print("Synthesizing taxonomy…", flush=True)
    with OpenRouter(api_key=config.OPENROUTER_API_KEY) as client:
        taxonomy, synth_usage, repair_usage = synthesize_taxonomy_validated(
            client, candidates, model
        )

    doc["cost_usd"] = round(float(doc["cost_usd"]) + synth_usage.cost_usd, 8)
    doc["prompt_tokens"] = int(doc["prompt_tokens"]) + synth_usage.prompt_tokens
    doc["completion_tokens"] = (
        int(doc["completion_tokens"]) + synth_usage.completion_tokens
    )
    if repair_usage:
        doc["cost_usd"] = round(float(doc["cost_usd"]) + repair_usage.cost_usd, 8)
        doc["prompt_tokens"] = int(doc["prompt_tokens"]) + repair_usage.prompt_tokens
        doc["completion_tokens"] = (
            int(doc["completion_tokens"]) + repair_usage.completion_tokens
        )
    _checkpoint_batches(doc, theme_dir)

    theme_md = render_theme_set_md(taxonomy)
    atomic_write_json(theme_dir / "themes.json", taxonomy)
    atomic_write_text(theme_dir / "theme_set.md", theme_md)

    # Stable latest copies for the extractor (only after successful validation)
    atomic_write_json(config.THEMES_PATH, taxonomy)
    atomic_write_text(config.THEME_SET_PATH, theme_md)
    if not config.THEMES_PATH.is_file():
        raise SystemExit(
            f"Discovery wrote taxonomy but {config.THEMES_PATH} is missing after write"
        )
    if not config.THEME_SET_PATH.is_file():
        raise SystemExit(
            f"Discovery wrote theme set but {config.THEME_SET_PATH} is missing after write"
        )

    counts = count_taxonomy_nodes(taxonomy)
    elapsed = round(time.perf_counter() - started, 3)
    rel_theme = config.relative_output_path(theme_dir)
    summary = {
        "status": "completed",
        "model": model,
        "theme_dir": rel_theme,
        "batches_total": len(batches),
        "batches_failed": sum(1 for b in doc["batches"] if b.get("error")),
        "candidate_themes": len(candidates),
        "taxonomy_counts": counts,
        "wall_clock_seconds": elapsed,
        "cost_usd": doc["cost_usd"],
        "prompt_tokens": doc["prompt_tokens"],
        "completion_tokens": doc["completion_tokens"],
        "files": {
            "theme_dir_themes": f"{rel_theme}/themes.json",
            "theme_dir_theme_set": f"{rel_theme}/theme_set.md",
            "theme_dir_batches": f"{rel_theme}/discovery_batches.json",
            "theme_dir_summary": f"{rel_theme}/discovery_summary.json",
            "stable_themes": config.relative_output_path(config.THEMES_PATH),
            "stable_theme_set": config.relative_output_path(config.THEME_SET_PATH),
            "stable_batches": config.relative_output_path(
                config.ROOT / "data" / "discovery_batches.json"
            ),
            "stable_summary": config.relative_output_path(
                config.ROOT / "data" / "discovery_summary.json"
            ),
        },
    }
    atomic_write_json(theme_dir / "discovery_summary.json", summary)
    atomic_write_json(config.ROOT / "data" / "discovery_summary.json", summary)

    print(
        f"Discovery done in {elapsed}s | cost=${summary['cost_usd']} | "
        f"taxonomy={counts}",
        flush=True,
    )
    return theme_dir, taxonomy, summary


def resolve_themes_path(themes_dir: str | None) -> Path:
    if not themes_dir:
        return ensure_themes_file()
    path = resolve_under_repo(themes_dir)
    themes_file = path / "themes.json" if path.is_dir() else path
    if not themes_file.is_file():
        raise SystemExit(f"themes.json not found at {themes_file}")
    # Ensure extractor stable path matches the chosen generation
    atomic_copy_file(themes_file, config.THEMES_PATH)
    md = themes_file.with_name("theme_set.md")
    if md.is_file():
        atomic_copy_file(md, config.THEME_SET_PATH)
    if not config.THEMES_PATH.is_file():
        raise SystemExit(f"Failed to write stable themes file at {config.THEMES_PATH}")
    return config.THEMES_PATH


def ensure_themes_file() -> Path:
    """Return ``data/themes.json``, restoring from newest theme archive if missing."""
    if config.THEMES_PATH.is_file():
        return config.THEMES_PATH

    theme_dirs = sorted(
        (p for p in config.THEMES_OUT_DIR.glob("theme-*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    for theme_dir in theme_dirs:
        src = theme_dir / "themes.json"
        if not src.is_file():
            continue
        atomic_copy_file(src, config.THEMES_PATH)
        md = theme_dir / "theme_set.md"
        if md.is_file():
            atomic_copy_file(md, config.THEME_SET_PATH)
        if config.THEMES_PATH.is_file():
            print(
                f"Restored {config.relative_output_path(config.THEMES_PATH)} "
                f"from {config.relative_output_path(theme_dir)}",
                flush=True,
            )
            return config.THEMES_PATH

    raise SystemExit(
        "data/themes.json is missing and no out/themes/theme-*/themes.json found. "
        "Run: python discover_themes.py --discover-only"
    )


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Discover themes from reviews and optionally extract assignments"
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover/synthesize themes; do not run extraction",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Skip discovery; run extraction using existing or --themes-dir taxonomy",
    )
    parser.add_argument(
        "--themes-dir",
        type=str,
        default=None,
        help="Path to out/themes/theme-YYYYMMDD_HHMMSS (or themes.json) for extraction",
    )
    parser.add_argument(
        "--limit-batches",
        type=int,
        default=None,
        help="Only process the first N discovery batches (smoke tests)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit reviews during extraction (passed to pipeline)",
    )
    args = parser.parse_args(argv)

    if args.discover_only and args.extract_only:
        raise SystemExit("Use only one of --discover-only / --extract-only")

    if not args.extract_only:
        discover(limit_batches=args.limit_batches, batch_size=BATCH_SIZE)

    if args.discover_only:
        return 0

    resolve_themes_path(args.themes_dir)

    import pipeline

    pipeline.run(limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
