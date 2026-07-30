"""BioScout integration — the only BioScout-aware file in this package.

Everything else here is standalone, so this module is import-safe even when
BioScout is absent: it only touches BioScout at call time.

The main entry point is :func:`personalise_iteration`, which works against the
session-centric layout BioScout uses now::

    simulations/<subject>/<session>/session.yaml     # iterations live here
    generic models/<family>/<generic>.osim           # shared model library

Given a session and an iteration name it resolves that iteration's generic
model, warps it onto the subject's MRI landmarks, and writes
``<generic stem>_tps_<subject>.osim`` next to the generic — the naming the
``*_mri`` iterations in ``session.yaml`` expect.

Typical use::

    from bioscout.tps_personalise import personalise_iteration

    personalise_iteration(
        "simulations/Athlete_03/25_03_31", "rajagopal",
        mri_landmarks="models/Athlete_03_MRI_Katya/25_03_31/landmarks.mrk.json",
    )
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .config import PersonalisationConfig, SubjectInfo
from .logging_utils import get_logger
from .pipeline import Personaliser, PersonalisationResult

logger = get_logger(__name__)

#: Enum value BioScout should register if this is wired in as a pipeline step.
ANALYSIS_STEP_NAME = "personalise_tps"

#: Bone-landmark template shipped with the package, expressed in the shared
#: Arnold-lineage body frames (GPK / Catelli / Lernagopal / Rajagopal2015).
DEFAULT_TEMPLATE = Path(__file__).with_name("data") / "markers_and_bone_markers_in_bodies.xml"

#: The model the shipped template's frames were authored in. Used as the
#: reference for the compatibility check — see model_compat.py.
DEFAULT_TEMPLATE_SOURCE = "GPK/GPK_generic_modWO.osim"


def default_template() -> Path:
    """Path to the bundled bone-landmark template."""
    if not DEFAULT_TEMPLATE.exists():
        raise FileNotFoundError(
            f"bundled bone-landmark template missing at {DEFAULT_TEMPLATE}"
        )
    return DEFAULT_TEMPLATE


# --------------------------------------------------------------------- session
def personalise_iteration(
    session_dir: str | Path,
    iteration: str,
    mri_landmarks: str | Path,
    *,
    source_model: str | Path | None = None,
    bone_marker_template: str | Path | None = None,
    template_source_model: str | Path | None = None,
    output_dir: str | Path | None = None,
    output_name: str | None = None,
    geometry_dir: str | Path | None = None,
    check_template_frames: bool = True,
    inspect: bool = True,
    **overrides,
) -> PersonalisationResult:
    """TPS-personalise one iteration's model from a BioScout session.

    Parameters
    ----------
    session_dir, iteration
        Locate ``session.yaml`` and the iteration whose ``generic`` model is
        being personalised.
    mri_landmarks
        3D Slicer ``.mrk.json`` of the subject's segmented bone landmarks.
    source_model
        The ``.osim`` actually warped. Defaults to the iteration's generic
        model. Pass the subject-scaled model instead if you want the warp
        applied on top of dimensional scaling.
    bone_marker_template, template_source_model
        Default to the bundled template and the model its frames came from, so
        the frame-compatibility check runs by default. Passing
        ``check_template_frames=False`` downgrades a mismatch to a warning.
    output_dir, output_name
        Default to writing ``<generic stem>_tps_<subject>.osim`` beside the
        generic model, which is what a ``*_mri`` iteration in ``session.yaml``
        points at.
    """
    from bioscout import Session  # imported at call time — BioScout optional

    session_dir = Path(session_dir).resolve()
    session = Session.open(str(session_dir))
    spec = getattr(session, "spec", None)

    it = _iteration_spec(session, spec, iteration)
    generic = Path(_resolve_generic(session, it, iteration))
    subject_id = str(getattr(spec, "subject", None) or session_dir.parent.name)
    warp_from = Path(source_model) if source_model else generic

    out_dir = Path(output_dir) if output_dir else generic.parent
    out_name = output_name or f"{generic.stem}_tps_{subject_id}.osim"

    cfg = PersonalisationConfig(
        subject=SubjectInfo(
            id=subject_id,
            mass_kg=float(
                getattr(spec, "body_mass", None) or overrides.pop("mass_kg", 70.0)
            ),
            height_m=float(overrides.pop("height_m", 1.80)),
        ),
        generic_model=generic,
        scaled_model=warp_from,
        mri_landmarks=Path(mri_landmarks),
        bone_marker_template=(
            Path(bone_marker_template) if bone_marker_template else default_template()
        ),
        geometry_dir=Path(geometry_dir) if geometry_dir else generic.parent / "Geometry",
        output_dir=out_dir,
        personalised_model_name=out_name,
        template_source_model=(
            Path(template_source_model) if template_source_model
            else _default_template_source(session_dir)
        ),
        check_template_frames=check_template_frames,
        **overrides,
    )
    logger.info("Personalising iteration '%s': %s -> %s",
                iteration, warp_from.name, cfg.personalised_model_path)
    result = Personaliser(cfg).run()

    # Check the warp straight away — a warped muscle path is the thing most
    # likely to have gone wrong, and finding out at IK time is far too late.
    if inspect and result.model_written:
        print(f"[tps] inspecting moment arms of {cfg.personalised_model_path.name} "
              f"(needs opensim; takes a few minutes)")
        report = inspect_model(cfg.personalised_model_path)
        result.inspection = report
        if report["ok"]:
            print(f"[tps] inspection figures : {report['figures']}")
            print(f"[tps] wrap-corrected copy: {report['corrected']}")
            print( "[tps] the personalised model itself is unchanged; the _modWO "
                   "copy is an alternative to compare against.")
        else:
            print(f"[tps] inspection SKIPPED — {report['reason']}")
            print( "[tps] the model is fine; only the check did not run. Re-run with:")
            print(f"[tps]   python -m bioscout.muscle_inspect inspect --model "
                  f"\"{cfg.personalised_model_path}\"")
    return result


def _iteration_spec(session, spec, iteration):
    """The iteration's config, from session.yaml.

    `SessionSpec` exposes its iterations as a `models` LIST of `Model` objects
    (`get_model()` / `model_names()`), not an `iterations` dict — so read the
    parsed spec first and fall back to the session's raw YAML, which is the
    source of truth and always present.
    """
    model = spec.get_model(iteration) if spec is not None else None
    if model is not None:
        return model
    raw = (getattr(session, "_cfg", None) or {}).get("iterations") or {}
    if iteration in raw:
        return raw[iteration]
    have = sorted(raw) or (spec.model_names() if spec is not None else [])
    raise KeyError(
        f"iteration '{iteration}' not in session.yaml "
        f"(have: {', '.join(have) or 'none'})"
    )


def _resolve_generic(session, it, iteration):
    """Absolute path of the iteration's `generic` model.

    Accepts either a `Model` (attribute `generic_model`) or a raw YAML dict
    (key `generic`), and resolves it the same way bioscout does: models dir,
    then `<project>/generic models/`, then the project root.
    """
    generic = getattr(it, "generic_model", None) or (
        it.get("generic") if isinstance(it, dict) else None
    )
    if not generic:
        raise ValueError(f"iteration '{iteration}' declares no `generic` model")
    from bioscout.utils.session import Iteration, resolve_generic

    # Iteration._resolve_model_file already searches every base bioscout uses
    # and knows the project root; `Session` itself exposes neither.
    resolved = Iteration(str(session.session_dir), iteration)._resolve_model_file(generic)
    if resolved and os.path.exists(resolved):
        return resolved
    project_dir = os.path.abspath(
        os.path.join(str(session.session_dir), os.pardir, os.pardir, os.pardir)
    )
    return resolve_generic(generic, project_dir)


def _default_template_source(session_dir: Path) -> Optional[Path]:
    """Locate the model the bundled template's frames were authored in."""
    for base in (session_dir, *session_dir.parents):
        cand = base / "generic models" / DEFAULT_TEMPLATE_SOURCE
        if cand.exists():
            return cand
    return None


def inspect_model(model_path, *, coords=None, muscle_filter=None, n=None,
                  validate=True, make_plots=True):
    """Run the moment-arm sweep on a model and report what it found.

    A TPS warp moves every muscle path point and every wrap-surface
    translation, so it is exactly the operation that can introduce a
    discontinuous moment arm in a model whose paths were clean beforehand.
    Checking is therefore part of producing the model, not a separate chore.

    Delegates to ``muscle_inspect.run_moment_arm_inspection``, which besides
    sweeping and plotting also writes a wrap-corrected ``<model>_modWO.osim``
    **next to** the model. That corrected file is an extra artefact to compare
    against — nothing is repointed at it and the model given here is untouched.

    Needs ``opensim``. Returns a dict describing what was produced, with
    ``ok=False`` and a ``reason`` when it could not run: a failed inspection
    must never invalidate a good warp, so the caller carries on regardless.
    """
    model_path = Path(model_path)
    info = {"ok": False, "model": str(model_path), "corrected": None,
            "figures": None, "reason": None}
    if not model_path.is_file():
        info["reason"] = f"model not found: {model_path}"
        return info

    stem = model_path.stem
    info["corrected"] = str(model_path.with_name(f"{stem}_modWO.osim"))
    info["figures"] = str(model_path.parent / f"muscle_inspect_{stem}")

    argv = ["--model", str(model_path)]
    if coords:
        argv += ["--coords", *coords]
    if muscle_filter:
        argv += ["--muscle-filter", *muscle_filter]
    if n:
        argv += ["--n", str(n)]
    if not validate:
        argv.append("--no-validate")
    if not make_plots:
        argv.append("--no-plots")

    cwd = os.getcwd()          # the sweep resolves relative paths against cwd
    try:
        from bioscout.muscle_inspect import run_moment_arm_inspection as _mai
    except Exception as exc:
        info["reason"] = (f"muscle_inspect unavailable ({type(exc).__name__}: {exc}) "
                          "— needs opensim in this environment")
        return info
    try:
        _mai.main(argv)
        info["ok"] = True
    except SystemExit as exc:                  # the tool exits on bad input
        info["reason"] = f"muscle_inspect exited: {exc.code}"
    except Exception as exc:                   # pragma: no cover - needs opensim
        info["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        os.chdir(cwd)
    return info


# ------------------------------------------------------- legacy / direct entry
def run_for_player(
    project_root: str | Path,
    player_id: str,
    trial: Optional[str] = None,
    **overrides,
) -> PersonalisationResult:
    """Older players.json-based entry point, kept for existing callers."""
    cfg = PersonalisationConfig.from_bioscout(
        player_id=player_id, project_root=project_root, trial=trial, **overrides
    )
    return Personaliser(cfg).run()


def run_step_for_trial(analysis_obj) -> PersonalisationResult:
    """Adapter matching BioScout's ``_run_<step>(self, config)`` pattern."""
    project_root = getattr(analysis_obj, "project_root", None) or getattr(
        analysis_obj, "PROJECT_ROOT", None
    )
    player_id = getattr(analysis_obj, "player_id", None) or getattr(
        analysis_obj, "subject", None
    )
    trial = getattr(analysis_obj, "trial_name", None) or getattr(
        analysis_obj, "trial", None
    )
    if project_root is None or player_id is None:
        raise AttributeError(
            "Analyse object missing project_root/player_id; pass them explicitly "
            "via run_for_player() or personalise_iteration() instead."
        )
    return run_for_player(project_root, str(player_id), trial)
