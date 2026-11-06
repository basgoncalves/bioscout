"""The bioscout command line: ten verbs instead of sixty-six flags.

    bioscout                 the verb list (the desktop GUI was removed in 3.1:
                             use BioScout Web, https://basgoncalves.github.io/bioscout-web/)
    bioscout help [VERB]     this, or one verb's detail
    bioscout init            start a project (folders, models, project.yaml)
    bioscout web             open BioScout Web in the browser (--local: a local checkout)
    bioscout settings        this computer's settings (~/.bioscout/settings.yaml); also -settings
    bioscout model           check / edit / compare / tune-ma / scale / tps / mri2msk
    bioscout simulate        run an OpenSim/CEINMS stage on a session (or mrs)
    bioscout session         new / export / classify / check-grf / ingest /
                             reset -- reads
                             the results `simulate` writes, so it comes after it
    bioscout plot            figures, summaries, Collings ranking
    bioscout utils           env / install / md2pdf / qr_code / pylance

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
flag argv, and ``__main__.py`` proceeds exactly as before, reading it off the
module-global ``args`` the same way it always did. Verbs whose implementation
is already self-contained and dependency-light (``model check``, ``utils env``)
are dispatched directly and never load the scientific stack at all.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Sequence, Tuple

__all__ = ["VERBS", "build_parser", "route", "main", "legacy_hint"]

#: Root verbs. ``__main__`` checks this before it builds the legacy parser.
VERBS = ("help", "init", "web", "settings", "model", "simulate", "session", "project",
         "plot", "utils")

#: Subcommand -> the verb it lives under. These are the words people reach for
#: at the top level because that is where the old flags were (`bioscout --env`),
#: so a bare `bioscout env` should say where it went rather than "unknown".
NESTED = {
    "env": "utils env", "install": "utils install", "md2pdf": "utils md2pdf",
    "pylance": "utils pylance",
    "new": "session new", "edit": "session edit", "export": "session export",
    "classify": "session classify", "ingest": "session ingest",
    "check-grf": "session check-grf", "check_grf": "session check-grf",
    "reset": "session reset",
    "check": "model check", "compare": "model compare", "tune-ma": "model tune-ma",
    "scale": "model scale", "tps": "model tps", "mrs": "simulate mrs", "project": "init --from-settings",
    "validate": "model validate", "joint-centres": "model joint-centres",
    "jc": "model jc", "measure": "model measure",
    "summary": "plot summary", "jcf": "plot jcf", "figures": "plot figures",
}

_EPILOG = """\
examples:
  bioscout simulate so simulations/023/pre --replace
  bioscout simulate rra simulations/023/pre --iteration gpk --trial Gehen_01
  bioscout simulate forward simulations/023/pre --iteration gpk --trial Gehen_01
  bioscout model check models --strict
  bioscout session new simulations/022/pre
  bioscout plot --list
  bioscout help session

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
    i = sub.add_parser(
        "init", help="create a project: folders, models, templates, project.yaml",
        description="Creates the project skeleton (simulations/, models/, "
                    "setup_files/, logs/, results/) and a starter project.yaml. "
                    "With --from-settings it instead extracts project.yaml from "
                    "the project's EXISTING settings.py (the lab facts that differ "
                    "from bioscout's defaults) -- after a review run, that "
                    "settings.py can be deleted; see docs/IMPLEMENTATIONS.md §2.9.")
    i.add_argument("path", nargs="?", default=".", metavar="PROJECT_PATH")
    i.add_argument("--from-settings", action="store_true", dest="from_settings",
                   help="generate project.yaml from an existing settings.py "
                        "instead of scaffolding a new project")
    i.add_argument("--force", action="store_true",
                   help="with --from-settings: overwrite an existing project.yaml "
                        "(a .bak is kept). Without it: scaffold even when "
                        "models/, setup_files/ ... already exist and are not "
                        "empty (existing files are never overwritten)")

    # -- web / settings ------------------------------------------------------ #
    w = sub.add_parser("web", help="open BioScout Web (the app, in your browser)")
    w.add_argument("--local", nargs="?", const="", metavar="BIOSCOUT_WEB_DIR",
                   help="serve a local bioscout_web checkout instead of the hosted app "
                        "(default folder: BIOSCOUT_WEB_DIR, else C:/Git/bioscout_web)")
    w.add_argument("--port", type=int, default=8765, help="with --local (default 8765)")
    st = sub.add_parser("settings", help="this computer's bioscout settings "
                                          "(~/.bioscout/settings.yaml): logs, terminal output, MA method ...")
    st.add_argument("--show", action="store_true", help="print the values in effect")
    st.add_argument("--reset", action="store_true", help="rewrite the file with the defaults")

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

    ma = ms.add_parser("tune-ma", help="adjust a muscle's moment arm, interactively")
    ma.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    mv = ms.add_parser("validate", help="moment arms, fibre lengths, strength vs literature")
    mv.add_argument("--model", required=True, metavar="OSIM")
    mv.add_argument("--out", metavar="DIR")
    mv.add_argument("--side", default="_r", choices=["_r", "_l"])

    ms.add_parser("mri2msk", help="personalised model from MRI bone segmentations (MRI2MSK: STAPLE, "
                                  "TPS warp, torsion, knee axis); `bioscout model mri2msk -h`",
                  add_help=False)
    mme = ms.add_parser("measure", help="measure bones from STLs, e.g. acetabular coverage",
                        add_help=False)
    mme.add_argument("measure_args", nargs=argparse.REMAINDER)

    mj = ms.add_parser("joint-centres", aliases=["jc"],
                       help="add Harrington hip / midpoint knee-ankle centres to a TRC")
    mj.add_argument("trc", metavar="TRC")
    mj.add_argument("-o", "--out", metavar="FILE")
    mj.add_argument("--alias", action="append", metavar="EXPECTED=ACTUAL",
                    help="marker this lab spells differently, e.g. "
                         "--alias LPSI=LSACR --alias RKNEL=RLFC. Without these "
                         "a lab using other names gets NO joint centres.")

    # `model scale` -- interactive, session-less; `session scale` is the
    # session.yaml-driven one.
    sc_ = ms.add_parser(
        "scale", help="scale a model by answering questions (interactive)",
        description="Needs no project and no settings.py: point it at a generic "
                    ".osim and a static .trc and it works out the rest, asking "
                    "only about what it cannot determine. Shows which "
                    "measurements it can build BEFORE running, and refuses when "
                    "the femurs or tibiae are not measured -- a near-empty "
                    "MeasurementSet scales every body by 1.0 and returns generic "
                    "geometry wearing the subject's mass, which no downstream "
                    "result can reveal.")
    sc_.add_argument("--setup", "--xml", "-xml", dest="setup", metavar="XML",
                     help="run an existing ScaleTool setup XML exactly as "
                          "written (e.g. the scale_setup.xml a previous run "
                          "left beside the model) and ask nothing. Reproduces "
                          "the DIMENSIONAL scaling; marker placement is a "
                          "separate pass, see `bioscout help model`.")
    sc_.add_argument("--model", metavar="OSIM", help="generic (unscaled) model")
    sc_.add_argument("--static", metavar="TRC", help="static-trial markers")
    sc_.add_argument("--markerset", metavar="XML",
                     help="marker set to put on the model (default: its own)")
    sc_.add_argument("--mass", type=float, metavar="KG",
                     help="subject mass; default is measured from the static "
                          "GRF when a grf.mot sits beside the .trc")
    sc_.add_argument("--grf", metavar="MOT",
                     help="static-trial grf.mot to weigh the subject from "
                          "(default: grf.mot beside the .trc)")
    sc_.add_argument("-o", "--out", metavar="OSIM", help="scaled model to write")
    sc_.add_argument("--alias", action="append", metavar="EXPECTED=ACTUAL",
                     help="marker this lab spells differently, e.g. "
                          "--alias LPSI=LSACR. Repeatable; skips the prompt.")
    sc_.add_argument("--no-placer", action="store_true",
                     help="skip marker placement (dimensional scaling only)")
    sc_.add_argument("--no-scaling", action="store_true",
                     help="place markers only, do not resize the model")
    sc_.add_argument("--dry-run", action="store_true",
                     help="decide everything and show the measurements; run nothing")
    sc_.add_argument("-y", "--yes", action="store_true",
                     help="do not prompt; fail rather than ask")

    mt = ms.add_parser("tps", help="build an MRI-personalised model (interactive)",
                       description="Warps a generic model onto MRI/3D-Slicer "
                                   "landmarks. What it produces IS a model, "
                                   "which is why it lives here rather than at "
                                   "the top level.")
    mt.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    # -- simulate -------------------------------------------------------------- #
    # Only the stage groupings that actually exist as separate switches today
    # (Iteration.run() in utils/session.py): IK and ID are one atomic stage
    # there (`do_exbiomec`), and JRA is produced as part of the SO or CEINMS
    # stage, not on its own -- so there's no honest standalone `ik`/`id`/`jra`
    # yet. Splitting those apart is real surgery on code with hard-won
    # production history behind it (see docs/RESTRUCTURE_PLAN.md), left for
    # a later, separately-reviewed step rather than guessed at here.
    sm = sub.add_parser(
        "simulate", help="run an OpenSim/CEINMS stage on one session's model(s)",
        description="Runs a stage of Iteration.run() directly against an "
                    "existing session (needs session.yaml -- see `session new`). "
                    "Model creation/scaling lives under `model`, not here.")
    sms = sm.add_subparsers(dest="action", metavar="ACTION")

    def _simulate_action(name, help_text):
        act = sms.add_parser(name, help=help_text)
        act.add_argument("path", metavar="SESSION_PATH")
        act.add_argument("--iteration", metavar="A,B",
                         help="which model arm(s), comma-separated "
                              "(default: every one on disk)")
        act.add_argument("--trial", metavar="NAME",
                         help="restrict to these trials (comma-separated; "
                              "default: session.yaml's own trial list)")
        act.add_argument("--replace", action="store_true",
                         help="recompute outputs that already exist")
        return act

    _simulate_action("scale", "build each iteration's scaled model from session.yaml "
                              "(only missing ones unless --replace)")
    _simulate_action("emg", "session-wide EMG normalisation -> emg_filtered[_normalised].mot "
                            "(no c3d export; runs once per session)")
    _simulate_action("exbiomec", "inverse kinematics -> inverse dynamics")
    _simulate_action("ma", "muscle analysis")
    _simulate_action("so", "static optimisation -> muscle moments -> joint reaction")
    _simulate_action("rra", "residual reduction algorithm (RRATool) -> <trial>/residual_reduction/ "
                            "(diagnostic: adjusted kinematics, residuals, COM-adjusted model)")
    _simulate_action("cmc", "computed muscle control (CMCTool) -> JRA on the CMC forces "
                            "-> <trial>/joint_contact_forces/output_cmc.sto (+ SO comparison, "
                            "contributions), like SO; no open-loop replay").add_argument(
        "--duration", type=float, metavar="S",
        help="simulate only the first S seconds of the trial window (quick test, e.g. 0.1)")
    _simulate_action("forward", "forward simulation: CMC tracking -> open-loop ForwardTool "
                                "replay + JRA on CMC forces -> <trial>/forward_simulation/ "
                                "(uses the RRA result when present)")
    _simulate_action("mew", "mew (Python muscle solver) -> joint reaction, into <trial>/mew/")
    _simulate_action("figures", "per-trial QC figures: grf_events.png, emg_processing.png")
    _simulate_action("ceinms", "calibrate + execute CEINMS -> joint reaction").add_argument(
        "--calibrate", action="store_true",
        help="(re)calibrate first; default: calibrate only when the iteration "
             "has no ceinms_calibration/subjectCalibrated.xml yet")
    # `simulate mrs` forwards to bioscout.simulate.mrs.cli's own parser (see
    # route()); registered here only so it shows in `bioscout simulate -h`.
    sms.add_parser("mrs", help="Muscle Redundancy Solver (KU Leuven, via MATLAB): "
                               "`simulate mrs check`, `simulate mrs run TRIAL`")

    # -- session ------------------------------------------------------------- #
    s = sub.add_parser("session",
                       help="create, export, classify, check-grf or reset a session")
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

    se = ss.add_parser(
        "export", help="1_c3dfiles/*.c3d -> 2_experimental/<trial>/ (markers, GRF, EMG)",
        description="Reads each trial's .c3d from the session's 1_c3dfiles/ and "
                    "writes, per trial, into 2_experimental/<trial>/: "
                    "marker_experimental.trc, grf.mot + GRF.xml, emg.mot and the "
                    "filtered emg_filtered.mot. These are MODEL-INDEPENDENT "
                    "inputs shared by every iteration, which is why they live "
                    "beside the session and not inside 3_iterations/.")
    se.add_argument("path", metavar="SESSION_PATH")

    sc = ss.add_parser(
        "classify", help="what is each trial? (reads 2_experimental, writes a report)",
        description="Reads the markers and GRF already exported into "
                    "2_experimental/<trial>/ — so run `session export` first — "
                    "and works out what each trial IS (walking, running, squat, "
                    "jump, static...). Writes movement_detection.yaml + .png "
                    "into each trial's folder, plus movement_detection/"
                    "classification.csv (one row per trial), movement_detection/"
                    "trials_valid.csv (trial, valid true/false, reason) and "
                    "movement_detection/movement_detection.yaml (all trials "
                    "in one file). session.yaml is NEVER modified unless you "
                    "pass --write-yaml: disagreements are reported for you to "
                    "accept, not applied.")
    sc.add_argument("path", metavar="SESSION_PATH")
    sc.add_argument("--no-plots", action="store_true", help="skip the per-trial QC figures")
    sc.add_argument("--write-yaml", action="store_true",
                    help="also update session.yaml: trial types and time "
                         "ranges from the detection plus a `valid` tag per "
                         "trial (the old file is kept as "
                         "session.yaml.pre_detection); seeds one when the "
                         "session has none")

    sg = ss.add_parser(
        "check-grf", help="audit which foot each force plate is assigned to",
        description="Re-derives every trial's force-plate -> foot assignment "
                    "from the CURRENT grf.mot + marker TRC and reports where "
                    "the existing GRF.xml disagrees. GRF.xml is written once by "
                    "`session export` and never revisited, so it goes stale "
                    "whenever grf.mot is re-exported or the assignment logic is "
                    "fixed -- and a bilateral trial with both plates on one foot "
                    "gives that leg the whole body weight while the other gets "
                    "none, silently invalidating its ID / SO / JRA. Read-only "
                    "unless you pass --write.")
    sg.add_argument("path", nargs="?", default=".", metavar="PROJECT_OR_SESSION",
                    help="project root (default: the current folder)")
    sg.add_argument("--subject", default="*", help="limit to one subject, e.g. 009")
    sg.add_argument("--session", default="*", help="limit to one session, e.g. pre")
    sg.add_argument("--write", action="store_true",
                    help="regenerate the GRF.xml of every trial that changed")
    sg.add_argument("--csv", dest="csv_path", metavar="PATH",
                    help="where to write the audit table "
                         "(default: <project>/grf_xml_audit.csv)")

    si = ss.add_parser(
        "ingest", help="copy loose .c3d from a capture folder INTO a session",
        description="Takes a folder of raw captures straight off the rig "
                    "(Walk01.c3d, Squat02.c3d, ...) and files them into "
                    "simulations/<subject>/<session>/1_c3dfiles/, creating the "
                    "session folder if needed. This is the step BEFORE "
                    "`session export`: ingest puts the c3d where bioscout "
                    "looks for it, export turns it into trc/mot. Skip it if "
                    "you already copied the c3d in by hand.")
    si.add_argument("folder", metavar="C3D_FOLDER")
    si.add_argument("--subject", required=True)
    si.add_argument("--session", required=True)

    ssc = ss.add_parser(
        "scale", help="scale this session's model(s) from session.yaml",
        description="Builds the scaled model for one session, driven entirely "
                    "by its session.yaml: body_mass (the static GRF wins when "
                    "readable), static_trial, markerset, marker_aliases, and "
                    "each iteration's generic / so_model / linear_scaling / "
                    "marker_placer / mvic_factor. Nothing is typed on the "
                    "command line but WHICH session. Needs no settings.py and "
                    "no project root — just the session folder. `bioscout scale` "
                    "is the interactive, session-less equivalent.")
    ssc.add_argument("path", metavar="SESSION_PATH")
    ssc.add_argument("--iteration", metavar="NAME",
                     help="which model arm (default: every one on disk)")
    ssc.add_argument("--replace", action="store_true",
                     help="rebuild a model that already exists")

    sst = ss.add_parser(
        "stage", help="copy the captures session.yaml names into 1_c3dfiles/",
        description="bioscout reads a capture from <session>/1_c3dfiles/<trial>.c3d "
                    "and nowhere else -- `c3d_source:` in session.yaml is the "
                    "pointer for this copy, not a read path. Stages the trials, "
                    "the static trial, the CEINMS calibration trials and every "
                    "EMG-normalisation capture (the session MVC maximum spans "
                    "all of them). `session ingest` is the loose-folder version.")
    sst.add_argument("path", metavar="SESSION_PATH")
    sst.add_argument("--source", metavar="FOLDER", help="default: session.yaml's c3d_source")
    sst.add_argument("--apply", action="store_true", help="actually copy (default: report)")

    sw = ss.add_parser(
        "windows", help="per-trial time_range from the plates (or the movement detector)",
        description="Without a time_range, IK is solved over the WHOLE capture "
                    "-- of which the participant is in the volume for a second "
                    "or two -- and the session produces nothing. For a trial "
                    "that strikes a plate the window that matters is the stance "
                    "phase (--source grf, the default); for a lift or a squat "
                    "it is the movement detector (--source motion). Every "
                    "window is clipped to the span the markers support. "
                    "Existing windows are kept unless --force, and session.yaml "
                    "is edited as TEXT, so its comments survive.")
    sw.add_argument("path", metavar="SESSION_PATH")
    sw.add_argument("--source", default="grf", choices=["grf", "motion"])
    sw.add_argument("--pad", type=float, default=0.10, metavar="S")
    sw.add_argument("--grf-threshold", type=float, default=20.0, dest="grf_threshold",
                    metavar="N", help="newtons on a plate before it counts as loaded")
    sw.add_argument("--force", action="store_true", help="replace windows that exist")
    sw.add_argument("--trial", action="append", metavar="NAME",
                    help="only this trial (repeatable); default: every exported trial")
    sw.add_argument("--apply", action="store_true", help="write them (default: report)")

    ssd = ss.add_parser(
        "sides", help="which leg each trial loads -> `side:` in session.yaml",
        description="Read from GRF.xml's plate-to-foot assignment (worked out "
                    "at export from the CoP against the foot markers), "
                    "cross-checked against which plates actually carry load "
                    "inside the trial's window.")
    ssd.add_argument("path", metavar="SESSION_PATH")
    ssd.add_argument("--force", action="store_true", help="replace sides that exist")
    ssd.add_argument("--apply", action="store_true", help="write them (default: report)")

    sev = ss.add_parser("events", add_help=False,
                        help="list a trial's task events (hip drive, impact peak, "
                             "bottom of the squat ...) as events.yaml defines them")
    sev.add_argument("events_args", nargs=argparse.REMAINDER)

    sr = ss.add_parser("reset", help="strip trials back to inputs-only")
    sr.add_argument("--subject")
    sr.add_argument("--session")
    sr.add_argument("--trial")
    sr.add_argument("--dry-run", action="store_true", help="preview, touch nothing")
    sr.add_argument("--raw", action="store_true",
                    help="also prune inputs/ down to the raw c3d")

    # -- project ------------------------------------------------------------- #
    pr = sub.add_parser(
        "project", help="the project's own settings: edit, show, status",
        description="project.yaml holds the lab facts that differ from "
                    "bioscout's defaults (axes, EMG rig, muscle groups) and, "
                    "under `project:`, the facts about the project itself: the "
                    "roster, the session states, what a window or a batch "
                    "defaults to. `bioscout init` creates it.")
    prs = pr.add_subparsers(dest="action", metavar="ACTION")

    pre_ = prs.add_parser("edit", help="edit project.yaml in a form")
    pre_.add_argument("path", nargs="?", metavar="PROJECT_PATH")
    pre_.add_argument("--no-gui", action="store_true",
                      help="print the file instead of opening the editor")

    prsh = prs.add_parser("show", help="print project.yaml and where it was found")
    prsh.add_argument("path", nargs="?", metavar="PROJECT_PATH")

    prst = prs.add_parser(
        "status", help="what is on disk per session (runs nothing)")
    prst.add_argument("path", nargs="?", default=".", metavar="PROJECT_PATH")
    prst.add_argument("--subjects", metavar="IDS", help="comma-separated (default: the roster)")
    prst.add_argument("--sessions", metavar="NAMES", help="comma-separated, or 'all'")
    prst.add_argument("--iteration", metavar="NAME")
    prst.add_argument("-v", "--verbose", action="store_true", help="one row per trial")

    prre = prs.add_parser(
        "results", help="every time-varying result -> analysis-ready CSVs in <project>/results",
        description="One CSV per variable (EMG, joint angles/moments, muscle forces, "
                    "activations, lengths, moment arms, JCF ...), time-normalised per "
                    "cycle from movement_detection/cycles.csv. Opens in Excel, JASP, pandas.")
    from bioscout.results.export import add_arguments as _res_args
    _res_args(prre)

    # -- plot ---------------------------------------------------------------- #
    pl = sub.add_parser(
        "plot", help="figures from the results on disk",
        description="Anything that is not `summary`, `collings` or `kinematics` is taken as "
                    "figure keys, so `bioscout plot p01 s_all` and "
                    "`bioscout plot figures p01 s_all` are the same command.")
    pls = pl.add_subparsers(dest="action", metavar="ACTION")

    import argparse as _ap
    pjcc = pls.add_parser("jcf_coverage", add_help=False,
                          help="where a trial's contact forces land on the bones")
    pjcc.add_argument("jcf_coverage_args", nargs=_ap.REMAINDER)

    pjc = pls.add_parser("jcf", help="polar JCF direction/magnitude on the model's bones",
                         add_help=False)
    pjc.add_argument("jcf_args", nargs=_ap.REMAINDER)

    pk = pls.add_parser("kinematics", add_help=False,
                        help="joint angles + IK marker errors across a session's "
                             "iterations -> 4_outputs/kinematics")
    pk.add_argument("kinematics_args", nargs=_ap.REMAINDER)

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

    uq = us.add_parser("qr_code", aliases=["qr"],
                       help="make a QR code for a link (prompts for link and save path)")
    uq.add_argument("link", nargs="?", metavar="URL")
    uq.add_argument("-o", "--out", metavar="FILE", help=".png / .svg / .pdf, or a folder")
    uq.add_argument("--scale", type=int, default=10, help="pixels per module (default 10)")

    up = us.add_parser("pylance", help="write .vscode/settings.json so 'import bioscout' resolves")
    up.add_argument("path", nargs="?", metavar="PROJECT_DIR")

    return p


# --------------------------------------------------------------------------- #
# legacy flags -> the verb that replaced them
# --------------------------------------------------------------------------- #
_LEGACY = {
    "--init": "bioscout init", "--gui": "bioscout web", "-g": "bioscout web",
    "--new-session": "bioscout session new", "--c3d-export": "bioscout session export",
    "--export-session": "bioscout session export",
    "--classifier": "bioscout session classify", "--classify": "bioscout session classify",
    "--ingest-c3d": "bioscout session ingest", "--reset": "bioscout session reset",
    "--model-edit": "bioscout model edit", "--model_edit": "bioscout model edit",
    "--edit": "bioscout model edit",
    "--compare-models": "bioscout model compare",
    "--compare_models": "bioscout model compare",
    "--change-moment-arms": "bioscout model tune-ma", "--ma": "bioscout model tune-ma",
    "--joint-centres": "bioscout model joint-centres",
    "--joint-centers": "bioscout model joint-centres", "--jc": "bioscout model joint-centres",
    "--tps": "bioscout model tps",
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
        return ["--init", ns.path] + (["--init-force"] if getattr(ns, "force", False) else [])

    if v == "session":
        if a == "scale":
            out = ["--scale-session", ns.path]
            _flag(out, "--iteration", ns.iteration)
            _flag(out, "--replace", ns.replace, store_true=True)
            return out
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
        if a == "tune-ma":
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
        if a == "tps":
            return ["--tps"] + ([ns.path] if ns.path else [])
        if a in ("joint-centres", "jc"):
            out = ["--joint-centres", ns.trc]
            _flag(out, "-o", ns.out)
            for a_ in (getattr(ns, "alias", None) or []):
                out += ["--alias", a_]
            return out

    if v == "model" and a == "scale":
        if ns.setup:
            out = ["--scale-setup", ns.setup]
            _flag(out, "--mass", ns.mass)
            return out
        out = ["--scale-model"]
        _flag(out, "--scale-generic", ns.model)
        _flag(out, "--static", ns.static)
        _flag(out, "--markerset", ns.markerset)
        _flag(out, "--mass", ns.mass)
        _flag(out, "--grf", ns.grf)
        _flag(out, "-o", ns.out)
        for a_ in (ns.alias or []):
            out += ["--alias", a_]
        _flag(out, "--no-placer", ns.no_placer, store_true=True)
        _flag(out, "--no-scaling", ns.no_scaling, store_true=True)
        _flag(out, "--dry-run", ns.dry_run, store_true=True)
        _flag(out, "-y", ns.yes, store_true=True)
        return out



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
GUI_MOVED = ("The bioscout desktop GUI was removed in 3.1. For an interface use BioScout Web "
             "(https://basgoncalves.github.io/bioscout-web/) -- it opens the same project folders (project.yaml, session.yaml) "
             "in the browser. `bioscout help` lists the command-line verbs.")


WEB_URL = "https://basgoncalves.github.io/bioscout-web/"


def _web(ns):
    """`bioscout web`: open BioScout Web in the browser (hosted), or with --local serve a
    bioscout_web checkout on http://localhost:<port>/ and open that."""
    import webbrowser
    if getattr(ns, "local", None) is None:
        print(f"[bioscout] opening BioScout Web: {WEB_URL}")
        webbrowser.open(WEB_URL)
        return 0
    import functools
    import http.server
    d = ns.local or os.environ.get("BIOSCOUT_WEB_DIR") or "C:/Git/bioscout_web"
    if not os.path.isfile(os.path.join(d, "index.html")):
        print(f"[bioscout] no index.html in {d} -- pass the bioscout_web folder: bioscout web --local PATH")
        return 1
    url = f"http://localhost:{ns.port}/"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=d)
    with http.server.ThreadingHTTPServer(("127.0.0.1", ns.port), handler) as srv:
        print(f"[bioscout] serving {d} at {url}  (Ctrl+C stops it)")
        webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def _project_yaml_path(path=None):
    """The project.yaml to show/edit: a file, a project folder, or the nearest one
    above the current folder. Returns a Path that may not exist yet."""
    from pathlib import Path
    from bioscout.project_config import find_project_yaml
    if path:
        p = Path(path)
        if p.is_file() or p.suffix.lower() in (".yaml", ".yml"):
            return p
        if (p / "project.yaml").is_file():
            return p / "project.yaml"
        found = find_project_yaml(str(p))
        return Path(found) if found else p / "project.yaml"
    found = find_project_yaml()
    return Path(found) if found else Path.cwd() / "project.yaml"


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

    if v == "session" and a == "check-grf":
        # Self-contained: one module, its own report. Needs opensim only through
        # assign_grfs_to_feet, which is the thing being audited.
        from bioscout.session.grf_check import check_session
        _root = ns.path or "."
        _csv = ns.csv_path or os.path.join(_root, "grf_xml_audit.csv")
        _rows, _chg, _sus = check_session(root=_root, subject=ns.subject,
                                          session=ns.session, write=ns.write,
                                          csv_path=_csv)
        # Non-zero when something is actually wrong, so it is usable in a check
        # script: suspect trials are the real failure, a pending change is not.
        return 1 if _sus else 0

    if v == "init" and getattr(ns, "from_settings", False):
        # Imports the project's settings.py, which needs the full stack — but
        # the extraction itself is one call and prints its own verdict.
        from bioscout.project_config import init_project_yaml
        return init_project_yaml(ns.path, force=ns.force)

    if v == "utils" and a in ("qr_code", "qr"):
        from bioscout.devtools.qrgen import make_qr
        return make_qr(ns.link, ns.out, scale=ns.scale)

    if v == "utils" and a == "env":
        from bioscout.devtools.envcheck import ensure
        st = ensure(create=bool(ns.create))
        return 0 if (st["match"] or st["env_exists"]) else 1

    if v == "web":
        return _web(ns)

    if v == "session" and a in ("stage", "windows", "sides"):
        if a == "stage":
            from bioscout.session.stage import stage_c3d
            stage_c3d(ns.path, source=ns.source, apply=ns.apply)
            return 0
        from bioscout.session import windows as _w
        if a == "windows":
            _w.set_time_ranges(ns.path, trials=ns.trial, source=ns.source,
                               pad=ns.pad, threshold=ns.grf_threshold,
                               force=ns.force, apply=ns.apply)
        else:
            _w.set_sides(ns.path, force=ns.force, apply=ns.apply)
        return 0

    if v == "project":
        resolve_path = _project_yaml_path
        if a == "status":
            from bioscout.core.status import table
            out = table(ns.path, ns.subjects, ns.sessions, ns.iteration, ns.verbose)
            for part in (out if isinstance(out, tuple) else (out,)):
                try:
                    print(part.to_string())
                except AttributeError:
                    for row in part:
                        print(row)
            return 0
        if a == "results":
            from bioscout.results.export import run as _results
            return _results(ns)
        ypath = resolve_path(getattr(ns, "path", None))
        if a == "show" or (a == "edit" and getattr(ns, "no_gui", False)):
            if not ypath.is_file():
                print(f"no project.yaml at {ypath} -- `bioscout init` creates one")
                return 1
            print(f"# {ypath}")
            print(ypath.read_text(encoding="utf-8", errors="replace"))
            return 0
        if a == "edit":
            # no desktop editor any more: show the file and where to edit it
            print(f"# {ypath}  (edit it in a text editor, or in BioScout Web: Project settings)")
            print(ypath.read_text(encoding="utf-8", errors="replace")
                  if ypath.is_file() else "(no project.yaml yet)")
            return 0

    if v == "plot" and a == "jcf":
        from bioscout.plot.jcf_direction import main as _jcf
        return _jcf(ns.jcf_args) or 0

    if v == "plot" and a == "figures":
        from bioscout.plot.figures import main as _figures
        argv = list(ns.keys)
        if ns.list_figures:
            argv.append("--list")
        for name, val in (("--project", ns.project), ("--session", ns.session),
                          ("--subject", ns.subject)):
            if val:
                argv += [name, val]
        return _figures(argv) or 0

    if v == "model" and a == "validate":
        from bioscout.model.inspect.__main__ import main as _mi
        argv = ["all", "--model", ns.model, "--side", ns.side]
        if ns.out:
            argv += ["--out", ns.out]
        return _mi(argv)

    if v == "simulate":
        # Direct dispatch straight to Iteration.run() via the Session it
        # belongs to -- no legacy flag translation exists for this (there is
        # no old flat-flag equivalent of a single simulate stage). Session()
        # raises a clear FileNotFoundError when session.yaml is missing rather
        # than silently doing nothing, which is exactly what a run command
        # should do on a bad path.
        from bioscout.session.recording import Session
        try:
            s = Session(ns.path)
        except FileNotFoundError as e:
            print(f"[simulate] {e}", file=sys.stderr)
            return 1
        iterations = ([i.strip() for i in ns.iteration.split(",") if i.strip()]
                      if ns.iteration else None)
        trials = [t.strip() for t in ns.trial.split(",")] if ns.trial else None
        if iterations:
            _known = set(s.iterations) | set((s._cfg.get("iterations") or {}))
            _bad = [i for i in iterations if i not in _known]
            if _bad:
                print(f"[simulate {a}] no iteration(s) {_bad} in {ns.path} -- have "
                      f"{', '.join(sorted(_known))}", file=sys.stderr)
                return 1
        # -- stages that are not Iteration.run() flags -------------------------
        if a == "scale":
            bad = 0
            for it in (iterations or s.iterations):
                try:
                    s.iteration(it).scale_model(replace=bool(ns.replace))
                    print(f"[simulate scale] {it}: ok")
                except Exception as e:                           # noqa: BLE001
                    bad += 1
                    print(f"[simulate scale] {it}: FAILED -- {type(e).__name__}: {e}",
                          file=sys.stderr)
            return 1 if bad else 0
        if a == "emg":
            # session-wide: the [0, 1] reference spans every trial of the session,
            # so it is one call whatever --iteration/--trial say
            it = (iterations or s.iterations)[0]
            s.iteration(it).run_emg_normalise(replace=bool(ns.replace))
            print(f"[simulate emg] {s.name}: normalised across all trials")
            return 0
        if a == "figures":
            made, failed = 0, []
            for it in (iterations or s.iterations)[:1]:      # inputs are per trial, not per model
                itr = s.iteration(it)
                for name in (trials or [t for t, m in (s._cfg.get("trials") or {}).items()
                                        if str((m or {}).get("type", "")).lower() != "static"]):
                    tr = itr.trial(name)
                    for what, fn in (("grf_events", tr.plot_grf_events),
                                     ("emg_processing", tr.plot_emg_processing)):
                        try:
                            fn()
                            made += 1
                        except Exception as e:                   # noqa: BLE001
                            failed.append(f"{name}/{what}: {type(e).__name__}: {e}")
            print(f"[simulate figures] {made} written" + (f", {len(failed)} failed" if failed else ""))
            for f in failed[:8]:
                print(f"    {f}")
            return 0
        stage_kwarg = {"exbiomec": "do_exbiomec", "ma": "do_muscle_analysis",
                       "so": "do_so", "rra": "do_rra", "cmc": "do_cmc", "forward": "do_forward", "mew": "do_mew", "ceinms": "do_ceinms"}[a]
        if a == "ceinms":
            import os
            results = {}
            for it in (iterations or s.iterations):
                itr = s.iteration(it)
                cal = bool(ns.calibrate) or not os.path.exists(os.path.join(
                    itr.path, "ceinms_calibration", "subjectCalibrated.xml"))
                results.update(s.run(iterations=[it], trials=trials, calibrate=cal,
                                     replace=bool(ns.replace), do_ceinms=True))
        else:
            _extra = ({"cmc_duration": ns.duration}
                      if a == "cmc" and getattr(ns, "duration", None) else {})
            results = s.run(iterations=iterations, trials=trials,
                            replace=bool(ns.replace), **{stage_kwarg: True}, **_extra)
        # one line per iteration: what ran, what was skipped, ok or not --
        # the raw dict repeated every stage's empty lists and the report twice
        for _it, _r in (results or {}).items():
            if not isinstance(_r, dict):
                print(f"[simulate {a}] {_it}: {_r}")
                continue
            _done = {k: v for k, v in _r.items()
                     if isinstance(v, list) and v and k not in ("skipped",)}
            _bits = [f"{k}: {', '.join(map(str, v))}" for k, v in _done.items()]
            if _r.get("skipped"):
                _bits.append(f"skipped: {', '.join(map(str, _r['skipped']))}")
            _miss = (_r.get("report") or {}).get("missing") or []
            if _miss:
                _bits.append(f"MISSING: {', '.join(map(str, _miss))}")
            print(f"[simulate {a}] {_it}: {'; '.join(_bits) or 'nothing to do'}"
                  f"  -> {'ok' if _r.get('ok') else 'NOT OK'}")
        return 0

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

    # `simulate mrs` owns its own parser (same forwarding trick as `plot jcf`).
    if argv[:2] == ["simulate", "mrs"]:
        from bioscout.simulate.mrs.cli import main as _mrs
        return ("exit", _mrs(argv[2:]) or 0)

    # `run` forwards its whole tail: it owns its own parser and detaches.
    if argv[:1] == ["run"]:
        from bioscout.core.batch import main as _run
        return ("exit", _run(argv[1:]) or 0)

    # `model measure` forwards its whole tail to bioscout.model.measure.
    # `model mri2msk` forwards its whole tail to bioscout.model.mri2msk.cli.
    if argv[:2] == ["model", "mri2msk"]:
        from bioscout.model.mri2msk.cli import main as _mri
        return ("exit", _mri(argv[2:]) or 0)

    if argv[:2] == ["model", "measure"]:
        from bioscout.model.measure import main as _measure
        return ("exit", _measure(argv[2:]) or 0)

    # `plot jcf` forwards its whole tail to the module's own parser (argparse
    # REMAINDER does not reliably swallow leading options like -h).
    if argv[:2] == ["plot", "jcf_coverage"] or argv[:2] == ["plot", "jcf-coverage"]:
        from bioscout.plot.jcf_coverage import main as _jcfc
        return ("exit", _jcfc(argv[2:]) or 0)

    # `session events TRIAL`: which instants the figures will show, from
    # bioscout/session/events.yaml (+ project.yaml / session.yaml overrides)
    if argv[:2] == ["session", "events"]:
        from bioscout.session.events import main as _sev
        return ("exit", _sev(argv[2:]) or 0)

    if argv[:2] == ["plot", "jcf"]:
        from bioscout.plot.jcf_direction import main as _jcf
        return ("exit", _jcf(argv[2:]) or 0)

    # `plot kinematics SESSION`: joint angles and IK marker errors compared
    # across iterations, into <session>/4_outputs/kinematics (as `plot collings`
    # does for muscle rankings). Own parser, same reason as `plot jcf`.
    if argv[:2] == ["plot", "kinematics"]:
        from bioscout.plot.kinematics import main as _kin
        return ("exit", _kin(argv[2:]) or 0)

    # `bioscout plot p01 s_all` == `bioscout plot figures p01 s_all`. argparse
    # cannot have both a free positional list and subcommands on one parser, so
    # the default action is inserted here rather than fought for in the grammar.
    if len(argv) >= 1 and argv[0] == "plot":
        rest = argv[1:]
        # `plot --help` must show the VERB's help — the list of actions — not
        # the default action's, or summary and collings become undiscoverable.
        if rest and rest[0] in ("-h", "--help"):
            pass
        elif not rest or rest[0] not in ("figures", "summary", "collings", "jcf",
                                         "jcf_coverage", "jcf-coverage",
                                         "kinematics"):
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
    if ns.verb in ("session", "model", "utils", "plot", "simulate",
                   "project") and not getattr(ns, "action", None):
        parser.parse_args([ns.verb, "--help"])          # exits

    code = _direct(ns)
    if code is not None:
        return ("exit", code)

    return ("legacy", _to_legacy(ns))


#: verbs whose output belongs in the log, not on the terminal: they print
#: hundreds of OpenSim lines over minutes, and the one line worth reading
#: scrolls away. --verbose puts the stream back.
_QUIET_VERBS = {("simulate",), ("session", "export"), ("session", "classify"),
                ("session", "scale")}


def _is_quiet_verb(argv) -> bool:
    return any(tuple(argv[:len(k)]) == k for k in _QUIET_VERBS)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Standalone entry: ``python -m bioscout.cli <verb> ...``."""
    argv_in = list(sys.argv[1:] if argv is None else argv)
    # `bioscout -settings`: this computer's bioscout settings (~/.bioscout/settings.yaml)
    from bioscout import user_settings as _us
    if argv_in and argv_in[0] in ("-settings", "--settings", "settings"):
        return _us.command(argv_in[1:])
    _uset = _us.apply()                       # file -> environment (a shell variable wins)
    verbose = "--verbose" in argv_in or "-v" in argv_in or bool(_uset.get("log_terminal"))
    argv_in = [a for a in argv_in if a not in ("--verbose", "-v")]
    if verbose:
        os.environ["BIOSCOUT_VERBOSE"] = "1"     # verbs with a short default report read this
    if _is_quiet_verb(argv_in) and not verbose:
        from bioscout.utils import shared as _sh
        _sh.set_quiet_console(True)
    kind, value = route(argv_in)
    if kind == "exit":
        return int(value)                                # type: ignore[arg-type]
    import runpy
    os.environ["BIOSCOUT_FROM_VERB"] = "1"   # legacy-flag hint is for typed flags only
    sys.argv = [sys.argv[0]] + list(value)               # type: ignore[arg-type]
    runpy.run_module("bioscout", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
