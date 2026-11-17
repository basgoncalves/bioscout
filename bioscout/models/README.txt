Bundled OpenSim models
======================

    generic/<Model>/<model>.osim        one folder per generic model
    generic/<Model>/Geometry/           only the meshes that model uses

`bioscout init` (and `bioscout.Project(path)` on a new folder) copies generic/ into
<project>/models/generic/ and creates <project>/models/personalised/ for the scaled
models (personalised/<subject>/<session>/).

    generic/GPK/                  GPK_v4_016 -- default lower-body model (+ provenance.json:
                                  what changed relative to GPK_v4_015, and why)
    generic/Rajagopal2015/        Rajagopal 2015 full body (no meshes bundled)
    generic/Full_Body_with_ball/  full body + ball (video tools)
    generic/Digital_Athlete/      GPK lower limb + Full_Body upper body
                                  (build_digital_athlete.py rebuilds it)
    generic/arm26_ball/, generic/Neck_model/   video tools; no meshes bundled

Geometry folders are gitignored (*Geometry/); keep each model's meshes in its own
generic/<Model>/Geometry/ so a copied model folder is complete on its own.

The .py / .pkl / FORCE_MODEL.md files here are the joint-force regression
(force_model.py), not OpenSim models, and are not copied into projects.
