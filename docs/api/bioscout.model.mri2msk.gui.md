# `bioscout.model.mri2msk.gui`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py)

MRI2MSK GUI - BioScout-style (dark CustomTkinter).

Start with:  bioscout model mri2msk gui

Left sidebar (logo, pages, logos), participant bar, page area and a console.  
Pages: Model Warping (steps 1-8) and Post-Warp Pipeline (BioScout session:  
export C3D, scale, IK, ID, SO, JRA, JCF contributions).  
Steps run in a background thread; a timer re-checks the participant folder  
every few seconds (landmarks saved, warped model exported, ...).

## Contents

- class [`MRI2MSKApp`](#mri2mskapp) — 
  - [`MRI2MSKApp.show_page`](#mri2mskappshow_page) — 
  - [`MRI2MSKApp.log`](#mri2mskapplog) — 
  - [`MRI2MSKApp.cfg`](#mri2mskappcfg) — 
  - [`MRI2MSKApp.set_participant`](#mri2mskappset_participant) — 
  - [`MRI2MSKApp.run_in_background`](#mri2mskapprun_in_background) — Run ``work()`` in a thread with stdout routed to the console.
- [`find_opensim_creator`](#find_opensim_creator) — 
- [`open_path`](#open_path) — 
- [`main`](#main) — 

<a id="mri2mskapp"></a>

## class `MRI2MSKApp`

```python
MRI2MSKApp(root)
```

| input | type | default |
|---|---|---|
| `root` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L108)</sub>

<a id="mri2mskappshow_page"></a>

### `MRI2MSKApp.show_page`

```python
MRI2MSKApp.show_page(key)
```

| input | type | default |
|---|---|---|
| `key` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L281)</sub>

<a id="mri2mskapplog"></a>

### `MRI2MSKApp.log`

```python
MRI2MSKApp.log(msg, tag=None)
```

| input | type | default |
|---|---|---|
| `msg` | – | required |
| `tag` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L289)</sub>

<a id="mri2mskappcfg"></a>

### `MRI2MSKApp.cfg`

```python
MRI2MSKApp.cfg() -> pl.Config | None
```

**returns** `pl.Config \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L323)</sub>

<a id="mri2mskappset_participant"></a>

### `MRI2MSKApp.set_participant`

```python
MRI2MSKApp.set_participant(d)
```

| input | type | default |
|---|---|---|
| `d` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L335)</sub>

<a id="mri2mskapprun_in_background"></a>

### `MRI2MSKApp.run_in_background`

```python
MRI2MSKApp.run_in_background(label, work, on_status=None)
```

| input | type | default |
|---|---|---|
| `label` | – | required |
| `work` | – | required |
| `on_status` | – | `None` |

Run ``work()`` in a thread with stdout routed to the console.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L616)</sub>

### `find_opensim_creator`

```python
find_opensim_creator() -> str | None
```

**returns** `str \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L52)</sub>

### `open_path`

```python
open_path(p)
```

| input | type | default |
|---|---|---|
| `p` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L69)</sub>

### `main`

```python
main()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/gui.py#L713)</sub>
