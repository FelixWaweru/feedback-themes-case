"""Configuration loaded from environment and static pipeline knobs."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", encoding="utf-8")

REVIEWS_PATH = ROOT / "data" / "reviews.json"
THEMES_PATH = ROOT / "data" / "themes.json"
THEME_SET_PATH = ROOT / "data" / "theme_set.md"
OUT_DIR = ROOT / "out"
RUNS_DIR = OUT_DIR / "runs"
THEMES_OUT_DIR = OUT_DIR / "themes"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
# Review assignment / extraction pipeline
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
# Theme discovery + taxonomy synthesis (separate so you can use a different model)
OPENROUTER_THEME_MODEL = os.getenv(
    "OPENROUTER_THEME_MODEL",
    os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
).strip()


# Static concurrency / reliability knobs (not env) — tune for <6 min wall clock.
MAX_WORKERS = 8
REQUEST_TIMEOUT_S = 60
MAX_RETRIES = 3
RETRY_BASE_DELAY_S = 1.5

# Theme discovery knobs
DISCOVERY_BATCH_SIZE = 25
DISCOVERY_MAX_THEMES_PER_BATCH = 5
DISCOVERY_MAX_WORKERS = 4


def relative_output_path(path: Path | str) -> str:
    """Serialize paths for JSON/MD outputs as repo-relative posix paths.

    Example: ``feedback-themes-case/out/runs/20260731_174835``
    (relative to the parent of the repo root — never an absolute machine path).
    """
    resolved = Path(path).resolve()
    root_parent = ROOT.parent.resolve()
    try:
        return resolved.relative_to(root_parent).as_posix()
    except ValueError:
        try:
            # Fallback: relative to repo root if outside parent for any reason
            return f"{ROOT.name}/{resolved.relative_to(ROOT.resolve()).as_posix()}"
        except ValueError:
            # Last resort: keep only the trailing out/… or data/… segment if present
            parts = resolved.parts
            for marker in ("out", "data"):
                if marker in parts:
                    idx = parts.index(marker)
                    return "/".join((ROOT.name, *parts[idx:]))
            return f"{ROOT.name}/{resolved.name}"
