# `bioscout.simulate.iaa_files`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py)

Induced acceleration analysis (IAA) files -- one layout for both engines.

<trial>/induced_accelerations/<engine>/      (engine = opensim | pyosim)  
    IAA_<coordinate>.sto              rad/s^2 (m/s^2 for translations)  
    IAA_center_of_mass_{X,Y,Z}.sto    m/s^2  
    IAA_grf_<foot body>_{X,Y,Z}.sto   N, the force the ground puts on the foot  
    iaa_info.json                     engine, contact model, muscle / actuator names  
    iaa_summary.png                   muscle groups vs total vs measured  
    raw/                              (opensim) OpenSim's own InducedAccelerations output

Every .sto has one column per contributor -- each muscle, each SO actuator  
(reserves / residuals), ``gravity``, ``velocity`` -- plus ``total`` (their  
sum) and ``measured`` (from the IK / GRF: the check that the decomposition  
adds up). No OpenSim import here.

## Contents

- [`write`](#write) — res: dict(t, labels, coords, qdd (n,nq,nc), com (n,3,nc), reactions {body: (n,3,nc)}, measured {qdd (n,nq), com (n,3), grf {body: (n,3)}}, muscles, engine, constraint).
- [`from_opensim`](#from_opensim) — OpenSim's InducedAccelerations output in POTENTIALS mode (acceleration per 1 N / 1 N*m) x the SO force of each actuator -> the common layout. gravity / velocity are kept as they are. constraints: {constraint name: foot body}. The reactions OpenSim reports on the foot body are the foot's pull on the constraint; they are negated here to the force the ground puts on the foot.
- [`group_of`](#group_of) — 'Vasti R', 'gravity', 'velocity', 'Reserves/residuals', 'Other muscles L' ...
- [`read`](#read) — One IAA target ('knee_angle_r', 'center_of_mass_Y', 'grf_calcn_r_Y') -> pandas DataFrame; grouped=True sums the muscles into groups (time, groups..., total, measured).
- [`check_line`](#check_line) — How well total matches measured: RMS error / RMS measured, for COM Y and the feet's Y.
- [`plot`](#plot) — iaa_summary.png: the stacked contributions (see stack()).
- [`plot_lines`](#plot_lines) — 
- [`compare`](#compare) — Two engines side by side: same groups, solid = a, dashed = b.
- [`stack`](#stack) — Stacked contributions of each muscle group (grouped=True) or muscle (False), plus gravity, velocity and reserves/residuals, to each target: the COM acceleration, the foot GRF and the joint accelerations. Positive contributions stack above zero, negative below; the black line is their sum, the dashed one the measured value. bw: body weight in N -> GRF panels in BW.

### `write`

```python
write(out_dir, res, log=print)
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |
| `res` | – | required |
| `log` | – | `print` |

res: dict(t, labels, coords, qdd (n,nq,nc), com (n,3,nc), reactions {body: (n,3,nc)},  
measured {qdd (n,nq), com (n,3), grf {body: (n,3)}}, muscles, engine, constraint).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L35)</sub>

### `from_opensim`

```python
from_opensim(
    raw_dir,
    prefix,
    forces_sto,
    out_dir,
    measured=None,
    muscles=(),
    constraints=None,
    constraint='rolling',
    force_threshold=None,
    actuator_fill=None,
    log=print
)
```

| input | type | default |
|---|---|---|
| `raw_dir` | – | required |
| `prefix` | – | required |
| `forces_sto` | – | required |
| `out_dir` | – | required |
| `measured` | – | `None` |
| `muscles` | – | `()` |
| `constraints` | – | `None` |
| `constraint` | – | `'rolling'` |
| `force_threshold` | – | `None` |
| `actuator_fill` | – | `None` |
| `log` | – | `print` |

OpenSim's InducedAccelerations output in POTENTIALS mode (acceleration per 1 N / 1 N*m)  
x the SO force of each actuator -> the common layout. gravity / velocity are kept as they are.  
constraints: {constraint name: foot body}. The reactions OpenSim reports on the foot body are  
the foot's pull on the constraint; they are negated here to the force the ground puts on the foot.

actuator_fill: a pyosim IAA result (bioscout.pyosim.iaa.run(write=False)). OpenSim 4.5's  
InducedAccelerations reports ZERO for every non-muscle actuator (CoordinateActuator reserves,  
Point/Torque residuals) in either mode -- tested on 4.5.2 -- so those columns are taken from  
the pyosim solve of the same constrained equations, and iaa_info.json says so.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L75)</sub>

### `group_of`

```python
group_of(label, muscles)
```

| input | type | default |
|---|---|---|
| `label` | – | required |
| `muscles` | – | required |

'Vasti R', 'gravity', 'velocity', 'Reserves/residuals', 'Other muscles L' ...

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L182)</sub>

### `read`

```python
read(out_dir, target, grouped=True)
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |
| `target` | – | required |
| `grouped` | – | `True` |

One IAA target ('knee_angle_r', 'center_of_mass_Y', 'grf_calcn_r_Y') -> pandas DataFrame;  
grouped=True sums the muscles into groups (time, groups..., total, measured).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L196)</sub>

### `check_line`

```python
check_line(out_dir)
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |

How well total matches measured: RMS error / RMS measured, for COM Y and the feet's Y.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L213)</sub>

### `plot`

```python
plot(out_dir, save=None, top=8)
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |
| `save` | – | `None` |
| `top` | – | `8` |

iaa_summary.png: the stacked contributions (see stack()).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L244)</sub>

### `plot_lines`

```python
plot_lines(out_dir, save=None, top=8)
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |
| `save` | – | `None` |
| `top` | – | `8` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L253)</sub>

### `compare`

```python
compare(
    dir_a,
    dir_b,
    save,
    targets=('center_of_mass_Y', 'grf_calcn_r_Y', 'knee_angle_r', 'hip_flexion_r'),
    top=6
)
```

| input | type | default |
|---|---|---|
| `dir_a` | – | required |
| `dir_b` | – | required |
| `save` | – | required |
| `targets` | – | `('center_of_mass_Y', 'grf_calcn_r_Y', 'knee_angle_r', 'hip_flexion_r')` |
| `top` | – | `6` |

Two engines side by side: same groups, solid = a, dashed = b.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L282)</sub>

### `stack`

```python
stack(
    out_dir,
    targets=DEFAULT_STACK,
    grouped=True,
    top=8,
    ncols=3,
    save=None,
    title=None,
    bw=None
)
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |
| `targets` | – | `DEFAULT_STACK` |
| `grouped` | – | `True` |
| `top` | – | `8` |
| `ncols` | – | `3` |
| `save` | – | `None` |
| `title` | – | `None` |
| `bw` | – | `None` |

Stacked contributions of each muscle group (grouped=True) or muscle (False), plus  
gravity, velocity and reserves/residuals, to each target: the COM acceleration, the  
foot GRF and the joint accelerations. Positive contributions stack above zero,  
negative below; the black line is their sum, the dashed one the measured value.  
bw: body weight in N -> GRF panels in BW.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/iaa_files.py#L356)</sub>
