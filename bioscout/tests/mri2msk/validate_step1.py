"""Compare the Python STAPLE port with MATLAB's preAligningToOpenSim.mat.

    python bioscout/tests/mri2msk/validate_step1.py ../MRI2MSK/exampleParticipant/stls
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # the bioscout checkout
from bioscout.model.mri2msk.pipeline import _find_one, load_prealignment, jcs_staple  # noqa: E402

stl_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "../MRI2MSK/exampleParticipant/stls")
ref = load_prealignment(stl_dir)
for key in ("pelvis", "femur_l", "femur_r", "tibia_l", "tibia_r"):
    if key == "pelvis":
        f, bone, side = _find_one(stl_dir, ["*pelvis*.stl"]), "pelvis", "l"
    else:
        bone, side = key.split("_")
        f = _find_one(stl_dir, [f"*{bone}_{side}*.stl", f"*{side}_{bone}*.stl"])
    t = time.time()
    o, V = jcs_staple(f, bone, side)
    r = ref[key]
    ang = [np.degrees(np.arccos(np.clip(V[:, i] @ r.rotation_matrix[:, i], -1, 1))) for i in range(3)]
    print(f"{key:8s} {time.time() - t:5.1f}s  origin diff {np.linalg.norm(o - r.origin_translation):7.3f} mm"
          f"  axis diff [deg] X {ang[0]:.3f}  Y {ang[1]:.3f}  Z {ang[2]:.3f}")
