# `bioscout.model.osim_model`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py)

bioscout.model.osim_model -- edit an .osim like an object (plain XML, no OpenSim).

    import bioscout as bs

    m = bs.model("gpkv4_scaled.osim")    # the only entry point

    # markers (the MODEL's virtual markers, in their parent frame, metres)  
    rasis = m.marker("RASIS")  
    rasis.location                         # array([x, y, z])  
    rasis.location = rasis.location + [0, -0.02, 0]  
    rasis.move([0, -20, 0], unit="mm")     # same thing  
    m.move_markers(["LASIS", "RASIS"], [0, -20, 0], unit="mm")

    # any property of any named component  
    ps = m.muscle("psoas_r")  
    ps.max_isometric_force                 # 1234.5   (child tags read as attributes)  
    ps.max_isometric_force *= 0.8  
    ps.set("optimal_fiber_length", 0.11)  
    ps.path_points[1].move([5, 0, 0], unit="mm")  
    m.wrap("IL_at_brim_r").radius = 0.03  
    m.get("hip_flexion_r").range           # coordinates, joints, bodies, ... by name

    # every bioscout.model.edit operation (wrap_add, wrap_detach, mvic, ma_target, ...)  
    m.apply("wrap_add", body="pelvis", wrap_name="new_cyl_r", kind="cylinder",  
            radius=0.03, length=0.1, muscles=["psoas_r"])

    m.changes                              # what was edited, in order  
    m.save("gpkv4_scaled_edited.osim")     # never over the input unless overwrite=True

Locations are in the component's PARENT frame (``m.marker("RASIS").parent_frame``),  
which is what the .osim stores; ``move`` adds the offset in that same frame.  
Elements under ``<defaults>`` (templates) are never returned.

## Contents

- class [`Component`](#component) — One named element of the model. Child tags read/write as attributes: ``c.max_isometric_force``, ``c.max_isometric_force = 900``; or use ``get(prop)`` / ``set(prop, value)``. Values are float, numpy array, bool or str.
  - [`Component.name`](#componentname) — 
  - [`Component.kind`](#componentkind) — The OpenSim class (XML tag), e.g. 'Marker', 'Millard2012EquilibriumMuscle'.
  - [`Component.element`](#componentelement) — 
  - [`Component.props`](#componentprops) — Every simple (leaf) child property and its value.
  - [`Component.get`](#componentget) — 
  - [`Component.set`](#componentset) — 
- class [`Point`](#point) — Anything with a <location> in a parent frame: markers, path points.
  - [`Point.location`](#pointlocation) — 
  - [`Point.location`](#pointlocation) — 
  - [`Point.parent_frame`](#pointparent_frame) — 
  - [`Point.move`](#pointmove) — Add ``offset`` (x, y, z) in the parent frame.
- class [`Marker`](#marker) — 
- class [`Wrap`](#wrap) — 
  - [`Wrap.translation`](#wraptranslation) — 
  - [`Wrap.translation`](#wraptranslation) — 
  - [`Wrap.move`](#wrapmove) — 
- class [`Muscle`](#muscle) — 
  - [`Muscle.path_points`](#musclepath_points) — 
  - [`Muscle.wraps`](#musclewraps) — Names of the wrap objects this muscle's path uses.
- class [`Model`](#model) — An .osim held in memory as XML. See the module docstring for examples.
  - [`Model.root`](#modelroot) — 
  - [`Model.names`](#modelnames) — Names of every component (``kind``: tag or tag substring, e.g. 'Marker', 'Muscle', 'Wrap').
  - [`Model.find`](#modelfind) — Components whose name matches a glob, e.g. ``find('*ASIS')``, ``find('psoas*', 'Muscle')``.
  - [`Model.get`](#modelget) — 
  - [`Model.marker`](#modelmarker) — 
  - [`Model.muscle`](#modelmuscle) — 
  - [`Model.wrap`](#modelwrap) — 
  - [`Model.coordinate`](#modelcoordinate) — 
  - [`Model.body`](#modelbody) — 
  - [`Model.markers`](#modelmarkers) — 
  - [`Model.muscles`](#modelmuscles) — 
  - [`Model.move_markers`](#modelmove_markers) — Move several markers (names or one glob) by the same offset in their parent frames.
  - [`Model.scale`](#modelscale) — Multiply ``prop`` by ``factor`` on every matching component, e.g. ``m.scale('max_isometric_force', 0.8, 'psoas*')``. Returns how many changed.
  - [`Model.apply`](#modelapply) — Run a bioscout.model.edit operation (``bioscout model-edit list``) on the current in-memory state; the result is loaded back into this object. Returns the op's OpResult (``.ok``, ``.changed``, ``.messages``).
  - [`Model.save`](#modelsave) — Write the model. Without ``path``: ``<stem>_edited.osim`` next to the input. Refuses to write over the input (or an existing file) unless ``overwrite=True``.
  - [`Model.summary`](#modelsummary) — 

<a id="component"></a>

## class `Component`

```python
Component(model: 'Model', el: ET.Element)
```

| input | type | default |
|---|---|---|
| `model` | 'Model' | required |
| `el` | ET.Element | required |

One named element of the model. Child tags read/write as attributes:  
``c.max_isometric_force``, ``c.max_isometric_force = 900``; or use  
``get(prop)`` / ``set(prop, value)``. Values are float, numpy array, bool or str.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L92)</sub>

<a id="componentname"></a>

### `Component.name`

```python
Component.name() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L103)</sub>

<a id="componentkind"></a>

### `Component.kind`

```python
Component.kind() -> str
```

**returns** `str`

The OpenSim class (XML tag), e.g. 'Marker', 'Millard2012EquilibriumMuscle'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L107)</sub>

<a id="componentelement"></a>

### `Component.element`

```python
Component.element() -> ET.Element
```

**returns** `ET.Element`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L112)</sub>

<a id="componentprops"></a>

### `Component.props`

```python
Component.props() -> dict
```

**returns** `dict`

Every simple (leaf) child property and its value.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L119)</sub>

<a id="componentget"></a>

### `Component.get`

```python
Component.get(prop: str)
```

| input | type | default |
|---|---|---|
| `prop` | str | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L131)</sub>

<a id="componentset"></a>

### `Component.set`

```python
Component.set(prop: str, value) -> 'Component'
```

| input | type | default |
|---|---|---|
| `prop` | str | required |
| `value` | – | required |

**returns** `'Component'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L134)</sub>

<a id="point"></a>

## class `Point`(Component)

Anything with a <location> in a parent frame: markers, path points.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L156)</sub>

<a id="pointlocation"></a>

### `Point.location`

```python
Point.location() -> np.ndarray
```

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L160)</sub>

<a id="pointlocation"></a>

### `Point.location`

```python
Point.location(xyz)
```

| input | type | default |
|---|---|---|
| `xyz` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L164)</sub>

<a id="pointparent_frame"></a>

### `Point.parent_frame`

```python
Point.parent_frame() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L168)</sub>

<a id="pointmove"></a>

### `Point.move`

```python
Point.move(offset: Sequence[float], unit: str = 'm') -> 'Point'
```

| input | type | default |
|---|---|---|
| `offset` | Sequence[float] | required |
| `unit` | str | `'m'` |

**returns** `'Point'`

Add ``offset`` (x, y, z) in the parent frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L175)</sub>

<a id="marker"></a>

## class `Marker`(Point)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L181)</sub>

<a id="wrap"></a>

## class `Wrap`(Component)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L185)</sub>

<a id="wraptranslation"></a>

### `Wrap.translation`

```python
Wrap.translation() -> np.ndarray
```

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L187)</sub>

<a id="wraptranslation"></a>

### `Wrap.translation`

```python
Wrap.translation(xyz)
```

| input | type | default |
|---|---|---|
| `xyz` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L191)</sub>

<a id="wrapmove"></a>

### `Wrap.move`

```python
Wrap.move(offset: Sequence[float], unit: str = 'm') -> 'Wrap'
```

| input | type | default |
|---|---|---|
| `offset` | Sequence[float] | required |
| `unit` | str | `'m'` |

**returns** `'Wrap'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L194)</sub>

<a id="muscle"></a>

## class `Muscle`(Component)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L199)</sub>

<a id="musclepath_points"></a>

### `Muscle.path_points`

```python
Muscle.path_points() -> List[Point]
```

**returns** `List[Point]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L201)</sub>

<a id="musclewraps"></a>

### `Muscle.wraps`

```python
Muscle.wraps() -> List[str]
```

**returns** `List[str]`

Names of the wrap objects this muscle's path uses.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L208)</sub>

<a id="model"></a>

## class `Model`

```python
Model(path: Union[str, os.PathLike])
```

| input | type | default |
|---|---|---|
| `path` | Union[str, os.PathLike] | required |

An .osim held in memory as XML. See the module docstring for examples.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L232)</sub>

<a id="modelroot"></a>

### `Model.root`

```python
Model.root() -> ET.Element
```

**returns** `ET.Element`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L242)</sub>

<a id="modelnames"></a>

### `Model.names`

```python
Model.names(kind: Optional[str] = None) -> List[str]
```

| input | type | default |
|---|---|---|
| `kind` | Optional[str] | `None` |

**returns** `List[str]`

Names of every component (``kind``: tag or tag substring, e.g. 'Marker', 'Muscle', 'Wrap').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L262)</sub>

<a id="modelfind"></a>

### `Model.find`

```python
Model.find(pattern: str = '*', kind: Optional[str] = None) -> List[Component]
```

| input | type | default |
|---|---|---|
| `pattern` | str | `'*'` |
| `kind` | Optional[str] | `None` |

**returns** `List[Component]`

Components whose name matches a glob, e.g. ``find('*ASIS')``, ``find('psoas*', 'Muscle')``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L266)</sub>

<a id="modelget"></a>

### `Model.get`

```python
Model.get(name: str, kind: Optional[str] = None) -> Component
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `kind` | Optional[str] | `None` |

**returns** `Component`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L271)</sub>

<a id="modelmarker"></a>

### `Model.marker`

```python
Model.marker(name) -> Marker
```

| input | type | default |
|---|---|---|
| `name` | – | required |

**returns** `Marker`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L284)</sub>

<a id="modelmuscle"></a>

### `Model.muscle`

```python
Model.muscle(name) -> Muscle
```

| input | type | default |
|---|---|---|
| `name` | – | required |

**returns** `Muscle`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L287)</sub>

<a id="modelwrap"></a>

### `Model.wrap`

```python
Model.wrap(name) -> Wrap
```

| input | type | default |
|---|---|---|
| `name` | – | required |

**returns** `Wrap`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L290)</sub>

<a id="modelcoordinate"></a>

### `Model.coordinate`

```python
Model.coordinate(name) -> Component
```

| input | type | default |
|---|---|---|
| `name` | – | required |

**returns** `Component`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L293)</sub>

<a id="modelbody"></a>

### `Model.body`

```python
Model.body(name) -> Component
```

| input | type | default |
|---|---|---|
| `name` | – | required |

**returns** `Component`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L296)</sub>

<a id="modelmarkers"></a>

### `Model.markers`

```python
Model.markers() -> List[Marker]
```

**returns** `List[Marker]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L300)</sub>

<a id="modelmuscles"></a>

### `Model.muscles`

```python
Model.muscles() -> List[Muscle]
```

**returns** `List[Muscle]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L304)</sub>

<a id="modelmove_markers"></a>

### `Model.move_markers`

```python
Model.move_markers(
    names: Union[str, Iterable[str]],
    offset,
    unit: str = 'm'
) -> List[Marker]
```

| input | type | default |
|---|---|---|
| `names` | Union[str, Iterable[str]] | required |
| `offset` | – | required |
| `unit` | str | `'m'` |

**returns** `List[Marker]`

Move several markers (names or one glob) by the same offset in their parent frames.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L308)</sub>

<a id="modelscale"></a>

### `Model.scale`

```python
Model.scale(prop: str, factor: float, names='*', kind: Optional[str] = 'Muscle') -> int
```

| input | type | default |
|---|---|---|
| `prop` | str | required |
| `factor` | float | required |
| `names` | – | `'*'` |
| `kind` | Optional[str] | `'Muscle'` |

**returns** `int`

Multiply ``prop`` by ``factor`` on every matching component, e.g.  
``m.scale('max_isometric_force', 0.8, 'psoas*')``. Returns how many changed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L317)</sub>

<a id="modelapply"></a>

### `Model.apply`

```python
Model.apply(op: str, **params)
```

| input | type | default |
|---|---|---|
| `op` | str | required |
| `**params` | – | – |

Run a bioscout.model.edit operation (``bioscout model-edit list``) on the  
current in-memory state; the result is loaded back into this object.  
Returns the op's OpResult (``.ok``, ``.changed``, ``.messages``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L328)</sub>

<a id="modelsave"></a>

### `Model.save`

```python
Model.save(path: Union[str, os.PathLike, None] = None, overwrite: bool = False) -> Path
```

| input | type | default |
|---|---|---|
| `path` | Union[str, os.PathLike, None] | `None` |
| `overwrite` | bool | `False` |

**returns** `Path`

Write the model. Without ``path``: ``<stem>_edited.osim`` next to the input.  
Refuses to write over the input (or an existing file) unless ``overwrite=True``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L361)</sub>

<a id="modelsummary"></a>

### `Model.summary`

```python
Model.summary() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/osim_model.py#L371)</sub>
