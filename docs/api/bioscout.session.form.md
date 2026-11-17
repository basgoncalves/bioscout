# `bioscout.session.form`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py)

The model behind the session editor: read a ``session.yaml``, edit it safely.

Separate from the dialog on purpose. Everything that can silently corrupt a  
session lives here and is unit-tested; the GUI on top is only widgets.

  
**The rule that shapes this module**

``session.yaml`` is hand-written and **carries comments that explain the study**  
— the FAIS files open with six lines on why there is one CEINMS calibration per  
fatigue state. Round-tripping through ``yaml.safe_load`` + ``yaml.dump`` loses  
every one of them, reorders keys, and reformats values, and the loss is silent  
and unrecoverable. So nothing here ever re-dumps: edits go through  
:class:`bioscout.utils.file_edit.YamlDocument`, which patches the character span  
of the value being changed and leaves every other byte alone.

  
**What it checks**

The red flags are the things that make a run fail hours later, or — worse —  
succeed on the wrong data:

* no c3d files in ``1_c3dfiles/`` (there is nothing to run)  
* ``static_trial`` naming a trial that does not exist (scaling has nothing to measure)  
* calibration or normalisation trials that are not in the session  
* trials in the yaml with no matching c3d, and c3d files no trial refers to  
* a duplicate ``emg_map`` key — YAML keeps the last silently, and the run then  
  reads the wrong electrode

## Contents

- class [`SessionForm`](#sessionform) — One session's editable state, backed by a surgical YAML patcher.
  - [`SessionForm.reload`](#sessionformreload) — 
  - [`SessionForm.c3d_dir`](#sessionformc3d_dir) — 
  - [`SessionForm.c3d_trials`](#sessionformc3d_trials) — Trial names taken from the c3d filenames, sorted.
  - [`SessionForm.trials`](#sessionformtrials) — Every trial name the session knows: the yaml's, then any extra c3d.
  - [`SessionForm.trial_types`](#sessionformtrial_types) — 
  - [`SessionForm.value`](#sessionformvalue) — 
  - [`SessionForm.list_value`](#sessionformlist_value) — 
  - [`SessionForm.trial_role`](#sessionformtrial_role) — Trials with ``role`` — ``"calibration"`` or ``"emg_normalisation"``.
  - [`SessionForm.set_trial_role`](#sessionformset_trial_role) — Write ``trials.<trial>.<role>: true|false``.
  - [`SessionForm.problems`](#sessionformproblems) — Human-readable blockers and warnings, worst first. Empty is good.
  - [`SessionForm.duplicate_emg_keys`](#sessionformduplicate_emg_keys) — Repeated keys under ``emg_map``. ``safe_load`` cannot see these.
  - [`SessionForm.set_scalar`](#sessionformset_scalar) — Set a top-level scalar, keeping its type.
  - [`SessionForm.set_list`](#sessionformset_list) — Replace a top-level list.
  - [`SessionForm.set_trial_type`](#sessionformset_trial_type) — Set ``trials.<trial>.type``, creating the trial entry if it is new.
  - [`SessionForm.set_trial_field`](#sessionformset_trial_field) — Set any key under ``trials.<trial>``, creating the trial if it is new.
  - [`SessionForm.set_ceinms`](#sessionformset_ceinms) — Set keys under ``ceinms:``.
  - [`SessionForm.iterations`](#sessionformiterations) — 
  - [`SessionForm.calibration_configs`](#sessionformcalibration_configs) — Named calibration blocks, if `calibration:` holds names rather than bare parameters. An iteration's `calibration:` selects one of these.
  - [`SessionForm.set_iteration_field`](#sessionformset_iteration_field) — Set one key inside one iteration block, creating the key if absent. A dict is written as an inline mapping, a number bare, a bool as true/false, anything else as a (quoted if needed) string.
  - [`SessionForm.delete_iteration_field`](#sessionformdelete_iteration_field) — Remove one key from one iteration block (no-op if absent).
  - [`SessionForm.add_iteration`](#sessionformadd_iteration) — Create an iteration block. Written as an indented block mapping so it reads like the ones already there, not as inline flow style.
  - [`SessionForm.duplicate_iteration`](#sessionformduplicate_iteration) — 
  - [`SessionForm.delete_iteration`](#sessionformdelete_iteration) — 
  - [`SessionForm.delete_trial`](#sessionformdelete_trial) — Remove a trial from `trials:` and from every list that names it.
  - [`SessionForm.emg_filter`](#sessionformemg_filter) — The effective settings, defaults included, for display.
  - [`SessionForm.set_emg_filter`](#sessionformset_emg_filter) — Write `emg_filter:`, creating the block on first use.
  - [`SessionForm.emg_map`](#sessionformemg_map) — ``{channel: [muscle, ...]}`` as stored. A scalar value (one muscle written without brackets) is normalised to a one-element list here so callers never branch on shape.
  - [`SessionForm.set_emg_map_entry`](#sessionformset_emg_map_entry) — Write one ``emg_map`` entry, creating the block on first use.
  - [`SessionForm.delete_emg_map_entry`](#sessionformdelete_emg_map_entry) — 
  - [`SessionForm.dirty`](#sessionformdirty) — 
  - [`SessionForm.diff`](#sessionformdiff) — 
  - [`SessionForm.save`](#sessionformsave) — 
  - [`SessionForm.scaffold`](#sessionformscaffold) — Write a first ``session.yaml`` from the c3d files, then load it.

<a id="sessionform"></a>

## class `SessionForm`

```python
SessionForm(session_dir)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |

One session's editable state, backed by a surgical YAML patcher.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L96)</sub>

<a id="sessionformreload"></a>

### `SessionForm.reload`

```python
SessionForm.reload() -> 'SessionForm'
```

**returns** `'SessionForm'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L109)</sub>

<a id="sessionformc3d_dir"></a>

### `SessionForm.c3d_dir`

```python
SessionForm.c3d_dir() -> Optional[Path]
```

**returns** `Optional[Path]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L118)</sub>

<a id="sessionformc3d_trials"></a>

### `SessionForm.c3d_trials`

```python
SessionForm.c3d_trials() -> List[str]
```

**returns** `List[str]`

Trial names taken from the c3d filenames, sorted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L125)</sub>

<a id="sessionformtrials"></a>

### `SessionForm.trials`

```python
SessionForm.trials() -> List[str]
```

**returns** `List[str]`

Every trial name the session knows: the yaml's, then any extra c3d.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L132)</sub>

<a id="sessionformtrial_types"></a>

### `SessionForm.trial_types`

```python
SessionForm.trial_types() -> Dict[str, str]
```

**returns** `Dict[str, str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L138)</sub>

<a id="sessionformvalue"></a>

### `SessionForm.value`

```python
SessionForm.value(key, default=None)
```

| input | type | default |
|---|---|---|
| `key` | – | required |
| `default` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L146)</sub>

<a id="sessionformlist_value"></a>

### `SessionForm.list_value`

```python
SessionForm.list_value(key) -> List[str]
```

| input | type | default |
|---|---|---|
| `key` | – | required |

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L149)</sub>

<a id="sessionformtrial_role"></a>

### `SessionForm.trial_role`

```python
SessionForm.trial_role(role: str) -> List[str]
```

| input | type | default |
|---|---|---|
| `role` | str | required |

**returns** `List[str]`

Trials with ``role`` — ``"calibration"`` or ``"emg_normalisation"``.

Reads the per-trial flag first and the legacy top-level list second,  
exactly like the runtime (``session.calibration_trial_names``), so the  
form shows what a run would actually do rather than what the file  
happens to spell.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L154)</sub>

<a id="sessionformset_trial_role"></a>

### `SessionForm.set_trial_role`

```python
SessionForm.set_trial_role(trial: str, role: str, on: bool) -> None
```

| input | type | default |
|---|---|---|
| `trial` | str | required |
| `role` | str | required |
| `on` | bool | required |

**returns** `None`

Write ``trials.<trial>.<role>: true|false``.

The per-trial flag is the schema going forward; writing it here is  
what migrates a session the first time someone ticks a box in the  
editor. The legacy list is left alone — ``_trial_role`` already  
prefers the flag, so the two cannot disagree about this trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L170)</sub>

<a id="sessionformproblems"></a>

### `SessionForm.problems`

```python
SessionForm.problems() -> List[str]
```

**returns** `List[str]`

Human-readable blockers and warnings, worst first. Empty is good.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L181)</sub>

<a id="sessionformduplicate_emg_keys"></a>

### `SessionForm.duplicate_emg_keys`

```python
SessionForm.duplicate_emg_keys() -> List[str]
```

**returns** `List[str]`

Repeated keys under ``emg_map``. ``safe_load`` cannot see these.

A duplicate is legal YAML and resolves to the last occurrence, so the  
parsed document looks fine while the file says something else. The only  
way to catch it is to read the source.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L241)</sub>

<a id="sessionformset_scalar"></a>

### `SessionForm.set_scalar`

```python
SessionForm.set_scalar(key: str, value) -> None
```

| input | type | default |
|---|---|---|
| `key` | str | required |
| `value` | – | required |

**returns** `None`

Set a top-level scalar, keeping its type.

The tag comes from the node already in the file, so ``body_mass: 89.4``  
stays a number instead of becoming the string ``"75.2"`` — which parses,  
looks right in a diff, and then fails a comparison somewhere downstream.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L275)</sub>

<a id="sessionformset_list"></a>

### `SessionForm.set_list`

```python
SessionForm.set_list(key: str, items: Sequence[str]) -> None
```

| input | type | default |
|---|---|---|
| `key` | str | required |
| `items` | Sequence[str] | required |

**returns** `None`

Replace a top-level list.

Block style when the key already uses it, so a hand-formatted file keeps  
its shape; flow style (``[a, b]``) for a key being created, which is  
unambiguous wherever it is inserted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L304)</sub>

<a id="sessionformset_trial_type"></a>

### `SessionForm.set_trial_type`

```python
SessionForm.set_trial_type(trial: str, type_name: str) -> None
```

| input | type | default |
|---|---|---|
| `trial` | str | required |
| `type_name` | str | required |

**returns** `None`

Set ``trials.<trial>.type``, creating the trial entry if it is new.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L339)</sub>

<a id="sessionformset_trial_field"></a>

### `SessionForm.set_trial_field`

```python
SessionForm.set_trial_field(trial: str, key: str, value) -> None
```

| input | type | default |
|---|---|---|
| `trial` | str | required |
| `key` | str | required |
| `value` | – | required |

**returns** `None`

Set any key under ``trials.<trial>``, creating the trial if it is new.

A list value is written in flow style — ``time_range: [3.415, 4.85]`` —  
which is how session.yaml already spells it and keeps the trial entry to  
two lines.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L343)</sub>

<a id="sessionformset_ceinms"></a>

### `SessionForm.set_ceinms`

```python
SessionForm.set_ceinms(**params) -> None
```

| input | type | default |
|---|---|---|
| `**params` | – | – |

**returns** `None`

Set keys under ``ceinms:``.

The mapping node is re-fetched for every key: each write re-parses the  
document, which invalidates the character offsets held by any node  
grabbed earlier. Reusing one made the second edit land at the wrong  
place and produced unparseable YAML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L365)</sub>

<a id="sessionformiterations"></a>

### `SessionForm.iterations`

```python
SessionForm.iterations() -> Dict[str, dict]
```

**returns** `Dict[str, dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L379)</sub>

<a id="sessionformcalibration_configs"></a>

### `SessionForm.calibration_configs`

```python
SessionForm.calibration_configs() -> List[str]
```

**returns** `List[str]`

Named calibration blocks, if `calibration:` holds names rather than  
bare parameters. An iteration's `calibration:` selects one of these.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L383)</sub>

<a id="sessionformset_iteration_field"></a>

### `SessionForm.set_iteration_field`

```python
SessionForm.set_iteration_field(iteration: str, key: str, value) -> None
```

| input | type | default |
|---|---|---|
| `iteration` | str | required |
| `key` | str | required |
| `value` | – | required |

**returns** `None`

Set one key inside one iteration block, creating the key if absent.  
A dict is written as an inline mapping, a number bare, a bool as  
true/false, anything else as a (quoted if needed) string.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L392)</sub>

<a id="sessionformdelete_iteration_field"></a>

### `SessionForm.delete_iteration_field`

```python
SessionForm.delete_iteration_field(iteration: str, key: str) -> None
```

| input | type | default |
|---|---|---|
| `iteration` | str | required |
| `key` | str | required |

**returns** `None`

Remove one key from one iteration block (no-op if absent).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L418)</sub>

<a id="sessionformadd_iteration"></a>

### `SessionForm.add_iteration`

```python
SessionForm.add_iteration(name: str, **fields) -> None
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `**fields` | – | – |

**returns** `None`

Create an iteration block. Written as an indented block mapping so it  
reads like the ones already there, not as inline flow style.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L428)</sub>

<a id="sessionformduplicate_iteration"></a>

### `SessionForm.duplicate_iteration`

```python
SessionForm.duplicate_iteration(name: str, new_name: str) -> None
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `new_name` | str | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L449)</sub>

<a id="sessionformdelete_iteration"></a>

### `SessionForm.delete_iteration`

```python
SessionForm.delete_iteration(name: str) -> None
```

| input | type | default |
|---|---|---|
| `name` | str | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L452)</sub>

<a id="sessionformdelete_trial"></a>

### `SessionForm.delete_trial`

```python
SessionForm.delete_trial(name: str) -> None
```

| input | type | default |
|---|---|---|
| `name` | str | required |

**returns** `None`

Remove a trial from `trials:` and from every list that names it.

Leaving the name behind in `calibration_trials:` or  
`normalisation_trials:` would resurrect it as a trial with no block —  
the same dangling reference the red flags complain about — so the  
lists are pruned in the same edit. Nothing on disk is touched: the  
trial's folder, if it has one, is the user's to delete.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L455)</sub>

<a id="sessionformemg_filter"></a>

### `SessionForm.emg_filter`

```python
SessionForm.emg_filter() -> Dict[str, Any]
```

**returns** `Dict[str, Any]`

The effective settings, defaults included, for display.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L473)</sub>

<a id="sessionformset_emg_filter"></a>

### `SessionForm.set_emg_filter`

```python
SessionForm.set_emg_filter(**params) -> None
```

| input | type | default |
|---|---|---|
| `**params` | – | – |

**returns** `None`

Write `emg_filter:`, creating the block on first use.

Only values that differ from the default are written, so a session that  
keeps the defaults keeps a clean file rather than gaining five lines  
that say what the code already does.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L478)</sub>

<a id="sessionformemg_map"></a>

### `SessionForm.emg_map`

```python
SessionForm.emg_map() -> Dict[str, list]
```

**returns** `Dict[str, list]`

``{channel: [muscle, ...]}`` as stored. A scalar value (one muscle  
written without brackets) is normalised to a one-element list here so  
callers never branch on shape.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L497)</sub>

<a id="sessionformset_emg_map_entry"></a>

### `SessionForm.set_emg_map_entry`

```python
SessionForm.set_emg_map_entry(channel: str, muscles) -> None
```

| input | type | default |
|---|---|---|
| `channel` | str | required |
| `muscles` | – | required |

**returns** `None`

Write one ``emg_map`` entry, creating the block on first use.

``muscles`` is a sequence of OpenSim muscle names (``vasmed_r``…).  
Serialised as a flow list — ``[vasmed_r, vasint_r]`` — which is the  
shape every hand-written session.yaml already uses, so a file edited  
here stays diffable against one edited by hand.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L512)</sub>

<a id="sessionformdelete_emg_map_entry"></a>

### `SessionForm.delete_emg_map_entry`

```python
SessionForm.delete_emg_map_entry(channel: str) -> None
```

| input | type | default |
|---|---|---|
| `channel` | str | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L530)</sub>

<a id="sessionformdirty"></a>

### `SessionForm.dirty`

```python
SessionForm.dirty() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L536)</sub>

<a id="sessionformdiff"></a>

### `SessionForm.diff`

```python
SessionForm.diff() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L539)</sub>

<a id="sessionformsave"></a>

### `SessionForm.save`

```python
SessionForm.save(backup: bool = True) -> Path
```

| input | type | default |
|---|---|---|
| `backup` | bool | `True` |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L542)</sub>

<a id="sessionformscaffold"></a>

### `SessionForm.scaffold`

```python
SessionForm.scaffold(template=None, body_mass=None) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `template` | – | `None` |
| `body_mass` | – | `None` |

**returns** `Optional[Path]`

Write a first ``session.yaml`` from the c3d files, then load it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/form.py#L548)</sub>
