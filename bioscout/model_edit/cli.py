"""Command line for model_edit — guided when you have no arguments, flat when you do.

    bioscout --model-edit                    # guided, from the current project
    python -m bioscout.model_edit list
    python -m bioscout.model_edit list --long
    python -m bioscout.model_edit show mvic
    python -m bioscout.model_edit info    --model X.osim
    python -m bioscout.model_edit apply   mvic --model X.osim --factor 3.0
    python -m bioscout.model_edit recipe  build_gpk.yaml --root . --dry-run

Both front ends are built from the registry, so an op added in ``ops/`` shows up
in ``list``, gets ``--flags`` in ``apply``, gets prompts in the guided mode, and
is accepted in a recipe, with no change here.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import List, Optional

from .spec import VERBS, by_verb, get

__all__ = ["run", "main", "build_parser"]

BANNER = "=" * 70


# --------------------------------------------------------------------- shared
def discover_models(project: str, limit: int = 400) -> List[str]:
    """Every .osim a project offers, generics first then built iterations."""
    pats = [
        os.path.join(project, "generic models", "**", "*.osim"),
        os.path.join(project, "models", "**", "*.osim"),
        os.path.join(project, "simulations", "*", "*", "3_iterations", "*", "*.osim"),
        os.path.join(project, "simulations", "*", "*", "*", "*.osim"),
    ]
    seen, out = set(), []
    for p in pats:
        for f in sorted(glob.glob(p, recursive=True)):
            r = os.path.realpath(f)
            # _backup_model_edit/ holds copies this tool made; offering them
            # back as models to edit is how you end up two generations deep in
            # a file called scaled_mvicx3.00_mvicx3.00.osim.
            if r in seen or f"{os.sep}_backup_" in r:
                continue
            seen.add(r)
            out.append(os.path.relpath(f, project))
            if len(out) >= limit:
                return out
    return out


def _print_result(res, verbose=True):
    for m in res.messages:
        print(m)
    print(res.summary_line())


# ----------------------------------------------------------------- list / show
def cmd_list(args) -> int:
    groups = by_verb()
    try:
        import bioscout.utils
        bioscout.utils.get_openSim()
        have_os = True
    except Exception:                                        # noqa: BLE001
        have_os = False
    print(f"[model-edit] OpenSim bindings: "
          f"{'available' if have_os else 'NOT available — ops marked * cannot run here'}")
    for verb in VERBS:
        for i, op in enumerate(groups.get(verb, [])):
            if i == 0:
                print(f"\n{verb.upper().replace('_', ' ')}")
            star = "*" if op.needs_opensim and not have_os else " "
            tail = "" if op.writes_model else "   (writes no model)"
            print(f"  {star}{op.name:18s} {op.summary}{tail}")
            if args.long:
                if op.delegates_to:
                    print(f"      -> {op.delegates_to}")
                if op.suffix:
                    print(f"      output: <model>{op.suffix}.osim")
    print(f"\n[model-edit] `show <op>` for parameters, "
          f"`apply <op> --model M ...` to run one.")
    return 0


def cmd_show(args) -> int:
    try:
        op = get(args.op)
    except KeyError as e:
        print(f"[model-edit] {e}")
        return 2
    print(f"\n{op.name} — {op.summary}")
    print(f"  group          {op.verb}")
    print(f"  needs OpenSim  {'yes' if op.needs_opensim else 'no'}")
    print(f"  writes a model {'yes' if op.writes_model else 'no'}")
    if op.suffix:
        print(f"  output name    <model>{op.suffix}.osim")
    if op.delegates_to:
        print(f"  delegates to   {op.delegates_to}")
    if op.notes:
        print(f"\n  {op.notes}")
    if not op.params:
        print("\n  (no parameters)")
        return 0
    print("\n  parameters")
    for p in op.params:
        req = "required" if p.required else f"default {p.default!r}"
        src = f", from the model's {p.choices_from}" if p.choices_from else ""
        ch = f", one of {list(p.choices)}" if p.choices else ""
        print(f"    --{p.name:<16s} {p.kind:<11s} ({req}{ch}{src})")
        print(f"      {p.help}")
    return 0


# ----------------------------------------------------------------------- apply
def _add_op_flags(sub: argparse.ArgumentParser, op) -> None:
    for p in op.params:
        kw = {"help": p.help, "default": None, "dest": p.name}
        if p.kind == "bool":
            # Both spellings, so a recipe default of True can be turned off.
            sub.add_argument(f"--{p.name.replace('_', '-')}",
                             action="store_const", const=True, **kw)
            sub.add_argument(f"--no-{p.name.replace('_', '-')}",
                             action="store_const", const=False,
                             dest=p.name, default=None,
                             help=f"(disable) {p.help}")
            continue
        if p.kind.startswith("list"):
            kw["nargs"] = "+"
        sub.add_argument(f"--{p.name.replace('_', '-')}", **kw)


def cmd_apply(args, extra: List[str]) -> int:
    from .run import apply

    try:
        op = get(args.op)
    except KeyError as e:
        print(f"[model-edit] {e}")
        return 2
    sub = argparse.ArgumentParser(prog=f"model-edit apply {op.name}",
                                  description=op.summary, epilog=op.notes)
    _add_op_flags(sub, op)
    ns = sub.parse_args(extra)
    params = {k: v for k, v in vars(ns).items() if v is not None}

    res = apply(op.name, args.model, args.out, out_dir=args.out_dir,
                overwrite=args.overwrite, dry_run=args.dry_run, **params)
    _print_result(res)
    return 0 if res.ok else 1


def cmd_info(args) -> int:
    from .run import apply
    res = apply("info", args.model)
    _print_result(res)
    if res.ok:
        for k, v in res.data.items():
            print(f"    {k:16s} {v}")
    return 0 if res.ok else 1


# ---------------------------------------------------------------------- recipe
def cmd_recipe(args) -> int:
    from .recipe import RecipeError, describe, load, run as run_recipe, validate_recipe

    root = Path(args.root or Path(args.file).parent).resolve()
    try:
        doc = load(args.file)
    except RecipeError as e:
        print(f"[model-edit] {e}")
        return 2
    problems = validate_recipe(doc, root)
    print(BANNER)
    for line in describe(doc, root):
        print(line)
    print(BANNER)
    if problems:
        print("[model-edit] this recipe will not run:")
        for p in problems:
            print(f"  - {p}")
        return 2
    if args.check:
        print("[model-edit] recipe is valid.")
        return 0
    try:
        results = run_recipe(args.file, root, dry_run=args.dry_run,
                             overwrite=args.overwrite)
    except RecipeError as e:
        print(f"[model-edit] {e}")
        return 2
    ok = all(r.ok for r in results) and len(results) == len(doc["steps"])
    print(f"[model-edit] {sum(1 for r in results if r.ok)}/{len(doc['steps'])} "
          f"step(s) completed")
    return 0 if ok else 1


# ---------------------------------------------------------------------- guided
def run(project_path: Optional[str] = None) -> int:
    """The guided prompt — `bioscout --model-edit`.

    Same shape as the TPS and moment-arm prompts: discovered defaults in
    brackets, Enter accepts, a summary, and nothing written before you confirm.
    """
    from .introspect import summary as model_summary
    from .prompt import ask_params, confirm, pick
    from .run import apply

    project = os.path.abspath(project_path or os.getcwd())
    print(BANNER)
    print("  bioscout — model edit")
    print(f"  project: {project}")
    print(BANNER)

    models = discover_models(project)
    if not models:
        print("[model-edit] no .osim found under 'generic models/' or "
              "'simulations/*/*/3_iterations/'.")
        print("[model-edit] run this from a bioscout project, or pass its path.")
        return 2
    print(f"\n{len(models)} model(s) found.\n")
    model_rel = pick("model to work on", models)
    model = os.path.join(project, model_rel)

    try:
        s = model_summary(model)
        print(f"\n  {s['name']}: {s['coordinates']} coordinates, {s['muscles']} muscles, "
              f"{s['bodies']} bodies, {s['markers']} markers, "
              f"{s['wraps']} wraps ({s['wraps_scalable']} scalable)")
    except Exception as e:                                   # noqa: BLE001
        print(f"  (could not read the model: {e})")
        return 1

    groups = by_verb()
    names, labels = [], []
    for verb in VERBS:
        for op_ in groups.get(verb, []):
            names.append(op_.name)
            labels.append(f"{op_.name:18s} {op_.summary}")
    print()
    chosen = pick("operation", labels).split()[0]
    op_ = get(chosen)

    if op_.notes:
        print(f"\n  NOTE: {op_.notes}\n")
    if op_.needs_opensim:
        try:
            import bioscout.utils
            bioscout.utils.get_openSim()
        except Exception as e:                               # noqa: BLE001
            print(f"[model-edit] {op_.name} needs the OpenSim bindings, which are "
                  f"not importable here ({type(e).__name__}). Nothing was changed.")
            return 1

    params = ask_params(op_, model=model)

    from .run import plan
    try:
        p = plan(op_.name, model, **params)
    except Exception as e:                                   # noqa: BLE001
        print(f"[model-edit] {e}")
        return 1

    print(f"\n{BANNER}")
    print(f"  {op_.name} — {op_.summary}")
    print(f"  model : {model_rel}")
    for k, v in p["params"].items():
        if v is not None:
            print(f"  {k:14s}: {v}")
    print(f"  output: {os.path.relpath(p['out'], project) if p['out'] else '(no model written)'}")
    print(BANNER)
    if not confirm("apply this?", default=False):
        print("[model-edit] nothing was changed.")
        return 0

    res = apply(op_.name, model, p["out"], overwrite=True, **params)
    _print_result(res)
    if res.ok and res.data:
        for k, v in res.data.items():
            print(f"    {k:16s} {v}")
    if res.ok and res.model and op_.verb == "moment_arms":
        print("\n[model-edit] a wrap edit is the change most likely to push a "
              "muscle path through a bone.")
        if confirm("run the discontinuity check now?", default=True):
            _print_result(apply("check_paths", res.model))
    return 0 if res.ok else 1


# ------------------------------------------------------------------- argparse
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m bioscout.model_edit",
        description="Build and edit OpenSim models: scale, strength, moment "
                    "arms, coordinates, markers, inspect.")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("list", help="every operation, grouped")
    p.add_argument("--long", action="store_true",
                   help="also show what each op delegates to and how it names output")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="parameters and caveats of one operation")
    p.add_argument("op")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("info", help="what is in a model")
    p.add_argument("--model", required=True)
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("apply", help="run one operation")
    p.add_argument("op")
    p.add_argument("--model", required=True)
    p.add_argument("--out", default=None,
                   help="output .osim (default: derived from the op's suffix)")
    p.add_argument("--out-dir", default=None, dest="out_dir")
    p.add_argument("--overwrite", action="store_true",
                   help="replace an existing output (the old file is backed up)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.set_defaults(func=None)          # handled specially: it takes extra flags

    p = sub.add_parser("recipe", help="run a YAML build recipe")
    p.add_argument("file")
    p.add_argument("--root", default=None,
                   help="project root that paths resolve against "
                        "(default: the recipe's folder)")
    p.add_argument("--check", action="store_true", help="validate only")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_recipe)

    p = sub.add_parser("guided", help="the interactive prompt")
    p.add_argument("project", nargs="?", default=None)
    p.set_defaults(func=lambda a: run(a.project))
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return run(None)
    ap = build_parser()
    if argv[0] == "apply":
        known, extra = ap.parse_known_args(argv)
        return cmd_apply(known, extra)
    args = ap.parse_args(argv)
    if getattr(args, "func", None) is None:
        ap.print_help()
        return 2
    return args.func(args)
