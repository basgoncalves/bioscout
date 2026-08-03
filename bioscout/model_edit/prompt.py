"""Interactive prompt helpers, in one place.

``change_moment_arms/cli.py`` and ``__main__.py``'s ``run_tps_mode`` each carry
their own byte-identical copy of ``_ask`` and ``_pick``. This is that code,
once, with the model-aware bits added: a parameter can name a
``choices_from`` and the prompt fills the option list from the model in hand.

The house conventions these preserve, because users have learned them:
defaults shown in ``[brackets]``, Enter accepts, numbered pick lists, and
nothing is written until a confirmation step.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from .introspect import options_for
from .run import BadParam, coerce

__all__ = ["ask", "pick", "confirm", "ask_param", "ask_params"]


def ask(prompt: str, default: Optional[str] = None,
        choices: Optional[Sequence[str]] = None) -> str:
    """Free-text question with a default and optional validation."""
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return str(default)
        if not raw:
            continue
        if choices and raw not in choices:
            print(f"  choose one of: {', '.join(map(str, choices))}")
            continue
        return raw


def pick(prompt: str, options: Sequence[str], default: Optional[str] = None,
         allow_multiple: bool = False, allow_all: bool = False) -> Any:
    """Numbered chooser. Returns a string, or a list when ``allow_multiple``.

    Accepts numbers or the names themselves, because a list of 100 muscles is
    faster to type than to count through.
    """
    options = list(options)
    if not options:
        raise ValueError(f"{prompt}: nothing to choose from")
    if allow_all:
        options = options + ["ALL"]
    width = len(str(len(options)))
    for i, o in enumerate(options, 1):
        print(f"  {i:>{width}}. {o}")
    hint = "numbers or names, space-separated" if allow_multiple else "number or name"
    while True:
        raw = ask(f"{prompt} ({hint})", default)
        tokens = raw.replace(",", " ").split() if allow_multiple else [raw]
        out, bad = [], []
        for t in tokens:
            if t.isdigit() and 1 <= int(t) <= len(options):
                out.append(options[int(t) - 1])
            elif t in options:
                out.append(t)
            else:
                bad.append(t)
        if bad:
            print(f"  not an option: {', '.join(bad)}")
            continue
        return out if allow_multiple else out[0]


def confirm(prompt: str, default: bool = False) -> bool:
    d = "yes" if default else "no"
    return ask(f"{prompt} (yes/no)", d, choices=("yes", "no", "y", "n")).lower().startswith("y")


def ask_param(param, model=None, current=None):
    """Ask for one :class:`~bioscout.model_edit.spec.Param`, typed and validated.

    This is the function that makes the registry pay off: every op gets a
    correct prompt, with the right option list and the right coercion, without
    anyone writing prompt code per op.
    """
    label = f"{param.label} — {param.help}"
    default = current if current is not None else param.default

    options = list(param.choices)
    if param.choices_from and model is not None:
        try:
            options = options_for(param.choices_from, model)
        except Exception as e:                               # noqa: BLE001
            print(f"  (could not read {param.choices_from} from the model: {e})")
            options = []

    if param.kind == "bool":
        return confirm(label, bool(default))

    if options:
        multi = param.kind.startswith("list")
        print(f"\n{label}")
        if len(options) > 40:
            # A 100-muscle numbered list is unreadable; type it or say ALL.
            print(f"  ({len(options)} options — type names, or ALL)")
            while True:
                raw = ask("value", None if param.required else (default if default else "skip"))
                if raw == "skip" and not param.required:
                    return None
                vals = raw.replace(",", " ").split()
                bad = [v for v in vals if v not in options and v.upper() != "ALL"]
                if bad:
                    print(f"  not in the model: {', '.join(bad)}")
                    continue
                return vals if multi else vals[0]
        chosen = pick("value", options,
                      default=(str(default) if default not in (None, "") else None),
                      allow_multiple=multi, allow_all=multi)
        return chosen

    while True:
        raw = ask(label, None if param.required else
                  ("skip" if default is None else str(default)))
        if raw == "skip" and not param.required:
            return None
        try:
            return coerce(param, raw)
        except BadParam as e:
            print(f"  {e}")


def ask_params(op, model=None, preset=None) -> dict:
    """Walk every parameter of an op. Presets are shown as the default."""
    preset = preset or {}
    out = {}
    for p in op.params:
        out[p.name] = ask_param(p, model=model, current=preset.get(p.name))
    return out
