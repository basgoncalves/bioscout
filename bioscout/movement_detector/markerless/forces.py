"""
forces.py -- pluggable muscle-force prediction.

The app treats the force model as a swappable component. It knows three things
about any model: what input coordinates it wants, what muscles it returns, and
whether it is actually valid for the activity being analysed.

That last one matters here. The bundled model
(models/kinematics_only_model.pkl) is a CEINMS surrogate trained on the FAIS
GAIT dataset. Its 80 outputs are all lower-limb muscles -- glutes, hamstrings,
quadriceps, adductors, triceps surae. It contains no latissimus dorsi, no
biceps, no brachialis, no trapezius, i.e. none of the muscles that do the work
in a pull-up. It is wired in so the pipeline is exercised end to end, and it
reports itself as NOT VALID for pull-ups. Swap in an upper-limb model by
implementing ForceModel and registering it; nothing else in the app changes.
"""
from __future__ import annotations

import os
import pickle

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")


class Validity:
    """How much the caller should trust a prediction.

    The middle rung matters. A model can be wrong about an activity in two very
    different ways: it may not model the relevant muscles AT ALL (a gait model
    asked about a pull-up), or it may model exactly the right muscles but have
    been fitted on a different task (a gait model asked about a squat). The
    first is meaningless; the second is a testable hypothesis.
    """
    VALID = "valid"                  # trained on this activity
    EXTRAPOLATED = "extrapolated"    # right muscles and joints, different task
    OUT_OF_DOMAIN = "out_of_domain"  # cannot represent this activity at all
    UNAVAILABLE = "unavailable"      # no model loaded


class ForceModel:
    """Interface every force model implements.

    name            short identifier
    feature_names   OpenSim coordinate names the model consumes, in order
    target_names    muscle names the model returns, in order
    validity_for(activity) -> (Validity, human-readable reason)
    predict(coords, n_frames) -> (n_frames, n_targets) array of Newtons
    """

    name = "base"
    feature_names: list = []
    target_names: list = []

    def validity_for(self, activity):
        return Validity.UNAVAILABLE, "no model"

    def predict(self, coords, n_frames):
        raise NotImplementedError

    # -- shared helper -----------------------------------------------------
    #: Value used for coordinates the pipeline cannot measure. "mean" uses the
    #: model's own training mean, which puts the unknown coordinate at zero
    #: standard deviations -- the average posture the model saw. "zero" writes
    #: a literal 0 deg, which for a coordinate whose training mean is far from
    #: zero is itself an extrapolation, and a gratuitous one.
    fill_strategy = "mean"

    def fill_values(self):
        """Per-feature default. Subclasses with training stats override this."""
        return np.zeros(len(self.feature_names))

    def build_matrix(self, coords, n_frames):
        """Assemble (n_frames, n_features) from a {coord_name: array} dict.

        Coordinates the model wants but the pipeline cannot measure are filled
        per fill_strategy. The names are returned so callers can report them --
        a large fill count is itself a reason to distrust the output.
        """
        defaults = (self.fill_values() if self.fill_strategy == "mean"
                    else np.zeros(len(self.feature_names)))
        X = np.tile(np.asarray(defaults, float), (n_frames, 1))
        missing = []
        for j, fname in enumerate(self.feature_names):
            arr = coords.get(fname)
            if arr is None:
                missing.append(fname)
                continue
            X[:, j] = np.asarray(arr, float)[:n_frames]
        return X, missing


class NullForceModel(ForceModel):
    """Placeholder used when no model file is present. Predicts nothing."""

    name = "none"

    def validity_for(self, activity):
        return Validity.UNAVAILABLE, "No force model is installed."

    def predict(self, coords, n_frames):
        return np.zeros((n_frames, 0))


class NumpyMLPModel(ForceModel):
    """Two-layer numpy MLP stored as a pickled dict of arrays.

    Expected keys: W1 b1 W2 b2 xm xs ym ys feat targ info.
    Forward pass is standardise -> linear -> activation -> linear ->
    de-standardise -> inverse output transform. Pure numpy, so it needs no ML
    runtime on the phone.

    Two things about the bundled pickle were not recorded in the file and are
    therefore parameters here, defaulting to the most likely values:

    activation
        "tanh" or "relu". ym lies in 0.65..5.77 and ys in 1.10..3.71, so the
        stored targets are standardised log1p forces (the same convention the
        torch MuscleForceNet in the training repo uses). Evaluated at the
        training mean, tanh yields peak forces around 2e4 N and relu around
        5e8 N, so tanh is the plausible one -- but confirm it with
        tools/calibrate_model.py against a gait trial that has ground-truth
        MuscleForces.sto before trusting absolute magnitudes.

    output_transform
        "expm1" undoes the log1p, "none" leaves the de-standardised value.
    """

    def __init__(self, path, activation="tanh", output_transform="expm1",
                 trained_on="unknown", valid_activities=(),
                 related_activities=()):
        with open(path, "rb") as fh:
            m = pickle.load(fh)
        self.W1 = np.asarray(m["W1"], float)
        self.b1 = np.asarray(m["b1"], float)
        self.W2 = np.asarray(m["W2"], float)
        self.b2 = np.asarray(m["b2"], float)
        self.xm = np.asarray(m["xm"], float)
        self.xs = np.asarray(m["xs"], float)
        self.ym = np.asarray(m["ym"], float)
        self.ys = np.asarray(m["ys"], float)
        self.feature_names = list(m["feat"])
        self.target_names = list(m["targ"])
        self.info = m.get("info", "")
        self.activation = activation
        self.output_transform = output_transform
        self.trained_on = trained_on
        self.valid_activities = set(valid_activities)
        #: Activities using the same muscles and joints as the training task,
        #: but not the training task itself -- extrapolation, not nonsense.
        self.related_activities = set(related_activities)
        self.name = os.path.splitext(os.path.basename(path))[0]

        n_in, n_hid = self.W1.shape
        if n_in != len(self.feature_names):
            raise ValueError("W1 rows (%d) != feature count (%d)"
                             % (n_in, len(self.feature_names)))
        if self.W2.shape != (n_hid, len(self.target_names)):
            raise ValueError("W2 shape %s inconsistent with hidden/target sizes"
                             % (self.W2.shape,))

    def validity_for(self, activity):
        if activity in self.valid_activities:
            return Validity.VALID, "Trained on %s." % self.trained_on
        if activity in self.related_activities:
            return Validity.EXTRAPOLATED, (
                "Trained on %s, not on %s. The output muscles and joints are "
                "the right ones for this movement, so the prediction is a "
                "plausible extrapolation rather than a category error -- but "
                "it is unvalidated, and the model sees only joint angles, so "
                "it cannot know what external load you are carrying. Check the "
                "input z-scores before trusting magnitudes."
                % (self.trained_on, activity))
        return Validity.OUT_OF_DOMAIN, (
            "Trained on %s. Its %d outputs are lower-limb muscles only, so it "
            "cannot represent %s. Numbers shown are a pipeline demonstration, "
            "not a biomechanical estimate."
            % (self.trained_on, len(self.target_names), activity))

    def fill_values(self):
        """The standardisation mean IS the training mean, in degrees."""
        return self.xm

    def input_zscores(self, coords, n_frames):
        """How far each supplied coordinate sits from the training data.

        Returns [(name, mean_z, max_abs_z, measured), ...]. This is the honest
        readout of whether a new activity is inside the model's experience:
        anything beyond roughly 3 sigma is extrapolation, whatever the
        prediction looks like.
        """
        X, missing = self.build_matrix(coords, n_frames)
        xs = np.where(np.abs(self.xs) < 1e-12, 1.0, self.xs)
        Z = (X - self.xm) / xs
        out = []
        for j, name in enumerate(self.feature_names):
            out.append((name, float(np.mean(Z[:, j])),
                        float(np.max(np.abs(Z[:, j]))),
                        name not in missing))
        return out

    def _activate(self, H):
        if self.activation == "relu":
            return np.maximum(H, 0.0)
        return np.tanh(H)

    def predict(self, coords, n_frames):
        X, missing = self.build_matrix(coords, n_frames)
        self.last_missing = missing
        xs = np.where(np.abs(self.xs) < 1e-12, 1.0, self.xs)
        Z = (X - self.xm) / xs
        H = self._activate(Z @ self.W1 + self.b1)
        Y = (H @ self.W2 + self.b2) * self.ys + self.ym
        if self.output_transform == "expm1":
            # Targets were stored as log1p(force); clip first so a wild
            # extrapolation cannot overflow to inf.
            Y = np.expm1(np.clip(Y, -20.0, 20.0))
        return Y


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------
def _kinematics_only():
    path = os.path.join(MODELS_DIR, "kinematics_only_model.pkl")
    if not os.path.exists(path):
        return None
    return NumpyMLPModel(
        path,
        activation="tanh",
        output_transform="expm1",
        trained_on="the FAIS gait dataset (CEINMS surrogate, walking/running)",
        # AUDITED 2026-09-02 and FAILED: see models/MODEL_CARD.md. On a real
        # training-set gait trial with all 34 inputs present it peaks at
        # 113,250 N, and moving knee_angle_r a single standard deviation off
        # the training mean takes it from 1,110 N to 32,583 N. It is not valid
        # for ANY activity, gait included, so it claims none.
        valid_activities=set(),
        related_activities=set(),
    )


REGISTRY = {
    "kinematics_only": _kinematics_only,
    "none": lambda: NullForceModel(),
}


def load_model(key="none"):
    """Load a registered model, falling back to the null model."""
    factory = REGISTRY.get(key)
    if factory is None:
        return NullForceModel()
    try:
        model = factory()
    except Exception:
        return NullForceModel()
    return model or NullForceModel()


#: No human muscle produces more than a few thousand newtons; the largest in
#: the Rajagopal model (vastus lateralis) has a max isometric force near
#: 5000 N. Anything above this is arithmetic, not biomechanics.
MAX_PLAUSIBLE_FORCE_N = 5000.0


def implausible_fraction(forces, ceiling=MAX_PLAUSIBLE_FORCE_N):
    """Fraction of predicted values above any physiological ceiling.

    Worth checking on EVERY prediction, because a model with log-space targets
    fails in a specific and dangerous way: the inputs can sit only two or three
    standard deviations outside the training data -- which looks acceptable on
    an input-domain check -- while the de-standardised output is exponentiated,
    turning that modest extrapolation into an answer wrong by three orders of
    magnitude. The input check alone will not catch it. This will.
    """
    if forces is None or not getattr(forces, "size", 0):
        return 0.0
    return float(np.mean(np.abs(forces) > ceiling))


def summarise(forces, target_names, top_n=8):
    """Peak force per muscle, biggest first -> [(muscle, peak_N), ...]."""
    if forces.size == 0:
        return []
    peaks = np.nanmax(np.abs(forces), axis=0)
    order = np.argsort(peaks)[::-1][:top_n]
    return [(target_names[i], float(peaks[i])) for i in order]
