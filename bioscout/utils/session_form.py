"""The model behind the session editor: read a ``session.yaml``, edit it safely.

Separate from the dialog on purpose. Everything that can silently corrupt a
session lives here and is unit-tested; the GUI on top is only widgets.

The rule that shapes this module
--------------------------------
``session.yaml`` is hand-written and **carries comments that explain the study**
— the FAIS files open with six lines on why there is one CEINMS calibration per
fatigue state. Round-tripping through ``yaml.safe_load`` + ``yaml.dump`` loses
every one of them, reorders keys, and reformats values, and the loss is silent
and unrecoverable. So nothing here ever re-dumps: edits go through
:class:`bioscout.utils.file_edit.YamlDocument`, which patches the character span
of the value being changed and leaves every other byte alone.

What it checks
--------------
The red flags are the things that make a run fail hours later, or — worse —
succeed on the wrong data:

* no c3d files in ``1_c3dfiles/`` (there is nothing to run)
* ``static_trial`` naming a trial that does not exist (scaling has nothing to measure)
* calibration or normalisation trials that are not in the session
* trials in the yaml with no matching c3d, and c3d files no trial refers to
* a duplicate ``emg_map`` key — YAML keeps the last silently, and the run then
  reads the wrong electrode
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["SessionForm", "TRIAL_TYPES", "SCALAR_FIELDS",
           "ITERATION_FIELDS", "EMG_FILTER_FIELDS"]

#: Offered in the per-trial dropdown. Free text is still accepted — a lab with a
#: task this list does not name should not be blocked by a combobox.
TRIAL_TYPES = ("static", "running", "walking", "cut", "jump", "squat",
               "generic", "calibration")

#: (key, label, kind) for the plain scalars, in the order the form shows them.
SCALAR_FIELDS = (
    ("subject", "subject", "text"),
    ("session", "session", "text"),
    ("body_mass", "body mass (kg)", "number"),
    ("markerset", "markerset", "text"),
    ("setup_folder", "setup folder", "text"),
    ("c3d_source", "c3d source", "text"),
)

#: (key, label, kind, default) for one iteration block. `prescaled` and
#: `linear_scaling` are the pair that decides whether bioscout scales the model
#: again — get them wrong and you silently scale an already-scaled model.
ITERATION_FIELDS = (
    ("generic", "generic model", "text", ""),
    ("so_model", "SO model", "text", ""),
    ("ceinms_model", "CEINMS model", "text", ""),
    ("calibration", "calibration config", "text", ""),
    ("calibrated", "calibrated", "bool", True),
    ("prescaled", "prescaled", "bool", False),
    ("linear_scaling", "linear scaling", "bool", True),
    ("opt_neval", "opt_neval", "number", 10),
    ("mvic_factor", "mvic_factor", "number", 3.0),
    ("label", "label", "text", ""),
    ("color", "colour", "text", ""),
    ("group", "group", "text", ""),
)

#: EMG filter block. Defaults mirror bioscout.utils.emg_filter.DEFAULTS, which
#: are exactly the values the code used before the block existed.
EMG_FILTER_FIELDS = (
    ("bandpass_low", "band-pass low (Hz)", 20.0),
    ("bandpass_high", "band-pass high (Hz)", 95.0),
    ("bandpass_order", "band-pass order", 4),
    ("envelope_lowpass", "envelope low-pass (Hz)", 6.0),
    ("envelope_order", "envelope order", 4),
)

_C3D_DIRS = ("1_c3dfiles", "")


class SessionForm:
    """One session's editable state, backed by a surgical YAML patcher."""

    def __init__(self, session_dir):
        self.dir = Path(session_dir)
        self.path = self.dir / "session.yaml"
        self.exists = self.path.is_file()
        self.doc = None
        self.data: Dict[str, Any] = {}
        if self.exists:
            self.reload()

    # -- loading ------------------------------------------------------------ #
    def reload(self) -> "SessionForm":
        from bioscout.utils.file_edit import load_document
        import yaml
        self.doc = load_document(self.path)
        self.data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.exists = True
        return self

    # -- what is on disk ---------------------------------------------------- #
    def c3d_dir(self) -> Optional[Path]:
        for sub in _C3D_DIRS:
            d = self.dir / sub if sub else self.dir
            if d.is_dir() and any(d.glob("*.c3d")):
                return d
        return self.dir / "1_c3dfiles"

    def c3d_trials(self) -> List[str]:
        """Trial names taken from the c3d filenames, sorted."""
        d = self.c3d_dir()
        if d is None or not d.is_dir():
            return []
        return sorted(p.stem for p in d.glob("*.c3d"))

    def trials(self) -> List[str]:
        """Every trial name the session knows: the yaml's, then any extra c3d."""
        named = list((self.data.get("trials") or {}).keys())
        extra = [t for t in self.c3d_trials() if t not in named]
        return named + extra

    def trial_types(self) -> Dict[str, str]:
        block = self.data.get("trials") or {}
        out = {}
        for name in self.trials():
            entry = block.get(name)
            out[name] = (entry or {}).get("type", "") if isinstance(entry, dict) else ""
        return out

    def value(self, key, default=None):
        return self.data.get(key, default)

    def list_value(self, key) -> List[str]:
        v = self.data.get(key) or []
        return [str(x) for x in v] if isinstance(v, list) else []

    # -- red flags ---------------------------------------------------------- #
    def problems(self) -> List[str]:
        """Human-readable blockers and warnings, worst first. Empty is good."""
        out: List[str] = []
        c3ds = self.c3d_trials()
        d = self.c3d_dir()

        if not c3ds:
            where = d if d else self.dir / "1_c3dfiles"
            out.append(f"NO C3D FILES in {where.name}/ — there is nothing to run. "
                       f"Copy the session's captures in first.")

        if self.exists:
            known = set(self.trials())
            static = self.value("static_trial")
            if not static:
                out.append("no static_trial set — scaling has nothing to measure the "
                           "segments between")
            elif static not in known:
                out.append(f"static_trial '{static}' is not a trial in this session")

            for key in ("calibration_trials", "normalisation_trials"):
                missing = [t for t in self.list_value(key) if t not in known]
                if missing:
                    out.append(f"{key}: {', '.join(missing[:4])}"
                               f"{'...' if len(missing) > 4 else ''} not in this session")

            named = set((self.data.get("trials") or {}).keys())
            no_c3d = sorted(named - set(c3ds))
            if c3ds and no_c3d:
                out.append(f"{len(no_c3d)} trial(s) in the yaml have no c3d: "
                           f"{', '.join(no_c3d[:4])}{'...' if len(no_c3d) > 4 else ''}")
            unlisted = sorted(set(c3ds) - named)
            if named and unlisted:
                out.append(f"{len(unlisted)} c3d file(s) are not listed under trials: "
                           f"{', '.join(unlisted[:4])}{'...' if len(unlisted) > 4 else ''}")

            dup = self.duplicate_emg_keys()
            if dup:
                out.append(f"DUPLICATE emg_map key(s): {', '.join(dup)} — YAML keeps "
                           f"only the last, so the run would read the wrong electrode")
        return out

    def duplicate_emg_keys(self) -> List[str]:
        """Repeated keys under ``emg_map``. ``safe_load`` cannot see these.

        A duplicate is legal YAML and resolves to the last occurrence, so the
        parsed document looks fine while the file says something else. The only
        way to catch it is to read the source.
        """
        if not self.path.is_file():
            return []
        text = self.path.read_text(encoding="utf-8")
        m = re.search(r"^emg_map:[ \t]*$", text, re.M)
        if not m:
            return []
        seen, dup = set(), []
        for line in text[m.end():].splitlines():
            if line.strip() and not line.startswith((" ", "\t")):
                break                                   # next top-level key
            km = re.match(r"^  (\S[^:]*):", line)
            if not km:
                continue
            key = km.group(1)
            (dup.append(key) if key in seen else seen.add(key))
        return sorted(set(dup))

    # -- edits (surgical; nothing else in the file moves) -------------------- #
    def _root(self):
        return self.doc.ynode

    def _value_node(self, key):
        for knode, vnode in (self._root().value or []):
            if str(knode.value) == str(key):
                return vnode
        return None

    def set_scalar(self, key: str, value) -> None:
        """Set a top-level scalar, keeping its type.

        The tag comes from the node already in the file, so ``body_mass: 89.4``
        stays a number instead of becoming the string ``"75.2"`` — which parses,
        looks right in a diff, and then fails a comparison somewhere downstream.
        """
        from bioscout.utils.file_edit import _yaml_scalar_text
        node = self._value_node(key)
        old_src = self.doc.entry_source(self._root(), key) or ""
        tag = getattr(node, "tag", None) or "tag:yaml.org,2002:str"
        src = _yaml_scalar_text(value, old_src, tag)
        self.doc.set_entry_source(self._root(), key, src)

    def _block_seq_span(self, node):
        """True character span of a block sequence, last item's line included.

        PyYAML's ``end_mark`` for a block sequence sits at the START OF THE NEXT
        TOKEN — the file only reveals the list ended once something appears at a
        shallower indent. Patching that span therefore overwrites the following
        key's line: shrinking a two-item list produced ``- HAB2emg_map:`` and
        silently deleted the list AND the key after it. Clamp to the end of the
        last item's own line instead.
        """
        text = self.doc.text
        last = node.value[-1]
        end = text.find("\n", last.end_mark.index)
        return (node.start_mark.index, len(text) if end == -1 else end)

    def set_list(self, key: str, items: Sequence[str]) -> None:
        """Replace a top-level list.

        Block style when the key already uses it, so a hand-formatted file keeps
        its shape; flow style (``[a, b]``) for a key being created, which is
        unambiguous wherever it is inserted.
        """
        import yaml as _yaml
        items = [str(i) for i in items]
        node = self._value_node(key)
        is_seq = isinstance(node, _yaml.SequenceNode)
        block = is_seq and bool(node.value) and \
            not self.doc.text[node.start_mark.index:].lstrip().startswith("[")

        if not items and block:
            # `key:\n[]` is not valid YAML — the empty list has to come back up
            # onto the key's own line, so the preceding newline is part of the
            # span being replaced.
            node_start = self.doc.text.rfind("\n", 0, node.start_mark.index)
            self.doc._edits[(node_start, self._block_seq_span(node)[1])] = " []"
            self.doc.apply_staged()
            return
        if not items:
            src = "[]"
        elif block:
            src = "\n".join(f"- {i}" for i in items)
        else:
            src = "[" + ", ".join(items) + "]"

        if block:
            self.doc._edits[self._block_seq_span(node)] = src
            self.doc.apply_staged()
        else:
            self.doc.set_entry_source(self._root(), key, src)

    def set_trial_type(self, trial: str, type_name: str) -> None:
        """Set ``trials.<trial>.type``, creating the trial entry if it is new."""
        self.set_trial_field(trial, "type", type_name)

    def set_trial_field(self, trial: str, key: str, value) -> None:
        """Set any key under ``trials.<trial>``, creating the trial if it is new.

        A list value is written in flow style — ``time_range: [3.415, 4.85]`` —
        which is how session.yaml already spells it and keeps the trial entry to
        two lines.
        """
        if isinstance(value, (list, tuple)):
            src = "[" + ", ".join(str(v) for v in value) + "]"
        elif isinstance(value, bool):
            src = "true" if value else "false"
        else:
            src = str(value)
        trials = self.doc.ensure_mapping("trials")
        if not self.doc.has_entry(trials, trial):
            self.doc.add_entry(trials, trial, f"\n    {key}: {src}")
            return
        for knode, vnode in trials.value:
            if str(knode.value) == trial:
                self.doc.set_entry_source(vnode, key, src)
                return

    def set_ceinms(self, **params) -> None:
        """Set keys under ``ceinms:``.

        The mapping node is re-fetched for every key: each write re-parses the
        document, which invalidates the character offsets held by any node
        grabbed earlier. Reusing one made the second edit land at the wrong
        place and produced unparseable YAML.
        """
        self.doc.ensure_mapping("ceinms")
        for k, v in params.items():
            if v not in (None, ""):
                self.doc.set_entry_source(self.doc.map_node("ceinms"), k, str(v))

    # -- iterations --------------------------------------------------------- #
    def iterations(self) -> Dict[str, dict]:
        blocks = self.data.get("iterations") or self.data.get("models") or {}
        return {k: (v or {}) for k, v in blocks.items()} if isinstance(blocks, dict) else {}

    def calibration_configs(self) -> List[str]:
        """Named calibration blocks, if `calibration:` holds names rather than
        bare parameters. An iteration's `calibration:` selects one of these."""
        cal = self.data.get("calibration")
        if not isinstance(cal, dict):
            return []
        named = [k for k, v in cal.items() if isinstance(v, dict)]
        return sorted(named)

    def set_iteration_field(self, iteration: str, key: str, value) -> None:
        """Set one key inside one iteration block, creating the key if absent."""
        from bioscout.utils.file_edit import _yaml_scalar_text
        its = self.doc.ensure_mapping("iterations")
        for knode, vnode in its.value:
            if str(knode.value) != iteration:
                continue
            if isinstance(value, bool):
                src = "true" if value else "false"
            else:
                old = ""
                for kk, vv in (vnode.value or []):
                    if str(kk.value) == key:
                        old = self.doc.text[vv.start_mark.index:vv.end_mark.index]
                        break
                src = _yaml_scalar_text(value, old, "tag:yaml.org,2002:str")
            self.doc.set_entry_source(vnode, key, src)
            return
        raise KeyError(f"no iteration {iteration!r} in {self.path}")

    def add_iteration(self, name: str, **fields) -> None:
        """Create an iteration block. Written as an indented block mapping so it
        reads like the ones already there, not as inline flow style."""
        its = self.doc.ensure_mapping("iterations")
        if self.doc.has_entry(its, name):
            raise ValueError(f"iteration {name!r} already exists")
        lines = []
        for key, _label, kind, default in ITERATION_FIELDS:
            val = fields.get(key, default)
            if val in (None, ""):
                continue
            if kind == "bool":
                lines.append(f"    {key}: {'true' if val else 'false'}")
            elif kind == "number":
                lines.append(f"    {key}: {val}")
            else:
                lines.append(f"    {key}: {val}")
        self.doc.add_entry(its, name, "\n" + "\n".join(lines))

    def duplicate_iteration(self, name: str, new_name: str) -> None:
        self.doc.duplicate_entry(self.doc.ensure_mapping("iterations"), name, new_name)

    def delete_iteration(self, name: str) -> None:
        self.doc.delete_entry(self.doc.ensure_mapping("iterations"), name)

    # -- emg filter ---------------------------------------------------------- #
    def emg_filter(self) -> Dict[str, Any]:
        """The effective settings, defaults included, for display."""
        from bioscout.utils.emg_filter import settings_for
        return settings_for(self.data)

    def set_emg_filter(self, **params) -> None:
        """Write `emg_filter:`, creating the block on first use.

        Only values that differ from the default are written, so a session that
        keeps the defaults keeps a clean file rather than gaining five lines
        that say what the code already does.
        """
        from bioscout.utils.emg_filter import DEFAULTS
        wanted = {k: v for k, v in params.items()
                  if v not in (None, "") and float(v) != float(DEFAULTS[k])}
        if not wanted and not isinstance(self.data.get("emg_filter"), dict):
            return
        self.doc.ensure_mapping("emg_filter")
        for k, v in wanted.items():
            node = self.doc.map_node("emg_filter")
            src = str(int(v)) if k.endswith("_order") else str(float(v))
            self.doc.set_entry_source(node, k, src)

    # -- EMG map (channel -> muscles) ---------------------------------------- #
    def emg_map(self) -> Dict[str, list]:
        """``{channel: [muscle, ...]}`` as stored. A scalar value (one muscle
        written without brackets) is normalised to a one-element list here so
        callers never branch on shape."""
        raw = self.data.get("emg_map") or {}
        out = {}
        for ch, muscles in raw.items():
            if muscles is None:
                out[str(ch)] = []
            elif isinstance(muscles, (list, tuple)):
                out[str(ch)] = [str(m) for m in muscles]
            else:
                out[str(ch)] = [str(muscles)]
        return out

    def set_emg_map_entry(self, channel: str, muscles) -> None:
        """Write one ``emg_map`` entry, creating the block on first use.

        ``muscles`` is a sequence of OpenSim muscle names (``vasmed_r``…).
        Serialised as a flow list — ``[vasmed_r, vasint_r]`` — which is the
        shape every hand-written session.yaml already uses, so a file edited
        here stays diffable against one edited by hand."""
        channel = str(channel).strip()
        if not channel:
            raise ValueError("emg_map channel name is empty")
        items = [str(m).strip() for m in (muscles or ()) if str(m).strip()]
        self.doc.ensure_mapping("emg_map")
        node = self.doc.map_node("emg_map")
        # replace_entry, NOT set_entry_source: the existing value is usually a
        # BLOCK list, and patching only the value span glues the replacement
        # onto the next channel's key line.
        self.doc.replace_entry(node, channel, "[" + ", ".join(items) + "]")

    def delete_emg_map_entry(self, channel: str) -> None:
        node = self.doc.map_node("emg_map")
        if node is not None:
            self.doc.delete_entry(node, str(channel))

    # -- output ------------------------------------------------------------- #
    def dirty(self) -> bool:
        return bool(self.doc) and bool(self.doc.dirty)   # Document.dirty is a property

    def diff(self) -> str:
        return self.doc.diff() if self.doc else ""

    def save(self, backup: bool = True) -> Path:
        out = self.doc.save(backup=backup)
        self.reload()
        return out

    # -- creation ----------------------------------------------------------- #
    def scaffold(self, template=None, body_mass=None) -> Optional[Path]:
        """Write a first ``session.yaml`` from the c3d files, then load it."""
        from bioscout.utils.session import scaffold_session_yaml
        written = scaffold_session_yaml(str(self.dir), template=template,
                                        body_mass=body_mass)
        if written:
            self.reload()
        return Path(written) if written else None
