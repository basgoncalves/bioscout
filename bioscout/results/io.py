"""Read an OpenSim / CEINMS storage file."""
from __future__ import annotations

import pandas as pd

__all__ = ["read_storage"]


def read_storage(path: str) -> pd.DataFrame:
    """OpenSim .sto/.mot (or CEINMS .sto) -> DataFrame with a ``time`` column,
    numeric, sorted, one row per time."""
    skip = 0
    with open(path, "r", errors="replace") as f:
        for i, line in enumerate(f):
            s = line.strip()
            if s.lower() == "endheader":
                skip = i + 1
                break
            if s.split("\t")[0].strip().lower() == "time" or \
               (s.split() and s.split()[0].lower() == "time"):
                skip = i
                break
            if i > 200:
                break
    df = pd.read_csv(path, sep="\t", skiprows=skip, engine="c")
    if df.shape[1] == 1:
        df = pd.read_csv(path, sep=r"\s+", skiprows=skip, engine="python")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    tcol = next((c for c in df.columns if c.lower() == "time"), df.columns[0])
    if tcol != "time":
        df = df.rename(columns={tcol: "time"})
    df = df.apply(pd.to_numeric, errors="coerce")
    return df.dropna(subset=["time"]).drop_duplicates("time").sort_values("time")
