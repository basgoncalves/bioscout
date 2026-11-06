"""Compare automatic landmarks with manual Mesh Warper landmarks.

Maps the manual base landmarks onto the participant mesh with the automatic
registration and reports the distance to the manual participant landmarks.

    python bioscout/tests/mri2msk/validate_landmarks.py ../MRI2MSK/exampleParticipant ../BaseModel_Lernagopal
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # the bioscout checkout
from bioscout.model.mri2msk import geometry as geo, landmarks as lm  # noqa: E402
from bioscout.model.mri2msk.pipeline import _find_one  # noqa: E402

part = Path(sys.argv[1] if len(sys.argv) > 1 else "../MRI2MSK/exampleParticipant")
base = Path(sys.argv[2] if len(sys.argv) > 2 else "../BaseModel_Lernagopal")
for key in ("pelvis", "femur_l", "femur_r", "tibia_l", "tibia_r"):
    if key == "pelvis":
        bstl = _find_one(base, ["*pelvis*.stl"], exclude=None)
        pstl = _find_one(part / "stls", ["*pelvis*_resizedToOpenSim_inOpenSimCS.stl"], exclude=None)
    else:
        b, s = key.split("_")
        bstl = _find_one(base, [f"*{s}_{b}*.stl"], exclude=None)
        pstl = _find_one(part / "stls", [f"*{b}_{s}*_resizedToOpenSim_inOpenSimCS.stl"], exclude=None)
    lmd = part / "landmarks"
    base_csv = lmd / f"base_{key}.csv"
    man_csv = next((p for p in lmd.glob(f"*{key}.csv") if "base" not in p.name), None)
    if not (bstl and pstl and base_csv.is_file() and man_csv):
        print(f"{key}: missing files, skipped")
        continue
    t = time.time()
    _, bp = lm.read_landmarks_csv(base_csv)
    _, mp = lm.read_landmarks_csv(man_csv)
    bv, bf = geo.load_stl(bstl)
    pv, pf = geo.load_stl(pstl)
    auto = lm.snap_to_surface(lm.register(bv, bf, pv, pf)(bp), pv, pf)
    e = np.linalg.norm(auto - mp, axis=1) * 1000
    print(f"{key:8s} {time.time() - t:4.1f}s  n={len(e):2d}  error mean {e.mean():5.1f}  "
          f"median {np.median(e):5.1f}  max {e.max():5.1f} mm")
