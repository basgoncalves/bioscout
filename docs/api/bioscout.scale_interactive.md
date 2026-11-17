# `bioscout.scale_interactive`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py)

`bioscout scale` — scale a model by answering questions, no project needed.

    bioscout scale  
    bioscout scale --model generic.osim --static static.trc --mass 78.4  
    bioscout scale --dry-run          # decide everything, run nothing

Scaling fails in one of two ways, and only one of them is loud:

  * ScaleTool refuses — a missing file, a marker set naming a body the model  
    does not have. Annoying, but it tells you.  
  * ScaleTool succeeds on almost no measurements. An empty or near-empty  
    MeasurementSet scales every body by 1.0, so the output is generic geometry  
    wearing the subject's mass. Nothing downstream can tell, and joint moments  
    computed on it look perfectly reasonable.

The second is what this command exists to prevent. It reads the model, the  
marker set and the TRC, works out which measurements can actually be built,  
shows you that table BEFORE anything runs, and refuses if the segments that  
carry the joint moments are not measured.

Marker naming is the usual reason a measurement cannot be built: the defaults  
are the Vicon-CGM/powerlifting spellings, and a lab recording ``LSACR`` where  
those say ``LPSI``, or ``RLFC`` where they say ``RKNEL``, gets no hip or knee  
joint centre and therefore no femur or tibia scaling. Rather than carry a table  
of every lab's names, this asks — offering the markers your TRC actually  
contains, best guesses first. The answers are printed as a reusable alias map.

Nothing is written until you confirm the summary.

## Contents

- [`ask`](#ask) — One prompt. Empty input takes the default; Ctrl-C/EOF exits cleanly.
- [`pick`](#pick) — Numbered menu. Accepts the number, the value, 'o' for a free answer, or 's' to skip. Returns None when skipped.
- [`confirm`](#confirm) — 
- [`resolve_marker_names`](#resolve_marker_names) — Ask which of THIS lab's markers stand in for the ones the defaults name.
- [`floor_gaps`](#floor_gaps) — Which required groups the surviving measurements do not cover.
- [`run`](#run) — The `bioscout scale` command. Returns a process exit code.

### `ask`

```python
ask(prompt, default=None, choices=None)
```

| input | type | default |
|---|---|---|
| `prompt` | – | required |
| `default` | – | `None` |
| `choices` | – | `None` |

One prompt. Empty input takes the default; Ctrl-C/EOF exits cleanly.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py#L40)</sub>

### `pick`

```python
pick(prompt, options, default=None, allow_other=True, allow_skip=False)
```

| input | type | default |
|---|---|---|
| `prompt` | – | required |
| `options` | – | required |
| `default` | – | `None` |
| `allow_other` | – | `True` |
| `allow_skip` | – | `False` |

Numbered menu. Accepts the number, the value, 'o' for a free answer, or  
's' to skip. Returns None when skipped.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py#L60)</sub>

### `confirm`

```python
confirm(prompt, default=True)
```

| input | type | default |
|---|---|---|
| `prompt` | – | required |
| `default` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py#L94)</sub>

### `resolve_marker_names`

```python
resolve_marker_names(
    trc_markers,
    model_markers=None,
    interactive=True,
    aliases=None,
    log=print
)
```

| input | type | default |
|---|---|---|
| `trc_markers` | – | required |
| `model_markers` | – | `None` |
| `interactive` | – | `True` |
| `aliases` | – | `None` |
| `log` | – | `print` |

Ask which of THIS lab's markers stand in for the ones the defaults name.

Returns ``{expected: actual}`` for every expected marker that is missing and  
was answered. Only asks about markers that are genuinely absent, so a lab  
using the default names is never prompted at all.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py#L121)</sub>

### `floor_gaps`

```python
floor_gaps(kept)
```

| input | type | default |
|---|---|---|
| `kept` | – | required |

Which required groups the surviving measurements do not cover.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py#L167)</sub>

### `run`

```python
run(
    model=None,
    static=None,
    markerset=None,
    mass=None,
    out=None,
    aliases=None,
    dry_run=False,
    yes=False,
    linear=True,
    placer=True,
    grf=None
)
```

| input | type | default |
|---|---|---|
| `model` | – | `None` |
| `static` | – | `None` |
| `markerset` | – | `None` |
| `mass` | – | `None` |
| `out` | – | `None` |
| `aliases` | – | `None` |
| `dry_run` | – | `False` |
| `yes` | – | `False` |
| `linear` | – | `True` |
| `placer` | – | `True` |
| `grf` | – | `None` |

The `bioscout scale` command. Returns a process exit code.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/scale_interactive.py#L175)</sub>
