"""Timestamped run directories, atomic writes, and thread-safe RunState."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src import config
from src.fsutil import (
    atomic_write_json,
    atomic_write_text,
    unique_dir,
)
from src.openrouter_client import ExtractResult
from src.project import build_categorisation, build_flat, review_record
from src.summary_md import render_summary_md
from src.themes import ThemeTaxonomy

# Re-export for callers that import write helpers from io_run.
__all__ = [
    "RunState",
    "atomic_write_json",
    "atomic_write_text",
    "create_run_dir",
]


def create_run_dir(runs_dir: Path | None = None) -> Path:
    base = runs_dir or config.RUNS_DIR
    return unique_dir(base, prefix="")


@dataclass
class RunState:
    taxonomy: ThemeTaxonomy
    model: str
    reviews_total: int
    run_dir: Path
    started_at: float = field(default_factory=time.perf_counter)
    lock: threading.Lock = field(default_factory=threading.Lock)
    status: str = "running"
    reviews_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    reviews_processed: int = 0
    reviews_failed: int = 0

    def file_map(self) -> dict[str, str]:
        rel_run = config.relative_output_path(self.run_dir)
        return {
            "run_categorisation": f"{rel_run}/categorisation.json",
            "run_flat": f"{rel_run}/flat.json",
            "run_summary_json": f"{rel_run}/run_summary.json",
            "run_summary_md": f"{rel_run}/run_summary.md",
            "stable_flat": config.relative_output_path(config.OUT_DIR / "flat.json"),
            "stable_categorisation": config.relative_output_path(
                config.OUT_DIR / "categorisation.json"
            ),
            "stable_summary_json": config.relative_output_path(
                config.OUT_DIR / "run_summary.json"
            ),
            "stable_summary_md": config.relative_output_path(
                config.OUT_DIR / "run_summary.md"
            ),
        }

    def _ordered_reviews(self) -> list[dict[str, Any]]:
        return [self.reviews_by_id[k] for k in sorted(self.reviews_by_id)]

    def _assignment_rows(self) -> int:
        return sum(len(r.get("themes", [])) for r in self.reviews_by_id.values())

    def build_summary(self) -> dict[str, Any]:
        elapsed = round(time.perf_counter() - self.started_at, 3)
        return {
            "status": self.status,
            "reviews_total": self.reviews_total,
            "reviews_processed": self.reviews_processed,
            "reviews_failed": self.reviews_failed,
            "assignment_rows": self._assignment_rows(),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "wall_clock_seconds": elapsed,
            "cost_usd": round(self.cost_usd, 8),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "model": self.model,
            "output_dir": config.relative_output_path(self.run_dir),
            "files": self.file_map(),
        }

    def _checkpoint_unlocked(self) -> None:
        reviews = self._ordered_reviews()
        categorisation = build_categorisation(
            model=self.model,
            theme_set_version=self.taxonomy.version,
            theme_registry=self.taxonomy.registry_for_output(),
            reviews=reviews,
        )
        flat = build_flat(reviews)
        summary = self.build_summary()
        summary_md = render_summary_md(summary)

        targets = [
            (self.run_dir / "categorisation.json", categorisation, "json"),
            (self.run_dir / "flat.json", flat, "json"),
            (self.run_dir / "run_summary.json", summary, "json"),
            (self.run_dir / "run_summary.md", summary_md, "text"),
            (config.OUT_DIR / "categorisation.json", categorisation, "json"),
            (config.OUT_DIR / "flat.json", flat, "json"),
            (config.OUT_DIR / "run_summary.json", summary, "json"),
            (config.OUT_DIR / "run_summary.md", summary_md, "text"),
        ]
        for path, payload, kind in targets:
            if kind == "json":
                atomic_write_json(path, payload)
            else:
                atomic_write_text(path, str(payload))

    def initialize(self) -> None:
        with self.lock:
            self._checkpoint_unlocked()

    def commit(self, result: ExtractResult) -> None:
        with self.lock:
            self.prompt_tokens += result.usage.prompt_tokens
            self.completion_tokens += result.usage.completion_tokens
            self.cost_usd += result.usage.cost_usd

            if result.error:
                self.reviews_failed += 1
                self.errors.append(
                    {"review_id": result.review_id, "error": result.error}
                )
            else:
                self.reviews_processed += 1
                self.reviews_by_id[result.review_id] = review_record(
                    result.review_id, result.rating, result.rows
                )
                for warning in result.warnings:
                    self.warnings.append(
                        {"review_id": result.review_id, "warning": warning}
                    )

            self._checkpoint_unlocked()

    def finalize(self, status: str) -> dict[str, Any]:
        with self.lock:
            self.status = status
            self._checkpoint_unlocked()
            return self.build_summary()
