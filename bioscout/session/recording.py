"""Session — one recording session folder (the one holding session.yaml).

``bs.Session(path)`` opens it (logging + project bootstrap), lists and creates
its model iterations (:meth:`Session.iteration`, :meth:`Session.add_iteration`),
and runs/exports/summarises/resets across them. Project-wide operations (every
session of every subject) live on :class:`bioscout.Project`.
"""
from __future__ import annotations

import os
import glob
import shutil
import time
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from typing import TYPE_CHECKING
if TYPE_CHECKING:                       # editor types only, no runtime import
    from bioscout.results import Results
from xml.etree import ElementTree as ET
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception:
    yaml = None

from . import layout as _layout
from .layout import experimental_dir, _RAW_ATTR_FILES
from .iteration import Iteration
from .config import ITERATION_FILE_KEYS, normalise_iterations, SessionKeys

# ---------------------------------------------------------------------------
# Session — the session-level setup object that holds runnable Iterations
# ---------------------------------------------------------------------------
def _bootstrap_project(session_dir, run_name, project_dir=None, verbose=False):
    """Start PROJECT-folder logging BEFORE Project's own auto-logging fires,
    then bootstrap ``bioscout.Project`` once so trials resolve their models.
    Used by ``Session(path)``.

    2026-08-17: logs used to go into ``<session>/logs`` — one folder per
    subject x session made runs impossible to audit. Everything now lands in
    ``<project>/logs`` (session assumed at ``<project>/simulations/<pid>/<name>``,
    else the session's grandparent-of-grandparent), with the subject/session
    baked into the FILENAME so one folder still says which run is which.
    ``BIOSCOUT_LOG_DIR`` overrides the folder either way."""
    import bioscout
    from bioscout import utils
    if session_dir is not None:
        try:
            sd = os.path.abspath(str(session_dir))
            root = project_dir or os.path.dirname(os.path.dirname(os.path.dirname(sd)))
            # ONE log per process (2026-11-04): a command that opens the session
            # again (one Session per iteration, a re-scan ...) keeps writing to
            # the same file instead of starting bioscout_<time>_2.log, _3.log ...
            if not getattr(utils.shared, "_LOG_STARTED", False):
                utils.shared.start_logging(name=run_name,
                                           log_dir=os.path.join(str(root), "logs"))
        except Exception:
            pass
    bioscout.Project(project_dir, verbose=verbose)
    # Project bootstrap / first model loads can leave OpenSim's logger at 'info';
    # apply the configured level now so the run starts quiet.
    try:
        from bioscout.model.opensim_base import _quiet_osim
        _quiet_osim()
    except Exception:
        pass


def _iteration_block_span(lines, name):
    """(start, end, indent, inner_indent) of ``name:`` under top-level
    ``iterations:`` in ``lines`` (LF-split text); start is None if absent."""
    import re
    top = next((i for i, ln in enumerate(lines) if re.match(r"iterations\s*:", ln)), None)
    if top is None:
        return None, None, 0, 2
    key_re = re.compile(r"^(\s+)[\"']?" + re.escape(name) + r"[\"']?\s*:\s*(#.*)?$")
    start = None
    for i in range(top + 1, len(lines)):
        ln = lines[i]
        if ln.strip() and not ln.startswith((" ", "\t", "#")):
            break                                   # next top-level key
        if key_re.match(ln):
            start = i
            break
    if start is None:
        return None, None, 0, 2
    ind = len(key_re.match(lines[start]).group(1))
    end = start + 1
    while end < len(lines):
        ln = lines[end]
        if ln.strip() and (len(ln) - len(ln.lstrip(" "))) <= ind:
            break
        end += 1
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    inner = next((len(ln) - len(ln.lstrip(" ")) for ln in lines[start + 1:end]
                  if ln.strip() and not ln.lstrip().startswith("#")), ind + 2) - ind
    return start, end, ind, inner


class Session(SessionKeys):
    """A recording session (e.g. ``25_03_31``) — the setup object that unifies
    one session's config (``session.yaml``) and its model iterations. Iterations
    are the runnable units::

        s  = Session(r"...\\simulations\\Athlete_03\\25_03_31")
        s.iterations                     # ['cateli', 'gpk', 'gpk_mri', ...]
        it = s.iteration("gpk_mri")      # -> Iteration (runnable)
        it.run(trials=["Walking_02"], do_so=True)
        it.scale_model(muscle_opt=False)
        it.plot_summary(trials=["Walking_02"])
    """

    def __init__(self, session_dir, *, project_dir=None, verbose=False,
                 bootstrap=True):
        """Open a recording session by its FOLDER PATH — the directory holding
        ``session.yaml``, e.g. ``.../simulations/Athlete_03/25_03_31``.

        Constructing one starts logging into ``<project>/logs`` and bootstraps
        ``bioscout.Project`` (which chdir's into the project) so the iterations
        resolve their models; ``project_dir`` names the project when the
        session is not at ``<project>/simulations/<subject>/<session>`` or the
        cwd is elsewhere. Pass
        ``bootstrap=False`` to skip that (a bare config view: no logging, no
        project). Use ``.iteration(name)`` for a runnable :class:`Iteration`.
        """
        self.session_dir = os.path.abspath(session_dir)
        if not os.path.exists(os.path.join(self.session_dir, "session.yaml")):
            raise FileNotFoundError(
                f"no session.yaml in {self.session_dir!r}. Pass the SESSION FOLDER "
                f"path (the dir holding session.yaml), e.g. "
                f".../simulations/Athlete_03/25_03_31.")
        self.name = os.path.basename(self.session_dir)      # session id, e.g. "25_03_31"
        # project_dir= wins over session.yaml's project_dir (relative to this
        # folder), which wins over <project>/simulations/<subject>/<session>.
        self._project_dir_given = os.path.abspath(str(project_dir)) if project_dir else None
        # reading the file fills every session.<key> (config.SessionKeys)
        self._cfg = Iteration._read_yaml(os.path.join(self.session_dir, "session.yaml"))
        if bootstrap:
            _bootstrap_project(self.session_dir, self.name, self.project_dir, verbose)

    # session-level folders that are NOT model iterations (shared inputs, raw c3d,
    # outputs, logs) -- never treated, anchored on, or run as a model.
    _NON_ITERATION_DIRS = _layout.NON_ITERATION_DIRS

    def __repr__(self):
        """One line that says what this session HAS.

        ``<Session ...>`` alone answered none of the questions you open a
        session to ask, so every check ("did it find my trials? which
        iterations? is there a model yet?") cost three more lines.
        """
        try:
            n_t = sum(1 for m in (self._cfg.get("trials") or {}).values()
                      if str((m or {}).get("type", "")).lower() != "static")
        except Exception:                                      # noqa: BLE001
            n_t = "?"
        try:
            its = self.iterations
        except Exception:                                      # noqa: BLE001
            its = []
        subj = os.path.basename(os.path.dirname(os.path.abspath(self.session_dir)))
        return (f"<Session {subj}/{os.path.basename(self.session_dir)}  "
                f"trials={n_t}  iterations={its or '[]'}>")

    def describe(self, log=print, trials=True):
        """Print what this session declares and what it has on disk: the
        session-wide keys, the trials by type and role, then every iteration
        (:meth:`Iteration.describe`: its models found or MISSING, marker set,
        scaling recipe, CEINMS, and which stage outputs each trial has).
        ``trials=False`` leaves out the per-trial stage tables."""
        cfg = self._cfg or {}
        subj = os.path.basename(os.path.dirname(os.path.abspath(self.session_dir)))
        log(self.yaml_path)                                   # clickable: opens the file
        log(f"session {subj}/{self.name}")
        log(f"  {'project_dir':<18}: {cfg.get('project_dir') or '(not set: 3 folders up)'}"
            f"  -> {self.project_dir}")
        for key in ("body_mass", "static_trial", "measured_side", "implanted_side", "instrumented_joint",
                    "setup_folder", "c3d_source", "markerset"):
            if cfg.get(key) is not None:
                log(f"  {key:<18}: {cfg[key]}")
        tcfg = cfg.get("trials") or {}
        by_type = {}
        for name, meta in tcfg.items():
            by_type.setdefault(str((meta or {}).get("type") or "?"), []).append(name)
        log(f"  {'trials':<18}: {len(tcfg)}"
            + (f"   ({', '.join(f'{k} x{len(v)}' for k, v in sorted(by_type.items()))})"
               if by_type else ""))
        for key in ("calibration_trials", "normalisation_trials"):
            got = cfg.get(key) or []
            if got:
                got = list(got) if not isinstance(got, str) else [got]
                log(f"  {key:<18}: {len(got)}   {', '.join(got[:6])}"
                    + (" ..." if len(got) > 6 else ""))
        emg = cfg.get("emg_map") or {}
        if emg:
            log(f"  {'emg_map':<18}: {len(emg)} entr{'y' if len(emg) == 1 else 'ies'}")
        its = self.iterations
        log(f"  {'iterations':<18}: {len(its)}   {', '.join(its)}")
        declared = cfg.get("iterations") or {}
        for name in its:
            log("")
            if name not in declared:
                log(f"iteration {name!r}: folder on disk, NOT declared in session.yaml")
                continue
            it = Iteration(self.session_dir, name)
            it.describe(log=log, trials=None if trials else [])
        return None

    @property
    def iterations(self):
        """Model-iteration folders present on disk (the ground truth), unioned
        with any ``session.yaml`` ``iterations`` keys — excluding shared dirs
        (``experimental``, ``logs``) and dotfiles. ``session.yaml`` need not list
        every iteration; the folders do."""
        root = _layout.iterations_root(self.session_dir)
        # A session that has only just been ingested has no 3_iterations yet —
        # it is created when the first model is scaled. Listing it raised
        # FileNotFoundError and took export down with it, which is backwards:
        # the raw export is model-INDEPENDENT and is exactly the step you run
        # before there is any model at all.
        if not os.path.isdir(root):
            on_disk = set()
        else:
            on_disk = {d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d))
                       and d not in self._NON_ITERATION_DIRS
                       and not d.startswith(".")
                       and "_backup_" not in d}
        # A half-migrated session may still have iterations directly under the
        # session folder; pick those up too rather than silently losing them.
        # But ONLY when the session is not already in the numbered layout: a
        # numbered session keeps its iterations in 3_iterations by definition,
        # so scanning its top level just collects whatever else is lying there.
        # It collected `_to_delete`, called it an iteration, and exported 11
        # trials into it.
        if root != self.session_dir and not _layout.is_numbered_layout(self.session_dir):
            on_disk |= {d for d in os.listdir(self.session_dir)
                        if os.path.isdir(os.path.join(self.session_dir, d))
                        and d not in self._NON_ITERATION_DIRS
                        and not d.startswith(".") and not d.startswith("_")
                        and "_backup_" not in d}
        # Everything session.yaml DECLARES, folder or no folder. It used to be
        # filtered by `os.path.isdir(...)`, which hid exactly what `iteration()`
        # is happy to create: declare a second arm, and `s.iterations` kept
        # saying there was one until something happened to make its directory.
        # The declaration is the truth; the folder appears when the arm runs.
        cfg = set(self._cfg.get("iterations") or {})
        return sorted(on_disk | cfg)

    def iteration(self, name):
        """Return the runnable :class:`Iteration` for model ``name``.

        An iteration DECLARED in session.yaml but not yet on disk is created
        here. Declaring it was previously not enough — the folder only appeared
        as a side effect of some earlier step, so adding a model to session.yaml
        and calling ``s.iteration(name)`` raised FileNotFoundError and listed
        the very name you had just declared as "available". A name that is not
        declared still raises, so a typo is still an error.
        """
        _p = _layout.iteration_path(self.session_dir, name)
        if not os.path.isdir(_p):
            _declared = (self._cfg.get("iterations") or {})
            if name in _declared:
                os.makedirs(_p, exist_ok=True)
                print(f"[Session] {self.name}: created iteration folder "
                      f"{os.path.relpath(_p, self.session_dir)} "
                      f"(declared in session.yaml)")
            else:
                raise FileNotFoundError(
                    f"iteration {name!r} not found under {self.session_dir} and "
                    f"not declared in session.yaml. available: {self.iterations}")
        return Iteration(self.session_dir, name)

    def add_iteration(self, name, copy_from=None, **overrides):
        """Declare a new model iteration in session.yaml, copied from an existing one.

        ``copy_from=None`` starts an empty block instead: ``model_scaled`` set
        to ``models/personalised/<subject>/<session>/<name>_scaled.osim`` and
        ``label`` to ``name``; give ``model_generic=`` (and ``markerset=``) as
        overrides or fill them in the file before scaling.

            it = session.add_iteration("gpk_mri", copy_from="gpk",
                                       model_generic="../../../../../generic models/GPK_v4/GPK_v4_016_mri.osim",
                                       label="Scaled (GPK, MRI)")

        The ``copy_from`` block (generic model, scaling flags, emg_map, colour...)
        is copied under ``name`` and ``overrides`` are applied on top. Only the
        configuration is copied -- no models, no results; run the steps you
        want (``it.scale_model()``, ``it.run(...)``) on the new iteration.

        Two things are changed unless you override them, because a straight
        copy would be wrong: a ``model_scaled`` file name containing
        ``copy_from`` (``gpk_scaled.osim``) is renamed (``gpk_mri_scaled.osim``)
        so scaling the copy cannot overwrite the original's model, and
        ``label`` becomes ``name`` so the two do not share a legend entry.
        Paths stay valid as they are: they are relative to the iteration
        folder, and the new one sits beside the old one.

        The block is inserted after ``copy_from``'s; the rest of session.yaml,
        comments included, is left as it was. The file is only written if it
        re-reads to exactly the intended configuration. Returns the new
        :class:`Iteration` (its folder is created).
        """
        import re
        from .config import load_session_yaml
        name = str(name).strip()
        copy_from = str(copy_from).strip() if copy_from is not None else None
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError(f"iteration name {name!r}: use letters, digits, '_', '-', '.' "
                             f"(it becomes a folder name)")
        ypath = os.path.join(self.session_dir, "session.yaml")
        cfg = load_session_yaml(ypath) or {}
        its = cfg.get("iterations")
        if its is None and copy_from is None:
            its = {}
        if not isinstance(its, dict):
            raise ValueError(f"{ypath}: `iterations` is not a mapping -- add_iteration "
                             f"only edits the `iterations: {{name: {{...}}}}` form")
        if copy_from is not None and copy_from not in its:
            raise KeyError(f"copy_from={copy_from!r} is not an iteration of {self.name}; "
                           f"have {list(its)}")
        if name.lower() in {str(k).strip().lower() for k in its}:
            raise ValueError(f"iteration {name!r} already exists in {ypath}")

        if copy_from is None:
            _itdir = _layout.iteration_path(self.session_dir, name)
            # where scale_model writes it (Iteration.models_dir)
            _m = os.path.join(Iteration(self.session_dir, name).models_dir(create=False),
                              f"{name}_scaled.osim")
            block = {"model_scaled": os.path.relpath(_m, _itdir).replace(os.sep, "/"),
                     "label": name}
        else:
            # the normalised block: current key names, one model_scaled
            block = dict((self._cfg.get("iterations") or {}).get(copy_from)
                         or its[copy_from] or {})
        v = block.get("model_scaled")
        if copy_from is not None and isinstance(v, str) and copy_from in os.path.basename(v):
            head, base = v.replace("\\", "/").rsplit("/", 1) if "/" in v.replace("\\", "/") \
                else ("", v)
            block["model_scaled"] = (head + "/" if head else "") + base.replace(copy_from, name)
        if "label" in block:
            block["label"] = name
        block.update(overrides)

        with open(ypath, "rb") as fh:
            raw = fh.read().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.replace("\r\n", "\n").split("\n")
        top = next((i for i, ln in enumerate(lines) if re.match(r"iterations\s*:", ln)), None)
        if copy_from is None:
            # append at the end of `iterations:` (created at the end of the file)
            if top is None or re.match(r"iterations\s*:\s*\{\s*\}", lines[top]):
                if top is not None:
                    del lines[top]
                while lines and not lines[-1].strip():
                    lines.pop()
                lines.append("iterations:")
                top = len(lines) - 1
            end = top + 1
            while end < len(lines) and (not lines[end].strip()
                                        or lines[end].startswith((" ", "\t", "#"))):
                end += 1
            while end - 1 > top and not lines[end - 1].strip():
                end -= 1
            ind = next((len(ln) - len(ln.lstrip(" ")) for ln in lines[top + 1:end]
                        if ln.strip() and not ln.lstrip().startswith("#")), 2)
            inner = 2
            start = None
        if top is None:
            raise ValueError(f"{ypath}: no top-level `iterations:` line found")
        if copy_from is not None:
            start, end, ind, inner = _iteration_block_span(lines, copy_from)
            if start is None:
                raise ValueError(f"{ypath}: could not find the `{copy_from}:` block "
                                 f"under iterations")
        body = yaml.safe_dump(block, sort_keys=False, default_flow_style=False,
                              allow_unicode=True).rstrip("\n").split("\n")
        new_lines = [" " * ind + f"{name}:"] + [" " * (ind + inner) + b for b in body]
        text = nl.join(lines[:end] + new_lines + lines[end:])

        check = yaml.safe_load(text) or {}
        want = dict(cfg)
        want["iterations"] = dict(its, **{name: block})
        if check != want:
            raise RuntimeError(f"add_iteration: the edited {ypath} did not re-read as "
                               f"intended; nothing was written")
        tmp = ypath + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(tmp, ypath)
        self._cfg = Iteration._read_yaml(ypath)
        print(f"[Session] {self.name}: added iteration {name!r} ("
              + (f"copied from {copy_from!r}" if copy_from else "new, empty")
              + (f"; set {sorted(overrides)}" if overrides else "") + ")")
        return self.iteration(name)

    def migrate(self, dry_run=False, backup=True):
        """Rewrite session.yaml to the current schema. Returns the new text.

        * ``project_dir:`` added (relative to the session folder) if missing
        * every iteration block rewritten with the current keys:
          ``model_generic`` / ``model_scaled`` (the old so_model/ceinms_model
          collapse into one) / ``markerset``, each written RELATIVE TO THE
          ITERATION FOLDER -- found the old way (search) and written as the
          path it actually is
        * a session-level ``markerset`` moved into the iterations

        Only the iteration blocks are re-serialised (their inline comments go);
        the rest of the file, comments and line endings included, stays.
        ``dry_run=True`` prints the diff and writes nothing; ``backup`` keeps
        ``session.yaml.bak``.
        """
        import difflib
        import re
        ypath = os.path.join(self.session_dir, "session.yaml")
        with open(ypath, "rb") as fh:
            raw = fh.read().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.replace("\r\n", "\n").split("\n")

        # new blocks, from the normalised config, files resolved and re-relativised
        new_blocks = {}
        for name in (self._cfg.get("iterations") or {}):
            it = Iteration(self.session_dir, name)
            # no makedirs here: the folder is made when a stage first writes to
            # it -- declaring an iteration must not leave empty folders behind
            cfg = dict(it.config)
            block = {}                                  # file keys first
            for key in ITERATION_FILE_KEYS:
                if cfg.get(key):
                    got = getattr(it, key)
                    block[key] = it.relpath(got, key) if got and os.path.exists(got) else cfg[key]
            block.update((k, v) for k, v in cfg.items() if k not in block)
            new_blocks[name] = block

        # top level: drop a session-wide markerset (now in every block)
        top_ms = next((i for i, ln in enumerate(lines) if re.match(r"markerset\s*:", ln)), None)
        if top_ms is not None and new_blocks:
            del lines[top_ms]
        # top level: project_dir after `session:` (or first line)
        if not any(re.match(r"project_dir\s*:", ln) for ln in lines):
            rel = os.path.relpath(self.project_dir, self.session_dir).replace(os.sep, "/")
            at = next((i + 1 for i, ln in enumerate(lines) if re.match(r"session\s*:", ln)), 0)
            lines.insert(at, f"project_dir: {rel}")

        for name, block in new_blocks.items():
            start, end, ind, inner = _iteration_block_span(lines, name)
            if start is None:
                continue
            body = yaml.safe_dump(block, sort_keys=False, default_flow_style=False,
                                  allow_unicode=True, width=1000).rstrip("\n").split("\n")
            lines[start:end] = ([lines[start]]
                                + [" " * (ind + inner) + b for b in body])
        text = nl.join(lines)

        check = normalise_iterations(yaml.safe_load(text) or {}, warn=lambda m: None)
        if (check.get("iterations") or {}) != new_blocks:
            raise RuntimeError(f"migrate: the rewritten {ypath} did not re-read as "
                               f"intended; nothing was written")
        diff = "".join(difflib.unified_diff(raw.replace("\r\n", "\n").splitlines(True),
                                            text.replace("\r\n", "\n").splitlines(True),
                                            "session.yaml", "session.yaml (migrated)"))
        if dry_run or not diff:
            print(diff or f"[Session] {self.name}: session.yaml is already current")
            return text
        if backup:
            with open(ypath + ".bak", "wb") as fh:
                fh.write(raw.encode("utf-8"))
        tmp = ypath + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(tmp, ypath)
        self._cfg = Iteration._read_yaml(ypath)
        print(diff)
        print(f"[Session] {self.name}: migrated {ypath}" + (" (backup: session.yaml.bak)"
                                                           if backup else ""))
        return text

    def run(self, iterations=None, *, do_scale=False, **kw):
        """Run several iterations with the same stage flags. ``iterations``
        defaults to every iteration present on disk. ``do_scale`` builds each
        iteration's scaled models first (delegates to :meth:`Iteration.scale_model`,
        reading ``session.yaml``); the remaining keyword args forward verbatim to
        :meth:`Iteration.run` (``trials``, ``do_exbiomec``, ``do_so``, ``do_ceinms``,
        ``replace`` ...)::

            Session(path).run(iterations=["gpk", "gpk_mri"], do_so=True)
            Session(path).run(do_scale=True, do_so=True)   # scale + analyse
        """
        out = {}
        for name in (iterations or self.iterations):
            out[name] = self.iteration(name).run(do_scale=do_scale, **kw)
        return out

    def export(self, trials=None, export_src=None, *, replace=False,
               normalise=True, detect=True):
        """Session-level c3d export, done ONCE. The raw markers/GRF/EMG are model-
        INDEPENDENT and shared by every iteration (they live in ``experimental/<trial>/``),
        so exporting per-iteration just repeats identical work. This ingests loose c3d
        -> markers/GRF/EMG -> filters EMG -> runs the session-wide EMG normalise ->
        classifies each trial (``detect``, writing ``movement_detection.yaml`` and
        ``.png`` into the trial folder), once.
        Prefer this over per-iteration ``run(export=True)``::

            s = Session(path)
            s.export(trials=["Deadlift_35kg_01", "Deadlift_35kg_02"], export_src="c3dfiles")
            for name in ("cateli", "gpk"):
                s.iteration(name).run(trials=[...], do_ceinms=True, calibrate=False)
        """
        its = self.iterations
        if not its:
            # Export writes markers/GRF/EMG into 2_experimental/, which no model
            # owns. The Iteration object is only being borrowed for its file
            # plumbing, so borrow a scratch one rather than refusing to run.
            _scratch = "_export"
            _p = _layout.iteration_path(self.session_dir, _scratch)
            os.makedirs(_p, exist_ok=True)
            print(f"[Session] {self.name}: no model iterations yet — exporting "
                  f"the raw trials anyway (they are model-independent).")
            try:
                return Iteration(self.session_dir, _scratch).export_trials(
                    trials=trials, export_src=export_src, replace=replace,
                    normalise=normalise, detect=detect)
            finally:
                # Remove the scratch anchor completely. Deleting it only when
                # empty left `3_iterations/_export/<trial>/{ceinms,inputs,...}`
                # behind, which then LOOKS like a model iteration on the next
                # run. Only empty scaffolding is removed — if anything actually
                # wrote a file in there, keep it and say so, because that means
                # an output landed somewhere it should not have.
                try:
                    _files = [os.path.join(_r, _f)
                              for _r, _, _fs in os.walk(_p) for _f in _fs]
                    if not _files:
                        import shutil as _sh
                        _sh.rmtree(_p, ignore_errors=True)
                    else:
                        print(f"[Session] {self.name}: scratch export folder "
                              f"{_p} holds {len(_files)} file(s) — kept for "
                              f"inspection, delete it once checked.")
                except OSError:
                    pass
        return self.iteration(its[0]).export_trials(
            trials=trials, export_src=export_src, replace=replace,
            normalise=normalise, detect=detect)

    def scale_model(self, iterations=None, **kw):
        """Convenience: scale EVERY iteration's model (scaling only, no analysis).
        The real implementation lives on :meth:`Iteration.scale_model`; this just
        loops it over ``iterations`` (default: all). For scale + analysis in one
        call, prefer ``run(do_scale=True, ...)``."""
        out = {}
        for name in (iterations or self.iterations):
            out[name] = self.iteration(name).scale_model(**kw)
        return out

    @property
    def results(self) -> "Results":
        """This session's results -- call it to load, nothing is read before::

            sess.results()                                        # what exists
            sess.results("so_forces", trial="Gehen_01", iteration="gpkv4", var="*_r")
            sess.results(["ik", "id"], trial="Gehen*", window="cycle").mean().plot()

        See :mod:`bioscout.results`."""
        from bioscout.results import for_session
        return for_session(self.session_dir)

    @property
    def results_dir(self):
        """Flat output folder for cross-model summaries:
        ``<project>/results/<subject>/<session>`` (no subfolders)."""
        from bioscout import utils as _u
        subject = os.path.basename(os.path.dirname(self.session_dir))
        proj = str(getattr(_u, "PROJECT_DIR", None)
                   or os.path.dirname(os.path.dirname(os.path.dirname(self.session_dir))))
        return os.path.join(proj, "results", subject, self.name)

    def summarise(self, trials=None, iterations=None, out_dir=None,
                  figures=("kinematics", "moments", "jcf"), leg="r"):
        """Cross-model comparison figures for this session: overlay EVERY model
        iteration (cateli/gpk/gpk_mri/...) on the same axes, one figure per trial
        TYPE, written FLAT into ``results_dir`` (``<project>/results/<subject>/
        <session>``). Reuses each iteration's on-disk kinematics / ID moments /
        JRA (no re-solve). Colours/labels come from ``session.yaml`` iterations;
        SO = solid, CEINMS = dashed.

            Session(path).summarise()
        """
        import numpy as np, pandas as pd, re
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from bioscout import utils as _u
        ss = getattr(getattr(_u, "settings", None), "SummarySettings", None)
        npts = int(getattr(ss, "npts", 101) or 101)
        dofs = [d for d in (getattr(ss, "dofs", None) or
                            ["hip_flexion_r", "knee_angle_r", "ankle_angle_r"]) if d.endswith("_" + leg) or d.startswith("pelvis")]
        joints = list(getattr(ss, "joints", None) or ["hip", "knee", "ankle"])
        iters = [m for m in (iterations or self.iterations)
                 if os.path.isdir(_layout.iteration_path(self.session_dir, m))]
        # FAIS patch 2026-08-12: `_trial_names` lives on Iteration, not Session,
        # so summarise() without an explicit `trials=` always raised
        # AttributeError. Take the session.yaml trial list directly, minus the
        # static trial and the marker-less EMG-only captures.
        if trials:
            names = [trials] if isinstance(trials, str) else list(trials)
        else:
            _emg_only = set(self._cfg.get("normalisation_trials") or [])
            _static = self._cfg.get("static_trial")
            names = [tn for tn, meta in (self._cfg.get("trials") or {}).items()
                     if tn != _static and tn not in _emg_only
                     and str((meta or {}).get("type", "")).lower() != "static"]
        icfg = (self._cfg.get("iterations") or {})
        color = {m: (icfg.get(m, {}) or {}).get("color", None) for m in iters}
        label = {m: (icfg.get(m, {}) or {}).get("label", m) for m in iters}
        bm = self._cfg.get("body_mass")
        bw = float(bm) * 9.81 if bm else None
        out = out_dir or self.results_dir
        os.makedirs(out, exist_ok=True)

        # group trials by TYPE (strip trailing _NN):  Walking, Squat_BW, ...
        types = {}
        for tn in names:
            types.setdefault(re.sub(r"_\d+$", "", tn), []).append(tn)

        def _ce_of(model):
            """CEINMS weights of one iteration (its own ceinms: over the session's)."""
            from bioscout.session.config import ceinms_for
            return ceinms_for(self._cfg, model)

        def _load(model, trial, rel):
            p = os.path.join(_layout.iteration_path(self.session_dir, model), trial, rel)
            try:
                return _u.load_any_data_file(p) if os.path.exists(p) else None
            except Exception:
                return None

        def _tnorm(y):
            y = np.asarray(y, float); y = y[~np.isnan(y)]
            return (np.interp(np.linspace(0, 100, npts), np.linspace(0, 100, y.size), y)
                    if y.size > 1 else np.full(npts, np.nan))

        def _band(model, ttype, getter):
            """mean±sd across reps of one trial-type for one model."""
            curves = [getter(model, tn) for tn in types[ttype]]
            curves = [c for c in curves if c is not None]
            if not curves:
                return None, None
            a = np.vstack(curves)
            return np.nanmean(a, 0), np.nanstd(a, 0)

        made = []
        # ---- kinematics / moments : one panel per DOF ------------------------
        for kind, rel, suffix, unit in (("kinematics", "external_biomechanics/joint_angles.mot", "", "deg"),
                                        ("moments", "external_biomechanics/inverse_dynamics.sto", "_moment", "N·m")):
            if kind not in figures:
                continue
            cols = [d + suffix for d in dofs]
            for ttype in types:
                def getter_factory(col):
                    def g(model, tn):
                        df = _load(model, tn, rel)
                        if df is None or col not in df.columns:
                            return None
                        return _tnorm(df[col].to_numpy())
                    return g
                ncol = 3; nrow = int(np.ceil(len(cols) / ncol))
                fig, ax = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 2.4 * nrow), squeeze=False)
                for i, col in enumerate(cols):
                    a = ax[i // ncol][i % ncol]; g = getter_factory(col)
                    for m in iters:
                        mean, sd = _band(m, ttype, g)
                        if mean is None:
                            continue
                        a.plot(np.linspace(0, 100, npts), mean, color=color[m], lw=1.6, label=label[m])
                        a.fill_between(np.linspace(0, 100, npts), mean - sd, mean + sd, color=color[m], alpha=0.15)
                    a.set_title(col, fontsize=8); a.tick_params(labelsize=7)
                for j in range(len(cols), nrow * ncol):
                    ax[j // ncol][j % ncol].axis("off")
                h, l = ax[0][0].get_legend_handles_labels()
                fig.legend(h, l, loc="lower center", ncol=min(len(iters), 5), fontsize=8, frameon=False)
                fig.suptitle(f"{self.name} — {ttype} — {kind} ({unit})", fontsize=12)
                fig.tight_layout(rect=[0, 0.05, 1, 0.97])
                p = os.path.join(out, f"summary_{kind}_{ttype}.png")
                fig.savefig(p, dpi=int(getattr(ss, "dpi", 200) or 200)); plt.close(fig); made.append(p)

        # ---- JCF : resultant per joint, SO (solid) vs CEINMS (dashed) --------
        if "jcf" in figures:
            def resultant(df, joint):
                if df is None:
                    return None
                fc = [c for c in df.columns if joint in c.lower() and c.lower().endswith(("fx", "fy", "fz"))
                      and (f"_{leg}_" in c.lower() or c.lower().endswith(leg + "_fx"))]
                # fall back: any columns for the joint if leg-specific not found
                if len(fc) < 2:
                    fc = [c for c in df.columns if joint in c.lower() and c.lower().endswith(("fx", "fy", "fz"))]
                if len(fc) < 2:
                    return None
                comp = {c[-2:]: df[c].to_numpy(float) for c in fc[:3]}
                r = np.sqrt(sum(v ** 2 for v in comp.values()))
                r = r / bw if bw else r
                # FAIS patch 2026-08-12: the kinematics/moments getters return
                # _tnorm(...) but this one returned the RAW column, so _band
                # vstacked native-length curves and the plot below hit
                # "x and y must have same first dimension, shapes (101,) and
                # (234,)" for every trial that is not exactly npts frames long.
                return _tnorm(r)
            for ttype in types:
                fig, ax = plt.subplots(1, len(joints), figsize=(4.6 * len(joints), 3.4), squeeze=False)
                for k, joint in enumerate(joints):
                    a = ax[0][k]
                    for algo, rel, ls in (("SO", "joint_contact_forces/output_so.sto", "-"),
                                          ("CEINMS", "joint_contact_forces/output_ceinms.sto", "--")):
                        def g(model, tn, _rel=rel, _j=joint):
                            return resultant(_load(model, tn, _rel), _j)
                        for m in iters:
                            mean, sd = _band(m, ttype, g)
                            if mean is None:
                                continue
                            a.plot(np.linspace(0, 100, npts), mean, color=color[m], ls=ls, lw=1.5,
                                   label=f"{label[m]} {algo}")
                    a.set_title(f"{joint} |JCF|", fontsize=9); a.set_xlabel("% task", fontsize=8)
                    a.set_ylabel("x BW" if bw else "N", fontsize=8); a.tick_params(labelsize=7)
                h, l = ax[0][0].get_legend_handles_labels()
                fig.legend(h, l, loc="lower center", ncol=min(len(iters) * 2, 6), fontsize=7, frameon=False)
                fig.suptitle(f"{self.name} — {ttype} — joint contact forces (SO solid, CEINMS dashed)", fontsize=12)
                fig.tight_layout(rect=[0, 0.08, 1, 0.95])
                p = os.path.join(out, f"summary_jcf_{ttype}.png")
                fig.savefig(p, dpi=int(getattr(ss, "dpi", 200) or 200)); plt.close(fig); made.append(p)

        # ---- MUSCLE SHARE : who is loading each joint, per TASK ------------
        # FAIS addition 2026-08-12. NOT an induced-acceleration analysis: JRA
        # writes only the resultant contact force, so a muscle's true induced
        # contribution would need one JRA run per muscle. What this shows is each
        # muscle's force as a SHARE OF THE TOTAL MUSCLE FORCE crossing that joint
        # — the dominant term in the contact force, and the one that is free to
        # compute from files already on disk. Label it as such in any manuscript.
        if "muscle_share" in figures:
            TOPN = int(getattr(ss, "muscle_share_top_n", 5) or 5)
            COORD = {"hip": "hip_flexion", "knee": "knee_angle",
                     "ankle": "ankle_angle"}

            # "task" = session.yaml `type`, NOT the `types` dict above: that one
            # strips a trailing _NN, which for FAIS names (RunL1, SLSback_post2)
            # leaves every trial in a group of its own.
            tasks = {}
            for tn in names:
                k = str(((self._cfg.get("trials") or {}).get(tn) or {})
                        .get("type", "other")).lower()
                tasks.setdefault(k, []).append(tn)

            def _muscles_spanning(model, tn, joint):
                """Muscles with a non-zero moment arm about `joint` in this trial."""
                ma = _load(model, tn, os.path.join(
                    "muscle_analysis",
                    f"_MuscleAnalysis_MomentArm_{COORD[joint]}_{leg}.sto"))
                if ma is None:
                    return []
                keep = []
                for c in ma.columns:
                    if str(c).lower() == "time":
                        continue
                    v = pd.to_numeric(ma[c], errors="coerce").to_numpy(float)
                    if np.isfinite(v).any() and np.nanmax(np.abs(v)) > 1e-4:
                        keep.append(str(c))
                return keep

            def _forces(model, tn):
                for rel in ("static_optimisation/StaticOptimization_force.sto",
                            "static_optimisation/SO_StaticOptimization_force.sto",
                            "ceinms/Execution_a%s_b%s_g%s/MuscleForces.sto" % (
                                _ce_of(model).get("alpha", 10),
                                _ce_of(model).get("beta", 1),
                                _ce_of(model).get("gamma", 1000))):
                    df = _load(model, tn, rel)
                    if df is not None:
                        return df
                return None

            for task, tns in sorted(tasks.items()):
                if task in ("static", "generic", "other"):
                    continue
                fig, ax = plt.subplots(1, len(joints),
                                       figsize=(4.8 * len(joints), 3.6),
                                       squeeze=False)
                drew = False
                for k, joint in enumerate(joints):
                    a = ax[0][k]
                    per_muscle = {}          # muscle -> list of % curves
                    for m in iters:
                        for tn in tns:
                            span = _muscles_spanning(m, tn, joint)
                            df = _forces(m, tn)
                            if df is None or not span:
                                continue
                            cols = [c for c in df.columns if str(c) in span]
                            if not cols:
                                continue
                            arr = np.vstack([_tnorm(pd.to_numeric(df[c],
                                             errors="coerce").to_numpy(float))
                                             for c in cols])
                            tot = np.nansum(np.abs(arr), axis=0)
                            tot[tot <= 0] = np.nan
                            for c, row in zip(cols, arr):
                                per_muscle.setdefault(str(c), []).append(
                                    100.0 * np.abs(row) / tot)
                    if not per_muscle:
                        a.text(0.5, 0.5, "no muscle_analysis /\nforce data",
                               ha="center", va="center", transform=a.transAxes,
                               color="0.6", fontsize=8)
                        a.set_title(f"{joint}", fontsize=9)
                        continue
                    mean_of = {c: np.nanmean(np.vstack(v), axis=0)
                               for c, v in per_muscle.items()}
                    top = sorted(mean_of, key=lambda c: np.nanmax(mean_of[c]),
                                 reverse=True)[:TOPN]
                    xs = np.linspace(0, 100, npts)
                    for c in top:
                        a.plot(xs, mean_of[c], lw=1.6, label=c)
                        drew = True
                    rest = [c for c in mean_of if c not in top]
                    if rest:
                        a.plot(xs, np.nansum(np.vstack([mean_of[c] for c in rest]),
                                             axis=0),
                               lw=1.0, ls=":", color="0.5",
                               label=f"other ({len(rest)})")
                    a.set_title(f"{joint} — top {len(top)} of "
                                f"{len(mean_of)} muscles", fontsize=9)
                    a.set_xlabel("% task", fontsize=8)
                    a.set_ylabel("% of muscle force at the joint", fontsize=8)
                    a.set_xlim(0, 100); a.tick_params(labelsize=7)
                    a.grid(color="0.92", lw=0.5)
                    a.legend(fontsize=6, ncol=2, frameon=False)
                if not drew:
                    plt.close(fig)
                    print(f"[Session] muscle_share: no data for task {task!r}")
                    continue
                fig.suptitle(f"{self.name} — {task} — muscle share of the force "
                             f"crossing each joint ({leg} limb, "
                             f"{len(tns)} trial(s))", fontsize=12)
                fig.tight_layout(rect=[0, 0.02, 1, 0.93])
                pth = os.path.join(out, f"summary_muscle_share_{task}.png")
                fig.savefig(pth, dpi=int(getattr(ss, "dpi", 200) or 200))
                plt.close(fig); made.append(pth)

        # ---- MUSCLE CONTRIBUTIONS TO THE JOINT MOMENTS ----------------------
        # Method of:
        #   Maniar N, Schache AG, Cole MH, Opar DA (2019). Lower-limb muscle
        #   function during sidestep cutting. Journal of Biomechanics 82:186-192.
        #   https://doi.org/10.1016/j.jbiomech.2018.10.021
        # Their section 2.6: "Muscle-derived joint moments (computed from the
        # predicted muscle forces and their respective moment arms) were well
        # matched with the experimental joint moments (R^2 = 1.0 +/- 0.0;
        # nRMSE = 2.0e-2 +/- 0.03%)". So, for muscle i about coordinate q:
        #
        #       M_i(t) = F_i(t) * r_iq(t)
        #
        # with F from static optimisation (or CEINMS) and r from the OpenSim
        # MuscleAnalysis moment arms. Muscles are pooled into the functional
        # groups of their Fig. 3, and the net inverse-dynamics moment is drawn
        # shaded behind, exactly as they present it. Summing every muscle should
        # reproduce the ID moment to within the reserve/residual actuators —
        # that identity is the built-in check, reported per panel as R^2.
        if "muscle_moment" in figures:
            MANIAR_GROUPS = {
                "HAM":       ("bflh", "bfsh", "semimem", "semiten"),
                "RECFEM":    ("recfem",),
                "VASTI":     ("vasmed", "vaslat", "vasint"),
                "GMAX":      ("glmax1", "glmax2", "glmax3"),
                "GMED":      ("glmed1", "glmed2", "glmed3"),
                "GMIN":      ("glmin1", "glmin2", "glmin3"),
                "ILIOPSOAS": ("iliacus", "psoas"),
                "PIRI":      ("piri",),
                "ADD":       ("addbrev", "addlong", "addmagDist", "addmagIsch",
                              "addmagMid", "addmagProx"),
                "GAS":       ("gasmed", "gaslat"),
                "SOLEUS":    ("soleus",),
                "TIBANT":    ("tibant",),
            }
            MOM_COORDS = [("hip_flexion", "Hip flexion"),
                          ("hip_adduction", "Hip adduction"),
                          ("hip_rotation", "Hip rotation"),
                          ("knee_angle", "Knee flexion"),
                          ("ankle_angle", "Ankle plantarflexion")]

            def _grp_of(muscle):
                base = re.sub(r"_[rl]$", "", str(muscle))
                for g, mem in MANIAR_GROUPS.items():
                    if base in mem:
                        return g
                return None

            def _forces_df(model, tn):
                for rel in ("static_optimisation/StaticOptimization_force.sto",
                            "static_optimisation/SO_StaticOptimization_force.sto",
                            "ceinms/Execution_a%s_b%s_g%s/MuscleForces.sto" % (
                                _ce_of(model).get("alpha", 10),
                                _ce_of(model).get("beta", 1),
                                _ce_of(model).get("gamma", 1000))):
                    df = _load(model, tn, rel)
                    if df is not None:
                        return df
                return None

            tasks2 = {}
            for tn in names:
                k = str(((self._cfg.get("trials") or {}).get(tn) or {})
                        .get("type", "other")).lower()
                tasks2.setdefault(k, []).append(tn)

            for task, tns in sorted(tasks2.items()):
                if task in ("static", "generic", "other"):
                    continue
                fig, ax = plt.subplots(1, len(MOM_COORDS),
                                       figsize=(3.6 * len(MOM_COORDS), 3.6),
                                       squeeze=False)
                drew = False
                for k, (coord, nice) in enumerate(MOM_COORDS):
                    a = ax[0][k]
                    per_grp, nets, checks = {}, [], []
                    for m in iters:
                        for tn in tns:
                            ma = _load(model=m, trial=tn, rel=os.path.join(
                                "muscle_analysis",
                                f"_MuscleAnalysis_MomentArm_{coord}_{leg}.sto"))
                            fdf = _forces_df(m, tn)
                            idf = _load(m, tn,
                                        "external_biomechanics/inverse_dynamics.sto")
                            if ma is None or fdf is None:
                                continue
                            shared = [c for c in ma.columns
                                      if str(c).lower() != "time" and c in fdf.columns]
                            if not shared:
                                continue
                            tot = np.zeros(npts)
                            acc = {}
                            for c in shared:
                                r_ = _tnorm(pd.to_numeric(ma[c], errors="coerce")
                                            .to_numpy(float))
                                f_ = _tnorm(pd.to_numeric(fdf[c], errors="coerce")
                                            .to_numpy(float))
                                mi = f_ * r_                     # Maniar eq: F * r
                                g = _grp_of(c)
                                if g:
                                    acc[g] = acc.get(g, 0.0) + mi
                                tot = tot + np.nan_to_num(mi)
                            for g, v in acc.items():
                                per_grp.setdefault(g, []).append(v)
                            if idf is not None:
                                ncol = next((c for c in idf.columns
                                             if str(c).lower().startswith(
                                                 f"{coord}_{leg}")), None)
                                if ncol is not None:
                                    net = _tnorm(pd.to_numeric(idf[ncol],
                                                 errors="coerce").to_numpy(float))
                                    nets.append(net)
                                    ok = np.isfinite(net) & np.isfinite(tot)
                                    if ok.sum() > 2 and np.ptp(net[ok]) > 0:
                                        checks.append(1.0 - np.sum((net[ok]-tot[ok])**2)
                                                      / np.sum((net[ok]-net[ok].mean())**2))
                    if not per_grp:
                        a.text(0.5, 0.5, "no moment-arm /\nforce data", ha="center",
                               va="center", transform=a.transAxes, color="0.6",
                               fontsize=8)
                        a.set_title(nice, fontsize=9); continue
                    xs = np.linspace(0, 100, npts)
                    if nets:
                        a.fill_between(xs, 0, np.nanmean(np.vstack(nets), 0),
                                       color="0.82", zorder=1,
                                       label="net (inverse dynamics)")
                    order = sorted(per_grp,
                                   key=lambda g: np.nanmax(np.abs(
                                       np.nanmean(np.vstack(per_grp[g]), 0))),
                                   reverse=True)
                    for g in order[:6]:
                        a.plot(xs, np.nanmean(np.vstack(per_grp[g]), 0), lw=1.6,
                               label=g, zorder=3)
                        drew = True
                    a.axhline(0, color="0.5", lw=0.6, zorder=2)
                    ttl = nice + (f"  (R²={np.mean(checks):.2f})" if checks else "")
                    a.set_title(ttl, fontsize=9)
                    a.set_xlabel("% task", fontsize=8)
                    if k == 0:
                        a.set_ylabel("Moment (N·m)", fontsize=8)
                    a.set_xlim(0, 100); a.tick_params(labelsize=7)
                    a.legend(fontsize=6, frameon=False, ncol=2)
                if not drew:
                    plt.close(fig)
                    print(f"[Session] muscle_moment: no data for task {task!r}")
                    continue
                fig.suptitle(f"{self.name} — {task} — muscle contributions to the "
                             f"net joint moments ({leg} limb, {len(tns)} trial(s))"
                             f"   [method: Maniar et al. 2019, J Biomech 82:186-192]",
                             fontsize=11)
                fig.tight_layout(rect=[0, 0.02, 1, 0.92])
                pth = os.path.join(out, f"summary_muscle_moment_{task}.png")
                fig.savefig(pth, dpi=int(getattr(ss, "dpi", 200) or 200))
                plt.close(fig); made.append(pth)

        print(f"[Session] {self.name}: wrote {len(made)} summary figures -> {out}")
        return made

    @staticmethod
    def _is_trial_dir(path):
        """A trial folder holds raw inputs (flat) OR an ``inputs/`` subfolder OR a
        ``trial_settings.xml`` manifest."""
        return (os.path.isdir(os.path.join(path, "inputs"))
                or os.path.exists(os.path.join(path, "trial_settings.xml"))
                or os.path.exists(os.path.join(path, "c3dfile.c3d"))
                or os.path.exists(os.path.join(path, "marker_experimental.trc")))

    def reset(self, trials=None, iterations=None, *, backup=True, dry_run=False,
              trial_keep=None, raw_inputs=False, verbose=True):
        """Strip THIS session's trial folders back to inputs-only.

        Walks each model-iteration folder (``<session>/<iteration>/<trial>/``) and,
        as a fallback, any flat trial folders directly under the session; each trial
        is reduced to ``trial_keep`` (``inputs/`` + ``trial_settings.xml`` by default)
        and every generated output — IK/ID/MA/SO/JRA results, ``setup_*.xml``,
        ``MuscleAnalysis/``, ``Execution*/``, plots, filtered EMG ... — is deleted.
        Shared session dirs (``experimental/``, ``logs/``) are never touched.

        With ``backup`` (default) the whole session folder is first copied to a
        timestamped sibling ``<session>_backup_<YYYYmmdd_HHMMSS>``. Use ``dry_run=True``
        to PREVIEW without deleting (recommended first). ``raw_inputs=True`` also prunes
        each ``inputs/`` down to just the raw c3d. ``trials`` / ``iterations`` (name or
        list) scope the reset. Returns ``{"timestamp","backup","trials_reset","removed"}``.
        """
        import shutil, datetime
        log = print if verbose else (lambda *a, **k: None)
        tkeep = set(trial_keep) if trial_keep is not None else set(self._TRIAL_KEEP)
        tfilter = ({trials} if isinstance(trials, str)
                   else set(trials) if trials else None)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        info = {"timestamp": ts, "backup": None, "trials_reset": 0, "removed": 0}

        if backup and not dry_run:
            dst = f"{self.session_dir}_backup_{ts}"
            log(f"[reset] backup {self.name} -> {os.path.basename(dst)} (can take a while)")
            shutil.copytree(self.session_dir, dst)
            info["backup"] = dst
        elif backup:
            log(f"[reset] (dry-run) would back up {self.name} with ts={ts}")

        def _remove(p):
            info["removed"] += 1
            if dry_run:
                log(f"    would remove {os.path.relpath(p, self.session_dir)}")
                return
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            except Exception as e:
                log(f"    [warn] could not remove {p}: {e}")

        # Scopes to search for trial folders: each requested iteration dir, plus the
        # session dir itself (legacy flat layout). De-dup by absolute path.
        it_scope = iterations if iterations is not None else self.iterations
        it_scope = [it_scope] if isinstance(it_scope, str) else list(it_scope)
        scopes = [os.path.join(self.session_dir, it) for it in it_scope]
        scopes.append(self.session_dir)
        seen = set()
        for scope in scopes:
            if not os.path.isdir(scope):
                continue
            for entry in sorted(os.listdir(scope)):
                p = os.path.join(scope, entry)
                ap = os.path.abspath(p)
                if ap in seen or entry in self._NON_ITERATION_DIRS or entry.startswith("."):
                    continue
                if not (os.path.isdir(p) and self._is_trial_dir(p)):
                    continue
                if tfilter is not None and entry not in tfilter:
                    continue
                seen.add(ap)
                keep_eff = ({"inputs", "trial_settings.xml"}
                            if trial_keep is None and os.path.isdir(os.path.join(p, "inputs"))
                            else tkeep)
                kept = 0
                for item in sorted(os.listdir(p)):
                    if item in keep_eff:
                        kept += 1
                    else:
                        _remove(os.path.join(p, item))
                if raw_inputs:
                    inp = os.path.join(p, "inputs")
                    if os.path.isdir(inp):
                        for item in sorted(os.listdir(inp)):
                            if item not in self._RAW_INPUTS:
                                _remove(os.path.join(inp, item))
                info["trials_reset"] += 1
                log(f"[reset] {os.path.relpath(p, self.session_dir)}: kept {kept} input(s)"
                    f"{' (raw c3d only)' if raw_inputs else ''}")
        log(f"[reset] {'DRY-RUN ' if dry_run else ''}{self.name}: "
            f"{info['trials_reset']} trials reset, {info['removed']} item(s) "
            f"{'to remove' if dry_run else 'removed'}; backup={info['backup']}")
        return info

    # s["gpk_mri"] is sugar for s.iteration("gpk_mri")
    def __getitem__(self, name):
        return self.iteration(name)

    def __iter__(self):
        return (self.iteration(n) for n in self.iterations)

    # (__repr__ lives at the top of the class — the one that used to sit here
    #  shadowed it, because a later definition wins.)


# ---------------------------------------------------------------------------
# find_session_dir — locate a session on disk by name
# ---------------------------------------------------------------------------
def find_session_dir(session, project_dir=None, subject=None):
    """Locate the athlete/session folder holding session.yaml for ``session``
    (layout: ``simulations/<athlete>/<session>/session.yaml``).

    ``subject`` scopes the search to one participant, and you almost always want
    it: a session NAME like "pre" is not unique — every participant in the study
    has one. Without a subject this used to glob ``*/pre/session.yaml`` and
    return ``sorted(hits)[0]``, i.e. the lowest participant id that happens to
    have a folder by that name. Asking for subject 022's "pre" therefore solved
    009's data, under 022's name, silently. An ambiguous name with no subject is
    now an error rather than a coin toss.
    """
    from bioscout import utils
    sim = str(getattr(utils, "SIMULATIONS_DIR", "")
              or os.path.join(project_dir or os.getcwd(), "simulations"))
    if os.path.isabs(session) and os.path.exists(os.path.join(session, "session.yaml")):
        return session                      # already a session folder
    if subject:
        cand = os.path.join(sim, str(subject), session)
        if os.path.exists(os.path.join(cand, "session.yaml")):
            return cand
        raise FileNotFoundError(
            f"no session.yaml for subject={subject!r} session={session!r} "
            f"(looked for {os.path.join(sim, str(subject), session, 'session.yaml')})")
    hits = sorted(glob.glob(os.path.join(sim, "*", session, "session.yaml")))
    if not hits:
        cand = session if os.path.isabs(session) else os.path.join(sim, session)
        if os.path.exists(os.path.join(cand, "session.yaml")):
            return cand
        raise FileNotFoundError(
            f"no session.yaml for session={session!r} under {sim} "
            f"(looked for */{session}/session.yaml)")
    if len(hits) > 1:
        _who = [os.path.basename(os.path.dirname(os.path.dirname(h))) for h in hits]
        raise ValueError(
            f"session={session!r} is ambiguous — {len(hits)} participants have "
            f"one: {', '.join(_who[:8])}{' ...' if len(_who) > 8 else ''}. "
            f"Pass subject= (or an absolute session path); picking the first "
            f"would silently solve the wrong participant's data.")
    return os.path.dirname(hits[0])


# `bioscout.session.recording.Session` is where the class LIVES, but `bioscout` is
# where users get it (bs.Session / from bioscout.session import Session). Without
# this, repr/type/tracebacks name the private three-deep path and read as if
# there were several different Session classes. There is one.
for _cls in (Session, Iteration):
    _cls.__module__ = "bioscout"
del _cls


__all__ = ["Session", "find_session_dir"]
