# `bioscout.model.edit.spec`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py)

The contract every model operation obeys, and the registry they live in.

One dataclass describes an operation completely: what it is called, what it  
does, what parameters it takes and of what kind, how it names its output, and  
whether it needs OpenSim. Everything else in this package -- the guided prompt,  
the argparse CLI, the recipe runner, and (next) the GUI panel -- is *generated*  
from that description rather than hand-written per operation. Adding an  
operation is one ``@op`` decorator, and it appears in all of them at once.

That is the whole point. bioscout already had the capability three times over  
(``simulate/opensim.py``, ``change_moment_arms``, ``muscle_inspect``), but each  
with its own calling convention, its own interactive prompt, and its own idea  
of where the output goes. This module does not reimplement any of that work --  
every op delegates -- it just makes them agree.

The three rules an op must follow, none of which the underlying functions  
consistently did:

1. **Never prompt.** ``simulate/opensim.py`` has ~40 bare ``input()`` calls used as  
   lazy argument defaults; they block a GUI and hang a batch run. An op always  
   passes every argument explicitly.  
2. **Always take an explicit output path.** Callers of  
   ``increase_isometric_force`` had no say in the ``_increased_3.00.osim`` it  
   derived, and ``set_total_mass`` overwrites in place by default. Here the  
   facade computes the name from ``Op.suffix`` and hands it down, so the naming  
   rule lives in exactly one place (``naming.py``).  
3. **Return a result, do not print one.** ``OpResult`` carries what changed, so  
   a caller can assert on it. Ops may still print progress.

## Contents

- class [`Param`](#param) — One argument of an operation, described well enough to build a UI from.
  - [`Param.label`](#paramlabel) — 
- class [`Op`](#op) — A single model operation.
  - [`Op.param`](#opparam) — 
  - [`Op.required_params`](#oprequired_params) — 
- class [`OpResult`](#opresult) — What an operation did. Returned, never printed, so callers can assert.
  - [`OpResult.summary_line`](#opresultsummary_line) — 
- [`op`](#op) — Register a function as an operation.
- [`get`](#get) — Look an operation up by name, with a helpful error when it is absent.
- [`by_verb`](#by_verb) — ``{verb: [Op, ...]}`` in :data:`VERBS` order, for listing.

<a id="param"></a>

## class `Param`

One argument of an operation, described well enough to build a UI from.

``kind`` drives how the value is asked for and parsed:  
``float int str bool path choice list[str] list[float]``.

``choices_from`` names a *model-dependent* option list that cannot be known  
until a model is picked -- ``coordinates``, ``muscles``, ``wraps``,  
``bodies``. The prompt resolves it by calling  
:func:`bioscout.model.edit.introspect.options_for`, so the CLI can offer the  
real coordinate names of the model in hand instead of a static list, and the  
GUI can fill a dropdown the same way.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L53)</sub>

<a id="paramlabel"></a>

### `Param.label`

```python
Param.label() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L85)</sub>

<a id="op"></a>

## class `Op`

A single model operation.

``suffix`` is a format template evaluated against the resolved parameters,  
e.g. ``"_mvicx{factor:.2f}"`` -> ``scaled_opt_N10_mvicx3.00.osim``. It is  
how an output name is derived when the caller does not give one; an empty  
suffix means the caller MUST supply ``out``. See :mod:`naming`.

``needs_opensim`` is honest about the split that runs through this whole  
package: wrap radii and path points are plain XML and run anywhere, while  
anything that has to *evaluate* a model (moment-arm sweeps, ScaleTool, mass  
and inertia) needs the OpenSim Python bindings. The CLI reports this before  
it asks for anything, rather than failing halfway through a recipe.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L90)</sub>

<a id="opparam"></a>

### `Op.param`

```python
Op.param(name: str) -> Param
```

| input | type | default |
|---|---|---|
| `name` | str | required |

**returns** `Param`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L115)</sub>

<a id="oprequired_params"></a>

### `Op.required_params`

```python
Op.required_params() -> Tuple[Param, ...]
```

**returns** `Tuple[Param, ...]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L122)</sub>

<a id="opresult"></a>

## class `OpResult`

What an operation did. Returned, never printed, so callers can assert.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L127)</sub>

<a id="opresultsummary_line"></a>

### `OpResult.summary_line`

```python
OpResult.summary_line() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L141)</sub>

### `op`

```python
op(
    name: str,
    verb: str,
    summary: str,
    params: Sequence[Param],
    suffix: str = '',
    needs_opensim: bool = True,
    writes_model: bool = True,
    delegates_to: str = '',
    notes: str = ''
)
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `verb` | str | required |
| `summary` | str | required |
| `params` | Sequence[Param] | required |
| `suffix` | str | `''` |
| `needs_opensim` | bool | `True` |
| `writes_model` | bool | `True` |
| `delegates_to` | str | `''` |
| `notes` | str | `''` |

Register a function as an operation.

The wrapped function is called as ``fn(model, out, **params)`` and must  
return an :class:`OpResult`. It must not prompt and must not invent an  
output path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L154)</sub>

### `get`

```python
get(name: str) -> Op
```

| input | type | default |
|---|---|---|
| `name` | str | required |

**returns** `Op`

Look an operation up by name, with a helpful error when it is absent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L178)</sub>

### `by_verb`

```python
by_verb() -> Dict[str, list]
```

**returns** `Dict[str, list]`

``{verb: [Op, ...]}`` in :data:`VERBS` order, for listing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/spec.py#L188)</sub>
