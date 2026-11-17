# `bioscout.lab.tools`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py)

tools.py -- one OpenSim / CEINMS tool at a time, for the BioScout Web "Simulate" page.

The page sends the files for ONE tool (dropped into that tool's section) and the  
model chosen from the list; the lab engine (web_engine.py) stores them under  
<job>/tools/<tool>/in/ and runs ``run_tool`` in a child process. Every tool calls  
the same bioscout function the pipeline uses, so a result here is a result there.

Anything a tool needs and was not dropped is taken, in this order:  
  1. the output of an earlier tool in the same job (scaled model, IK .mot, GRF.xml,  
     muscle-analysis folder, SO forces ...), so the sections chain without re-uploading;  
  2. the template in bioscout/setup_files (IK task set, SO actuators, marker set ...);  
  3. nothing -> the tool says which file is missing.

Outputs go to <job>/tools/<tool>/out/. ``describe()`` lists, per tool, the input  
slots the page draws drop areas for.

## Contents

- [`list_models`](#list_models) — Generic models the page can choose from: bioscout/models and any extra folders.
- [`describe`](#describe) — Tools, slots and templates for the page (paths stripped).
- [`tool_dir`](#tool_dir) — 
- [`dropped`](#dropped) — 
- [`template`](#template) — 
- [`output_of`](#output_of) — 
- [`model_for`](#model_for) — Dropped model > scaled model from Scale > the generic model chosen on the page.
- [`ik_for`](#ik_for) — 
- [`grf_for`](#grf_for) — (grf.mot, GRF.xml): this tool's drop, else the ones ID used; the xml is made when missing.
- [`need`](#need) — 
- [`grf_window`](#grf_window) — (t0, t1) of the span where any plate carries more than `threshold` N vertically.
- [`rra_defaults`](#rra_defaults) — actuators (pelvis residuals + a reserve per free coordinate) and tasks (every free coordinate), plus a setup template with the placeholders run_rra fills in.
- [`run_tool`](#run_tool) — Runs inside the child process the engine starts. Reads <job>/tools/state.json.
- [`run_ceinms_python`](#run_ceinms_python) — CEINMS in Python (bioscout.simulate.mew): the same EMG-informed Hill-type solve, runs on any OS, and without EMG it falls back to the no-EMG tier instead of failing. Outputs use CEINMS's file names (MuscleForces.sto, ...).
- [`run_ceinms`](#run_ceinms) — CEINMS execution on the uncalibrated subject built from the model, driven by the dropped EMG envelopes, with the IK, ID and MA of this job.

### `list_models`

```python
list_models(extra_dirs=())
```

| input | type | default |
|---|---|---|
| `extra_dirs` | – | `()` |

Generic models the page can choose from: bioscout/models and any extra folders.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L111)</sub>

### `describe`

```python
describe()
```

Tools, slots and templates for the page (paths stripped).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L122)</sub>

### `tool_dir`

```python
tool_dir(job_dir, tool, kind)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |
| `kind` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L130)</sub>

### `dropped`

```python
dropped(job_dir, tool, slot)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |
| `slot` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L136)</sub>

### `template`

```python
template(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L141)</sub>

### `output_of`

```python
output_of(job_dir, tool, pattern)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |
| `pattern` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L146)</sub>

### `model_for`

```python
model_for(job_dir, tool, state)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |
| `state` | – | required |

Dropped model > scaled model from Scale > the generic model chosen on the page.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L151)</sub>

### `ik_for`

```python
ik_for(job_dir, tool)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L158)</sub>

### `grf_for`

```python
grf_for(job_dir, tool)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |

(grf.mot, GRF.xml): this tool's drop, else the ones ID used; the xml is made when missing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L162)</sub>

### `need`

```python
need(path, what)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `what` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L181)</sub>

### `grf_window`

```python
grf_window(mot, threshold=20.0)
```

| input | type | default |
|---|---|---|
| `mot` | – | required |
| `threshold` | – | `20.0` |

(t0, t1) of the span where any plate carries more than `threshold` N vertically.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L187)</sub>

### `rra_defaults`

```python
rra_defaults(model_path, out_dir)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `out_dir` | – | required |

actuators (pelvis residuals + a reserve per free coordinate) and tasks (every free  
coordinate), plus a setup template with the placeholders run_rra fills in.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L208)</sub>

### `run_tool`

```python
run_tool(job_dir, tool)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `tool` | – | required |

Runs inside the child process the engine starts. Reads <job>/tools/state.json.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L275)</sub>

### `run_ceinms_python`

```python
run_ceinms_python(job_dir, state, out, opts)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `state` | – | required |
| `out` | – | required |
| `opts` | – | required |

CEINMS in Python (bioscout.simulate.mew): the same EMG-informed Hill-type  
solve, runs on any OS, and without EMG it falls back to the no-EMG tier  
instead of failing. Outputs use CEINMS's file names (MuscleForces.sto, ...).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L396)</sub>

### `run_ceinms`

```python
run_ceinms(job_dir, state, out)
```

| input | type | default |
|---|---|---|
| `job_dir` | – | required |
| `state` | – | required |
| `out` | – | required |

CEINMS execution on the uncalibrated subject built from the model, driven by the  
dropped EMG envelopes, with the IK, ID and MA of this job.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/tools.py#L446)</sub>
