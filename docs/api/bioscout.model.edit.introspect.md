# `bioscout.model.edit.introspect`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py)

What is *in* a model — read without OpenSim, so a UI can be built offline.

Every option list a prompt or a dropdown needs (coordinates, muscles, wrap  
surfaces, bodies, markers) is available straight from the ``.osim`` XML. Reading  
them with ``opensim.Model`` would mean the GUI could not populate a single  
dropdown on a machine without the bindings, and would cost a full model  
initialisation per keystroke. These are plain ``xml.etree`` scans.

Only the *names* come from here. Anything that needs the model evaluated -- a  
moment arm, a mass, a segment length -- belongs in an op, not in this module.

## Contents

- [`defaults_ids`](#defaults_ids) — ids of every element inside a ``<defaults>`` block.
- [`iter_real`](#iter_real) — Iterate elements that belong to the model, skipping ``<defaults>``.
- [`coordinates`](#coordinates) — Coordinate names, in model order.
- [`muscles`](#muscles) — Muscle names only — reserve/residual actuators are excluded.
- [`bodies`](#bodies) — 
- [`markers`](#markers) — 
- [`wraps`](#wraps) — ``{wrap name: kind}`` for every wrap surface, e.g. ``WrapCylinder``.
- [`options_for`](#options_for) — Resolve a :attr:`~bioscout.model.edit.spec.Param.choices_from` name.
- [`summary`](#summary) — One-line inventory, cheap enough to print before every operation.

### `defaults_ids`

```python
defaults_ids(root: ET.Element) -> set
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |

**returns** `set`

ids of every element inside a ``<defaults>`` block.

An .osim carries template objects under ``<defaults>`` -- typically one  
``<Millard2012EquilibriumMuscle name="default">`` -- which are NOT part of  
the model. Counting them inflates every inventory by one and, worse, makes  
a correct SO/CEINMS pair look wrong: the template's  
``max_isometric_force`` is not multiplied by the strength factor, so a  
check that "every muscle is exactly x3" fails on a model that is exactly  
x3. Every scan in this package filters through here.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L36)</sub>

### `iter_real`

```python
iter_real(root: ET.Element, tag: str = None)
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |
| `tag` | str | `None` |

Iterate elements that belong to the model, skipping ``<defaults>``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L55)</sub>

### `coordinates`

```python
coordinates(model) -> List[str]
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `List[str]`

Coordinate names, in model order.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L77)</sub>

### `muscles`

```python
muscles(model) -> List[str]
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `List[str]`

Muscle names only — reserve/residual actuators are excluded.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L82)</sub>

### `bodies`

```python
bodies(model) -> List[str]
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L87)</sub>

### `markers`

```python
markers(model) -> List[str]
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L91)</sub>

### `wraps`

```python
wraps(model) -> Dict[str, str]
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `Dict[str, str]`

``{wrap name: kind}`` for every wrap surface, e.g. ``WrapCylinder``.

Kind matters because only cylinders and spheres carry a single scalable  
``<radius>``; an ellipsoid writes three numbers and cannot be grown by one  
factor without changing its shape.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L95)</sub>

### `options_for`

```python
options_for(what: str, model) -> List[str]
```

| input | type | default |
|---|---|---|
| `what` | str | required |
| `model` | – | required |

**returns** `List[str]`

Resolve a :attr:`~bioscout.model.edit.spec.Param.choices_from` name.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L110)</sub>

### `summary`

```python
summary(model) -> Dict[str, object]
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `Dict[str, object]`

One-line inventory, cheap enough to print before every operation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/introspect.py#L127)</sub>
