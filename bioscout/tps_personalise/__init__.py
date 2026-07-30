"""
bioscout.tps_personalise
========================

Thin-plate-spline (TPS) personalisation of OpenSim musculoskeletal models from
segmented MRI bone geometry.

Originally a refactor of the notebook pipeline by Ekaterina Stansfield
(katya-stanzy/thin-plate-spline_personalised_muscoloskeletal_model), brought
into bioscout with three changes that make it usable across model families:

* **OpenSim 3.x and 4.x** ``.osim`` files are both read and written
  (``osim_format``). Rajagopal2015 as distributed is a Version 30000 document;
  the original only handled Version 40000+.
* **No third-party TPS dependency** — ``_tps_backend`` implements the same
  spline in numpy, used automatically when the ``thin-plate-spline`` package
  isn't installed.
* **Frame-compatibility checking** (``model_compat``) so one bone-landmark
  template can be reused across generic models *and fail loudly* when the
  frames don't actually match, rather than silently producing a wrong warp.

Importing this package has no side effects. Heavy dependencies (``opensim``,
``pyvista``) are imported lazily by the modules that need them, so this works
in a plain numpy/pandas environment — bone meshes simply aren't warped when
``pyvista`` is missing (logged, not fatal).

Typical use
-----------
Standalone::

    from bioscout.tps_personalise import PersonalisationConfig, Personaliser
    Personaliser(PersonalisationConfig.from_yaml("config.yaml")).run()

From a bioscout session::

    from bioscout.tps_personalise import personalise_iteration
    personalise_iteration("simulations/Athlete_03/25_03_31", "rajagopal",
                          mri_landmarks=".../landmarks.mrk.json")

Command line::

    python -m bioscout.tps_personalise --config config.yaml
"""
from __future__ import annotations

__version__ = "0.2.0"

# Light, side-effect-free public API. Heavy modules (axes, osim_model, pipeline)
# are importable directly but not eagerly loaded here, so this import stays
# cheap and dependency-light.
from .config import PersonalisationConfig, SubjectInfo  # noqa: F401
from .tps import OneBodyTPS  # noqa: F401
from .pipeline import Personaliser, PersonalisationResult  # noqa: F401
from .bioscout_adapter import personalise_iteration  # noqa: F401
from .model_compat import compare_bone_frames  # noqa: F401

__all__ = [
    "__version__",
    "PersonalisationConfig",
    "SubjectInfo",
    "OneBodyTPS",
    "Personaliser",
    "PersonalisationResult",
    "personalise_iteration",
    "compare_bone_frames",
]
