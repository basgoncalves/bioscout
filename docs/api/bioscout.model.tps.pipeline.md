# `bioscout.model.tps.pipeline`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py)

High-level personalisation orchestrator.

This replaces the notebook-driven workflow (notebooks ``2.0`` -> ``4``). The  
nine-notebook, run-cells-in-order process becomes a single callable object with  
clear, individually-testable stages and structured logging.

The orchestration is deliberately split into small methods so a host  
application (BioScout GUI/CLI) can run, monitor, or override any stage.

  
**Stages**

1. ``load_inputs``      — parse OSIM markers, MRI landmarks, muscles, wraps.  
2. ``match_landmarks``  — match MRI<->OSIM bone markers, group by body.  
3. ``fit_transforms``   — per body, fit a :class:`OneBodyTPS`.  
4. ``apply_transforms`` — warp muscle paths / skin / wraps / surfaces.  
5. ``write_outputs``    — CSVs + transformed surfaces (+ model update hook).

Heavy steps that require ``opensim``/``pyvista`` degrade gracefully: if those  
libraries are absent the geometry is still computed and written as CSV, and the  
final ``.osim`` write is reported as skipped.

## Contents

- class [`PersonalisationResult`](#personalisationresult) — 
- class [`Personaliser`](#personaliser) — Run the TPS personalisation described by a :class:`PersonalisationConfig`.
  - [`Personaliser.run`](#personaliserrun) — 
  - [`Personaliser.check_model_frames`](#personalisercheck_model_frames) — Verify the bone-landmark template is valid for this generic model.
  - [`Personaliser.load_inputs`](#personaliserload_inputs) — 
  - [`Personaliser.match_landmarks`](#personalisermatch_landmarks) — 
  - [`Personaliser.fit_transforms`](#personaliserfit_transforms) — 
  - [`Personaliser.apply_and_write`](#personaliserapply_and_write) — Warp every geometry set and rotate it into each body's child frame.

<a id="personalisationresult"></a>

## class `PersonalisationResult`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L43)</sub>

<a id="personaliser"></a>

## class `Personaliser`

```python
Personaliser(config: PersonalisationConfig)
```

| input | type | default |
|---|---|---|
| `config` | PersonalisationConfig | required |

Run the TPS personalisation described by a :class:`PersonalisationConfig`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L55)</sub>

<a id="personaliserrun"></a>

### `Personaliser.run`

```python
Personaliser.run() -> PersonalisationResult
```

**returns** `PersonalisationResult`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L72)</sub>

<a id="personalisercheck_model_frames"></a>

### `Personaliser.check_model_frames`

```python
Personaliser.check_model_frames() -> None
```

**returns** `None`

Verify the bone-landmark template is valid for this generic model.

No-op unless ``template_source_model`` is configured. Skipping this and  
warping with a template built in another model's frames does not raise  
anywhere downstream — it just yields a wrong model — so the check runs  
before any expensive work.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L90)</sub>

<a id="personaliserload_inputs"></a>

### `Personaliser.load_inputs`

```python
Personaliser.load_inputs() -> None
```

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L108)</sub>

<a id="personalisermatch_landmarks"></a>

### `Personaliser.match_landmarks`

```python
Personaliser.match_landmarks() -> None
```

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L119)</sub>

<a id="personaliserfit_transforms"></a>

### `Personaliser.fit_transforms`

```python
Personaliser.fit_transforms() -> None
```

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L133)</sub>

<a id="personaliserapply_and_write"></a>

### `Personaliser.apply_and_write`

```python
Personaliser.apply_and_write() -> None
```

**returns** `None`

Warp every geometry set and rotate it into each body's child frame.

Two steps per body, matching the original notebook exactly:  
  1. apply the body's TPS (result is in the MRI/fit frame), then  
  2. rotate into the OpenSim body-local (child) frame via ``axes.py``.

Step 2 was missing in the first refactor, which left all geometry in  
the global MRI frame — the cause of the scattered/exploded model.  
Patella bodies are rotated with their femur's axes, so femurs are  
processed first.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/pipeline.py#L150)</sub>
