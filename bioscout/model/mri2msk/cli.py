"""`bioscout model mri2msk`: the MRI2MSK steps from the command line.

    bioscout model mri2msk gui                 the desktop GUI (steps 1-8 + Post-Warp tab)
    bioscout model mri2msk status --participant DIR --base-model FILE
    bioscout model mri2msk <step> --participant DIR --base-model FILE
    bioscout model mri2msk 3 --participant DIR --base-model FILE --n 25
        (auto landmarks; --n one number for all bones or e.g. pelvis=30,tibia_l=20)
    bioscout model mri2msk post --participant DIR --base-model FILE [--session DIR] [--mass KG]
        (Post-Warp on a BioScout session: export, scale, IK, ID, SO, JRA, JCF contributions)
"""
import argparse
from pathlib import Path
import json

from . import pipeline as pl

STEPS = {
    "1": pl.step1_rescale_and_align, "2": pl.step2_align_skin,
    "2b": pl.step2b_add_skin_to_base_model, "4": pl.step4_create_warp_setup,
    "5": pl.step5_warp_model,
    "6": pl.step6_replace_skin, "7a": pl.step7a_correct_torsion,
    "7b": pl.step7b_correct_mass_centers, "8": pl.step8_mechanical_knee_axis,
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bioscout model mri2msk", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["gui", *STEPS, "3", "post", "status"],
                    help="gui (the desktop app), 1 2 2b 3 4 5 6 7a 7b 8 (the warping steps), status, "
                         "post (scale..JCF on a session)")
    ap.add_argument("--participant")
    ap.add_argument("--base-model")
    ap.add_argument("--yes", action="store_true", help="step 8: apply MKA without plot/prompt")
    ap.add_argument("--mass", type=float, help="post: participant mass in kg (needed for scaling)")
    ap.add_argument("--post-steps", default="export,scale,ik,id,so,jra,jcf", help="post: comma list of steps")
    ap.add_argument("--session", help="post: BioScout session folder, e.g. <participant>/session1")
    ap.add_argument("--n", default="25", help="step 3: landmarks per bone, '25' or 'pelvis=30,femur_l=25,...'")
    a = ap.parse_args(argv)
    if a.step == "gui":
        from .gui import main as gui_main
        return gui_main()
    if not (a.participant and a.base_model):
        ap.error("--participant and --base-model are required for command-line steps")
    cfg = pl.Config(a.participant, a.base_model)
    if a.step == "status":
        print(json.dumps(pl.detect_completed_steps(cfg), indent=2))
    elif a.step == "post":
        from . import postwarp as pw
        p = cfg.participant_folder
        sess = Path(a.session) if a.session else (pw.find_sessions(p) or [None])[0]
        if sess is None:
            ap.error("no session folder found - pass --session <participant>/<session>")
        mass = a.mass or pw.detect_body_mass(p, sess)
        ps = pw.PostWarpSession(sess, p, pw.latest_warped_model(p), mass)
        if not ps.exists():
            ps.create()
        steps = [s.strip() for s in a.post_steps.split(",") if s.strip()]
        print(f"session: {sess}\nmodel: {ps.warped_model}\nmass: {mass}\ntrials: {ps.trials()}")
        if "export" in steps:
            ps.run_export()
        if "scale" in steps:
            ps.run_scale()
        for t in ps.trials():
            for s in steps:
                if s in pw.TRIAL_STEPS:
                    print(f"[{t}] {s}")
                    ps.run_trial(s, t)
    elif a.step == "3":
        from . import landmarks as lm
        if "=" in a.n:
            counts = {k.strip(): int(v) for k, v in (kv.split("=") for kv in a.n.split(","))}
            counts = {b: counts.get(b, 25) for b in pl.LANDMARK_BONES}
        else:
            counts = {b: int(a.n) for b in pl.LANDMARK_BONES}
        lm.auto_landmarks_for_participant(pl.prepare_mesh_warper_files(cfg), counts)
    elif a.step == "8":
        confirm = True if a.yes else (lambda c: input(f"Apply {c}? [y/N] ").lower().startswith("y"))
        print(pl.step8_mechanical_knee_axis(cfg, confirm=confirm, show_plot=not a.yes))
    else:
        print(STEPS[a.step](cfg))


if __name__ == "__main__":
    raise SystemExit(main())
