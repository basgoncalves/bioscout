# `bioscout.devtools.run_check`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py)

bioscout.devtools.run_check — the anti-silent-failure toolbox.

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

## Contents

- [`verify_run`](#verify_run) — Which requested stage actually produced output, per trial.
- [`format_report`](#format_report) — The trial × stage ok/MISS table, as printable lines.
- [`write_report`](#write_report) — ``run_report.json`` next to the log — machine-readable status is what makes a 29-subject batch auditable. Best-effort: reporting must never be the thing that fails the run.
- [`validate_emg_map`](#validate_emg_map) — Check session.yaml's ``emg_map`` keys against the labels that actually exist in the recorded EMG.
- [`duplicate_yaml_keys`](#duplicate_yaml_keys) — Duplicate keys within one mapping scope of a YAML document.
- [`long_paths`](#long_paths) — Existing paths under ``root`` whose length + ``headroom`` exceeds ``limit``. -> [(length, path)], longest first.

### `verify_run`

```python
verify_run(iteration_dir, trials, stages, experimental_dir=None)
```

| input | type | default |
|---|---|---|
| `iteration_dir` | – | required |
| `trials` | – | required |
| `stages` | – | required |
| `experimental_dir` | – | `None` |

Which requested stage actually produced output, per trial.

-> ``{"trials": {trial: {stage: bool}}, "missing": [(trial, stage)],  
      "ok": bool, "stages": [...]}``

Purely a filesystem check, run AFTER the stages: the run's own log says  
what was attempted, this says what exists. The difference between the two  
is exactly the class of failure that used to scroll past — an export that  
failed on every trial while the run ended "[settings] done".

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py#L45)</sub>

### `format_report`

```python
format_report(report)
```

| input | type | default |
|---|---|---|
| `report` | – | required |

The trial × stage ok/MISS table, as printable lines.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py#L74)</sub>

### `write_report`

```python
write_report(report, path)
```

| input | type | default |
|---|---|---|
| `report` | – | required |
| `path` | – | required |

``run_report.json`` next to the log — machine-readable status is what  
makes a 29-subject batch auditable. Best-effort: reporting must never be  
the thing that fails the run.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py#L89)</sub>

### `validate_emg_map`

```python
validate_emg_map(mapped_channels, analog_labels)
```

| input | type | default |
|---|---|---|
| `mapped_channels` | – | required |
| `analog_labels` | – | required |

Check session.yaml's ``emg_map`` keys against the labels that actually  
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

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py#L106)</sub>

### `duplicate_yaml_keys`

```python
duplicate_yaml_keys(text)
```

| input | type | default |
|---|---|---|
| `text` | – | required |

Duplicate keys within one mapping scope of a YAML document.

-> ``[(key, first_line_no, dup_line_no)]`` (1-based lines)

A text-level scan on purpose: by the time a YAML loader has run, the  
duplicate is GONE — ``yaml.safe_load`` keeps the last value without a  
word, which is precisely how ``Voltage_1:`` twice in a generated  
session.yaml cost a day. Scope = indentation level under the nearest  
shallower line, which is exact for the block-style files bioscout writes  
and conservative elsewhere (flow style is not scanned rather than  
guessed at).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py#L140)</sub>

### `long_paths`

```python
long_paths(root, limit=240, headroom=40)
```

| input | type | default |
|---|---|---|
| `root` | – | required |
| `limit` | – | `240` |
| `headroom` | – | `40` |

Existing paths under ``root`` whose length + ``headroom`` exceeds  
``limit``. -> [(length, path)], longest first.

``headroom`` stands in for what a run APPENDS below what exists now —  
``ceinms/Execution_a10_b1_g1000/MuscleForces.sto`` is 40+ characters on  
its own, which is why the failure only appears mid-run. 240 rather than  
260 because OpenSim's own temp names eat the rest.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/run_check.py#L190)</sub>
