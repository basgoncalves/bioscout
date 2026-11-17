# `bioscout.model.mri2msk.gui_postwarp`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py)

Post-Warp Pipeline page (BioScout session) for the MRI2MSK GUI.

## Contents

- class [`PostWarpTab`](#postwarptab) — 
  - [`PostWarpTab.config_dict`](#postwarptabconfig_dict) — 
  - [`PostWarpTab.apply_config`](#postwarptabapply_config) — 
  - [`PostWarpTab.participant`](#postwarptabparticipant) — 
  - [`PostWarpTab.autodetect`](#postwarptabautodetect) — 
  - [`PostWarpTab.mass`](#postwarptabmass) — 
  - [`PostWarpTab.session`](#postwarptabsession) — 
  - [`PostWarpTab.refresh`](#postwarptabrefresh) — 
  - [`PostWarpTab.selected_trials`](#postwarptabselected_trials) — 
  - [`PostWarpTab.run`](#postwarptabrun) — 

<a id="postwarptab"></a>

## class `PostWarpTab`

```python
PostWarpTab(app, parent)
```

| input | type | default |
|---|---|---|
| `app` | – | required |
| `parent` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L29)</sub>

<a id="postwarptabconfig_dict"></a>

### `PostWarpTab.config_dict`

```python
PostWarpTab.config_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L119)</sub>

<a id="postwarptabapply_config"></a>

### `PostWarpTab.apply_config`

```python
PostWarpTab.apply_config(d: dict)
```

| input | type | default |
|---|---|---|
| `d` | dict | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L123)</sub>

<a id="postwarptabparticipant"></a>

### `PostWarpTab.participant`

```python
PostWarpTab.participant() -> Path | None
```

**returns** `Path \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L132)</sub>

<a id="postwarptabautodetect"></a>

### `PostWarpTab.autodetect`

```python
PostWarpTab.autodetect(quiet=False)
```

| input | type | default |
|---|---|---|
| `quiet` | – | `False` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L136)</sub>

<a id="postwarptabmass"></a>

### `PostWarpTab.mass`

```python
PostWarpTab.mass() -> float | None
```

**returns** `float \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L177)</sub>

<a id="postwarptabsession"></a>

### `PostWarpTab.session`

```python
PostWarpTab.session() -> pw.PostWarpSession | None
```

**returns** `pw.PostWarpSession \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L183)</sub>

<a id="postwarptabrefresh"></a>

### `PostWarpTab.refresh`

```python
PostWarpTab.refresh(force=False)
```

| input | type | default |
|---|---|---|
| `force` | – | `False` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L223)</sub>

<a id="postwarptabselected_trials"></a>

### `PostWarpTab.selected_trials`

```python
PostWarpTab.selected_trials() -> list[str]
```

**returns** `list[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L266)</sub>

<a id="postwarptabrun"></a>

### `PostWarpTab.run`

```python
PostWarpTab.run(steps: list[str])
```

| input | type | default |
|---|---|---|
| `steps` | list[str] | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui_postwarp.py#L271)</sub>
