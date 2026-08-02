"""Theme taxonomy loading, prompt formatting, and path validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_SEP = " > "


@dataclass(frozen=True, slots=True)
class ThemePath:
    strategic: str
    midlevel: str
    specific: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.strategic, self.midlevel, self.specific)

    @property
    def label(self) -> str:
        return f"{self.strategic}{_PATH_SEP}{self.midlevel}{_PATH_SEP}{self.specific}"


class ThemeTaxonomy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.raw = data
        self.version = str(data.get("version", "unknown"))
        self.paths: list[ThemePath] = []
        self._by_key: dict[tuple[str, str, str], ThemePath] = {}
        self._by_key_cf: dict[tuple[str, str, str], ThemePath] = {}
        self._by_specific: dict[str, list[ThemePath]] = {}
        self._by_specific_cf: dict[str, list[ThemePath]] = {}
        self._by_label: dict[str, ThemePath] = {}
        self._by_label_cf: dict[str, ThemePath] = {}
        self._definitions: dict[tuple[str, str, str], str] = {}
        self._load(data)

    @classmethod
    def load(cls, path: Path) -> ThemeTaxonomy:
        with path.open(encoding="utf-8") as fh:
            return cls(json.load(fh))

    def _load(self, data: dict[str, Any]) -> None:
        mid_parents: dict[str, str] = {}
        specific_parents: dict[str, tuple[str, str]] = {}
        for strategic in data.get("strategic", []):
            s_name = strategic["name"].strip()
            for midlevel in strategic.get("midlevel", []):
                m_name = midlevel["name"].strip()
                if m_name in mid_parents and mid_parents[m_name] != s_name:
                    raise ValueError(
                        f"midlevel {m_name!r} under multiple strategic themes"
                    )
                mid_parents[m_name] = s_name
                for specific in midlevel.get("specific", []):
                    sp_name = specific["name"].strip()
                    parent = (s_name, m_name)
                    if sp_name in specific_parents and specific_parents[sp_name] != parent:
                        raise ValueError(
                            f"specific {sp_name!r} under multiple midlevel themes"
                        )
                    specific_parents[sp_name] = parent
                    path = ThemePath(s_name, m_name, sp_name)
                    self.paths.append(path)
                    self._by_key[path.key] = path
                    self._by_key_cf[
                        (s_name.casefold(), m_name.casefold(), sp_name.casefold())
                    ] = path
                    self._by_specific.setdefault(sp_name, []).append(path)
                    self._by_specific_cf.setdefault(sp_name.casefold(), []).append(path)
                    self._by_label[path.label] = path
                    self._by_label_cf[path.label.casefold()] = path
                    self._definitions[path.key] = str(specific.get("definition", "")).strip()

    def validate_triple(
        self, strategic: str, midlevel: str, specific: str
    ) -> ThemePath | None:
        key = (strategic.strip(), midlevel.strip(), specific.strip())
        return self._by_key.get(key)

    def resolve_path_label(self, label: str) -> ThemePath | None:
        """Resolve a full ``A > B > C`` label (exact, then casefold, then repair)."""
        text = label.strip()
        if not text:
            return None
        hit = self._by_label.get(text) or self._by_label_cf.get(text.casefold())
        if hit is not None:
            return hit
        parts = [p.strip() for p in text.split(_PATH_SEP) if p.strip()]
        if len(parts) >= 3:
            return self.resolve_assignment(parts[0], parts[1], _PATH_SEP.join(parts[2:]))
        if len(parts) == 1:
            return self.resolve_assignment("", "", parts[0])
        if len(parts) == 2:
            return self.resolve_assignment(parts[0], parts[1], "")
        return None

    def resolve_assignment(
        self, strategic: str, midlevel: str, specific: str
    ) -> ThemePath | None:
        """Resolve a possibly scrambled triple to a known taxonomy path.

        Order: exact match → segment/path parse → unique specific name →
        casefold exact names.
        """
        s = strategic.strip()
        m = midlevel.strip()
        sp = specific.strip()

        exact = self.validate_triple(s, m, sp)
        if exact is not None:
            return exact

        segments = self._collect_segments(s, m, sp)
        if segments:
            from_segments = self._match_from_segments(segments)
            if from_segments is not None:
                return from_segments

        for candidate in (sp, segments[-1] if segments else ""):
            if not candidate:
                continue
            by_specific = self._unique_specific(candidate)
            if by_specific is not None:
                return by_specific

        if s and m and sp:
            cf = self._by_key_cf.get((s.casefold(), m.casefold(), sp.casefold()))
            if cf is not None:
                return cf

        return None

    @staticmethod
    def _collect_segments(strategic: str, midlevel: str, specific: str) -> list[str]:
        parts: list[str] = []
        for field in (strategic, midlevel, specific):
            if not field:
                continue
            if _PATH_SEP in field:
                parts.extend(p.strip() for p in field.split(_PATH_SEP) if p.strip())
            else:
                parts.append(field)
        # Collapse consecutive duplicate segment names (common model scramble).
        collapsed: list[str] = []
        for part in parts:
            if not collapsed or collapsed[-1].casefold() != part.casefold():
                collapsed.append(part)
        return collapsed

    def _match_from_segments(self, segments: list[str]) -> ThemePath | None:
        n = len(segments)
        # Sliding windows of three consecutive segments
        hits: list[ThemePath] = []
        for i in range(n - 2):
            triple = self.validate_triple(segments[i], segments[i + 1], segments[i + 2])
            if triple is None:
                triple = self._by_key_cf.get(
                    (
                        segments[i].casefold(),
                        segments[i + 1].casefold(),
                        segments[i + 2].casefold(),
                    )
                )
            if triple is not None:
                hits.append(triple)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # Prefer the last match (often the most specific scramble tail).
            return hits[-1]

        # Any segment that uniquely identifies a specific theme name.
        for seg in reversed(segments):
            hit = self._unique_specific(seg)
            if hit is not None:
                return hit
        return None

    def _unique_specific(self, name: str) -> ThemePath | None:
        text = name.strip()
        if not text:
            return None
        matches = self._by_specific.get(text) or self._by_specific_cf.get(text.casefold())
        if matches is not None and len(matches) == 1:
            return matches[0]
        return None

    def prompt_block(self) -> str:
        lines = [
            "You may ONLY assign themes from this exact taxonomy.",
            "Return only path values copied EXACTLY from the allowed list below.",
            "Do not invent or reorder tier names.",
            "Assign a path when the review mentions that path's subject — praise, "
            "complaint, or neutral all count. Do not leave assignments empty only "
            "because the review is positive.",
            "Empty assignments only when no allowed path's subject appears in the review.",
            "Prefer 1–3 paths when multiple distinct subjects appear.",
            "Do not invent new theme names. Do not summarize sentiment alone as a theme.",
            "",
            "Allowed paths:",
        ]
        for path in self.paths:
            definition = self._definitions.get(path.key, "")
            lines.append(f"- {path.label}")
            if definition:
                lines.append(f"  Definition: {definition}")
        return "\n".join(lines)

    def registry_for_output(self) -> dict[str, Any]:
        return self.raw
