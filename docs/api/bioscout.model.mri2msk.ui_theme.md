# `bioscout.model.mri2msk.ui_theme`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py)

BioScout-style look for the MRI2MSK GUI (dark CustomTkinter).

Palette sampled from the BioScout app: near-black window, dark-grey sidebar and  
cards, blue primary buttons, green success, muted status colours.

## Contents

- [`setup`](#setup) — 
- [`f`](#f) — 
- [`card`](#card) — Rounded dark panel with an optional bold title; returns the frame. Put content into ``frame.body``.
- [`button`](#button) — 
- [`entry`](#entry) — 
- [`label`](#label) — 
- [`set_enabled`](#set_enabled) — 
- [`is_enabled`](#is_enabled) — 
- [`image`](#image) — CTkImage from assets/ (None if missing).
- [`style_treeview`](#style_treeview) — Dark ttk.Treeview matching the CTk theme.
- [`set_app_icon`](#set_app_icon) — Window + Windows-taskbar icon from assets/icon.ico / icon_64.png.
- [`set_windows_app_id`](#set_windows_app_id) — Own taskbar entry/icon instead of python.exe's (call before creating the window).

### `setup`

```python
setup()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L42)</sub>

### `f`

```python
f(size=12, weight='normal')
```

| input | type | default |
|---|---|---|
| `size` | – | `12` |
| `weight` | – | `'normal'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L47)</sub>

### `card`

```python
card(parent, title: str | None = None, **kw) -> ctk.CTkFrame
```

| input | type | default |
|---|---|---|
| `parent` | – | required |
| `title` | str \| None | `None` |
| `**kw` | – | – |

**returns** `ctk.CTkFrame`

Rounded dark panel with an optional bold title; returns the frame.  
Put content into ``frame.body``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L51)</sub>

### `button`

```python
button(parent, text, command=None, kind='primary', width=90, **kw) -> ctk.CTkButton
```

| input | type | default |
|---|---|---|
| `parent` | – | required |
| `text` | – | required |
| `command` | – | `None` |
| `kind` | – | `'primary'` |
| `width` | – | `90` |
| `**kw` | – | – |

**returns** `ctk.CTkButton`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L64)</sub>

### `entry`

```python
entry(parent, var, width=200, readonly=False) -> ctk.CTkEntry
```

| input | type | default |
|---|---|---|
| `parent` | – | required |
| `var` | – | required |
| `width` | – | `200` |
| `readonly` | – | `False` |

**returns** `ctk.CTkEntry`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L72)</sub>

### `label`

```python
label(parent, text='', size=12, color=TEXT, weight='normal', **kw) -> ctk.CTkLabel
```

| input | type | default |
|---|---|---|
| `parent` | – | required |
| `text` | – | `''` |
| `size` | – | `12` |
| `color` | – | `TEXT` |
| `weight` | – | `'normal'` |
| `**kw` | – | – |

**returns** `ctk.CTkLabel`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L81)</sub>

### `set_enabled`

```python
set_enabled(widget, on: bool)
```

| input | type | default |
|---|---|---|
| `widget` | – | required |
| `on` | bool | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L85)</sub>

### `is_enabled`

```python
is_enabled(widget) -> bool
```

| input | type | default |
|---|---|---|
| `widget` | – | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L92)</sub>

### `image`

```python
image(name: str, height: int | None = None)
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `height` | int \| None | `None` |

CTkImage from assets/ (None if missing).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L99)</sub>

### `style_treeview`

```python
style_treeview(root)
```

| input | type | default |
|---|---|---|
| `root` | – | required |

Dark ttk.Treeview matching the CTk theme.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L111)</sub>

### `set_app_icon`

```python
set_app_icon(root)
```

| input | type | default |
|---|---|---|
| `root` | – | required |

Window + Windows-taskbar icon from assets/icon.ico / icon_64.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L129)</sub>

### `set_windows_app_id`

```python
set_windows_app_id(app_id='univie.neuromechanics.mri2msk')
```

| input | type | default |
|---|---|---|
| `app_id` | – | `'univie.neuromechanics.mri2msk'` |

Own taskbar entry/icon instead of python.exe's (call before creating the window).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/ui_theme.py#L149)</sub>
