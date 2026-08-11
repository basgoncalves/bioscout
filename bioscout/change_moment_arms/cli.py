"""``bioscout --change-moment-arms`` — guided moment-arm adjustment.

Same shape as ``bioscout --tps``: discovered defaults in [brackets], Enter
accepts, a summary before anything is written, and nothing touched until you
confirm.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

__all__ = ["run"]


def _is_report_path(path):
    """True if ``path`` lives inside a report folder rather than beside models.

    Reports go to ``<model_dir>/validation/<model>/`` (and, before 2.0.0b11,
    ``muscle_inspect_*/`` / ``moment_arm_change_*/``). A model picker that does
    not skip these offers a figure folder as something to edit.
    """
    from bioscout.muscle_inspect.paths import is_report_dir
    from pathlib import Path as _P
    return any(is_report_dir(part) for part in _P(path).parts)


def _ask(prompt, default=None, choices=None):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        try:
            ans = input(f"  {prompt}{suffix}: ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            print("\n[ma] cancelled.")
            raise SystemExit(1)
        if not ans and default is not None:
            ans = str(default)
        if not ans:
            print("      (required)")
            continue
        if choices and ans not in choices:
            print(f"      pick one of: {', '.join(choices)}")
            continue
        return ans


def _pick(prompt, options, default=None):
    if not options:
        return _ask(prompt, default)
    print(f"  {prompt}:")
    for i, o in enumerate(options, 1):
        print(f"      {i}. {o}")
    default = default if default in options else options[0]
    while True:
        ans = _ask("     choice (number or name)", default)
        if ans in options:
            return ans
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1]
        print("      not a valid choice")


def _moved_points(before_model, after_model):
    """``{(muscle, point): xyz}`` for every path point the edit moved."""
    import xml.etree.ElementTree as ET

    def pts(f):
        root = ET.parse(f).getroot()
        out = {}
        for m in root.iter():
            if not (m.get("name") and m.find("GeometryPath") is not None):
                continue
            for pp in m.find("GeometryPath").iter("PathPoint"):
                loc = pp.findtext("location")
                if loc:
                    out[(m.get("name"), pp.get("name"))] = loc.strip()
        return out

    b, a = pts(before_model), pts(after_model)
    return {k: a[k] for k in a if k in b and a[k] != b[k]}


def _apply_same(src, dst, radii, moved):
    """Write the same wrap radii and path-point locations onto another model."""
    import xml.etree.ElementTree as ET
    from pathlib import Path

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(Path(src), parser=parser)
    root = tree.getroot()
    for wo in root.iter():
        nm = wo.get("name") if hasattr(wo, "get") else None
        if nm in radii:
            el = wo.find("radius")
            if el is not None:
                el.text = repr(float(radii[nm]))
    for m in root.iter():
        if not (m.get("name") and m.find("GeometryPath") is not None):
            continue
        for pp in m.find("GeometryPath").iter("PathPoint"):
            key = (m.get("name"), pp.get("name"))
            if key in moved:
                pp.find("location").text = moved[key]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)


def _run_all(project, model, by_coord) -> int:
    """Scale every spanning muscle's moment arm, across every chosen coordinate."""
    import os
    from pathlib import Path

    targets = [t for ts in by_coord.values() for t in ts]
    coords = list(by_coord)

    print("  A whole-model change should be a SCALE, not a fixed offset: moment")
    print("  arms here are signed (abductors negative, adductors positive), so a")
    print("  fixed +mm would grow one group and shrink the other. A scale factor")
    print("  preserves sign and grows every magnitude — which is what more muscle")
    print("  bulk does.")
    print("  A wrap surface can only grow so far before the path leaves it or")
    print("  crosses bone, so the achievable range is roughly 1.05-1.25. Above")
    print("  that most muscles come back partial or skipped.")
    scale = float(_ask("scale factor (1.15 = +15% on every moment arm)", "1.15"))
    out_default = f"{model.stem}_ma{str(scale).replace('.', 'p')}.osim"
    _ = coords  # named above; kept for the summary block
    out_path = model.parent / _ask("output model name", out_default)
    n_wrap = sum(1 for t in targets if t.wraps)
    print()
    print("-" * 70)
    print(f"  model    : {os.path.relpath(model, project)}")
    print(f"  coords   : {', '.join(coords)}")
    for c, ts in by_coord.items():
        print(f"     {c:20s} {len(ts):3d} muscles")
    print(f"  muscles  : {len(targets)} pairs  ({n_wrap} wrap radius, "
          f"{len(targets)-n_wrap} path translation)")
    print(f"  scale    : x{scale}")
    print(f"  output   : {os.path.relpath(out_path, project)}")
    print("-" * 70)
    print(f"  This solves each muscle separately against the model built so far,")
    print(f"  so expect roughly {len(targets)*12} OpenSim sweeps — minutes to")
    print( "  tens of minutes. Failures are skipped, not fatal.")
    if _ask("proceed?", "yes", choices=["yes", "no"]) != "yes":
        print("[ma] cancelled — nothing written.")
        return 0
    print()

    from .core import apply_batch, check_model
    import shutil, tempfile
    work = Path(tempfile.mkdtemp(prefix="cma_all_"))
    cur = work / model.name
    shutil.copy2(model, cur)
    n_ok = n_partial = n_failed = 0
    routes, failures, partials = {}, [], []
    try:
        for c, ts in by_coord.items():
            print(f"\n  --- {c} ({len(ts)} muscles) ---")
            nxt = work / f"nxt_{c}.osim"
            rep = apply_batch(cur, nxt, [t.muscle for t in ts], c, scale=scale)
            shutil.copy2(rep["model"], cur)
            n_ok += rep["n_ok"]
            n_partial += rep.get("n_partial", 0)
            n_failed += rep["n_failed"]
            for k, v in rep["routes"].items():
                routes[k] = routes.get(k, 0) + v
            partials += [(c, r) for r in rep["results"]
                         if r.get("applied") and not r.get("ok")]
            failures += [(c, r) for r in rep["results"] if not r.get("applied")]
        shutil.copy2(cur, out_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    rep = {"model": str(out_path)}
    print()
    print(f"[ma] wrote {rep['model']}")
    print(f"[ma] {n_ok + n_partial} muscle-coordinate pair(s) changed "
          f"({n_ok} hit the target, {n_partial} partial), {n_failed} skipped")
    for route, cnt in sorted(routes.items()):
        print(f"[ma]   via {route}: {cnt}")
    if partials:
        print("[ma] partial — the geometry ran out before the target:")
        for c, r in sorted(partials, key=lambda x: x[1].get("fraction", 0)):
            print(f"[ma]   {r['muscle']:16s} ({c}) "
                  f"{r.get('achieved_mm', 0):+6.2f} of "
                  f"{r.get('requested_mm', 0):+6.2f} mm "
                  f"({r.get('fraction', 0):.0%})")
        print("[ma] These carry a real but smaller change. If most of the model")
        print("[ma] is here, the scale factor is above what this geometry can")
        print("[ma] deliver — re-run at a lower one rather than reporting it as")
        print("[ma] a uniform increase.")
    if failures:
        print("[ma] skipped:")
        for c, r in failures:
            print(f"[ma]   {r['muscle']:16s} ({c}) {r.get('reason')}")

    # The ALL path was missing this: an iteration runs an SO model AND a CEINMS
    # model, and if only one carries the change the two force estimates are no
    # longer comparable. The single-muscle path already did it.
    out_path = Path(rep["model"])
    siblings = sorted(p_ for p_ in model.parent.glob("*.osim")
                      if p_ != model and p_ != out_path
                      and not _is_report_path(p_)
                      and "_ma" not in p_.stem)
    if siblings:
        print()
        print("  Other models in the same folder — an iteration's SO and CEINMS")
        print("  models must carry the same geometry to stay comparable:")
        for p_ in siblings:
            print(f"      {p_.name}")
        if _ask("apply the same change to them too?", "yes",
                choices=["yes", "no"]) == "yes":
            from .wraps import read_wraps, set_wrap_radii
            import xml.etree.ElementTree as ET
            after = read_wraps(out_path)
            before = read_wraps(model)
            radii = {k: after[k].radius for k in after
                     if after[k].radius and before.get(k) and before[k].radius
                     and abs(after[k].radius - before[k].radius) > 1e-12}
            moved = _moved_points(model, out_path)
            for p_ in siblings:
                sib_out = p_.with_name(p_.stem + out_path.stem[len(model.stem):] + ".osim")
                try:
                    _apply_same(p_, sib_out, radii, moved)
                    print(f"[ma] wrote {sib_out.name}"
                          f"  ({len(radii)} wraps, {len(moved)} path points)")
                except Exception as exc:
                    print(f"[ma] {p_.name}: SKIPPED — {type(exc).__name__}: {exc}")

    print()
    print("  Inspecting the modified model — before/after overlay per muscle,")
    print("  a summary CSV, and the standard muscle_inspect pass. The full pass")
    print("  sweeps every default coordinate, not just the ones you edited,")
    print("  because an edit about hip adduction also moves that muscle's hip")
    print("  flexion and knee moment arms.")
    full = _ask("run the full muscle_inspect pass too (slower)?", "yes",
                choices=["yes", "no"]) == "yes"
    from .inspection import inspect_change
    inspect_change(model, rep["model"], coords, full=full)
    print("\n[ma] NOTE: moment arm and muscle-tendon length moved together, so the")
    print( "[ma] force-length operating point changed. Re-run the muscle")
    print( "[ma] optimisation if that matters.")
    return 0


def run(project_path=None) -> int:
    project = Path(project_path or os.getcwd()).resolve()
    print()
    print("=" * 70)
    print("  bioscout --change-moment-arms")
    print("=" * 70)
    print("  Raises a muscle's moment arm by growing the wrap surface that")
    print("  stands in for its bulk — the mechanism by which a larger muscle")
    print("  holds its line of action further from the joint.")
    print(f"  project: {project}")
    print()

    # -- model ----------------------------------------------------------
    # Both libraries: the shared generics AND the per-iteration scaled models,
    # because tuning is usually done on the model a session actually runs
    # (3_iterations/<it>/scaled*.osim), not on the generic.
    models = []
    for pat in ("generic models/**/*.osim",
                "simulations/*/*/3_iterations/*/*.osim",
                "simulations/*/*/*/*.osim"):
        models += glob.glob(str(project / pat), recursive=True)
    models = sorted({m for m in models if not _is_report_path(m)
                     and "_backup_" not in m})
    if not models:
        print(f"[ma] no .osim found under {project}")
        return 1
    rel = [os.path.relpath(m, project) for m in models]
    model = project / _pick("model to modify", rel)
    print()

    # -- coordinate(s) --------------------------------------------------
    from .core import expand_coordinates, list_coordinates
    print("  One or more coordinates, comma-separated. A name without a side is")
    print("  expanded to both legs — 'hip_adduction' means _r and _l.")
    while True:
        raw = _ask("coordinate(s)", "hip_adduction")
        coords, unknown = expand_coordinates(raw, model)
        if unknown:
            print(f"      not in this model: {', '.join(unknown)}")
            known = list_coordinates(model)
            hint = [c for c in known if any(u.split('_')[0] in c for u in unknown)]
            print(f"      available: {', '.join(hint or known)}")
            continue
        if coords:
            break
        print("      nothing matched")
    print(f"  -> {', '.join(coords)}")
    print()

    from .core import list_targets
    by_coord = {}
    for c in coords:
        print(f"  sweeping {model.name} about {c} (needs opensim)...")
        try:
            t = list_targets(model, c)
        except Exception as exc:
            print(f"\n[ma] could not sweep the model — {type(exc).__name__}: {exc}")
            print("[ma] this step needs opensim; run it in the msk311 environment.")
            return 1
        if t:
            by_coord[c] = t
        else:
            print(f"      no muscle has a moment arm > 1 mm about {c} — skipping")
    if not by_coord:
        print("\n[ma] nothing to adjust.")
        return 1

    # A muscle listed under two coordinates gets solved twice; the second solve
    # works on the already-edited model and will disturb the first target.
    seen = {}
    for c, ts in by_coord.items():
        for t in ts:
            seen.setdefault(t.muscle, []).append(c)
    overlap = {m: cs for m, cs in seen.items() if len(cs) > 1}
    if overlap:
        print()
        print("  NOTE these muscles span more than one of the coordinates you chose:")
        for m, cs in sorted(overlap.items()):
            print(f"      {m:14s} {', '.join(cs)}")
        print("  Each is solved once per coordinate, in order, against the model")
        print("  built so far — so the LAST coordinate's target is the one that")
        print("  ends up satisfied. Pick one coordinate per run to avoid that.")

    for c, ts in by_coord.items():
        print(f"\n  muscles spanning {c} (peak |moment arm|, and how each can be changed):")
        for i, t in enumerate(ts, 1):
            print(f"      {i:2d}. {t.muscle:14s} {t.peak_ma_mm:6.1f} mm   via {t.route}"
                  + (f"  ({', '.join(t.wraps)})" if t.wraps else ""))
    print()
    targets = [t for ts in by_coord.values() for t in ts]
    coord = coords[0]
    names = sorted({t.muscle for t in targets})
    n_wrap = sum(1 for t in targets if t.wraps)
    print(f"      ALL  -> every muscle above ({len(targets)} muscle-coordinate "
          f"pairs: {n_wrap} by wrap radius, {len(targets)-n_wrap} by translation)")
    print()
    muscle = _pick("muscle to adjust (or ALL)", names + ["ALL"], default="ALL")
    print()

    if muscle == "ALL":
        return _run_all(project, model, by_coord)

    coord = next(c for c, ts in by_coord.items()
                 if any(t.muscle == muscle for t in ts))
    target = next(t for t in by_coord[coord] if t.muscle == muscle)

    if not target.wraps:
        print(f"  {muscle} has no wrap surface on its path, so there is no bulk")
        print( "  to grow. Its line of action can only be moved by translating the")
        print( "  attachment points, which models a different anatomical change.")
        print( "  Use change_moment_arms.paths.translate_path_points() directly.")
        return 1

    # -- amount ---------------------------------------------------------
    print("  How much larger should the moment arm be? Enter mm to add to the")
    print("  whole curve (the powerlifting-bulk case is a positive offset).")
    offset = float(_ask("offset (mm)", "5"))
    out_default = f"{model.stem}_ma_{muscle}_{offset:+.0f}mm.osim".replace("+", "p")
    out_name = _ask("output model name", out_default)
    out_path = model.parent / out_name
    print()

    print("-" * 70)
    print(f"  model      : {os.path.relpath(model, project)}")
    print(f"  muscle     : {muscle}   ({coord}, peak {target.peak_ma_mm:.1f} mm)")
    print(f"  route      : wrap radius — {', '.join(target.wraps)}")
    print(f"  offset     : {offset:+.1f} mm")
    print(f"  output     : {os.path.relpath(out_path, project)}")
    print("-" * 70)
    if _ask("proceed?", "yes", choices=["yes", "no"]) != "yes":
        print("[ma] cancelled — nothing written.")
        return 0
    print("\n  searching for the radius that gives that offset...")

    from .core import apply_offset, check_model
    res = apply_offset(model, out_path, muscle, coord, offset, wraps=target.wraps)
    if not res.get("ok"):
        print(f"[ma] did NOT reach the target: {res.get('reason')}")
        if res.get("model"):
            print(f"[ma] closest attempt written to {res['model']}")
        return 1

    print(f"[ma] wrote {res['model']}")
    for w, (old, new) in res["wraps"].items():
        print(f"[ma]   {w}: {old:.4f} -> {new:.4f} m  (x{new/old:.3f})")
    print(f"[ma] requested {res['requested_mm']:+.2f} mm, "
          f"achieved {res['achieved_mm']:+.2f} mm "
          f"(error {res['error_mm']:+.2f} mm, {res['iterations']} sweeps)")

    # An iteration runs a CEINMS model and an SO model. They must carry the
    # SAME geometry or the two force estimates are no longer comparable, which
    # is the whole point of the study — so offer the siblings explicitly.
    siblings = sorted(p for p in model.parent.glob("*.osim")
                      if p != model and p != out_path
                      and not _is_report_path(p))
    if siblings:
        print()
        print("  Other models in the same folder — an iteration's SO and CEINMS")
        print("  models must carry the same geometry to stay comparable:")
        for p_ in siblings:
            print(f"      {p_.name}")
        if _ask("apply the same wrap radii to them too?", "yes",
                choices=["yes", "no"]) == "yes":
            from .wraps import set_wrap_radii
            radii = {w: new for w, (old_, new) in res["wraps"].items()}
            for p_ in siblings:
                sib_out = p_.with_name(
                    p_.stem + out_path.stem[len(model.stem):] + ".osim")
                try:
                    set_wrap_radii(p_, sib_out, radii)
                    print(f"[ma] wrote {sib_out.name}")
                except Exception as exc:
                    print(f"[ma] {p_.name}: SKIPPED — {type(exc).__name__}: {exc}")

    print()
    print("  Inspecting the modified model (growing a wrap can push a path")
    print("  through a bone) — before/after overlay, summary CSV, and the")
    print("  standard muscle_inspect pass over every default coordinate.")
    full = _ask("run the full muscle_inspect pass too (slower)?", "yes",
                choices=["yes", "no"]) == "yes"
    from .inspection import inspect_change
    inspect_change(model, res["model"], [coord], full=full)
    print("\n[ma] NOTE: changing a moment arm changes muscle-tendon length, so the")
    print( "[ma] force-length operating point moved too. Re-run the muscle")
    print( "[ma] optimisation if that matters for your simulation.")
    return 0
