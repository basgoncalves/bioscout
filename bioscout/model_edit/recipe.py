"""A model build, written down.

A recipe is a YAML file: a base model and an ordered list of operations. Each
step's output feeds the next unless the step says ``from:``, which is what makes
the SO/CEINMS pair expressible -- they are a *branch*, not a chain:

    scaled.osim -> scaled_opt_N10.osim ------------------> (CEINMS model)
                                        \\
                                         -> _mvicx3.00.osim (SO model)

Today that sequence lives as imperative code in the project's ``settings.py``
and as an interactive session for the moment-arm variants, which is why the
``gpk_optimised`` models could not be rebuilt from their provenance -- there was
none. A recipe is re-runnable, diffable, and reviewable.

Example::

    base: "generic models/GPK/GPK_generic_modWO.osim"
    out_dir: "simulations/Athlete_03/25_03_31/3_iterations/gpk"
    steps:
      - op: scale
        static_trc: "../../2_experimental/Static_01/marker_experimental.trc"
        marker_set: "setupFiles/markers_powerlifter.xml"
        mass: 91.01
        save_as: scaled.osim
      - op: muscle_opt
        n_eval: 10
        save_as: scaled_opt_N10.osim          # the CEINMS model
      - op: mvic
        factor: 3.0
        save_as: scaled_opt_N10_mvicx3.00.osim  # the SO model
      - op: check_paths                        # verify, from the CEINMS model
        from: scaled_opt_N10.osim

Paths are resolved against ``root`` (the project directory), or against the
recipe file's own folder when no root is given, so a recipe is portable.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .run import apply, plan
from .spec import OpResult, get

__all__ = ["load", "run", "validate_recipe", "RecipeError", "describe"]

_STEP_KEYS = {"op", "save_as", "from", "out", "out_dir", "overwrite", "when"}


class RecipeError(ValueError):
    pass


def load(path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:                                      # pragma: no cover
        raise RecipeError("PyYAML is required to read a recipe "
                          "(pip install pyyaml)") from None
    with open(str(path), "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise RecipeError(f"{path}: expected a mapping at the top level")
    if "steps" not in doc:
        raise RecipeError(f"{path}: no 'steps:' list")
    if not isinstance(doc["steps"], list) or not doc["steps"]:
        raise RecipeError(f"{path}: 'steps:' must be a non-empty list")
    return doc


def _resolve(root: Path, value) -> str:
    p = Path(str(value))
    return str(p if p.is_absolute() else (root / p))


def validate_recipe(doc: Dict[str, Any], root: Path) -> List[str]:
    """Check the whole recipe before running any of it.

    A recipe that fails on step 7 after step 3 spent an hour on muscle
    optimisation is worse than useless, so every op name, every parameter name
    and every ``from:`` reference is checked up front.
    """
    problems: List[str] = []
    if not doc.get("base"):
        problems.append("no 'base:' model")
    else:
        b = _resolve(root, doc["base"])
        if not os.path.exists(b):
            problems.append(f"base model not found: {b}")

    produced = {}
    for i, step in enumerate(doc["steps"], 1):
        if not isinstance(step, dict) or "op" not in step:
            problems.append(f"step {i}: needs an 'op:' key")
            continue
        name = step["op"]
        try:
            op = get(name)
        except KeyError as e:
            problems.append(f"step {i}: {e}")
            continue
        src = step.get("from")
        if src and src not in produced and not os.path.exists(_resolve(root, src)):
            problems.append(
                f"step {i} ({name}): from: {src!r} is neither a file nor "
                f"the save_as of an earlier step "
                f"({', '.join(produced) or 'none so far'})")
        known = {p.name for p in op.params} | _STEP_KEYS
        unknown = set(step) - known
        if unknown:
            problems.append(f"step {i} ({name}): unknown key(s) "
                            f"{', '.join(sorted(unknown))}")
        for p in op.required_params:
            if step.get(p.name) is None:
                problems.append(f"step {i} ({name}): '{p.name}' is required — {p.help}")
        if op.writes_model and not (step.get("save_as") or step.get("out") or op.suffix):
            problems.append(f"step {i} ({name}): needs 'save_as:' — this op has "
                            f"no default output name")
        if step.get("save_as"):
            produced[step["save_as"]] = i
    return problems


def describe(doc: Dict[str, Any], root: Path) -> List[str]:
    """Human-readable plan, including which steps need OpenSim."""
    lines = [f"base: {_resolve(root, doc.get('base', '?'))}"]
    if doc.get("out_dir"):
        lines.append(f"out_dir: {_resolve(root, doc['out_dir'])}")
    for i, step in enumerate(doc["steps"], 1):
        try:
            op = get(step.get("op", ""))
        except KeyError:
            lines.append(f"  {i}. {step.get('op')!r}  <- UNKNOWN OP")
            continue
        src = step.get("from") or "(previous)"
        dst = step.get("save_as") or step.get("out") or (
            f"<auto:{op.suffix}>" if op.suffix else "(no model)")
        flag = "" if not op.needs_opensim else "  [needs OpenSim]"
        lines.append(f"  {i}. {op.name:16s} {src} -> {dst}{flag}")
    return lines


def run(path, root=None, *, dry_run: bool = False,
        overwrite: bool = False, log=print) -> List[OpResult]:
    """Execute a recipe. Stops at the first failure and says which step it was."""
    path = Path(path)
    doc = load(path)
    root = Path(root) if root else path.parent
    root = root.resolve()

    problems = validate_recipe(doc, root)
    if problems:
        raise RecipeError(f"{path}:\n  - " + "\n  - ".join(problems))

    out_dir: Optional[str] = _resolve(root, doc["out_dir"]) if doc.get("out_dir") else None
    current = _resolve(root, doc["base"])
    produced: Dict[str, str] = {}
    results: List[OpResult] = []

    for i, step in enumerate(doc["steps"], 1):
        step = dict(step)
        name = step.pop("op")
        save_as = step.pop("save_as", None)
        src_ref = step.pop("from", None)
        out = step.pop("out", None)
        step_dir = step.pop("out_dir", None)
        step_over = step.pop("overwrite", None)
        step.pop("when", None)

        src = current
        if src_ref:
            src = produced.get(src_ref) or _resolve(root, src_ref)

        target = None
        if out:
            target = _resolve(root, out)
        elif save_as:
            base_dir = _resolve(root, step_dir) if step_dir else (out_dir or str(Path(src).parent))
            target = str(Path(base_dir) / save_as)

        # Path-valued parameters are resolved against the project root too, so
        # a recipe can be moved without rewriting every line.
        op = get(name)
        for p in op.params:
            if p.kind == "path" and step.get(p.name):
                step[p.name] = _resolve(root, step[p.name])

        log(f"[model-edit] step {i}/{len(doc['steps'])}: {name}"
            f"  {Path(src).name} -> {Path(target).name if target else '(no model)'}")
        res = apply(name, src, target,
                    out_dir=(_resolve(root, step_dir) if step_dir else out_dir),
                    overwrite=bool(step_over if step_over is not None else overwrite),
                    dry_run=dry_run, **step)
        for m in res.messages:
            log(m)
        results.append(res)
        if not res.ok:
            log(f"[model-edit] step {i} ({name}) FAILED — {res.reason}")
            log(f"[model-edit] stopping. Steps 1..{i - 1} are on disk and can be "
                f"reused with `from:`.")
            break
        if res.model:
            current = res.model
            if save_as:
                produced[save_as] = res.model
    return results
