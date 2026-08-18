"""bioscout.tests.test_plot — the plotting layer, without OpenSim or scipy.

Everything here runs on numpy + pandas + matplotlib alone, which is the point:
``bioscout.plot`` is the part of the package a collaborator should be able to
use on a bare checkout with nothing but the results table.
"""
import os
import shutil
import tempfile
import unittest

try:
    import matplotlib
    matplotlib.use("Agg")
    import numpy as np
    import pandas as pd
    from bioscout import plot
    HAVE = True
except Exception as exc:                                       # noqa: BLE001
    HAVE = False
    WHY = str(exc)


@unittest.skipUnless(HAVE, "numpy/pandas/matplotlib not available")
class TestTidy(unittest.TestCase):
    def table(self):
        return pd.DataFrame([
            {"Task": "run", "Condition": "pre",  "Trial": "r1",
             "Channel": "vasmed_r", "Value": 6.0},
            {"Task": "run", "Condition": "pre",  "Trial": "r1",
             "Channel": "vaslat_r", "Value": 4.0},
            {"Task": "run", "Condition": "pre",  "Trial": "r1",
             "Channel": "soleus_r", "Value": 7.0},
            {"Task": "run", "Condition": "post", "Trial": "r2",
             "Channel": "vasmed_r", "Value": 2.0},
            {"Task": "run", "Condition": "post", "Trial": "r2",
             "Channel": "soleus_r", "Value": 9.0},
        ])

    def test_read_passthrough_and_filter(self):
        d = plot.read(self.table(), Condition="pre")
        self.assertEqual(len(d), 3)

    def test_select_unknown_column_raises(self):
        # a filter that silently does nothing is a figure that quietly plots
        # the wrong rows — it must be loud
        with self.assertRaises(KeyError):
            plot.select(self.table(), Nonsuch="x")

    def test_select_list_and_callable(self):
        t = self.table()
        self.assertEqual(len(plot.select(t, Condition=["pre", "post"])), 5)
        self.assertEqual(
            len(plot.select(t, Channel=lambda c: c.startswith("vas"))), 3)

    def test_from_mapping_depths(self):
        one = plot.from_mapping({"Vasti": 3.0, "Hamstrings": 1.0})
        self.assertEqual(sorted(one.columns), ["Channel", "Value"])
        two = plot.from_mapping({"pre": {"Vasti": 3.0}, "post": {"Vasti": 2.0}},
                                levels=["Condition"])
        self.assertIn("Condition", two.columns)
        self.assertEqual(len(two), 2)
        three = plot.from_mapping(
            {"run": {"pre": {"Vasti": 3.0}, "post": {"Vasti": 2.0}}})
        self.assertEqual(sorted(set(three["Task"])), ["run"])

    def test_group_channels_sums_compartments(self):
        g = plot.group_channels(self.table(), plot.MUSCLE_GROUPS)
        pre = g[(g["Condition"] == "pre") & (g["Channel"] == "Vasti")]
        self.assertAlmostEqual(float(pre["Value"].iloc[0]), 10.0)
        self.assertNotIn("vasmed_r", set(g["Channel"]))

    def test_cells_shape_and_order(self):
        g = plot.group_channels(self.table(), plot.MUSCLE_GROUPS)
        c = plot.cells(g, "Condition", facet="Task",
                       compare_order=["pre", "post"])
        self.assertEqual(list(c), ["run"])
        labels = [lab for lab, _ in c["run"]]
        self.assertEqual(labels, ["pre", "post"])
        # ranking is by value, descending
        pre = c["run"][0][1]
        self.assertEqual(max(pre, key=pre.get), "Vasti")

    def test_counts(self):
        n = plot.counts(self.table(), "Condition", "Task", over="Trial")
        self.assertEqual(n[("run", "pre")], 1)


@unittest.skipUnless(HAVE, "numpy/pandas/matplotlib not available")
class TestWork(unittest.TestCase):
    """The integral, checked against a case with an exact answer."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bs_plot_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _sto(self, name, cols, rows):
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("%s\nversion=1\nnRows=%d\nnColumns=%d\nendheader\n"
                     % (name, len(rows), len(cols)))
            fh.write("\t".join(cols) + "\n")
            for r in rows:
                fh.write("\t".join("%.10f" % v for v in r) + "\n")
        return p

    def test_constant_force_constant_velocity(self):
        # F = 10 N held constant while the muscle shortens at 0.5 m/s for 2 s
        #   -> |F.v| dt = 10 * 0.5 * 2 = 10 J, exactly.
        t = np.linspace(0.0, 2.0, 201)
        force = self._sto("f.sto", ["time", "soleus_r"],
                          [[ti, 10.0] for ti in t])
        length = self._sto("l.sto", ["time", "soleus_r"],
                           [[ti, 1.0 - 0.5 * ti] for ti in t])
        w = plot.muscle_work(force, length, side="_r", phase="total")
        self.assertAlmostEqual(w["Triceps surae"], 10.0, places=6)
        # shortening throughout, so total == concentric and eccentric is zero
        self.assertAlmostEqual(
            plot.muscle_work(force, length, phase="concentric")["Triceps surae"],
            10.0, places=6)
        self.assertAlmostEqual(
            plot.muscle_work(force, length, phase="eccentric")
            .get("Triceps surae", 0.0), 0.0, places=6)

    def test_total_is_not_net(self):
        # shorten then lengthen by the same amount under the same force:
        # net work is zero, total work is not. Ranking on the wrong one is the
        # easiest mistake this module can make, so it is pinned here.
        t = np.linspace(0.0, 2.0, 401)
        L = np.where(t <= 1.0, 1.0 - 0.5 * t, 0.5 + 0.5 * (t - 1.0))
        force = self._sto("f2.sto", ["time", "soleus_r"],
                          [[ti, 10.0] for ti in t])
        length = self._sto("l2.sto", ["time", "soleus_r"],
                           [[ti, li] for ti, li in zip(t, L)])
        total = plot.muscle_work(force, length, phase="total")["Triceps surae"]
        net = plot.muscle_work(force, length, phase="net")["Triceps surae"]
        # `delta`, not `places`: np.gradient smooths the single sample at the
        # velocity reversal, which costs the total ~0.25 % on this waveform.
        # That is the derivative doing its job, not an error to chase.
        self.assertAlmostEqual(total, 10.0, delta=0.05)
        self.assertAlmostEqual(net, 0.0, delta=0.05)

    def test_side_filter_and_missing_files(self):
        t = np.linspace(0.0, 1.0, 11)
        force = self._sto("f3.sto", ["time", "soleus_r", "soleus_l"],
                          [[ti, 10.0, 10.0] for ti in t])
        length = self._sto("l3.sto", ["time", "soleus_r", "soleus_l"],
                           [[ti, 1.0 - 0.5 * ti, 1.0 - 0.5 * ti] for ti in t])
        self.assertEqual(list(plot.muscle_work(force, length, side="_l")),
                         ["Triceps surae"])
        self.assertEqual(plot.muscle_work("/no/such.sto", length), {})

    def test_work_table_carries_every_key(self):
        t = np.linspace(0.0, 1.0, 11)
        force = self._sto("f4.sto", ["time", "soleus_r"],
                          [[ti, 10.0] for ti in t])
        length = self._sto("l4.sto", ["time", "soleus_r"],
                           [[ti, 1.0 - 0.5 * ti] for ti in t])
        df = plot.work_table([{"Task": "run", "Condition": "pre",
                               "Trial": "r1", "force": force,
                               "length": length}])
        for col in ("Task", "Condition", "Trial", "Side", "Variable",
                    "Channel", "Metric", "Value"):
            self.assertIn(col, df.columns)
        self.assertEqual(set(df["Variable"]), {"muscle_work_total"})

    def test_group_of(self):
        self.assertEqual(plot.group_of("vasmed_r"), "Vasti")
        self.assertEqual(plot.group_of("vasmed"), "Vasti")
        self.assertIsNone(plot.group_of("time"))
        self.assertIsNone(plot.group_of("pelvis_tilt"))


@unittest.skipUnless(HAVE, "numpy/pandas/matplotlib not available")
class TestCompare(unittest.TestCase):
    def test_demo_draws(self):
        import matplotlib.pyplot as plt
        p = plot.demo()
        fig = p.draw()
        # 3 facets x 2 compared levels
        self.assertEqual(len(fig.axes), 6)
        plt.close(fig)

    def test_builder_is_immutable(self):
        base = plot.demo()
        other = base.top(4)
        self.assertEqual(base._cfg().top, 8)
        self.assertEqual(other._cfg().top, 4)

    def test_callable_module(self):
        self.assertIsInstance(plot(plot.demo()._data), plot.Compare)

    def test_missing_compare_raises(self):
        with self.assertRaises(ValueError):
            plot.compare(plot.demo()._data).draw()

    def test_unknown_setting_raises(self):
        with self.assertRaises(TypeError):
            plot.demo().set(dpu=600)

    def test_styles_and_normalisations_all_draw(self):
        import matplotlib.pyplot as plt
        for style in ("delta", "connector", "both"):
            for norm in ("reference", "panel"):
                p = plot.demo().style(style).normalise(norm)
                plt.close(p.draw())

    def test_save_writes_a_file(self):
        import matplotlib.pyplot as plt
        d = tempfile.mkdtemp(prefix="bs_plot_")
        try:
            out = plot.demo().save(os.path.join(d, "sub", "fig.png"))
            self.assertTrue(os.path.isfile(out))
        finally:
            plt.close("all")
            shutil.rmtree(d, ignore_errors=True)

    def test_curves_draw(self):
        import matplotlib.pyplot as plt
        x = np.arange(0, 101)
        rows = []
        for cond, k in (("pre", 1.0), ("post", 0.8)):
            for tr in range(3):
                for ch in ("Vasti", "Hamstrings"):
                    rows += [{"Condition": cond, "Trial": "%s%d" % (cond, tr),
                              "Channel": ch, "Percent": float(a),
                              "Value": k * float(np.sin(np.pi * a / 100))}
                             for a in x]
        p = plot.compare(pd.DataFrame(rows)).compare("Condition").curves()
        fig = p.draw()
        self.assertEqual(len(fig.axes), 2)
        plt.close(fig)

    def test_config_scope(self):
        self.assertEqual(plot.settings().top, 8)
        with plot.using(top=3):
            self.assertEqual(plot.settings().top, 3)
        self.assertEqual(plot.settings().top, 8)


def suite():
    loader = unittest.TestLoader()
    s = unittest.TestSuite()
    for cls in (TestTidy, TestWork, TestCompare):
        s.addTests(loader.loadTestsFromTestCase(cls))
    return s


if __name__ == "__main__":
    unittest.main(verbosity=2)
