"""Where an operation's output goes — one rule, in one place.

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
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["derive_out", "prepare_out", "backup"]


class OutputExists(FileExistsError):
    """Raised rather than clobbering a model the caller did not mean to replace."""


def derive_out(model: os.PathLike | str, suffix: str,
               params: Dict[str, Any], out_dir: Optional[str] = None) -> Path:
    """``<out_dir or model.parent>/<model.stem><suffix>.osim``.

    ``suffix`` is formatted against ``params`` -- ``"_mvicx{factor:.2f}"`` with
    ``factor=3.0`` gives ``_mvicx3.00``. A KeyError here means the op declared a
    suffix referring to a parameter it does not have, which is a bug in the op,
    so it is raised rather than silently dropped.
    """
    model = Path(model)
    if not suffix:
        raise ValueError(
            "this operation does not derive an output name — pass out=... "
            "explicitly (it has no single obvious suffix)")
    try:
        tail = suffix.format(**params)
    except KeyError as e:
        raise KeyError(f"suffix {suffix!r} refers to unknown parameter {e}") from None
    except (ValueError, TypeError) as e:
        raise ValueError(f"suffix {suffix!r} could not be formatted: {e}") from None
    parent = Path(out_dir) if out_dir else model.parent
    return parent / f"{model.stem}{tail}.osim"


def backup(path: os.PathLike | str, tag: str = "model_edit") -> Optional[Path]:
    """Copy ``path`` beside itself under ``_backup_<tag>/`` before it is replaced.

    Returns the backup path, or None if there was nothing to back up. Deliberately
    a sibling folder rather than a ``.bak`` suffix: a stray ``*.osim.bak`` in an
    iteration folder gets picked up by the model globs in ``settings.py`` and
    ``change_moment_arms/cli.py``, and then shows up as a model you can run.
    """
    path = Path(path)
    if not path.exists():
        return None
    bdir = path.parent / f"_backup_{tag}"
    bdir.mkdir(parents=True, exist_ok=True)
    dst = bdir / path.name
    n = 1
    while dst.exists():
        dst = bdir / f"{path.stem}.{n}{path.suffix}"
        n += 1
    shutil.copy2(path, dst)
    return dst


def prepare_out(model: os.PathLike | str, out: Optional[os.PathLike | str],
                suffix: str, params: Dict[str, Any], *,
                out_dir: Optional[str] = None,
                overwrite: bool = False, tag: str = "model_edit") -> Path:
    """Resolve and validate the output path, creating its directory.

    Refuses two things on purpose:

    * writing on top of the input model. Editing in place makes a chain
      irreproducible and destroys the only copy of the thing you were comparing
      against; ``set_total_mass`` does this today and it is why an MRI model's
      mass history cannot be reconstructed.
    * silently replacing an existing different file. With ``overwrite=True`` the
      previous version is copied into ``_backup_<tag>/`` first, so re-running a
      recipe is safe but not lossy.
    """
    model = Path(model).resolve()
    out = Path(out).resolve() if out else derive_out(model, suffix, params,
                                                     out_dir).resolve()
    if out == model:
        raise ValueError(
            f"refusing to write over the input model ({model.name}). "
            f"Give a different out=, or an out_dir=.")
    if out.exists():
        if not overwrite:
            raise OutputExists(
                f"{out} already exists. Use --overwrite (or overwrite=True) "
                f"to replace it — the current file is copied into "
                f"_backup_{tag}/ first, so nothing is lost.")
        backup(out, tag)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
