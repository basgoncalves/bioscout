"""MRI2MSK: personalised musculoskeletal models from MRI bone segmentations.

Python port of the MRI2MSK MATLAB toolbox (W. Koller, Univ. Vienna), moved into bioscout from
MRI2MSKpy (2026-11-04). The generic model is warped to the participant's MRI-segmented bones
(STAPLE joint coordinate systems, thin-plate-spline warping) and then corrected (skin,
torsion, mass centres, mechanical knee axis).

    bioscout model mri2msk -h                 the steps from the command line
    from bioscout.model.mri2msk import Config, step1_rescale_and_align, ...

The desktop GUI is gui.py (`bioscout model mri2msk gui`); docs: README.md, WORKFLOW.md.
"""
from .pipeline import (  # noqa: F401
    Config, BoneAlignment, load_prealignment, save_prealignment,
    step1_rescale_and_align, step2_align_skin, step2b_add_skin_to_base_model,
    step4_create_warp_setup, step5_warp_model, step6_replace_skin, step7a_correct_torsion,
    step7b_correct_mass_centers, step8_mechanical_knee_axis, detect_completed_steps,
)

__version__ = "0.1.0.dev0"
