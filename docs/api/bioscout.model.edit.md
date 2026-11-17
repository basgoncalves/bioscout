# `bioscout.model.edit`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/__init__.py)

bioscout.model.edit  
===================

One consistent way to build and change an OpenSim model — scale it, set its  
mass, change its strength, grow its moment arms, widen a coordinate, place its  
markers, inspect it — reachable from Python, the command line, a YAML recipe,  
and (next) the GUI.

    bioscout --model-edit                         # guided  
    python -m bioscout.model.edit list  
    python -m bioscout.model.edit apply mvic --model scaled_opt_N10.osim --factor 3  
    python -m bioscout.model.edit recipe build_gpk.yaml --root .

    from bioscout.model.edit import apply, run_recipe  
    res = apply("mvic", "scaled_opt_N10.osim", factor=3.0)  
    res.ok, res.model, res.changed

This package **adds no biomechanics**. Every operation delegates to code that  
was already here — ``simulate/opensim.py``, ``utils/scale_measurements.py``,  
``change_moment_arms``, ``muscle_inspect``, ``utils/model_report.py``. What it  
adds is agreement between them:

* **no operation prompts.** ``simulate/opensim.py`` uses ``input()`` as a lazy  
  argument default in about forty places, which hangs a batch run and makes a  
  GUI impossible.  
* **one output-naming rule** (:mod:`~bioscout.model.edit.naming`) instead of the  
  eight that were in use, and never writing over the input.  
* **one description of each operation** (:mod:`~bioscout.model.edit.spec`), from  
  which the prompt, the ``--flags``, the recipe validator and the GUI form are  
  all generated. Adding an op is one decorator.  
* **results are returned, not printed**, so a caller can assert on them.

The pure-XML / OpenSim split is deliberate and declared per op: wrap radii, path  
points, coordinate ranges, marker removal, model comparison and diffing are  
plain XML and run anywhere, including in tests and in a GUI on a machine with no  
bindings. ``model_edit list`` marks the ones that cannot run where you are.

## Contents

- [`list_ops`](#list_ops) — List registered operations, optionally filtered to one group.
- [`describe_op`](#describe_op) — The :class:`~bioscout.model.edit.spec.Op` record for ``name``.

### `list_ops`

```python
list_ops(verb=None)
```

| input | type | default |
|---|---|---|
| `verb` | – | `None` |

List registered operations, optionally filtered to one group.

Named ``list_ops`` and not ``ops``: the submodule holding the operations is  
``bioscout.model.edit.ops``, and a module-level function of the same name  
shadows it, so ``from . import ops`` inside this package returns the  
function and the registry silently stays empty.

    >>> [o.name for o in list_ops("strength")]  
['muscle_opt', 'mvic']

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/__init__.py#L76)</sub>

### `describe_op`

```python
describe_op(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

The :class:`~bioscout.model.edit.spec.Op` record for ``name``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/__init__.py#L94)</sub>
