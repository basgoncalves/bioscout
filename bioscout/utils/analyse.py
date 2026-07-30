"""Command-line entry point: run Analyse methods on a trial folder.

    python -m bioscout.utils.analyse <trial_dir> [method ...] [--project DIR]

Examples
--------
    # default: regenerate the JRA SO-vs-CEINMS comparison figure
    python -m bioscout.utils.analyse simulations/Athlete_03_Cateli/25_03_31/Walking_02

    # run several plotting methods in one go
    python -m bioscout.utils.analyse .../Walking_02 plot_jra_comparison plot_so plot_ik_id_summary

    # bind an explicit project (otherwise the nearest parent settings.py is used)
    python -m bioscout.utils.analyse .../Walking_02 --project C:/Users/Basilio/ucloud/Powerlifiting

If ``--project`` is omitted, the nearest parent directory containing a
``settings.py`` is bound via ``bioscout.Project`` so that project-level config
(JRA_COLUMNS, literature styling, model paths, log location, ...) comes from YOUR
project rather than the bundled template.
"""
from __future__ import annotations

import argparse
import os


def _find_project(start):
    """Nearest ancestor directory (incl. start) that contains a settings.py."""
    d = os.path.abspath(start)
    while d and d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, "settings.py")):
            return d
        d = os.path.dirname(d)
    return None


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m bioscout.utils.analyse",
        description="Run one or more Analyse methods on a trial folder "
                    "(default: plot_jra_comparison).")
    p.add_argument("trial", help="path to the trial directory (contains trial_settings.xml)")
    p.add_argument("methods", nargs="*",
                   help="Analyse method name(s) to call (default: plot_jra_comparison)")
    p.add_argument("--project", default=None,
                   help="project dir to bind settings (default: nearest parent settings.py)")
    a = p.parse_args(argv)

    trial = os.path.abspath(a.trial)
    if not os.path.isdir(trial):
        p.error(f"trial directory not found: {trial}")
    methods = a.methods or ["plot_jra_comparison"]

    import bioscout
    proj = a.project or _find_project(trial)
    if proj:
        try:
            bioscout.Project(proj, setup_editor=False)
        except Exception as e:
            print(f"[warn] could not bind project {proj}: {e}")
    else:
        print("[warn] no project settings.py found near the trial; "
              "using bundled template defaults")

    from bioscout.utils.analysis import Analyse

    # session-level verbs (normalise_emg / calibrate / prepare_ceinms / run ...)
    # live on Iteration (the runnable unit); get_session() returns one.
    from bioscout.utils.session import Iteration as Session
    t = Analyse(trial)

    # Lazily-built Session for the trial's parent folder, so session-scoped verbs
    # (normalise_emg, calibrate, prepare_ceinms, ...) can be called from the same
    # CLI without a separate `python -c` incantation. Layout is
    # <Subject>/<Session>/<Trial>, so the trial sits one level below the session.
    _sess = {"obj": None, "tried": False}
    def _get_session():
        if _sess["tried"]:
            return _sess["obj"]
        _sess["tried"] = True
        sess_dir = os.path.dirname(trial)
        subj_name = os.path.basename(os.path.dirname(sess_dir))
        sess_name = os.path.basename(sess_dir)
        s = None
        if proj:
            try:
                import bioscout as _b
                p = _b.Project(proj, setup_editor=False)
                s = p.subject(subj_name).get_session(sess_name)
            except Exception as e:
                print(f"[warn] could not resolve Session {subj_name}/{sess_name}: {e}")
        _sess["obj"] = s
        return s

    for meth in methods:
        fn = getattr(t, meth, None)
        if callable(fn):
            print(f"[analyse] {os.path.basename(trial)} -> {meth}()")
            fn()
            continue
        # Not a trial method — try the session (normalise_emg, calibrate, ...).
        if hasattr(Session, meth):
            s = _get_session()
            sfn = getattr(s, meth, None) if s is not None else None
            if callable(sfn):
                print(f"[analyse] session {os.path.basename(os.path.dirname(trial))} "
                      f"-> {meth}()")
                sfn()
                continue
            print(f"[error] could not bind a Session to run '{meth}' for {trial}")
            continue
        print(f"[error] neither Analyse nor Session has method '{meth}'")


if __name__ == "__main__":
    main()
