"""Is bioscout running in the environment it expects, and if not, build it.

    bioscout --env            # report
    bioscout --env-create     # create bioscoutv<version> and install into it
    python -m bioscout.envcheck

One environment per bioscout version, named ``bioscoutv<version>`` -- so
``bioscout 2.0.0b8`` wants ``bioscoutv2.0.0b8``. That is deliberate rather than a
single long-lived env: OpenSim, CEINMS and the model files move together with the
package, and a run from three months ago is only reproducible if its dependency
set still exists. Old envs are cheap to keep and one command to delete.

THE ONE THING THAT CANNOT WORK
------------------------------
**A process cannot activate a conda environment for the shell that launched it.**
Activation edits the *parent* shell's PATH and environment variables; a child
Python process has no way to reach back and do that. So this module can:

  * tell you which environment you are in and which one you should be in,
  * CREATE the right environment and install everything into it,
  * print the exact line to run,

and it cannot activate it for you. Anything claiming otherwise is either
re-exec'ing your shell or lying. The shell function in ``bioscout-env.sh``
(shipped beside this file's docs) is the honest version of "just do it": it runs
in *your* shell, so it can activate.

This module lives at the TOP of the package, not under ``bioscout.utils``, and
imports nothing but the standard library. ``bioscout/utils/__init__.py`` pulls in
scipy, matplotlib and the rest — so an envcheck that lived there could not be
imported until the environment it is supposed to build already existed.

Install strategy: pip installs ``uv`` once, then ``uv`` installs everything else.
uv resolves and downloads an order of magnitude faster than pip, which matters
when the dependency set includes opencv and mediapipe. OpenSim is the exception
-- it is not reliably on PyPI, so it is tried with uv/pip first and falls back to
``conda install -c opensim-org opensim``.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

__all__ = [
    "expected_env_name", "current_env", "conda_available", "list_envs",
    "env_exists", "create_env", "install_into", "status", "report",
    "ensure", "activation_command",
    "missing_packages", "autoinstall_missing",
]

#: Python pinned for new environments. OpenSim's pip wheels stop at 3.11 and the
#: conda package is happiest there too; 3.12+ is where "pip install opensim"
#: starts failing in ways that read as a network problem.
DEFAULT_PYTHON = "3.11"

_ENV_PREFIX = "bioscoutv"

#: Set to 1 to silence the startup check entirely (CI, HPC batch jobs, any
#: context where a warning on stderr is noise rather than help).
_OPT_OUT = "BIOSCOUT_NO_ENV_CHECK"

#: Set to 1 to keep the startup check but never let it install anything.
_NO_AUTOINSTALL = "BIOSCOUT_NO_AUTO_INSTALL"

# ---------------------------------------------------------------------------
# Runtime dependency check
#
# The env check above compares environment NAMES. That is all it ever did, and
# it is why a launch could say "you are in 'bioscout_env', expected
# 'bioscoutv2.0.0c1'" and then die on `import psutil` several seconds later
# without ever connecting the two. Names are a proxy; what actually matters is
# whether the modules import.
#
# {pip name: import name} for the declared runtime deps. Kept in step with
# setup.py's install_requires by tests/test_envcheck.py.
# ---------------------------------------------------------------------------
RUNTIME_PACKAGES: Dict[str, str] = {
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "plotly": "plotly",
    "scikit-learn": "sklearn",
    "customtkinter": "customtkinter",
    "Pillow": "PIL",
    "pyyaml": "yaml",
    "c3d": "c3d",
    "packaging": "packaging",
    "pyperclip": "pyperclip",
    "psutil": "psutil",
    "pyautogui": "pyautogui",
    "pygetwindow": "pygetwindow",
    "screeninfo": "screeninfo",
    "fitparse": "fitparse",
    "requests": "requests",
}

#: NEVER auto-installed, whatever is missing.
#:
#: `opensim` is not reliably on PyPI at all and belongs to conda. numpy and
#: scipy are the ones that make this rule matter: they are conda-managed in a
#: working bioscout env, OpenSim's bindings are compiled against those exact
#: builds, and letting pip swap them for its own wheels is a well-known way to
#: turn a working solver into an import error or, worse, a silently different
#: numerical result. If one of these is genuinely missing, the environment is
#: wrong in a way that installing a package will not fix — say so instead.
NEVER_AUTOINSTALL = frozenset({"opensim", "numpy", "scipy"})


def missing_packages(packages: Optional[Dict[str, str]] = None) -> List[str]:
    """Pip names of declared runtime deps whose import is not importable.

    Uses ``find_spec`` rather than importing: it is milliseconds for the whole
    set, has no import side effects, and cannot itself blow up the launch.
    """
    import importlib.util
    out: List[str] = []
    for pip_name, import_name in (packages or RUNTIME_PACKAGES).items():
        try:
            if importlib.util.find_spec(import_name) is None:
                out.append(pip_name)
        except (ImportError, ValueError, AttributeError):
            # A namespace-package oddity or a half-removed dist. Treat as
            # missing — worst case we reinstall something already present.
            out.append(pip_name)
    return out


def autoinstall_missing(log=print, timeout: int = 900) -> List[str]:
    """Install any missing runtime deps into the RUNNING interpreter's env.

    Returns the list of packages still missing afterwards (empty on success).

    Deliberate choices:

    * ``sys.executable -m pip`` — installs into the interpreter that is
      actually running, not whichever pip happens to be first on PATH. That
      distinction is the whole point when several conda envs exist.
    * only the MISSING names are passed, and there is no ``--upgrade``. This
      never touches a package that already imports, so a working environment
      cannot be changed by a launch.
    * :data:`NEVER_AUTOINSTALL` members are reported, never installed.
    """
    missing = missing_packages()
    blocked = [p for p in missing if p in NEVER_AUTOINSTALL]
    installable = [p for p in missing if p not in NEVER_AUTOINSTALL]

    for p in blocked:
        log(f"[env] {p} is missing and is NOT auto-installed — it is conda-managed "
            f"and pip would risk the OpenSim bindings. Fix the environment instead.")

    if not installable:
        return blocked

    log(f"[env] missing: {', '.join(installable)} — installing into "
        f"{current_env() or os.path.basename(sys.prefix)} ...")
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           *installable]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:                                 # noqa: BLE001
        log(f"[env] auto-install could not run ({exc}). Install by hand:")
        log(f"[env]     {sys.executable} -m pip install {' '.join(installable)}")
        return missing

    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-6:]
        log("[env] auto-install FAILED:")
        for line in tail:
            log(f"[env]   {line}")
        log(f"[env] install by hand: {sys.executable} -m pip install "
            f"{' '.join(installable)}")
        return missing

    # find_spec caches negative lookups on the path finder; clear it or the
    # freshly installed packages still look absent to this process.
    import importlib
    importlib.invalidate_caches()
    still = [x for x in missing_packages() if x in installable]
    if still:
        log(f"[env] installed, but still not importable: {', '.join(still)}. "
            f"A restart of bioscout usually settles it.")
    else:
        log(f"[env] installed {len(installable)} package(s) — continuing.")
    return blocked + still


def _version() -> str:
    from bioscout import __version__
    return __version__


def _sanitise(v: str) -> str:
    """Version -> a name conda and every shell will accept unquoted."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", v)


def expected_env_name(version: Optional[str] = None) -> str:
    """``bioscoutv2.0.0b8`` for bioscout 2.0.0b8."""
    return f"{_ENV_PREFIX}{_sanitise(version or _version())}"


def current_env() -> Optional[str]:
    """Name of the active conda env, else the active venv's folder name."""
    name = os.environ.get("CONDA_DEFAULT_ENV")
    if name:
        return name
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        return os.path.basename(venv.rstrip("/\\"))
    return None


def conda_available() -> bool:
    return shutil.which("conda") is not None


def _run(cmd: List[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def list_envs() -> List[str]:
    """Every conda environment name. Empty list if conda is not on PATH."""
    if not conda_available():
        return []
    try:
        p = _run(["conda", "env", "list", "--json"], timeout=60)
        prefixes = json.loads(p.stdout or "{}").get("envs", [])
    except Exception:                                        # noqa: BLE001
        return []
    return [os.path.basename(p.rstrip("/\\")) for p in prefixes]


def env_exists(name: Optional[str] = None) -> bool:
    return (name or expected_env_name()) in list_envs()


def activation_command(name: Optional[str] = None) -> str:
    return f"conda activate {name or expected_env_name()}"


# --------------------------------------------------------------------------- #
def create_env(name: Optional[str] = None, python: str = DEFAULT_PYTHON,
               log=print) -> bool:
    """``conda create -y -n <name> python=<python>``. Idempotent."""
    name = name or expected_env_name()
    if not conda_available():
        log("[env] conda is not on PATH — cannot create an environment.")
        return False
    if env_exists(name):
        log(f"[env] {name} already exists.")
        return True
    log(f"[env] creating {name} (python {python}) — a minute or two ...")
    p = _run(["conda", "create", "-y", "-n", name, f"python={python}"])
    if p.returncode != 0:
        log(f"[env] conda create failed:\n{(p.stderr or p.stdout)[-1500:]}")
        return False
    log(f"[env] created {name}")
    return True


def _conda_run(name: str, *args: str, timeout: int = 1800):
    # --no-capture-output so pip/uv progress reaches the terminal live; a silent
    # ten-minute install is indistinguishable from a hang.
    return subprocess.run(["conda", "run", "-n", name, "--no-capture-output", *args],
                          text=True, timeout=timeout)


def install_into(name: Optional[str] = None, *, requirements: Optional[str] = None,
                 editable: Optional[str] = None, log=print) -> bool:
    """pip-install uv into ``name``, then let uv install everything else.

    ``requirements`` defaults to the repo's requirements.txt when bioscout is
    running from a source checkout; ``editable`` to that checkout, so the env
    tracks your working tree instead of a release.
    """
    name = name or expected_env_name()
    if not conda_available():
        log("[env] conda is not on PATH.")
        return False
    if not env_exists(name):
        log(f"[env] {name} does not exist — create it first.")
        return False

    root = _repo_root()
    if requirements is None and root:
        cand = os.path.join(root, "requirements.txt")
        requirements = cand if os.path.exists(cand) else None
    if editable is None and root and os.path.exists(os.path.join(root, "setup.py")):
        editable = root

    log(f"[env] {name}: installing uv ...")
    if _conda_run(name, "python", "-m", "pip", "install", "-q", "uv").returncode != 0:
        log("[env] could not install uv — falling back to pip for everything.")
        pipper = ["python", "-m", "pip", "install"]
    else:
        # uv needs to be told which interpreter to install into; inside
        # `conda run -n <name>` sys.executable IS that interpreter.
        pipper = ["python", "-m", "uv", "pip", "install", "--python",
                  _env_python(name) or sys.executable]

    ok = True
    if requirements:
        log(f"[env] {name}: installing from {os.path.basename(requirements)} ...")
        ok &= _conda_run(name, *pipper, "-r", requirements).returncode == 0
    if editable:
        log(f"[env] {name}: installing bioscout (editable) from {editable} ...")
        ok &= _conda_run(name, *pipper, "-e", editable).returncode == 0

    ok &= _install_opensim(name, pipper, log=log)
    log(f"[env] {name}: {'ready' if ok else 'finished WITH ERRORS — read above'}")
    return ok


def _install_opensim(name: str, pipper: List[str], log=print) -> bool:
    """OpenSim: try the wheel, fall back to conda. Never silently skip it."""
    probe = _conda_run(name, "python", "-c", "import opensim", timeout=180)
    if probe.returncode == 0:
        log("[env] opensim: already importable")
        return True
    log("[env] opensim: not present, trying the PyPI wheel ...")
    if _conda_run(name, *pipper, "opensim>=4.6").returncode == 0:
        if _conda_run(name, "python", "-c", "import opensim", timeout=180).returncode == 0:
            log("[env] opensim: installed from PyPI")
            return True
    log("[env] opensim: falling back to conda -c opensim-org ...")
    p = subprocess.run(["conda", "install", "-y", "-n", name, "-c", "opensim-org",
                        "opensim"], text=True, timeout=3600)
    if p.returncode == 0 and _conda_run(name, "python", "-c", "import opensim",
                                        timeout=180).returncode == 0:
        log("[env] opensim: installed from conda")
        return True
    log("[env] opensim: COULD NOT INSTALL. Every OpenSim stage (scaling, IK, ID, "
        "MA, SO, JRA) will refuse to run. See "
        "https://simtk.org/projects/opensim for the manual bindings.")
    return False


def _env_python(name: str) -> Optional[str]:
    for pfx in _env_prefixes():
        if os.path.basename(pfx.rstrip("/\\")) == name:
            for rel in ("python.exe", os.path.join("bin", "python")):
                cand = os.path.join(pfx, rel)
                if os.path.exists(cand):
                    return cand
    return None


def _env_prefixes() -> List[str]:
    if not conda_available():
        return []
    try:
        p = _run(["conda", "env", "list", "--json"], timeout=60)
        return json.loads(p.stdout or "{}").get("envs", [])
    except Exception:                                        # noqa: BLE001
        return []


def _repo_root() -> Optional[str]:
    """The source checkout bioscout is running from, or None if pip-installed."""
    import bioscout
    root = os.path.dirname(os.path.dirname(os.path.abspath(bioscout.__file__)))
    return root if os.path.exists(os.path.join(root, "setup.py")) else None


# --------------------------------------------------------------------------- #
def status() -> Dict[str, object]:
    want = expected_env_name()
    have = current_env()
    return {
        "version": _version(),
        "expected_env": want,
        "current_env": have,
        "match": have == want,
        "conda": conda_available(),
        "env_exists": env_exists(want),
        "activate": activation_command(want),
        "python": sys.executable,
        "repo_root": _repo_root(),
    }


def report(log=print) -> Dict[str, object]:
    s = status()
    log(f"[env] bioscout {s['version']}")
    log(f"[env] expected environment : {s['expected_env']}")
    log(f"[env] current environment  : {s['current_env'] or '(none — base or system python)'}")
    log(f"[env] interpreter          : {s['python']}")
    log(f"[env] conda on PATH        : {'yes' if s['conda'] else 'NO'}")

    # The name can match while the env is still unusable, and can mismatch
    # while everything imports fine. Report what is actually there.
    try:
        _missing = missing_packages()
    except Exception:                                        # noqa: BLE001
        _missing = []
    if _missing:
        log(f"[env] MISSING packages     : {', '.join(_missing)}")
        log(f"[env]     {sys.executable} -m pip install "
            f"{' '.join(p for p in _missing if p not in NEVER_AUTOINSTALL)}")
        for _p in (p for p in _missing if p in NEVER_AUTOINSTALL):
            log(f"[env]     {_p}: conda-managed — do NOT pip install it here.")
    else:
        log("[env] declared packages    : all importable")

    if s["match"]:
        log("[env] OK — you are in the right environment."
            if not _missing else
            "[env] Right environment, but packages are missing (see above).")
        return s
    if not s["conda"]:
        log("[env] conda is not on PATH, so nothing can be created here.")
        return s
    if s["env_exists"]:
        log(f"[env] {s['expected_env']} EXISTS but is not active. Run:")
        log(f"[env]     {s['activate']}")
    else:
        log(f"[env] {s['expected_env']} does not exist yet. Create and populate it:")
        log(f"[env]     bioscout --env-create")
        log(f"[env] then:")
        log(f"[env]     {s['activate']}")
    return s


def ensure(*, create: bool = False, install: bool = True,
           python: str = DEFAULT_PYTHON, log=print) -> Dict[str, object]:
    """Report, and optionally build the environment. Never activates — it can't."""
    s = report(log=log)
    if s["match"] or not s["conda"] or not create:
        return s
    name = str(s["expected_env"])
    if not s["env_exists"] and not create_env(name, python=python, log=log):
        return status()
    if install:
        install_into(name, log=log)
    log("")
    log(f"[env] done. Now run this in YOUR shell — a child process cannot")
    log(f"[env] activate an environment for the shell that started it:")
    log(f"[env]     {activation_command(name)}")
    return status()


def explain_missing(exc: BaseException) -> str:
    """A message that names the missing package AND the command that fixes it.

    A bare ``ModuleNotFoundError: No module named 'numpy'`` tells you what is
    absent but not that bioscout can build the environment for you, so the
    honest next step looks like hand-installing fifteen packages. bioscout has
    had ``--env-create`` (pip installs uv, uv installs the rest) since 2.0.0b8;
    it just never ran unless you already knew to ask for it.

    Stdlib only, like the rest of this module: it has to work in exactly the
    environment where nothing is installed.
    """
    name = getattr(exc, "name", None) or str(exc)
    env = current_env() or "the active environment"
    expected = expected_env_name()
    req = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "requirements.txt")
    # Quoted, always. On Windows this path has backslashes, and git-bash /
    # MINGW64 eat them as escapes when it is bare:
    #   uv pip install -r C:\Git\bioscout\requirements.txt
    #   -> error: File not found: `C:Gitbioscoutrequirements.txt`
    # Double quotes are literal in bash, cmd and PowerShell alike, so one form
    # is copy-pasteable from every shell someone might be in. Spaces in the
    # path (Program Files, OneDrive) need them regardless.
    req_q = f'"{req}"' 
    lines = [
        "",
        "=" * 72,
        f"  bioscout cannot start: '{name}' is not installed in {env}.",
        "=" * 72,
        "",
        "  Build the environment (installs uv, then everything else with it):",
        "",
        "      bioscout --env-create",
        "",
        f"  Or install into the environment you are in right now:",
        "",
        f"      uv pip install -r {req_q}",
        f"      python -m pip install -r {req_q}      (if uv is not available)",
        "",
        "  OpenSim is NOT on that list — it is not installable from PyPI on",
        "  every platform:",
        "",
        "      conda install -c opensim-org opensim",
        "",
    ]
    if expected and env != expected:
        lines += [f"  Note: the expected environment for this build is '{expected}'.",
                  f"  You are in '{env}'.", ""]
    lines += ["=" * 72, ""]
    return "\n".join(lines)


def startup_warning(log=None) -> None:
    """One quiet line when the running env is not the expected one, and a
    dependency check that installs whatever is missing.

    The env-name half is deliberately a warning and never a block: plenty of
    legitimate setups (a shared HPC module, a system python with everything
    present) will never match the name, and refusing to start would be worse
    than useless.

    The dependency half is the one that earns its keep. Comparing names told
    the user they were in 'bioscout_env' instead of 'bioscoutv2.0.0c1' and
    stopped there; the actual failure was `import psutil` several seconds
    later, inside a tab, reported as a crash. ``find_spec`` over the declared
    set costs milliseconds on the normal path (nothing missing → nothing
    printed, nothing run) and turns that crash into a one-line install.

    Set ``BIOSCOUT_NO_AUTO_INSTALL=1`` to keep the check but only be told;
    ``BIOSCOUT_NO_ENV_CHECK=1`` silences both.
    """
    if os.environ.get(_OPT_OUT):
        return
    w = log or (lambda m: print(m, file=sys.stderr))

    try:
        s = status()
        if not s["match"]:
            where = s["current_env"] or "base/system python"
            w(f"[env] running in '{where}', expected '{s['expected_env']}'. "
              f"`bioscout --env` for details, {_OPT_OUT}=1 to silence.")
    except Exception:                                        # noqa: BLE001
        pass

    # Never let the dependency check be the thing that stops a launch: a
    # broken check is strictly worse than no check.
    try:
        if os.environ.get(_NO_AUTOINSTALL):
            missing = missing_packages()
            if missing:
                w(f"[env] missing packages: {', '.join(missing)}")
                w(f"[env]     {sys.executable} -m pip install {' '.join(missing)}")
            return
        autoinstall_missing(log=w)
    except Exception as exc:                                 # noqa: BLE001
        w(f"[env] dependency check skipped ({type(exc).__name__}: {exc})")


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="python -m bioscout.envcheck",
        description="Check, and optionally create, bioscout's conda environment.")
    ap.add_argument("--create", action="store_true",
                    help="create the environment if missing and install into it")
    ap.add_argument("--no-install", action="store_true",
                    help="with --create, make the env but install nothing")
    ap.add_argument("--python", default=DEFAULT_PYTHON,
                    help=f"python version for a new env (default {DEFAULT_PYTHON})")
    a = ap.parse_args(argv)
    s = ensure(create=a.create, install=not a.no_install, python=a.python)
    return 0 if s["match"] or s["env_exists"] else 1


if __name__ == "__main__":
    sys.exit(main())
