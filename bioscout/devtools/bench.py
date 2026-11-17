"""Overnight pipeline benchmark: where does the time go, and what scales?

    python -m bioscout.devtools.bench --smoke      # ~2 min: does every stage run?
    python -m bioscout.devtools.bench              # the overnight run (8 h budget)

Runs on COPIES of example_data/orthoload (Walking_01, iteration gpk), so your
example data is never touched. Four tests, in this order, each with a share of
the time budget (time a test does not use passes on to the next):

  stages    each stage timed on its own, --reps times (scale, IK, ID, MA, SO,
            muscle moments, JRA, mew, JCF contributions)          -> which stage is slow
  profile   one chain under cProfile; time split into OpenSim / bioscout /
            matplotlib / pandas / numpy / file I/O per stage       -> why it is slow
  soak      the IK..mew chain repeated in ONE process; memory, handles,
            open figures and time per round                         -> leaks / slow-down
  parallel  N copies of the trial run with 1, 2, 4 ... processes, plus the
            JCF-contributions n_jobs sweep                          -> does parallel pay

Everything lands in example_data/_bench/<date_time>/ (gitignored):
  STATUS.md        rewritten after every unit -- open it to see where the run is
  SUMMARY.md       the morning read (rewritten after every test, so a crash
                   still leaves the part that finished)
  stage_times.csv  one row per timed stage, every test
  parallel.csv     one row per worker count
  profile/         <stage>.prof (snakeviz-able) + <stage>_top.txt
  run.log          everything the pipeline printed

Ctrl+C stops cleanly and still writes SUMMARY.md.
"""
from __future__ import annotations

import argparse
import contextlib
import cProfile
import csv
import datetime as _dt
import glob
import io
import json
import math
import os
import platform
import pstats
import random
import shutil
import statistics
import sys
import time
import traceback
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")      # no windows popping up at 3 am
os.environ.setdefault("BIOSCOUT_OPEN_LOG", "0")  # every Session() would open its log in VS Code

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = REPO / "example_data" / "orthoload"
DEFAULT_SESSION = "H1_orthoload/11_05_06"

# stage -> output (glob, relative to the trial folder) that must be NEWER than
# the stage start, or the stage "ran" without producing anything.
OUTPUTS = {
    "ik":      "external_biomechanics/joint_angles.mot",
    "id":      "external_biomechanics/inverse_dynamics.sto",
    "ma":      "muscle_analysis/_MuscleAnalysis_Length.sto",
    "so":      "static_optimisation/*force.sto",
    "mm":      "muscle_analysis/_MuscleMoments_*_so.sto",
    "jra":     "joint_contact_forces/output_so.sto",
    "mew":     "mew/JRA_ReactionLoads.sto",
    "contrib": "joint_contact_forces/contributions_so.sto",
}
LABEL = {"scale": "Scale", "ik": "IK", "id": "ID", "ma": "Muscle analysis",
         "so": "Static optimisation", "mm": "Muscle moments", "jra": "JRA",
         "mew": "mew", "contrib": "JCF contributions"}
CHAIN = ["ik", "id", "ma", "so", "mm", "jra", "mew"]          # soak + parallel
STAGES_TEST = ["scale"] + CHAIN + ["contrib"]                  # stages + profile
WEIGHTS = {"stages": 0.20, "profile": 0.10, "soak": 0.30, "parallel": 0.40}

CSV_FIELDS = ["test", "round", "workers", "job", "stage", "wall_s", "cpu_s",
              "open_s", "rss_mb", "handles", "threads", "figs", "status",
              "error", "started"]


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _now():
    return _dt.datetime.now()                  # local time (the PC's zone)


def _hms(s):
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return "-"
    s = int(round(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _proc_stats():
    """rss MB, handles (Windows) / fds, threads, open pyplot figures."""
    rss = handles = threads = figs = None
    try:
        import psutil
        p = psutil.Process()
        rss = p.memory_info().rss / 2**20
        threads = p.num_threads()
        handles = p.num_handles() if os.name == "nt" else p.num_fds()
    except Exception:
        pass
    try:
        if "matplotlib.pyplot" in sys.modules:
            figs = len(sys.modules["matplotlib.pyplot"].get_fignums())
    except Exception:
        pass
    return rss, handles, threads, figs


def _git_head():
    try:
        head = (REPO / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1]
            f = REPO / ".git" / ref
            sha = f.read_text().strip() if f.exists() else "?"
            return f"{ref.rsplit('/', 1)[-1]} {sha[:7]}"
        return head[:7]
    except Exception:
        return "?"


_PKG = str(REPO / "bioscout")


def _polluted(entry):
    """sys.path entries INSIDE the bioscout package. bioscout.utils and
    simulate/ceinms/shared.py insert bioscout/, bioscout/utils,
    bioscout/simulate and bioscout/simulate/ceinms so their old bare
    `import utils` / `import openSim` lines resolve. Harmless in the process
    that did it (the real opensim is already imported), but a spawned child
    inherits that sys.path, and its first `import opensim` then finds
    bioscout/simulate/opensim.py instead of the OpenSim package:
    "module 'opensim' has no attribute 'Model'"."""
    try:
        e = os.path.normcase(os.path.abspath(entry or "."))
    except Exception:
        return False
    return e.startswith(os.path.normcase(_PKG))


@contextlib.contextmanager
def _clean_path():
    """Hide the package-internal sys.path entries while child processes are
    spawned (they copy sys.path at start), then put them back."""
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if not _polluted(p)]
    try:
        yield
    finally:
        sys.path[:] = saved


def _copy_project(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "logs", "_bench", ".vscode", "__pycache__"))
    return dst


# --------------------------------------------------------------------------
# running one stage (used in-process AND inside worker processes)
# --------------------------------------------------------------------------
class Runner:
    """Opens the session once; runs one stage at a time on one trial."""

    def __init__(self, project, session, iteration, trial, log_path, fake=False):
        self.project, self.session, self.iteration = str(project), session, iteration
        self.trial_name, self.log_path, self.fake = trial, log_path, fake
        self.trial_dir = os.path.join(self.project, "simulations", *session.split("/"),
                                      "3_iterations", iteration, trial)
        self._it = None
        self._leak = []                                  # fake mode only

    # -- the real thing ---------------------------------------------------
    def it(self):
        if self._it is None:
            import bioscout as bs
            sess = bs.Session(os.path.join(self.project, "simulations",
                                           *self.session.split("/")))
            self._it = sess.iteration(self.iteration)
            try:
                from bioscout.model.opensim_base import _quiet_osim
                _quiet_osim()
            except Exception:
                pass
        return self._it

    def _stage_real(self, stage, n_jobs=None):
        it = self.it()
        if stage == "scale":
            it.scale_model(replace=True)
            return 0.0
        if stage == "mew":
            it.run(trials=[self.trial_name], do_mew=True, replace=True, log=print)
            return 0.0
        t0 = time.perf_counter()
        t = it.trial(self.trial_name)
        open_s = time.perf_counter() - t0
        if stage == "ik":
            t.run_ik(replace=True)
        elif stage == "id":
            t.run_id(replace=True)
        elif stage == "ma":
            t.run_ma(replace=True)
        elif stage == "so":
            t.run_so(replace=True)
        elif stage == "mm":
            t.calculate_muscle_moments(forces_type="so")
        elif stage == "jra":
            t.run_jra(replace=True)
        elif stage == "contrib":
            # The JRA template comes from settings.SETUP_DIR, which for a project
            # without its own settings.py is bioscout/setupFiles -- a folder that
            # does not exist -- and decompose() then skips the copy silently and
            # every JointReaction fails on a missing setup_JRA_contrib.xml.
            if not os.path.exists(os.path.join(str(t.setup_dir or ""), "setup_JRA.xml")):
                for cand in (os.path.join(self.project, "setupFiles"),
                             os.path.join(_PKG, "setup_files")):
                    if os.path.exists(os.path.join(cand, "setup_JRA.xml")):
                        print(f"[bench] setup_dir {t.setup_dir!r} has no setup_JRA.xml "
                              f"-> using {cand}")
                        t._session_setup_dir = cand
                        t.setup_dir = cand
                        if isinstance(getattr(t, "_overrides", None), dict):
                            t._overrides["setup_dir"] = cand   # load_settings re-applies these LAST
                        break
            with _clean_path():          # its process pool would import the wrong opensim
                t.run_jra_contributions(forces_type="so", replace=True, n_jobs=n_jobs)
        else:
            raise ValueError(f"unknown stage {stage}")
        return open_s

    # -- self-test without OpenSim ---------------------------------------
    def _stage_fake(self, stage, n_jobs=None):
        base = {"scale": .3, "ik": .4, "id": .2, "ma": .6, "so": .8, "mm": .1,
                "jra": .3, "mew": .5, "contrib": .4}[stage]
        end = time.perf_counter() + base * random.uniform(.9, 1.1)
        x = 0
        while time.perf_counter() < end:                 # burn CPU, not sleep
            x += 1
        self._leak.append(bytearray(2 * 2**20))          # 2 MB "leak" per stage
        if stage in os.environ.get("BENCH_FAKE_FAIL", "").split(","):
            raise RuntimeError(f"fake failure in {stage}")
        print(f"[fake] {stage} done")
        if stage == "scale":
            return 0.0
        out = os.path.join(self.trial_dir, OUTPUTS[stage].replace("*", "x"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        Path(out).write_text("fake")
        return 0.01

    def _check_output(self, stage, t_start):
        if stage == "scale":
            if self.fake:
                return True
            p = getattr(self.it(), "model_scaled", None)
            return bool(p) and os.path.exists(p) and os.path.getmtime(p) >= t_start - 2
        hits = glob.glob(os.path.join(self.trial_dir, OUTPUTS[stage]))
        return any(os.path.getmtime(h) >= t_start - 2 for h in hits)

    def run(self, stage, n_jobs=None, profiler=None):
        """-> dict row (wall/cpu/open/status/error + process stats)."""
        cwd0 = os.getcwd()
        started = _now().isoformat(timespec="seconds")
        t_wall0, t_cpu0, t_epoch = time.perf_counter(), time.process_time(), time.time()
        status, err, open_s = "ok", "", None
        with open(self.log_path, "a", encoding="utf-8", errors="replace") as lf:
            lf.write(f"\n===== {started} {stage} ({self.project}) =====\n")
            lf.flush()
            fd_saved = None
            try:
                try:                                  # C++ std::cout -> run.log too
                    sys.stdout.flush()
                    fd_saved = os.dup(1)
                    os.dup2(lf.fileno(), 1)
                except Exception:
                    fd_saved = None
                with contextlib.redirect_stdout(lf), contextlib.redirect_stderr(lf):
                    if profiler is not None:
                        profiler.enable()
                    try:
                        fn = self._stage_fake if self.fake else self._stage_real
                        open_s = fn(stage, n_jobs=n_jobs)
                    finally:
                        if profiler is not None:
                            profiler.disable()
                        try:
                            import matplotlib.pyplot as plt   # same as Iteration.run
                            plt.close("all")
                        except Exception:
                            pass
                if not self._check_output(stage, t_epoch):
                    status = "no_output"
            except KeyboardInterrupt:
                raise
            except BaseException as e:                      # noqa: BLE001
                status, err = "error", f"{type(e).__name__}: {e}"[:300]
                lf.write(traceback.format_exc())
            finally:
                os.chdir(cwd0)
                if fd_saved is not None:
                    try:
                        lf.flush()
                        os.dup2(fd_saved, 1)
                        os.close(fd_saved)
                    except Exception:
                        pass
        rss, handles, threads, figs = _proc_stats()
        return dict(stage=stage, wall_s=round(time.perf_counter() - t_wall0, 3),
                    cpu_s=round(time.process_time() - t_cpu0, 3),
                    open_s=None if open_s is None else round(open_s, 3),
                    rss_mb=None if rss is None else round(rss, 1),
                    handles=handles, threads=threads, figs=figs,
                    status=status, error=err, started=started)


def _chain_job(project, session, iteration, trial, stages, log_path, fake):
    """Worker-process entry: run the chain once on one project copy."""
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.stdin = io.StringIO()            # an input() prompt fails instead of hanging
    sys.path[:] = [p for p in sys.path if not _polluted(p)]
    if not fake:
        try:
            import opensim               # the real one, before bioscout touches sys.path
        except Exception:
            pass
    r = Runner(project, session, iteration, trial, log_path, fake=fake)
    t0 = time.perf_counter()
    rows = [r.run(st) for st in stages]
    return {"project": project, "pid": os.getpid(), "rows": rows,
            "wall_s": time.perf_counter() - t0,
            "ok": all(x["status"] == "ok" for x in rows)}


# --------------------------------------------------------------------------
# the bench
# --------------------------------------------------------------------------
class Bench:
    def __init__(self, a):
        self.a = a
        self.fake = a.fake
        self.t_start = time.time()
        self.t_end = self.t_start + a.hours * 3600
        self.out = Path(a.out) if a.out else (
            REPO / "example_data" / "_bench" / _now().strftime("%Y%m%d_%H%M%S"))
        self.out.mkdir(parents=True, exist_ok=True)
        self.copies = self.out / "copies"
        self.log = str(self.out / "run.log")
        os.environ["BIOSCOUT_LOG_DIR"] = str(self.out / "logs")   # keep project logs out
        (self.out / "logs").mkdir(exist_ok=True)
        self.csv_path = self.out / "stage_times.csv"
        self.par_path = self.out / "parallel.csv"
        self.events, self.current = [], "starting"
        self.n_ok = self.n_bad = 0
        self.unit_started = time.time()
        sys.stdin = io.StringIO()            # an input() prompt fails instead of hanging
        threading.Thread(target=self._heartbeat, daemon=True).start()
        self.results = {}                     # per-test summary bits
        self.rows = []
        self.cores_phys, self.cores_log = self._cores()
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                csv.writer(f).writerow(CSV_FIELDS)

    # -- bookkeeping -------------------------------------------------------
    @staticmethod
    def _cores():
        try:
            import psutil
            return psutil.cpu_count(logical=False) or 1, psutil.cpu_count() or 1
        except Exception:
            n = os.cpu_count() or 1
            return n, n

    def _heartbeat(self):
        """Rewrite STATUS.md every minute, so a stage that hangs is visible
        (\"running for 2:14:00\") even though nothing else is being logged."""
        while True:
            time.sleep(60)
            self.write_status()

    def event(self, msg):
        line = f"{_now():%H:%M:%S}  {msg}"
        print(line, flush=True)
        self.events.append(line)
        self.events = self.events[-25:]
        self.write_status()

    def record(self, test, row, round_=None, workers=None, job=None):
        row = dict(row, test=test, round=round_, workers=workers, job=job)
        self.rows.append(row)
        self.unit_started = time.time()
        if row["status"] == "ok":
            self.n_ok += 1
        else:
            self.n_bad += 1
        with open(self.csv_path, "a", newline="") as f:
            csv.DictWriter(f, CSV_FIELDS, extrasaction="ignore").writerow(row)
        extra = f"  [{row['status']}] {row['error']}" if row["status"] != "ok" else ""
        self.event(f"{test:8s} r{round_ if round_ is not None else '-'} "
                   f"{LABEL.get(row['stage'], row['stage']):20s} {row['wall_s']:8.1f} s"
                   f"  rss {row['rss_mb']} MB{extra}")

    def write_status(self):
        el = time.time() - self.t_start
        txt = [f"# bench status  (updated {_now():%Y-%m-%d %H:%M:%S})", "",
               f"- now running: **{self.current}** (for {_hms(time.time() - self.unit_started)})",
               f"- elapsed {_hms(el)} of {_hms(self.a.hours * 3600)} budget "
               f"(ends by {_dt.datetime.fromtimestamp(self.t_end):%H:%M})",
               f"- stages ok {self.n_ok}, failed {self.n_bad}",
               f"- output: {self.out}", "", "## last events", "", "```",
               *self.events, "```", ""]
        try:
            (self.out / "STATUS.md").write_text("\n".join(txt), encoding="utf-8")
        except OSError:
            pass

    def time_left(self):
        return self.t_end - time.time()

    def copy(self, name):
        proj = _copy_project(self.a.project, self.copies / name)
        if self.a.window and not self.fake:
            _shorten_window(proj, self.a.session, self.a.trial, self.a.window)
        return proj

    def runner(self, name):
        proj = self.copy(name)
        return Runner(proj, self.a.session, self.a.iteration, self.a.trial,
                      self.log, fake=self.fake)

    # -- tests -------------------------------------------------------------
    def test_stages(self, deadline):
        """Each stage on its own, --reps rounds. Scale runs on its own copy
        (rescaling rewrites model_scaled, which every other stage reads)."""
        r = self.runner("stages")
        rs = self.runner("scale")
        for rnd in range(1, self.a.reps + 1):
            for st in STAGES_TEST:
                if time.time() > deadline:
                    self.event(f"stages: budget used during round {rnd}")
                    return
                self.current = f"stages round {rnd}/{self.a.reps}: {LABEL[st]}"
                self.record("stages", (rs if st == "scale" else r).run(st), rnd)

    def test_profile(self, deadline):
        r = self.runner("profile")
        pdir = self.out / "profile"
        pdir.mkdir(exist_ok=True)
        buckets = {}
        for st in STAGES_TEST:
            if time.time() > deadline:
                self.event("profile: budget used")
                break
            self.current = f"profile: {LABEL[st]}"
            prof = cProfile.Profile()
            row = (self.runner("profile_scale") if st == "scale" else r).run(st, profiler=prof)
            self.record("profile", row, 1)
            prof.dump_stats(str(pdir / f"{st}.prof"))
            s = io.StringIO()
            ps = pstats.Stats(prof, stream=s)
            ps.sort_stats("cumulative").print_stats(40)
            ps.sort_stats("tottime").print_stats(40)
            (pdir / f"{st}_top.txt").write_text(s.getvalue(), encoding="utf-8")
            buckets[st] = _bucket(ps)
        self.results["profile"] = buckets
        json.dump(buckets, open(pdir / "buckets.json", "w"), indent=1)

    def test_soak(self, deadline):
        r = self.runner("soak")
        for rnd in range(1, self.a.soak + 1):
            if time.time() > deadline:
                self.event(f"soak: budget used after {rnd - 1} rounds")
                return
            for st in CHAIN:
                self.current = f"soak round {rnd}/{self.a.soak}: {LABEL[st]}"
                self.record("soak", r.run(st), rnd)

    def test_parallel(self, deadline):
        jobs = self.a.jobs
        workers = sorted(set(self.a.workers), reverse=True)   # cheapest first
        self.event(f"parallel: making {jobs} project copies")
        projs = [str(self.copy(f"par{j:02d}")) for j in range(jobs)]
        chain_est = self._chain_serial_estimate()
        rows = []
        for w in workers:
            est = math.ceil(jobs / w) * chain_est if chain_est else None
            if est and time.time() + est > deadline:
                self.event(f"parallel: skip {w} worker(s) (needs ~{_hms(est)})")
                continue
            self.current = f"parallel: {jobs} jobs on {w} worker(s)"
            self.event(self.current)
            t0 = time.perf_counter()
            done = []
            with _clean_path(), ProcessPoolExecutor(
                    max_workers=w, mp_context=multiprocessing.get_context("spawn")) as ex:
                futs = [ex.submit(_chain_job, p, self.a.session, self.a.iteration,
                                  self.a.trial, CHAIN,
                                  str(self.out / "logs" / f"par{j:02d}_w{w}.log"), self.fake)
                        for j, p in enumerate(projs)]
                for j, fu in enumerate(as_completed(futs)):
                    try:
                        res = fu.result()
                    except Exception as e:                  # noqa: BLE001
                        self.event(f"parallel job crashed: {e}")
                        continue
                    done.append(res)
                    for row in res["rows"]:
                        self.record("parallel", row, 1, workers=w, job=j)
            wall = time.perf_counter() - t0
            if chain_est is None and w == 1 and done:
                chain_est = statistics.median(d["wall_s"] for d in done)
            ok = sum(d["ok"] for d in done)
            rows.append({"workers": w, "jobs": jobs, "ok_jobs": ok, "wall_s": round(wall, 1),
                         "jobs_per_hour": round(3600 * ok / wall, 2) if wall else None,
                         "median_job_s": round(statistics.median(d["wall_s"] for d in done), 1)
                         if done else None})
            self._write_parallel(rows, chain_est, jobs)
            self.event(f"parallel: {w} worker(s) -> {_hms(wall)} for {ok}/{jobs} jobs")
            if chain_est is None and done:
                chain_est = statistics.median(d["wall_s"] for d in done) * 1.0
        self._write_parallel(rows, chain_est, jobs)
        if not self.a.smoke:
            self._contrib_sweep(deadline)

    def _contrib_sweep(self, deadline):
        """JCF contributions is the one step that already uses a process pool;
        its n_jobs curve says whether pools pay off on this machine."""
        if time.time() > deadline:
            return
        r = self.runner("contrib")
        top = max(1, self.cores_log - 1)
        for n in sorted({1, 2, 4, top}):
            if n > top or time.time() > deadline:
                continue
            self.current = f"contributions with n_jobs={n}"
            self.record("contrib_jobs", r.run("contrib", n_jobs=n), 1, workers=n)

    def _chain_serial_estimate(self):
        med = self._medians(("stages", "soak"))
        s = sum(med.get(st, 0) for st in CHAIN)
        return s or None

    def _medians(self, tests):
        by = {}
        for x in self.rows:
            if x["test"] in tests and x["status"] == "ok":
                by.setdefault(x["stage"], []).append(x["wall_s"])
        return {k: statistics.median(v) for k, v in by.items()}

    def _write_parallel(self, rows, chain_est, jobs):
        base = next((r["wall_s"] for r in rows if r["workers"] == 1), None)
        est = base is None and chain_est
        if est:
            base = chain_est * jobs
        for r in rows:
            r["speedup"] = round(base / r["wall_s"], 2) if base and r["wall_s"] else None
            r["efficiency"] = (round(r["speedup"] / r["workers"], 2)
                               if r["speedup"] else None)
            r["baseline"] = "estimated from serial stage times" if est else "measured"
        self.results["parallel"] = rows
        with open(self.par_path, "w", newline="") as f:
            if rows:
                wr = csv.DictWriter(f, list(rows[0]))
                wr.writeheader()
                wr.writerows(rows)

    # -- driver ------------------------------------------------------------
    def run(self):
        self.write_header()
        todo = [t for t in ("stages", "profile", "soak", "parallel") if t in self.a.tests]
        try:
            for i, name in enumerate(todo):
                left = sum(WEIGHTS[t] for t in todo[i:])
                deadline = (self.t_end if self.a.smoke else      # smoke: one shared cap
                            time.time() + self.time_left() * WEIGHTS[name] / left)
                self.current = name
                self.event(f"== {name} (until {_dt.datetime.fromtimestamp(deadline):%H:%M})")
                try:
                    getattr(self, f"test_{name}")(deadline)
                except KeyboardInterrupt:
                    raise
                except Exception as e:                      # noqa: BLE001
                    self.event(f"{name} FAILED: {type(e).__name__}: {e}")
                    with open(self.log, "a") as lf:
                        lf.write(traceback.format_exc())
                self.write_summary()
        except KeyboardInterrupt:
            self.event("interrupted (Ctrl+C) -- writing summary")
        self.current = "done"
        self.write_summary()
        if not self.a.keep_copies and self.copies.exists():
            shutil.rmtree(self.copies, ignore_errors=True)
        self.event(f"done. read {self.out / 'SUMMARY.md'}")

    def write_header(self):
        info = {"started": _now().isoformat(timespec="seconds"),
                "host": platform.node(), "os": platform.platform(),
                "cpu": platform.processor(), "cores": f"{self.cores_phys} physical / "
                                                    f"{self.cores_log} logical",
                "python": sys.version.split()[0], "bioscout_git": _git_head(),
                "project": str(self.a.project), "session": self.a.session,
                "iteration": self.a.iteration, "trial": self.a.trial,
                "fake": self.fake, "args": vars(self.a)}
        try:
            import psutil
            info["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
        except Exception:
            pass
        if not self.fake:
            try:
                import opensim
                info["opensim"] = opensim.__version__
            except Exception as e:
                info["opensim"] = f"import failed: {e}"
            try:
                import bioscout
                info["bioscout"] = bioscout.__version__
            except Exception:
                pass
        self.info = info
        json.dump(info, open(self.out / "machine.json", "w"), indent=1, default=str)

    # -- the morning read ----------------------------------------------------
    def write_summary(self):
        L = [f"# Pipeline bench -- {self.info['started'][:16].replace('T', ' ')}", "",
             f"{self.info.get('host')} | {self.info.get('cores')} cores | "
             f"{self.info.get('ram_gb', '?')} GB | Python {self.info['python']} | "
             f"OpenSim {self.info.get('opensim', '-')} | bioscout "
             f"{self.info.get('bioscout', '-')} ({self.info['bioscout_git']})",
             f"Trial {self.a.trial}, iteration {self.a.iteration}"
             + (f", window cut to {self.a.window} s" if self.a.window else "") + ". "
             f"Ran {_hms(time.time() - self.t_start)}; "
             f"{self.n_ok} stages ok, {self.n_bad} failed.", ""]
        if self.fake:
            L += ["> **FAKE MODE** -- harness self-test, numbers mean nothing.", ""]

        # 1. stage table
        by = {}
        for x in self.rows:
            if x["test"] in ("stages", "soak") and x["status"] == "ok":
                by.setdefault(x["stage"], []).append(x)
        if by:
            chain_total = sum(statistics.median(r["wall_s"] for r in by[s])
                              for s in STAGES_TEST if s in by)
            L += ["## 1. Where the time goes (one trial, one process; stages + soak runs)", "",
                  "| stage | runs | median | min | max | spread | CPU/wall | share |",
                  "|---|---|---|---|---|---|---|---|"]
            ranked = sorted(by, key=lambda s: -statistics.median(r["wall_s"] for r in by[s]))
            for s in ranked:
                w = [r["wall_s"] for r in by[s]]
                c = [r["cpu_s"] for r in by[s]]
                med = statistics.median(w)
                spread = (max(w) - min(w)) / med * 100 if med else 0
                L.append(f"| {LABEL[s]} | {len(w)} | {med:.1f} s | {min(w):.1f} | "
                         f"{max(w):.1f} | {spread:.0f}% | "
                         f"{statistics.median(c) / med * 100 if med else 0:.0f}% | "
                         f"{med / chain_total * 100 if chain_total else 0:.0f}% |")
            L += ["", f"Whole chain (median, all stages above): **{_hms(chain_total)}** "
                  "per trial. CPU/wall well below 100% = waiting on disk or on "
                  "child processes; above 100% = multithreaded.", ""]

        # 2. profile buckets
        pb = self.results.get("profile")
        if pb:
            cats = ["opensim", "bioscout", "matplotlib", "pandas", "numpy/scipy",
                    "file I/O", "other"]
            L += ["## 2. Inside each stage (cProfile, own time)", "",
                  "| stage | " + " | ".join(cats) + " |",
                  "|---|" + "---|" * len(cats)]
            for st, b in pb.items():
                tot = sum(b.values()) or 1
                L.append(f"| {LABEL[st]} | " + " | ".join(
                    f"{b.get(c, 0) / tot * 100:.0f}%" for c in cats) + " |")
            L += ["", "OpenSim = time inside the C++ tools (not fixable here). "
                  "JCF contributions runs in child processes, so its profile only "
                  "shows the parent. "
                  "Everything else is ours: plotting, table reading/writing, "
                  "log writes. Details: profile/<stage>_top.txt, or "
                  "`snakeviz profile/<stage>.prof`.", ""]

        # 3. soak
        soak = [x for x in self.rows if x["test"] == "soak"]
        if soak:
            rounds = sorted({x["round"] for x in soak})
            per = []
            for rd in rounds:
                rr = [x for x in soak if x["round"] == rd]
                if len(rr) == len(CHAIN):
                    per.append((rd, sum(x["wall_s"] for x in rr), rr[-1]["rss_mb"],
                                rr[-1]["handles"], rr[-1]["figs"]))
            if len(per) >= 2:
                xs = [p[0] for p in per]
                rss = [p[2] for p in per if p[2] is not None]
                slope = _slope(xs[:len(rss)], rss) if len(rss) >= 3 else None
                k = max(1, len(per) // 5)
                t_first = statistics.median(p[1] for p in per[:k])
                t_last = statistics.median(p[1] for p in per[-k:])
                L += ["## 3. Soak (same process, chain repeated)", "",
                      f"- rounds completed: {len(per)}"
                      + ("" if len(per) >= 10 else " (too few for a trend)"),
                      f"- memory: {per[0][2]} MB after round 1 -> {per[-1][2]} MB "
                      f"after round {per[-1][0]}"
                      + (f"; trend **{slope:+.1f} MB per round**" if slope is not None else ""),
                      f"- handles: {per[0][3]} -> {per[-1][3]}; open figures at "
                      f"end of a round: {per[-1][4]}",
                      f"- chain time: first rounds {t_first:.0f} s, last rounds "
                      f"{t_last:.0f} s ({(t_last / t_first - 1) * 100 if t_first else 0:+.0f}%)",
                      "", "A steady MB/round climb or a growing chain time means a "
                      "long batch should restart its process every N trials.", ""]

        # 4. parallel
        par = self.results.get("parallel")
        if par:
            L += ["## 4. Several trials at once (separate processes)", "",
                  "| workers | jobs ok | wall | jobs/hour | speedup | efficiency |",
                  "|---|---|---|---|---|---|"]
            for r in sorted(par, key=lambda r: r["workers"]):
                L.append(f"| {r['workers']} | {r['ok_jobs']}/{r['jobs']} | "
                         f"{_hms(r['wall_s'])} | {r['jobs_per_hour']} | "
                         f"{r.get('speedup') or '-'}x | {r.get('efficiency') or '-'} |")
            L += ["", f"Speedup baseline: {par[0].get('baseline', '-')}. "
                  "Efficiency near 1 = cores scale cleanly; it drops when disk "
                  "or memory bandwidth becomes the limit.", ""]
        cj = [x for x in self.rows if x["test"] == "contrib_jobs" and x["status"] == "ok"]
        if cj:
            L += ["JCF contributions (already parallel) by n_jobs: " + ", ".join(
                f"{x['workers']} -> {x['wall_s']:.0f} s" for x in cj), ""]

        # 5. failures
        bad = [x for x in self.rows if x["status"] != "ok"]
        if bad:
            L += ["## Failures", ""]
            seen = set()
            for x in bad:
                key = (x["stage"], x["status"], x["error"][:80])
                if key in seen:
                    continue
                seen.add(key)
                n = sum(1 for y in bad if (y["stage"], y["status"], y["error"][:80]) == key)
                L.append(f"- {LABEL.get(x['stage'], x['stage'])} x{n}: {x['status']} "
                         f"{x['error']}")
            L += ["", "`no_output` = the stage returned but wrote no new output "
                  "file. Tracebacks are in run.log.", ""]
        (self.out / "SUMMARY.md").write_text("\n".join(L), encoding="utf-8")


def _shorten_window(proj, session, trial, seconds):
    """Cut the trial's time_range in the COPY's session.yaml to `seconds`,
    starting at the implanted-side on-plate contact when there is one (so mew
    still sees stance), else at the window start. session.yaml is the window
    authority, so every stage follows it."""
    import yaml
    path = os.path.join(proj, "simulations", *session.split("/"), "session.yaml")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tr = cfg["trials"][trial]
    t0, t1 = (float(x) for x in tr["time_range"])
    from bioscout.session.config import measured_side_of as _ms
    from bioscout.session.gait_events import normalise as _ev
    side = _ms(cfg) if _ms(cfg) in ("l", "r") else None
    start = next((e["time"] for k, e in _ev(tr.get("events")).items()
                  if side and k.startswith("foot_contact_") and k.endswith("_" + side)
                  and e.get("on_plate")), t0)
    start = min(max(start, t0), max(t0, t1 - seconds))
    tr["time_range"] = [round(start, 4), round(min(t1, start + seconds), 4)]
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)


def _bucket(ps):
    """Own (exclusive) time per library, from a pstats.Stats."""
    out = {}
    for (fn, _ln, func), (_cc, _nc, tt, _ct, _callers) in ps.stats.items():
        f = fn.replace("\\", "/").lower()
        fu = func.lower()
        if "/bioscout/" in f and "/site-packages/opensim" not in f:
            k = "bioscout"
        elif "opensim" in f or "opensim" in fu:
            k = "opensim"
        elif "matplotlib" in f or "/pil/" in f or "fonttools" in f:
            k = "matplotlib"
        elif "/pandas/" in f:
            k = "pandas"
        elif "/numpy/" in f or "/scipy/" in f or "numpy" in fu:
            k = "numpy/scipy"
        elif f == "~" and any(s in fu for s in ("io.open", "_io.", "method 'write'",
                                                "method 'read", "nt.stat", "posix.stat",
                                                "nt.listdir", "scandir", "copyfile")):
            k = "file I/O"
        else:
            k = "other"
        out[k] = out.get(k, 0.0) + tt
    return {k: round(v, 2) for k, v in out.items()}


def _slope(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    den = sum((a - mx) ** 2 for a in x)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / den if den else 0.0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m bioscout.devtools.bench",
                                description=__doc__.split("\n\n")[0])
    p.add_argument("--hours", type=float, default=None,
                   help="total time budget (default 8; 2 min with --smoke)")
    p.add_argument("--tests", default="stages,profile,soak,parallel",
                   help="comma list, run in this order (default: all four)")
    p.add_argument("--reps", type=int, default=5, help="rounds in the stages test (5)")
    p.add_argument("--soak", type=int, default=100, help="max soak rounds (100)")
    p.add_argument("--jobs", type=int, default=None,
                   help="trial copies in the parallel test (default: max workers, min 4)")
    p.add_argument("--workers", default=None,
                   help="comma list of process counts (default 1,2,4,... up to physical "
                        "cores, capped at 1 per 1.5 GB RAM)")
    p.add_argument("--project", default=str(DEFAULT_PROJECT))
    p.add_argument("--session", default=DEFAULT_SESSION,
                   help="session folder under simulations/ (default H1_orthoload/11_05_06)")
    p.add_argument("--iteration", default="gpk")
    p.add_argument("--trial", default="Walking_01")
    p.add_argument("--out", default=None, help="output folder (default example_data/_bench/<now>)")
    p.add_argument("--keep-copies", action="store_true",
                   help="keep the project copies (several hundred MB) after the run")
    p.add_argument("--window", type=float, default=None,
                   help="shorten the trial to this many seconds in the copies "
                        "(default: the full session.yaml window)")
    p.add_argument("--smoke", action="store_true",
                   help="~2 min check that every stage runs: 0.25 s window, 1 round, "
                        "2 soak rounds, 2 jobs on 2 workers, no profile")
    p.add_argument("--fake", action="store_true", help=argparse.SUPPRESS)  # harness self-test
    a = p.parse_args(argv)

    b_cores = Bench._cores()[0]              # physical: hyperthreads add little here
    try:
        import psutil
        b_cores = max(1, min(b_cores, int(psutil.virtual_memory().total / 2**30 / 1.5)))
    except Exception:
        pass
    if a.smoke:
        a.reps, a.soak, a.hours = 1, 2, a.hours or 2 / 60
        a.jobs, a.workers = 2, a.workers or "2"
        a.window = a.window or 0.25
        if a.tests == "stages,profile,soak,parallel":
            a.tests = "stages,soak,parallel"
    a.hours = a.hours or 8.0
    a.tests = [t.strip() for t in a.tests.split(",") if t.strip()]
    if a.workers:
        a.workers = [int(w) for w in str(a.workers).split(",")]
    else:
        a.workers, w = [], 1
        while w < b_cores:
            a.workers.append(w)
            w *= 2
        a.workers.append(b_cores)
    a.jobs = a.jobs or max(4, max(a.workers))
    if not a.fake and not os.path.isdir(os.path.join(a.project, "simulations")):
        p.error(f"no simulations/ in {a.project}")
    Bench(a).run()


if __name__ == "__main__":
    main()
