# Muscle contributions to the joint contact force

`bioscout.utils.jcf_contributions` + `Analyse.run_jra_contributions()`

## The idea

At fixed kinematics OpenSim's `JointReaction` is **linear in the applied
actuator forces**, so the contact force of a joint splits exactly:

```
JCF_total(t) = JCF_base(t) + Σ_g [ JCF_g(t) − JCF_base(t) ]
```

* `JCF_base` — the analysis with **every muscle force zeroed**: gravity, segment
  inertia, the GRF, the residuals and the reserves alone.
* `JCF_g` — the analysis with **only muscle group g** switched on.

So the contribution of group *g* is one extra JointReaction run. The cost is
`n_groups + 2` runs per trial per force set (baseline + total + one per group).
Nothing is re-optimised: the muscle forces stay exactly the ones SO or CEINMS
produced, only the JointReaction bookkeeping is repeated.

## What is reported

Per joint, per source, per frame:

| column | meaning |
|---|---|
| `fx, fy, fz` | the contribution **vector** in the JRA frame — additive by construction |
| `along_total` | its projection on the unit vector of the total JCF: the scalar contribution to the **resultant**, additive, sums to `\|JCF_total\|` |
| `total_mag` | `\|JCF_total\|`, for reference |

Magnitudes are **not** additive (`Σ|v_g| ≠ |Σ v_g|`) — quote `along_total`.

## Use

```python
trial.run_jra_contributions(forces_type="both")     # 'so' | 'ceinms' | 'both'
trial.run_jra_contributions(forces_type="ceinms", per_muscle=True, replace=True)
```

Writes, next to the JRA:

```
joint_contact_forces/contributions_{so,ceinms}/
    contributions.csv    time, joint, source, fx, fy, fz, along_total, total_mag  [N]
    summary.csv          per joint x source at the peak-JCF frame + peak + impulse
    closure.txt          THE CHECK — see below
    contributions.png          bars: each source at the peak-JCF frame
    contributions_curves.png   curves: each source over TIME (sums to |JCF|)
```

`contributions_curves.png` also overlays the **in-vivo** JCF as a dashed purple
line when the trial has one: `run_jra_contributions` picks up
`<experimental>/invivo_jcf.mot` automatically and takes the instrumented side
from `self.invivo_side`, else a sibling `.akf` id (`h9l_...` = left), else
`self.side`. Load it by hand with
`jcf_contributions.load_measured_jcf(path, side)` and pass it as
`plot_contribution_curves(measured=...)`. It is a MEASUREMENT of the joint, not
a source — it is not part of the sum.

Both figures are laid out **joint rows x side columns** (hip/knee/ankle down,
right/left across); `run_jra_contributions` always computes BOTH sides, which
costs no extra runs because one JRA output carries every joint.

Path-level API (no Analyse object needed):

```python
from bioscout.utils.jcf_contributions import decompose, summarise, plot_contributions
df = decompose(model_path, ik_file, grf_xml, forces_file, out_dir,
               jra_columns=BatchSettings.JRA_COLUMNS(model, "r"))
```

## Groups

`settings.BatchSettings.MUSCLE_GROUPS` first, then `EXTRA_GROUPS` in the module
(iliopsoas, tibialis posterior, peroneals, …) for what it does not cover, then
one source per leftover muscle. **Every muscle is named** — nothing is lumped,
which is what makes the decomposition close. Rajagopal-family models give
36 groups (both legs) → 38 JRA runs. `per_muscle=True` gives 80 → 82 runs.

## Read `closure.txt` before quoting anything

It reports `max |Σ sources − total|` per joint. Linearity says it should be
~0 (numerical noise). If it is not, the decomposition is not valid for that
trial and the numbers are not usable.

## Traps

* **The residual / reserve / GRF columns stay in every run.** Only muscle
  columns are zeroed. Strip the rest and the JointReaction cannot balance: the
  force blows up ~100x *and stops depending on the muscle forces at all*, so
  every group returns the same wrong answer. `run_jra_contributions` refuses to
  run the CEINMS decomposition if `add_so_columns_to_ceinms_results()` fails,
  for exactly that reason.
* **Never hand-roll an `AnalyzeTool`** — this module goes through
  `openSim.run_jra`, which is the only supported path.
* **Contralateral muscles are not zero.** The reaction is realised through
  forward dynamics, so a left-leg muscle does move the right-leg accelerations.
  Every muscle is included; do not "optimise" by dropping the other side.
* This is **not** CEINMS's `MusclesContribution.sto`, which is the contribution
  of each muscle to the joint **moment**, not to the contact force.
