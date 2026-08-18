"""Run movement detection over a whole exported session.

One implementation, two callers: ``bioscout --classifier <session>`` and a
project pipeline that sets ``DO_DETECT``. They used to be the same code copied
twice, which is the sort of thing that agrees on the day it is written and
disagrees three commits later.
"""
from __future__ import annotations

import os
import sys


def classify_session(session_path: str, settings=None, no_plots: bool = False,
                     write_session_yaml: bool = False, per_trial: bool = True,
                     quiet: bool = False):
    """Classify every trial in ``session_path`` and write the outputs.

    Per trial, beside the data it describes (``per_trial``, the default) —
    this is what the c3d export produces, so the detection travels with the
    trial and not in a folder somewhere else:

    * ``2_experimental/<trial>/movement_detection.yaml`` — type, confidence,
      reason, time_range, side and the task/phase breakdown for that trial
    * ``2_experimental/<trial>/movement_detection.png`` — its QC figure

    And once, beside the session:

    * ``session_auto_detection.yaml`` — the detection, never read by the
      pipeline and never overwriting ``session.yaml``
    * ``movement_detection/classification.csv`` — one row per trial, the
      only cross-trial view (which is why it stays session-level)
    * ``movement_detection/plots/<trial>.png`` — the old figure location,
      written only when ``per_trial=False``; the figures are not duplicated.

    ``settings`` is a project's ``BatchSettings`` (or anything with the same
    attribute names); it supplies the lab conventions — marker names and TRC
    axes. When omitted, the function looks for a ``settings.py`` above the
    session and falls back to the conventional defaults.

    ``write_session_yaml`` corrects ``session.yaml``'s trial types from the
    detection, backing the old file up first. ``quiet`` trims the per-trial
    chatter to one summary line — the export already prints a line per trial.
    Returns the detection dict, or None when the session could not be read.
    """
    import csv as _csv
    import yaml as _yaml
    from bioscout.movement_detector import (classify_trial, segment_trial,
                                            plot_trial_tasks, MocapConfig)

    _say = (lambda *_a, **_k: None) if quiet else print

    _sess = os.path.abspath(session_path)
    if not os.path.isdir(_sess):
        print(f"[classifier] session folder not found: {_sess}"); return None

    _exp = None
    for _name in ("2_experimental", "experimental"):
        if os.path.isdir(os.path.join(_sess, _name)):
            _exp = os.path.join(_sess, _name); break
    if _exp is None:
        print(f"[classifier] no experimental folder under {_sess}\n"
              f"[classifier] export the session first: it needs "
              f"2_experimental/<trial>/marker_experimental.trc")
        return None

    _ypath = os.path.join(_sess, "session.yaml")
    _cfg = {}
    if os.path.isfile(_ypath):
        try:
            _cfg = _yaml.safe_load(open(_ypath, encoding="utf-8")) or {}
        except Exception as _e:
            print(f"[classifier] could not read session.yaml ({_e}); continuing")
    _mass = _cfg.get("body_mass")
    if _mass is None:
        print("[classifier] no body_mass in session.yaml — force thresholds fall "
              "back to a fraction of peak, which is less reliable.")

    # --- lab conventions come from the PROJECT, not from guesswork --------
    # A project already states its markerset, foot markers and TRC axes in
    # settings.py; the detector should read them rather than re-derive them
    # from marker names. Walk up from the session folder to find that file.
    # Absent or unreadable, the defaults are the conventional ones and the run
    # proceeds exactly as before.
    _mcfg, _mcfg_src = MocapConfig(), ""
    if settings is not None:
        _mcfg = MocapConfig.from_settings(settings)
        _mcfg_src = getattr(settings, '__name__', 'settings passed in')
    _probe = _sess if settings is None else None
    for _ in range(6 if _probe else 0):
        _cand = os.path.join(_probe, "settings.py")
        if os.path.isfile(_cand):
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location("_bs_project_settings", _cand)
                _mod = _ilu.module_from_spec(_spec)
                _sys_path_added = os.path.dirname(_cand) not in sys.path
                if _sys_path_added:
                    sys.path.insert(0, os.path.dirname(_cand))
                _spec.loader.exec_module(_mod)
                _bs = getattr(_mod, "BatchSettings", None)
                if _bs is not None:
                    _mcfg = MocapConfig.from_settings(_bs)
                    _mcfg_src = _cand
            except Exception as _e:
                print(f"[classifier] settings.py found at {_cand} but not usable "
                      f"({type(_e).__name__}: {_e}); using default conventions")
            _mcfg_src = _mcfg_src or "<unusable>"
            break
        _up = os.path.dirname(_probe)
        if _up == _probe:
            break
        _probe = _up
    if _mcfg_src and _mcfg_src != "<unusable>":
        _fm = len(_mcfg.left_foot_markers or []) + len(_mcfg.right_foot_markers or [])
        _say(f"[classifier] conventions from {_mcfg_src}: "
              f"vertical={_mcfg.vertical_axis} ap={_mcfg.ap_axis} "
              f"lateral={_mcfg.lateral_axis}"
              + (f", {_fm} foot markers named" if _fm else ", foot markers by name"))
    elif _mcfg_src == "<unusable>":
        pass                       # already reported above
    else:
        _say("[classifier] no project settings.py found — using default "
              "conventions (vertical=Y, foot markers by name)")

    _trials = sorted(d for d in os.listdir(_exp)
                     if os.path.isdir(os.path.join(_exp, d)))
    # Everything this command produces lands together, beside the session it
    # describes, so the detection travels with the data rather than living in
    # whichever project happened to run it.
    _det = os.path.join(_sess, "movement_detection")
    _plots = os.path.join(_det, "plots")
    _do_plots = not no_plots
    _out, _n_multi, _rows, _n_png = {}, 0, [], 0
    for _t in _trials:
        _d = os.path.join(_exp, _t)
        try:
            _lab, _conf, _why, _f = classify_trial(_d, body_mass=_mass,
                                                   cfg=_mcfg)
            _segs = segment_trial(_d, body_mass=_mass, cfg=_mcfg)
        except Exception as _e:
            print(f"  {_t:24} ERROR {type(_e).__name__}: {_e}")
            continue
        if len(_segs) > 1:
            _n_multi += 1
        _entry = {"type": _lab, "confidence": round(float(_conf), 2),
                  "reason": _why}
        if getattr(_f, "cut_direction", ""):
            _entry["cut_direction"] = _f.cut_direction
            _entry["cut_angle_deg"] = _f.cut_angle_deg
        # The trial's range is the range of the TASKS that gave it its
        # label, not the modality-consensus window: on a cut capture the
        # consensus spans the whole run-up, while the finding is the 0.3 s in
        # which the turn happened. Same for the side — it is the leg the task
        # was performed on, not whichever leg happened to be single-support.
        _key = [_g for _g in _segs if _g.task == _lab] or \
               [_g for _g in _segs if _g.task not in ("static", "single_leg_stance")]
        if _key:
            _entry["time_range"] = [min(_g.t_start for _g in _key),
                                    max(_g.t_end for _g in _key)]
            _sides = {_g.side for _g in _key if _g.side}
            if len(_sides) == 1:
                _entry["side"] = next(iter(_sides))
            elif _sides:
                _entry["side"] = "both"
        elif getattr(_f, "window_consensus", ()):
            _entry["time_range"] = list(_f.window_consensus)
        if getattr(_f, "window_consensus", ()):
            _entry["modality_window"] = list(_f.window_consensus)
        if _segs:
            _entry["tasks"] = [
                {"task": _g.task, "time_range": [_g.t_start, _g.t_end],
                 **({"side": _g.side} if _g.side else {}),
                 **({"direction": _g.direction}
                    if getattr(_g, "direction", None) else {}),
                 **({"angle_deg": _g.angle_deg}
                    if getattr(_g, "angle_deg", None) is not None else {}),
                 **({"jump_height_m": _g.jump_height_m}
                    if getattr(_g, "jump_height_m", None) is not None else {}),
                 **({"jump_height_grf_m": _g.jump_height_grf_m}
                    if getattr(_g, "jump_height_grf_m", None) is not None else {}),
                 **({"flight_time_s": _g.flight_time_s}
                    if getattr(_g, "flight_time_s", None) is not None else {}),
                 **{_k: getattr(_g, _k) for _k in
                    ("bar_rom_m", "bar_ap_drift_m", "bar_path_deviation_m",
                     "bar_peak_velocity_ms", "bar_mean_concentric_velocity_ms")
                    if getattr(_g, _k, None) is not None},
                 **({"phases": [{"phase": _p.phase,
                                 "time_range": [_p.t_start, _p.t_end],
                                 **({"side": _p.side} if _p.side else {})}
                                for _p in _g.phases]} if _g.phases else {})}
                for _g in _segs]
        _out[_t] = _entry

        _yt = str(((_cfg.get("trials") or {}).get(_t) or {}).get("type", ""))
        _row = {"trial": _t, "detected": _lab, "session_yaml_type": _yt,
                "agrees": (_yt == "" or _yt == _lab),
                "confidence": round(float(_conf), 2), "n_tasks": len(_segs),
                "reason": _why,
                "cut_direction": getattr(_f, "cut_direction", ""),
                "cut_angle_deg": getattr(_f, "cut_angle_deg", ""),
                "median_speed": getattr(_f, "median_speed", ""),
                "vertical_rom_m": getattr(_f, "vertical_rom_m", ""),
                "longest_flight_s": getattr(_f, "longest_flight_s", ""),
                "peak_vgrf_bw": getattr(_f, "peak_vgrf_bw", ""),
                "single_support_frac": getattr(_f, "single_support_frac", ""),
                "tasks": "; ".join(f"{_g.task}[{_g.t_start:.2f}-{_g.t_end:.2f}]"
                                   for _g in _segs)}
        for _g, _sfx in zip(_segs, "abcdefghijklmnop"):
            _row[f"task_{_sfx}"] = _g.task
            _row[f"task_{_sfx}_start"] = _g.t_start
            _row[f"task_{_sfx}_end"] = _g.t_end
            if getattr(_g, "angle_deg", None) is not None:
                _row[f"task_{_sfx}_angle_deg"] = _g.angle_deg
            for _fld in ("jump_height_m", "jump_height_grf_m", "flight_time_s",
                         "bar_rom_m", "bar_ap_drift_m", "bar_path_deviation_m",
                         "bar_peak_velocity_ms",
                         "bar_mean_concentric_velocity_ms"):
                if getattr(_g, _fld, None) is not None:
                    _row[f"task_{_sfx}_{_fld}"] = getattr(_g, _fld)
        _rows.append(_row)

        # The detection belongs beside the data it describes. Written per
        # trial it survives a trial being copied, re-exported or moved, and
        # anything reading 2_experimental/<trial>/ finds it without knowing
        # the session layout.
        if per_trial:
            try:
                _tdoc = {"trial": _t,
                         "generated_by": f"bioscout {getattr(__import__('bioscout'), '__version__', 'unknown')} export",
                         **_entry}
                if _yt:
                    _tdoc["session_yaml_type"] = _yt
                    _tdoc["agrees"] = (_yt == _lab)
                with open(os.path.join(_d, "movement_detection.yaml"), "w",
                          encoding="utf-8") as _fh:
                    _yaml.safe_dump(_tdoc, _fh, sort_keys=False,
                                    default_flow_style=False, allow_unicode=True)
            except Exception as _e:
                print(f"  [detect] {_t}: could not write movement_detection.yaml "
                      f"({type(_e).__name__}: {_e})")

        if _do_plots:
            _png = (os.path.join(_d, "movement_detection.png") if per_trial
                    else os.path.join(_plots, f"{_t}.png"))
            try:
                if plot_trial_tasks(_d, _png, body_mass=_mass, cfg=_mcfg,
                                    segments=_segs):
                    _n_png += 1
            except Exception as _e:
                print(f"  [plot] {_t}: {type(_e).__name__}: {_e}")

        _old = _yt
        _flag = "" if not _old else ("  ==" if _old == _lab else f"  != session.yaml says {_old}")
        _say(f"  {_t:24} {_lab:18} {len(_segs)} task(s){_flag}")

    _dst = os.path.join(_sess, "session_auto_detection.yaml")
    _ver = getattr(__import__('bioscout'), '__version__', 'unknown')
    # A MIRROR of session.yaml with the trials replaced by what was detected —
    # same keys, same order, so a diff shows only the trials block and the file
    # can eventually be copied over session.yaml wholesale. Reporting the
    # detection alone made you hold the two files side by side to work out what
    # would actually change.
    _doc = {"generated_by": f"bioscout {_ver} --classifier",
            "note": ("Detected from markers/GRF. Identical to session.yaml except "
                     "for `trials`, so `diff` shows exactly what the detection "
                     "would change. Never read by the pipeline and never written "
                     "over session.yaml on its own — use --write-session-yaml."),
            }
    for _k in _cfg:                       # keep session.yaml's own key order
        if _k != "trials":
            _doc[_k] = _cfg[_k]
    _doc.setdefault("session", os.path.basename(_sess))
    if _mass is not None:
        _doc["body_mass"] = _mass
    # Per trial: whatever session.yaml already said, with the detection laid
    # over it. Anything session.yaml carries that the detector has no opinion
    # on — events, notes, a hand-set time_range — survives.
    _merged = {}
    for _k, _v in _out.items():
        _base = dict(((_cfg.get("trials") or {}).get(_k)) or {})
        _base.update(_v)
        _merged[_k] = _base
    for _k, _v in (_cfg.get("trials") or {}).items():
        _merged.setdefault(_k, dict(_v or {}))   # listed but not exported
    _doc["trials"] = _merged
    with open(_dst, "w", encoding="utf-8") as _fh:
        _yaml.safe_dump(_doc, _fh, sort_keys=False, default_flow_style=False,
                        allow_unicode=True)
    _csv_path = os.path.join(_det, "classification.csv")
    if _rows:
        _keys = []
        for _r in _rows:
            for _k in _r:
                if _k not in _keys:
                    _keys.append(_k)
        os.makedirs(_det, exist_ok=True)
        with open(_csv_path, "w", newline="", encoding="utf-8") as _fh:
            _w = _csv.DictWriter(_fh, fieldnames=_keys)
            _w.writeheader(); _w.writerows(_rows)

    _dis = [_r for _r in _rows if not _r["agrees"]]
    if quiet:
        print(f"  [detect] {len(_out)} trial(s) classified, {len(_dis)} "
              f"disagreeing with session.yaml"
              + (f", {_n_png} figure(s)" if _do_plots else ""))
        for _r in _dis:
            print(f"  [detect] {_r['trial']:24} detected {_r['detected']}"
                  f" != session.yaml {_r['session_yaml_type'] or '(unset)'}")
    else:
        print(f"\n[classifier] {len(_out)} trial(s), {_n_multi} with more than "
              f"one task, {len(_dis)} disagreeing with session.yaml")
        print(f"[classifier] wrote {_dst}")
        if _rows:
            print(f"[classifier] wrote {_csv_path}")
        if not _do_plots:
            print("[classifier] figures skipped (--no-plots)")
        elif per_trial:
            print(f"[classifier] wrote {_n_png} figures -> "
                  f"{os.path.join('2_experimental', '<trial>', 'movement_detection.png')}")
        else:
            print(f"[classifier] wrote {_n_png} figures -> {_plots}")
        if per_trial:
            print(f"[classifier] wrote {len(_out)} x "
                  f"{os.path.join('2_experimental', '<trial>', 'movement_detection.yaml')}")

    if not os.path.isfile(_ypath):
        if write_session_yaml:
            _seed = {"session": os.path.basename(_sess), "body_mass": _mass,
                     "trials": {k: {"type": v["type"]} for k, v in _out.items()}}
            with open(_ypath, "w", encoding="utf-8") as _fh:
                _yaml.safe_dump(_seed, _fh, sort_keys=False)
            print(f"[classifier] no session.yaml existed — seeded {_ypath}")
            print("[classifier] REVIEW IT: detection is a starting point, not a source of truth.")
        else:
            print("[classifier] this session has no session.yaml. "
                  "Re-run with --write-session-yaml to seed one from the detection.")
    elif write_session_yaml:
        # A session.yaml already exists. Correct the trial TYPES from the
        # detection and leave everything else alone — body mass, markerset,
        # EMG map and calibration choices are not the detector's to touch.
        # The previous file is kept, because a detector is a starting point.
        _bak = _ypath + ".pre_detection"
        if not os.path.exists(_bak):
            _shutil_ = __import__("shutil")
            _shutil_.copy2(_ypath, _bak)
            print(f"[classifier] backed up {os.path.basename(_ypath)} -> "
                  f"{os.path.basename(_bak)}")
        _tr = _cfg.setdefault("trials", {}) or {}
        _changed = []
        for _k, _v in _out.items():
            _was = str((_tr.get(_k) or {}).get("type", ""))
            _now = _v["type"]
            if _was != _now:
                _changed.append((_k, _was or "(unset)", _now))
            _entry_y = _tr.get(_k) or {}
            _entry_y["type"] = _now
            if _v.get("time_range"):
                _entry_y["time_range"] = _v["time_range"]
            _tr[_k] = _entry_y
        _cfg["trials"] = _tr
        with open(_ypath, "w", encoding="utf-8") as _fh:
            _yaml.safe_dump(_cfg, _fh, sort_keys=False)
        print(f"[classifier] updated {_ypath}: {len(_changed)} trial type(s) changed")
        for _k, _was, _now in _changed:
            print(f"             {_k:24} {_was} -> {_now}")
        print("[classifier] REVIEW IT: detection is a starting point, not a source of truth.")
    return _out

