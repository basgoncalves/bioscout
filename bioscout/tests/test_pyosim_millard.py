"""bioscout.pyosim.millard reproduces OpenSim's Millard curves (reference values from opensim 4.6)."""
import unittest
import numpy as np
from bioscout.pyosim import millard

AFL_K2L = dict(min_norm_active_fiber_length=0.25, transition_norm_fiber_length=0.77,
               max_norm_active_fiber_length=1.9, shallow_ascending_slope=0.75, minimum_value=0.0)
REF_AFL_K2L = [(0.3, 0.013814140736), (0.6, 0.619028109238), (0.9, 0.962436924069), (1.0, 1.0),
               (1.3, 0.718600513879), (1.7, 0.218883310162)]
REF_AFL_DEF = [(0.5, 0.117653354928), (0.8, 0.87067661328), (1.1, 0.95737553228), (1.6, 0.263661676264)]
REF_FV = [(-0.95, 0.0028515625), (-0.5, 0.158085604442), (-0.1, 0.625214284313), (0.0, 1.0),
          (0.1, 1.225153837754), (0.5, 1.331131569314), (0.95, 1.3991328125)]


class TestMillardCurves(unittest.TestCase):
    def _check(self, curve, ref):
        x = np.array([r[0] for r in ref]); y = np.array([r[1] for r in ref])
        np.testing.assert_allclose(curve(x), y, atol=1e-9)

    def test_active_force_length(self):
        self._check(millard.active_force_length(AFL_K2L), REF_AFL_K2L)
        self._check(millard.active_force_length(), REF_AFL_DEF)

    def test_force_velocity(self):
        self._check(millard.force_velocity(), REF_FV)


if __name__ == "__main__":
    unittest.main()
