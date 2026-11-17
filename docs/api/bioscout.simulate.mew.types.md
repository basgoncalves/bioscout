# `bioscout.simulate.mew.types`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py)

Data contracts for :mod:`mew`.

Everything that crosses a module boundary is one of these. They are plain  
dataclasses with no dependency beyond numpy, so the contract can be read and  
tested without OpenSim, torch or bioscout installed.

## Contents

- class [`Tier`](#tier) — How much information the solve actually had.
  - [`Tier.label`](#tierlabel) — 
  - [`Tier.nominal_confidence`](#tiernominal_confidence) — Prior confidence for the tier, before residual-based adjustment.
- class [`SubjectSpec`](#subjectspec) — The minimum viable description of a participant.
  - [`SubjectSpec.model_hash`](#subjectspecmodel_hash) — Short content hash of the .osim, recorded in provenance.
  - [`SubjectSpec.bmi`](#subjectspecbmi) — 
- class [`TrialInputs`](#trialinputs) — One trial's signals. Only ``kinematics`` is required.
  - [`TrialInputs.available`](#trialinputsavailable) — 
- class [`Provenance`](#provenance) — What every input actually was. This is what makes a result defensible.
  - [`Provenance.to_json`](#provenanceto_json) — 
- class [`MuscleForceResult`](#muscleforceresult) — Muscle forces plus everything needed to judge them.
  - [`MuscleForceResult.reserves`](#muscleforceresultreserves) — The reserve actuators: what the muscles could NOT produce, per DOF.
  - [`MuscleForceResult.reserve_names`](#muscleforceresultreserve_names) — 
  - [`MuscleForceResult.confidence`](#muscleforceresultconfidence) — 0-1. Tier prior, degraded by how much moment the muscles could not explain.
  - [`MuscleForceResult.confidence`](#muscleforceresultconfidence) — 
  - [`MuscleForceResult.to_dataframe`](#muscleforceresultto_dataframe) — 
  - [`MuscleForceResult.peak_forces`](#muscleforceresultpeak_forces) — 
  - [`MuscleForceResult.summary`](#muscleforceresultsummary) — 
  - [`MuscleForceResult.array`](#muscleforceresultarray) — One output array by name, whether it is a field or a series entry.
  - [`MuscleForceResult.write_outputs`](#muscleforceresultwrite_outputs) — Write every output as its own .sto in ``out_dir``. Returns the paths.
  - [`MuscleForceResult.write_sto`](#muscleforceresultwrite_sto) — Write forces in the CEINMS-compatible .sto that bioscout already reads.

<a id="tier"></a>

## class `Tier`(IntEnum)

How much information the solve actually had.

Higher is better. :class:`~mew.analyser.Mew` picks  
the highest tier the inputs support unless one is pinned.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L22)</sub>

<a id="tierlabel"></a>

### `Tier.label`

```python
Tier.label() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L34)</sub>

<a id="tiernominal_confidence"></a>

### `Tier.nominal_confidence`

```python
Tier.nominal_confidence() -> float
```

**returns** `float`

Prior confidence for the tier, before residual-based adjustment.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L43)</sub>

<a id="subjectspec"></a>

## class `SubjectSpec`

The minimum viable description of a participant.

``height`` (m) and ``mass`` (kg) plus ``model`` is the whole required input  
set for tier 0 — everything else refines it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L52)</sub>

<a id="subjectspecmodel_hash"></a>

### `SubjectSpec.model_hash`

```python
SubjectSpec.model_hash() -> str
```

**returns** `str`

Short content hash of the .osim, recorded in provenance.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L78)</sub>

<a id="subjectspecbmi"></a>

### `SubjectSpec.bmi`

```python
SubjectSpec.bmi() -> Optional[float]
```

**returns** `Optional[float]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L90)</sub>

<a id="trialinputs"></a>

## class `TrialInputs`

One trial's signals. Only ``kinematics`` is required.

Paths OR in-memory arrays are both accepted: the loader in  
:mod:`mew.io_ports` normalises either into ``(times, DataFrame)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L100)</sub>

<a id="trialinputsavailable"></a>

### `TrialInputs.available`

```python
TrialInputs.available() -> Dict[str, bool]
```

**returns** `Dict[str, bool]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L117)</sub>

<a id="provenance"></a>

## class `Provenance`

What every input actually was. This is what makes a result defensible.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L131)</sub>

<a id="provenanceto_json"></a>

### `Provenance.to_json`

```python
Provenance.to_json(indent=2) -> str
```

| input | type | default |
|---|---|---|
| `indent` | – | `2` |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L147)</sub>

<a id="muscleforceresult"></a>

## class `MuscleForceResult`

Muscle forces plus everything needed to judge them.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L155)</sub>

<a id="muscleforceresultreserves"></a>

### `MuscleForceResult.reserves`

```python
MuscleForceResult.reserves() -> Optional[np.ndarray]
```

**returns** `Optional[np.ndarray]`

The reserve actuators: what the muscles could NOT produce, per DOF.

Same array as ``moment_residual``, named for what it is downstream. A  
reserve is a GENERALISED force -- a moment (Nm) at a rotational  
coordinate, a force (N) at a translational one -- which is why the file  
it is written to mixes units, exactly as OpenSim's own force files do.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L174)</sub>

<a id="muscleforceresultreserve_names"></a>

### `MuscleForceResult.reserve_names`

```python
MuscleForceResult.reserve_names() -> List[str]
```

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L185)</sub>

<a id="muscleforceresultconfidence"></a>

### `MuscleForceResult.confidence`

```python
MuscleForceResult.confidence() -> float
```

**returns** `float`

0-1. Tier prior, degraded by how much moment the muscles could not explain.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L190)</sub>

<a id="muscleforceresultconfidence"></a>

### `MuscleForceResult.confidence`

```python
MuscleForceResult.confidence(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L203)</sub>

<a id="muscleforceresultto_dataframe"></a>

### `MuscleForceResult.to_dataframe`

```python
MuscleForceResult.to_dataframe(what='forces')
```

| input | type | default |
|---|---|---|
| `what` | – | `'forces'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L207)</sub>

<a id="muscleforceresultpeak_forces"></a>

### `MuscleForceResult.peak_forces`

```python
MuscleForceResult.peak_forces() -> Dict[str, float]
```

**returns** `Dict[str, float]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L214)</sub>

<a id="muscleforceresultsummary"></a>

### `MuscleForceResult.summary`

```python
MuscleForceResult.summary() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L217)</sub>

<a id="muscleforceresultarray"></a>

### `MuscleForceResult.array`

```python
MuscleForceResult.array(key) -> Optional[np.ndarray]
```

| input | type | default |
|---|---|---|
| `key` | – | required |

**returns** `Optional[np.ndarray]`

One output array by name, whether it is a field or a series entry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L241)</sub>

<a id="muscleforceresultwrite_outputs"></a>

### `MuscleForceResult.write_outputs`

```python
MuscleForceResult.write_outputs(out_dir, include=None, provenance=True) -> List[str]
```

| input | type | default |
|---|---|---|
| `out_dir` | – | required |
| `include` | – | `None` |
| `provenance` | – | `True` |

**returns** `List[str]`

Write every output as its own .sto in ``out_dir``. Returns the paths.

One quantity per file rather than one wide file: that is how CEINMS and  
OpenSim's MuscleAnalysis both do it, it keeps units consistent within a  
file, and it means a downstream reader never has to know which columns  
of a mixed file it wants.

Reserves get their own file too (``Reserves.sto``), because they are  
indexed by COORDINATE, not by muscle -- a different number of columns  
with different names, which is precisely why they cannot share a file  
with the muscle quantities.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L249)</sub>

<a id="muscleforceresultwrite_sto"></a>

### `MuscleForceResult.write_sto`

```python
MuscleForceResult.write_sto(path, extra=False)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `extra` | – | `False` |

Write forces in the CEINMS-compatible .sto that bioscout already reads.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/types.py#L293)</sub>
