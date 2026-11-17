"""quiet_run: notebook calls honour log_terminal (details to the log, cell shows
warnings/errors only) and always restore the streams."""
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

try:
    from bioscout.utils import shared as S
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False


@unittest.skipUnless(HAVE, "bioscout.utils not importable")
class TestQuietRun(unittest.TestCase):
    def _run(self, log_terminal):
        d = tempfile.mkdtemp()
        with mock.patch.object(S, "in_notebook", lambda: True), \
             mock.patch.object(S, "_log_terminal", lambda: log_terminal), \
             mock.patch.dict(os.environ, {"BIOSCOUT_OPEN_LOG": "0"}):
            S.start_logging(name="t", log_dir=d)

            @S.quiet_run("demo")
            def work():
                print("detail line")
                print("[WARNING] odd")
                raise_it = False
                return 7 if not raise_it else None

            buf, old = io.StringIO(), sys.stdout
            sys.stdout = buf
            try:
                r = work()
            finally:
                sys.stdout = old
            S.stop_logging()
        return r, buf.getvalue()

    def test_quiet_shows_warnings_only(self):
        r, shown = self._run(False)
        self.assertEqual(r, 7)
        self.assertIn("[WARNING] odd", shown)
        self.assertNotIn("detail line", shown)
        self.assertIsNone(S._SAVED_STREAMS)

    def test_log_terminal_true_prints_everything(self):
        _r, shown = self._run(True)
        self.assertIn("detail line", shown)


if __name__ == "__main__":
    unittest.main()
