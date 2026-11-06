"""Compare the Python Model Warper (step 5) with an OpenSim Creator warp.

    python bioscout/tests/mri2msk/validate_warp.py ../MRI2MSK/exampleParticipant \\
        BaseModelWithSkin/exampleParticipant_unscaled_withSkin_markersAdjusted.osim

Warps ``<participant>/<model>`` with ``<participant>/warp_setup.xml`` into a
temporary folder and compares markers, path points, offset frames, wrap
cylinders and mesh vertices with ``<participant>/warpedModel/warpedModel.osim``
and ``warpedModel/warpedGeometry/*.obj`` produced by OpenSim Creator.
"""
import collections
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # the bioscout checkout
from bioscout.model.mri2msk.model_warper import read_mesh, warp_model  # noqa: E402


def collect(f):
    root = ET.parse(f).getroot()
    out = {}

    def walk(el, path):
        nm = el.get("name")
        p = path + "/" + nm if nm else path
        for k in ("location", "translation", "radius", "xyz_body_rotation", "orientation"):
            c = el.find(k)
            if nm and c is not None and c.text and re.fullmatch(r"[\s\-\d.eE+]+", c.text):
                out[(el.tag, p, k)] = np.array(c.text.split(), float)
        for ch in el:
            walk(ch, p)

    walk(root, "")
    return out


part = Path(sys.argv[1] if len(sys.argv) > 1 else "../MRI2MSK/exampleParticipant")
model = part / (sys.argv[2] if len(sys.argv) > 2 else
                "BaseModelWithSkin/exampleParticipant_unscaled_withSkin_markersAdjusted.osim")
osc_model = part / "warpedModel" / "warpedModel.osim"
osc_geom = part / "warpedModel" / "warpedGeometry"
tmp = Path(tempfile.mkdtemp(prefix="mri2msk_warp_"))
py_model = warp_model(model, part / "warp_setup.xml", tmp / "warpedModel.osim", tmp / "warpedGeometry",
                      log=lambda *_: None)

a, b = collect(py_model), collect(osc_model)
stats = collections.defaultdict(list)
for k in a:
    if k in b and a[k].shape == b[k].shape:
        f = 180 / np.pi if k[2] in ("xyz_body_rotation", "orientation") else 1000
        stats[(k[0], k[2])].append(np.max(np.abs(a[k] - b[k])) * f)
print(f"{'element':26s} {'property':18s} {'n':>5s} {'max':>10s}")
for (tag, prop), v in sorted(stats.items()):
    unit = "deg" if prop in ("xyz_body_rotation", "orientation") else "mm"
    print(f"{tag:26s} {prop:18s} {len(v):5d} {max(v):10.5f} {unit}")
print("meshes:")
for f in sorted(osc_geom.glob("*.obj")):
    if "rotated" in f.name or not (tmp / "warpedGeometry" / f.name).is_file():
        continue
    Va, _ = read_mesh(tmp / "warpedGeometry" / f.name)
    Vb, _ = read_mesh(f)
    if Va.shape == Vb.shape:
        print(f"  {f.name:40s} max {np.linalg.norm(Va - Vb, axis=1).max() * 1000:.5f} mm")
    else:
        print(f"  {f.name:40s} vertex count differs ({len(Va)} vs {len(Vb)})")
