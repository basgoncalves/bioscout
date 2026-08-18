"""bioscout.tests.test_logging — the stdout tee, and the two ways it ate output.

Both bugs here were found in a Jupyter notebook (2026-08-18): a cell ran
`bs.Project(...)`, the next cell called `print()`, the cell reported success in
0.0s and displayed NOTHING. Neither failure raises, so only a test keeps them
fixed.

Pure stdlib — no OpenSim, no scipy, no ipykernel.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

try:
    from bioscout.utils import shared
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False


class _Reset:
    """start_logging is idempotent per PROCESS, so each test has to put the
    module's globals back or only the first one would do anything."""

    def __enter__(self):
        self.out, self.err = sys.stdout, sys.stderr
        self.state = (shared._LOG_STARTED, shared._LOG_HANDLE,
                      shared._LOG_FINISHED, shared._OSIM_SINK)
        shared._LOG_STARTED = False
        shared._LOG_HANDLE = None
        shared._LOG_FINISHED = False
        self.dir = tempfile.mkdtemp(prefix="bs_log_")
        return self

    def __exit__(self, *exc):
        h = shared._LOG_HANDLE
        sys.stdout, sys.stderr = self.out, self.err
        (shared._LOG_STARTED, shared._LOG_HANDLE, shared._LOG_FINISHED,
         shared._OSIM_SINK) = self.state
        try:
            if h:
                h.close()
        except Exception:
            pass
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


@unittest.skipUnless(HAVE, "bioscout.utils.shared not importable")
class TestTee(unittest.TestCase):
    def test_raw_passes_everything_through(self):
        buf = io.StringIO()
        t = shared._Tee(buf, raw=True)
        t.write("nothing here is on any whitelist\n")
        self.assertIn("nothing here is on any whitelist", buf.getvalue())

    def test_filtered_drops_unwhitelisted_under_minimal(self):
        # the behaviour `raw` exists to switch off — pinned so the fix cannot be
        # "solved" by deleting the filter
        buf = io.StringIO()
        t = shared._Tee(buf, raw=False)
        real = shared._log_verbosity
        shared._log_verbosity = lambda: "minimal"
        try:
            t.write("some ordinary sentence a user printed\n")
        finally:
            shared._log_verbosity = real
        self.assertEqual(buf.getvalue(), "")

    def test_stream_probes_do_not_raise(self):
        t = shared._Tee(io.StringIO())
        self.assertIsInstance(t.isatty(), bool)
        self.assertTrue(isinstance(t.encoding, str))
        t.flush()


@unittest.skipUnless(HAVE, "bioscout.utils.shared not importable")
class TestStartLogging(unittest.TestCase):
    def test_tees_onto_the_current_stdout_not_the_process_one(self):
        """THE notebook bug: ipykernel replaces sys.stdout with the stream that
        feeds the cell, so a tee built on sys.__stdout__ writes to the terminal
        that launched the kernel and the cell shows nothing."""
        with _Reset() as r:
            cell = io.StringIO()                 # stands in for ipykernel's stream
            sys.stdout = cell
            shared.start_logging("test", log_dir=r.dir)
            print("visible in the cell")
            self.assertIn("visible in the cell", cell.getvalue())

    def test_notebook_output_is_not_filtered(self):
        with _Reset() as r:
            cell = io.StringIO()
            sys.stdout = cell
            real_nb, real_v = shared.in_notebook, shared._log_verbosity
            shared.in_notebook = lambda: True
            shared._log_verbosity = lambda: "minimal"
            try:
                shared.start_logging("test", log_dir=r.dir)
                print("2.0.0c1 C:/Git/bioscout/bioscout/__init__.py")
            finally:
                shared.in_notebook, shared._log_verbosity = real_nb, real_v
            self.assertIn("2.0.0c1", cell.getvalue())

    def test_console_run_still_filters(self):
        """Batch behaviour is unchanged: outside a kernel the log stays terse."""
        with _Reset() as r:
            console = io.StringIO()
            sys.stdout = console
            real_nb, real_v = shared.in_notebook, shared._log_verbosity
            shared.in_notebook = lambda: False
            shared._log_verbosity = lambda: "minimal"
            try:
                shared.start_logging("test", log_dir=r.dir)
                before = console.getvalue()
                print("an ordinary line nobody whitelisted")
            finally:
                shared.in_notebook, shared._log_verbosity = real_nb, real_v
            self.assertEqual(console.getvalue(), before)

    def test_writes_a_log_file(self):
        with _Reset() as r:
            sys.stdout = io.StringIO()
            shared.start_logging("test", log_dir=r.dir)
            logs = [f for f in os.listdir(r.dir) if f.endswith(".log")]
            self.assertEqual(len(logs), 1)
            self.assertTrue(logs[0].startswith("bioscout_"))

    def test_disabled_by_env(self):
        with _Reset() as r:
            sys.stdout = cell = io.StringIO()
            old = os.environ.get("BIOSCOUT_LOG")
            os.environ["BIOSCOUT_LOG"] = "0"
            try:
                self.assertIsNone(shared.start_logging("test", log_dir=r.dir))
                self.assertIs(sys.stdout, cell)      # stdout left alone entirely
            finally:
                if old is None:
                    os.environ.pop("BIOSCOUT_LOG", None)
                else:
                    os.environ["BIOSCOUT_LOG"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
