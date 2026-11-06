"""bioscout.results — loading, actions, plotting and export on a fake session
tree. numpy + pandas + matplotlib only; nothing outside a temp folder is written."""
import os
import shutil
import tempfile
import unittest

try:
    import matplotlib
    matplotlib.use("Agg")
    import numpy as np
    import pandas as pd
    from bioscout import results as R
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False


def _sto(p, cols, seed=0, t1=1.2, n=121):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rng = np.random.default_rng(seed)
    t = np.linspace(0, t1, n)
    with open(p, "w") as f:
        f.write(f"x\nversion=1\nnRows={n}\nnColumns={len(cols) + 1}\nendheader\n")
        f.write("time\t" + "\t".join(cols) + "\n")
        for ti in t:
            f.write(f"{ti:.4f}\t" + "\t".join(
                f"{np.sin(ti * (k + 1)) * 100 + rng.normal():.5f}" for k in range(len(cols))) + "\n")


def build(root):
    s = os.path.join(root, "simulations", "K2L", "11_03_24")
    os.makedirs(os.path.join(s, "movement_detection"))
    with open(os.path.join(s, "session.yaml"), "w") as f:
        f.write("body_mass: 70\ntrials:\n  Gehen_01: {type: walking}\n  Gehen_02: {type: walking}\n"
                "iterations:\n  gpkv4: {color: '#1f77b4', label: GPK}\n")
    with open(os.path.join(s, "movement_detection", "cycles.csv"), "w") as f:
        f.write("trial,cycle,side,task,t_start,t_end,stance_start,stance_end\n"
                "Gehen_01,c1,r,walking,0.1,1.1,0.1,0.7\n"
                "Gehen_02,c1,r,walking,0.05,1.0,0.05,0.6\n")
    for tr in ("Gehen_01", "Gehen_02"):
        _sto(os.path.join(s, "2_experimental", tr, "grf.mot"), ["ground_force_vy"], 1)
        for j, it in enumerate(("gpkv4", "gpkv4_pyosim")):
            d = os.path.join(s, "3_iterations", it, tr)
            _sto(os.path.join(d, "external_biomechanics", "joint_angles.mot"),
                 ["hip_flexion_r", "knee_angle_r"], 3 + j)
            _sto(os.path.join(d, "external_biomechanics", "setup_IK.sto"), ["x"])
            _sto(os.path.join(d, "static_optimisation", "StaticOptimization_force.sto"),
                 ["vasmed_r", "soleus_r", "vasmed_l"], 6 + j)
            _sto(os.path.join(d, "joint_contact_forces", "output_so.sto"),
                 ["hip_r_on_pelvis_in_pelvis_fy"], 8)
            for dof in ("knee_angle_r", "hip_flexion_r"):
                _sto(os.path.join(d, "muscle_analysis", f"x_MuscleAnalysis_MomentArm_{dof}.sto"),
                     ["vasmed_r"], 9)
            for k, ex in enumerate(("Execution_1", "Execution_2")):
                _sto(os.path.join(d, "ceinms", ex, "MuscleForces.sto"), ["vasmed_r"], 20 + 5 * k)
    return s


@unittest.skipUnless(HAVE, "numpy/pandas/matplotlib not available")
class TestResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.sess = build(cls.tmp)
        cls.res = R.for_session(cls.sess)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_available_reads_nothing_and_skips_setups(self):
        a = self.res()
        self.assertIn("muscle_forces_so", a.columns)
        self.assertNotIn("external_biomechanics_setup_ik", a.columns)
        self.assertEqual(a.loc[("gpkv4", "Gehen_01"), "joint_angles"], 1)

    def test_one_file_one_trial(self):
        f = self.res("so_forces", trial="Gehen_01", iteration="gpkv4", var=["vasmed_r"])
        self.assertIsInstance(f, R.ResultSet)
        self.assertEqual(f.variable, "muscle_forces_so")
        self.assertEqual(f.vars, ["vasmed_r"])
        self.assertEqual(f.x, "time")
        self.assertEqual(len(f), 1)
        self.assertEqual(len(f.df), 121)

    def test_many_trials_iterations_glob_vars(self):
        f = self.res("so_forces", trial="Gehen*", var="*_r")
        self.assertEqual(sorted(f.vars), ["soleus_r", "vasmed_r"])
        self.assertEqual(len(f), 4)
        self.assertEqual(f["vasmed_r"].shape[1], 4)        # curves table
        self.assertEqual(len(f.where(iteration="gpkv4")), 2)

    def test_cycle_window_normalises(self):
        f = self.res("ik", window="cycle")
        self.assertEqual(f.x, "pct")
        self.assertEqual(f.df.groupby(["iteration", "trial"]).size().unique().tolist(), [101])
        self.assertEqual(set(f.ids.cycle), {"c1"})
        m = f.mean("iteration")
        self.assertEqual(len(m), 2)

    def test_several_files_and_groups(self):
        r = self.res(["ik", "jcf_so"], trial="Gehen_01")
        self.assertIsInstance(r, R.ResultSets)
        self.assertEqual(set(r), {"joint_angles", "joint_contact_forces_so"})
        ma = self.res("moment_arms")
        self.assertEqual(set(ma), {"moment_arms/knee_angle_r", "moment_arms/hip_flexion_r"})
        self.assertIsInstance(self.res("moment_arms/knee_angle_r"), R.ResultSet)

    def test_experimental_kept_when_iteration_fixed(self):
        it = R.for_session(self.sess, iteration="gpkv4")
        g = it("grf")
        self.assertEqual(set(g.ids.iteration), {""})
        self.assertEqual(set(it("ik").ids.iteration), {"gpkv4"})

    def test_newest_ceinms_execution_only(self):
        f = self.res("ceinms_forces", iteration="gpkv4", trial="Gehen_01")
        self.assertEqual(len(f), 1)

    def test_to_bw_peak_at(self):
        f = self.res("jcf_so", iteration="gpkv4", trial="Gehen_01")
        bw = f.to_bw()
        self.assertAlmostEqual(bw.df.iloc[5, -1] * 70 * 9.81, f.df.iloc[5, -1], 6)
        self.assertEqual(bw.unit, "N/BW")
        self.assertEqual(f.peak().shape, (1, 1))
        self.assertEqual(f.at(0.5).shape, (1, 1))

    def test_plot_returns_figure_and_writes_nothing(self):
        before = set(os.listdir(self.tmp))
        fig = self.res("ik", window="cycle").plot(var="*_r")
        self.assertEqual(len(fig.axes), 2)
        self.assertEqual(set(os.listdir(self.tmp)), before)
        import matplotlib.pyplot as plt
        plt.close(fig.fig)

    def test_custom_action_and_file_kind(self):
        @R.action
        def doubled(rs):
            df = rs.df.copy()
            df[rs.vars] *= 2
            return rs._new(df)
        f = self.res("ik", iteration="gpkv4", trial="Gehen_01")
        self.assertAlmostEqual(f.doubled().df.iloc[3, -1], 2 * f.df.iloc[3, -1])
        self.assertIsInstance(self.res(["ik"]).doubled(), R.ResultSets)
        del R.ACTIONS["doubled"]

    def test_unknown_file_lists_what_exists(self):
        with self.assertRaises(LookupError) as cm:
            self.res("nope")
        self.assertIn("joint_angles", str(cm.exception))

    def test_load_from_project_and_export(self):
        f = R.load(self.tmp, "ik", subject="K2L", trial="Gehen_01")
        self.assertEqual(len(f), 2)
        out = R.export_results(self.tmp, os.path.join(self.tmp, "out"), variables="ik",
                               verbose=False)
        df = pd.read_csv(os.path.join(out, "joint_angles", "knee_angle_r.csv"))
        self.assertEqual(len(df), 4)
        self.assertIn("pct_100", df.columns)


if __name__ == "__main__":
    unittest.main()
