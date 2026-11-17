# `bioscout.session.movement_detector.session`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/session.py)

Run movement detection over a whole exported session.

One implementation, two callers: ``bioscout --classifier <session>`` and a  
project pipeline that sets ``DO_DETECT``. They used to be the same code copied  
twice, which is the sort of thing that agrees on the day it is written and  
disagrees three commits later.

## Contents

- [`classify_session`](#classify_session) — Classify every trial in ``session_path`` and write the outputs.

### `classify_session`

```python
classify_session(
    session_path: str,
    settings=None,
    no_plots: bool = False,
    write_session_yaml: bool = False,
    per_trial: bool = True,
    quiet: bool = False,
    trials=None,
    verbose: bool = False
)
```

| input | type | default |
|---|---|---|
| `session_path` | str | required |
| `settings` | – | `None` |
| `no_plots` | bool | `False` |
| `write_session_yaml` | bool | `False` |
| `per_trial` | bool | `True` |
| `quiet` | bool | `False` |
| `trials` | – | `None` |
| `verbose` | bool | `False` |

Classify every trial in ``session_path`` and write the outputs.

Per trial, beside the data it describes (``per_trial``, the default) —  
this is what the c3d export produces, so the detection travels with the  
trial and not in a folder somewhere else:

* ``2_experimental/<trial>/movement_detection.yaml`` — type, confidence,  
  reason, time_range, side and the task/phase breakdown for that trial  
* ``2_experimental/<trial>/movement_detection.png`` — its QC figure

And once, beside the session:

* ``movement_detection/movement_detection.yaml`` — every trial's  
  detection and its ``valid`` flag in one file; never read by the  
  pipeline and never overwriting ``session.yaml``  
* ``movement_detection/trials_valid.csv`` — trial, valid, reason  
* ``movement_detection/classification.csv`` — one row per trial, the  
  only cross-trial view (which is why it stays session-level)  
* ``movement_detection/plots/<trial>.png`` — the old figure location,  
  written only when ``per_trial=False``; the figures are not duplicated.

``settings`` is a project's ``BatchSettings`` (or anything with the same  
attribute names); it supplies the lab conventions — marker names and TRC  
axes. When omitted, the function looks for a ``settings.py`` above the  
session and falls back to the conventional defaults.

``write_session_yaml`` corrects ``session.yaml``'s trial types and time  
ranges from the detection and adds a ``valid`` tag per trial, backing the  
old file up first. A trial detected as "unknown" keeps its type. ``quiet`` trims the per-trial  
chatter to one summary line — the export already prints a line per trial.

``trials`` re-detects only the named trials. Every other trial keeps the  
result it already has, read back from its own  
``movement_detection.yaml``, so the session-level files stay complete and  
a one-trial re-run costs one trial's work instead of the session's. Re-run  
one capture after changing a threshold, or after fixing the marker set,  
without waiting for the sixty that did not change.

Returns the detection dict, or None when the session could not be read.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/session.py#L182)</sub>
