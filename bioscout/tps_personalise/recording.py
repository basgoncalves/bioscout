"""Write transformed geometry back to disk.

Refactor of ``ScaleAndRecordData``. Each record_* call writes one CSV (markers
in metres) or STL (surfaces). Changes:
  * no work in ``__init__`` — call :meth:`write_all` (or the individual methods)
    explicitly,
  * units conversion factor is a parameter, not a magic ``/1000``,
  * uses a context-local numpy print option instead of mutating global state.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd


@contextmanager
def _full_precision():
    saved = np.get_printoptions()
    np.set_printoptions(suppress=True, precision=17)
    try:
        yield
    finally:
        np.set_printoptions(**saved)


class GeometryWriter:
    """Persist transformed markers / muscle paths / wraps / surfaces for a body."""

    def __init__(self, body: str, output_dir: str | Path, to_metres: float = 1e-3):
        self.body = body
        self.output_dir = Path(output_dir)
        self.to_metres = to_metres
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _write_points(self, points, names, suffix: str) -> Optional[Path]:
        if points is None or len(points) == 0:
            return None
        rows = {
            "body": [self.body] * len(names),
            "name": list(names),
            "location": [np.asarray(p, float) * self.to_metres for p in points],
        }
        path = self.output_dir / f"{self.body}_{suffix}.csv"
        with _full_precision():
            pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def write_bone_markers(self, points, names) -> Optional[Path]:
        return self._write_points(points, names, "bone_markers")

    def write_skin_markers(self, points, names) -> Optional[Path]:
        return self._write_points(points, names, "skin_markers")

    def write_muscle_paths(self, points, names) -> Optional[Path]:
        return self._write_points(points, names, "muscle_paths")

    def write_wrap_translations(self, points, names) -> Optional[Path]:
        return self._write_points(points, names, "wrap_translations")

    def write_surfaces(self, surfaces, names: Sequence[str]) -> list[Path]:
        """Save each pyvista surface as STL (converted back to metres)."""
        import pyvista as pv  # lazy
        out = []
        for name, surf in zip(names, surfaces):
            mesh = pv.PolyData(np.asarray(surf.points) * self.to_metres, surf.faces)
            path = self.output_dir / f"{name}.stl"
            mesh.save(path)
            out.append(path)
        return out
