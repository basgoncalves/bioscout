# `bioscout.lab.web_engine`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py)

web_engine.py -- the lab engine: OpenSim for the BioScout Web lab demo.

A browser cannot run OpenSim. This is the computer that does: a small web  
service on the lab PC that takes a student's static trial, motion trial and  
force data, lays them out as an ordinary bioscout session, and runs the same  
pipeline a researcher would -- export, scale, inverse kinematics + inverse  
dynamics, static optimisation + joint reaction loads -- one step at a time,  
handing each step's result back to the page to plot.

    python -m bioscout.lab.web_engine                    this PC only  
    python -m bioscout.lab.web_engine --tunnel           + an https address phones can reach  
    python -m bioscout.lab.web_engine --template D:\course_project

It prints a link. Open it (or show it as a QR code) and the lab demo's  
"OpenSim trial" card is connected.

What it will and will not do, none of it adjustable from the page:

  * It listens on 127.0.0.1 only. A browser on this PC can reach that from the  
    https page; anything else gets in only through the tunnel you start.  
  * Every request needs the session code printed at start-up. It changes each  
    time the engine starts. Without it the service answers /health and nothing  
    else.  
  * Students upload DATA. The model, the marker set and the setup files are the  
    ones in the template project on this PC (--template); a page cannot swap  
    them, and cannot name a path.  
  * One OpenSim step runs at a time, each in its own process. OpenSim changes  
    the working directory and can take the interpreter down with it; a queue  
    and a child process keep one student's bad trial from being everyone's.  
  * Each student's files live in their own session folder under --work and are  
    deleted after --keep-hours.

The service itself imports nothing but the standard library, so it starts  
instantly and can be tested without OpenSim (--fake replays the template's  
stored results). bioscout and OpenSim are imported only inside the child  
process that runs a step.

## Contents

- class [`Engine`](#engine) — 
  - [`Engine.new_job`](#enginenew_job) — 
  - [`Engine.job`](#enginejob) — 
  - [`Engine.public`](#enginepublic) — 
  - [`Engine.job_dir`](#enginejob_dir) — 
  - [`Engine.models`](#enginemodels) — 
  - [`Engine.tool_state_write`](#enginetool_state_write) — 
  - [`Engine.set_model`](#engineset_model) — 
  - [`Engine.set_options`](#engineset_options) — 
  - [`Engine.tool_inputs`](#enginetool_inputs) — 
  - [`Engine.tool_upload`](#enginetool_upload) — 
  - [`Engine.tool_clear`](#enginetool_clear) — 
  - [`Engine.tool_start`](#enginetool_start) — 
  - [`Engine.tool_outputs`](#enginetool_outputs) — 
  - [`Engine.tool_file`](#enginetool_file) — 
  - [`Engine.ready`](#engineready) — 
  - [`Engine.set_mass`](#engineset_mass) — 
  - [`Engine.invalidate`](#engineinvalidate) — A changed input makes every later result stale.
  - [`Engine.save_upload`](#enginesave_upload) — 
  - [`Engine.use_example`](#engineuse_example) — 
  - [`Engine.start`](#enginestart) — 
  - [`Engine.log_path`](#enginelog_path) — 
  - [`Engine.log_tail`](#enginelog_tail) — 
  - [`Engine.result_path`](#engineresult_path) — 
  - [`Engine.scaled_model`](#enginescaled_model) — 
  - [`Engine.result`](#engineresult) — 
  - [`Engine.bundle`](#enginebundle) — Everything this trial produced, as a zip the student keeps.
- [`session_dir`](#session_dir) — 
- [`exp_dir`](#exp_dir) — 
- [`c3d_dir`](#c3d_dir) — 
- [`trial_out`](#trial_out) — 
- [`model_dir`](#model_dir) — 
- [`write_session_yaml`](#write_session_yaml) — 
- [`read_storage`](#read_storage) — An OpenSim .sto/.mot as {columns, time, data:{column:[...]}, inDegrees}, thinned to at most max_rows rows. Standard library only.
- [`read_scale_factors`](#read_scale_factors) — 
- [`find_preset`](#find_preset) — The one model + marker set this engine scales and solves with, as paths relative to the project folder.
- [`find_example`](#find_example) — A static + a motion trial already exported in the template, to try the whole chain without uploading anything.
- [`prepare_work`](#prepare_work) — 
- [`purge_old`](#purge_old) — 
- [`run_step`](#run_step) — Runs inside the child. Imports bioscout (and with it OpenSim).
- [`make_handler`](#make_handler) — 
- [`start_tunnel`](#start_tunnel) — cloudflared quick tunnel: an https address that forwards to this PC.
- [`student_link`](#student_link) — 
- [`main`](#main) — 

<a id="engine"></a>

## class `Engine`

```python
Engine(work, template, preset, example, code, fake=False)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `template` | – | required |
| `preset` | – | required |
| `example` | – | required |
| `code` | – | required |
| `fake` | – | `False` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L322)</sub>

<a id="enginenew_job"></a>

### `Engine.new_job`

```python
Engine.new_job()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L334)</sub>

<a id="enginejob"></a>

### `Engine.job`

```python
Engine.job(job)
```

| input | type | default |
|---|---|---|
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L345)</sub>

<a id="enginepublic"></a>

### `Engine.public`

```python
Engine.public(st)
```

| input | type | default |
|---|---|---|
| `st` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L351)</sub>

<a id="enginejob_dir"></a>

### `Engine.job_dir`

```python
Engine.job_dir(job)
```

| input | type | default |
|---|---|---|
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L372)</sub>

<a id="enginemodels"></a>

### `Engine.models`

```python
Engine.models()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L375)</sub>

<a id="enginetool_state_write"></a>

### `Engine.tool_state_write`

```python
Engine.tool_state_write(st)
```

| input | type | default |
|---|---|---|
| `st` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L382)</sub>

<a id="engineset_model"></a>

### `Engine.set_model`

```python
Engine.set_model(st, name)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L389)</sub>

<a id="engineset_options"></a>

### `Engine.set_options`

```python
Engine.set_options(st, tool, opts)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `tool` | – | required |
| `opts` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L395)</sub>

<a id="enginetool_inputs"></a>

### `Engine.tool_inputs`

```python
Engine.tool_inputs(job, tool)
```

| input | type | default |
|---|---|---|
| `job` | – | required |
| `tool` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L401)</sub>

<a id="enginetool_upload"></a>

### `Engine.tool_upload`

```python
Engine.tool_upload(st, tool, slot, filename, body)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `tool` | – | required |
| `slot` | – | required |
| `filename` | – | required |
| `body` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L408)</sub>

<a id="enginetool_clear"></a>

### `Engine.tool_clear`

```python
Engine.tool_clear(st, tool, slot)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `tool` | – | required |
| `slot` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L424)</sub>

<a id="enginetool_start"></a>

### `Engine.tool_start`

```python
Engine.tool_start(st, tool)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `tool` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L429)</sub>

<a id="enginetool_outputs"></a>

### `Engine.tool_outputs`

```python
Engine.tool_outputs(st, tool)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `tool` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L442)</sub>

<a id="enginetool_file"></a>

### `Engine.tool_file`

```python
Engine.tool_file(st, tool, rel)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `tool` | – | required |
| `rel` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L455)</sub>

<a id="engineready"></a>

### `Engine.ready`

```python
Engine.ready(st)
```

| input | type | default |
|---|---|---|
| `st` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L463)</sub>

<a id="engineset_mass"></a>

### `Engine.set_mass`

```python
Engine.set_mass(st, mass)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `mass` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L468)</sub>

<a id="engineinvalidate"></a>

### `Engine.invalidate`

```python
Engine.invalidate(st, from_step)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `from_step` | – | required |

A changed input makes every later result stale.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L476)</sub>

<a id="enginesave_upload"></a>

### `Engine.save_upload`

```python
Engine.save_upload(st, kind, body)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `kind` | – | required |
| `body` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L482)</sub>

<a id="engineuse_example"></a>

### `Engine.use_example`

```python
Engine.use_example(st)
```

| input | type | default |
|---|---|---|
| `st` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L504)</sub>

<a id="enginestart"></a>

### `Engine.start`

```python
Engine.start(st, step)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `step` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L522)</sub>

<a id="enginelog_path"></a>

### `Engine.log_path`

```python
Engine.log_path(job, step)
```

| input | type | default |
|---|---|---|
| `job` | – | required |
| `step` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L539)</sub>

<a id="enginelog_tail"></a>

### `Engine.log_tail`

```python
Engine.log_tail(job, step, n=25)
```

| input | type | default |
|---|---|---|
| `job` | – | required |
| `step` | – | required |
| `n` | – | `25` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L542)</sub>

<a id="engineresult_path"></a>

### `Engine.result_path`

```python
Engine.result_path(job, key)
```

| input | type | default |
|---|---|---|
| `job` | – | required |
| `key` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L652)</sub>

<a id="enginescaled_model"></a>

### `Engine.scaled_model`

```python
Engine.scaled_model(job)
```

| input | type | default |
|---|---|---|
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L663)</sub>

<a id="engineresult"></a>

### `Engine.result`

```python
Engine.result(st, what)
```

| input | type | default |
|---|---|---|
| `st` | – | required |
| `what` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L668)</sub>

<a id="enginebundle"></a>

### `Engine.bundle`

```python
Engine.bundle(st)
```

| input | type | default |
|---|---|---|
| `st` | – | required |

Everything this trial produced, as a zip the student keeps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L686)</sub>

### `session_dir`

```python
session_dir(work, job)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L93)</sub>

### `exp_dir`

```python
exp_dir(work, job, trial)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `job` | – | required |
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L97)</sub>

### `c3d_dir`

```python
c3d_dir(work, job)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L101)</sub>

### `trial_out`

```python
trial_out(work, job)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L105)</sub>

### `model_dir`

```python
model_dir(work, job)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `job` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L109)</sub>

### `write_session_yaml`

```python
write_session_yaml(work, job, mass, preset, trial_type='walking')
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `job` | – | required |
| `mass` | – | required |
| `preset` | – | required |
| `trial_type` | – | `'walking'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L130)</sub>

### `read_storage`

```python
read_storage(path, max_rows=240)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `max_rows` | – | `240` |

An OpenSim .sto/.mot as {columns, time, data:{column:[...]}, inDegrees},  
thinned to at most max_rows rows. Standard library only.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L173)</sub>

### `read_scale_factors`

```python
read_scale_factors(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L201)</sub>

### `find_preset`

```python
find_preset(project, model=None, markerset=None)
```

| input | type | default |
|---|---|---|
| `project` | – | required |
| `model` | – | `None` |
| `markerset` | – | `None` |

The one model + marker set this engine scales and solves with, as paths  
relative to the project folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L211)</sub>

### `find_example`

```python
find_example(template)
```

| input | type | default |
|---|---|---|
| `template` | – | required |

A static + a motion trial already exported in the template, to try the  
whole chain without uploading anything.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L234)</sub>

### `prepare_work`

```python
prepare_work(work, template)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `template` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L259)</sub>

### `purge_old`

```python
purge_old(work, keep_hours)
```

| input | type | default |
|---|---|---|
| `work` | – | required |
| `keep_hours` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L267)</sub>

### `run_step`

```python
run_step(sd, step)
```

| input | type | default |
|---|---|---|
| `sd` | – | required |
| `step` | – | required |

Runs inside the child. Imports bioscout (and with it OpenSim).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L277)</sub>

### `make_handler`

```python
make_handler(engine)
```

| input | type | default |
|---|---|---|
| `engine` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L705)</sub>

### `start_tunnel`

```python
start_tunnel(port, on_url)
```

| input | type | default |
|---|---|---|
| `port` | – | required |
| `on_url` | – | required |

cloudflared quick tunnel: an https address that forwards to this PC.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L847)</sub>

### `student_link`

```python
student_link(engine_url, code)
```

| input | type | default |
|---|---|---|
| `engine_url` | – | required |
| `code` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L868)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/web_engine.py#L872)</sub>
