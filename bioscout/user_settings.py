"""bioscout's own settings for this computer (not a project's): ``bioscout -settings``.

One YAML file, ``~/.bioscout/settings.yaml`` (``BIOSCOUT_SETTINGS`` points elsewhere),
read at the start of every ``bioscout`` command. Each setting maps to the environment
variable bioscout already reads; a variable you set yourself in the shell wins over the
file, the file wins over bioscout's default.

    bioscout -settings            open the file in your editor (written with defaults first)
    bioscout -settings --show     print the values in effect and where each comes from
    bioscout -settings --reset    rewrite the file with the defaults
"""
import os
import sys

#: name -> (default, environment variable, comment)
SETTINGS = {
    "log_terminal":       (False, None,
                           "print everything live in the terminal too (same as --verbose)"),
    "open_log":           (True, "BIOSCOUT_OPEN_LOG",
                           "open the run log (and the running step's log) in your editor"),
    "log_tabs":           ("reuse", "BIOSCOUT_LOG_TABS",
                           "reuse: one editor tab follows the runs (live_<k>.log) | per-run: a tab per log"),
    "step_logs":          (True, "BIOSCOUT_STEP_LOGS",
                           "each step's details in its own log beside its results; the run log keeps one line per step"),
    "log_viewer":         ("", "BIOSCOUT_LOG_VIEWER",
                           'command that opens a log, e.g. "code -r" or "notepad++"; empty: VS Code, else the system app'),
    "log_dir":            ("", "BIOSCOUT_LOG_DIR",
                           "folder for every run log; empty: <project>/logs"),
    "contributions_jobs": (8, "BIOSCOUT_JCF_JOBS",
                           "parallel OpenSim JRA runs for the JRA contributions (at most CPUs - 1)"),
    "ma_method":          ("opensim", "BIOSCOUT_MA_METHOD",
                           "OpenSim engine muscle analysis: opensim (full MuscleAnalysis tool) | fast (bioscout, finite differences)"),
}


def path():
    return os.environ.get("BIOSCOUT_SETTINGS") or os.path.join(os.path.expanduser("~"), ".bioscout", "settings.yaml")


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    return str(v)


def write_default(p=None):
    p = p or path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    lines = ["# bioscout settings for this computer -- `bioscout -settings` opens this file.",
             "# A shell environment variable of the same meaning wins over this file.", ""]
    for k, (d, env, c) in SETTINGS.items():
        lines += [f"# {c}" + (f"   [{env}]" if env else ""), f"{k}: {_fmt(d)}", ""]
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return p


def load():
    """-> {name: value} from the file (missing names: default)."""
    vals = {k: d for k, (d, _, _) in SETTINGS.items()}
    p = path()
    if os.path.isfile(p):
        try:
            import yaml
            got = yaml.safe_load(open(p, encoding="utf-8")) or {}
            vals.update({k: v for k, v in got.items() if k in SETTINGS and v is not None})
        except Exception as e:                                   # noqa: BLE001
            print(f"[bioscout] could not read {p}: {e} -- defaults used", file=sys.stderr)
    return vals


def apply():
    """Put the file's values into the environment (a variable already set wins). -> values."""
    vals = load()
    for k, (d, env, _) in SETTINGS.items():
        if not env:
            continue
        v = vals[k]
        if v in ("", None) or v == d:           # at the default: leave bioscout's own default alone
            continue
        if isinstance(v, bool):
            v = "1" if v else "0"
        if k == "log_tabs":
            v = str(v).strip().lower()
        os.environ.setdefault(env, str(v))
    return vals


def command(args):
    """``bioscout -settings [--show | --reset]``."""
    p = path()
    if "--reset" in args or not os.path.isfile(p):
        write_default(p)
        print(f"[bioscout] settings written with the defaults: {p}")
    if "--show" in args:
        vals = load()
        print(f"bioscout settings ({p}):")
        for k, (d, env, _) in SETTINGS.items():
            src = "environment" if env and env in os.environ else ("file" if vals[k] != d else "default")
            shown = os.environ[env] if src == "environment" else _fmt(vals[k])
            print(f"  {k:<20} {shown:<12} ({src}{', ' + env if env else ''})")
        return 0
    print(f"[bioscout] settings: {p}")
    try:
        from bioscout.utils.shared import _open_in_editor
        _open_in_editor(p)
    except Exception:                                            # noqa: BLE001
        pass
    return 0
