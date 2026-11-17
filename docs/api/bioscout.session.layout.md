# `bioscout.session.layout`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/layout.py)

Where things live inside a session folder — old and new layouts.

A session used to be a flat pile of folders::

    <session>/  
        c3dfiles/            raw captures  
        experimental/        model-independent exports (markers, GRF, EMG)  
        cateli/              model iteration  
        gpk/                 model iteration  
        logs/  results/  ...

which sorts alphabetically into an order that says nothing about the pipeline,  
and mixes iterations in with shared inputs. The numbered layout fixes both::

    <session>/  
        1_c3dfiles/  
        2_experimental/  
        3_iterations/  
            cateli/  
            gpk/  
        logs/  results/  ...

**Both are supported.** Every resolver here prefers whichever form already  
exists on disk and falls back to the numbered name when creating something new,  
so existing sessions (and other projects, and collaborators' copies) keep  
working untouched while new output adopts the numbered names. Nothing here  
renames anything — migration is a deliberate, separate act.

Call the resolvers rather than joining these names by hand; that is the only  
thing keeping the two layouts from drifting apart.

## Contents

- [`is_numbered_layout`](#is_numbered_layout) — True when this session already uses the numbered folder names.
- [`c3d_root`](#c3d_root) — Folder holding this session's raw ``.c3d`` captures.
- [`experimental_root`](#experimental_root) — Folder holding model-independent exports (markers, GRF, EMG).
- [`iterations_root`](#iterations_root) — Parent folder of the model iterations.
- [`iteration_path`](#iteration_path) — Folder for one model iteration.

### `is_numbered_layout`

```python
is_numbered_layout(session_dir: str) -> bool
```

| input | type | default |
|---|---|---|
| `session_dir` | str | required |

**returns** `bool`

True when this session already uses the numbered folder names.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/layout.py#L77)</sub>

### `c3d_root`

```python
c3d_root(session_dir: str, create: bool = False) -> str
```

| input | type | default |
|---|---|---|
| `session_dir` | str | required |
| `create` | bool | `False` |

**returns** `str`

Folder holding this session's raw ``.c3d`` captures.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/layout.py#L85)</sub>

### `experimental_root`

```python
experimental_root(
    session_dir: str,
    subdir: Optional[str] = None,
    create: bool = False
) -> str
```

| input | type | default |
|---|---|---|
| `session_dir` | str | required |
| `subdir` | Optional[str] | `None` |
| `create` | bool | `False` |

**returns** `str`

Folder holding model-independent exports (markers, GRF, EMG).

``subdir`` overrides the name entirely — that is how a downsample run  
redirects to e.g. ``experimental_ds10``. An override is used verbatim  
(no numbered/plain resolution), since it names one specific variant.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/layout.py#L90)</sub>

### `iterations_root`

```python
iterations_root(session_dir: str, create: bool = False) -> str
```

| input | type | default |
|---|---|---|
| `session_dir` | str | required |
| `create` | bool | `False` |

**returns** `str`

Parent folder of the model iterations.

Resolution order:  
  1. ``<session>/3_iterations`` if it exists;  
  2. ``<session>/3_iterations`` if the session is otherwise numbered  
     (``1_c3dfiles``/``2_experimental`` present) — a numbered session  
     should not start dropping iterations at the top level;  
  3. the session folder itself if the session is in the old flat layout;  
  4. ``<session>/3_iterations`` for a session with nothing in it yet, so  
     new sessions get the numbered layout.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/layout.py#L106)</sub>

### `iteration_path`

```python
iteration_path(session_dir: str, iteration: str) -> str
```

| input | type | default |
|---|---|---|
| `session_dir` | str | required |
| `iteration` | str | required |

**returns** `str`

Folder for one model iteration.

Looks under ``3_iterations/`` first, then directly under the session, so a  
half-migrated session still resolves. Falls back to the layout's canonical  
location when neither exists yet (i.e. for a folder about to be created).

The session-level fallback takes only a folder whose name matches EXACTLY  
and is not one of the shared folders. Windows compares names without case,  
so ``isdir(<session>/gpk)`` is True for a ``GPK/`` folder of generic-model  
files, and that folder became iteration ``gpk``: every iteration-relative  
path (model_scaled, markerset, ...) resolved one level too high, and new  
outputs would have gone into the model folder (found 2026-09-11, the  
TestIterationKeys fixture on Windows; Linux never saw it).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/layout.py#L131)</sub>
