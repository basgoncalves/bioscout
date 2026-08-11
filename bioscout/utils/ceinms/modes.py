"""CEINMS execution modes — how many solves, and what the result *is*.

CEINMS execution needs three objective weights (Sartori et al. 2014, Eq. 1):

    F_obj = alpha * E_trackMOM + beta * E_sumEXC + gamma * E_trackEMG

`alpha` weights joint-moment tracking, `beta` is an EFFORT penalty (sum of
squared excitations), `gamma` is the EMG-TRACKING weight. Only the RATIOS
beta/alpha and gamma/alpha are identifiable — scaling an objective cannot move
its minimum — which is why alpha is conventionally fixed at 1.

Choosing gamma is not a solved problem, and the choice is not cosmetic: on the
powerlifting dataset this module was written for, gamma moved hip contact force
by several body weights. So `bioscout` does not pretend there is one right way
to run CEINMS. It offers five, and asks you to say which one you used.

    single      one solve at the (alpha, beta, gamma) you name
    bounds      three solves: lower, production, upper -> an estimate + a band
    full_loop   a grid over the ranges you name -> a range + a median
    lcurve      Sartori's L-curve sweep, production taken from the knee
    optimise    CEINMSoptimise searches the weights itself (slow)

Set it in session.yaml::

    ceinms:
      mode: bounds
      alpha: 1
      beta: 1
      gamma: 30
      gamma_bounds: [10, 100]

or in a project settings file as ``CEINMSSettings.mode``. Default is `single`,
so existing projects keep their behaviour.

WHAT EACH MODE LEAVES ON DISK
    Every mode writes one output folder per solve, named
    ``Execution_a<alpha>_b<beta>_g<gamma>``, and a manifest
    ``ceinms/ceinms_modes_manifest.json`` listing them with the production arm
    flagged. The PRODUCTION arm is always solved LAST, so whatever the trial's
    `jra_forces_ceinms` points at when the mode returns is the production
    result -- a run that dies half way leaves a tree that is incomplete rather
    than one that silently describes the wrong weighting.

A NOTE ON `lcurve`, WHICH IS WHY THE OTHER MODES EXIST
    The L-curve procedure locates the knee of the trade-off between normalised
    moment-tracking and EMG-tracking error. It is the published method and it
    is implemented here faithfully, tie-break included. It is also, on some
    datasets, NOT IDENTIFIABLE: when the curve is nearly flat past the elbow,
    both axes are normalised to their own extremes and the knee tracks the
    RANGE SWEPT rather than the data. Measured on this project's squat trials,
    the knee came out at exactly one tenth of the upper bound of the gamma
    range, in five nested ranges out of five.

    `lcurve` therefore reports `knee_gamma_over_range_top` in its manifest. If
    that ratio is the same across two different sweeps, the knee is an artefact
    of your grid and you should use `bounds` or `full_loop` and report a band
    instead of a point.
"""
from __future__ import annotations

import io
import json
import os

MODES = {
    "single": "One solve at the alpha/beta/gamma you name. The result is a "
              "single curve. Cheapest, and correct when the weighting is "
              "already justified elsewhere.",
    "bounds": "Three solves — a lower gamma, the production gamma, and an "
              "upper gamma. The result is the production estimate PLUS a "
              "sensitivity band showing how much the weighting moved it. Use "
              "this when you must report how sensitive the answer is without "
              "paying for a full grid.",
    "full_loop": "A grid over the alpha/beta/gamma ranges you name. The result "
                 "is a range with a median across the grid. Use when you want "
                 "the distribution rather than a bracket; cost is the product "
                 "of the range lengths.",
    "lcurve": "Sartori's L-curve sweep over beta and gamma, with the knee "
              "located by the L-method. Production is taken from the knee. "
              "Verify the knee is not an artefact of the swept range before "
              "trusting it — see the module docstring.",
    "optimise": "CEINMSoptimise searches the weight space itself. No sweep to "
                "configure, but far the slowest, and its configuration is "
                "built separately from the execution one — check the tracked "
                "dofSet matches.",
}

DEFAULT_MODE = "single"

# Sartori et al. 2014, Table 2 sweeps, sub-sampled. Only used when a mode needs
# a grid and the project did not supply one.
_DEFAULT_BETAS = [0, 0.2, 1, 3, 10, 30, 100, 300]
_DEFAULT_GAMMAS = [0, 1, 3, 10, 30, 100, 300, 1000, 3000]


class ModeError(ValueError):
    pass


def _num(x):
    f = float(x)
    return int(f) if f == int(f) else f


def fmt(v):
    """Weight -> the string used in folder names. Matches the existing
    `Execution_a{alpha}_b{beta}_g{gamma}` convention, so a `single` run keeps
    the exact folder name it had before modes existed."""
    return ("%g" % float(v)) if not isinstance(v, str) else v


def _get(trial, *names, default=None):
    """First attribute present on the trial, else `default`.

    Config reaches a trial as plain attributes (Session._apply_session_config),
    and different projects spell the same idea differently, so each option is
    looked up under every name it has had.
    """
    for n in names:
        v = getattr(trial, n, None)
        if v is not None:
            return v
    return default


def _seq(v, what):
    if v is None:
        return None
    if isinstance(v, str):
        v = [x for x in v.replace(",", " ").split() if x]
    try:
        return [_num(x) for x in v]
    except (TypeError, ValueError):
        raise ModeError("%s must be a list of numbers, got %r" % (what, v))


def resolve(trial):
    """-> (mode, arms). `arms` is a list of dicts, PRODUCTION LAST::

        {"alpha":1, "beta":1, "gamma":10, "tag":"g10", "production":False}

    The production arm carries ``tag=None``: its outputs keep the plain,
    untagged filenames, so downstream code that knows nothing about modes
    reads the production result by default.
    """
    mode = str(_get(trial, "ceinms_mode", "mode", default=DEFAULT_MODE)).strip().lower()
    if mode not in MODES:
        raise ModeError("unknown CEINMS mode %r — choose one of: %s"
                        % (mode, ", ".join(sorted(MODES))))

    a = _num(_get(trial, "alpha", default=1))
    b = _num(_get(trial, "beta", default=1))
    g = _num(_get(trial, "gamma", default=1))

    def arm(al, be, ga, production=False):
        return {"alpha": _num(al), "beta": _num(be), "gamma": _num(ga),
                "tag": None if production else "a%s_b%s_g%s" % (fmt(al), fmt(be), fmt(ga)),
                "production": bool(production)}

    if mode in ("single", "optimise"):
        return mode, [arm(a, b, g, production=True)]

    if mode == "bounds":
        lo_hi = _seq(_get(trial, "gamma_bounds", "ceinms_gamma_bounds"),
                     "gamma_bounds")
        if not lo_hi or len(lo_hi) != 2:
            raise ModeError("mode 'bounds' needs gamma_bounds: [lower, upper]")
        lo, hi = sorted(lo_hi)
        if not (lo < g < hi):
            # Not fatal, but it is almost always a mistake: a band that does
            # not contain the estimate cannot be read as a sensitivity around
            # it, and silently plotting one would misrepresent the result.
            raise ModeError("gamma_bounds %s must bracket the production gamma "
                            "%s" % (lo_hi, g))
        return mode, [arm(a, b, lo), arm(a, b, hi), arm(a, b, g, production=True)]

    if mode == "full_loop":
        als = _seq(_get(trial, "alpha_range", "alphas"), "alpha_range") or [a]
        bes = _seq(_get(trial, "beta_range", "betas"), "beta_range") or [b]
        gas = _seq(_get(trial, "gamma_range", "gammas"), "gamma_range") or [g]
        arms = [arm(al, be, ga) for al in als for be in bes for ga in gas
                if not (al == a and be == b and ga == g)]
        arms.append(arm(a, b, g, production=True))
        return mode, arms

    if mode == "lcurve":
        bes = _seq(_get(trial, "lcurve_betas", "beta_range"), "lcurve_betas") \
            or list(_DEFAULT_BETAS)
        gas = _seq(_get(trial, "lcurve_gammas", "gamma_range"), "lcurve_gammas") \
            or list(_DEFAULT_GAMMAS)
        # The production arm is not known until the sweep has been read, so it
        # is appended by `run` once the knee is found.
        return mode, [arm(a, be, ga) for be in bes for ga in gas]

    raise ModeError("unreachable: %s" % mode)          # pragma: no cover


# ------------------------------------------------------------------ the sweep
def read_components(path):
    """-> (E_trackMOM, E_sumEXC, E_trackEMG, alpha, beta, gamma) summed over
    frames, or None.

    Hand-parsed on purpose. `ObjectiveFunctionComponentsAndWeightings.sto`
    declares `datacolumns 7` and then lists every muscle in its name row, so a
    reader that trusts the header sees the mismatch and drops every data row —
    silently returning an empty frame rather than raising.
    """
    if not os.path.exists(path):
        return None
    tot, w, n = [0.0, 0.0, 0.0], None, 0
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        seen = False
        for line in fh:
            if not seen:
                seen = line.strip().lower() == "endheader"
                continue
            f = [x for x in line.replace("\r", "").rstrip("\n").split("\t")
                 if x.strip()]
            if len(f) < 7:
                continue
            try:
                v = [float(x) for x in f[-6:]]
            except ValueError:
                continue                      # the muscle-name row
            for i in range(3):
                tot[i] += v[i]
            w = tuple(v[3:]); n += 1
    return None if not n else tuple(tot) + (w or (float("nan"),) * 3)


def _l_method(x, y):
    """Salvador & Chan's L-method: split at every interior point, fit a line
    either side, keep the split with the lowest total RMSE.

    -> (index, rmse_two_segment, rmse_single_line). The single-line RMSE is
    returned so the caller can ask whether there is an elbow AT ALL rather
    than assuming one — a straight curve still yields a "best" split.
    """
    n = len(x)
    if n < 4:
        return None
    try:
        import numpy as np
    except ImportError:                                  # pragma: no cover
        return None
    x, y = np.asarray(x, float), np.asarray(y, float)
    p1 = np.polyfit(x, y, 1)
    rmse1 = float(np.sqrt(np.mean((np.polyval(p1, x) - y) ** 2)))
    best = None
    for c in range(2, n - 1):
        la = np.polyfit(x[:c], y[:c], 1)
        lb = np.polyfit(x[c - 1:], y[c - 1:], 1)
        e = (np.sum((np.polyval(la, x[:c]) - y[:c]) ** 2) +
             np.sum((np.polyval(lb, x[c - 1:]) - y[c - 1:]) ** 2))
        r = float((e / n) ** 0.5)
        if best is None or r < best[0]:
            best = (r, c)
    return best[1] - 1, best[0], rmse1


def lcurve_knee(records, tol=0.01):
    """Sartori's knee from a swept grid.

    `records` is [{"beta","gamma","E_trackMOM","E_sumEXC","E_trackEMG"}, ...].
    -> dict with the chosen beta/gamma and the diagnostics that say whether to
    believe it, or None.

    Two details are theirs, not inventions. Terms are normalised to their own
    maximum over the sweep. And the 'best' curve takes, at each gamma, the
    lowest normalised E_trackMOM — but among betas within `tol` of that
    minimum it takes the one with the LOWEST E_sumEXC, because low E_sumEXC
    "ensured excitation peaks were distributed across all MTUs and prevented
    them from saturating". Without that tie-break beta = 0 wins every point by
    construction (removing the effort penalty can only help moment tracking)
    and the procedure always returns beta = 0, which their Table 2 never does.
    """
    rs = [r for r in records if r.get("E_trackMOM") is not None]
    if len(rs) < 4:
        return None
    mx = {k: max(abs(r[k]) for r in rs) or 1.0
          for k in ("E_trackMOM", "E_sumEXC", "E_trackEMG")}
    for r in rs:
        for k in mx:
            r["n_" + k] = r[k] / mx[k]

    best = []
    for ga in sorted({r["gamma"] for r in rs}):
        at = [r for r in rs if r["gamma"] == ga]
        lo = min(r["n_E_trackMOM"] for r in at)
        near = [r for r in at if r["n_E_trackMOM"] <= lo + tol]
        best.append(min(near, key=lambda r: r["n_E_sumEXC"]))
    best.sort(key=lambda r: r["n_E_trackEMG"])

    lm = _l_method([r["n_E_trackEMG"] for r in best],
                   [r["n_E_trackMOM"] for r in best])
    if lm is None:
        return None
    i, rmse2, rmse1 = lm
    knee = best[i]
    top = max(r["gamma"] for r in rs) or 1.0
    return {
        "beta": knee["beta"], "gamma": knee["gamma"],
        "n_E_trackEMG": knee["n_E_trackEMG"],
        "n_E_trackMOM": knee["n_E_trackMOM"],
        "rmse_two_segment": rmse2, "rmse_single_line": rmse1,
        # > ~2 means there is a real elbow; near 1 means the curve is straight
        # and the "knee" is just the best place to break a line.
        "elbow_ratio": (rmse1 / rmse2) if rmse2 else float("nan"),
        # The artefact detector. Sweep two different gamma ranges: if this
        # ratio is unchanged, the knee is a property of the grid, not the data.
        "gamma_range_top": top,
        "knee_gamma_over_range_top": knee["gamma"] / top,
    }


# ------------------------------------------------------------------- the run
def manifest_path(trial):
    return os.path.join(_ceinms_dir(trial), "ceinms_modes_manifest.json")


def _ceinms_dir(trial):
    d = getattr(trial, "ceinms_exe_dir", None) or "ceinms"
    d = os.path.dirname(str(d)) or "ceinms"
    base = getattr(trial, "path", ".")
    return os.path.join(base, d) if not os.path.isabs(d) else d


def _newest_output(cdir):
    """The Execution_* folder this solve just wrote, found by mtime.

    Not by reconstructing the name: bioscout formats the folder from its own
    copy of the weights, so "30" here can be "30.0" there, and a name-based
    lookup then reports a successful solve as missing.
    """
    import glob
    hits = glob.glob(os.path.join(cdir, "Execution_*"))
    return max(hits, key=os.path.getmtime) if hits else None


def _set_weights(trial, al, be, ga):
    """Set the execution weights WHERE THE TRIAL ACTUALLY READS THEM.

    Setting the attributes alone is not enough. Session._apply_session_config
    stores session.yaml's values in `trial._overrides` and those win, so an arm
    that assigned `trial.gamma = 30` still solved at session.yaml's `30.0` --
    every arm wrote to the SAME output folder and overwrote the last, leaving
    one solve where the manifest claimed three. Observed 2026-08-10: a `bounds`
    run produced a single Execution_a1_b1_g30.0 while the manifest listed
    g10/g100/g30, all flagged ok=false because the names it expected were never
    written. Both places are set here, and `ok` is confirmed from disk.
    """
    trial.alpha, trial.beta, trial.gamma = al, be, ga
    ov = getattr(trial, "_overrides", None)
    if isinstance(ov, dict):
        ov["alpha"], ov["beta"], ov["gamma"] = al, be, ga


def run(trial, single_fn, log=None):
    """Execute every arm the mode calls for, production LAST, and write the
    manifest. `single_fn()` is the trial's one-shot execution, which reads
    trial.alpha/beta/gamma — so an arm is applied by setting those and calling
    it, which is also why the originals are restored in a finally block.

    -> the manifest dict.
    """
    def _say(m):
        if log:
            log(m)

    mode, arms = resolve(trial)
    _say("[ceinms] mode=%s — %d solve(s)" % (mode, len(arms)))

    if mode == "optimise":
        # Deliberately not reimplemented here: CEINMSoptimise builds its own
        # cfg, and duplicating that is how the two drift apart. Callers route
        # to the existing optimise path; this module only records the choice.
        return _write(trial, mode, [], None,
                      note="optimise is run by the CEINMSoptimise path, not by "
                           "the execution loop")

    a0 = (getattr(trial, "alpha", None), getattr(trial, "beta", None),
          getattr(trial, "gamma", None))
    done, records = [], []
    try:
        for k, arm in enumerate(arms):
            _set_weights(trial, arm["alpha"], arm["beta"], arm["gamma"])
            _say("[ceinms]   arm %d/%d  a=%s b=%s g=%s%s"
                 % (k + 1, len(arms), fmt(arm["alpha"]), fmt(arm["beta"]),
                    fmt(arm["gamma"]), "   (PRODUCTION)" if arm["production"] else ""))
            single_fn()
            out = _newest_output(_ceinms_dir(trial))
            arm = dict(arm, output_dir=out or "",
                       ok=bool(out) and os.path.exists(
                           os.path.join(out, "MuscleForces.sto")))
            done.append(arm)
            c = read_components(os.path.join(
                out, "ObjectiveFunctionComponentsAndWeightings.sto"))
            if c:
                records.append({"beta": arm["beta"], "gamma": arm["gamma"],
                                "E_trackMOM": c[0], "E_sumEXC": c[1],
                                "E_trackEMG": c[2]})

        knee = None
        if mode == "lcurve":
            knee = lcurve_knee(records)
            if knee is None:
                _say("[ceinms]   L-curve: not enough solves to locate a knee")
            else:
                _say("[ceinms]   knee: beta=%s gamma=%s  (elbow %.1fx, "
                     "knee/range-top %.3f)"
                     % (fmt(knee["beta"]), fmt(knee["gamma"]),
                        knee["elbow_ratio"], knee["knee_gamma_over_range_top"]))
                if knee["elbow_ratio"] < 2:
                    _say("[ceinms]   [warn] two-segment fit beats a straight "
                         "line by less than 2x — this curve has no real elbow, "
                         "so the knee is not meaningful.")
                # production = the knee, solved last so it is what stays
                _set_weights(trial, a0[0], knee["beta"], knee["gamma"])
                _say("[ceinms]   arm %d/%d  a=%s b=%s g=%s   (PRODUCTION, from knee)"
                     % (len(arms) + 1, len(arms) + 1, fmt(a0[0]),
                        fmt(knee["beta"]), fmt(knee["gamma"])))
                single_fn()
                out = os.path.join(_ceinms_dir(trial),
                                   "Execution_a%s_b%s_g%s"
                                   % (fmt(a0[0]), fmt(knee["beta"]), fmt(knee["gamma"])))
                done.append({"alpha": a0[0], "beta": knee["beta"],
                             "gamma": knee["gamma"], "tag": None,
                             "production": True, "output_dir": out,
                             "ok": os.path.exists(os.path.join(out, "MuscleForces.sto"))})
    finally:
        # Leave the trial describing the PRODUCTION arm whatever happened. A
        # half-finished run must not leave alpha/beta/gamma pointing at some
        # bracket arm that later code would take for the real answer.
        prod = next((d for d in reversed(done) if d.get("production")), None)
        if prod:
            _set_weights(trial, prod["alpha"], prod["beta"], prod["gamma"])
        elif a0[0] is not None:
            _set_weights(trial, *a0)

    return _write(trial, mode, done, knee)


def _write(trial, mode, arms, knee, note=None):
    m = {"mode": mode, "description": MODES.get(mode, ""), "arms": arms,
         "production": next((a for a in arms if a.get("production")), None),
         "knee": knee}
    if note:
        m["note"] = note
    try:
        os.makedirs(_ceinms_dir(trial), exist_ok=True)
        with io.open(manifest_path(trial), "w", encoding="utf-8") as fh:
            json.dump(m, fh, indent=1)
    except OSError:
        pass
    return m


# --------------------------------------------------------------- aggregation
def aggregate_band(values_by_arm):
    """Turn per-arm results into what the mode promises the reader.

    `values_by_arm` maps an arm label to a value (or an array-like). Returns
    ``{"production", "low", "high", "median", "n"}``.

    `production` is the estimate you quote — the value from the production
    arm, NOT the median. The other arms are brackets chosen to expose a
    sensitivity, not samples of equal standing, so averaging over them would
    invent a central tendency that means nothing. `median` is reported anyway
    because `full_loop` sweeps a grid dense enough for it to be descriptive.
    """
    import numpy as np
    if not values_by_arm:
        return None
    keys = list(values_by_arm)
    prod = values_by_arm.get("production", values_by_arm[keys[-1]])
    stack = np.array([np.asarray(values_by_arm[k], dtype=float) for k in keys])
    return {"production": np.asarray(prod, dtype=float),
            "low": np.nanmin(stack, axis=0),
            "high": np.nanmax(stack, axis=0),
            "median": np.nanmedian(stack, axis=0),
            "n": len(keys)}


# ------------------------------------------------------------------ the class
class ExecutionMode(object):
    """The chosen CEINMS execution mode, and everything that follows from it.

    Reachable as ``bioscout.utils.ceinms.ExecutionMode`` -- `ceinms.py`
    re-exports it, so there is one API surface even though the logic lives
    here.

    WHY THE LOGIC LIVES IN ITS OWN MODULE RATHER THAN IN ceinms.py
        `ceinms.py` imports opensim, scipy, matplotlib and pandas at module
        top, is shadowed by the same-named `utils/ceinms/` package, and is
        loaded by that package inside a `try/except Exception` that degrades to
        "binary package only". `utils/__init__` likewise starts with
        `ceinms = None`.

        Mode selection must not inherit any of that. If resolving `mode:
        bounds` depended on OpenSim importing, a missing DLL would turn a
        three-arm sensitivity run into a one-arm run WITHOUT an error -- the
        config option would be silently ignored. This module imports only the
        standard library (numpy arrives lazily, inside the two functions that
        need it), so `mode` is parsed and validated the same way whether or not
        the solver can start.

        >>> ExecutionMode.describe()          # works with no OpenSim present

    Usage::

        m = ExecutionMode(trial)
        print(m.mode, len(m.arms))
        manifest = m.run(trial.run_ceinms_exe_single)
    """

    __slots__ = ("trial", "_mode", "_arms", "manifest")

    def __init__(self, trial):
        self.trial = trial
        self._mode, self._arms = resolve(trial)
        self.manifest = None

    # -- what was chosen ---------------------------------------------------
    @property
    def mode(self):
        return self._mode

    @property
    def arms(self):
        """The solves this mode will run, PRODUCTION LAST. For `lcurve` this is
        the sweep only — the production arm is appended once the knee is known,
        which is why it cannot be listed up front."""
        return list(self._arms)

    @property
    def description(self):
        return MODES[self._mode]

    @property
    def n_solves(self):
        return len(self._arms) + (1 if self._mode == "lcurve" else 0)

    def __repr__(self):
        return "<ExecutionMode %s: %d solve(s)>" % (self._mode, self.n_solves)

    # -- doing it ----------------------------------------------------------
    def run(self, single_fn, log=None):
        """Execute every arm, production last, and write the manifest."""
        self.manifest = run(self.trial, single_fn, log=log)
        return self.manifest

    # -- helpers, exposed so callers need only this class -------------------
    @staticmethod
    def aggregate(values_by_arm):
        return aggregate_band(values_by_arm)

    @staticmethod
    def knee(records, tol=0.01):
        return lcurve_knee(records, tol=tol)

    @classmethod
    def describe(cls, mode=None):
        """One-line description of a mode, or of all of them."""
        if mode:
            m = str(mode).strip().lower()
            if m not in MODES:
                raise ModeError("unknown CEINMS mode %r" % mode)
            return MODES[m]
        return dict(MODES)
