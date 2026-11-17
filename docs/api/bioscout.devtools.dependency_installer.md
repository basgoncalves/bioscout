# `bioscout.devtools.dependency_installer`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/dependency_installer.py)

  
**dependency_installer.py**

Checks and installs bioscout dependencies.

  
**Dependency categories**

  pip      — standard PyPI packages; handled by `pip install bioscout`  
  conda    — opensim; NOT on PyPI, must be installed via conda  
  optional — opencv / mediapipe; needed only for video/recording tabs

  
**Usage**

  python -m bioscout --install          # interactive check + install  
  python -m bioscout --install --quiet  # non-interactive, just report

## Contents

- class [`Dep`](#dep) — 
- [`check`](#check) — Return {import_name: is_installed} for all tracked deps.
- [`report`](#report) — Print a dependency status table.
- [`install_missing`](#install_missing) — Check all deps and offer to install missing ones.

<a id="dep"></a>

## class `Dep`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/dependency_installer.py#L28)</sub>

### `check`

```python
check() -> dict[str, bool]
```

**returns** `dict[str, bool]`

Return {import_name: is_installed} for all tracked deps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/dependency_installer.py#L112)</sub>

### `report`

```python
report() -> None
```

**returns** `None`

Print a dependency status table.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/dependency_installer.py#L117)</sub>

### `install_missing`

```python
install_missing(interactive: bool = True) -> bool
```

| input | type | default |
|---|---|---|
| `interactive` | bool | `True` |

**returns** `bool`

Check all deps and offer to install missing ones.

Returns True if all non-optional deps are satisfied after the run.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/dependency_installer.py#L128)</sub>
