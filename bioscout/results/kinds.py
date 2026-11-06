"""Which result files exist, and what each one is called.

One ordered rule list maps a file (its path relative to the trial folder) to a
*variable* name. The first matching rule wins; a rule whose name is ``None``
marks files that are never results (setups, marker locations, .trc).

Add an output to every loader, plot and export with one call::

    from bioscout.results import register_file
    register_file("rra_kinematics", r"residual_reduction/.*_Kinematics_q\\.sto$",
                  unit="deg", aliases=("rra",), description="RRA-adjusted kinematics")
"""
from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

__all__ = ["FileKind", "FILES", "register_file", "variable_for", "resolve", "describe"]


@dataclass
class FileKind:
    name: Optional[str]            # variable name; "{1}" = first regex group; None = ignore
    pattern: str                   # regex searched in the posix path relative to the trial
    unit: str = ""
    description: str = ""
    aliases: Tuple[str, ...] = ()
    rx: "re.Pattern" = field(init=False, repr=False)

    def __post_init__(self):
        self.rx = re.compile(self.pattern)

    @property
    def group(self) -> Optional[str]:
        """Name without the per-file part: 'moment_arms/{1}' -> 'moment_arms'."""
        return None if self.name is None else self.name.split("/")[0].replace("_{1}", "")


#: ordered: the first match wins
FILES: List[FileKind] = []


def register_file(name, pattern, *, unit="", description="", aliases=(), first=False):
    """Add a file kind. ``first=True`` puts it ahead of the built-ins (use it to
    override how an existing file is named)."""
    k = FileKind(name, pattern, unit, description, tuple(aliases))
    FILES.insert(0, k) if first else _insert_before_fallbacks(k)
    return k


def _insert_before_fallbacks(k):
    # the generic MuscleAnalysis / CEINMS catch-alls must stay last
    i = next((n for n, f in enumerate(FILES) if getattr(f, "_fallback", False)), len(FILES))
    FILES.insert(i, k)


def _fallback(name, pattern, **kw):
    k = register_file(name, pattern, **kw)
    k._fallback = True
    return k


# ---------------------------------------------------------------- built-ins --- #
for _p in (r"(^|/)_ik_", r"(^|/)setup_", r"\.trc$", r"(^|/)ceinms_calibration/"):
    register_file(None, _p)

# experimental (model-independent; iteration is "")
register_file("emg", r"^emg_filtered_normalised\.mot$", unit="-",
              description="filtered, normalised EMG envelopes")
register_file("emg_raw", r"^emg\.mot$", unit="V", description="EMG as exported from the c3d")
register_file("grf", r"^grf\.mot$", unit="N",
              description="ground reaction forces, COPs and free moments per plate")
register_file("invivo_jcf", r"^invivo_jcf\.mot$", unit="N",
              description="measured (instrumented implant) joint contact forces")
# external biomechanics
register_file("joint_angles", r"external_biomechanics/joint_angles\.mot$", unit="deg",
              aliases=("ik",), description="inverse kinematics (deg / m)")
register_file("joint_moments", r"external_biomechanics/inverse_dynamics\.sto$", unit="Nm",
              aliases=("id",), description="inverse dynamics (N*m / N)")
# static optimisation
register_file("muscle_forces_so", r"static_optimisation/StaticOptimization_force\.sto$",
              unit="N", aliases=("so_forces",), description="static optimisation muscle forces")
register_file("muscle_activations_so",
              r"static_optimisation/StaticOptimization_activation\.sto$", unit="-",
              aliases=("so_activations",), description="static optimisation activations")
# joint reaction analysis
register_file("joint_contact_forces_{1}", r"joint_contact_forces/output_(\w+)\.sto$",
              unit="N", aliases=("jcf",), description="joint contact forces (JRA)")
register_file("jcf_contributions_{1}", r"contributions_(\w+)\.sto$", unit="N",
              description="per-muscle contributions to joint contact force")
# muscle analysis
register_file("moment_arms/{1}", r"_MuscleAnalysis_MomentArm_(\w+)\.sto$", unit="m",
              description="muscle moment arms, one file per coordinate")
register_file("muscle_moments_ma/{1}", r"_MuscleAnalysis_Moment_(\w+)\.sto$", unit="Nm",
              description="MuscleAnalysis moments, one file per coordinate")
register_file("muscle_moments_so/{1}", r"_MuscleMoments_(\w+)_so\.sto$", unit="Nm",
              description="muscle moments from SO forces, one file per coordinate")
register_file("muscle_moments_ceinms/{1}", r"_MuscleMoments_(\w+)_ceinms\.sto$", unit="Nm",
              description="muscle moments from CEINMS forces, one file per coordinate")
register_file("muscle_tendon_lengths", r"_MuscleAnalysis_Length\.sto$", unit="m",
              aliases=("lengths",), description="musculotendon lengths")
# CEINMS (the newest Execution_* only -- see scan._newest_execution)
register_file("muscle_forces_ceinms", r"ceinms/.*MuscleForces\.sto$", unit="N",
              aliases=("ceinms_forces",), description="CEINMS muscle forces")
register_file("muscle_activations_ceinms", r"ceinms/.*Activations\.sto$", unit="-",
              aliases=("ceinms_activations",), description="CEINMS activations")
# catch-alls, always last
_fallback("ma_{1}", r"_MuscleAnalysis_(\w+)\.sto$", description="other MuscleAnalysis outputs")
_fallback("ceinms_{1}", r"ceinms/.*/(\w+)\.sto$", description="other CEINMS outputs")

# names that are only ever exported when asked for (raw EMG is huge)
OPT_IN = {"emg_raw"}


# ------------------------------------------------------------------ naming --- #
def _snake(s: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    return re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()


def match(rel: str) -> Tuple[Optional[str], Optional[FileKind]]:
    """``(variable, kind)`` for a file at ``rel`` (posix, relative to the trial).
    Unknown .sto/.mot files get ``<folder>_<stem>`` and no kind."""
    if not rel.lower().endswith((".sto", ".mot")):
        return None, None
    for k in FILES:
        m = k.rx.search(rel)
        if m:
            if k.name is None:
                return None, k
            var = k.name
            if "{1}" in var:
                g = m.group(1)
                var = var.replace("{1}", g if "/" in var else _snake(g))
            return var, k
    parent = os.path.basename(os.path.dirname(rel))
    stem = os.path.splitext(os.path.basename(rel))[0]
    return _snake(f"{parent}_{stem}" if parent else stem), None


def variable_for(rel: str) -> Optional[str]:
    return match(rel)[0]


#: aliases for single members of a per-file family
EXTRA_ALIASES = {"jcf_so": "joint_contact_forces_so",
                 "jcf_ceinms": "joint_contact_forces_ceinms"}


def _alias_map() -> Dict[str, str]:
    out = dict(EXTRA_ALIASES)
    for k in FILES:
        if k.name:
            for a in k.aliases:
                out[a] = k.name.replace("_{1}", "_*").replace("{1}", "*")
    return out


def resolve(requested) -> Optional[List[str]]:
    """User names -> glob patterns on variable names. Accepts a variable
    ('muscle_forces_so'), an alias ('so_forces', 'ik', 'jcf'), a group
    ('moment_arms' = every coordinate) or a glob ('joint_*')."""
    if requested is None:
        return None
    if isinstance(requested, str):
        requested = [r.strip() for r in requested.split(",") if r.strip()]
    al = _alias_map()
    out = []
    for r in requested:
        r = al.get(r, r)
        out += [r, r + "/*"]                    # a group selects all its members
    return out


def canonical(name: str) -> str:
    """'so_forces' -> 'muscle_forces_so'; unknown names come back unchanged."""
    return _alias_map().get(name, name)


def wanted(var: str, patterns: Optional[List[str]]) -> bool:
    if not patterns:
        return var not in OPT_IN
    return any(fnmatch.fnmatchcase(var, p) for p in patterns)


def describe() -> pd.DataFrame:
    """The registry as a table (what ``session.results.files`` shows)."""
    return pd.DataFrame([dict(name=k.name.replace("{1}", "<x>"), aliases=", ".join(k.aliases),
                              unit=k.unit, description=k.description, pattern=k.pattern)
                         for k in FILES if k.name])


def kind_of(var: str) -> Optional[FileKind]:
    for k in FILES:
        if k.name and fnmatch.fnmatchcase(var, k.name.replace("{1}", "*")):
            return k
    return None
