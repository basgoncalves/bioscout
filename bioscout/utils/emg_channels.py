"""Inspect a c3d's analog channels and write the emg_map for session.yaml.

    python -m bioscout.utils.emg_channels TRIAL.c3d              # the table
    python -m bioscout.utils.emg_channels TRIAL.c3d --yaml       # emg_map stub
    python -m bioscout.utils.emg_channels TRIAL.c3d --yaml -o emg_map.yaml

WHY THIS EXISTS
    `emg_map` is the only statement in a project of which analog channel is
    which muscle, and until now it was written by hand from a channel list
    nobody could see without opening the c3d in Vicon.

    That produced a silent, expensive failure, already documented in
    `exportC3D._resolve_emg_channels`: subject 022's c3d carries 32 channels
    containing the word "Voltage" -- 16 named ``Voltage_<n>-<MUSCLE>`` at
    0.4-3.4 V, which ARE the conditioned EMG, and 16 bare ``Voltage_<n>`` at
    0.01-0.04 V, which are unused inputs recording noise. A substring match on
    "Voltage" took all 32, and every EMG-informed result solved before it was
    caught had read the wrong columns.

    Nothing about that is visible in a filename. It IS visible in the
    amplitudes, which is why this prints them: the two populations differ by
    two orders of magnitude and the table separates instantly.

WHAT IT DOES NOT DO
    It does not guess which muscle a channel belongs to beyond reading the
    tag the operator typed into the c3d. An untagged channel is reported as
    untagged, not matched by position or by neighbour -- guessing that is how
    a muscle ends up driven by the channel next to it.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

#: `Voltage_3-VM` -> tag "VM". The tag is what the operator typed at capture,
#: so it is evidence; the bare stem is not.
_TAGGED = re.compile(r"^(?P<stem>.+?)[-_](?P<tag>[A-Za-z][A-Za-z0-9_]*)$")


def read_channels(c3d_path):
    """[(label, n, vmin, vmax, rms)] for every analog channel."""
    import warnings
    import numpy as np
    import c3d

    with open(c3d_path, "rb") as fh:
        reader = c3d.Reader(fh)
        labels = [str(l or "").strip() for l in reader.analog_labels]
        rows = []
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="No point data found",
                                    category=UserWarning)
            for _fno, _pts, analog in reader.read_frames():
                a = np.asarray(analog)
                if a.ndim == 2:
                    rows.append(a)
                else:
                    rows.append(a.reshape(-1, 1))
    if not rows:
        return [(l, 0, float("nan"), float("nan"), float("nan")) for l in labels]
    data = np.concatenate(rows, axis=1)                # (n_channels, n_samples)
    out = []
    for i, lab in enumerate(labels):
        v = np.asarray(data[i], dtype=float)
        v = v[np.isfinite(v)]
        if v.size == 0:
            out.append((lab, 0, float("nan"), float("nan"), float("nan")))
        else:
            out.append((lab, int(v.size), float(v.min()), float(v.max()),
                        float(np.sqrt(np.mean(v ** 2)))))
    return out


def classify(chans, emg_hint="voltage", quiet_ratio=10.0):
    """Split into (tagged, untagged, other) and mark the quiet ones.

    `quiet_ratio`: a channel whose RMS is this many times below the MEDIAN of
    the tagged channels is almost certainly an unused input. Relative, not an
    absolute threshold -- amplifier gain differs between labs, the two
    populations' SEPARATION does not.
    """
    import numpy as np
    hint = emg_hint.lower()
    cand = [c for c in chans if hint in c[0].lower()]
    other = [c for c in chans if hint not in c[0].lower()]
    tagged, untagged = [], []
    for c in cand:
        m = _TAGGED.match(c[0])
        # a trailing pure number is an index, not a muscle tag
        (tagged if (m and not m.group("tag").isdigit()) else untagged).append(c)
    ref = [c[4] for c in tagged if np.isfinite(c[4])]
    floor = (np.median(ref) / quiet_ratio) if ref else None
    return tagged, untagged, other, floor


def _fmt(chans, floor, note=""):
    lines = []
    for lab, n, lo, hi, rms in chans:
        flag = ""
        if floor is not None and rms == rms and rms < floor:
            flag = "  <- quiet, likely an unused input"
        lines.append(f"    {lab:<34}{n:>8}{lo:>10.4f}{hi:>10.4f}{rms:>10.4f}{flag}")
    return lines


def report(c3d_path, emg_hint="voltage"):
    chans = read_channels(c3d_path)
    tagged, untagged, other, floor = classify(chans, emg_hint)
    print(f"\n{os.path.basename(c3d_path)} — {len(chans)} analog channel(s)")
    hdr = f"    {'channel':<34}{'samples':>8}{'min':>10}{'max':>10}{'rms':>10}"
    if tagged:
        print(f"\n  TAGGED — a muscle name in the label. These are the EMG.")
        print(hdr)
        print("\n".join(_fmt(tagged, floor)))
    if untagged:
        print(f"\n  UNTAGGED — matched '{emg_hint}' but carry no muscle name.")
        print(hdr)
        print("\n".join(_fmt(untagged, floor)))
        if floor is not None:
            quiet = sum(1 for c in untagged if c[4] == c[4] and c[4] < floor)
            if quiet:
                print(f"\n    {quiet} of these are >{10:.0f}x quieter than the "
                      f"tagged channels.\n    That is the 022 signature: unused "
                      f"inputs recording noise. Do NOT map them.")
    if other:
        print(f"\n  OTHER — {len(other)} channel(s) not matching '{emg_hint}' "
              f"(force plates, sync, ...)")
    if not tagged and untagged:
        print("\n  NOTE no channel carries a muscle tag. The map has to be "
              "written\n  by hand from the lab's own record of the electrode "
              "placement —\n  this tool will not guess it from position.")
    return tagged, untagged


def to_yaml(tagged, indent="  "):
    """An emg_map stub keyed on the TAGGED channel names, muscles left blank."""
    lines = ["emg_map:"]
    for lab, _n, _lo, _hi, _rms in tagged:
        m = _TAGGED.match(lab)
        tag = m.group("tag") if m else ""
        lines.append(f"{indent}{lab}:            # {tag} — fill in the muscle(s)")
    lines.append("")
    lines.append("# Keys are the TAGGED channel names, verbatim. exportC3D matches")
    lines.append("# emg_map keys against the c3d's analog labels exactly (then")
    lines.append("# case-insensitively) and nothing fuzzier, so a shortened or")
    lines.append("# prettified key silently drops that channel.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("c3d")
    p.add_argument("--emg-hint", default="voltage",
                   help="substring that marks a candidate EMG channel")
    p.add_argument("--yaml", action="store_true", help="print an emg_map stub")
    p.add_argument("-o", "--out", default=None, help="write the stub to a file")
    a = p.parse_args(argv)
    if not os.path.isfile(a.c3d):
        sys.exit(f"no such c3d: {a.c3d}")
    tagged, _ = report(a.c3d, a.emg_hint)
    if a.yaml or a.out:
        body = to_yaml(tagged)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(body + "\n")
            print(f"\nwrote {a.out}")
        else:
            print("\n" + body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
