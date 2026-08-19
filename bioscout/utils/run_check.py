"""bioscout.utils.run_check — the anti-silent-failure toolbox.

Every function here exists because of a failure that produced NO error — the
worst kind, catalogued in ``docs/IMPLEMENTATIONS.md`` §1 "Silent-failure
traps". A run that ended ``[settings] done`` with every export failed; CEINMS
calibrated on the wrong EMG columns without a warning; a generated
session.yaml with ``Voltage_1:`` twice, YAML keeping whichever came last; a
path five characters over MAX_PATH surfacing as "file not found" deep inside
OpenSim, hours in.

The common shape of the fix is the same each time: **check the contract at the
boundary and be loud** — raise where the result would be wrong, print a table
where the result is missing.

Standard library only. This module must be importable anywhere a run report
needs READING — a CI runner, a collaborator's laptop, the bridge VM — so it
depends on nothing scientific.
"""
from __future__ import annotations

import glob
import json
import os

# --------------------------------------------------------------------------
# 1. Stage output verification — "missing outputs do not fail the run"
# --------------------------------------------------------------------------
#: What each stage is expected to leave behind, per trial. Glob patterns
#: relative to the trial's folder inside the iteration (except ``export``,
#: which is checked against the session's experimental folder — it is the
#: stage that CREATES those inputs). A stage "produced" a trial when EVERY
#: pattern for it matches at least one file.
STAGE_OUTPUTS = {
    "export": ("marker_experimental.trc",),
    "exbiomec": (os.path.join("external_biomechanics", "joint_angles.mot"),),
    "muscle_analysis": (os.path.join("muscle_analysis",
                                     "_MuscleAnalysis_Length.sto"),),
    "so": (os.path.join("static_optimisation", "*force.sto"),),
    "ceinms": (os.path.join("ceinms", "Execution_*", "MuscleForces.sto"),),
}


def verify_run(iteration_dir, trials, stages, experimental_dir=None):
    """Which requested stage actually produced output, per trial.

    -> ``{"trials": {trial: {stage: bool}}, "missing": [(trial, stage)],
          "ok": bool, "stages": [...]}``

    Purely a filesystem check, run AFTER the stages: the run's own log says
    what was attempted, this says what exists. The difference between the two
    is exactly the class of failure that used to scroll past — an export that
    failed on every trial while the run ended "[settings] done".
    """
    stages = [s for s in stages if s in STAGE_OUTPUTS]
    report = {"trials": {}, "missing": [], "stages": stages, "ok": True}
    for tn in trials:
        row = {}
        for st in stages:
            base = (os.path.join(str(experimental_dir), tn)
                    if st == "export" and experimental_dir
                    else os.path.join(str(iteration_dir), tn))
            ok = all(glob.glob(os.path.join(base, pat))
                     for pat in STAGE_OUTPUTS[st])
            row[st] = ok
            if not ok:
                report["missing"].append((tn, st))
                report["ok"] = False
        report["trials"][tn] = row
    return report


def format_report(report):
    """The trial × stage ok/MISS table, as printable lines."""
    stages = report["stages"]
    if not stages or not report["trials"]:
        return ["  (nothing to verify)"]
    w = max([len(t) for t in report["trials"]] + [6]) + 2
    lines = ["  " + " " * w + "  ".join(f"{s[:12]:>12}" for s in stages)]
    for tn, row in report["trials"].items():
        cells = "  ".join(f"{('ok' if row[s] else 'MISS'):>12}" for s in stages)
        lines.append(f"  {tn:<{w}}{cells}")
    n = len(report["missing"])
    lines.append(f"  -> {'ALL STAGES PRODUCED OUTPUT' if not n else str(n) + ' MISSING stage output(s) — the run is NOT complete'}")
    return lines


def write_report(report, path):
    """``run_report.json`` next to the log — machine-readable status is what
    makes a 29-subject batch auditable. Best-effort: reporting must never be
    the thing that fails the run."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"ok": report["ok"], "stages": report["stages"],
                       "missing": [list(m) for m in report["missing"]],
                       "trials": report["trials"]}, fh, indent=1)
        return path
    except Exception:                                          # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# 2. EMG map validation — "CEINMS ran on the wrong columns, silently"
# --------------------------------------------------------------------------
def validate_emg_map(mapped_channels, analog_labels):
    """Check session.yaml's ``emg_map`` keys against the labels that actually
    exist in the recorded EMG.

    -> ``{"missing": [...], "suspicious": [(mapped, better)], "ok": bool}``

    ``missing``    mapped channels that exist in NO trial's EMG — normalising
                   or calibrating on these is impossible; the caller should
                   REFUSE, not degrade.
    ``suspicious`` the FAIS trap: rigs export each electrode twice, a bare
                   ``Voltage_1`` and a tagged ``Voltage_1-VM`` (the
                   conditioned signal). Both exist, so a map keyed on the bare
                   name validates — and CEINMS then calibrates on the raw
                   column with no warning. Flagged, never auto-fixed: which
                   one is right is a statement about the rig, not the code.
    """
    labels = {str(x) for x in analog_labels}
    mapped = [str(m) for m in mapped_channels]
    missing = sorted(m for m in mapped if m not in labels)
    suspicious = []
    for m in mapped:
        if m not in labels:
            continue
        for lab in labels:
            if lab != m and lab.startswith(m) and len(lab) > len(m) \
                    and lab[len(m)] in "-_.":
                suspicious.append((m, lab))
    return {"missing": missing, "suspicious": sorted(set(suspicious)),
            "ok": not missing}


# --------------------------------------------------------------------------
# 3. Duplicate YAML keys — "YAML silently keeps the last one"
# --------------------------------------------------------------------------
def duplicate_yaml_keys(text):
    """Duplicate keys within one mapping scope of a YAML document.

    -> ``[(key, first_line_no, dup_line_no)]`` (1-based lines)

    A text-level scan on purpose: by the time a YAML loader has run, the
    duplicate is GONE — ``yaml.safe_load`` keeps the last value without a
    word, which is precisely how ``Voltage_1:`` twice in a generated
    session.yaml cost a day. Scope = indentation level under the nearest
    shallower line, which is exact for the block-style files bioscout writes
    and conservative elsewhere (flow style is not scanned rather than
    guessed at).
    """
    dups = []
    # stack of (indent, {key: line_no}) for the open mapping scopes
    stack = [(-1, {})]
    for i, raw in enumerate(str(text).splitlines(), 1):
        line = raw.rstrip()
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        if stripped.startswith("- "):
            # a sequence item opens a fresh scope for its inline mapping
            stack = [s for s in stack if s[0] < indent] + [(indent, {})]
            stripped = stripped[2:].lstrip()
            indent += 2
        # key: (block mapping entry; ignore flow style and plain scalars)
        head = stripped.split("#", 1)[0]
        if ":" not in head:
            continue
        key = head.split(":", 1)[0].strip()
        if not key:
            continue
        # close scopes deeper than or equal to a shallower sibling
        while stack and stack[-1][0] > indent:
            stack.pop()
        if not stack or stack[-1][0] < indent:
            stack.append((indent, {}))
        seen = stack[-1][1]
        if key in seen:
            dups.append((key, seen[key], i))
        else:
            seen[key] = i
    return dups


# --------------------------------------------------------------------------
# 4. Path length — MAX_PATH failures "deep inside OpenSim, hours in"
# --------------------------------------------------------------------------
def long_paths(root, limit=240, headroom=40):
    """Existing paths under ``root`` whose length + ``headroom`` exceeds
    ``limit``. -> [(length, path)], longest first.

    ``headroom`` stands in for what a run APPENDS below what exists now —
    ``ceinms/Execution_a10_b1_g1000/MuscleForces.sto`` is 40+ characters on
    its own, which is why the failure only appears mid-run. 240 rather than
    260 because OpenSim's own temp names eat the rest."""
    hits = []
    root = os.path.abspath(str(root))
    for dirpath, _dirs, files in os.walk(root):
        for name in files + [""]:
            p = os.path.join(dirpath, name) if name else dirpath
            if len(p) + headroom > limit:
                hits.append((len(p), p))
    hits.sort(reverse=True)
    return hits[:20]


__all__ = ["STAGE_OUTPUTS", "verify_run", "format_report", "write_report",
           "validate_emg_map", "duplicate_yaml_keys", "long_paths"]
