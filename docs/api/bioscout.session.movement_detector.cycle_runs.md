# `bioscout.session.movement_detector.cycle_runs`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/cycle_runs.py)

cycle_runs — turn a multi-cycle capture into one runnable folder per cycle.

A capture is one recording; a CYCLE is one thing to simulate. FAIS 073's  
``walking1`` is 85 s, twelve walkways and forty-three gait cycles, and the  
whole pipeline below ``2_experimental`` — inverse dynamics, static  
optimisation, CEINMS — takes exactly one contiguous window with one  
plate-to-body mapping. It therefore cannot run on the capture. It can run on a  
cycle.

This module is the seam between the two. It reads the cycles  
:func:`bioscout.session.movement_detector.gait_cycles` found and writes, per cycle::

    3_iterations/<iteration>/<trial>_r7/  
        grf.mot     the capture's force, trimmed to this cycle  
        GRF.xml     ExternalLoads for THIS cycle's plate-to-foot mapping  
        cycle.yaml  what the folder is: window, leg, events, plates

  
**Why the force is rewritten rather than referenced**

Over a walkway every plate takes both feet, so "plate 2 is the left foot" is  
a statement about one footfall, not about a trial: on walking1 plate 2 carries  
four left and nine right footfalls. Worse, inside a single 1.1 s cycle a plate  
is hit by BOTH feet on 17 of the 43 cycles — the trailing foot is still  
rolling off as the leading foot lands — and no ExternalLoads file can say  
that, because ``applied_to_body`` is one body for the whole file.

The fix is to give such a plate two columns in this cycle's own ``grf.mot``,  
one per foot, each carrying the plate's force only over the frames that  
foot was on it and zero elsewhere. The mapping is then one plate-column to one  
body, which is what OpenSim can express, and nothing is invented: the split  
comes from the per-frame centre-of-pressure assignment  
:func:`bioscout.session.movement_detector.contact_feet` already makes.

## Contents

- [`write_cycle_files`](#write_cycle_files) — Write ``grf.mot`` + ``GRF.xml`` + ``cycle.yaml`` for ONE cycle.
- [`prepare_cycle_runs`](#prepare_cycle_runs) — One run folder per gait cycle of ``exp_dir``, under ``out_root``.

### `write_cycle_files`

```python
write_cycle_files(
    exp_dir: str,
    out_dir: str,
    cycle: dict,
    contacts: Optional[List[dict]] = None,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None,
    pad_s: float = DEFAULT_PAD_S,
    right_foot_body: str = 'calcn_r',
    left_foot_body: str = 'calcn_l',
    lowpass_cutoff: float = 6.0
) -> Dict[str, str]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `out_dir` | str | required |
| `cycle` | dict | required |
| `contacts` | Optional[List[dict]] | `None` |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |
| `pad_s` | float | `DEFAULT_PAD_S` |
| `right_foot_body` | str | `'calcn_r'` |
| `left_foot_body` | str | `'calcn_l'` |
| `lowpass_cutoff` | float | `6.0` |

**returns** `Dict[str, str]`

Write ``grf.mot`` + ``GRF.xml`` + ``cycle.yaml`` for ONE cycle.

Returns ``{"dir", "grf_mot", "grf_xml", "cycle_yaml"}``. The plate-to-foot  
mapping is decided inside the cycle's own window and nowhere else.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/cycle_runs.py#L73)</sub>

### `prepare_cycle_runs`

```python
prepare_cycle_runs(
    exp_dir: str,
    out_root: str,
    body_mass: Optional[float] = None,
    cfg: Optional[MocapConfig] = None,
    cycles: Optional[List[dict]] = None,
    pad_s: float = DEFAULT_PAD_S,
    quiet: bool = False,
    **kw
) -> List[dict]
```

| input | type | default |
|---|---|---|
| `exp_dir` | str | required |
| `out_root` | str | required |
| `body_mass` | Optional[float] | `None` |
| `cfg` | Optional[MocapConfig] | `None` |
| `cycles` | Optional[List[dict]] | `None` |
| `pad_s` | float | `DEFAULT_PAD_S` |
| `quiet` | bool | `False` |
| `**kw` | – | – |

**returns** `List[dict]`

One run folder per gait cycle of ``exp_dir``, under ``out_root``.

    prepare_cycle_runs("…/2_experimental/walking1",  
                       "…/3_iterations/rajagopal_fai")  
    # -> …/3_iterations/rajagopal_fai/walking1_l1/{grf.mot,GRF.xml,cycle.yaml}

Returns one dict per cycle written; a cycle that cannot be written (no  
plate under either foot in its window) is reported and skipped rather than  
written wrong.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/cycle_runs.py#L242)</sub>
