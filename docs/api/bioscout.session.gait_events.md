# `bioscout.session.gait_events`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/gait_events.py)

Gait events in session.yaml -- one format, read and written in one place.

Each trial's ``events`` is a mapping with a unique name per event, one line  
each (so editors fold it and any tool can address an event by name)::

    trials:  
      Walking_01:  
        events:  
          foot_contact_1_l: {time: 5.3203, source: markers, on_plate: false, at_record_edge: true}  
          foot_off_1_l:     {time: 5.4703, source: markers, on_plate: false}  
          foot_contact_1_r: {time: 5.5703, source: grf, on_plate: true}

Name: ``<event>_<n>_<side>`` -- the event in snake case, its count (1, 2, ...  
in time order per event and side) and ``r`` / ``l``. Fields left out mean  
false / unknown, so ``at_record_edge`` only appears when it is true.

:func:`normalise` also reads the older shapes (a list of ``{name, time, ...}``  
dicts with names like "Right Foot Contact", or a plain list of times) --  
``session.migrate()`` rewrites a file into this format.

## Contents

- class [`FlowMap`](#flowmap) — A dict written on one line (``{time: 5.5, source: grf}``) by session.yaml's writer.
- [`event_key`](#event_key) — 
- [`normalise`](#normalise) — Any events shape -> ``{key: {time, source?, on_plate?, at_record_edge?}}``, ordered by time. Keys of the new format are kept as they are.
- [`for_yaml`](#for_yaml) — What the writer puts under ``events:`` -- normalised, one line per event.
- [`table`](#table) — Events as a DataFrame: name, event, n, side, time, source, on_plate, at_record_edge.

<a id="flowmap"></a>

## class `FlowMap`(dict)

A dict written on one line (``{time: 5.5, source: grf}``) by session.yaml's writer.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/gait_events.py#L33)</sub>

### `event_key`

```python
event_key(kind: str, n: int, side: str) -> str
```

| input | type | default |
|---|---|---|
| `kind` | str | required |
| `n` | int | required |
| `side` | str | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/gait_events.py#L53)</sub>

### `normalise`

```python
normalise(raw) -> Dict[str, Dict]
```

| input | type | default |
|---|---|---|
| `raw` | – | required |

**returns** `Dict[str, Dict]`

Any events shape -> ``{key: {time, source?, on_plate?, at_record_edge?}}``,  
ordered by time. Keys of the new format are kept as they are.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/gait_events.py#L69)</sub>

### `for_yaml`

```python
for_yaml(events) -> Dict[str, FlowMap]
```

| input | type | default |
|---|---|---|
| `events` | – | required |

**returns** `Dict[str, FlowMap]`

What the writer puts under ``events:`` -- normalised, one line per event.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/gait_events.py#L94)</sub>

### `table`

```python
table(events)
```

| input | type | default |
|---|---|---|
| `events` | – | required |

Events as a DataFrame: name, event, n, side, time, source, on_plate, at_record_edge.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/gait_events.py#L99)</sub>
