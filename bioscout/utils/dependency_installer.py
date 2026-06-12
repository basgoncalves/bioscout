"""
dependency_installer.py
-----------------------
Checks and installs bioscout dependencies.

Dependency categories
---------------------
  pip      — standard PyPI packages; handled by `pip install bioscout`
  conda    — opensim; NOT on PyPI, must be installed via conda
  optional — opencv / mediapipe; needed only for video/recording tabs

Usage
-----
  python -m bioscout --install          # interactive check + install
  python -m bioscout --install --quiet  # non-interactive, just report
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Dep:
    import_name: str
    pip_name: str = ""          # PyPI package name ("" = not on PyPI)
    conda_channel: str = ""     # conda channel if needed (e.g. "opensim-org")
    conda_name: str = ""        # conda package name
    optional: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Dependency catalogue
# ---------------------------------------------------------------------------
DEPS: list[Dep] = [
    # ── opensim: pip (4.6+) preferred, conda fallback ────────────────────
    Dep(
        import_name="opensim",
        pip_name="opensim",
        conda_channel="opensim-org",
        conda_name="opensim",
        description="OpenSim biomechanics modelling (pip opensim>=4.6 or conda)",
    ),
    # ── optional pip (video / recording features) ─────────────────────────
    Dep(
        import_name="cv2",
        pip_name="opencv-python",
        optional=True,
        description="OpenCV — required for video recording and pose estimation",
    ),
    Dep(
        import_name="mediapipe",
        pip_name="mediapipe",
        optional=True,
        description="MediaPipe — required for real-time pose estimation",
    ),
    # ── pip (should already be installed via setup.py install_requires) ───
    Dep(import_name="numpy",        pip_name="numpy",         description="Numerical arrays"),
    Dep(import_name="pandas",       pip_name="pandas",        description="Data analysis"),
    Dep(import_name="scipy",        pip_name="scipy",         description="Scientific computing"),
    Dep(import_name="matplotlib",   pip_name="matplotlib",    description="Plotting"),
    Dep(import_name="sklearn",      pip_name="scikit-learn",  description="Machine learning"),
    Dep(import_name="customtkinter",pip_name="customtkinter", description="Modern GUI"),
    Dep(import_name="PIL",          pip_name="Pillow",        description="Image processing"),
    Dep(import_name="yaml",         pip_name="pyyaml",        description="YAML config files"),
    Dep(import_name="c3d",          pip_name="c3d",           description="C3D motion capture files"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_installed(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _pip_install(package: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True, text=True, timeout=300,
    )
    return result.returncode == 0


def _conda_available() -> bool:
    return subprocess.run(
        ["conda", "--version"], capture_output=True
    ).returncode == 0


def _conda_install(channel: str, package: str) -> bool:
    result = subprocess.run(
        ["conda", "install", "-c", channel, package, "-y"],
        capture_output=True, text=True, timeout=600,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check() -> dict[str, bool]:
    """Return {import_name: is_installed} for all tracked deps."""
    return {d.import_name: _is_installed(d.import_name) for d in DEPS}


def report() -> None:
    """Print a dependency status table."""
    status = check()
    print("\n── Dependency status ──────────────────────────────────────────")
    for d in DEPS:
        ok = status[d.import_name]
        tag = "✓" if ok else ("· optional" if d.optional else "✗ MISSING")
        print(f"  {tag:12s}  {d.import_name:20s}  {d.description}")
    print()


def install_missing(interactive: bool = True) -> bool:
    """Check all deps and offer to install missing ones.

    Returns True if all non-optional deps are satisfied after the run.
    """
    status = check()

    missing_critical  = [d for d in DEPS if not status[d.import_name] and not d.optional]
    missing_optional  = [d for d in DEPS if not status[d.import_name] and d.optional]

    if not missing_critical and not missing_optional:
        print("✓ All dependencies are satisfied.")
        return True

    report()

    # ── critical ──────────────────────────────────────────────────────────
    if missing_critical:
        print(f"✗ {len(missing_critical)} required dependency/ies missing:\n")
        for d in missing_critical:
            print(f"  {d.import_name}: {d.description}")

        if interactive:
            ans = input("\nAttempt to install them now? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("Skipped. Re-run with --install when ready.")
                return False

        for d in missing_critical:
            if d.conda_name:
                _install_conda_dep(d)
            elif d.pip_name:
                print(f"  pip install {d.pip_name} …")
                ok = _pip_install(d.pip_name)
                print(f"  {'✓' if ok else '✗'} {d.pip_name}")

    # ── optional ──────────────────────────────────────────────────────────
    if missing_optional:
        print(f"\n⚠  {len(missing_optional)} optional dependency/ies missing "
              f"(video / recording features):\n")
        for d in missing_optional:
            print(f"  {d.import_name}: {d.description}")

        if interactive:
            ans = input("\nInstall optional deps? [y/N] ").strip().lower()
            if ans in ("y", "yes"):
                for d in missing_optional:
                    print(f"  pip install {d.pip_name} …")
                    ok = _pip_install(d.pip_name)
                    print(f"  {'✓' if ok else '✗'} {d.pip_name}")

    # final verdict
    final = check()
    all_ok = all(final[d.import_name] for d in DEPS if not d.optional)
    if all_ok:
        print("\n✓ All required dependencies are satisfied.")
    else:
        still_missing = [d.import_name for d in DEPS
                         if not d.optional and not final[d.import_name]]
        print(f"\n✗ Still missing: {', '.join(still_missing)}")
    return all_ok


def _install_conda_dep(d: Dep) -> None:
    """Install a dependency that has both pip (4.6+) and conda options.

    Strategy for opensim:
      1. Try  pip install opensim  (works for opensim >=4.6 on PyPI)
      2. If pip fails, fall back to conda install
      3. If conda not available either, print manual instructions
    """
    # ── Step 1: try pip if a pip_name is set ──────────────────────────────
    if d.pip_name:
        print(f"\n  Trying: pip install {d.pip_name}  (opensim 4.6+ is on PyPI) …")
        ok = _pip_install(d.pip_name)
        if ok and _is_installed(d.import_name):
            print(f"  ✓ {d.pip_name} installed via pip.")
            return
        print(f"  pip install failed (may need Python ≤3.11). Trying conda …")

    # ── Step 2: try conda ─────────────────────────────────────────────────
    print(f"\n  Running: conda install -c {d.conda_channel} {d.conda_name}")
    if not _conda_available():
        print("  conda not found.")
        _print_opensim_manual_instructions()
        return

    ok = _conda_install(d.conda_channel, d.conda_name)
    if ok:
        print(f"  ✓ {d.conda_name} installed via conda.")
    else:
        print(f"  ✗ conda install failed.")
        _print_opensim_manual_instructions()


def _print_opensim_manual_instructions() -> None:
    print("""
  ── Manual OpenSim install options ─────────────────────────────────
  Option A — pip (opensim 4.6+, Python 3.11):
      pip install opensim

  Option B — conda (any supported version):
      conda install -c opensim-org opensim

  Option C — clone a working conda env (fastest if you have one):
      conda create --name new_env --clone msk311b
      conda activate new_env
      pip install -e /path/to/bioscout

  Option D — download from opensim.stanford.edu and follow the
      Python bindings setup guide.
  ────────────────────────────────────────────────────────────────────
""")
