"""Convenience dispatcher:  python -m bioscout.muscle_inspect <command> [args]

Commands:
  inspect   coordinate-sweep inspect + fix + moment-arm validation (accepts flags)
  check     motion-driven (.mot) muscle-path check   (edit its CONFIG)
  validate  moment-arm literature validation only    (edit its CONFIG)
  compare   settings-sweep harness                    (edit its CONFIG)
  fibre     model fascicle length & pennation vs literature   --model M --lit CSV --out DIR
  strength  isometric (and isokinetic) joint strength vs literature MVC bands
  all       FULL validation in one folder: moment arms + fibre length/pennation +
            isometric + isokinetic strength.  --model M  (data auto-resolved)

Each delegated command is also runnable directly, e.g.
  python -m bioscout.muscle_inspect.run_moment_arm_inspection --model model.osim
"""
import argparse
import importlib
import inspect
import os
import sys

# commands delegated to a module that defines its own main()
_COMMANDS = {
    "inspect": "run_moment_arm_inspection",
    "check": "run_muscle_checker",
    "validate": "validate_against_literature",
    "compare": "compare_settings",
}


def _run_fibre(rest):
    from . import muscle_length_validation as V
    p = argparse.ArgumentParser(prog="muscle_inspect fibre")
    p.add_argument("--model", required=True, help="OpenSim .osim model")
    p.add_argument("--lit", required=True, help="literature CSV (fascicle_length/pennation rows)")
    p.add_argument("--out", default="muscle_inspect_out", help="output directory")
    p.add_argument("--side", default="_r")
    p.add_argument("-n", type=int, default=40)
    a = p.parse_args(rest)
    out = V.run_fibre_validation(a.model, a.lit, a.out, side=a.side, n=a.n)
    print(f"fibre validation figure: {out}")


def _run_strength(rest):
    from . import strength as S
    p = argparse.ArgumentParser(prog="muscle_inspect strength")
    p.add_argument("--model", required=True, help="OpenSim .osim model")
    p.add_argument("--lit", required=True, help="literature_strength.csv")
    p.add_argument("--groups", required=True, help="muscle_functions.csv / groups CSV")
    p.add_argument("--out", default="muscle_inspect_out", help="output directory")
    p.add_argument("--side", default="_r")
    p.add_argument("-n", type=int, default=40)
    p.add_argument("--isokinetic", metavar="ISO_CSV",
                   help="also run isokinetic check with this velocity-band CSV")
    a = p.parse_args(rest)
    fig = S.run_strength(a.model, a.lit, a.groups, a.out, side=a.side, n=a.n)
    print(f"isometric strength figure: {fig}")
    if a.isokinetic:
        figk = S.run_isokinetic(a.model, a.isokinetic, a.groups, a.lit, a.out, side=a.side)
        print(f"isokinetic strength figure: {figk}")


def _run_all(rest):
    """One-shot FULL validation: moment arms + fibre + isometric + isokinetic.

    Auto-resolves the bundled literature (validation/ folder) so only --model is
    required. Writes everything into muscle_inspect_<model>/ next to the model.
    """
    from . import muscle_length_validation as V
    from . import strength as S
    from .paths import LITERATURE_MOMENT_ARMS_CSV
    p = argparse.ArgumentParser(prog="muscle_inspect all")
    p.add_argument("--model", required=True, help="OpenSim .osim model")
    p.add_argument("--out", default=None, help="default: muscle_inspect_<model>/ next to the model")
    p.add_argument("--lit", default=None, help="moment-arm + fibre CSV (default: bundled)")
    p.add_argument("--strength-lit", dest="strength_lit", default=None,
                   help="strength CSV (default: bundled literature_strength.csv)")
    p.add_argument("--groups", default=None, help="muscle_functions.csv (default: bundled)")
    p.add_argument("--side", default="_r")
    p.add_argument("-n", type=int, default=60)
    p.add_argument("--no-moment-arms", dest="moment", action="store_false", default=True)
    p.add_argument("--no-fibre", dest="fibre", action="store_false", default=True)
    p.add_argument("--no-strength", dest="strength", action="store_false", default=True)
    p.add_argument("--no-isokinetic", dest="isok", action="store_false", default=True)
    a = p.parse_args(rest)

    data_dir = os.path.dirname(LITERATURE_MOMENT_ARMS_CSV)   # the validation/ folder
    lit = a.lit or LITERATURE_MOMENT_ARMS_CSV
    scsv = a.strength_lit or os.path.join(data_dir, "literature_strength.csv")
    groups = a.groups or os.path.join(data_dir, "muscle_functions.csv")
    base = os.path.splitext(os.path.basename(a.model))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.model)), f"muscle_inspect_{base}")
    os.makedirs(out, exist_ok=True)
    print(f"[all] full validation -> {out}")

    if a.moment:
        V.run_validation(a.model, lit, out, side=a.side, n=a.n)
    if a.fibre:
        V.run_fibre_validation(a.model, lit, out, side=a.side, n=max(30, a.n // 2))
    if a.strength:
        S.run_strength(a.model, scsv, groups, out, side=a.side, n=40)
        if a.isok:
            S.run_isokinetic(a.model, scsv, groups, scsv, out, side=a.side)
    print(f"[all] done -> {out}")


_INLINE = {"fibre": _run_fibre, "strength": _run_strength, "all": _run_all}


def main():
    known = set(_COMMANDS) | set(_INLINE)
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help") or sys.argv[1] not in known:
        print(__doc__)
        sys.exit(0 if (len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help")) else 2)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd in _INLINE:
        _INLINE[cmd](rest)
        return
    mod = importlib.import_module(f".{_COMMANDS[cmd]}", __package__)
    if "argv" in inspect.signature(mod.main).parameters:
        mod.main(rest)
    else:
        sys.argv = [_COMMANDS[cmd]] + rest   # let the module's own argparse (if any) see args
        mod.main()


if __name__ == "__main__":
    main()
