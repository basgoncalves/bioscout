# `bioscout.session.movement_detector.mocap`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py)

mocap.py — trial-level movement classification from MOCAP data.

The rest of this package classifies FRAMES of 2-D pose landmarks from video  
(``detector.detect_segments``). This module answers a different question, for  
marker-based laboratory capture: **what task is this whole trial?** — from the  
exported ``marker_experimental.trc`` and ``grf.mot`` that BioScout already  
writes into ``<session>/2_experimental/<trial>/``.

  
**Why it exists**

Projects type their trials from the FILE NAME (``RunG3`` -> running,  
``SquatNorm1`` -> squat). That is a naming convention, not a measurement: it  
cannot catch a mislabelled capture, a trial where the participant did something  
else, or a squat where one foot missed the plate. This module derives the task  
from the signals so the two can be compared.

  
**Tasks**

emg_only            no 3-D point data at all (MVIC / strength captures)  
static              stationary, both feet loaded, no vertical excursion  
squat               bilateral, vertical pelvis cycling, no travel  
single_leg_squat    as squat but only ONE foot loaded  
jump                flight phase with low travel speed + high landing impulse  
running             high travel speed WITH a flight phase  
walking             moderate travel speed, no flight phase  
cut                 fast travel with a large lateral component  
unknown             nothing matched with enough confidence

The thresholds live in :class:`MocapConfig` and are expressed in SI units  
(m, s, body weights) so they transfer between labs, unlike the pixel/frame  
thresholds the video path uses.

## Contents

- class [`MocapConfig`](#mocapconfig) — Thresholds for :func:`classify_trial`, all in SI units.
  - [`MocapConfig.axes`](#mocapconfigaxes) — (vertical, anterior-posterior, lateral) column indices into a TRC.
  - [`MocapConfig.horizontal`](#mocapconfighorizontal) — The two non-vertical column indices, anterior-posterior first.
  - [`MocapConfig.from_settings`](#mocapconfigfrom_settings) — Build a config from a project's settings object.
- class [`TrialFeatures`](#trialfeatures) — Everything :func:`classify_trial` measured. Reported alongside the label so a disagreement can be read rather than guessed at.
  - [`TrialFeatures.as_dict`](#trialfeaturesas_dict) — 
- class [`TaskSegment`](#tasksegment) — One contiguous block of a trial holding a single task.
  - [`TaskSegment.duration`](#tasksegmentduration) — 
  - [`TaskSegment.as_dict`](#tasksegmentas_dict) — 
- [`read_trc`](#read_trc) — (time, {marker: (n,3) array in METRES}, rate) from an OpenSim .trc.
- [`read_grf`](#read_grf) — (time, {column: values}) from an OpenSim .mot.
- [`extract_trial_features`](#extract_trial_features) — Measure one trial's ``2_experimental/<trial>/`` folder.
- [`foot_events_from_markers`](#foot_events_from_markers) — Foot contacts and toe-offs per leg, from MARKER kinematics alone.
- [`contact_feet`](#contact_feet) — Ground contacts with the foot that made each one, from the DATA.
- [`jump_height`](#jump_height) — Jump height by three independent routes, all in metres.
- [`bar_centre`](#bar_centre) — Mean of the barbell markers, or None when the project has no bar.
- [`bar_metrics`](#bar_metrics) — Bar path measures over one lift, in SI units.
- [`segment_trial`](#segment_trial) — Split one trial into the tasks it actually contains.
- [`gait_cycles`](#gait_cycles) — One dict per gait cycle in a capture — the unit the pipeline runs on.
- [`detect_window`](#detect_window) — Suggest the analysis window from each modality independently.
- [`classify_features`](#classify_features) — (label, confidence 0-1, one-line reason) from measured features.
- [`classify_trial`](#classify_trial) — Classify one exported trial folder.
- [`plot_trial_tasks`](#plot_trial_tasks) — Vertical GRF + pelvis height for one trial, with the tasks shaded.

<a id="mocapconfig"></a>

## class `MocapConfig`

Thresholds for :func:`classify_trial`, all in SI units.

Defaults were set against FAIS running / squat / single-leg-squat / jump  
captures (200 Hz, 59 markers, 4 force plates) and are deliberately loose —  
the classifier is meant to catch gross mislabelling, not to adjudicate  
borderline technique.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L80)</sub>

<a id="mocapconfigaxes"></a>

### `MocapConfig.axes`

```python
MocapConfig.axes() -> Tuple[int, int, int]
```

**returns** `Tuple[int, int, int]`

(vertical, anterior-posterior, lateral) column indices into a TRC.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L329)</sub>

<a id="mocapconfighorizontal"></a>

### `MocapConfig.horizontal`

```python
MocapConfig.horizontal() -> List[int]
```

**returns** `List[int]`

The two non-vertical column indices, anterior-posterior first.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L336)</sub>

<a id="mocapconfigfrom_settings"></a>

### `MocapConfig.from_settings`

```python
MocapConfig.from_settings(settings=None, **overrides) -> 'MocapConfig'
```

| input | type | default |
|---|---|---|
| `settings` | – | `None` |
| `**overrides` | – | – |

**returns** `'MocapConfig'`

Build a config from a project's settings object.

Reads the names a bioscout project already declares — ``markerset``,  
``right_foot_markers``, ``trc_vertical_axis`` and friends — so the lab  
convention is stated once, in the project, instead of being re-guessed  
from marker names inside the detector. Anything absent keeps its  
default, so passing a partial settings object is fine and passing none  
gives exactly the old behaviour.

    from bioscout.session.movement_detector import MocapConfig  
    cfg = MocapConfig.from_settings(settings.BatchSettings)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L342)</sub>

<a id="trialfeatures"></a>

## class `TrialFeatures`

Everything :func:`classify_trial` measured. Reported alongside the label  
so a disagreement can be read rather than guessed at.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L449)</sub>

<a id="trialfeaturesas_dict"></a>

### `TrialFeatures.as_dict`

```python
TrialFeatures.as_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L481)</sub>

<a id="tasksegment"></a>

## class `TaskSegment`

One contiguous block of a trial holding a single task.

``phase`` names a sub-division of the parent task — "eccentric" / "hold" /  
"concentric" for a squat, "stride" / "stance" / "swing" for gait. Top-level  
task rows carry an empty ``phase``; their sub-phases are listed in  
``phases``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L863)</sub>

<a id="tasksegmentduration"></a>

### `TaskSegment.duration`

```python
TaskSegment.duration() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L911)</sub>

<a id="tasksegmentas_dict"></a>

### `TaskSegment.as_dict`

```python
TaskSegment.as_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L914)</sub>

### `read_trc`

```python
read_trc(path: str) -> Tuple[np.ndarray, Dict[str, np.ndarray], float]
```

| input | type | default |
|---|---|---|
| `path` | str | required |

**returns** `Tuple[np.ndarray, Dict[str, np.ndarray], float]`

(time, {marker: (n,3) array in METRES}, rate) from an OpenSim .trc.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L490)</sub>

### `read_grf`

```python
read_grf(path: str) -> Tuple[np.ndarray, Dict[str, np.ndarray]]
```

| input | type | default |
|---|---|---|
| `path` | str | required |

**returns** `Tuple[np.ndarray, Dict[str, np.ndarray]]`

(time, {column: values}) from an OpenSim .mot.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L556)</sub>

### `extract_trial_features`

```python
extract_trial_features(
    exp_dir: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None
) -> TrialFeatures
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |

**returns** `TrialFeatures`

Measure one trial's ``2_experimental/<trial>/`` folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L738)</sub>

### `foot_events_from_markers`

```python
foot_events_from_markers(
    exp_dir: str,
    cfg: Optional['MocapConfig'] = None,
    contacts: Optional[List[dict]] = None
) -> Dict[str, Dict[str, List[float]]]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `cfg` | Optional['MocapConfig'] | `None` |
| `contacts` | Optional[List[dict]] | `None` |

**returns** `Dict[str, Dict[str, List[float]]]`

Foot contacts and toe-offs per leg, from MARKER kinematics alone.

``{"l": {"contact": [t...], "off": [t...]}, "r": {...}}``.

Force plates only see a foot while it is ON a plate, so a stride that  
starts on a plate and ends off it cannot be closed from GRF. Marker  
kinematics see the foot throughout: a contact is a minimum of foot height  
where vertical velocity crosses from negative to ~zero, and a toe-off is  
where it starts rising again. That lets the contralateral stride be  
completed while the other leg is the one being measured.

Detection is deliberately kinematic-only so it works for the many trials  
here whose GRF.xml maps one plate or none.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L1134)</sub>

### `contact_feet`

```python
contact_feet(
    exp_dir: str,
    body_mass=None,
    cfg: Optional['MocapConfig'] = None
) -> List[dict]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `body_mass` | – | `None` |
| `cfg` | Optional['MocapConfig'] | `None` |

**returns** `List[dict]`

Ground contacts with the foot that made each one, from the DATA.

Returns ``[{"t_on", "t_off", "side", "peak_n", "plate", "margin_m"}]``.

The foot is decided by comparing the plate's centre of pressure against  
each foot's markers at the instant of peak force — NOT by reading  
GRF.XML. That mapping is produced once at export time and is wrong often  
enough to matter: on Run_baselineB2 it labels both plates "right", while  
the CoP sits 2.5 cm from the LEFT foot and 73 cm from the right on the  
first contact. ``margin_m`` is the difference between the two distances,  
so a marginal assignment is visible rather than silent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L1263)</sub>

### `jump_height`

```python
jump_height(
    t: np.ndarray,
    vert: np.ndarray,
    t_takeoff: float,
    t_land: float,
    gt: Optional[np.ndarray] = None,
    total: Optional[np.ndarray] = None,
    body_mass: Optional[float] = None,
    t_start: Optional[float] = None,
    cfg: Optional['MocapConfig'] = None
) -> Dict[str, float]
```

| input | type | default |
|---|---|---|
| `t` | np.ndarray | required |
| `vert` | np.ndarray | required |
| `t_takeoff` | float | required |
| `t_land` | float | required |
| `gt` | Optional[np.ndarray] | `None` |
| `total` | Optional[np.ndarray] | `None` |
| `body_mass` | Optional[float] | `None` |
| `t_start` | Optional[float] | `None` |
| `cfg` | Optional['MocapConfig'] | `None` |

**returns** `Dict[str, float]`

Jump height by three independent routes, all in metres.

* **impulse** — the net vertical impulse from ``t_start`` (where the body  
  is at rest, i.e. the start of the task) to take-off gives the take-off  
  velocity; height is then ``v**2 / 2g``. This is the reference method,  
  and the only one that uses the force plates.  
* **flight**  — ``g * t_flight**2 / 8`` from the airborne duration alone.  
  Needs no mass and no marker, so it survives trials where either is bad,  
  but it assumes take-off and landing heights are equal — which they are  
  not if the participant lands in a deeper crouch than they left.  
* **marker**  — peak pelvis height minus pelvis height at take-off. This  
  is the same quantity the impulse route estimates, measured directly.

Three routes rather than one because they fail differently: a mis-entered  
body mass moves the impulse estimate and leaves the other two untouched,  
an occluded pelvis moves the marker estimate alone. Agreement between them  
is the check that any of them is trustworthy.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L1543)</sub>

### `bar_centre`

```python
bar_centre(
    markers: Dict[str, np.ndarray],
    cfg: Optional['MocapConfig'] = None
) -> Optional[np.ndarray]
```

| input | type | default |
|---|---|---|
| `markers` | Dict[str, np.ndarray] | required |
| `cfg` | Optional['MocapConfig'] | `None` |

**returns** `Optional[np.ndarray]`

Mean of the barbell markers, or None when the project has no bar.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L1608)</sub>

### `bar_metrics`

```python
bar_metrics(
    t: np.ndarray,
    bar: np.ndarray,
    t_start: float,
    t_end: float,
    concentric: Optional[Tuple[float, float]] = None,
    cfg: Optional['MocapConfig'] = None
) -> Dict[str, float]
```

| input | type | default |
|---|---|---|
| `t` | np.ndarray | required |
| `bar` | np.ndarray | required |
| `t_start` | float | required |
| `t_end` | float | required |
| `concentric` | Optional[Tuple[float, float]] | `None` |
| `cfg` | Optional['MocapConfig'] | `None` |

**returns** `Dict[str, float]`

Bar path measures over one lift, in SI units.

* ``rom_m``            vertical travel of the bar  
* ``start_frac``       where the bar began within its own vertical range;  
  the number that separates a deadlift (0) from a squat (1)  
* ``ap_drift_m``       total fore-aft excursion — how far the bar wandered  
  away from the vertical, which is the usual coaching read on bar path  
* ``path_deviation_m`` largest fore-aft departure from the bar's position  
  at the start of the concentric, i.e. the bow in the pull  
* ``peak_velocity_ms`` fastest upward bar velocity  
* ``mean_concentric_velocity_ms`` mean upward velocity over the concentric,  
  the quantity velocity-based training is prescribed against

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L1627)</sub>

### `segment_trial`

```python
segment_trial(
    exp_dir: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None
) -> List[TaskSegment]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |

**returns** `List[TaskSegment]`

Split one trial into the tasks it actually contains.

A capture is rarely one task. A single-leg squat trial is typically  
*stand -> lift a foot -> squat -> rise -> put the foot down*, and collapsing  
that to one label both loses the timing and can pick the wrong winner: the  
standing portions make the whole trial look bilateral.

Support state comes from the FOOT MARKERS, not the force plates. Plate  
mapping is per-trial and frequently partial — SLSback_post1's GRF.xml  
registers a single plate, so the stance foot spends the trial on an  
unmapped one and force alone reports "airborne" for 68% of a standing  
trial. Marker height needs no plate mapping at all. GRF is still used for  
flight detection when the mapping covers both feet.

Returns a list of :class:`TaskSegment` ordered in time; an empty list when  
there are no markers to work from.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L1919)</sub>

### `gait_cycles`

```python
gait_cycles(
    exp_dir: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None,
    segments: Optional[List[TaskSegment]] = None
) -> List[dict]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |
| `segments` | Optional[List[TaskSegment]] | `None` |

**returns** `List[dict]`

One dict per gait cycle in a capture — the unit the pipeline runs on.

A long overground recording is not one thing to simulate. walking1 on FAIS  
073 is 85 s, twelve walkways and thirty-six footfalls, and every one of  
those footfalls is a separate stride with its own plate, its own leg and  
its own window. This is the list that becomes  
``3_iterations/<model>/<name>/`` — one folder per cycle.

Each entry::

    {"name": "walking1_r1", "side": "right", "index": 1, "task": "walking",  
     "time_range": [t0, t1],        # the cycle, foot-off to foot-off  
     "cycle_from": "foot_off",  
     "stance": [t_on, t_off],       # the plate contact inside it  
     "plates": ["ground_force_2"],  # more than one if the step straddled  
     "peak_n": 837.3,  
     "side_margin_m": 0.52,         # CoP margin behind the leg assignment  
     "shared_plate": False,         # the plate also took the other foot  
     "straddled": False,            # the step spanned two plates  
     "events": [["r", "strike", 82.94], ...],  
     "confidence": 0.75, "reason": "..."}

``events`` holds the foot strikes and foot offs of BOTH legs inside the  
window, which is what an external-loads file for that cycle needs: the  
contralateral foot is on the ground for part of every walking cycle.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L2583)</sub>

### `detect_window`

```python
detect_window(
    exp_dir: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None
) -> Dict[str, tuple]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |

**returns** `Dict[str, tuple]`

Suggest the analysis window from each modality independently.

Returns ``{"grf": (t0,t1), "markers": (...), "emg": (...),  
"consensus": (...)}`` — an empty tuple where that modality had nothing to  
say. Three independent opinions are reported rather than one number so a  
disagreement is visible: if GRF and markers bracket different intervals,  
the plate assignment or the marker export is suspect.

* **grf**     — total vertical force above ``load_bw`` body weights.  
* **markers** — pelvis speed above ``static_speed``, OR (for a stationary  
  task, where that never fires) pelvis height outside a 2 cm band around  
  its own start, which is what a squat descent looks like.  
* **emg**     — any normalised channel above ``emg_active`` of its own  
  range. Uses ``emg_filtered_normalised.mot`` when present, else  
  ``emg_filtered.mot``.  
* **consensus** — the MEDIAN start and median end of whichever modalities  
  spoke. The median ignores one dissenting modality without needing it to  
  be identified in advance.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L2704)</sub>

### `classify_features`

```python
classify_features(
    f: TrialFeatures,
    cfg: Optional[MocapConfig] = None
) -> Tuple[str, float, str]
```

| input | type | default |
|---|---|---|
| `f` | TrialFeatures | required |
| `cfg` | Optional[MocapConfig] | `None` |

**returns** `Tuple[str, float, str]`

(label, confidence 0-1, one-line reason) from measured features.

Ordered most-specific first. Confidence is a blunt indicator of how far the  
deciding feature sat from its threshold, not a probability.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L2790)</sub>

### `classify_trial`

```python
classify_trial(
    exp_dir: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None
)
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |

Classify one exported trial folder.

Returns ``(label, confidence, reason, TrialFeatures)``.

    from bioscout.session.movement_detector import classify_trial  
    label, conf, why, feats = classify_trial(  
        "simulations/021/session1/2_experimental/RunG3", body_mass=61.3)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L2860)</sub>

### `plot_trial_tasks`

```python
plot_trial_tasks(
    exp_dir: str,
    out_png: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None,
    segments=None
) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `out_png` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |
| `segments` | – | `None` |

**returns** `Optional[str]`

Vertical GRF + pelvis height for one trial, with the tasks shaded.

Lives here rather than in a project's test folder so the CLI  
(``bioscout --classifier``) and any project test draw the SAME figure — a  
QC plot that differs between the tool and the test is worse than none.

Returns the path written, or None when the trial has nothing to draw.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mocap.py#L2926)</sub>
