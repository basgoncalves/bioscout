# `bioscout.figures` — one catalogue for every plot

62 figures from the powerlifting scripts and from bioscout itself, registered in
one place with the inputs each one needs. **Nothing is re-implemented** — the
module finds the existing builder, asks for its inputs and calls it, so the
figures stay identical to what `results.py` / `manuscript.py` produce today.

## Run it standalone

```bash
python -m bioscout.figures                 # menu: pick numbers, keys or a group
python -m bioscout.figures --list          # just print the catalogue
python -m bioscout.figures p04 p07jcf      # run these two, prompt for inputs
python -m bioscout.figures master          # run a whole group
python -m bioscout.figures p04 --session Athlete_01_S1 --subject Athlete_01
python -m bioscout.figures --project C:/Users/Basilio/ucloud/Powerlifiting p01
```

At the menu you can type: `3`, `p04`, `master`, `all`, or any mix separated by
spaces. Every input a figure needs is then prompted with a default in brackets —
press Enter to take it. Trials and trial types are offered as a numbered list
built from the session on disk.

## Use it inside bioscout / a notebook

```python
from bioscout import figures

figures.list_figures()                     # or figures.catalog("master")
figures.run("p04")                         # prompts for the trial
figures.run("p04", trial="Squat_BW_01")    # nothing to prompt for
figures.run_many(["p01", "p05", "s_jcf_angle"])
figures.menu()                             # the interactive picker

ctx = figures.session_ctx()                # sess / S / L / trials / tasks
figures.master()                           # the master_*.csv dataframes
```

Rule: **anything you pass is used, anything you omit is asked for.** The same
registry therefore works scripted and by hand.

## Finding the powerlifting project

Project figures import `results.py` by path. The folder is resolved from, in
order: `--project` / `figures.project_dir(path)`, `$POWERLIFTING_DIR`,
`$BIOSCOUT_PROJECT_DIR`, `~/ucloud/Powerlifiting`, the known Windows path, then
the working directory. Set it once:

```bash
export POWERLIFTING_DIR=/c/Users/Basilio/ucloud/Powerlifiting   # bash
setx POWERLIFTING_DIR "C:\Users\Basilio\ucloud\Powerlifiting"   # cmd
```

The `ceinms` and `model` groups need **no** project — they only need a file path,
so they work against any session or any `.osim`.

## The groups

| group | what | source |
|---|---|---|
| `session` | per-session report figures 01–09 (markers, kinematics + moments, moment arms, muscle dynamics, muscle moments, trial-type averages, JRF) | `results.py` |
| `summary` | session / task / kinematics / JCF-compass / muscle-moment panels, poster, and `s_all` = the full `results.py` run | `results.py` |
| `calibration` | CEINMS calibration fit + MTU parameter panels | `calibration_figures.py` |
| `master` | cross-session figures: effect heatmap and dumbbell, peak JCF, factor effects, muscle ranking, work ranks, rank shift, model effects, error by model, curve overlays and diffs | `results.py` (reads `results/master_*.csv`) |
| `manuscript` | fig01 setup, fig05 metric summary, fig07 muscle forces, task panel, model overview, quick metric/curve plots | `manuscript.py` |
| `ceinms` | calibration loop, model parameters, uncalibrated vs calibrated, moment tracking, optimisation, EMG vs excitations, muscle forces | `bioscout.utils.ceinms.plot` |
| `model` | full model validation (moment arms + fibre + strength), isokinetic, moment-arm-over-motion wrap QC, JCF vs literature | `bioscout.muscle_inspect` |

## Notes

- The session context (`Session`, `Series`, `Legs`) is built once and reused, so
  running several `session`/`summary` figures in a row costs one load.
- `master` figures read `results/master_*.csv`. If they are missing or stale:
  `m_rescan` (or `python results.py --master`) rewrites them; `m_all` redraws
  every master figure from the CSVs already on disk in seconds.
- Output paths are unchanged — each builder still writes where it always did
  (`results/<subject>/<session>/…`, `results/master_figures/`, or the folder you
  give a `model`/`ceinms` figure).
- A figure that fails in `run_many` prints `[FAILED] <key>: <error>` and the rest
  keep going.

## Adding a figure

One line at the bottom of the relevant section in `figures.py`:

```python
_reg("m_new", "master", "what it shows",
     _m("fig_master_new_thing", "discrete"),
     [P("metric", "metric", "peak_JCF_BW")])
```

For a figure that needs the session context, take `c` as the first argument and
pass `ctx=True`:

```python
_reg("p10", "session", "what it shows",
     lambda c, trial: c.R.fig_10_thing(c.sess, c.S, trial), [TRIAL], ctx=True)
```

`P(name, prompt, default, kind, choices)` — `kind` is
`text|path|int|float|bool|list|opt` (`opt` means blank is allowed);
`choices` is a callable `(state) -> list` and gets `state["ctx"]` for
context figures, which is how the trial list is built.
