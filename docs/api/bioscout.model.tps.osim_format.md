# `bioscout.model.tps.osim_format`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py)

Read/write helpers that work on **both** OpenSim 3.x and 4.x ``.osim`` XML.

  
**Why this module exists**

The original pipeline was written against OpenSim 4 models (GPK, Catelli,  
Lernagopal — all ``Version 40000``+). ``Rajagopal2015.osim`` as distributed is  
``Version 30000``, and the two schemas differ in every place this package  
touches:

===================  ==========================  ================================  
concept              OpenSim 3.x                 OpenSim 4.x  
===================  ==========================  ================================  
marker's body        ``<body>femur_r</body>``    ``<socket_parent_frame>/bodyset/femur_r``  
path point's body    ``<body>``                  ``<socket_parent_frame>``  
joint centre         ``<location_in_parent>``    ``PhysicalOffsetFrame/<translation>``  
bone mesh            ``DisplayGeometry/``        ``Mesh/<mesh_file>``  
                     ``<geometry_file>``  
===================  ==========================  ================================

Rather than force every model through an OpenSim round-trip (which needs the  
``opensim`` python package just to *read* a file), the accessors below  
normalise the two layouts. Everything here is ``xml.etree`` only.

## Contents

- [`strip_socket`](#strip_socket) — Normalise ``/bodyset/femur_r`` (v4) or ``femur_r`` (v3) -> ``femur_r``.
- [`model_version`](#model_version) — Return the ``OpenSimDocument`` Version integer (0 when absent).
- [`is_v3`](#is_v3) — True for OpenSim 3.x documents (Version < 40000).
- [`frame_of`](#frame_of) — Body/frame name a Marker or PathPoint is attached to, either schema.
- [`mesh_elements`](#mesh_elements) — Yield ``(body, mesh_name, element, file_tag)`` for every bone mesh.
- [`path_point_elements`](#path_point_elements) — Yield every muscle path point element, on either schema.
- [`set_joint_centre`](#set_joint_centre) — Write a joint-centre translation, on either schema. Returns True if set.

### `strip_socket`

```python
strip_socket(text: Optional[str]) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `text` | Optional[str] | required |

**returns** `Optional[str]`

Normalise ``/bodyset/femur_r`` (v4) or ``femur_r`` (v3) -> ``femur_r``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L41)</sub>

### `model_version`

```python
model_version(root: ET.Element) -> int
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |

**returns** `int`

Return the ``OpenSimDocument`` Version integer (0 when absent).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L54)</sub>

### `is_v3`

```python
is_v3(root: ET.Element) -> bool
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |

**returns** `bool`

True for OpenSim 3.x documents (Version < 40000).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L62)</sub>

### `frame_of`

```python
frame_of(element: ET.Element) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `element` | ET.Element | required |

**returns** `Optional[str]`

Body/frame name a Marker or PathPoint is attached to, either schema.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L68)</sub>

### `mesh_elements`

```python
mesh_elements(root: ET.Element) -> Iterator[Tuple[str, str, ET.Element, str]]
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |

**returns** `Iterator[Tuple[str, str, ET.Element, str]]`

Yield ``(body, mesh_name, element, file_tag)`` for every bone mesh.

``file_tag`` is the child tag holding the filename (``mesh_file`` on v4,  
``geometry_file`` on v3) so callers can read or rewrite it uniformly. On v3  
a ``DisplayGeometry`` has no name attribute, so the geometry filename stem  
is used as the mesh name — stable enough to key a rename map on.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L77)</sub>

### `path_point_elements`

```python
path_point_elements(root: ET.Element) -> Iterator[ET.Element]
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |

**returns** `Iterator[ET.Element]`

Yield every muscle path point element, on either schema.

v4 calls them ``PathPoint``; v3 uses ``PathPoint`` too, but also  
``ConditionalPathPoint`` and ``MovingPathPoint`` which have no fixed  
``location`` and must be skipped (a moving point is a function of a  
coordinate — warping its constant would silently corrupt the model).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L100)</sub>

### `set_joint_centre`

```python
set_joint_centre(joint: ET.Element, offset_name: str, text: str) -> bool
```

| input | type | default |
|---|---|---|
| `joint` | ET.Element | required |
| `offset_name` | str | required |
| `text` | str | required |

**returns** `bool`

Write a joint-centre translation, on either schema. Returns True if set.

v4: the ``PhysicalOffsetFrame`` named ``offset_name`` -> ``<translation>``.  
v3: the joint's own ``<location_in_parent>`` (there are no offset frames,  
so ``offset_name`` is only used for the v4 lookup).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_format.py#L114)</sub>
