# `bioscout.simulate.mew.jcf`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/jcf.py)

Joint contact forces from bioscout.simulate.mew muscle forces.

JCF is not a second model -- it is OpenSim's JointReaction analysis driven by  
the muscle forces this package produced. So this module's job is to hand  
JointReaction a COMPLETE and BALANCED actuator set, and then call it.

  
**THE TRAP THIS MODULE EXISTS TO AVOID**

JointReaction's ``forces_file`` must contain EVERY actuator in the model, not  
just the muscles: the pelvis residuals (FX..MZ), the coordinate reserves, the  
lumbar actuators and the external GRF columns. Feed it muscle columns alone and  
the analysis cannot balance the dynamics -- it dumps the entire imbalance into  
the proximal joint, producing a hip contact force roughly 100x too large that is  
also IDENTICAL no matter what the muscle forces were. It looks like a result. It  
is not one. bioscout learned this on the CEINMS path (see  
``Analyse.add_so_columns_to_ceinms_results``); the same rule applies here.

So :func:`build_forces_file` merges the non-muscle columns from the trial's  
Static Optimisation force file into our muscle forces, and REFUSES to write an  
unbalanced file unless explicitly told to.

One improvement on the CEINMS path: where a ``<dof>_reserve`` column  
corresponds to a DOF this solver actually tracked, we substitute OUR OWN  
residual moment rather than SO's. The reserve then means what it says -- the  
moment THIS solution could not produce -- instead of silently importing a  
different model's leftovers.

## Contents

- [`build_forces_file`](#build_forces_file) — Write a JointReaction-ready forces file. Returns ``(path, report)``.
- [`run_joint_reaction`](#run_joint_reaction) — Call OpenSim's JointReaction through bioscout, writing into ``out_dir``.
- [`contact_force_magnitude`](#contact_force_magnitude) — ``(times, |F|)`` for one joint, in N -- or in body weights if mass is given.
- [`sanity_check`](#sanity_check) — Is this JCF physiologically possible, or is it the unbalanced-JRA artefact?

### `build_forces_file`

```python
build_forces_file(
    result: MuscleForceResult,
    so_forces_path,
    out_path,
    use_own_reserves=True,
    allow_unbalanced=False
) -> Tuple[str, Dict[str, object]]
```

| input | type | default |
|---|---|---|
| `result` | MuscleForceResult | required |
| `so_forces_path` | – | required |
| `out_path` | – | required |
| `use_own_reserves` | – | `True` |
| `allow_unbalanced` | – | `False` |

**returns** `Tuple[str, Dict[str, object]]`

Write a JointReaction-ready forces file. Returns ``(path, report)``.

  
**Parameters**

result            what :meth:`Mew.run` returned  
so_forces_path    ``static_optimisation/StaticOptimization_force.sto`` --  
                  the source of the residual / reserve / GRF columns  
use_own_reserves  replace ``<dof>_reserve`` with this solve's own moment  
                  residual for every DOF we tracked (recommended)  
allow_unbalanced  write muscle columns only. The resulting JCF will be  
                  wrong, usually by ~100x at the proximal joint. Only for  
                  deliberately inspecting that failure.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/jcf.py#L49)</sub>

### `run_joint_reaction`

```python
run_joint_reaction(
    model,
    kinematics,
    grf_xml,
    forces_file,
    out_dir,
    setup_xml=None,
    save_name='JRA_ReactionLoads.sto',
    verbose=True
) -> str
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `kinematics` | – | required |
| `grf_xml` | – | required |
| `forces_file` | – | required |
| `out_dir` | – | required |
| `setup_xml` | – | `None` |
| `save_name` | – | `'JRA_ReactionLoads.sto'` |
| `verbose` | – | `True` |

**returns** `str`

Call OpenSim's JointReaction through bioscout, writing into ``out_dir``.

Delegates to ``bioscout.simulate.opensim.run_jra`` rather than reimplementing  
it: that function already handles the setup XML, relative-path rewriting and  
the assembly-accuracy workaround for the coupled knee. Needs opensim and  
bioscout importable -- this is the one part of the pipeline that cannot run  
in pure Python.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/jcf.py#L122)</sub>

### `contact_force_magnitude`

```python
contact_force_magnitude(
    jra_path,
    joint='hip_r',
    body_mass=None
) -> Tuple[np.ndarray, np.ndarray]
```

| input | type | default |
|---|---|---|
| `jra_path` | – | required |
| `joint` | – | `'hip_r'` |
| `body_mass` | – | `None` |

**returns** `Tuple[np.ndarray, np.ndarray]`

``(times, |F|)`` for one joint, in N -- or in body weights if mass is given.

JRA writes ``<joint>_on_<body>_in_<frame>_f{x,y,z}``; the joint name is  
matched loosely so ``hip_r`` finds ``hip_r_on_femur_r_in_femur_r_fx``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/jcf.py#L174)</sub>

### `sanity_check`

```python
sanity_check(jra_path, body_mass, joint='hip_r', max_bw=12.0) -> Dict[str, object]
```

| input | type | default |
|---|---|---|
| `jra_path` | – | required |
| `body_mass` | – | required |
| `joint` | – | `'hip_r'` |
| `max_bw` | – | `12.0` |

**returns** `Dict[str, object]`

Is this JCF physiologically possible, or is it the unbalanced-JRA artefact?

Peak hip contact force in running is ~5-8 body weights. Anything above  
``max_bw`` is almost certainly a forces file that was missing its residual  
and reserve columns -- the ~100x failure this module is built to prevent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/jcf.py#L197)</sub>
