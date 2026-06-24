"""
bioscout.utils.analysis — the analysis object model.

This module lives next to :class:`bioscout.utils.Analyse` and gathers the
typed objects that wrap it:

    Project ─▶ Subject ─▶ Session ─▶ Trial   (a Trial *is* an Analyse)

It used to live in two top-level modules (``bioscout/subject.py`` and
``bioscout/project.py``); they are now thin shims that re-export from here so
all the analysis-side code sits together under ``utils``.

Quick start::

    import bioscout
    proj = bioscout.Project()                  # cwd is the project root
    proj.utils, proj.settings, proj.dir

    s = proj.subject("Athlete_03_Cateli")
    trial = s.sessions[0].trials[0]            # a Trial == an Analyse
    trial.run_ik(replace=True)

    from bioscout import build_model_config
    model_config = build_model_config(proj.subjects)

Paths resolve against ``bioscout.utils`` (MODELS_DIR / SIMULATIONS_DIR /
SETUP_DIR), which ``bioscout.Project`` / ``init_project()`` point at the
project folder.
"""
import os
import sys
import json
import shutil
import importlib
import importlib.util
import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# Subject
# ===========================================================================

def _is_ceinms(force_type) -> bool:
    return str(force_type).upper().startswith("CEIN")


@dataclass
class Subject:
    """A subject / model variant and all parameters needed to analyse + plot it."""
    name: str                                  # folder under simulations/<name>/ and models/<name>/
    label: Optional[str] = None                # display name on plots (defaults to name)
    session: Optional[str] = None              # default session, e.g. "25_03_31"
    model_so: Optional[str] = None             # .osim used for static optimisation
    model_ceinms: Optional[str] = None         # .osim used for CEINMS (defaults to model_so)
    setup_folder: Optional[str] = None         # subfolder of setupFiles/ with the OpenSim setup XMLs
    color: str = "black"                       # plot colour
    line_style_so: str = "-"                   # plot line style for SO curves
    line_style_ceinms: str = "--"              # plot line style for CEINMS curves
    group: Optional[str] = None                # optional grouping tag (e.g. "generic" / "MRI")
    body_mass: Optional[float] = None          # optional, kg
    meta: dict = field(default_factory=dict)   # free-form extras

    def __post_init__(self):
        if self.label is None:
            self.label = self.name
        if self.model_ceinms is None:
            self.model_ceinms = self.model_so

    # ---- models -----------------------------------------------------------
    def model_for(self, force_type="SO") -> Optional[str]:
        """Model filename for a solver ('SO' or 'CEINMS')."""
        return self.model_ceinms if _is_ceinms(force_type) else self.model_so

    def model_path(self, force_type="SO", session=None) -> str:
        """Absolute path to the .osim for a solver."""
        from bioscout import utils
        sess = session or self.session or ""
        return os.path.join(str(utils.MODELS_DIR), self.name, sess, self.model_for(force_type) or "")

    # ---- trials -----------------------------------------------------------
    def trial_path(self, trial, session=None) -> str:
        """Absolute path to simulations/<name>/<session>/<trial>."""
        from bioscout import utils
        sess = session or self.session or ""
        return os.path.join(str(utils.SIMULATIONS_DIR), self.name, sess, trial)

    def setup_dir(self) -> str:
        """Absolute path to this subject's OpenSim setup-file folder."""
        from bioscout import utils
        base = getattr(getattr(utils, "settings", None), "SETUP_DIR", None) \
            or os.path.join(str(utils.PROJECT_DIR), "setupFiles")
        return os.path.join(str(base), self.setup_folder) if self.setup_folder else str(base)

    def analyse(self, trial, force_type="SO", session=None, configure=True):
        """Return an ``Analyse`` object for a trial, with the right model +
        setup folder wired in for the chosen solver."""
        from bioscout import utils
        a = utils.Analyse(self.trial_path(trial, session))
        if configure:
            a.subject = self.name
            a.session = session or self.session or getattr(a, "session", None)
            model = self.model_for(force_type)
            if model:
                try:
                    a.update_model(model)
                except Exception as e:
                    print(f"[Subject] {self.name}: could not set model {model}: {e}")
            sd = self.setup_dir()
            if os.path.isdir(sd):
                a.update_trial_attribute("setup_dir", sd)
        return a

    # ---- plotting helpers -------------------------------------------------
    def line_style(self, force_type="SO") -> str:
        return self.line_style_ceinms if _is_ceinms(force_type) else self.line_style_so

    def curve_label(self, force_type="SO") -> str:
        return f"{self.label} - CEINMS" if _is_ceinms(force_type) else self.label

    def to_config(self, force_types=("SO",)) -> dict:
        """Return model_config-style entries for the given solver(s)."""
        cfg = {}
        for ft in force_types:
            cfg[self.curve_label(ft)] = {
                "subject": self.name,
                "color": self.color,
                "force_type": "CEINMS" if _is_ceinms(ft) else "SO",
                "line_style": self.line_style(ft),
            }
        return cfg

    # ---- hierarchy navigation (Subject -> Session -> Trial) ---------------
    @property
    def sessions(self):
        """List of Session objects for this subject (folders under
        simulations/<name>/). If a default session is set, just that one."""
        base = os.path.join(_sim_dir(), self.name)
        if self.session:
            names = [self.session]
        elif os.path.isdir(base):
            names = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))
        else:
            names = []
        return [Session(self, n) for n in names]

    def get_session(self, name):
        """Session by name."""
        return Session(self, name)

    def trials(self, session=None, force_type="SO"):
        """List of Trial objects for one session (default: self.session)."""
        return Session(self, session or self.session).trials

    def make_trial(self, trial_path, force_type="SO", configure=True):
        """Return a Trial (an Analyse) for an absolute trial path, with this
        subject's model + setup folder wired in for the chosen solver."""
        Trial = _trial_class()
        t = Trial(trial_path)
        if configure:
            try:
                _parts = os.path.normpath(trial_path).split(os.sep)
                t.subject = self.name
                t.session = _parts[-2] if len(_parts) >= 2 else self.session
                model = self.model_for(force_type)
                if model:
                    t.update_model(model)
                sd = self.setup_dir()
                if os.path.isdir(sd):
                    t.update_trial_attribute("setup_dir", sd)
            except Exception as e:
                print(f"[Subject] {self.name}: configure trial failed: {e}")
        return t

    @classmethod
    def from_model_folder(cls, name, folder, session=None, **overrides):
        """Build a Subject by inspecting the .osim files in a model folder.

        Picks ``model_so`` = a strength-increased model (filename contains
        'increased' / '3.00' / 'x3'); ``model_ceinms`` = the matching base model.
        Any keyword in ``overrides`` (color, label, setup_folder, …) wins.
        """
        try:
            files = [f for f in os.listdir(folder) if f.lower().endswith(".osim")]
        except Exception:
            files = []
        model_so, model_ceinms = _pick_models(files)
        kw = dict(name=name, session=session, model_so=model_so, model_ceinms=model_ceinms)
        kw.update(overrides)
        return cls(**kw)

    def __repr__(self):
        return f"<Subject {self.label!r} ({self.name}) SO={self.model_so} CEINMS={self.model_ceinms}>"


def build_model_config(subjects, force_types=("SO", "CEINMS")) -> dict:
    """Build a Plot-compatible ``model_config`` dict from a list of Subjects.

    Result: ``{curve_label: {subject, color, force_type, line_style}}`` — exactly
    what ``bioscout.utils.Plot`` reads from ``settings.model_config``.
    """
    cfg = {}
    for s in subjects:
        cfg.update(s.to_config(force_types))
    return cfg


# ===========================================================================
# Hierarchy: Subject -> Session -> Trial (a Trial IS an Analyse)
# ===========================================================================

def _sim_dir():
    from bioscout import utils
    return str(getattr(utils, "SIMULATIONS_DIR", ""))


_TRIAL_CLS = None


def _trial_class():
    """Return (and cache) the Trial class: Analyse + run_*(replace=...)."""
    global _TRIAL_CLS
    if _TRIAL_CLS is not None:
        return _TRIAL_CLS
    from bioscout import utils

    class Trial(utils.Analyse):
        """A trial = an Analyse, plus run_*(replace=...) convenience.

        Inherits every pipeline method of Analyse (run_ik, run_id, run_ma,
        run_so, run_jra, CEINMS, plotting, …). The thin overrides below let you
        pass replace= directly, e.g. trial.run_ik(replace=True).
        """
        def _set_replace(self, replace):
            if replace is not None:
                self.update_trial_attribute("replace", replace)

        def run_ik(self, replace=None):          self._set_replace(replace); return super().run_ik()
        def run_id(self, replace=None):          self._set_replace(replace); return super().run_id()
        def run_ma(self, replace=None):          self._set_replace(replace); return super().run_ma()
        def run_so(self, replace=None):          self._set_replace(replace); return super().run_so()
        def run_jra(self, replace=None):         self._set_replace(replace); return super().run_jra()
        def run_jra_ceinms(self, replace=None):  self._set_replace(replace); return super().run_jra_ceinms()

    _TRIAL_CLS = Trial
    return Trial


class Session:
    """One recording session of a Subject; navigates to its trials."""

    def __init__(self, subject, name):
        self.subject = subject     # Subject
        self.name = name           # session folder name, e.g. "25_03_31"

    @property
    def path(self):
        return os.path.join(_sim_dir(), self.subject.name, self.name or "")

    @property
    def trials(self):
        """List of Trial objects (one per trial folder in this session)."""
        p = self.path
        if not os.path.isdir(p):
            return []
        return [self.subject.make_trial(os.path.join(p, d))
                for d in sorted(os.listdir(p)) if os.path.isdir(os.path.join(p, d))]

    def trial(self, name, force_type="SO"):
        """Trial by name (e.g. 'Squat_BW_01')."""
        return self.subject.make_trial(os.path.join(self.path, name), force_type=force_type)

    def __repr__(self):
        n = len(self.trials) if os.path.isdir(self.path) else 0
        return f"<Session {self.subject.name}/{self.name} — {n} trials>"


_DEFAULT_PALETTE = ["green", "blue", "red", "purple", "orange",
                    "brown", "teal", "magenta", "olive", "cyan"]

# substrings that mark a strength-increased model
_INCREASED_TOKENS = ("increased", "3.00", "_x3", "x3_")


def _pick_models(osim_files):
    """From .osim filenames pick (model_so, model_ceinms).

    SO  = a strength-increased model (name contains an _INCREASED_TOKENS marker).
    CEINMS = the base model that the increased one derives from (its name minus
             the marker), else the shortest plain model.
    """
    osims = [f for f in osim_files if f.lower().endswith(".osim")]
    if not osims:
        return None, None
    increased = [f for f in osims if any(t in f.lower() for t in _INCREASED_TOKENS)]
    base = [f for f in osims if f not in increased]
    model_so = increased[0] if increased else (sorted(base, key=len)[0] if base else None)

    model_ceinms = None
    if model_so and increased:
        stem = model_so.lower()
        for t in _INCREASED_TOKENS:
            stem = stem.split(t)[0]
        stem = stem.rstrip("_").rstrip(".")
        for b in sorted(base, key=len):
            if b.lower().startswith(stem):
                model_ceinms = b
                break
    if model_ceinms is None:
        model_ceinms = sorted(base, key=len)[0] if base else model_so
    return model_so, model_ceinms


def discover_subjects(models_dir=None, session=None, names=None,
                      palette=None, **common):
    """Auto-build a list of :class:`Subject` from the project's models folder.

    Scans ``models_dir`` (defaults to ``bioscout.utils.MODELS_DIR``); each
    sub-folder becomes a Subject, with SO/CEINMS models guessed from its .osim
    files (see :meth:`Subject.from_model_folder`). Looks inside
    ``models/<name>/<session>/`` when ``session`` is given and present.

    ``names`` restricts to specific subjects; ``palette`` overrides colours;
    extra keywords (e.g. ``setup_folder=...``) are applied to every Subject.
    """
    from bioscout import utils
    models_dir = str(models_dir or getattr(utils, "MODELS_DIR", ""))
    palette = palette or _DEFAULT_PALETTE
    out = []
    if not os.path.isdir(models_dir):
        print(f"[bioscout] discover_subjects: models dir not found: {models_dir}")
        return out
    folders = names or sorted(d for d in os.listdir(models_dir)
                              if os.path.isdir(os.path.join(models_dir, d)))
    for i, nm in enumerate(folders):
        base = os.path.join(models_dir, nm)
        folder = os.path.join(base, session) if session and os.path.isdir(os.path.join(base, session)) else base
        kw = dict(session=session, color=palette[i % len(palette)])
        kw.update(common)
        out.append(Subject.from_model_folder(nm, folder, **kw))
    return out


# ===========================================================================
# Project bootstrap
# ===========================================================================

def _force_load_helper(utils, name):
    """Load a lazily-imported helper (openSim/ceinms) onto ``utils``."""
    if getattr(utils, name, None) is not None:
        return
    mod = None
    try:                                   # bare import (utils/ dir is on sys.path)
        mod = importlib.import_module(name)
    except Exception:
        try:                               # package-qualified fallback
            mod = importlib.import_module(f"bioscout.utils.{name}")
        except Exception:
            if name == "openSim":
                print(f"[bioscout] could not load '{name}' — traceback:")
                traceback.print_exc()
            return
    setattr(utils, name, mod)
    sys.modules.setdefault(name, mod)


def check_settings_version(settings, project_dir=None, verbose=True):
    """Compare a project's ``settings.__version__`` to the package schema version.

    Returns True if they match (or can't be compared), False on mismatch.
    Does NOT modify anything — migrating a heavily-customised project
    ``settings.py`` can drop custom fields, so updating is left to an explicit,
    backed-up call (``bioscout.utils.settings_updater.write_updated_settings``)
    or the GUI's "Update Settings" button.
    """
    try:
        import bioscout.settings as _pkg_settings
        pkg_ver = getattr(_pkg_settings, "__version__", None)
    except Exception:
        pkg_ver = None
    proj_ver = getattr(settings, "__version__", None)

    if pkg_ver is None or proj_ver is None:
        if verbose and proj_ver is None:
            print(f"[bioscout] project settings.py has no __version__ — "
                  f"add  __version__ = \"{pkg_ver or '2.2'}\"  to track the schema.")
        return True
    if str(proj_ver) != str(pkg_ver):
        if verbose:
            loc = f" ({project_dir})" if project_dir else ""
            print(f"[bioscout] settings schema mismatch{loc}: project __version__={proj_ver} "
                  f"!= package={pkg_ver}.")
            print("           To migrate (backs up settings.py first):")
            print("             from bioscout.utils.settings_updater import write_updated_settings")
            print("             write_updated_settings(r'<project>/settings.py')")
            print("           NOTE: the migrator only preserves standard fields; back up custom "
                  "config (model_config, MODELS, …) first.")
        return False
    if verbose:
        print(f"[bioscout] settings schema v{proj_ver} OK")
    return True


def _find_project_root(start=None):
    """Locate the project root, robust to the cwd having been changed into a
    trial folder by Analyse(). Priority:
      1. explicit `start`
      2. BIOSCOUT_PROJECT_DIR env var
      3. walk up from cwd to the first folder with settings.py, or with both
         models/ and simulations/
      4. cwd
    """
    if start:
        return Path(start).resolve()
    env = os.environ.get("BIOSCOUT_PROJECT_DIR")
    if env and os.path.isdir(env):
        return Path(env).resolve()
    p = Path(os.getcwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / "settings.py").exists():
            return cand
        if (cand / "models").is_dir() and (cand / "simulations").is_dir():
            return cand
    return p


def migrate_settings(project, write=False, verbose=True):
    """Update a project's settings.py to the current schema, keeping its values.

    Same engine as the GUI's "Update Settings" button
    (``bioscout.utils.settings_updater``): regenerates the file from the latest
    package template and re-injects the project's own values.

    ``write=False`` (default) returns ``(new_text, preserved_lines)`` for preview.
    ``write=True`` writes settings.py in place (backing up the original first)
    and returns the list of preserved-value descriptions.
    """
    sp = Path(project)
    if sp.is_dir():
        sp = sp / "settings.py"
    try:
        from bioscout.utils import settings_updater as su
    except Exception:
        su = importlib.import_module("utils.settings_updater")
    if write:
        preserved = su.write_updated_settings(sp)
        if verbose:
            print(f"[bioscout] settings.py migrated to current schema (backup created): {sp}")
            for line in preserved:
                print(line)
        return preserved
    return su.build_updated_settings(sp)


def ensure_editor_paths(project_dir, verbose=True):
    """Make Pylance/Pyright resolve the project's own modules (e.g. `import
    settings`) by adding "." to python.analysis.extraPaths in the project's
    .vscode/settings.json.

    Relative ("."), so it is portable across machines. Idempotent and
    non-destructive: creates the file if missing, otherwise only adds the keys
    that aren't already there. Never raises (editor convenience only).

    Takes effect when the project folder is opened as a VS Code workspace
    folder (File ▸ Add Folder to Workspace…).
    """
    try:
        vs = Path(project_dir) / ".vscode"
        f = vs / "settings.json"
        data = {}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8")) or {}
            except Exception:
                return  # unparseable / commented JSONC — leave the user's file alone
        paths = data.get("python.analysis.extraPaths", [])
        changed = False
        if "." not in paths:
            paths.append(".")
            data["python.analysis.extraPaths"] = paths
            changed = True
        sev = data.setdefault("python.analysis.diagnosticSeverityOverrides", {})
        for k in ("reportMissingImports", "reportMissingModuleSource"):
            if k not in sev:
                sev[k] = "none"
                changed = True
        if changed:
            vs.mkdir(exist_ok=True)
            f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            if verbose:
                print(f"[bioscout] editor paths configured: {f}")
    except Exception:
        pass  # never break init_project over editor config


class Project:
    """A BioScout project bound to a folder.

    The folder is expected to hold ``models/``, ``simulations/``, ``results/``
    and a project ``settings.py``. Construction wires the package to it.

    Attributes
    ----------
    dir : Path        the project root
    utils : module    bioscout.utils, with OpenSim/CEINMS loaded and dirs set
    settings : module the project's settings.py
    """

    def __init__(self, project_dir=None, verbose=True, setup_editor=True):
        self.dir = _find_project_root(project_dir)
        sys.path.insert(0, str(self.dir))
        os.chdir(self.dir)   # reset cwd (Analyse() chdir's into trial folders)

        from bioscout import utils
        self.utils = utils
        _force_load_helper(utils, "openSim")
        _force_load_helper(utils, "ceinms")

        self.settings = self._load_settings(verbose)
        self._point_dirs()
        check_settings_version(self.settings, self.dir, verbose=verbose)

        # If the settings (e.g. a freshly scaffolded template) declares no
        # subjects, populate them by scanning models/ so the project is usable.
        try:
            if self.settings is not None and not getattr(self.settings, "SUBJECTS", None):
                subs = self.discover_subjects()
                if subs:
                    self.settings.SUBJECTS = subs
                    if not getattr(self.settings, "model_config", None):
                        self.settings.model_config = build_model_config(subs)
                    if verbose:
                        print(f"[bioscout] discovered {len(subs)} subject(s) from models/")
        except Exception:
            pass

        if setup_editor:
            ensure_editor_paths(self.dir, verbose=verbose)

        if verbose:
            import bioscout
            print(f"BioScout {getattr(bioscout, '__version__', '?')}  |  project: {self.dir.name}")
            print(f"openSim ready: {utils.openSim is not None}   "
                  f"ceinms ready: {getattr(utils, 'ceinms', None) is not None}   "
                  f"settings.SESSION: {getattr(self.settings, 'SESSION', None)}")

    # -- setup steps ---------------------------------------------------------
    def _load_settings(self, verbose=True, scaffold=True):
        sp = self.dir / "settings.py"
        if not sp.exists() and scaffold:
            # Create a starter settings.py from the package template so the
            # project has one to edit (mirrors `python -m bioscout --init`).
            try:
                import bioscout.settings as _pkg
                shutil.copy2(Path(_pkg.__file__), sp)
                if verbose:
                    print(f"[bioscout] created settings.py from template -> {sp}")
                    print("           edit PROJECT_ROOT and your project config, then re-run.")
            except Exception as e:
                if verbose:
                    print(f"[bioscout] could not scaffold settings.py: {e}")
        if sp.exists():
            spec = importlib.util.spec_from_file_location("settings", str(sp))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sys.modules["settings"] = mod
            self.utils.settings = mod
            return mod
        if verbose:
            print(f"[bioscout] no settings.py in {self.dir} — using package defaults")
        return getattr(self.utils, "settings", None)

    def _point_dirs(self):
        u, d = self.utils, self.dir
        u.PROJECT_DIR     = str(d)
        u.MODELS_DIR      = str(d / "models")
        u.SIMULATIONS_DIR = str(d / "simulations")
        u.RESULTS_DIR     = str(d / "results")

    # -- convenience ---------------------------------------------------------
    def trial_path(self, subject, session, trial):
        """Absolute path to simulations/<subject>/<session>/<trial>."""
        return os.path.join(self.utils.SIMULATIONS_DIR, subject, session, trial)

    def analyse(self, subject, session, trial):
        """Return an ``Analyse`` object for one trial folder."""
        return self.utils.Analyse(self.trial_path(subject, session, trial))

    def results_dir(self, *parts):
        """Make and return results/<*parts>."""
        d = os.path.join(self.utils.RESULTS_DIR, *parts)
        os.makedirs(d, exist_ok=True)
        return d

    def discover_subjects(self, session=None, **kw):
        """Auto-build Subjects from this project's models/ folder (see
        bioscout.discover_subjects)."""
        return discover_subjects(self.utils.MODELS_DIR,
                                 session=session or getattr(self.settings, "SESSION", None), **kw)

    def migrate_settings(self, write=False, verbose=True):
        """Update this project's settings.py to the current schema, keeping
        its values (see bioscout.migrate_settings)."""
        return migrate_settings(self.dir, write=write, verbose=verbose)

    # ---- hierarchy: Project -> Subject -> Session -> Trial ----------------
    @property
    def subjects(self) -> "list[Subject]":
        """The project's Subject objects (from settings.SUBJECTS)."""
        return list(getattr(self.settings, "SUBJECTS", []) or [])

    def subject(self, name) -> "Subject":
        """Subject by folder name or label."""
        for s in self.subjects:
            if getattr(s, "name", None) == name or getattr(s, "label", None) == name:
                return s
        return None

    def trial(self, subject, trial, session=None, force_type="SO"):
        """Configured Trial for a subject (name or Subject) / session / trial."""
        s = self.subject(subject) if isinstance(subject, str) else subject
        if s is None:
            return None
        sess = session or getattr(s, "session", None)
        return s.make_trial(s.trial_path(trial, sess), force_type=force_type)

    def __repr__(self):
        ok = "ok" if getattr(self.utils, "openSim", None) is not None else "None"
        return f"<bioscout.Project {self.dir.name!r} openSim={ok}>"


def init_project(project_dir=None, verbose=True, setup_editor=True):
    """Bootstrap BioScout for a project folder. Returns ``(utils, settings)``.

    Thin wrapper around :class:`Project` for the common "just give me utils and
    settings" case. ``setup_editor`` (default True) drops a relative
    ``.vscode/settings.json`` so Pylance resolves the project's own modules.
    """
    p = Project(project_dir, verbose=verbose, setup_editor=setup_editor)
    return p.utils, p.settings


__all__ = [
    "Subject", "Session", "Project",
    "build_model_config", "discover_subjects", "init_project",
    "check_settings_version", "migrate_settings", "ensure_editor_paths",
]
