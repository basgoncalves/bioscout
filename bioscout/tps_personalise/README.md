# `bioscout.tps_personalise`

Thin-plate-spline personalisation of OpenSim models from segmented MRI bone
geometry. Per bone (pelvis, femur, tibia, patella) a TPS is fitted from the
generic model's bone landmarks onto the subject's MRI landmarks, then applied
to muscle path points, markers, wrap surfaces, joint centres and bone meshes.

Ported from the standalone `tps-personalise` package (itself a refactor of
Ekaterina Stansfield's notebook pipeline). See `../../CHANGELOG.md` for the
version this landed in.

## Quick start

From a bioscout session (the normal path):

```python
from bioscout.tps_personalise import personalise_iteration

personalise_iteration(
    "simulations/Athlete_03/25_03_31", "rajagopal",
    mri_landmarks="models/Athlete_03_MRI_Katya/25_03_31/orientation_Katya.mrk.json",
)
# -> "generic models/Rajagopal2015_tps_Athlete_03.osim"
```

Standalone, from YAML:

```bash
python -m bioscout.tps_personalise --config config.yaml
```

## What changed versus the standalone package

**OpenSim 3.x support.** `osim_format.py` normalises the two schemas
(`<body>` vs `<socket_parent_frame>`, `location_in_parent` vs
`PhysicalOffsetFrame/translation`, `DisplayGeometry/geometry_file` vs
`Mesh/mesh_file`). Rajagopal2015 as distributed is a Version 30000 document, so
without this the whole model parsed as empty — 0 path points, 0 markers, no
error.

**No third-party TPS dependency.** `_tps_backend.py` implements the same
spline in numpy. The external `thin-plate-spline` package is still used when
installed, so results are unchanged for existing environments.

**Frame-compatibility checking.** The bone-landmark template stores landmarks
*in a model's body frames*, so reusing it across generic models is only valid
if those frames coincide. `model_compat.py` verifies this by checking that both
models attach the same bone meshes to the same bodies, unscaled and untransformed
— a sufficient condition, since the mesh vertices are in a fixed anatomical
frame. The check runs before any warping and raises by default: a mismatched
template does not error anywhere downstream, it just yields a wrong model.

For the four models in the powerlifting study the check passes on all of them,
so the single bundled template (`data/markers_and_bone_markers_in_bodies.xml`,
authored in GPK frames) covers GPK, Catelli, Lernagopal and Rajagopal2015:

```
bodies verified identical : pelvis, femur_r, femur_l, tibia_r, tibia_l, patella_r, patella_l
-> COMPATIBLE
```

**Joint-centre presets.** `MODEL_PRESETS` in `osim_model.py` holds the
joint-name → landmark wiring per model family (`walker_knee` for
Rajagopal/Catelli, `lerner_knee` for GPK/Lernagopal) and
`detect_joint_centre_preset()` picks one from the model's own joint names.
Previously the walker-knee map was the hard default, so Lerner-knee models
kept their generic knee centres and only logged a warning.

## Validation

Personalising Rajagopal2015 and GPK from the same MRI landmark set produces
**identical** hip and ankle joint centres (`hip_r = [-0.0513, -0.0746,
0.0859]`, `ankle_r = [0.0001, -0.4039, 0.0]`), which is the expected invariant:
the joint centres come from the subject's anatomy, not from which generic model
was warped. Segment lengths move by realistic amounts (Rajagopal thigh
0.408 → 0.396 m, shank 0.400 → 0.404 m) and muscle path points shift a mean of
9.8 mm (max 32 mm).

## Caveats

* **Bone meshes need `pyvista`.** Without it the personalised model keeps the
  source model's meshes. The joint centres, muscle paths and wraps — everything
  that affects a simulation result — are still personalised; only the visual
  geometry is generic. This is logged, not fatal.
* **`opensim` is optional but recommended.** When importable, the written model
  is loaded and re-serialised through the OpenSim API, which both validates it
  and produces canonical formatting. Without it the raw ElementTree output is
  written.
* **Moving path points are not warped.** `MovingPathPoint` locations are
  functions of a coordinate; warping their constants would corrupt the model,
  so they are skipped.
* The `landmarks_from_mri` auto-landmark extractor carries one known failing
  test (`test_extreme_and_region_pick_the_right_end`) inherited from the
  standalone package; it does not affect the personalisation path.
