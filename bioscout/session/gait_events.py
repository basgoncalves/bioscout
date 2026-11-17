"""Gait events in session.yaml -- one format, read and written in one place.

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
"""
from __future__ import annotations

import re
from typing import Dict, List

__all__ = ["normalise", "event_key", "table", "FlowMap", "for_yaml"]

_SIDES = {"right": "r", "left": "l", "r": "r", "l": "l"}
#: fields kept per event, in this order; False / None values are not written
FIELDS = ("time", "source", "on_plate", "at_record_edge")


class FlowMap(dict):
    """A dict written on one line (``{time: 5.5, source: grf}``) by session.yaml's writer."""


def _snake(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", str(s).lower()).strip("_")


def _split_name(name: str, side=None):
    """'Right Foot Contact' -> ('foot_contact', 'r'); 'foot_contact_2_r' -> ('foot_contact', 'r')."""
    s = _snake(name)
    m = re.match(r"^(.*?)(?:_(\d+))?_(r|l)$", s)
    if m:                                             # already a key
        return m.group(1), m.group(3)
    first, _, rest = s.partition("_")
    if first in _SIDES and rest:
        return rest, _SIDES[first]
    return s, _SIDES.get(str(side or "").lower(), "")


def event_key(kind: str, n: int, side: str) -> str:
    return f"{kind}_{n}_{side}" if side else f"{kind}_{n}"


def _clean(e: dict) -> Dict:
    out = {"time": round(float(e["time"]), 4)}
    for k in FIELDS[1:]:
        v = e.get(k)
        if v not in (None, False, ""):
            out[k] = v
    for k, v in e.items():                            # unknown extra fields survive
        if k not in out and k not in ("name", "side", "contact", "time") and v not in (None, False, ""):
            out[k] = v
    return out


def normalise(raw) -> Dict[str, Dict]:
    """Any events shape -> ``{key: {time, source?, on_plate?, at_record_edge?}}``,
    ordered by time. Keys of the new format are kept as they are."""
    if not raw:
        return {}
    if isinstance(raw, dict):                         # current format (values may be bare times)
        out = {str(k): _clean(v if isinstance(v, dict) else {"time": v}) for k, v in raw.items()}
        return dict(sorted(out.items(), key=lambda kv: kv[1]["time"]))
    items: List[dict] = []
    for i, e in enumerate(raw):
        if isinstance(e, dict):
            items.append(dict(e))
        elif isinstance(e, (list, tuple)) and len(e) == 3:   # [side, kind, time]
            items.append({"side": e[0], "name": e[1], "time": e[2]})
        else:                                         # bare time
            items.append({"name": "event", "time": e})
    items.sort(key=lambda e: float(e["time"]))
    out, count = {}, {}
    for e in items:
        kind, side = _split_name(e.get("name") or "event", e.get("side"))
        n = count[(kind, side)] = count.get((kind, side), 0) + 1
        out[event_key(kind, n, side)] = _clean(e)
    return out


def for_yaml(events) -> Dict[str, FlowMap]:
    """What the writer puts under ``events:`` -- normalised, one line per event."""
    return {k: FlowMap(v) for k, v in normalise(events).items()}


def table(events):
    """Events as a DataFrame: name, event, n, side, time, source, on_plate, at_record_edge."""
    import pandas as pd
    rows = []
    for k, v in normalise(events).items():
        m = re.match(r"^(.*)_(\d+)_(r|l)$", k) or re.match(r"^(.*)_(\d+)$", k)
        kind, n, side = (m.group(1), int(m.group(2)), m.group(3) if m.re.groups == 3 else "") \
            if m else (k, 1, "")
        rows.append({"name": k, "event": kind, "n": n, "side": side,
                     "time": v["time"], "source": v.get("source", ""),
                     "on_plate": bool(v.get("on_plate")),
                     "at_record_edge": bool(v.get("at_record_edge"))})
    return pd.DataFrame(rows, columns=["name", "event", "n", "side", "time", "source",
                                       "on_plate", "at_record_edge"])


def _register():
    try:
        import yaml
    except ImportError:
        return
    def rep(dumper, data):
        return dumper.represent_mapping("tag:yaml.org,2002:map", dict(data), flow_style=True)
    for D in (yaml.SafeDumper, yaml.Dumper):
        yaml.add_representer(FlowMap, rep, Dumper=D)


_register()


def migrate_text(text: str) -> str:
    """Rewrite every ``events:`` block of a session.yaml TEXT into the current
    format, leaving all other lines (and comments) as they are."""
    import yaml
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s*)events:\s*(#.*)?$", ln)
        if not m:
            out.append(ln); i += 1; continue
        ind = len(m.group(1))
        j = i + 1
        while j < len(lines):                         # block = deeper lines, or "- " at the same indent
            s = lines[j]
            if s.strip() == "":
                j += 1; continue
            k = len(s) - len(s.lstrip())
            if k > ind or (k == ind and s.lstrip().startswith("- ")):
                j += 1; continue
            break
        while j > i + 1 and lines[j - 1].strip() == "":
            j -= 1
        block = "\n".join(l[ind:] if len(l) >= ind else l for l in lines[i:j])
        raw = (yaml.safe_load(block) or {}).get("events")
        if not raw:
            out.extend(lines[i:j]); i = j; continue
        ev = normalise(raw)
        out.append(" " * ind + "events:" + (f"  {m.group(2)}" if m.group(2) else ""))
        for k, v in ev.items():
            body = yaml.safe_dump(FlowMap(v), default_flow_style=None, sort_keys=False, width=10_000).strip()
            out.append(" " * (ind + 2) + f"{k}: {body}")
        i = j
    return "\n".join(out)


def _rewrite_block(text: str, key: str, convert) -> str:
    """Replace every ``<key>:`` block of a YAML text by ``convert(value)`` --
    a list of ``(name, flow_dict)`` written one per line -- leaving the rest."""
    import yaml
    lines = text.split("\n")
    out, i = [], 0
    rx = re.compile(r"^(\s*)" + re.escape(key) + r":\s*(#.*)?$")
    while i < len(lines):
        m = rx.match(lines[i])
        if not m:
            out.append(lines[i]); i += 1; continue
        ind = len(m.group(1))
        j = i + 1
        while j < len(lines):
            s = lines[j]
            if s.strip() == "":
                j += 1; continue
            k = len(s) - len(s.lstrip())
            if k > ind or (k == ind and s.lstrip().startswith("- ")):
                j += 1; continue
            break
        while j > i + 1 and lines[j - 1].strip() == "":
            j -= 1
        block = "\n".join(l[ind:] if len(l) >= ind else l for l in lines[i:j])
        raw = (yaml.safe_load(block) or {}).get(key)
        items = convert(raw) if raw else None
        if not items:
            out.extend(lines[i:j]); i = j; continue
        out.append(" " * ind + key + ":" + (f"  {m.group(2)}" if m.group(2) else ""))
        for name, v in items:
            body = yaml.safe_dump(FlowMap(v), default_flow_style=None, sort_keys=False,
                                  width=10_000).strip()
            out.append(" " * (ind + 2) + f"{name}: {body}")
        i = j
    return "\n".join(out)


def _scale_measurements_items(raw):
    if isinstance(raw, dict):
        return [(k, dict(v or {})) for k, v in raw.items()]
    return [(str(it["name"]), {k: v for k, v in it.items() if k != "name"}) for it in raw]


def migrate_scale_measurements(text: str) -> str:
    """``scale_measurements`` as a mapping, one line per measurement."""
    return _rewrite_block(text, "scale_measurements", _scale_measurements_items)
