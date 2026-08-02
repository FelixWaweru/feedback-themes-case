"""Cross-platform filesystem and stdio helpers."""

from __future__ import annotations

import errno
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src import config

_REPLACE_RETRIES = 8
_REPLACE_BASE_DELAY_S = 0.05
_RETRYABLE_WINERRORS = frozenset({5, 32})  # ACCESS_DENIED, SHARING_VIOLATION
_RETRYABLE_ERRNOS = frozenset(
    {
        errno.EACCES,
        errno.EPERM,
        getattr(errno, "EBUSY", errno.EACCES),
    }
)


def configure_stdio() -> None:
    """Force UTF-8 on stdout/stderr when the console encoding is not UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        encoding = (getattr(stream, "encoding", None) or "").lower()
        if encoding.replace("-", "") in ("utf8", "utf_8"):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — best-effort on exotic streams
            pass


def _is_retryable_os_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror in _RETRYABLE_WINERRORS:
        return True
    return getattr(exc, "errno", None) in _RETRYABLE_ERRNOS


def _cleanup_tmp(tmp: Path) -> None:
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text via temp file + replace, with retries for locked targets."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    # newline="\n" keeps LF artefacts on Windows/macOS/Linux.
    tmp.write_text(text, encoding=encoding, newline="\n")

    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(tmp, path)
            return
        except OSError as exc:
            if not _is_retryable_os_error(exc):
                _cleanup_tmp(tmp)
                raise
            time.sleep(_REPLACE_BASE_DELAY_S * (attempt + 1))

    # Direct overwrite with the same retry policy (not atomic, still durable).
    last_error: OSError | None = None
    for attempt in range(_REPLACE_RETRIES):
        try:
            path.write_text(text, encoding=encoding, newline="\n")
            _cleanup_tmp(tmp)
            return
        except OSError as exc:
            last_error = exc
            if not _is_retryable_os_error(exc):
                _cleanup_tmp(tmp)
                raise
            time.sleep(_REPLACE_BASE_DELAY_S * (attempt + 1))

    _cleanup_tmp(tmp)
    if last_error is not None:
        raise last_error
    raise OSError(f"failed to write {path}")


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def atomic_copy_file(src: Path, dest: Path) -> None:
    """Copy file contents using atomic_write (avoids shutil lock issues on Windows)."""
    src = Path(src)
    dest = Path(dest)
    data = src.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(data)
        for attempt in range(_REPLACE_RETRIES):
            try:
                os.replace(tmp, dest)
                return
            except OSError as exc:
                if not _is_retryable_os_error(exc):
                    _cleanup_tmp(tmp)
                    raise
                time.sleep(_REPLACE_BASE_DELAY_S * (attempt + 1))
        dest.write_bytes(data)
        _cleanup_tmp(tmp)
        return
    atomic_write_text(dest, text, encoding="utf-8")


def unique_dir(parent: Path, prefix: str) -> Path:
    """Create ``{prefix}YYYYMMDD_HHMMSS`` or ``{prefix}-YYYYMMDD_HHMMSS`` under parent.

    If ``prefix`` already ends with ``-`` (e.g. ``theme-``), no extra hyphen is added.
    On same-second collision, appends ``-1``, ``-2``, …
    """
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not prefix:
        base_name = stamp
    elif prefix.endswith("-"):
        base_name = f"{prefix}{stamp}"
    else:
        base_name = f"{prefix}-{stamp}"

    candidate = parent / base_name
    try:
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate
    except FileExistsError:
        pass

    for n in range(1, 1000):
        candidate = parent / f"{base_name}-{n}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"could not allocate unique directory under {parent}")


def resolve_under_repo(user_path: str | Path) -> Path:
    """Resolve a CLI/summary path to an absolute path under (or absolute outside) the repo.

    Accepts:
    - absolute paths
    - ``out/...`` / ``data/...``
    - ``feedback-themes-case/out/...`` (repo-name prefix from summaries)
    - Windows backslash forms
    """
    raw = os.path.expanduser(str(user_path).strip())
    path = Path(raw)

    if path.is_absolute():
        return path.resolve()

    # Normalize to posix for prefix checks
    posix = path.as_posix().lstrip("./")
    repo_prefix = f"{config.ROOT.name}/"
    if posix.startswith(repo_prefix):
        posix = posix[len(repo_prefix) :]
    return (config.ROOT / posix).resolve()
