# `bioscout plot jcf` — JCF direction/magnitude polar plot

Polar plot of the joint contact force vector on the model's own bones, for
anyone who has run an OpenSim JointReaction analysis. One panel per joint:
the **bearing** is the force direction in one plane of the receiving bone's
reference frame (SUP up, ANT right on the sagittal view), the **radius** is
|JCF| (in body weights when a body weight is given, else kN). A loop is the
contact-force vector traced over the trial; `o` marks the start, `x` the end.
The grey silhouette is the bone itself, read out of the `.osim` (mesh files,
scale factors, offset frames) — its angles are exact, its radial size is
scaled to fill the panel.

Module: `bioscout/plot/jcf_direction.py`. Pure numpy + matplotlib — no
OpenSim install needed (the `.osim` and `.vtp` files are read as plain XML).

## Terminal

    bioscout plot jcf --model model.osim \
        --jra jra_SO.sto jra_CEINMS.sto --labels SO CEINMS \
        --mass 95 --ik joint_angles.mot -o jcf_direction.png

    # equivalent without installing:
    python -m bioscout.plot.jcf_direction --model ... --jra ...

Arguments

    --model   the .osim (bones + the hip frame conversion)
    --jra     one or more JointReaction *ReactionLoads*.sto files
    --labels  legend label per file (default: file names)
    --joints  joint names as in the columns (default: the hip/knee/ankle
              joints found in the file, right side preferred)
    --mass    body mass in kg  (or --bw, body weight in N) -> radius in BW
    --ik      the trial's IK .mot -> hip re-expressed in the PELVIS frame
    --plane   sagittal (default, SUP/ANT) or frontal (SUP/LAT, right limb)
    --geometry  extra folders to search for .vtp meshes
    -o        output png

## From a script

    from bioscout.plot.jcf_direction import plot_jcf_direction
    plot_jcf_direction("model.osim",
                       {"SO": "jra_so.sto", "CEINMS": "jra_ceinms.sto"},
                       mass=95, ik="joint_angles.mot",
                       out="jcf_direction.png")

## Notes

- The JRA must have been run with the reaction applied to the CHILD body,
  expressed in the CHILD frame (OpenSim's default), giving columns like
  `hip_r_on_femur_r_in_femur_r_fx`.
- The hip file therefore holds the force in the FEMUR frame. With `--ik`
  it is converted exactly to the femoral head on the acetabulum in the
  pelvis frame (Newton's third law + the hip's own SpatialTransform
  rotation at the IK angles); without `--ik` it is plotted as written and
  the panel title says which frame.
- Joints other than hip/knee/ankle plot fine, just without a bone drawing.
- `--plane frontal` labels assume a RIGHT limb (+z lateral); on a left limb
  read LAT/MED swapped.
- With `--ik` the neighbouring segment (femur / femur / tibia) is also drawn
  dotted at the two extremes of its motion, with a range-of-motion arc and
  the degrees at the rim — the manuscript figure's grammar. The compass and
  the ring labels appear on the first panel only, and all panels share one
  radial scale.
- Simplified vs the manuscript's figure4.py: one trial per call, no
  repetition or model averaging, no task grid.
