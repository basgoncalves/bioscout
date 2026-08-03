"""Muscle force and muscle-tendon parameters."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..spec import OpResult, Param, op

__all__ = []


@op("mvic",
    verb="strength",
    summary="Multiply max isometric force on every (or listed) muscle",
    delegates_to="bioscout.utils.openSim.increase_isometric_force",
    suffix="_mvicx{factor:.2f}",
    notes=("The SO strength model. Pairs with the CEINMS model it came from: "
           "the two must be identical in every wrap and path point and differ "
           "ONLY by this factor, or the SO/CEINMS contrast is comparing two "
           "different models. This op verifies that before returning."),
    params=[
        Param("factor", "float", default=3.0, unit="x",
              help="Multiply max_isometric_force by this"),
        Param("muscles", "list[str]", default=None, choices_from="muscles",
              help="Restrict to these muscles (default: all)"),
    ])
def mvic(model, out, *, factor=3.0, muscles=None, **_):
    from bioscout.utils import get_openSim
    _os = get_openSim()

    # increase_isometric_force derives its own '_increased_<f>.osim' name and
    # ignores any out path, so run it on a copy and rename the byproduct.
    work = Path(out).parent / f".model_edit_mvic_{Path(out).stem}.osim"
    shutil.copy2(str(model), work)
    try:
        _os.increase_isometric_force(str(work), muscleList=list(muscles) if muscles else 'all',
                                     factor=float(factor))
        produced = str(work).replace('.osim', f'_increased_{float(factor):.2f}.osim')
        if not os.path.exists(produced):
            return OpResult(False, "mvic", str(model),
                            reason=f"expected {os.path.basename(produced)}, "
                                   f"none was written")
        shutil.move(produced, str(out))
    finally:
        if work.exists():
            work.unlink()

    ok, detail = _verify_mvic_pair(model, out, float(factor))
    if not ok:
        return OpResult(False, "mvic", str(model), str(out), reason=detail)
    return OpResult(True, "mvic", str(model), str(out),
                    changed={"max_isometric_force": f"x{float(factor):.2f}",
                             "muscles": detail},
                    messages=[f"[model-edit] max isometric force x{float(factor):.2f} "
                              f"on {detail} muscle(s); wraps and path points identical"])


def _verify_mvic_pair(before, after, factor):
    """The pair must differ ONLY by ``factor`` on max_isometric_force.

    Pure XML, so it runs even where OpenSim does not, and it is the invariant
    that makes an SO model and a CEINMS model comparable at all.
    """
    import xml.etree.ElementTree as ET

    from ..introspect import iter_real

    def read(p):
        root = ET.parse(str(p)).getroot()
        # <defaults> holds a template muscle whose force is NOT multiplied.
        # Counting it here is what made this check reject correct pairs.
        mif = [float(e.text) for e in iter_real(root, "max_isometric_force")
               if e.text and e.text.strip()]
        rad, pts = [], []
        for el in iter_real(root):
            tag = getattr(el, "tag", "")
            if isinstance(tag, str) and tag.startswith("Wrap") and el.get("name"):
                r = el.find("radius")
                if r is not None and r.text:
                    rad.append((el.get("name"), tuple(float(x) for x in r.text.split())))
        for el in iter_real(root, "PathPoint"):
            loc = el.find("location")
            if loc is not None and loc.text:
                pts.extend(float(x) for x in loc.text.split())
        return mif, sorted(rad), pts

    m0, r0, p0 = read(before)
    m1, r1, p1 = read(after)
    if r0 != r1:
        return False, "wrap radii changed — they must not"
    if len(p0) != len(p1) or any(abs(a - b) > 1e-12 for a, b in zip(p0, p1)):
        return False, "path points changed — they must not"
    if len(m0) != len(m1):
        return False, f"muscle count changed ({len(m0)} -> {len(m1)})"
    bad = [i for i, (a, b) in enumerate(zip(m0, m1)) if abs(b - a * factor) > 1e-6]
    if bad:
        return False, f"{len(bad)} of {len(m0)} muscles are not exactly x{factor}"
    return True, len(m0)


@op("muscle_opt",
    verb="strength",
    summary="Optimise optimal fibre length and tendon slack length (Modenese 2015)",
    delegates_to="bioscout.utils.openSim.muscle_optimimizer_Modenese2015",
    suffix="_opt_N{n_eval}",
    notes=("SLOW — hours, and on the GPK model it has taken over a day at "
           "n_eval=10. It re-fits the muscle-tendon operating range against a "
           "reference model, so it must NOT be run on an MRI/TPS model: that "
           "throws away the personalised parameters the iteration exists to "
           "test. Changing a moment arm changes MTU length, so re-run this "
           "after a large wrap edit if the force-length operating point matters."),
    params=[
        Param("n_eval", "int", default=10,
              help="Evaluation points per muscle. Cost scales with this."),
        Param("reference", "path", default=None,
              help="Reference model defining the target operating range "
                   "(default: the generic this model was scaled from)"),
        Param("log_dir", "path", default=None,
              help="Where the optimisation log goes (default: beside out)"),
    ])
def muscle_opt(model, out, *, n_eval=10, reference=None, log_dir=None, **_):
    from bioscout.utils import get_openSim
    _os = get_openSim()

    written = _os.muscle_optimimizer_Modenese2015(
        osim_model_path=str(model), save_path=str(out),
        ref_model_path=str(reference) if reference else None,
        N_eval=int(n_eval),
        log_folder=str(log_dir) if log_dir else str(Path(out).parent))
    target = written or str(out)
    if not os.path.exists(target):
        return OpResult(False, "muscle_opt", str(model),
                        reason="optimiser produced no model")
    return OpResult(True, "muscle_opt", str(model), str(target),
                    changed={"n_eval": int(n_eval),
                             "reference": str(reference) if reference else "auto"},
                    messages=[f"[model-edit] Modenese2015 muscle optimisation "
                              f"(N={int(n_eval)}) -> {os.path.basename(target)}"])
