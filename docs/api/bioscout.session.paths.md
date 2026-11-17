# `bioscout.session.paths`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py)

One rule for every path in ``session.yaml``, and a report of which one applied.

  
**The problem this replaces**

There were three rules and nobody could say which applied where::

    setup_folder   os.path.join(project_dir, ...)          pipeline.py:964  
    c3d_source     os.path.join(project_dir, ...)          pipeline.py:966  
    markerset      search models/ -> generic models/ -> project root  
    so_model       the same three-root search

``markerset`` went through the *model* resolver, so  
``setup_files/markers_FAIS.xml`` landed correctly only because the third  
fallback happened to be the project root. And the FAIS sessions write  
``c3d_source: ../../../c3d_files/022``, which is session-relative, against a  
resolver that joins it to the project — three levels above the project, at a  
path that does not exist. It never bit anyone because the project stages its  
c3d files with its own script, so bioscout was never asked to resolve it.

  
**The rule**

Each key declares the bases it may resolve against, **best first**:

* **session-scoped** — data belonging to this session (``c3d_source``): the  
  session folder, then the project.  
* **project-scoped** — assets shared across sessions (``setup_folder``,  
  ``markerset``): the project, then the session.  
* **model** — ``so_model``, ``ceinms_model``, ``generic``: the iteration folder,  
  ``models/``, ``generic models/``, then the project root. Models genuinely live  
  in several places, so the search stays — what changes is that it now says  
  which one answered.

An absolute path is used as-is. The first base where the file exists wins, and  
:class:`Resolved` records it. Resolving through anything other than the first  
base is not an error — plenty of real projects are laid out that way — but it is  
reported, because "it worked, via a base you did not intend" is how a session  
silently reads the wrong file.

Nothing here imports anything but the standard library, so preflight and the  
session editor can both use it.

## Contents

- class [`Resolved`](#resolved) — What a session.yaml path turned into, and how.
  - [`Resolved.ok`](#resolvedok) — 
  - [`Resolved.preferred`](#resolvedpreferred) — True when the FIRST base for this key is the one that answered.
  - [`Resolved.note`](#resolvednote) — One line for a human, or None when it resolved as intended.
- [`base_order`](#base_order) — 
- [`resolve`](#resolve) — Resolve one session.yaml value. Never raises; check ``.ok``.
- [`resolve_all`](#resolve_all) — Resolve every path-like key in a loaded session.yaml, session keys first.

<a id="resolved"></a>

## class `Resolved`

What a session.yaml path turned into, and how.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L69)</sub>

<a id="resolvedok"></a>

### `Resolved.ok`

```python
Resolved.ok() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L80)</sub>

<a id="resolvedpreferred"></a>

### `Resolved.preferred`

```python
Resolved.preferred() -> bool
```

**returns** `bool`

True when the FIRST base for this key is the one that answered.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L84)</sub>

<a id="resolvednote"></a>

### `Resolved.note`

```python
Resolved.note() -> Optional[str]
```

**returns** `Optional[str]`

One line for a human, or None when it resolved as intended.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L89)</sub>

### `base_order`

```python
base_order(key: str) -> Tuple[str, ...]
```

| input | type | default |
|---|---|---|
| `key` | str | required |

**returns** `Tuple[str, ...]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L109)</sub>

### `resolve`

```python
resolve(key: str, raw, session_dir=None, project_dir=None, iteration_dir=None) -> Resolved
```

| input | type | default |
|---|---|---|
| `key` | str | required |
| `raw` | – | required |
| `session_dir` | – | `None` |
| `project_dir` | – | `None` |
| `iteration_dir` | – | `None` |

**returns** `Resolved`

Resolve one session.yaml value. Never raises; check ``.ok``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L130)</sub>

### `resolve_all`

```python
resolve_all(
    cfg: dict,
    session_dir=None,
    project_dir=None,
    iteration: Optional[str] = None,
    iteration_dir=None
) -> List[Resolved]
```

| input | type | default |
|---|---|---|
| `cfg` | dict | required |
| `session_dir` | – | `None` |
| `project_dir` | – | `None` |
| `iteration` | Optional[str] | `None` |
| `iteration_dir` | – | `None` |

**returns** `List[Resolved]`

Resolve every path-like key in a loaded session.yaml, session keys first.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/paths.py#L163)</sub>
