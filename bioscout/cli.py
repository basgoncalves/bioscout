"""The bioscout command line: ten verbs instead of sixty-six flags.

    bioscout                 launch the GUI (unchanged)
    bioscout help [VERB]     this, or one verb's detail
    bioscout init            start a project
    bioscout gui             launch the GUI
    bioscout run             the pipeline: IK -> ID -> MA -> SO -> CEINMS -> JRA
    bioscout session         new / export / classify / ingest / reset
    bioscout model           check / edit / compare / ma / validate / joint-centres
    bioscout tps             build an MRI-personalised model
    bioscout plot            figures, summaries, Collings ranking
    bioscout utils           env / install / md2pdf / pylance
    bioscout lab             EXPERIMENTAL 3.0: shots, load reports

Why this module exists
----------------------
The flat parser had grown to 66 options. Nineteen of them were basketball shot
detection and fitness-tracker imports; of the remaining forty-seven, **twenty-five
existed only to modify another flag** — their help text literally began
``With --X:``. ``--top``, ``--side``, ``--metric`` and ``--skip`` mean nothing
without ``--collings``; ``--toc``, ``--bib`` and ``--keep-docx`` mean nothing
without ``--md2pdf``. A subcommand tree makes all twenty-five disappear from the
root help without deleting a single one: they live under the verb they belong to.

Two design rules, both load-bearing:

1. **This module imports nothing but the standard library.** ``bioscout -h`` used
   to run the conda env check and import ``utils.openSim`` before it could print
   a help screen. Help must be instant and must work in a broken environment —
   it is what you reach for when nothing else runs.
2. **The old flags still work.** They are hidden from help and print one line
   naming the new form. Two real projects drive bioscout by flag from shell
   scripts; breaking them to tidy a help screen is a bad trade. Drop the aliases
   one release after everything has migrated.

How a verb reaches the old code
-------------------------------
Most verbs are *translated*: the parsed subcommand is rewritten into the legacy
flag argv, and ``__main__.py`` proceeds exactly as before. That keeps
``run_subject_mode()`` — which reads module-global ``args`` — working untouched,
so the riskiest handler in the package is not rewritten to gain a nicer help
screen. Verbs whose implementation is already self-contained and dependency-light
(``model check``, ``utils env``) are dispatched directly and never load the
scientific stack at all.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence, Tuple

__all__ = ["VERBS", "build_parser", "route", "main", "legacy_hint"]

#: Root verbs. ``__main__`` checks this before it builds the legacy parser.
VERBS = ("help", "init", "gui", "run", "session", "model", "tps", "plot",
         "utils", "lab", "project")

_EPILOG = """\
examples:
  bioscout run 021 --session pre,post --replace
  bioscout run 023 --session pre --so                    (only the SO stage)
  bioscout run 023 --session pre --export --scale --exbiomec   (a fresh session)
  bioscout model check models --strict
  bioscout session new simulations/022/pre
  bioscout plot --list
  bioscout help run

every verb takes --help of its own:  bioscout model --help
"""


# --------------------------------------------------------------------------- #
# the tree
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bioscout", description="Biomechanical analysis: c3d to joint contact forces.",
        epilog=_EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="verb", metavar="VERB")

    # -- help ---------------------------------------------------------------- #
    h = sub.add_parser("help", help="show help for a verb")
    h.add_argument("topic", nargs="?", metavar="VERB")

    # -- init ---------------------------------------------------------------- #
    i = sub.add_parser("init", help="create a project: folders, models, settings template")
    i.add_argument("path", nargs="?", default=".", metavar="PROJECT_PATH")

    # -- gui ----------------------------------------------------------------- #
    sub.add_parser("gui", help="launch the GUI (also the default with no verb)")

    # -- project ------------------------------------------------------------- #
    pj = sub.add_parser("project",
                        help="project-level config (project.yaml)")
    pjs = pj.add_subparsers(dest="action", metavar="ACTION")
    pji = pjs.add_parser(
        "init", help="generate project.yaml from an existing settings.py",
        description="Extracts the lab facts (BatchSettings/CEINMSSettings "
                    "data attributes that differ from bioscout's defaults) "
                    "into a declarative project.yaml. After a review run, "
                    "the settings.py can be deleted — see "
                    "docs/IMPLEMENTATIONS.md §2.9.")
    pji.add_argument("path", nargs="?", default=".", metavar="PROJECT_PATH")
    pji.add_argument("--force", action="store_true",
                     help="overwrite an existing project.yaml (a .bak is kept)")

    # -- run ----------------------------------------------------------------- #
    r = sub.add_parser(
        "run", help="run the pipeline for a subject",
        description="IK -> ID -> muscle analysis -> static optimisation -> CEINMS -> "
                    "joint reaction. With no SUBJECT, runs every subject in settings.")
    r.add_argument("subject", nargs="?", metavar="SUBJECT",
                   help="subject id; omit to run all")
    r.add_argument("--session", metavar="NAME",
                   help="restrict to these session folders (comma-separated)")
    r.add_argument("--trial", metavar="NAME",
                   help="restrict to these trials (comma-separated)")
    r.add_argument("--replace", action="store_true",
                   help="recompute outputs that already exist (default: skip them)")
    r.add_argument("--export", action="store_true",
                   help="(re)export markers/GRF/EMG from the c3d first")
    # Stage flags. No stage flag = the full pipeline (SO + CEINMS); any stage
    # flag = ONLY the named stages. The call site states the whole selection —
    # this replaces the DO_SO/DO_CEINMS block in a project settings.py.
    r.add_argument("--scale", action="store_true",
                   help="stage: build the session's personalised model "
                        "(generic + static -> ScaleTool), after --export")
    r.add_argument("--exbiomec", action="store_true",
                   help="stage: external biomechanics only (IK -> ID -> MA)")
    r.add_argument("--so", action="store_true",
                   help="stage: static optimisation (IK/ID/MA -> SO -> JRA)")
    r.add_argument("--ceinms", action="store_true",
                   help="stage: CEINMS (calibrate -> execute -> JRA)")
    r.add_argument("--reset", action="store_true",
                   help="strip trials back to inputs-only, then run")
    r.add_argument("--batch", metavar="FILE",
                   help="drive the run from a settings.py or batch .json instead")
    r.add_argument("--project", metavar="PATH")

    # -- session ------------------------------------------------------------- #
    s = sub.add_parser("session", help="create, export, classify or reset a session")
    ss = s.add_subparsers(dest="action", metavar="ACTION")

    sn = ss.add_parser("new", help="scaffold session.yaml (opens a dialog)")
    sn.add_argument("path", nargs="?", metavar="SESSION_PATH",
                    help="session folder holding 1_c3dfiles/*.c3d")
    sn.add_argument("--from", dest="from_session", metavar="SESSION_PATH",
                    help="existing session.yaml to copy the lab constants from "
                         "(markerset, emg_map, ceinms)")
    sn.add_argument("--body-mass", type=float, metavar="KG")
    sn.add_argument("--no-gui", action="store_true",
                    help="do not open the dialog; take the values from these flags")

    sed_ = ss.add_parser("edit", help="edit an existing session.yaml in a form")
    sed_.add_argument("path", nargs="?", metavar="SESSION_PATH")
    sed_.add_argument("--no-gui", action="store_true",
                      help="do not open the editor (there is no flag equivalent yet)")

    se = ss.add_parser("export", help="c3d -> 2_experimental (markers, GRF, EMG)")
    se.add_argument("path", metavar="SESSION_PATH")

    sc = ss.add_parser("classify", help="detect what each trial is, from markers/GRF")
    sc.add_argument("path", metavar="SESSION_PATH")
    sc.add_argument("--no-plots", action="store_true", help="skip the per-trial QC figures")
    sc.add_argument("--write-yaml", action="store_true",
                    help="also write session.yaml when the session has none "
                         "(an existing one is never modified)")

    si = ss.add_parser("ingest", help="distribute loose .c3d files into the tree")
    si.add_argument("folder", metavar="C3D_FOLDER")
    si.add_argument("--subject", required=True)
    si.add_argument("--session", required=True)

    sr = ss.add_parser("reset", help="strip trials back to inputs-only")
    sr.add_argument("--subject")
    sr.add_argument("--session")
    sr.add_argument("--trial")
    sr.add_argument("--dry-run", action="store_true", help="preview, touch nothing")
    sr.add_argument("--raw", action="store_true",
                    help="also prune inputs/ down to the raw c3d")

    # -- model --------------------------------------------------------------- #
    m = sub.add_parser("model", help="check, edit, compare and validate .osim models")
    ms = m.add_subparsers(dest="action", metavar="ACTION")

    mc = ms.add_parser("check", help="can every model still find its bone meshes?")
    mc.add_argument("path", nargs="*", metavar="FOLDER_OR_OSIM")
    mc.add_argument("--strict", action="store_true",
                    help="fail on anything not resolvable from the model's own folder")
    mc.add_argument("--search", action="append", metavar="DIR")
    mc.add_argument("--json", metavar="FILE")
    mc.add_argument("--project", metavar="PATH")
    mc.add_argument("-v", "--verbose", action="store_true")
    mc.add_argument("-q", "--quiet", action="store_true")

    me = ms.add_parser("edit", help="scale, set mass, change forces, moment arms, markers")
    me.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    mp = ms.add_parser("compare", help="dimensions and segment masses across models")
    mp.add_argument("models", nargs="+", metavar="FOLDER_OR_OSIM")
    mp.add_argument("--scale-setups", nargs="+", metavar="LABEL=SETUP.xml",
                    help="ScaleTool setups, to report the scaling INTENT behind each")
    mp.add_argument("-o", "--out", metavar="FILE", help="write the tables to .xlsx/.csv")
    mp.add_argument("--figures", nargs="?", const=True, metavar="DIR")

    ma = ms.add_parser("ma", help="adjust a muscle's moment arm, interactively")
    ma.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    mv = ms.add_parser("validate", help="moment arms, fibre lengths, strength vs literature")
    mv.add_argument("--model", required=True, metavar="OSIM")
    mv.add_argument("--out", metavar="DIR")
    mv.add_argument("--side", default="_r", choices=["_r", "_l"])

    mj = ms.add_parser("joint-centres", aliases=["jc"],
                       help="add Harrington hip / midpoint knee-ankle centres to a TRC")
    mj.add_argument("trc", metavar="TRC")
    mj.add_argument("-o", "--out", metavar="FILE")

    # -- tps ----------------------------------------------------------------- #
    t = sub.add_parser("tps", help="build an MRI-personalised model (interactive)")
    t.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    # -- plot ---------------------------------------------------------------- #
    pl = sub.add_parser(
        "plot", help="figures from the results on disk",
        description="Anything that is not `summary` or `collings` is taken as "
                    "figure keys, so `bioscout plot p01 s_all` and "
                    "`bioscout plot figures p01 s_all` are the same command.")
    pls = pl.add_subparsers(dest="action", metavar="ACTION")

    pf = pls.add_parser("figures", help="draw catalogue figures by key (the default)")
    pf.add_argument("keys", nargs="*", metavar="KEY",
                    help="figure keys (p01, s_all, m_curves, mi_ma, ...) or a group name")
    pf.add_argument("--list", action="store_true", dest="list_figures",
                    help="print the catalogue and exit")
    pf.add_argument("--project", metavar="PATH")
    pf.add_argument("--session", metavar="PATH")
    pf.add_argument("--subject", metavar="ID")

    pm = pls.add_parser("summary", help="kinematics/kinetics summary figures")
    pm.add_argument("path", nargs="?", metavar="SETTINGS_OR_PROJECT")
    pm.add_argument("--overall", action="store_true",
                    help="only rebuild the overall plots in <project>/summary")
    pm.add_argument("--subject", metavar="ID")
    pm.add_argument("--trial", metavar="NAME")
    pm.add_argument("--project", metavar="PATH")

    pc = pls.add_parser("collings", help="Collings-style muscle ranking figure")
    pc.add_argument("path", nargs="?", metavar="SESSION_PATH")
    pc.add_argument("--skip", nargs="*", metavar="ITERATION",
                    help="iterations to leave out")
    pc.add_argument("--metric", metavar="PEAK|IMPULSE")
    pc.add_argument("--side", choices=["_r", "_l"])
    pc.add_argument("--top", type=int, metavar="N")
    pc.add_argument("-o", "--out", metavar="FILE")

    # -- utils --------------------------------------------------------------- #
    u = sub.add_parser("utils", help="environment, dependencies, docs, editor setup")
    us = u.add_subparsers(dest="action", metavar="ACTION")

    ue = us.add_parser("env", help="which conda env bioscout expects vs is running in")
    ue.add_argument("--create", action="store_true",
                    help="create the expected env and install into it")

    us.add_parser("install", help="install missing dependencies")

    um = us.add_parser("md2pdf", help="markdown -> PDF (no LaTeX needed)")
    um.add_argument("files", nargs="+", metavar="FILE.md")
    um.add_argument("--outdir", metavar="DIR")
    um.add_argument("--toc", action="store_true")
    um.add_argument("--bib", metavar="FILE.bib")
    um.add_argument("--keep-docx", action="store_true")

    up = us.add_parser("pylance", help="write .vscode/settings.json so 'import bioscout' resolves")
    up.add_argument("path", nargs="?", metavar="PROJECT_DIR")

    # -- lab ----------------------------------------------------------------- #
    lab = sub.add_parser(
        "lab", help="EXPERIMENTAL (3.0): video and wearable tracking",
        description="Not part of the OpenSim pipeline and not ready. Kept here so "
                    "the MSK verbs above stay legible.")
    ls_ = lab.add_subparsers(dest="action", metavar="ACTION")

    lsh = ls_.add_parser("shots", help="basketball shot analysis from video")
    lsh.add_argument("video", metavar="VIDEO")
    lsh.add_argument("--shooting-hand", default="right", choices=["right", "left"])
    lsh.add_argument("--poses", metavar="POSES_JSON")
    lsh.add_argument("--fps", type=float)
    lsh.add_argument("--min-gap", type=float, default=1.5)
    lsh.add_argument("--n-points", type=int, default=1000)
    lsh.add_argument("--hoop-side", default="auto", choices=["auto", "right", "left"])
    lsh.add_argument("--yolo-model", metavar="WEIGHTS.pt")
    lsh.add_argument("--hoop", metavar="CX,CY,W,H")

    llr = ls_.add_parser("load-report", help="training-load & fatigue PDF from tracker exports")
    llr.add_argument("inputs", nargs="?", metavar="FILES_OR_FOLDER")
    llr.add_argument("--out", metavar="PDF")
    llr.add_argument("--hr-max", type=float)
    llr.add_argument("--hr-rest", type=float)
    llr.add_argument("--age", type=int)
    llr.add_argument("--sex", default="M", choices=["M", "F"])
    llr.add_argument("--zepp-pull", action="store_true")
    llr.add_argument("--strava-pull", action="store_true")
    llr.add_argument("--creds", metavar="JSON")

    la = ls_.add_parser("add-subject", help="add a player-tracking subject to subjects.json")
    la.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    return p


# --------------------------------------------------------------------------- #
# legacy flags -> the verb that replaced them
# --------------------------------------------------------------------------- #
_LEGACY = {
    "--init": "bioscout init", "--gui": "bioscout gui", "-g": "bioscout gui",
    "--run_subject": "bioscout run", "--batch": "bioscout run --batch",
    "-b": "bioscout run --batch",
    "--new-session": "bioscout session new", "--c3d-export": "bioscout session export",
    "--export-session": "bioscout session export",
    "--classifier": "bioscout session classify", "--classify": "bioscout session classify",
    "--ingest-c3d": "bioscout session ingest", "--reset": "bioscout session reset",
    "--model-edit": "bioscout model edit", "--model_edit": "bioscout model edit",
    "--edit": "bioscout model edit",
    "--compare-models": "bioscout model compare",
    "--compare_models": "bioscout model compare",
    "--change-moment-arms": "bioscout model ma", "--ma": "bioscout model ma",
    "--joint-centres": "bioscout model joint-centres",
    "--joint-centers": "bioscout model joint-centres", "--jc": "bioscout model joint-centres",
    "--tps": "bioscout tps",
    "--summary": "bioscout plot summary", "--collings": "bioscout plot collings",
    "--env": "bioscout utils env", "--env-check": "bioscout utils env",
    "--env-create": "bioscout utils env --create", "--install": "bioscout utils install",
    "--md2pdf": "bioscout utils md2pdf", "--pylance-fix": "bioscout utils pylance",
    "--shots": "bioscout lab shots", "--load-report": "bioscout lab load-report",
    "--add_subject": "bioscout lab add-subject",
}


def legacy_hint(argv: Sequence[str]) -> Optional[str]:
    """One-line nudge for the first legacy flag in ``argv``, or None.

    Deliberately a hint and not a warning: these still work, and a script that
    prints a WARNING on every run trains people to ignore warnings.
    """
    for a in argv:
        new = _LEGACY.get(a.split("=")[0])
        if new:
            return f"[bioscout] `{a}` still works; the new form is `{new}`."
    return None


# --------------------------------------------------------------------------- #
# verb -> legacy argv
# --------------------------------------------------------------------------- #
def _flag(out: List[str], name: str, value, *, store_true: bool = False) -> None:
    """Append ``name`` (and its value) when the option was actually given."""
    if value in (None, False, "", []):
        return
    out.append(name)
    if not store_true:
        out.extend([str(v) for v in value] if isinstance(value, list) else [str(value)])


def _to_legacy(ns: argparse.Namespace) -> List[str]:      # noqa: C901 — a flat lookup table
    v, a = ns.verb, getattr(ns, "action", None)
    out: List[str] = []

    if v == "init":
        return ["--init", ns.path]
    if v == "gui":
        return ["--gui"]

    if v == "run":
        if ns.batch:
            return ["-b", ns.batch]
        out = ["--run_subject"] + ([ns.subject] if ns.subject else [])
        _flag(out, "--session", ns.session)
        _flag(out, "--trial", ns.trial)
        _flag(out, "--REPLACE", ns.replace, store_true=True)
        _flag(out, "--export", ns.export, store_true=True)
        _flag(out, "--do-scale", ns.scale, store_true=True)
        _flag(out, "--do-exbiomec", ns.exbiomec, store_true=True)
        _flag(out, "--do-so", ns.so, store_true=True)
        _flag(out, "--do-ceinms", ns.ceinms, store_true=True)
        _flag(out, "--reset", ns.reset, store_true=True)
        _flag(out, "--project", ns.project)
        return out

    if v == "session":
        if a == "new":
            out = ["--new-session", ns.path or "."]
            _flag(out, "--from-session", ns.from_session)
            _flag(out, "--body-mass", ns.body_mass)
            return out
        if a == "edit":
            print("[session edit] needs a display — there is no flag equivalent. "
                  "Edit simulations/<subject>/<session>/session.yaml directly, or "
                  "use the GUI's File Editor tab.")
            return []
        if a == "export":
            return ["--c3d-export", ns.path]
        if a == "classify":
            out = ["--classifier", ns.path]
            _flag(out, "--no-plots", ns.no_plots, store_true=True)
            _flag(out, "--write-session-yaml", ns.write_yaml, store_true=True)
            return out
        if a == "ingest":
            return ["--ingest-c3d", ns.folder, "--subject", ns.subject,
                    "--session", ns.session]
        if a == "reset":
            out = ["--reset"]
            _flag(out, "--subject", ns.subject)
            _flag(out, "--session", ns.session)
            _flag(out, "--trial", ns.trial)
            _flag(out, "--reset-dry-run", ns.dry_run, store_true=True)
            _flag(out, "--reset-raw", ns.raw, store_true=True)
            return out

    if v == "model":
        if a == "edit":
            return ["--model-edit"] + ([ns.path] if ns.path else [])
        if a == "ma":
            return ["--change-moment-arms"] + ([ns.path] if ns.path else [])
        if a == "compare":
            out = ["--compare-models"] + list(ns.models)
            _flag(out, "--scale-setups", ns.scale_setups)
            _flag(out, "-o", ns.out)
            if ns.figures is True:
                out.append("--figures")
            elif ns.figures:
                out += ["--figures", str(ns.figures)]
            return out
        if a in ("joint-centres", "jc"):
            out = ["--joint-centres", ns.trc]
            _flag(out, "-o", ns.out)
            return out

    if v == "tps":
        return ["--tps"] + ([ns.path] if ns.path else [])

    if v == "plot":
        if a == "summary":
            out = ["--summary"] + ([ns.path] if ns.path else [])
            _flag(out, "-overall", ns.overall, store_true=True)
            _flag(out, "-s", ns.subject)
            _flag(out, "-t", ns.trial)
            _flag(out, "-p", ns.project)
            return out
        if a == "collings":
            out = ["--collings"] + ([ns.path] if ns.path else [])
            _flag(out, "--skip", ns.skip)
            _flag(out, "--metric", ns.metric)
            _flag(out, "--side", ns.side)
            _flag(out, "--top", ns.top)
            _flag(out, "-o", ns.out)
            return out

    if v == "utils":
        if a == "install":
            return ["--install"]
        if a == "md2pdf":
            out = ["--md2pdf"] + list(ns.files)
            _flag(out, "--outdir", ns.outdir)
            _flag(out, "--toc", ns.toc, store_true=True)
            _flag(out, "--bib", ns.bib)
            _flag(out, "--keep-docx", ns.keep_docx, store_true=True)
            return out
        if a == "pylance":
            return ["--pylance-fix"] + ([ns.path] if ns.path else [])

    if v == "lab":
        if a == "shots":
            out = ["--shots", ns.video,
                   "--shooting-hand", ns.shooting_hand,
                   "--hoop-side", ns.hoop_side,
                   "--min-gap", str(ns.min_gap), "--n-points", str(ns.n_points)]
            _flag(out, "--poses", ns.poses)
            _flag(out, "--fps", ns.fps)
            _flag(out, "--yolo-model", ns.yolo_model)
            _flag(out, "--hoop", ns.hoop)
            return out
        if a == "load-report":
            out = ["--load-report", ns.inputs or "."]
            _flag(out, "--load-out", ns.out)
            _flag(out, "--hr-max", ns.hr_max)
            _flag(out, "--hr-rest", ns.hr_rest)
            _flag(out, "--age", ns.age)
            out += ["--sex", ns.sex]
            _flag(out, "--zepp-pull", ns.zepp_pull, store_true=True)
            _flag(out, "--strava-pull", ns.strava_pull, store_true=True)
            _flag(out, "--creds", ns.creds)
            return out
        if a == "add-subject":
            return ["--add_subject"] + ([ns.path] if ns.path else [])

    return out


# --------------------------------------------------------------------------- #
# verbs that need nothing heavy
# --------------------------------------------------------------------------- #
def _direct(ns: argparse.Namespace) -> Optional[int]:
    """Run a verb here and return its exit code, or None to fall through.

    Only for implementations that are already self-contained: running them here
    means the scientific stack is never imported, so they work on a machine where
    the environment is half-built — which is exactly when you need them.
    """
    v, a = ns.verb, getattr(ns, "action", None)

    if v == "model" and a == "check":
        from bioscout.model.cli import main as _check
        argv = ["--verify"] + list(ns.path)
        if not ns.path:
            argv += ["--project", ns.project or "."]
        for name, val in (("--strict", ns.strict), ("--verbose", ns.verbose),
                          ("--quiet", ns.quiet)):
            if val:
                argv.append(name)
        for d in (ns.search or []):
            argv += ["--search", d]
        if ns.json:
            argv += ["--json", ns.json]
        return _check(argv)

    if v == "project" and a == "init":
        # Imports the project's settings.py, which needs the full stack — but
        # the extraction itself is one call and prints its own verdict.
        from bioscout.utils.project_config import init_project_yaml
        return init_project_yaml(ns.path, force=ns.force)

    if v == "utils" and a == "env":
        from bioscout.envcheck import ensure
        st = ensure(create=bool(ns.create))
        return 0 if (st["match"] or st["env_exists"]) else 1

    if v == "session" and a in ("new", "edit") and not getattr(ns, "no_gui", False):
        # One editor for both verbs: it detects whether session.yaml is already
        # there and offers to create it or edits it in place, which is what you
        # want when `session new` is pointed at a folder that turns out to have
        # one. --no-gui, or no display, falls through to the flag path below.
        try:
            from bioscout.gui.session_editor import gui_available, open_session_editor
        except Exception:
            return None
        if not gui_available():
            # Headless — ssh, CI, a container. Fall through to the flags rather
            # than exit 0 having written nothing, which reads as success.
            return None
        return open_session_editor(ns.path)

    if v == "plot" and a == "figures":
        from bioscout.figures import main as _figures
        argv = list(ns.keys)
        if ns.list_figures:
            argv.append("--list")
        for name, val in (("--project", ns.project), ("--session", ns.session),
                          ("--subject", ns.subject)):
            if val:
                argv += [name, val]
        return _figures(argv) or 0

    if v == "model" and a == "validate":
        from bioscout.muscle_inspect.__main__ import main as _mi
        argv = ["all", "--model", ns.model, "--side", ns.side]
        if ns.out:
            argv += ["--out", ns.out]
        return _mi(argv)

    return None


# --------------------------------------------------------------------------- #
# entry
# --------------------------------------------------------------------------- #
def route(argv: Sequence[str]) -> Tuple[str, object]:
    """Decide what a new-style argv means.

    Returns ``("exit", code)`` when the verb is finished, or
    ``("legacy", [flags])`` when ``__main__`` should carry on with the old
    machinery using the translated argv.
    """
    parser = build_parser()
    argv = list(argv)

    # `bioscout plot p01 s_all` == `bioscout plot figures p01 s_all`. argparse
    # cannot have both a free positional list and subcommands on one parser, so
    # the default action is inserted here rather than fought for in the grammar.
    if len(argv) >= 1 and argv[0] == "plot":
        rest = argv[1:]
        # `plot --help` must show the VERB's help — the list of actions — not
        # the default action's, or summary and collings become undiscoverable.
        if rest and rest[0] in ("-h", "--help"):
            pass
        elif not rest or rest[0] not in ("figures", "summary", "collings"):
            argv = ["plot", "figures"] + rest

    # `bioscout help [VERB]` == `bioscout [VERB] --help`
    if argv and argv[0] == "help":
        topic = argv[1] if len(argv) > 1 else None
        if topic and topic in VERBS:
            parser.parse_args([topic, "--help"])        # exits
        parser.print_help()
        return ("exit", 0)

    ns = parser.parse_args(argv)

    if not getattr(ns, "verb", None):
        parser.print_help()
        return ("exit", 0)

    # A verb with subcommands, given none: show that verb's help rather than
    # silently doing nothing.
    if ns.verb in ("session", "model", "utils", "lab", "plot", "project") and not getattr(ns, "action", None):
        parser.parse_args([ns.verb, "--help"])          # exits

    code = _direct(ns)
    if code is not None:
        return ("exit", code)

    return ("legacy", _to_legacy(ns))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Standalone entry: ``python -m bioscout.cli <verb> ...``."""
    kind, value = route(list(sys.argv[1:] if argv is None else argv))
    if kind == "exit":
        return int(value)                                # type: ignore[arg-type]
    import runpy
    sys.argv = [sys.argv[0]] + list(value)               # type: ignore[arg-type]
    runpy.run_module("bioscout", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
