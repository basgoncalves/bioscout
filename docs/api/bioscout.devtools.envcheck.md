# `bioscout.devtools.envcheck`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py)

Is bioscout running in the environment it expects, and if not, build it.

    bioscout utils env            # report  
    bioscout utils env --create   # create bioscoutv<version> and install into it

(``--env`` / ``--env-create`` still work and print a one-line pointer to the  
verb form. Verbs are the interface; the flags are the compatibility layer.)  
    python -m bioscout.devtools.envcheck

One environment per bioscout version, named ``bioscoutv<version>`` -- so  
``bioscout 2.0.0b8`` wants ``bioscoutv2.0.0b8``. That is deliberate rather than a  
single long-lived env: OpenSim, CEINMS and the model files move together with the  
package, and a run from three months ago is only reproducible if its dependency  
set still exists. Old envs are cheap to keep and one command to delete.

  
**THE ONE THING THAT CANNOT WORK**

**A process cannot activate a conda environment for the shell that launched it.**  
Activation edits the *parent* shell's PATH and environment variables; a child  
Python process has no way to reach back and do that. So this module can:

  * tell you which environment you are in and which one you should be in,  
  * CREATE the right environment and install everything into it,  
  * print the exact line to run,

and it cannot activate it for you. Anything claiming otherwise is either  
re-exec'ing your shell or lying. The shell function in ``bioscout-env.sh``  
(shipped beside this file's docs) is the honest version of "just do it": it runs  
in *your* shell, so it can activate.

This module lives at the TOP of the package, not under ``bioscout.utils``, and  
imports nothing but the standard library. ``bioscout/utils/__init__.py`` pulls in  
scipy, matplotlib and the rest — so an envcheck that lived there could not be  
imported until the environment it is supposed to build already existed.

Install strategy: pip installs ``uv`` once, then ``uv`` installs everything else.  
uv resolves and downloads an order of magnitude faster than pip, which matters  
when the dependency set includes opencv and mediapipe. OpenSim is the exception  
-- it is not reliably on PyPI, so it is tried with uv/pip first and falls back to  
``conda install -c opensim-org opensim``.

## Contents

- [`missing_packages`](#missing_packages) — Pip names of declared runtime deps whose import is not importable.
- [`autoinstall_missing`](#autoinstall_missing) — Install any missing runtime deps into the RUNNING interpreter's env.
- [`expected_env_name`](#expected_env_name) — ``bioscoutv2.0.0b8`` for bioscout 2.0.0b8.
- [`current_env`](#current_env) — Name of the active conda env, else the active venv's folder name.
- [`conda_available`](#conda_available) — 
- [`list_envs`](#list_envs) — Every conda environment name. Empty list if conda is not on PATH.
- [`env_exists`](#env_exists) — 
- [`activation_command`](#activation_command) — 
- [`create_env`](#create_env) — ``conda create -y -n <name> python=<python>``. Idempotent.
- [`install_into`](#install_into) — pip-install uv into ``name``, then let uv install everything else.
- [`status`](#status) — 
- [`report`](#report) — 
- [`ensure`](#ensure) — Report, and optionally build the environment. Never activates — it can't.

### `missing_packages`

```python
missing_packages(packages: Optional[Dict[str, str]] = None) -> List[str]
```

| input | type | default |
|---|---|---|
| `packages` | Optional[Dict[str, str]] | `None` |

**returns** `List[str]`

Pip names of declared runtime deps whose import is not importable.

Uses ``find_spec`` rather than importing: it is milliseconds for the whole  
set, has no import side effects, and cannot itself blow up the launch.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L116)</sub>

### `autoinstall_missing`

```python
autoinstall_missing(log=print, timeout: int = 900) -> List[str]
```

| input | type | default |
|---|---|---|
| `log` | – | `print` |
| `timeout` | int | `900` |

**returns** `List[str]`

Install any missing runtime deps into the RUNNING interpreter's env.

Returns the list of packages still missing afterwards (empty on success).

Deliberate choices:

* ``sys.executable -m pip`` — installs into the interpreter that is  
  actually running, not whichever pip happens to be first on PATH. That  
  distinction is the whole point when several conda envs exist.  
* only the MISSING names are passed, and there is no ``--upgrade``. This  
  never touches a package that already imports, so a working environment  
  cannot be changed by a launch.  
* :data:`NEVER_AUTOINSTALL` members are reported, never installed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L135)</sub>

### `expected_env_name`

```python
expected_env_name(version: Optional[str] = None) -> str
```

| input | type | default |
|---|---|---|
| `version` | Optional[str] | `None` |

**returns** `str`

``bioscoutv2.0.0b8`` for bioscout 2.0.0b8.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L204)</sub>

### `current_env`

```python
current_env() -> Optional[str]
```

**returns** `Optional[str]`

Name of the active conda env, else the active venv's folder name.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L209)</sub>

### `conda_available`

```python
conda_available() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L220)</sub>

### `list_envs`

```python
list_envs() -> List[str]
```

**returns** `List[str]`

Every conda environment name. Empty list if conda is not on PATH.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L228)</sub>

### `env_exists`

```python
env_exists(name: Optional[str] = None) -> bool
```

| input | type | default |
|---|---|---|
| `name` | Optional[str] | `None` |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L240)</sub>

### `activation_command`

```python
activation_command(name: Optional[str] = None) -> str
```

| input | type | default |
|---|---|---|
| `name` | Optional[str] | `None` |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L244)</sub>

### `create_env`

```python
create_env(name: Optional[str] = None, python: str = DEFAULT_PYTHON, log=print) -> bool
```

| input | type | default |
|---|---|---|
| `name` | Optional[str] | `None` |
| `python` | str | `DEFAULT_PYTHON` |
| `log` | – | `print` |

**returns** `bool`

``conda create -y -n <name> python=<python>``. Idempotent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L249)</sub>

### `install_into`

```python
install_into(
    name: Optional[str] = None,
    requirements: Optional[str] = None,
    editable: Optional[str] = None,
    log=print
) -> bool
```

| input | type | default |
|---|---|---|
| `name` | Optional[str] | `None` |
| `requirements` | Optional[str] | `None` |
| `editable` | Optional[str] | `None` |
| `log` | – | `print` |

**returns** `bool`

pip-install uv into ``name``, then let uv install everything else.

``requirements`` defaults to the repo's requirements.txt when bioscout is  
running from a source checkout; ``editable`` to that checkout, so the env  
tracks your working tree instead of a release.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L275)</sub>

### `status`

```python
status() -> Dict[str, object]
```

**returns** `Dict[str, object]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L373)</sub>

### `report`

```python
report(log=print) -> Dict[str, object]
```

| input | type | default |
|---|---|---|
| `log` | – | `print` |

**returns** `Dict[str, object]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L389)</sub>

### `ensure`

```python
ensure(
    create: bool = False,
    install: bool = True,
    python: str = DEFAULT_PYTHON,
    log=print
) -> Dict[str, object]
```

| input | type | default |
|---|---|---|
| `create` | bool | `False` |
| `install` | bool | `True` |
| `python` | str | `DEFAULT_PYTHON` |
| `log` | – | `print` |

**returns** `Dict[str, object]`

Report, and optionally build the environment. Never activates — it can't.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/envcheck.py#L431)</sub>
