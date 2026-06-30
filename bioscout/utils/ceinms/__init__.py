# CEINMS executables and DLLs — this directory holds the binary files.
#
# There is also a sibling module ``utils/ceinms.py`` with the Python CEINMS
# helpers (create_input_data, create_ceinms_cfg, create_ceinms_model, calibrate,
# …). Because a *package* shadows a same-named *module* on import, anything that
# ends up doing ``import ceinms`` (directly or indirectly) resolves to THIS
# package and would be missing those helpers — which is exactly what produced
# errors like ``module 'ceinms' has no attribute 'create_input_data'``.
#
# To make the package and the .py interchangeable, load the sibling .py by file
# path and re-export its public names here. Whichever object callers reach as
# ``ceinms``, the helpers are present. The load is degrade-safe: if OpenSim
# isn't importable (the .py imports it at module top), the package falls back to
# binary-only rather than failing the import.
import os as _os
import importlib.util as _ilu

_impl_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "ceinms.py")
try:
    _spec = _ilu.spec_from_file_location("bioscout.utils._ceinms_impl", _impl_path)
    _impl = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_impl)
    for _name in dir(_impl):
        if not _name.startswith("_"):
            globals()[_name] = getattr(_impl, _name)
    del _name
    HAS_CEINMS_HELPERS = True
except Exception as _exc:  # OpenSim missing, etc. — keep package usable for its exes
    HAS_CEINMS_HELPERS = False
    print(f"[bioscout.utils.ceinms] Python helpers unavailable ({_exc}); binary package only.")
