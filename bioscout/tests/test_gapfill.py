"""Tests for bioscout.utils.gapfill — marker gap filling.

Every test here is about the same thing: a gap filler that is wrong is worse
than one that does nothing, because OpenSim's IK ignores an absent marker and
believes a fabricated one. So the assertions are as much about what the filler
REFUSES as about what it fills.

Synthetic fixtures only (numpy), so this runs anywhere.
"""
import unittest

import numpy as np

from bioscout.utils import gapfill as gf


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _rigid_body(n=400, seed=0, markers=None, extra=None):
    """A rigid 5-marker cluster carried through a random-walk pose, optionally
    with extra markers on an INDEPENDENTLY moving second segment."""
    rng = np.random.default_rng(seed)
    base = np.array(markers if markers is not None else
                    [[0, 0, 0], [100, 0, 0], [0, 100, 0],
                     [50, 50, 20], [-50, 30, 10]], dtype=float)
    ph = rng.normal(size=n).cumsum() * 0.02
    m = len(base) + (0 if extra is None else len(extra))
    out = np.zeros((n, m, 3))
    ph2 = rng.normal(size=n).cumsum() * 0.05
    for f in range(n):
        c, s = np.cos(ph[f]), np.sin(ph[f])
        R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        t = np.array([f * 5.0, 900 + 20 * np.sin(ph[f]), 0.0])
        out[f, :len(base)] = (R @ base.T).T + t
        if extra is not None:
            c2, s2 = np.cos(ph2[f]), np.sin(ph2[f])
            R2 = np.array([[1, 0, 0], [0, c2, -s2], [0, s2, c2]])
            out[f, len(base):] = (R @ (R2 @ np.asarray(extra, float).T)).T + t
    return out


NAMES5 = ["RSACR", "LSACR", "USACR", "LASI", "RASI"]


class TestRigidFill(unittest.TestCase):
    def test_reconstructs_a_rigid_marker_exactly(self):
        truth = _rigid_body()
        d = truth.copy()
        d[100:190, 0] = np.nan                       # 90-frame hole
        out, rep = gf.fill_array(d, NAMES5)
        self.assertTrue(np.isfinite(out[100:190, 0]).all(),
                        "a marker with four rigid partners should be filled")
        err = np.linalg.norm(out[100:190, 0] - truth[100:190, 0], axis=1)
        # Exactly rigid input: the reconstruction is exact up to float noise.
        self.assertLess(err.max(), 1e-6, f"max error {err.max()} mm")
        self.assertEqual(rep.left_empty, 0)

    def test_reports_its_own_error(self):
        d = _rigid_body().copy()
        d[100:190, 0] = np.nan
        _, rep = gf.fill_array(d, NAMES5)
        mk = next(m for m in rep.markers if m.name == "RSACR")
        self.assertIsNotNone(mk.loo_rms, "a fill must come with an error bar")
        self.assertGreaterEqual(len(mk.donors), gf.MIN_DONORS)

    def test_present_samples_are_never_altered(self):
        d = _rigid_body().copy()
        d[100:190, 0] = np.nan
        d[250:256, 1] = np.nan
        out, _ = gf.fill_array(d, NAMES5)
        m = np.isfinite(d)
        self.assertTrue(np.allclose(out[m], d[m]),
                        "filling must not touch a sample that was measured")

    def test_idempotent(self):
        d = _rigid_body().copy()
        d[100:190, 0] = np.nan
        once, _ = gf.fill_array(d, NAMES5)
        twice, rep2 = gf.fill_array(once, NAMES5)
        self.assertTrue(np.allclose(once, twice, equal_nan=True))
        self.assertEqual(rep2.rigid_frames, 0)

    def test_edge_gap_is_filled_not_just_interior(self):
        # The marker only appears halfway through: nothing to interpolate
        # BETWEEN, but the segment's pose is known the whole time. This is the
        # case that matters on real data and the one the old filler skipped.
        truth = _rigid_body()
        d = truth.copy()
        d[:120, 0] = np.nan
        out, _ = gf.fill_array(d, NAMES5)
        self.assertTrue(np.isfinite(out[1:120, 0]).all())
        err = np.linalg.norm(out[1:120, 0] - truth[1:120, 0], axis=1)
        self.assertLess(err.max(), 1e-6)


class TestRefusal(unittest.TestCase):
    def test_a_loose_marker_is_left_empty(self):
        # Rigid with nothing — a random walk relative to the cluster. There is
        # no honest reconstruction, so there must be no reconstruction.
        rng = np.random.default_rng(7)
        body = _rigid_body(seed=7)
        n = body.shape[0]
        loose = body[:, 0] + rng.normal(size=(n, 3)).cumsum(0) * 3
        d = np.concatenate([body, loose[:, None, :]], axis=1)
        d[300:390, 5] = np.nan
        out, rep = gf.fill_array(d, NAMES5 + ["LOOSE"])
        self.assertFalse(np.isfinite(out[300:390, 5]).any(),
                         "a marker with no rigid partners must stay empty")
        mk = next(m for m in rep.markers if m.name == "LOOSE")
        self.assertEqual(mk.rigid_frames, 0)
        self.assertTrue(mk.note, "a refusal must say why")

    def test_too_few_partners(self):
        # Two markers total: a rigid transform needs three.
        d = _rigid_body()[:, :2].copy()
        d[100:190, 0] = np.nan
        out, rep = gf.fill_array(d, ["A", "B"])
        self.assertFalse(np.isfinite(out[100:190, 0]).any())
        self.assertGreater(rep.left_empty, 0)

    def test_whole_segment_missing_is_refused(self):
        # The failure mode on 022: the pelvis markers drop out TOGETHER, so
        # fewer than three remain and the segment is unobserved, not merely
        # under-determined. Nothing can be recovered and nothing should be.
        d = _rigid_body().copy()
        d[100:190, 0] = np.nan
        d[100:190, 1] = np.nan
        d[100:190, 2] = np.nan
        out, rep = gf.fill_array(d, NAMES5)
        self.assertFalse(np.isfinite(out[100:190, :3]).any(),
                         "with only two markers left the pose is unobserved")
        self.assertGreater(rep.left_empty, 0)


class TestShortGaps(unittest.TestCase):
    def test_short_gap_prefers_the_rigid_fill(self):
        # A short gap on a properly instrumented segment is reconstructed
        # exactly. Interpolating it instead would be merely close, and there is
        # no reason to accept "close" when "exact" is available.
        truth = _rigid_body()
        d = truth.copy()
        d[250:255, 1] = np.nan               # 5 frames, under MAX_SPLINE_GAP
        out, rep = gf.fill_array(d, NAMES5)
        mk = next(m for m in rep.markers if m.name == "LSACR")
        self.assertEqual(mk.spline_frames, 0, "rigid should have got there first")
        self.assertEqual(mk.rigid_frames, 5)
        err = np.linalg.norm(out[250:255, 1] - truth[250:255, 1], axis=1)
        self.assertLess(err.max(), 1e-6)

    def test_spline_is_the_fallback_when_there_is_no_cluster(self):
        # Two markers: no rigid transform is possible, so a SHORT interior gap
        # falls back to interpolating the trajectory itself.
        truth = _rigid_body()
        d = truth[:, :2].copy()
        d[250:255, 0] = np.nan
        out, rep = gf.fill_array(d, ["A", "B"])
        mk = next(m for m in rep.markers if m.name == "A")
        self.assertEqual(mk.spline_frames, 5)
        self.assertEqual(mk.left_empty, 0)
        err = np.linalg.norm(out[250:255, 0] - truth[250:255, 0], axis=1)
        self.assertLess(err.max(), 5.0)

    def test_long_gap_is_never_splined(self):
        # The rule that matters: no cluster and a LONG gap means empty, not a
        # straight line drawn through a swinging limb.
        d = _rigid_body()[:, :2].copy()
        d[100:190, 0] = np.nan
        out, rep = gf.fill_array(d, ["A", "B"])
        self.assertFalse(np.isfinite(out[100:190, 0]).any())
        mk = next(m for m in rep.markers if m.name == "A")
        self.assertEqual(mk.spline_frames, 0)
        self.assertEqual(mk.left_empty, 90)

    def test_no_gaps_is_a_no_op(self):
        d = _rigid_body()
        out, rep = gf.fill_array(d, NAMES5)
        self.assertTrue(np.array_equal(out, d))
        self.assertEqual(rep.spline_frames + rep.rigid_frames + rep.left_empty, 0)


class TestUsableWindow(unittest.TestCase):
    def test_finds_the_longest_clean_stretch(self):
        d = _rigid_body(n=400).copy()
        d[:50, 0] = np.nan                 # bad at the start
        d[:50, 1] = np.nan
        d[380:, 2] = np.nan                # and at the end
        d[380:, 3] = np.nan
        a, b, L, why = gf.usable_window(d, NAMES5, min_count=4)
        self.assertGreaterEqual(a, 50)
        self.assertLessEqual(b, 380)
        self.assertGreater(L, 300)
        self.assertIn("present", why)

    def test_all_present_gives_the_whole_trial(self):
        d = _rigid_body(n=200)
        a, b, L, _ = gf.usable_window(d, NAMES5)
        self.assertEqual((a, b, L), (0, 200, 200))


class TestTrcIo(unittest.TestCase):
    HEADER = (
        "PathFileType\t4\t(X/Y/Z)\ttest.trc\n"
        "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\t"
        "OrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n"
        "200\t200\t3\t2\tmm\t200\t1\t3\n"
        "Frame#\tTime\tA\t\t\tB\t\t\n"
        "\t\tX1\tY1\tZ1\tX2\tY2\tZ2\n"
    )
    BODY = ("1\t0.000\t1.00000\t2.00000\t3.00000\t4.00000\t5.00000\t6.00000\n"
            "2\t0.005\t\t\t\t4.10000\t5.10000\t6.10000\n"
            "3\t0.010\t1.20000\t2.20000\t3.20000\t4.20000\t5.20000\t6.20000\n")

    def _write(self, d):
        import os
        p = os.path.join(d, "t.trc")
        with open(p, "w", newline="") as fh:
            fh.write(self.HEADER + self.BODY)
        return p

    def test_roundtrip_preserves_header_and_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d)
            hdr, fr, tm, data, names = gf.read_trc(p)
            self.assertEqual(names, ["A", "B"])
            self.assertEqual(data.shape, (3, 2, 3))
            self.assertTrue(np.isnan(data[1, 0]).all(), "blank cells are NaN")
            out = p + ".out"
            gf.write_trc(out, hdr, fr, tm, data)
            with open(out) as fh:
                txt = fh.read()
            self.assertTrue(txt.startswith(self.HEADER),
                            "the .trc header must survive byte-for-byte")
            # a missing marker stays an EMPTY cell, never a number
            self.assertIn("2\t0.00500\t\t\t\t", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
