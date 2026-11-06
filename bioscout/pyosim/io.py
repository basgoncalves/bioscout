"""Read/write the OpenSim text formats IK and ID use (.trc, .mot/.sto)."""
import numpy as np


def read_trc(path):
    """-> times (n,), {marker: (n,3) in metres}, rate."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    keys = lines[1].split("\t"); vals = lines[2].split("\t")
    meta = dict(zip(keys, vals))
    units = (meta.get("Units") or "mm").strip().lower()
    scale = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}.get(units, 1e-3)
    names = [n for n in lines[3].split("\t")[2:] if n.strip()]
    rows = []
    for ln in lines[5:]:
        if not ln.strip():
            continue
        parts = ln.split("\t")
        rows.append([float(x) if x.strip() else np.nan for x in parts])
    width = 2 + 3 * len(names)
    A = np.array([r[:width] + [np.nan] * (width - len(r)) for r in rows])
    t = A[:, 1]
    mk = {n: A[:, 2 + 3 * i: 5 + 3 * i] * scale for i, n in enumerate(names)}
    return t, mk, float(meta.get("DataRate") or 1 / np.median(np.diff(t)))


def read_sto(path):
    """-> (column names, array). Works for .mot and .sto."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().lower() == "endheader")
    j = i + 1
    while not lines[j].strip():
        j += 1
    cols = [c.strip() for c in lines[j].split("\t")] if "\t" in lines[j] else lines[j].split()
    data = np.array([[float(x) for x in l.split()] for l in lines[j + 1:] if l.strip()])
    header = "\n".join(lines[:i])
    deg = "indegrees=yes" in header.replace(" ", "").lower()
    return cols, data, deg


def write_mot(path, cols, data, name="Coordinates", degrees=True):
    with open(path, "w", newline="\n") as f:
        f.write(f"{name}\nversion=1\nnRows={len(data)}\nnColumns={len(cols)}\n"
                f"inDegrees={'yes' if degrees else 'no'}\nendheader\n")
        f.write("\t".join(cols) + "\n")
        for r in data:
            f.write("\t".join(f"{v:.8f}" for v in r) + "\n")
