"""bioscout.utils.project_config — lab facts as data (docs/IMPLEMENTATIONS §2.9).

Steps 1 + 2 of retiring the copied per-project ``settings.py``:

1. **The overlay** (:func:`overlay`, called once from ``utils/__init__``):
   a small declarative ``project.yaml`` at the project root is applied ON TOP
   of whatever settings module resolved — the project's legacy ``settings.py``
   if it still exists, else bioscout's bundled template. The precedence every
   consumer already sees through ``utils.settings`` therefore becomes::

       session.yaml  ->  project.yaml  ->  settings.py (legacy)  ->  bioscout defaults

   Nothing breaks on day one: no project.yaml means nothing changes (plus one
   deprecation note when a legacy settings.py is carrying the load).

2. **The extractor** (:func:`init_project_yaml`, ``bioscout project init``):
   writes project.yaml FROM an existing settings.py — the data attributes of
   ``BatchSettings``/``CEINMSSettings`` that DIFFER from bioscout's bundled
   defaults. Only deviations are written: the file stays short because the
   defaults live in the package, versioned once.

Schema (version 1) — attribute names are used VERBATIM, which is what makes
the extractor's round-trip exact::

    schema: 1
    name: FAIS
    log_type: minimal              # -> settings.LOG_TYPE
    batch:                         # -> attributes set on BatchSettings
      emg_sampling_freq: 2000
      MUSCLE_GROUPS: {...}
    ceinms:                        # -> attributes set on CEINMSSettings
      calibration_trial_names: [SquatA1]

Deliberately NOT written by the extractor (they are not lab facts):
run selection (``SUBJECTS``, ``sessions``, ``trial_list``, ``RUN_*``/``DO_*``
flags, ``replace_existing``) — that belongs at the call site; and paths
(``PROJECT_ROOT``, ``MODELS_DIR``, ...) — the folder convention IS the
configuration.

Import-time dependencies: standard library only. PyYAML is imported lazily
inside the functions that parse/write, so this module loads (and the rest of
``bioscout.utils`` with it) even where yaml is missing.
"""
from __future__ import annotations

import importlib.util
import os
import types

#: How far up from the starting folder project.yaml is searched for. Six
#: levels reaches the project root from anywhere inside
#: ``simulations/<subject>/<session>/3_iterations/<iteration>/<trial>``.
_SEARCH_DEPTH = 6

#: Run selection must never be persisted in project.yaml — a selection written
#: into a config file is why "run the pipeline" silently re-ran one subject
#: from March. Matched by exact name or by prefix (RUN_/DO_).
_RUN_SELECTION = {"SUBJECTS", "subjects", "SESSIONS", "sessions",
                  "trial_list", "replace_existing"}
_RUN_PREFIXES = ("RUN_", "DO_")

#: Paths are convention, not configuration; only a broken convention would be
#: worth declaring, and none of the current consumers support that yet.
_PATH_ATTRS = {"PROJECT_ROOT", "MODELS_DIR", "SIMULATIONS_DIR", "RESULTS_DIR",
               "SETUP_FILES_DIR", "setup_files_folder"}


def _package_dir():
    """The bioscout package folder (…/bioscout), for telling the bundled
    settings template apart from a project's legacy copy."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_project_yaml(start=None):
    """Path of the nearest ``project.yaml`` at or above ``start`` (default:
    cwd), or None. Walks at most ``_SEARCH_DEPTH`` levels so a stray file in
    ``C:\\`` never captures every project on the machine."""
    d = os.path.abspath(start or os.getcwd())
    for _ in range(_SEARCH_DEPTH):
        p = os.path.join(d, "project.yaml")
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _load_yaml(path):
    import yaml                                   # lazy: see module docstring
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a mapping")
    return data


def _bundled_settings():
    """bioscout's own settings template (the in-package defaults), or None
    when even that cannot import (bare environment)."""
    try:
        from bioscout import settings as _s
        return _s
    except Exception:                                          # noqa: BLE001
        return None


def _ensure_section(base, cls_name):
    """The class/namespace on ``base`` that a section's attributes land on,
    created as a SimpleNamespace when the base has none."""
    target = getattr(base, cls_name, None)
    if target is None:
        target = types.SimpleNamespace()
        setattr(base, cls_name, target)
    return target


def apply(base, data, source="project.yaml"):
    """Set ``data``'s sections onto ``base`` (a settings module or namespace).
    Returns the number of attributes applied."""
    n = 0
    for section, cls_name in (("batch", "BatchSettings"),
                              ("ceinms", "CEINMSSettings")):
        mapping = data.get(section)
        if not mapping:
            continue
        if not isinstance(mapping, dict):
            print(f"[{source}] `{section}:` must be a mapping — skipped")
            continue
        target = _ensure_section(base, cls_name)
        for k, v in mapping.items():
            setattr(target, str(k), v)
            n += 1
    if data.get("log_type") is not None:
        base.LOG_TYPE = str(data["log_type"])
        n += 1
    return n


def overlay(settings_obj, start=None):
    """Apply the nearest project.yaml on top of ``settings_obj`` and return
    the result. With no project.yaml this is a near no-op (one deprecation
    note when a legacy settings.py is the active configuration). Never raises:
    configuration loading must not be the thing that stops a run."""
    base = settings_obj if settings_obj is not None else _bundled_settings()
    try:
        ypath = find_project_yaml(start)
        if not ypath:
            bfile = getattr(base, "__file__", None)
            if bfile and _package_dir() not in os.path.abspath(bfile):
                print("[settings] note: per-project settings.py is deprecated "
                      "— `bioscout project init` generates project.yaml "
                      "from it (docs/IMPLEMENTATIONS.md §2.9).")
            return base
        if base is None:
            base = types.SimpleNamespace()
        data = _load_yaml(ypath)
        if data.get("schema") not in (None, 1):
            print(f"[project.yaml] schema {data.get('schema')!r} is newer than "
                  f"this bioscout understands (1) — applying what it can.")
        n = apply(base, data)
        legacy = os.path.join(os.path.dirname(ypath), "settings.py")
        tail = " (wins over the legacy settings.py)" if os.path.isfile(legacy) else ""
        print(f"[project.yaml] {ypath} — {n} fact(s) applied{tail}")
    except Exception as e:                                     # noqa: BLE001
        print(f"[project.yaml] overlay failed ({e}) — continuing without it")
    return base


# --------------------------------------------------------------------------
# step 2: the extractor — `bioscout project init`
# --------------------------------------------------------------------------
def _is_data(v):
    if isinstance(v, (str, int, float, bool, type(None))):
        return True
    if isinstance(v, (list, tuple)):
        return all(_is_data(x) for x in v)
    if isinstance(v, dict):
        return all(isinstance(k, (str, int, float)) and _is_data(x)
                   for k, x in v.items())
    return False


def _plain(v):
    """Tuples -> lists (YAML round-trips lists; tuples come back as lists
    anyway, so write what will be read)."""
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def _lab_facts(cls):
    """Public, data-only attributes of a settings class — the extractable
    facts. Callables, classes, modules, dunders, run selection and paths are
    all skipped."""
    out = {}
    for k in dir(cls):
        if k.startswith("_") or k in _RUN_SELECTION or k in _PATH_ATTRS \
                or k.startswith(_RUN_PREFIXES):
            continue
        try:
            v = getattr(cls, k)
        except Exception:                                      # noqa: BLE001
            continue
        if _is_data(v):
            out[k] = _plain(v)
    return out


def _import_by_path(py_path, name="bioscout_project_settings"):
    spec = importlib.util.spec_from_file_location(name, py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract(settings_module, baseline=None):
    """The project.yaml ``data`` dict for ``settings_module``: lab facts that
    DIFFER from ``baseline`` (default: bioscout's bundled template; with no
    baseline importable, every fact is included)."""
    if baseline is None:
        baseline = _bundled_settings()
    data = {"schema": 1}
    for section, cls_name in (("batch", "BatchSettings"),
                              ("ceinms", "CEINMSSettings")):
        cls = getattr(settings_module, cls_name, None)
        if cls is None:
            continue
        facts = _lab_facts(cls)
        ref = _lab_facts(getattr(baseline, cls_name, object)) if baseline else {}
        diff = {k: v for k, v in facts.items()
                if k not in ref or ref[k] != v}
        if diff:
            data[section] = diff
    lt = getattr(settings_module, "LOG_TYPE", None)
    if lt is not None and lt != getattr(baseline, "LOG_TYPE", None):
        data["log_type"] = str(lt)
    return data


def init_project_yaml(project_dir=".", force=False, baseline=None):
    """``bioscout project init``: write ``<project_dir>/project.yaml`` from the
    project's settings.py. Returns a process exit code (0 written)."""
    import yaml                                   # lazy: see module docstring
    project_dir = os.path.abspath(project_dir)
    spath = os.path.join(project_dir, "settings.py")
    ypath = os.path.join(project_dir, "project.yaml")
    if not os.path.isfile(spath):
        print(f"[project init] no settings.py in {project_dir} — nothing to "
              f"extract. A project without one already runs on bioscout's "
              f"defaults; write project.yaml by hand for any deviation.")
        return 1
    if os.path.isfile(ypath) and not force:
        print(f"[project init] {ypath} already exists — use --force to "
              f"overwrite (a backup is kept).")
        return 1
    try:
        mod = _import_by_path(spath)
    except Exception as e:                                     # noqa: BLE001
        print(f"[project init] could not import {spath}: {e}")
        return 1
    data = extract(mod, baseline=baseline)
    name = os.path.basename(project_dir)
    body = yaml.safe_dump({**data, "name": name}, sort_keys=True,
                          default_flow_style=False, allow_unicode=True)
    if os.path.isfile(ypath):
        import shutil
        shutil.copy2(ypath, ypath + ".bak")
    with open(ypath, "w", encoding="utf-8") as fh:
        fh.write("# project.yaml — lab facts that differ from bioscout's "
                 "defaults. No code.\n"
                 "# Generated by `bioscout project init` from settings.py; "
                 "review, then the\n"
                 "# settings.py can be deleted (docs/IMPLEMENTATIONS.md "
                 "§2.9).\n")
        fh.write(body)
    n = sum(len(v) for k, v in data.items() if isinstance(v, dict))
    print(f"[project init] wrote {ypath} — {n} lab fact(s) that differ from "
          f"bioscout's defaults.\n"
          f"[project init] review it, run once to confirm, then delete "
          f"settings.py.")
    return 0


__all__ = ["find_project_yaml", "overlay", "apply", "extract",
           "init_project_yaml"]
