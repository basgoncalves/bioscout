# `bioscout.model.edit.naming`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/naming.py)

Where an operation's output goes — one rule, in one place.

bioscout had at least six naming conventions for the same idea, each baked into  
the function that used it: ``_increased_3.00.osim``, ``_updatedMasses.osim``,  
``_scaledMasses.osim``, ``_lockedCoords.osim``, ``_opt_N10.osim``,  
``_modWO.osim``, ``_wrap_added.osim``, ``_modified_validated.osim``, plus  
``set_total_mass`` writing in place. A caller could not predict the filename, so  
every caller either hard-coded it or globbed for it afterwards.

The rule here: the output is the input's stem plus the operation's suffix  
template, in the input's directory, unless the caller says otherwise. Suffixes  
compose, so a chain reads as its own provenance:

    scaled.osim -> scaled_opt_N10.osim -> scaled_opt_N10_mvicx3.00.osim

which is exactly the convention ``session.yaml`` already uses. The names it  
produces are therefore the names the Powerlifting project's ``ceinms_model`` and  
``so_model`` keys already point at, by construction rather than by coincidence.

## Contents

- [`derive_out`](#derive_out) — ``<out_dir or model.parent>/<model.stem><suffix>.osim``.
- [`backup`](#backup) — Copy ``path`` beside itself under ``_backup_<tag>/`` before it is replaced.
- [`prepare_out`](#prepare_out) — Resolve and validate the output path, creating its directory.

### `derive_out`

```python
derive_out(
    model: os.PathLike | str,
    suffix: str,
    params: Dict[str, Any],
    out_dir: Optional[str] = None
) -> Path
```

| input | type | default |
|---|---|---|
| `model` | os.PathLike \| str | required |
| `suffix` | str | required |
| `params` | Dict[str, Any] | required |
| `out_dir` | Optional[str] | `None` |

**returns** `Path`

``<out_dir or model.parent>/<model.stem><suffix>.osim``.

``suffix`` is formatted against ``params`` -- ``"_mvicx{factor:.2f}"`` with  
``factor=3.0`` gives ``_mvicx3.00``. A KeyError here means the op declared a  
suffix referring to a parameter it does not have, which is a bug in the op,  
so it is raised rather than silently dropped.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/naming.py#L34)</sub>

### `backup`

```python
backup(path: os.PathLike | str, tag: str = 'model_edit') -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `path` | os.PathLike \| str | required |
| `tag` | str | `'model_edit'` |

**returns** `Optional[Path]`

Copy ``path`` beside itself under ``_backup_<tag>/`` before it is replaced.

Returns the backup path, or None if there was nothing to back up. Deliberately  
a sibling folder rather than a ``.bak`` suffix: a stray ``*.osim.bak`` in an  
iteration folder gets picked up by the model globs in ``settings.py`` and  
``change_moment_arms/cli.py``, and then shows up as a model you can run.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/naming.py#L58)</sub>

### `prepare_out`

```python
prepare_out(
    model: os.PathLike | str,
    out: Optional[os.PathLike | str],
    suffix: str,
    params: Dict[str, Any],
    out_dir: Optional[str] = None,
    overwrite: bool = False,
    tag: str = 'model_edit'
) -> Path
```

| input | type | default |
|---|---|---|
| `model` | os.PathLike \| str | required |
| `out` | Optional[os.PathLike \| str] | required |
| `suffix` | str | required |
| `params` | Dict[str, Any] | required |
| `out_dir` | Optional[str] | `None` |
| `overwrite` | bool | `False` |
| `tag` | str | `'model_edit'` |

**returns** `Path`

Resolve and validate the output path, creating its directory.

Refuses two things on purpose:

* writing on top of the input model. Editing in place makes a chain  
  irreproducible and destroys the only copy of the thing you were comparing  
  against; ``set_total_mass`` does this today and it is why an MRI model's  
  mass history cannot be reconstructed.  
* silently replacing an existing different file. With ``overwrite=True`` the  
  previous version is copied into ``_backup_<tag>/`` first, so re-running a  
  recipe is safe but not lossy.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/naming.py#L80)</sub>
