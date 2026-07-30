"""Subject-specific scaling helpers.

Ported from ``simFunctions.py`` and the ``ScalingDF`` class. The OpenSim-touching
functions import ``opensim`` lazily so this module is importable without it.

NOTE: BioScout already provides model-scaling utilities. When integrating, prefer
BioScout's versions and keep these only for the bone-dimension scaling-factor
table (``scaling_factors``), which is specific to the TPS workflow.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_RAS = ["r", "a", "s"]


# ---------------------------------------------------------------- OpenSim mass
def total_model_mass(model) -> float:
    """Sum of all body masses in an OpenSim model."""
    bodies = model.getBodySet()
    return sum(bodies.get(i).getMass() for i in range(bodies.getSize()))


def scale_optimal_force_handsfield(
    model_generic, model_scaled, height_generic: float, height_scaled: float
):
    """Scale muscle max isometric force by total-muscle-volume regression.

    Uses the Handsfield et al. (2014) total-muscle-volume regression
    ``Vtotal = 47 * mass * height + 1285`` and the original force-scale factor
    ``(Vtotal_scaled/Vtotal_generic) / (lmo_scaled/lmo_generic)``.
    Behaviour identical to the original ``scaleOptimalForceSubjectSpecific``.
    """
    mass_g = total_model_mass(model_generic)
    mass_s = total_model_mass(model_scaled)
    v_generic = 47 * mass_g * height_generic + 1285
    v_scaled = 47 * mass_s * height_scaled + 1285

    mus_g = model_generic.getMuscles()
    mus_s = model_scaled.getMuscles()
    for i in range(mus_g.getSize()):
        mg, ms = mus_g.get(i), mus_s.get(i)
        lmo_g = mg.getOptimalFiberLength()
        lmo_s = ms.getOptimalFiberLength()
        factor = (v_scaled / v_generic) / (lmo_s / lmo_g)
        ms.setMaxIsometricForce(factor * mg.getMaxIsometricForce())
    return model_scaled


def set_max_contraction_velocity(model, value: float):
    muscles = model.getMuscles()
    for i in range(muscles.getSize()):
        muscles.get(i).setMaxContractionVelocity(value)
    return model


# ------------------------------------------------------- bone-dimension factors
def scaling_factors(osim_df: pd.DataFrame, mri_df: pd.DataFrame) -> pd.DataFrame:
    """Per-segment dimension comparison (osim vs mri) and scale factors.

    Reproduces ``ScalingDF`` for pelvis/femur/tibia heights, widths and depths.
    Returns a DataFrame with columns ``osim``, ``mri``, ``factors``.
    """
    def dims(df: pd.DataFrame) -> dict[str, float]:
        def n(a, b):
            return float(np.linalg.norm(
                (df.loc[a, _RAS] - df.loc[b, _RAS]).to_numpy(dtype=float)
            ))

        def mid(a, b):
            return (df.loc[a, _RAS].to_numpy(float) + df.loc[b, _RAS].to_numpy(float)) * 0.5

        ischium = mid("isch_tuber_r", "isch_tuber_l")
        ilium = mid("ilium_r", "ilium_l")
        poster = mid("PSIS_r", "PSIS_l")
        anter = mid("ASIS_r", "ASIS_l")
        return {
            "pelvis_height": float(np.linalg.norm(ilium - ischium)),
            "pelvis_width": n("femur_l_center_in_pelvis", "femur_r_center_in_pelvis"),
            "pelvis_depth": float(np.linalg.norm(poster - anter)),
            "femur_r_length": n("femur_r_center", "knee_r_center_in_femur_r"),
            "femur_r_width": n("knee_r_med", "knee_r_lat"),
            "femur_l_length": n("femur_l_center", "knee_l_center_in_femur_l"),
            "femur_l_width": n("knee_l_med", "knee_l_lat"),
            "tibia_r_length": n("tibia_r_center", "ankle_r_center"),
            "tibia_r_width": n("tibia_r_med", "tibia_r_lat"),
            "tibia_l_length": n("tibia_l_center", "ankle_l_center"),
            "tibia_l_width": n("tibia_l_med", "tibia_l_lat"),
        }

    osim_dims = dims(osim_df)
    mri_dims = dims(mri_df)
    out = pd.DataFrame({"osim": osim_dims, "mri": mri_dims})
    out["factors"] = out["mri"] / out["osim"]
    return out
