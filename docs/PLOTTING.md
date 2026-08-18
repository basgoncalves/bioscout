# Plotting — `bioscout.plot`

One comparison figure, driven by one table, configured at run time.

```python
import bioscout as bs

(bs.plot("results/master_results.csv")
   .where(Variable="muscle_work_total", Algo="SO")
   .compare("Condition", order=["pre-fatigue", "post-fatigue"])
   .facet("Task", icons=TASK_ICONS)
   .group(bs.plot.MUSCLE_GROUPS)
   .top(8)
   .title("total muscle work ranks")
   .save("results/group/work_ranks.png"))
```

## Why it exists

The ranked muscle-work figure had been written three times, in three projects,
each time from scratch:

| project | columns | rows |
|---|---|---|
| Powerlifting `results.py:fig_muscle_work_ranks` | generic models | algorithm |
| FAIS `figure_muscle_work.py` | task | pre-/post-fatigue |
| FAIS `results.py:fig_work_rank` | pre-/post-fatigue | task |

The drawing was never the difficult part — the three versions differ only in
**what the columns are**. So the columns and rows became arguments. Swap
`.compare("Condition")` for `.compare("Algo")` and the same table answers "does
static optimisation reorder the leg" instead of "does fatigue".

## The three layers

```
bioscout.plot.work      .sto files  ->  work in joules      work_table()
bioscout.plot.tidy      numbers     ->  one long table      read(), from_mapping()
bioscout.plot.compare   table       ->  a figure            Compare
```

The **middle layer is the contract**. A bioscout session goes through all
three. A project whose numbers came from somewhere else builds the table itself
and uses only the last one. Nothing in the drawing code knows what a session
is, and nothing knows what fatigue is.

### The table

One row per number. `Value` holds it; every other column is a key that
describes it:

```
Subject Session Iteration Trial Task Condition Fatigue Side Algo Model
Variable Channel Metric  Value
```

None of the keys are required and none are special-cased — you name the column
to compare across and the column to facet by, and any column present can play
either role. `Variable`/`Metric` is the convention for *which quantity is this*
(`muscle_work_total` / `work_J`), so one table can hold every figure's inputs.
FAIS's `results/master_results.csv` and Powerlifting's `master_discrete.csv`
are already exactly this shape and drop straight in.

Add an `x` column (`Percent`, `Time`) and each row becomes a sample of a curve
instead of a summary number — the same selection then feeds `.curves()`.

## Reading a rank figure

Bar colour is the item's rank in the **first** compared column, carried into
every column to its right. The left panel is therefore always a clean
dark-to-pale ramp *by construction*, so any colour disorder further right **is**
a re-ranking — no tracing of lines needed.

- `style="delta"` (default) — ▲/▼ after the label, places gained/lost
- `style="connector"` — the Collings et al. (2025) arrows
- `style="both"`

Normalisation is the other decision worth making on purpose:

- `normalise="reference"` (default) — every panel in a row is scaled to the
  **first column's** leader. A panel that shrank did less work, and a bar may
  legitimately pass 100 %.
- `normalise="panel"` — each panel scaled to its own leader. A pure ranking
  with the magnitudes thrown away. Sometimes what you want; never what you want
  by accident.

## Settings live in bioscout, not in your project

There is no figure config file to copy into a project. The defaults are in
`bioscout/plot/config.py`, and a script or notebook overrides what it cares
about:

```python
bs.plot.configure(dpi=300, top=10, cmap="viridis")     # for this process

with bs.plot.using(dpi=600, save_pdf=True):            # for one export
    fig.save("results/figure_3.png")

.set(panel_w_in=4.2, fs_label=11)                      # for one figure
```

Precedence: defaults → `configure()` → per-call keywords. An unknown setting
name raises; a silently ignored `dpi=600` is a figure that went to a journal at
200 dpi.

## Muscle work

```python
rows = bs.plot.work_table([
    {"Task": "run", "Condition": "pre", "Trial": "RunL1",
     "force":  ".../static_optimisation/SO_StaticOptimization_force.sto",
     "length": ".../muscle_analysis/_MuscleAnalysis_Length.sto"},
    ...
], phase="total")
```

`W = ∫ F·v dt`, with `v` the negated derivative of muscle–tendon length. That
length comes from the kinematics alone, so it is identical for every algorithm
run on the same trial — the algorithms differ only in the force, which is
exactly the comparison worth making.

Four phases, and the phase goes into the table (`Variable =
"muscle_work_<phase>"`) rather than being left to memory, because they rank
muscles differently:

| phase | integral | |
|---|---|---|
| `total` | `∫\|F·v\| dt` | concentric + eccentric — the default |
| `concentric` | `∫ F·v dt`, `v > 0` | |
| `eccentric` | `∫ F\|v\| dt`, `v < 0` | |
| `net` | `∫ F·v dt` | signed; the other three are its parts |

For a bioscout session, `session_records()` walks the trials and
`trial_inputs()` finds the two .sto files; a project supplies a
`label=lambda trial: {...}` callable to say which task and condition a trial
name means. That callable is the only project-specific thing in the path, and
it stays in the project.

Everything here reads .sto as plain text — no OpenSim, no scipy — so it runs on
a bare checkout and in CI.

## Relationship to the other figure code

- `bioscout.utils.collings` keeps the **fixed published layout**
  (`rank_shift_figure`, and the `--collings` CLI). Use it when you want that
  exact figure.
- `bioscout.plot` is the **configurable grid** version: any two columns, any
  facet, either normalisation, bars or curves.
- `bioscout.figures` is the **catalogue/menu** of named project figures. A
  `bioscout.plot` figure can be registered there like any other.

## Tests

`bioscout/tests/test_plot.py` — 21 tests, numpy + pandas + matplotlib only.
The work integral is pinned against cases with exact answers (constant force at
constant velocity; a shorten-then-lengthen cycle where net work is zero and
total work is not), because ranking on the wrong one of those is the easiest
mistake this module can make.
