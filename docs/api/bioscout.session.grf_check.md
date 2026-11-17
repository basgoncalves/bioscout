# `bioscout.session.grf_check`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/grf_check.py)

Audit each trial's force-plate -> foot assignment in GRF.xml.

  
**WHY THIS EXISTS**

``GRF.xml`` names which OpenSim body each force plate pushes on. It is written  
once by ``session export`` and then never revisited, so it silently goes stale  
in two ways:

* ``grf.mot`` is re-exported (new filtering, new plate set) and the XML still  
  describes the old force data;  
* the assignment logic itself is fixed -- as it was on 2026-08-12, when scoring  
  plates on the horizontal plane was found to collapse every plate onto ONE  
  foot -- and files written before the fix keep the wrong answer.

Either way the failure is quiet and expensive: a bilateral trial with both  
plates on ``calcn_l`` gives that leg the whole body weight and the other leg  
none, so its ID, SO and JRA are wrong while every file still looks valid. A  
static standing trial with both plates on one foot is the clearest tell.

This module re-derives the assignment from the CURRENT grf.mot + TRC and  
reports what would change. It is read-only unless ``write=True``.

## Contents

- [`read_assignment`](#read_assignment) — {plate_number: body_name} as the EXISTING GRF.xml has it, or {}.
- [`check_session`](#check_session) — Re-derive plate->foot for every trial under ``root``/simulations.

### `read_assignment`

```python
read_assignment(xml_path)
```

| input | type | default |
|---|---|---|
| `xml_path` | – | required |

{plate_number: body_name} as the EXISTING GRF.xml has it, or {}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/grf_check.py#L37)</sub>

### `check_session`

```python
check_session(root='.', subject='*', session='*', write=False, csv_path=None, log=print)
```

| input | type | default |
|---|---|---|
| `root` | – | `'.'` |
| `subject` | – | `'*'` |
| `session` | – | `'*'` |
| `write` | – | `False` |
| `csv_path` | – | `None` |
| `log` | – | `print` |

Re-derive plate->foot for every trial under ``root``/simulations.

Returns (rows, n_changed, n_onesided). ``write=True`` regenerates the  
GRF.xml of every trial whose assignment changed; nothing else is touched.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/grf_check.py#L55)</sub>
