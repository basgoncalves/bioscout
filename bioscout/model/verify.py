"""Verify that every ``.osim`` in a tree can find every mesh it references.

One model::

    from bioscout.model import verify_model
    report = verify_model("subject021.osim")
    print(report.headline)          # "3 refs unresolved — OpenSim will draw no bone"

A whole project::

    report = verify_tree(["models", "generic models"])
    print(format_text(report))
    raise SystemExit(report.exit_code())

The result objects are plain dataclasses with ``to_dict()``, so the same run can
be printed for a human and written as ``model_geometry.json`` next to the log —
machine-readable status is what makes a 29-subject batch auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
from xml.etree import ElementTree as ET

from .geometry import (PASSING_TIERS, TIER_ORDER, GeometryRef, clear_cache,
                       geometry_refs, resolve_ref)

__all__ = ["ModelReport", "TreeReport", "verify_model", "verify_tree",
           "find_models", "format_text"]

_FAIL_TIERS = ("empty", "missing", "unreadable")


# --------------------------------------------------------------------------- #
@dataclass
class ModelReport:
    path: Path
    refs: List[GeometryRef] = field(default_factory=list)
    error: Optional[str] = None          #: set when the .osim would not parse

    # -- counts ------------------------------------------------------------- #
    @property
    def n_refs(self) -> int:
        return len(self.refs)

    def by_tier(self) -> Dict[str, List[GeometryRef]]:
        out: Dict[str, List[GeometryRef]] = {}
        for r in self.refs:
            out.setdefault(r.tier, []).append(r)
        return out

    @property
    def failing(self) -> List[GeometryRef]:
        return [r for r in self.refs if r.tier in _FAIL_TIERS]

    @property
    def warning(self) -> List[GeometryRef]:
        return [r for r in self.refs
                if r.tier not in _FAIL_TIERS and r.tier not in PASSING_TIERS]

    @property
    def worst_tier(self) -> str:
        """Worst tier present, or ``local`` for a clean model with geometry."""
        if self.error:
            return "unreadable"
        if not self.refs:
            return "none"
        return max((r.tier for r in self.refs), key=TIER_ORDER.index)

    # -- verdicts ----------------------------------------------------------- #
    def ok(self, strict: bool = False) -> bool:
        if self.error:
            return False
        if self.failing:
            return False
        return not (strict and self.warning)

    @property
    def headline(self) -> str:
        if self.error:
            return f"unreadable — {self.error}"
        if not self.refs:
            return "no geometry referenced"
        if self.failing:
            n = sum(r.count for r in self.failing)
            return (f"{n} reference(s) unresolved — OpenSim will load this model "
                    f"WITHOUT those bones")
        if self.warning:
            tiers = sorted({r.tier for r in self.warning}, key=TIER_ORDER.index)
            return (f"resolves, but {len(self.warning)} of {self.n_refs} only via "
                    f"{'/'.join(tiers)} — not portable")
        return f"all {self.n_refs} reference(s) resolve locally"

    def to_dict(self) -> dict:
        return {
            "model": str(self.path),
            "error": self.error,
            "n_refs": self.n_refs,
            "worst_tier": self.worst_tier,
            "headline": self.headline,
            "refs": [
                {"raw": r.raw, "tag": r.tag, "body": r.body, "tier": r.tier,
                 "count": r.count,
                 "resolved": str(r.resolved) if r.resolved else None}
                for r in sorted(self.refs, key=lambda r: (TIER_ORDER.index(r.tier),
                                                          r.raw))
            ],
        }


@dataclass
class TreeReport:
    roots: List[Path] = field(default_factory=list)
    models: List[ModelReport] = field(default_factory=list)
    strict: bool = False

    @property
    def with_geometry(self) -> List[ModelReport]:
        return [m for m in self.models if m.refs or m.error]

    @property
    def broken(self) -> List[ModelReport]:
        return [m for m in self.models if m.failing or m.error]

    @property
    def not_portable(self) -> List[ModelReport]:
        return [m for m in self.models if not m.failing and not m.error and m.warning]

    def ok(self) -> bool:
        return all(m.ok(self.strict) for m in self.models)

    def exit_code(self) -> int:
        return 0 if self.ok() else 1

    def to_dict(self) -> dict:
        return {
            "roots": [str(r) for r in self.roots],
            "strict": self.strict,
            "n_models": len(self.models),
            "n_with_geometry": len(self.with_geometry),
            "n_broken": len(self.broken),
            "n_not_portable": len(self.not_portable),
            "ok": self.ok(),
            "models": [m.to_dict() for m in self.models],
        }


# --------------------------------------------------------------------------- #
def find_models(roots: Iterable, recursive: bool = True) -> List[Path]:
    """Every ``.osim`` under the given files/folders, deduplicated and sorted."""
    seen: Dict[str, Path] = {}
    for root in roots:
        p = Path(root)
        if p.is_file() and p.suffix.lower() == ".osim":
            seen[str(p.resolve())] = p
        elif p.is_dir():
            it = p.rglob("*.osim") if recursive else p.glob("*.osim")
            for m in it:
                if m.is_file():
                    seen[str(m.resolve())] = m
    return [seen[k] for k in sorted(seen)]


def verify_model(model_path, extra_search: Optional[Sequence] = None) -> ModelReport:
    """Resolve every geometry reference in one model, from that model's folder.

    Drops the directory index first, so a second call in the same process sees
    a tree you have just repaired. Within one call — and within one
    ``verify_tree`` — the index is kept, which is where the speed comes from.
    """
    clear_cache()
    return _verify_one(model_path, extra_search)


def _verify_one(model_path, extra_search: Optional[Sequence] = None) -> ModelReport:
    path = Path(model_path)
    try:
        refs = geometry_refs(path)
    except ET.ParseError as exc:
        return ModelReport(path=path, error=f"XML parse error: {exc}")
    except OSError as exc:
        return ModelReport(path=path, error=f"unreadable: {exc}")
    for r in refs:
        resolve_ref(r, path, extra_search)
    return ModelReport(path=path, refs=refs)


def verify_tree(roots: Iterable, extra_search: Optional[Sequence] = None,
                strict: bool = False, recursive: bool = True) -> TreeReport:
    """Verify every model under ``roots``."""
    clear_cache()
    root_paths = [Path(r) for r in roots]
    models = [_verify_one(m, extra_search) for m in find_models(root_paths, recursive)]
    return TreeReport(roots=root_paths, models=models, strict=strict)


# --------------------------------------------------------------------------- #
# text output
# --------------------------------------------------------------------------- #
_TIER_NOTE = {
    "local": "from the model's own folder",
    "parent": "only from ../Geometry — breaks if the model alone is copied",
    "bundled": "only from bioscout's bundled Geometry — not in your project",
    "search": "only from an external search path — machine-local",
    "absolute": "by ABSOLUTE path — will point somewhere else on another computer",
    "case": "only by IGNORING FILENAME CASE — works on Windows, breaks on Linux",
    "empty": "file exists but is ZERO BYTES",
    "missing": "NOT FOUND — no bone will be drawn",
    "unreadable": "model could not be parsed",
}


def _rel(p: Path, roots: Sequence[Path]) -> str:
    for r in roots:
        try:
            return str(p.resolve().relative_to(Path(r).resolve()))
        except ValueError:
            continue
    return str(p)


def format_text(report: TreeReport, verbose: bool = False, max_examples: int = 4) -> str:
    """Human-readable report. Clean models are one line each unless ``verbose``."""
    lines: List[str] = []
    add = lines.append

    add("")
    add("geometry resolution")
    add("-" * 78)

    if not report.models:
        add("  no .osim files found under: " + ", ".join(str(r) for r in report.roots))
        add("-" * 78)
        return "\n".join(lines) + "\n"

    for m in report.models:
        rel = _rel(m.path, report.roots)
        if m.error:
            add(f"  UNREADABLE  {rel}")
            add(f"              {m.error}")
            continue
        if not m.refs:
            if verbose:
                add(f"  --          {rel}  (no geometry referenced)")
            continue

        if m.failing:
            status = "BROKEN  "
        elif m.warning:
            status = "WARN    "
        else:
            status = "ok      "

        if status == "ok      " and not verbose:
            add(f"  ok      {rel}  ({m.n_refs} refs)")
            continue

        add(f"  {status}{rel}  ({m.n_refs} refs)")
        groups = m.by_tier()
        for tier in TIER_ORDER:
            group = groups.get(tier)
            if not group or (tier in PASSING_TIERS and not verbose):
                continue
            add(f"            {len(group)} {tier}: {_TIER_NOTE.get(tier, '')}")
            shown = group if verbose else group[:max_examples]
            for r in shown:
                where = f"  -> {r.resolved}" if r.resolved else ""
                body = f"  [{r.body}]" if r.body else ""
                add(f"              {r.raw}{body}{where}")
            if len(group) > len(shown):
                add(f"              ... and {len(group) - len(shown)} more")

    add("-" * 78)
    n_geo = len(report.with_geometry)
    add(f"{len(report.models)} model(s), {n_geo} referencing geometry, "
        f"{len(report.broken)} broken, {len(report.not_portable)} not portable")
    if report.broken:
        add("BROKEN models load with muscles and markers and NO BONES, silently.")
    if report.not_portable and not report.strict:
        add("Not-portable models resolve here but may not on another machine; "
            "re-run with --strict to fail on them.")
    add("")
    return "\n".join(lines) + "\n"
