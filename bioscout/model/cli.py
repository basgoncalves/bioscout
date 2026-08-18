"""Command line for ``bioscout.model``.

    python -m bioscout.model --verify                    # cwd
    python -m bioscout.model --verify models "generic models"
    python -m bioscout.model --verify --strict --json geometry.json
    bioscout --model                                     # same, via the main CLI
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from .verify import format_text, verify_tree

__all__ = ["build_parser", "main", "run"]

_DEFAULT_ROOTS = ("models", "generic models", "Models", "simulations")


def _default_roots(project: Path) -> List[Path]:
    """The folders a bioscout project keeps models in, that exist here.

    ``simulations`` is included because bioscout 2.x keeps the per-iteration
    copy of a subject's model inside the session tree — those copies are exactly
    the ones a folder move breaks, and they are the ones actually solved with.
    """
    found = [project / name for name in _DEFAULT_ROOTS if (project / name).is_dir()]
    return found or [project]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bioscout model",
        description="Check that every .osim can find the bone meshes it references, "
                    "from that model's own folder. A model that cannot loads in "
                    "OpenSim with no bones and no error.")
    p.add_argument("roots", nargs="*", metavar="FOLDER_OR_OSIM",
                   help="what to check (default: the model folders of the project)")
    p.add_argument("--verify", action="store_true",
                   help="run the check (the only mode today; accepted for symmetry "
                        "with the reorganiser)")
    p.add_argument("--project", default=None, metavar="PATH",
                   help="project root used to pick default roots (default: cwd)")
    p.add_argument("--search", action="append", default=None, metavar="DIR",
                   help="extra geometry folder to try; repeatable. Resolving only "
                        "through one of these is reported, not hidden.")
    p.add_argument("--strict", action="store_true",
                   help="fail on models that resolve only via a non-local tier "
                        "(../Geometry, bioscout's bundle, an absolute path, or "
                        "filename case). Portable-or-nothing.")
    p.add_argument("--no-recursive", action="store_true",
                   help="do not descend into subfolders")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="list every reference, including the ones that are fine")
    p.add_argument("--json", default=None, metavar="FILE",
                   help="also write the full report as JSON")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="print nothing; use the exit code (0 ok, 1 problems)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    project = Path(args.project or ".").resolve()
    roots = [Path(r) for r in args.roots] if args.roots else _default_roots(project)

    report = verify_tree(roots, extra_search=args.search, strict=args.strict,
                         recursive=not args.no_recursive)

    if not args.quiet:
        sys.stdout.write(format_text(report, verbose=args.verbose))

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"wrote {out}")

    return report.exit_code()


def run(project=None) -> int:
    """Entry point used by ``bioscout --model`` with no further flags."""
    return main(["--verify"] + (["--project", str(project)] if project else []))


if __name__ == "__main__":
    raise SystemExit(main())
