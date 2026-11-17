# `bioscout.core.jcf_contributions`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py)

Muscle contributions to the joint contact force (JCF), by force superposition.

WHY IT WORKS  
    At fixed kinematics the JointReaction analysis is LINEAR in the applied  
    actuator forces, so the contact force of a joint decomposes EXACTLY:

        JCF_total(t) = JCF_base(t) + sum_g [ JCF_g(t) - JCF_base(t) ]

    JCF_base   = the analysis with every MUSCLE force zeroed, i.e. what gravity,  
                 segment inertia, the GRF, the residuals and the reserves alone  
                 push through the joint.  
    JCF_g      = the analysis with ONLY muscle group g switched on.

    Cost: one JRA run per group + a baseline + a total (the total is re-run  
    rather than read off disk so the closure check compares like with like).  
    The check is written to the .sto header (closure=...) -- if it is not ~0 the decomposition  
    is not trustworthy, so read it before quoting anything.

WHAT IS REPORTED  (per joint, per source, per frame)  
    fx, fy, fz    the contribution VECTOR in the JRA frame (additive by  
                  construction)  
    along_total   its projection on the unit vector of the total JCF -- the  
                  scalar contribution to the RESULTANT. Magnitudes are not  
                  additive; this projection is, and it sums to |JCF_total|.

TRAPS  
    * The residual / reserve / GRF columns stay in EVERY run. Strip them and the  
      analysis cannot balance, the force blows up ~100x and stops depending on  
      the muscle forces at all (see docs/JCF_CONTRIBUTIONS.md).  
    * Always go through ``openSim.run_jra`` -- never hand-roll an AnalyzeTool.

## Contents

- [`read_sto`](#read_sto) — (header lines, DataFrame). The header is kept verbatim so a rewritten forces file stays byte-compatible with what OpenSim already accepted.
- [`write_sto`](#write_sto) — 
- [`model_muscles`](#model_muscles) — Muscle names in the .osim (the ONLY columns that may be zeroed).
- [`build_groups`](#build_groups) — name -> [columns]. settings.BatchSettings.MUSCLE_GROUPS, then EXTRA_GROUPS for what it does not cover, then one source per leftover muscle -- so every muscle is named and the decomposition closes.
- [`decompose`](#decompose) — Run the superposition and write `contributions.csv` + `closure.txt`.
- [`split_reserves`](#split_reserves) — Split the reserves out of the non-muscle baseline of an existing `contributions.csv` (2026-10-12).
- [`summarise`](#summarise) — One row per joint x source: the contribution at the frame of PEAK total JCF, its own peak, and its impulse. In BW when body_weight (N) is given.
- [`load_measured_jcf`](#load_measured_jcf) — In-vivo JCF from an instrumented implant (OrthoLoad) as {"<joint>_<side>": (time, |F| in N)} -- ready to hand to ``plot_contribution_curves(measured=...)``.
- [`source_color`](#source_color) — Stable colour for one contribution source. Side-independent ("R Vasti" and "L Vasti" match), fixed across figures, grey for the pooled remainder and dark grey for the non-muscle baseline.
- [`plot_contributions`](#plot_contributions) — Per joint, each source's contribution at the frame of peak JCF. Joint rows x side columns when the joints are keyed "<joint>_<side>".
- [`plot_contribution_curves`](#plot_contribution_curves) — Each source's contribution to the total JCF OVER TIME, one panel per joint (joint rows x side columns).
- [`write_contributions_sto`](#write_contributions_sto) — 
- [`read_contributions`](#read_contributions) — contributions_<t>.sto -> (long DataFrame as decompose() returns, body weight in N or None). Also accepts a legacy contributions.csv.
- [`stack_group`](#stack_group) — Contribution source -> one of STACK_ORDER.
- [`plot_contribution_stack`](#plot_contribution_stack) — Stacked contributions to |JCF| for ONE trial: rows = hip / knee / ankle, columns = left | right (left on the left); x = % trial, y = BW (N without body_weight). Uses the along-|JCF| projection, which is additive, so the stack tops out at |JCF| (black line); parts pulling against the resultant go below 0. ``measured`` = {"<joint>_<side>": (time, |F| N)} (load_measured_jcf): the in-vivo JCF, drawn red dashed on its panel over the same time window (2026-10-15).
- [`plot_contribution_stacks`](#plot_contribution_stacks) — Draw plot_contribution_stack for every contributions_<t>.sto under `root` (one .sto, a trial folder or a whole session); each figure is saved as the .sto's stem + .png next to it. Returns the list of figures written.

### `read_sto`

```python
read_sto(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

(header lines, DataFrame). The header is kept verbatim so a rewritten  
forces file stays byte-compatible with what OpenSim already accepted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L54)</sub>

### `write_sto`

```python
write_sto(path, header, df)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `header` | – | required |
| `df` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L67)</sub>

### `model_muscles`

```python
model_muscles(model_path)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |

Muscle names in the .osim (the ONLY columns that may be zeroed).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L82)</sub>

### `build_groups`

```python
build_groups(muscle_cols, groups=None, per_muscle=False)
```

| input | type | default |
|---|---|---|
| `muscle_cols` | – | required |
| `groups` | – | `None` |
| `per_muscle` | – | `False` |

name -> [columns]. settings.BatchSettings.MUSCLE_GROUPS, then EXTRA_GROUPS  
for what it does not cover, then one source per leftover muscle -- so every  
muscle is named and the decomposition closes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L118)</sub>

### `decompose`

```python
decompose(
    model_path,
    ik_file,
    grf_xml,
    forces_file,
    out_dir,
    jra_columns,
    groups=None,
    per_muscle=False,
    keep_sto=False,
    replace=False,
    setup_template=None,
    log=print,
    n_jobs=None,
    force_set='auto'
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `ik_file` | – | required |
| `grf_xml` | – | required |
| `forces_file` | – | required |
| `out_dir` | – | required |
| `jra_columns` | – | required |
| `groups` | – | `None` |
| `per_muscle` | – | `False` |
| `keep_sto` | – | `False` |
| `replace` | – | `False` |
| `setup_template` | – | `None` |
| `log` | – | `print` |
| `n_jobs` | – | `None` |
| `force_set` | – | `'auto'` |

Run the superposition and write `contributions.csv` + `closure.txt`.

jra_columns: {"hip": [fx, fy, fz], "knee": [...], "ankle": [...]}  
             (settings.BatchSettings.JRA_COLUMNS(model, side))  
Returns the long DataFrame: time, joint, source, fx, fy, fz, along_total,  
total_mag.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L211)</sub>

### `split_reserves`

```python
split_reserves(
    model_path,
    ik_file,
    grf_xml,
    forces_file,
    out_dir,
    jra_columns,
    setup_template=None,
    replace=False,
    log=print,
    reserve_pattern='_reserve$'
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `ik_file` | – | required |
| `grf_xml` | – | required |
| `forces_file` | – | required |
| `out_dir` | – | required |
| `jra_columns` | – | required |
| `setup_template` | – | `None` |
| `replace` | – | `False` |
| `log` | – | `print` |
| `reserve_pattern` | – | `'_reserve$'` |

Split the reserves out of the non-muscle baseline of an existing  
`contributions.csv` (2026-10-12).

decompose() leaves every non-muscle column in every run, so its baseline row  
is gravity + GRF + residuals + RESERVES. One more JointReaction with the  
muscles AND the reserve columns zeroed gives B0, then  
    Reserve actuators = B - B0          Non-muscle = B0  
The sum over sources is unchanged, so the closure stays exact. Residuals  
(FX..MZ) and GRF stay in -- zeroing those unbalances the analysis.

jra_columns: {"hip_l": [fx, fy, fz], ...} as passed to decompose().  
Idempotent: skipped when the csv already has a reserve row (unless replace).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L388)</sub>

### `summarise`

```python
summarise(df, body_weight=None)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `body_weight` | – | `None` |

One row per joint x source: the contribution at the frame of PEAK total  
JCF, its own peak, and its impulse. In BW when body_weight (N) is given.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L476)</sub>

### `load_measured_jcf`

```python
load_measured_jcf(path, side='r')
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `side` | – | `'r'` |

In-vivo JCF from an instrumented implant (OrthoLoad) as  
{"<joint>_<side>": (time, |F| in N)} -- ready to hand to  
``plot_contribution_curves(measured=...)``.

Uses the ``<joint>_measured_f`` magnitude column written by  
orthoload_to_bioscout, else builds the magnitude from  
``<joint>_measured_f{x,y,z}``. The instrumented side is NOT in the file --  
pass it (OrthoLoad trial ids carry it: `h9l_...` = left).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L494)</sub>

### `source_color`

```python
source_color(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

Stable colour for one contribution source. Side-independent ("R Vasti"  
and "L Vasti" match), fixed across figures, grey for the pooled remainder  
and dark grey for the non-muscle baseline.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L548)</sub>

### `plot_contributions`

```python
plot_contributions(df, save=None, body_weight=None, title=None, top=12, ncols=3)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `save` | – | `None` |
| `body_weight` | – | `None` |
| `title` | – | `None` |
| `top` | – | `12` |
| `ncols` | – | `3` |

Per joint, each source's contribution at the frame of peak JCF.  
Joint rows x side columns when the joints are keyed "<joint>_<side>".

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L590)</sub>

### `plot_contribution_curves`

```python
plot_contribution_curves(
    df,
    save=None,
    body_weight=None,
    title=None,
    top=6,
    ncols=3,
    stacked=False,
    xnorm=False,
    measured=None
)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `save` | – | `None` |
| `body_weight` | – | `None` |
| `title` | – | `None` |
| `top` | – | `6` |
| `ncols` | – | `3` |
| `stacked` | – | `False` |
| `xnorm` | – | `False` |
| `measured` | – | `None` |

Each source's contribution to the total JCF OVER TIME, one panel per  
joint (joint rows x side columns).

Curves are `along_total` — the projection on the total-JCF direction — so  
they add up to the black |JCF| line at every instant. `top` sources per  
panel are named (ranked by peak contribution); the rest are pooled into a  
thin grey "other" line so the panel still sums to the total.  
stacked=True draws them as a filled stack instead of lines (negative  
contributions then sit below zero and the stack top no longer meets the  
total line — read the lines when that matters).  
xnorm=True puts the x axis in % of the trial instead of seconds.  
measured: {joint_key: (time, |F| in N)} -- e.g. an instrumented implant's  
in-vivo JCF from :func:`load_measured_jcf` -- drawn as a dashed reference.  
It is a MEASUREMENT of the same joint, not one of the sources, so it is  
deliberately NOT part of the sum.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L633)</sub>

### `write_contributions_sto`

```python
write_contributions_sto(df, path, body_weight=None, closure=None)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `path` | – | required |
| `body_weight` | – | `None` |
| `closure` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L722)</sub>

### `read_contributions`

```python
read_contributions(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

contributions_<t>.sto -> (long DataFrame as decompose() returns, body  
weight in N or None). Also accepts a legacy contributions.csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L750)</sub>

### `stack_group`

```python
stack_group(source)
```

| input | type | default |
|---|---|---|
| `source` | – | required |

Contribution source -> one of STACK_ORDER.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L800)</sub>

### `plot_contribution_stack`

```python
plot_contribution_stack(
    df,
    save=None,
    body_weight=None,
    title=None,
    n_points=101,
    measured=None
)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `save` | – | `None` |
| `body_weight` | – | `None` |
| `title` | – | `None` |
| `n_points` | – | `101` |
| `measured` | – | `None` |

Stacked contributions to |JCF| for ONE trial: rows = hip / knee / ankle,  
columns = left | right (left on the left); x = % trial, y = BW (N without body_weight).  
Uses the along-|JCF| projection, which is additive, so the stack tops out  
at |JCF| (black line); parts pulling against the resultant go below 0.  
``measured`` = {"<joint>_<side>": (time, |F| N)} (load_measured_jcf): the in-vivo  
JCF, drawn red dashed on its panel over the same time window (2026-10-15).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L828)</sub>

### `plot_contribution_stacks`

```python
plot_contribution_stacks(root, body_weight=None, replace=True, log=print)
```

| input | type | default |
|---|---|---|
| `root` | – | required |
| `body_weight` | – | `None` |
| `replace` | – | `True` |
| `log` | – | `print` |

Draw plot_contribution_stack for every contributions_<t>.sto under `root`  
(one .sto, a trial folder or a whole session); each figure is saved as the  
.sto's stem + .png next to it. Returns the list of figures written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/jcf_contributions.py#L960)</sub>
