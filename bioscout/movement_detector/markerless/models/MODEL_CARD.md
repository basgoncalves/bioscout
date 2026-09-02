# Bundled force model

## kinematics_only_model.pkl — AUDIT FAILED, DO NOT USE

**Status as of 2026-09-02: this model is broken and is no longer the default.**
`load_model()` defaults to `"none"`; you must ask for `kinematics_only`
explicitly, and the app will still reject its output on plausibility grounds.

### The evidence

`python tools/audit_model.py --ik <a real joint_angles.mot>` reproduces all of
this. On a **real gait trial from the training dataset**
(`simulations/022/pre/.../Run_baselineA1`), with **all 34 inputs present** — no
camera estimation, no zero-filling, nothing out of domain:

| Input | Peak predicted force |
|---|---|
| All inputs at the training mean | 1,110 N (plausible) |
| `knee_angle_r` +1 sigma, all else at mean | 32,583 N |
| `knee_angle_r` +2 sigma | 309,437 N |
| 2000 samples drawn from the training distribution | 271,107,162 N |
| Real training-set gait trial, 34/34 inputs | 113,250 N |

The largest human muscle produces a few thousand newtons. Clipping every input
to ±2 sigma of the training mean does not help (2,609,839 N), and neither does
replacing the one genuinely odd coordinate, `pelvis_rotation`, with its
training mean — that makes it worse (4,577,102 N). So this is not a
domain-of-application problem. The model does not work on the data it was fitted
to.

### The likely cause

The one place it behaves is exactly at the training mean, where `Z = 0`, the
`Z @ W1` term vanishes and the hidden layer is `activation(b1)` — the bias path
alone. Correct at the mean and divergent everywhere else is the signature of a
**forward pass missing its normalisation**. The torch `MuscleForceNet` in
`code/ml_model.py` is `Linear → BatchNorm1d → ReLU → 3 residual blocks (each
with two BatchNorms) → Linear`. This pickle holds only `W1 b1 W2 b2` — a bare
two-layer net. It cannot be that architecture, and if it was exported from it,
the BatchNorm running statistics were dropped.

Note also that no script in the repo produces this file: `kinematics_only`
appears nowhere in `code/` or `notebook.ipynb`. It is an orphan artifact with no
provenance.

### What to do

1. Find or rewrite the export. If it came from the torch model, fold the
   BatchNorm parameters into the adjacent Linear weights rather than discarding
   them.
2. Or retrain a genuine kinematics-only model and export it with an audit
   attached.
3. Either way, make `tools/audit_model.py` pass before wiring it back in.

### What it was meant to be

A CEINMS surrogate for the FAIS gait dataset. 34 joint angles (deg, OpenSim
Rajagopal conventions) -> 128 hidden -> 80 lower-limb muscle forces. Stored as a
dict of numpy arrays (`W1 b1 W2 b2 xm xs ym ys feat targ info`), ~4,300 weights,
no torch or scikit-learn needed — which is why it was attractive for a phone.

Its targets are standardised **log1p** forces: `ym` spans 0.65..5.77 and `ys`
spans 1.10..3.71, which is the range of log1p newtons, not of newtons. The
hidden activation is unrecorded; **tanh** is the working assumption, since at
the training mean it gives 1,110 N against relu's 432 N and the "no transform"
variants give a nonsensical 7 N. That log scaling is also why the failure is so
violent: an error of a few units in log space is three orders of magnitude in
newtons.

### It was never valid for pull-ups either

Independently of the audit failure: all 80 outputs are lower-limb muscles —
adductors, hamstrings, quadriceps, glutes, triceps surae, iliopsoas. There is no
latissimus dorsi, biceps brachii, brachialis, trapezius or rhomboid. The muscles
that do the work in a pull-up are not in the output vector, and only 9 of its 34
inputs are recoverable from a single camera.

For **squats** the muscle list is right and the inputs are recoverable (11 of 34,
sitting within ~3.7 sigma of the training data). Had the model worked, squats
would have been a reasonable extrapolation. That remains the case for a
*replacement* model — see below.

## What a working model would need

For **squats**, an honest surrogate needs one thing this one structurally
cannot provide: **knowledge of external load**. It takes joint angles and
nothing else, so an empty bar and a 200 kg squat at identical depth and tempo
produce identical inputs and therefore identical predictions. That is tolerable
in gait, where body mass is the load and roughly constant — which is probably
why a kinematics-only surrogate was viable there at all — and untenable for
loaded lifting. Bodyweight squats are the case where the assumption holds.

For **pull-ups**, a model needs upper-limb and trunk outputs (lat, teres major,
biceps, brachialis, brachioradialis, posterior deltoid, lower trapezius,
rhomboids, pec major sternal head) and pull-up training data — forward or
tracking simulations on an upper-limb OpenSim model with the bar as an external
load.

Implement `ForceModel` in `pullupkit/forces.py`, add it to `REGISTRY`, and the
rest of the app picks it up unchanged.

## pose_landmarker_full.task

MediaPipe Pose Landmarker (full), copied from the BioScout repo. Bundled so the
app never needs a network connection.
