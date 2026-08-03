"""Applying an operation: validate, resolve the output path, delegate.

This is the only place that turns a dict of user-supplied strings into a call.
Everything upstream (prompt, argparse, recipe, GUI) produces the same dict and
goes through here, so a value is coerced and checked once rather than once per
front end.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .naming import prepare_out
from .spec import Op, OpResult, get

__all__ = ["apply", "coerce", "validate", "plan", "MissingParam", "BadParam"]


class MissingParam(ValueError):
    pass


class BadParam(ValueError):
    pass


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    raise BadParam(f"{v!r} is not a yes/no value")


def _as_list(v):
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return list(v)
    # "a, b c" -> ["a","b","c"] — commas and whitespace both separate, because
    # a shell and a YAML file and a text box all disagree about which to use.
    return [t for t in str(v).replace(",", " ").split() if t]


def coerce(param, value):
    """Turn one raw value into the type the op expects, or raise :class:`BadParam`."""
    if value is None:
        return None
    k = param.kind
    try:
        if k == "float":
            return float(value)
        if k == "int":
            return int(value)
        if k == "bool":
            return _as_bool(value)
        if k in ("str", "choice"):
            return str(value)
        if k == "path":
            return str(value)
        if k == "list[str]":
            return _as_list(value)
        if k == "list[float]":
            return [float(x) for x in _as_list(value)]
    except BadParam:
        raise
    except Exception as e:                                   # noqa: BLE001
        raise BadParam(f"{param.name}: {value!r} is not a valid {k} ({e})") from None
    raise BadParam(f"{param.name}: unhandled kind {k!r}")


def validate(op: Op, params: Dict[str, Any], model=None) -> Dict[str, Any]:
    """Coerce and check every parameter. Returns the cleaned dict.

    Unknown keys are an error rather than being ignored: a typo'd key in a YAML
    recipe that is silently dropped means the run does something other than what
    the file says, and the file is the record of what you did.
    """
    known = {p.name for p in op.params}
    unknown = set(params) - known - {"out", "out_dir", "overwrite", "save_as", "from"}
    if unknown:
        raise BadParam(f"{op.name}: unknown parameter(s) {', '.join(sorted(unknown))}. "
                       f"Known: {', '.join(sorted(known)) or '(none)'}")
    clean: Dict[str, Any] = {}
    for p in op.params:
        raw = params.get(p.name, p.default)
        if raw is None:
            if p.required:
                raise MissingParam(f"{op.name}: {p.name} is required — {p.help}")
            clean[p.name] = None
            continue
        v = coerce(p, raw)
        if p.choices and v not in p.choices:
            raise BadParam(f"{op.name}: {p.name} must be one of "
                           f"{', '.join(map(str, p.choices))}, got {v!r}")
        if p.kind == "path" and p.required and not os.path.exists(str(v)):
            raise BadParam(f"{op.name}: {p.name} not found: {v}")
        clean[p.name] = v
    return clean


def plan(name: str, model, out=None, *, out_dir=None, overwrite=False,
         **params) -> Dict[str, Any]:
    """Resolve what :func:`apply` would do, without doing it."""
    op = get(name)
    clean = validate(op, params, model)
    resolved: Optional[str] = None
    if op.writes_model:
        from .ops import SUFFIX_HOOKS
        hook = SUFFIX_HOOKS.get(op.name)
        suffix_params = hook(clean) if hook else clean
        resolved = str(prepare_out(model, out, op.suffix, suffix_params,
                                   out_dir=out_dir, overwrite=True)) \
            if (out or op.suffix) else None
    return {"op": op.name, "model": str(model), "out": resolved,
            "params": clean, "needs_opensim": op.needs_opensim,
            "writes_model": op.writes_model, "notes": op.notes}


def apply(name: str, model, out=None, *, out_dir=None, overwrite=False,
          dry_run=False, **params) -> OpResult:
    """Run one operation.

    ``model`` is the input .osim. ``out`` is optional when the op declares a
    suffix; see :mod:`bioscout.model_edit.naming` for the rule.
    """
    op = get(name)
    model = Path(model)
    if not model.exists():
        return OpResult(False, name, str(model), reason=f"model not found: {model}")

    try:
        clean = validate(op, params, model)
    except (MissingParam, BadParam) as e:
        return OpResult(False, name, str(model), reason=str(e))

    # Order matters. "that file already exists" is the LEAST interesting reason
    # to stop, so it is checked last: an op that cannot run here, or a parameter
    # that names something absent from the model, should say so rather than
    # complain about an output path it was never going to reach.
    if op.needs_opensim and not dry_run:
        try:
            from bioscout.utils import get_openSim
            get_openSim()
        except Exception as e:                               # noqa: BLE001
            return OpResult(False, name, str(model), reason=(
                f"{name} needs the OpenSim Python bindings, which are not "
                f"importable here ({type(e).__name__}: {e}). Ops that do not "
                f"need them run anywhere — see `model_edit list`."))

    resolved = None
    if op.writes_model:
        from .ops import SUFFIX_HOOKS
        hook = SUFFIX_HOOKS.get(op.name)
        suffix_params = hook(clean) if hook else clean
        try:
            resolved = prepare_out(model, out, op.suffix, suffix_params,
                                   out_dir=out_dir, overwrite=overwrite or dry_run)
        except Exception as e:                               # noqa: BLE001
            return OpResult(False, name, str(model), reason=str(e))

    if dry_run:
        return OpResult(True, name, str(model),
                        str(resolved) if resolved else None,
                        messages=[f"[model-edit] DRY RUN — would write {resolved}"
                                  if resolved else
                                  f"[model-edit] DRY RUN — {name} writes no model"])

    try:
        res = op.fn(model, resolved, **clean)
    except Exception as e:                                   # noqa: BLE001
        return OpResult(False, name, str(model), reason=f"{type(e).__name__}: {e}")

    if res is None:
        return OpResult(False, name, str(model),
                        reason=f"{name} returned nothing — this is a bug in the op")
    # An op that claims success must have produced the file it claims.
    if res.ok and op.writes_model and res.model and not os.path.exists(res.model):
        return OpResult(False, name, str(model), reason=(
            f"{name} reported success but {res.model} does not exist"))
    return res
