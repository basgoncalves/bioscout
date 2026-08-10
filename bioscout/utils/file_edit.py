"""bioscout.utils.file_edit — one document model for every config file we edit.

BioScout's configuration is spread over three formats and the GUI had no way to
touch any of them:

* **YAML** — ``session.yaml`` (the source of truth for a session),
  ``config/default_config.yaml``, ``tps_personalise/data/config.yaml``
* **XML**  — OpenSim setup files, ``GRF.xml``, markersets, CEINMS setup/config
* **JSON** — ``load_credentials.json``, ``video_batch_settings.json``

This module is the format-agnostic layer the GUI editor sits on. Every format
gets the same shape::

    doc = load_document(path)       # -> YamlDocument | XmlDocument | JsonDocument
    doc.root                        # -> Node tree, for a treeview
    doc.fields_for(node)            # -> [Field, ...], for a properties form
    field.set("0.42")               # stage a change
    doc.save()                      # atomic write, .bak kept


Why YAML is not simply re-dumped
--------------------------------
``session.yaml`` carries load-bearing prose. The only record of why a trial was
dropped is a comment::

    # Walking_02 REMOVED 2026-08-04 — do NOT re-enable. All 10 SO reserve
    # actuators hit the 50 Nm cap in four of the six models...

``yaml.safe_dump`` deletes every one of those, reorders keys, expands flow maps
and turns ``0.00`` into ``0.0``. So this module never re-dumps YAML. It composes
the document with PyYAML to get the **exact character span of every scalar**,
then edits the original text in place, replacing only the spans that changed.
Everything else — comments, blank lines, key order, quoting, alignment, flow
style, number formatting — is preserved byte-for-byte because it is never
rewritten. A one-field change produces a one-token diff.

Nothing here imports a GUI toolkit, so it is testable headless.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field as _dc_field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom

import yaml

__all__ = [
    "Node", "Field", "Document", "YamlDocument", "XmlDocument", "JsonDocument",
    "load_document", "UnsupportedFormat", "EDITABLE_SUFFIXES",
    "describe_format", "BIG_FILE_BYTES",
]


class UnsupportedFormat(Exception):
    """The file's suffix maps to no structured editor."""


EDITABLE_SUFFIXES = {
    ".yaml": "yaml", ".yml": "yaml",
    ".xml": "xml", ".osim": "xml",
    ".json": "json",
}

# An .osim with 10k elements makes a treeview crawl; the GUI warns above this
# and offers raw-text mode instead of building the tree.
BIG_FILE_BYTES = 3 * 1024 * 1024


def describe_format(path) -> Optional[str]:
    """Return ``'yaml'`` / ``'xml'`` / ``'json'`` for *path*, else None."""
    return EDITABLE_SUFFIXES.get(Path(path).suffix.lower())


# --------------------------------------------------------------------------- #
# tree + form primitives
# --------------------------------------------------------------------------- #
@dataclass
class Node:
    """One row in the structure tree (left pane)."""
    label: str
    kind: str = "mapping"          # mapping | sequence | element
    ref: Any = None                # underlying object (yaml node, ET.Element, dict)
    parent: Optional["Node"] = None
    children: List["Node"] = _dc_field(default_factory=list)
    key: Any = None
    summary: str = ""

    def add(self, child: "Node") -> "Node":
        child.parent = self
        self.children.append(child)
        return child

    def path(self) -> Tuple[Any, ...]:
        out, n = [], self
        while n is not None and n.parent is not None:
            out.append(n.key)
            n = n.parent
        return tuple(reversed(out))

    def path_str(self) -> str:
        return ".".join(str(p) for p in self.path()) or "(root)"


@dataclass
class Field:
    """One editable scalar in the properties form (right pane)."""
    label: str
    value: str                     # display string
    kind: str = "text"             # text | multiline | bool | number | choice
    choices: Sequence[str] = ()
    help: str = ""
    comment: str = ""              # trailing "# ..." on the source line
    original: Any = None
    _setter: Optional[Callable[[Any], None]] = None

    def set(self, raw) -> None:
        """Stage *raw* (display string, or bool from a checkbox) as this field's value."""
        if self._setter is not None:
            self._setter(raw)


# --------------------------------------------------------------------------- #
# scalar helpers
# --------------------------------------------------------------------------- #
_BOOL_TRUE = {"true", "yes", "on"}
_BOOL_FALSE = {"false", "no", "off"}
_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_PLAIN_SAFE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./+\- ]*$")


def _display(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_display(v) for v in value)
    return str(value)


def _looks_bool(text: str) -> bool:
    return str(text).strip().lower() in (_BOOL_TRUE | _BOOL_FALSE)


def _parse_bool(text) -> bool:
    if isinstance(text, bool):
        return text
    return str(text).strip().lower() in _BOOL_TRUE


def _infer_kind(value, choices: Sequence[str]) -> str:
    if isinstance(value, bool) or _looks_bool(_display(value)):
        return "bool"
    if choices:
        return "choice"
    if isinstance(value, (int, float)):
        return "number"
    text = _display(value)
    if "\n" in text or len(text) > 90:
        return "multiline"
    return "text"


def _yaml_scalar_text(raw, original_text: str, tag: str) -> str:
    """Render *raw* as YAML source, matching how *original_text* was written.

    Keeping the original quoting matters: ``session: "25_03_31"`` must stay
    quoted or YAML reads it as the number 25 minus 3 minus 31.
    """
    if isinstance(raw, bool):
        return "true" if raw else "false"
    s = str(raw)
    was_dq = original_text.startswith('"') and original_text.endswith('"')
    was_sq = original_text.startswith("'") and original_text.endswith("'")
    if was_dq or was_sq:
        q = '"' if was_dq else "'"
        return q + s.replace("\\", "\\\\").replace(q, "\\" + q if q == '"' else q * 2) + q
    if s == "":
        return '""'
    plain = (_PLAIN_SAFE_RE.match(s)
             and not s.strip().startswith(("#", "&", "*", "!", "%", "@", "`")))
    if plain and tag.endswith(":str") and not _reparses_as_str(s):
        # The value IS a string, but written bare it would come back as
        # something else. YAML 1.1 has more of these than you'd guess:
        # 25_03_31 -> 250331 (underscores are digit separators), no -> False,
        # 1:30 -> 90, 0o17/0x1F -> ints. Quoting is the only safe answer.
        plain = False
    if plain:
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _reparses_as_str(s: str) -> bool:
    try:
        return yaml.safe_load(s) == s
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# base document
# --------------------------------------------------------------------------- #
class Document:
    """Common behaviour: load, tree, form, atomic save with backup."""

    format = "?"
    #: True when saving rewrites the whole file rather than patching spans.
    reformats_on_save = True

    def __init__(self, path):
        self.path = Path(path)
        self.root: Optional[Node] = None
        self.schema: Dict[str, Any] = {}
        self._value_index: Dict[str, set] = {}
        self._baseline = ""          # dumps() as it was when last loaded/saved
        self._disk_text = ""

    # -- subclass hooks ----------------------------------------------------- #
    def _parse(self, text: str) -> None:
        raise NotImplementedError

    def dumps(self) -> str:
        raise NotImplementedError

    def build_tree(self) -> Node:
        raise NotImplementedError

    def fields_for(self, node: Node) -> List[Field]:
        raise NotImplementedError

    def validate_text(self, text: str) -> Optional[str]:
        raise NotImplementedError

    # -- shared ------------------------------------------------------------- #
    def load(self) -> "Document":
        self._disk_text = self.path.read_text(encoding="utf-8")
        self._rebuild(self._disk_text)
        self._baseline = self.dumps()
        return self

    def _rebuild(self, text: str) -> None:
        self._parse(text)
        self.schema = schema_for(self.path)
        self._index_values()
        self.root = self.build_tree()

    def reload(self) -> "Document":
        return self.load()

    def mark_dirty(self) -> None:            # kept for setter call sites
        pass

    @property
    def dirty(self) -> bool:
        """True when the in-memory document differs from the last load/save."""
        try:
            return self.dumps() != self._baseline
        except Exception:
            return True

    def revert(self) -> None:
        """Throw away every unsaved change."""
        self._rebuild(self._disk_text)
        self._baseline = self.dumps()

    def diff(self) -> str:
        """Unified diff of unsaved changes, for the Changes pane."""
        import difflib
        try:
            new = self.dumps()
        except Exception as exc:
            return f"(cannot render: {type(exc).__name__}: {exc})"
        if new == self._baseline:
            return ""
        return "".join(difflib.unified_diff(
            self._baseline.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=self.path.name + "  (saved)",
            tofile=self.path.name + "  (after save)", n=2))

    def raw_text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def save(self, path=None, backup: bool = True, text: Optional[str] = None) -> Path:
        """Write the document. Atomic: temp file first, then ``os.replace``.

        An exception mid-write leaves the original intact rather than half a
        file, which the pipeline would read happily and then fail on somewhere
        unrelated.
        """
        target = Path(path) if path else self.path
        payload = self.dumps() if text is None else text
        err = self.validate_text(payload)
        if err:
            raise ValueError(f"refusing to write invalid {self.format}: {err}")
        if backup and target.is_file():
            try:
                shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
            except Exception:
                pass
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8", newline="")
        os.replace(tmp, target)
        self.path = target
        self._disk_text = payload
        self._rebuild(payload)
        self._baseline = self.dumps()
        return target

    # -- dropdown inference ------------------------------------------------- #
    def _index_values(self) -> None:
        self._value_index = {}

    def choices_for(self, key, value=None) -> Sequence[str]:
        """Offer a combobox where a key behaves like an enumeration.

        A key taking a handful of distinct values across the file (``side``:
        left/right/both) is an enum in practice, and a free-text box is where a
        typo silently becomes a new category.
        """
        sch = (self.schema.get("fields") or {}).get(str(key), {})
        opts = list(sch.get("choices") or [])
        if not opts:
            seen = self._value_index.get(str(key)) or set()
            if 2 <= len(seen) <= 12:
                opts = sorted(seen, key=str)
        if opts:
            cur = _display(value)
            if cur and cur not in opts:
                opts = opts + [cur]
        return opts

    def help_for(self, key) -> str:
        return ((self.schema.get("fields") or {}).get(str(key), {})).get("help", "")

    def problems(self) -> List[str]:
        """Semantic checks beyond 'does it parse'."""
        return []


# --------------------------------------------------------------------------- #
# YAML — span-patching, never re-dumped
# --------------------------------------------------------------------------- #
class YamlDocument(Document):
    format = "yaml"
    reformats_on_save = False

    def __init__(self, path):
        super().__init__(path)
        self.text = ""
        self.ynode = None                       # composed yaml node tree
        self.data = {}                          # plain python values
        self._edits: Dict[Tuple[int, int], str] = {}
        self._inserts: List[Tuple[int, str]] = []

    # -- parse -------------------------------------------------------------- #
    def _parse(self, text: str) -> None:
        self.text = text
        self.ynode = yaml.compose(text)
        self.data = yaml.safe_load(text) or {}
        self._edits, self._inserts = {}, []

    def dumps(self) -> str:
        """Apply staged span edits to the original source, right-to-left."""
        out = self.text
        ops = [(s, e, r) for (s, e), r in self._edits.items()]
        ops += [(pos, pos, txt) for pos, txt in self._inserts]
        for start, end, repl in sorted(ops, key=lambda o: o[0], reverse=True):
            out = out[:start] + repl + out[end:]
        return out

    def validate_text(self, text: str) -> Optional[str]:
        try:
            yaml.safe_load(text)
            return None
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def apply_staged(self) -> None:
        """Fold staged span edits into the working text and re-compose.

        Structural edits (add/duplicate/delete) shift every span after them, so
        the node marks must be recomputed before the next edit is staged —
        otherwise the second edit patches the wrong characters.
        """
        new = self.dumps()
        if new != self.text:
            self._rebuild(new)

    # -- indexing ----------------------------------------------------------- #
    def _index_values(self) -> None:
        idx: Dict[str, set] = {}

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        walk(v)
                    elif v is not None and not isinstance(v, bool):
                        idx.setdefault(str(k), set()).add(_display(v))
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)
        walk(self.data)
        self._value_index = idx

    # -- tree --------------------------------------------------------------- #
    def build_tree(self) -> Node:
        root = Node(label=self.path.name, kind="mapping", ref=self.ynode)
        if self.ynode is not None:
            self._build(root, self.ynode)
        return root

    def _build(self, parent: Node, ynode) -> None:
        # Only containers become tree rows; scalars are FIELDS on their parent,
        # so editing one is a single click rather than a drill-down.
        if isinstance(ynode, yaml.MappingNode):
            for knode, vnode in ynode.value:
                if isinstance(vnode, yaml.MappingNode):
                    n = parent.add(Node(str(knode.value), "mapping", vnode,
                                        key=knode.value,
                                        summary=f"{len(vnode.value)} keys"))
                    self._build(n, vnode)
                elif isinstance(vnode, yaml.SequenceNode) and \
                        any(not isinstance(i, yaml.ScalarNode) for i in vnode.value):
                    n = parent.add(Node(str(knode.value), "sequence", vnode,
                                        key=knode.value,
                                        summary=f"{len(vnode.value)} items"))
                    self._build(n, vnode)
        elif isinstance(ynode, yaml.SequenceNode):
            for i, vnode in enumerate(ynode.value):
                if isinstance(vnode, yaml.MappingNode):
                    label = f"[{i}]"
                    for knode, vv in vnode.value:
                        if knode.value in ("name", "id") and isinstance(vv, yaml.ScalarNode):
                            label = str(vv.value)
                            break
                    n = parent.add(Node(label, "mapping", vnode, key=i))
                    self._build(n, vnode)
                elif isinstance(vnode, yaml.SequenceNode):
                    n = parent.add(Node(f"[{i}]", "sequence", vnode, key=i))
                    self._build(n, vnode)

    # -- form --------------------------------------------------------------- #
    def fields_for(self, node: Node) -> List[Field]:
        ynode, out = node.ref, []
        if isinstance(ynode, yaml.MappingNode):
            for knode, vnode in ynode.value:
                if isinstance(vnode, yaml.ScalarNode):
                    out.append(self._field(str(knode.value), vnode))
                elif isinstance(vnode, yaml.SequenceNode) and \
                        all(isinstance(i, yaml.ScalarNode) for i in vnode.value):
                    out.append(self._seq_field(str(knode.value), vnode))
        elif isinstance(ynode, yaml.SequenceNode):
            for i, vnode in enumerate(ynode.value):
                if isinstance(vnode, yaml.ScalarNode):
                    out.append(self._field(f"[{i}]", vnode))
        return out

    def _value_of(self, vnode) -> Any:
        try:
            return yaml.safe_load(self.text[vnode.start_mark.index:vnode.end_mark.index])
        except Exception:
            return vnode.value

    @staticmethod
    def _shown(src: str, value) -> str:
        """What the form should display for a scalar written as *src*.

        For an unquoted scalar this is the source text itself, NOT the parsed
        value. That difference matters: ``time_range: [0.00, 3.54]`` parses to
        0.0, and showing "0.0" would make an untouched field re-render as
        ``0.0`` on the next flush — so merely opening a file and pressing Save
        would reformat numbers all over it. Echoing the source makes an
        unedited field a no-op by construction.
        Quoted scalars still show the parsed value, so escapes read normally;
        the writer re-applies the same quoting, which is equally identity.
        """
        st = src.strip()
        if st[:1] in ('"', "'"):
            return _display(value)
        return st

    def _field(self, label: str, vnode) -> Field:
        span = (vnode.start_mark.index, vnode.end_mark.index)
        src = self.text[span[0]:span[1]]
        value = self._value_of(vnode)
        key = label.lstrip("@")
        choices = self.choices_for(key, value)

        def setter(raw, _span=span, _src=src, _tag=vnode.tag):
            new = _yaml_scalar_text(raw, _src, _tag)
            if new == _src:
                self._edits.pop(_span, None)
            else:
                self._edits[_span] = new

        return Field(label=label, value=self._shown(src, value),
                     kind=_infer_kind(value, choices), choices=choices,
                     help=self.help_for(key),
                     comment=self._trailing_comment(vnode.end_mark.index),
                     original=value, _setter=setter)

    def _seq_field(self, label: str, snode) -> Field:
        """A flat list (``[0.07, 1.16]``, ``[a, b, c]``) edited as one comma field."""
        items = [self.text[i.start_mark.index:i.end_mark.index] for i in snode.value]
        value = [self._value_of(i) for i in snode.value]
        span = (snode.start_mark.index, snode.end_mark.index)
        src = self.text[span[0]:span[1]]
        flow = src.lstrip().startswith("[")
        tags = [i.tag for i in snode.value]
        choices = self.choices_for(label, None)

        def setter(raw, _span=span, _src=src, _flow=flow, _tags=tags,
                   _items=items, _orig=value):
            parts = [p.strip() for p in str(raw).split(",")]
            parts = [p for p in parts if p != ""]
            try:
                if [yaml.safe_load(p) for p in parts] == _orig:
                    # Same values, possibly retyped by hand — leave the source
                    # spacing and 0.00-style formatting exactly as written.
                    self._edits.pop(_span, None)
                    return
            except Exception:
                pass
            rendered = [
                _yaml_scalar_text(p, _items[i] if i < len(_items) else "",
                                  _tags[i] if i < len(_tags) else "tag:yaml.org,2002:str")
                for i, p in enumerate(parts)
            ]
            if _flow or not rendered:
                new = "[" + ", ".join(rendered) + "]"
            else:
                indent = " " * (_src.index(_src.lstrip()[0]) if _src.strip() else 2)
                new = ("\n" + indent + "- ").join([""] + rendered)[1:]
            if new == _src:
                self._edits.pop(_span, None)
            else:
                self._edits[_span] = new

        return Field(label=label,
                     value=", ".join(self._shown(s, v)
                                     for s, v in zip(items, value)),
                     kind="text", choices=choices, help=self.help_for(label),
                     comment=self._trailing_comment(snode.end_mark.index),
                     original=value, _setter=setter)

    def _trailing_comment(self, idx: int) -> str:
        """The ``# ...`` after position *idx* on the same line, as a form hint."""
        nl = self.text.find("\n", idx)
        tail = self.text[idx:nl if nl != -1 else len(self.text)]
        h = tail.find("#")
        return tail[h + 1:].strip() if h != -1 else ""

    # -- structural edits --------------------------------------------------- #
    def _line_bounds(self, idx: int) -> Tuple[int, int]:
        start = self.text.rfind("\n", 0, idx) + 1
        end = self.text.find("\n", idx)
        return start, (len(self.text) if end == -1 else end + 1)

    def map_node(self, *keys):
        """The :class:`yaml.MappingNode` at ``keys``, or None.

        Lets callers outside the GUI (e.g. the Trial Analysis tab) patch one
        block of a session.yaml without walking the node tree themselves.
        """
        node = self.ynode
        for k in keys:
            if not isinstance(node, yaml.MappingNode):
                return None
            node = next((v for kn, v in node.value if str(kn.value) == str(k)), None)
            if node is None:
                return None
        return node

    def has_entry(self, map_node, key) -> bool:
        return any(str(kn.value) == str(key) for kn, _ in (map_node.value or []))

    def set_entry_source(self, map_node, key, value_src: str) -> None:
        """Replace ``key``'s VALUE with raw YAML *value_src* (add it if absent).

        Only the value span is touched, so a trailing ``# comment`` on that
        line — and every other line in the file — is left alone.
        """
        for knode, vnode in map_node.value:
            if str(knode.value) != str(key):
                continue
            self._edits[(vnode.start_mark.index, vnode.end_mark.index)] = value_src
            self.apply_staged()
            return
        self.add_entry(map_node, str(key), value_src)

    def ensure_mapping(self, key: str):
        """Return the top-level mapping at *key*, creating ``key: {}`` if absent."""
        node = self.map_node(key)
        if isinstance(node, yaml.MappingNode):
            return node
        if node is None:
            self.add_entry(self.ynode, key, "{}")
            return self.map_node(key)
        raise ValueError(f"'{key}' exists but is not a mapping")

    def entry_source(self, map_node, key) -> Optional[str]:
        """The raw source lines of ``key`` within *map_node* (block style only)."""
        for knode, vnode in map_node.value:
            if str(knode.value) != str(key):
                continue
            s, _ = self._line_bounds(knode.start_mark.index)
            _, e = self._line_bounds(max(vnode.end_mark.index - 1, knode.start_mark.index))
            return self.text[s:e]
        return None

    def add_entry(self, map_node, key: str, value_src: str = "{}") -> None:
        """Append ``key: value_src`` to *map_node*, matching its indentation."""
        if map_node.flow_style:
            close = self.text.rfind("}", 0, map_node.end_mark.index)
            inner = self.text[map_node.start_mark.index + 1:close].strip()
            sep = ", " if inner else ""
            self._inserts.append((close, f"{sep}{key}: {value_src}"))
            self.apply_staged()
            return
        else:
            if map_node.value:
                first_key = map_node.value[0][0]
                indent = " " * first_key.start_mark.column
                last_val = map_node.value[-1][1]
                _, end = self._line_bounds(max(last_val.end_mark.index - 1, 0))
            else:
                indent, end = "  ", map_node.end_mark.index
            block = f"{indent}{key}: {value_src}\n"
            self._inserts.append((end, block))
        self.apply_staged()

    def duplicate_entry(self, map_node, key, new_key: str) -> None:
        """Copy ``key``'s source block under *new_key* — how you add a trial."""
        src = self.entry_source(map_node, key)
        if src is None:
            raise KeyError(key)
        first_line, _, rest = src.partition("\n")
        stripped = first_line.lstrip()
        indent = first_line[:len(first_line) - len(stripped)]
        _, _, after_key = stripped.partition(":")
        block = f"{indent}{new_key}:{after_key}\n" + (rest if rest else "")
        last_val = map_node.value[-1][1]
        _, end = self._line_bounds(max(last_val.end_mark.index - 1, 0))
        self._inserts.append((end, block))
        self.apply_staged()

    def delete_entry(self, map_node, key) -> None:
        """Remove ``key`` from *map_node* (block style: whole lines)."""
        for knode, vnode in map_node.value:
            if str(knode.value) != str(key):
                continue
            if map_node.flow_style:
                raise ValueError("cannot delete from an inline {a: 1, b: 2} "
                                 "mapping — edit it as text instead")
            s, _ = self._line_bounds(knode.start_mark.index)
            _, e = self._line_bounds(max(vnode.end_mark.index - 1, knode.start_mark.index))
            self._edits[(s, e)] = ""
            self.apply_staged()
            return
        raise KeyError(key)

    # -- semantic checks ---------------------------------------------------- #
    def problems(self) -> List[str]:
        out: List[str] = []
        try:
            data = yaml.safe_load(self.dumps()) or {}
        except Exception as exc:
            return [f"does not parse: {exc}"]
        if not isinstance(data, dict):
            return out
        trials = data.get("trials")
        if isinstance(trials, dict):
            for name, blk in trials.items():
                if not isinstance(blk, dict):
                    continue
                tr = blk.get("time_range")
                if isinstance(tr, (list, tuple)) and len(tr) == 2:
                    try:
                        a, b = float(tr[0]), float(tr[1])
                        if b <= a:
                            out.append(f"trials.{name}.time_range: end ({b}) is "
                                       f"not after start ({a})")
                    except (TypeError, ValueError):
                        out.append(f"trials.{name}.time_range: not two numbers ({tr!r})")
                elif tr:
                    out.append(f"trials.{name}.time_range: expected [start, end], got {tr!r}")
                side = blk.get("side")
                if side is not None and str(side) not in ("left", "right", "both"):
                    out.append(f"trials.{name}.side: '{side}' is not left/right/both")
        static = data.get("static_trial")
        if static and isinstance(trials, dict) and static not in trials:
            out.append(f"static_trial '{static}' has no entry under trials:")
        for t in (data.get("calibration_trials") or []):
            if isinstance(trials, dict) and isinstance(t, str) and t not in trials:
                out.append(f"calibration_trials: '{t}' has no entry under trials:")
        iters = data.get("iterations")
        if isinstance(iters, dict):
            sdir = self.path.parent
            for name, blk in iters.items():
                if not isinstance(blk, dict):
                    continue
                for k in ("so_model", "ceinms_model", "session_model"):
                    rel = blk.get(k)
                    if rel and not self._iteration_file_exists(sdir, name, str(rel)):
                        out.append(f"iterations.{name}.{k}: '{rel}' not found "
                                   f"in {name}/ — has this model been scaled yet?")
        return out

    @staticmethod
    def _iteration_file_exists(session_dir: Path, iteration: str, rel: str) -> bool:
        """Resolve a model path the way ``utils.session_layout`` does.

        Models live at ``<session>/3_iterations/<iteration>/<file>``; older
        sessions keep the iteration folder directly under the session. Checking
        only one of those reported every model as missing.
        """
        for base in (session_dir / "3_iterations" / iteration,
                     session_dir / iteration,
                     session_dir / "models",
                     session_dir):
            if (base / rel).exists():
                return True
        return False


# --------------------------------------------------------------------------- #
# XML
# --------------------------------------------------------------------------- #
class XmlDocument(Document):
    format = "xml"
    reformats_on_save = True

    def __init__(self, path):
        super().__init__(path)
        self.xml_root: Optional[ET.Element] = None
        self._declaration = ""

    def _parse(self, text: str) -> None:
        m = re.match(r"\s*(<\?xml[^>]*\?>)", text)
        self._declaration = m.group(1) if m else ""
        # insert_comments keeps <!-- ... --> nodes, which plain ET.fromstring
        # silently drops — OpenSim setup files use them to explain units.
        try:
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
            parser.feed(text)
            self.xml_root = parser.close()
        except (TypeError, ValueError):
            self.xml_root = ET.fromstring(text)

    def dumps(self) -> str:
        raw = ET.tostring(self.xml_root, encoding="unicode")
        try:
            pretty = minidom.parseString(raw).toprettyxml(indent="\t")
            lines = [ln for ln in pretty.split("\n") if ln.strip()]
            if lines and lines[0].lstrip().startswith("<?xml"):
                lines = lines[1:]
            body = "\n".join(lines).strip()
        except Exception:
            body = raw.strip()
        head = self._declaration or '<?xml version="1.0" encoding="UTF-8" ?>'
        return head + "\n" + body + "\n"

    def validate_text(self, text: str) -> Optional[str]:
        try:
            ET.fromstring(text)
            return None
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def _index_values(self) -> None:
        idx: Dict[str, set] = {}
        for elem in self.xml_root.iter():
            if not isinstance(elem.tag, str):
                continue
            for attr, val in elem.attrib.items():
                if val.strip():
                    idx.setdefault(attr, set()).add(val.strip())
            if elem.text and elem.text.strip() and len(elem) == 0:
                idx.setdefault(elem.tag, set()).add(elem.text.strip())
        self._value_index = idx

    def build_tree(self) -> Node:
        root = Node(self.xml_root.tag, "element", self.xml_root)
        self._add_children(root, self.xml_root)
        return root

    def _add_children(self, parent: Node, elem: ET.Element) -> None:
        for i, child in enumerate(elem):
            if not isinstance(child.tag, str):     # comment / PI
                continue
            if len(child) == 0:                    # leaf -> field on this element
                continue
            label = child.tag
            name = child.get("name") or child.get("id")
            if name:
                label += f"  [{name}]"
            n = parent.add(Node(label, "element", child, key=i,
                                summary=f"{len(child)}"))
            self._add_children(n, child)

    def fields_for(self, node: Node) -> List[Field]:
        elem: ET.Element = node.ref
        out: List[Field] = []

        for attr, val in elem.attrib.items():
            choices = self.choices_for(attr, val)

            def set_attr(v, _e=elem, _a=attr):
                _e.set(_a, "" if v is None else _display(v))
                self.mark_dirty()
            out.append(Field(f"@{attr}", val, _infer_kind(val, choices), choices,
                             self.help_for(attr), original=val, _setter=set_attr))

        if elem.text and elem.text.strip() and len(elem) == 0:
            txt = elem.text.strip()
            choices = self.choices_for(elem.tag, txt)

            def set_text(v, _e=elem):
                _e.text = "" if v is None else _display(v)
                self.mark_dirty()
            out.append(Field("(text)", txt, _infer_kind(txt, choices), choices,
                             self.help_for(elem.tag), original=txt, _setter=set_text))

        for child in elem:
            if not isinstance(child.tag, str) or len(child) > 0:
                continue
            txt = (child.text or "").strip()
            label = child.tag
            if child.get("name"):
                label += f" [{child.get('name')}]"
            choices = self.choices_for(child.tag, txt)

            def set_child(v, _c=child):
                _c.text = "" if v is None else _display(v)
                self.mark_dirty()
            out.append(Field(label, txt, _infer_kind(txt, choices), choices,
                             self.help_for(child.tag), original=txt, _setter=set_child))
        return out


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #
class JsonDocument(Document):
    format = "json"
    reformats_on_save = True

    def __init__(self, path):
        super().__init__(path)
        self.data: Any = {}

    def _parse(self, text: str) -> None:
        self.data = json.loads(text) if text.strip() else {}

    def dumps(self) -> str:
        return json.dumps(self.data, indent=2, ensure_ascii=False) + "\n"

    def validate_text(self, text: str) -> Optional[str]:
        try:
            json.loads(text)
            return None
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def _index_values(self) -> None:
        idx: Dict[str, set] = {}

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        walk(v)
                    elif v is not None and not isinstance(v, bool):
                        idx.setdefault(str(k), set()).add(_display(v))
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)
        walk(self.data)
        self._value_index = idx

    def build_tree(self) -> Node:
        root = Node(self.path.name, "mapping", self.data)
        self._build(root, self.data)
        return root

    def _build(self, parent: Node, obj) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict):
                    n = parent.add(Node(str(k), "mapping", v, key=k,
                                        summary=f"{len(v)} keys"))
                    self._build(n, v)
                elif isinstance(v, list) and any(isinstance(i, (dict, list)) for i in v):
                    n = parent.add(Node(str(k), "sequence", v, key=k,
                                        summary=f"{len(v)} items"))
                    self._build(n, v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, dict):
                    n = parent.add(Node(str(v.get("name") or f"[{i}]"), "mapping",
                                        v, key=i))
                    self._build(n, v)
                elif isinstance(v, list):
                    n = parent.add(Node(f"[{i}]", "sequence", v, key=i))
                    self._build(n, v)

    def fields_for(self, node: Node) -> List[Field]:
        obj, out = node.ref, []
        items = obj.items() if isinstance(obj, dict) else enumerate(obj)
        for k, v in items:
            if isinstance(v, dict):
                continue
            if isinstance(v, list) and any(isinstance(i, (dict, list)) for i in v):
                continue
            choices = self.choices_for(k, v)
            proto = v

            def setter(raw, _c=obj, _k=k, _p=proto):
                _c[_k] = _json_coerce(raw, _p)
                self.mark_dirty()
            out.append(Field(str(k), _display(v), _infer_kind(v, choices), choices,
                             self.help_for(k), original=v, _setter=setter))
        return out


def _json_coerce(raw, proto):
    if isinstance(proto, bool):
        return _parse_bool(raw)
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip()
    if isinstance(proto, (list, tuple)):
        return [p.strip() for p in str(raw).split(",") if p.strip()]
    if isinstance(proto, int) and not isinstance(proto, bool):
        return int(s) if s.lstrip("+-").isdigit() else s
    if isinstance(proto, float):
        try:
            return float(s)
        except ValueError:
            return s
    return raw


# --------------------------------------------------------------------------- #
# per-file schema hints (choices + help shown in the form)
# --------------------------------------------------------------------------- #
_SESSION_YAML_SCHEMA = {
    "title": "Session configuration",
    "fields": {
        "subject":      {"help": "Athlete folder name under simulations/."},
        "session":      {"help": "Session folder name, usually YY_MM_DD."},
        "body_mass":    {"help": "Session-level mass in kg, from the static "
                                 "trial (mean vertical GRF / g)."},
        "static_trial": {"help": "Trial used for scaling and body mass. Must "
                                 "also appear under trials:."},
        "markerset":    {"help": "Markerset XML, relative to the session folder."},
        "type":         {"choices": ["static", "squat", "deadlift", "walking",
                                     "running", "jump", "bench", "other"],
                         "help": "Trial type — drives event detection and which "
                                 "analyses run."},
        "side":         {"choices": ["both", "left", "right"],
                         "help": "Limb of interest. 'both' analyses each side."},
        "time_range":   {"help": "[start, end] in seconds. Empty means the whole "
                                 "capture — no cropping."},
        "color":        {"choices": ["black", "red", "blue", "green", "orange",
                                     "purple", "grey", "magenta", "cyan"],
                         "help": "Plot colour for this model in summary figures."},
        "group":        {"choices": ["generic", "personalised", "mri"],
                         "help": "Model family, used to group summary plots."},
        "label":        {"help": "Legend text for this model in summary figures."},
        "linear_scaling": {"help": "ScaleTool ModelScaler — dimensional scaling on/off."},
        "marker_placer":  {"help": "ScaleTool MarkerPlacer — move markers onto "
                                   "the static trial."},
        "opt_neval":    {"help": "Modenese muscle-optimisation sampling points."},
        "mvic_factor":  {"help": "Isometric force multiplier applied after muscle-opt."},
        "alpha":        {"help": "CEINMS calibration weight — tracking term."},
        "beta":         {"help": "CEINMS calibration weight — regularisation."},
        "gamma":        {"help": "CEINMS calibration weight — EMG tracking."},
        "generic":      {"help": "Template .osim to scale from, relative to the "
                                 "shared 'generic models' library."},
        "session_model": {"help": "Already-personalised .osim (MRI/TPS). If set, "
                                  "geometric scaling is skipped."},
        "so_model":     {"help": ".osim used for static optimisation."},
        "ceinms_model": {"help": ".osim used for CEINMS."},
        "calibration_trials":   {"help": "Trials CEINMS calibrates on."},
        "normalisation_trials": {"help": "Trials spanned for EMG MVC "
                                         "normalisation, or 'all'."},
    },
}

_SCHEMAS = {
    "session.yaml": _SESSION_YAML_SCHEMA,
    "default_config.yaml": {"title": "Application defaults", "fields": {}},
}


def schema_for(path) -> Dict[str, Any]:
    return _SCHEMAS.get(Path(path).name, {"fields": {}})


def flow_map(mapping: Dict[str, Any]) -> str:
    """Render *mapping* as an inline ``{a: 1, b: [2, 3]}`` YAML value.

    session.yaml writes every trial as a one-line flow map, so patching one in
    this shape keeps the file looking like a human wrote it.
    """
    def render(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(render(i) for i in v) + "]"
        if isinstance(v, dict):
            return flow_map(v)
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return repr(v)
        return _yaml_scalar_text(str(v), "", "tag:yaml.org,2002:str")
    return "{" + ", ".join(f"{k}: {render(v)}" for k, v in mapping.items()) + "}"


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
_CLASSES = {"yaml": YamlDocument, "xml": XmlDocument, "json": JsonDocument}


def load_document(path) -> Document:
    """Open *path* as a structured document.

    Raises :class:`UnsupportedFormat` for a suffix with no editor — the GUI
    catches that and falls back to plain-text editing.
    """
    fmt = describe_format(path)
    if fmt is None:
        raise UnsupportedFormat(
            f"'{Path(path).suffix or 'no suffix'}' has no structured editor — "
            f"open it as text instead.")
    return _CLASSES[fmt](path).load()
