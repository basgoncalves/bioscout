# `bioscout.model.mri2msk`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/__init__.py)

MRI2MSK: personalised musculoskeletal models from MRI bone segmentations.

Python port of the MRI2MSK MATLAB toolbox (W. Koller, Univ. Vienna), moved into bioscout from  
MRI2MSKpy (2026-11-04). The generic model is warped to the participant's MRI-segmented bones  
(STAPLE joint coordinate systems, thin-plate-spline warping) and then corrected (skin,  
torsion, mass centres, mechanical knee axis).

    bioscout model mri2msk -h                 the steps from the command line  
    from bioscout.model.mri2msk import Config, step1_rescale_and_align, ...

The desktop GUI is gui.py (`bioscout model mri2msk gui`); docs: README.md, WORKFLOW.md.

## Available as `bioscout.model.mri2msk.<name>`

- [`bioscout.model.mri2msk.Config`](bioscout.model.mri2msk.pipeline.md#config) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.BoneAlignment`](bioscout.model.mri2msk.pipeline.md#bonealignment) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.load_prealignment`](bioscout.model.mri2msk.pipeline.md#load_prealignment) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.save_prealignment`](bioscout.model.mri2msk.pipeline.md#save_prealignment) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step1_rescale_and_align`](bioscout.model.mri2msk.pipeline.md#step1_rescale_and_align) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step2_align_skin`](bioscout.model.mri2msk.pipeline.md#step2_align_skin) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step2b_add_skin_to_base_model`](bioscout.model.mri2msk.pipeline.md#step2b_add_skin_to_base_model) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step4_create_warp_setup`](bioscout.model.mri2msk.pipeline.md#step4_create_warp_setup) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step5_warp_model`](bioscout.model.mri2msk.pipeline.md#step5_warp_model) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step6_replace_skin`](bioscout.model.mri2msk.pipeline.md#step6_replace_skin) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step7a_correct_torsion`](bioscout.model.mri2msk.pipeline.md#step7a_correct_torsion) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step7b_correct_mass_centers`](bioscout.model.mri2msk.pipeline.md#step7b_correct_mass_centers) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.step8_mechanical_knee_axis`](bioscout.model.mri2msk.pipeline.md#step8_mechanical_knee_axis) — from `bioscout.model.mri2msk.pipeline`
- [`bioscout.model.mri2msk.detect_completed_steps`](bioscout.model.mri2msk.pipeline.md#detect_completed_steps) — from `bioscout.model.mri2msk.pipeline`
