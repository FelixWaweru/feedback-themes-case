# [RUN.md](http://RUN.md)

How to run the Kvist Bank theme extraction pipeline from a clean checkout.

## Prerequisites

- Python 3.10+
- An [OpenRouter](https://openrouter.ai/) API key

## Setup (recommended)

Windows (PowerShell):

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
source .venv/bin/activate
```

The setup scripts create `.venv`, install `requirements.txt`, and copy `.env.example` → `.env` if needed.

Edit `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_THEME_MODEL=openai/gpt-4o-mini
```

- `OPENROUTER_MODEL` — used by `pipeline.py` for per-review theme assignment.
- `OPENROUTER_THEME_MODEL` — used by `discover_themes.py` for batch discovery and taxonomy synthesis.

You can point these at different OpenRouter models (e.g. a stronger model for discovery, a cheaper one for the 223 extract calls). Both should support structured outputs (`response_format` / JSON schema). **Theme discovery spend counts toward the $6 Gate 2 budget** (~9 batch calls + 1 synthesis call before the 223 extract calls).



Manual setup (without scripts):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # or: copy .env.example .env
```



## Discover themes (LLM)

Builds a three-tier taxonomy from `data/reviews.json` in batches of 25 (up to 5 themes per batch as `theme_one`…`theme_five`), synthesizes `themes.json` / `theme_set.md`, then optionally runs extraction.

```bash
# Windows
.\scripts\discover.ps1

# macOS / Linux
./scripts/discover.sh

# or directly
python discover_themes.py
```

Useful flags:

```bash
python discover_themes.py --discover-only
python discover_themes.py --discover-only --limit-batches 1
python discover_themes.py --extract-only
python discover_themes.py --extract-only --themes-dir out/themes/theme-20260731_175600
```



### Theme output folders

Each discovery run creates an immutable folder:

```
out/themes/theme-YYYYMMDD_HHMMSS/
  discovery_batches.json
  themes.json
  theme_set.md
  discovery_summary.json
```

Successful synthesis also refreshes stable latest copies:

- `data/themes.json`
- `data/theme_set.md`
- `data/discovery_batches.json`
- `data/discovery_summary.json`



## Extract themes (assignment pipeline)

Uses the taxonomy in `data/themes.json` (or a pinned `--themes-dir`) to label each review.

```bash
# Windows
.\scripts\run.ps1
.\scripts\run.ps1 --limit 10

# macOS / Linux
./scripts/run.sh
./scripts/run.sh --limit 10

# or directly
python pipeline.py
python pipeline.py --limit 10
python pipeline.py --themes-dir out/themes/theme-20260731_175600
```

Concurrency is controlled by the static `MAX_WORKERS` value in `pipeline.py` / `src/config.py` (default `8`). Discovery batch concurrency uses `DISCOVERY_MAX_WORKERS` (default `4`).

## Extraction outputs

Each extract run writes:

1. **Datetime archive** (never overwrites prior runs): `out/runs/YYYYMMDD_HHMMSS/`
  - `categorisation.json` — assessed categorisation structure
  - `flat.json` — checker projection
  - `run_summary.json` — machine summary (cost from OpenRouter `usage.cost`)
  - `run_summary.md` — human-readable summary derived from the JSON
2. **Stable latest copies** (overwritten every checkpoint / run):
  - `out/flat.json`
  - `out/categorisation.json`
  - `out/run_summary.json`
  - `out/run_summary.md`

Artefacts are checkpointed after **every** review under a thread lock with atomic file replace, so a crash mid-run still leaves prior results on disk.

## Score

```bash
# Preferred (sets PYTHONUTF8=1 for Windows consoles)
.\scripts\score.ps1
# or: ./scripts/score.sh

# Direct (on Windows, set PYTHONUTF8=1 in the same shell first)
python score.py --pred out/flat.json
```

`score.py` is the unmodified Compethic checker (stdlib only). Unicode-safe printing on Windows comes from `PYTHONUTF8=1` in the setup/run/discover/score scripts, not from edits inside `score.py`.

Standard library only; no API key. TREE should report `ok` when assignments stay inside the active taxonomy.

## Theme set

Readable definitions: `[data/theme_set.md](data/theme_set.md)`  
Machine registry: `[data/themes.json](data/themes.json)`  
Historical generations: `out/themes/theme-*/` 



## Prompt roots (optional)

Core prompt text can be overridden in `.env` (defaults live in `[src/prompts.py](src/prompts.py)` when unset):


| Env var                                | Role                    | Injected placeholders                         |
| -------------------------------------- | ----------------------- | --------------------------------------------- |
| `PROMPT_REVIEW_SYSTEM_ROOT`            | Extract system prompt   | `{taxonomy_block}` (auto-appended if omitted) |
| `PROMPT_REVIEW_USER_TEMPLATE`          | Extract user prompt     | `{rating}` `{title}` `{content_en}`           |
| `PROMPT_THEME_DISCOVERY_SYSTEM_ROOT`   | Discovery system prompt | —                                             |
| `PROMPT_THEME_DISCOVERY_USER_TEMPLATE` | Discovery user prompt   | `{batch_size}` `{batch_reviews}`              |
| `PROMPT_THEME_SYNTHESIS_SYSTEM_ROOT`   | Synthesis system prompt | —                                             |
| `PROMPT_THEME_SYNTHESIS_USER_TEMPLATE` | Synthesis user prompt   | `{candidates_json}` `{repair_section}`        |


Use `\n` for newlines in single-line `.env` values. Dynamic data (taxonomy paths, review text, batch lists, candidate JSON) is always injected by code so structured-output generation keeps working.

## Cross-platform notes

- Setup/run/discover/score scripts set `PYTHONUTF8=1` so Windows consoles do not choke on Unicode in logs or when running `score.py` (the checker itself is left unmodified).
- On Windows, `scripts/setup.ps1` prefers the `py -3` launcher, then `python` / `python3`.
- All artefact paths in summaries use repo-relative posix form, e.g. `feedback-themes-case/out/runs/20260731_174835` (never a machine-absolute path).
- `--themes-dir` accepts `out/themes/theme-...`, `feedback-themes-case/out/themes/theme-...`, backslashes, or an absolute path.
- Checkpoint writes retry on file locks (common when an IDE has `out/flat.json` open). Prefer closing previews of live output files if writes keep failing.
- Paths and `.env` are always read/written as UTF-8; JSON/Markdown artefacts use LF newlines on every OS.

## Notes

See [NOTES.html](NOTES.html) for architecture, decisions, sample cost/timing charts, and the five-failure section (refresh numbers from `out/run_summary.json` after a full run).