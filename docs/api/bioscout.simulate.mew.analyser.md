# `bioscout.simulate.mew.analyser`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py)

Mew -- the public facade.

    ma = Mew(model="Rajagopal2015.osim", height=1.81, mass=78,  
             kinematics="joint_angles.mot")  
    res = ma.run()  
    print(res.summary())

Everything optional is optional. The class figures out which tier the inputs  
support, runs it, and hands back a result that says what it did.

## Contents

- class [`Mew`](#mew) — Muscle forces from whatever inputs exist, with a tier and a confidence.
  - [`Mew.from_bioscout`](#mewfrom_bioscout) — Build from a bioscout ``Iteration`` and trial name. See bioscout_adapter.
  - [`Mew.from_trial_dir`](#mewfrom_trial_dir) — Build from a bioscout-layout trial folder, without importing bioscout.
  - [`Mew.parameters`](#mewparameters) — Calibrated theta if available, else generic scaled by height/mass.
  - [`Mew.geometry`](#mewgeometry) — 
  - [`Mew.run`](#mewrun) — Solve the trial at the highest supported tier (or a pinned one).
  - [`Mew.run_all_tiers`](#mewrun_all_tiers) — Solve at every tier the inputs support -- the degradation-curve figure.

<a id="mew"></a>

## class `Mew`

```python
Mew(
    model=None,
    height=None,
    mass=None,
    name='subject',
    kinematics=None,
    moments=None,
    grf=None,
    emg=None,
    moment_arms=None,
    emg_map=None,
    time_range=None,
    side='both',
    trial_type=None,
    trial_name='trial',
    theta_file=None,
    subject: Optional[SubjectSpec] = None,
    inputs: Optional[TrialInputs] = None,
    muscles: Optional[Sequence[str]] = None,
    dofs: Optional[Sequence[str]] = None,
    tendon='auto',
    geometry=None
)
```

| input | type | default |
|---|---|---|
| `model` | – | `None` |
| `height` | – | `None` |
| `mass` | – | `None` |
| `name` | – | `'subject'` |
| `kinematics` | – | `None` |
| `moments` | – | `None` |
| `grf` | – | `None` |
| `emg` | – | `None` |
| `moment_arms` | – | `None` |
| `emg_map` | – | `None` |
| `time_range` | – | `None` |
| `side` | – | `'both'` |
| `trial_type` | – | `None` |
| `trial_name` | – | `'trial'` |
| `theta_file` | – | `None` |
| `subject` | Optional[SubjectSpec] | `None` |
| `inputs` | Optional[TrialInputs] | `None` |
| `muscles` | Optional[Sequence[str]] | `None` |
| `dofs` | Optional[Sequence[str]] | `None` |
| `tendon` | – | `'auto'` |
| `geometry` | – | `None` |

Muscle forces from whatever inputs exist, with a tier and a confidence.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L29)</sub>

<a id="mewfrom_bioscout"></a>

### `Mew.from_bioscout`

```python
Mew.from_bioscout(iteration, trial, **kw) -> 'Mew'
```

| input | type | default |
|---|---|---|
| `iteration` | – | required |
| `trial` | – | required |
| `**kw` | – | – |

**returns** `'Mew'`

Build from a bioscout ``Iteration`` and trial name. See bioscout_adapter.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L58)</sub>

<a id="mewfrom_trial_dir"></a>

### `Mew.from_trial_dir`

```python
Mew.from_trial_dir(trial_dir, model, **kw) -> 'Mew'
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |
| `model` | – | required |
| `**kw` | – | – |

**returns** `'Mew'`

Build from a bioscout-layout trial folder, without importing bioscout.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L64)</sub>

<a id="mewparameters"></a>

### `Mew.parameters`

```python
Mew.parameters() -> MuscleParameters
```

**returns** `MuscleParameters`

Calibrated theta if available, else generic scaled by height/mass.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L72)</sub>

<a id="mewgeometry"></a>

### `Mew.geometry`

```python
Mew.geometry() -> geo.GeometryProvider
```

**returns** `geo.GeometryProvider`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L92)</sub>

<a id="mewrun"></a>

### `Mew.run`

```python
Mew.run(
    tier: Optional[Tier] = None,
    weights: Optional[SolverWeights] = None,
    smoothing: Optional[float] = None,
    filter_hz: Optional[float] = None,
    emg_delay=0.045,
    emg_gains=None
) -> MuscleForceResult
```

| input | type | default |
|---|---|---|
| `tier` | Optional[Tier] | `None` |
| `weights` | Optional[SolverWeights] | `None` |
| `smoothing` | Optional[float] | `None` |
| `filter_hz` | Optional[float] | `None` |
| `emg_delay` | – | `0.045` |
| `emg_gains` | – | `None` |

**returns** `MuscleForceResult`

Solve the trial at the highest supported tier (or a pinned one).

Two independent smoothing controls, because they are genuinely different  
things and conflating them would hide which one produced a result:

``smoothing``  
    The solver's temporal-coupling weight (``SolverWeights.delta``).  
    This is smoothing done DURING the solve: each frame is penalised for  
    departing from the previous frame's activations, so the solution  
    picked is a smooth one that still satisfies the moment constraint.  
    ``0`` turns it off and gives frame-independent solving -- the same  
    regime OpenSim SO runs in, chatter included. Physiologically it is  
    the defensible kind: activation cannot jump discontinuously.

``filter_hz``  
    A zero-lag low-pass applied to the OUTPUTS after solving. Cosmetic  
    by comparison: it makes the traces look smooth but the filtered  
    forces no longer exactly reproduce the tracked moments. Off by  
    default. Use it for figures, not for anything you then integrate,  
    differentiate, or feed to JointReaction.

Prefer ``smoothing``; reach for ``filter_hz`` only when you know why.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L102)</sub>

<a id="mewrun_all_tiers"></a>

### `Mew.run_all_tiers`

```python
Mew.run_all_tiers() -> Dict[str, MuscleForceResult]
```

**returns** `Dict[str, MuscleForceResult]`

Solve at every tier the inputs support -- the degradation-curve figure.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/analyser.py#L261)</sub>
