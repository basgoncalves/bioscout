"""bioscout.tests.test_logger_signature — the error handler must not be the bug.

Pins the 2026-08-24 crash: ``AppLogger.critical()`` took ``message`` alone,
but 21 call sites across the GUI log with ``exc_info=True`` and EVERY one of
them sits inside an ``except`` block. So::

    try:
        self.tabs[name] = tab_class(...)          # ImportError: no psutil
    except Exception as e:
        logger.critical(f"FAILED TO LOAD TAB ...", exc_info=True)   # TypeError

the TypeError escaped the handler and killed the whole application. A failure
the code had correctly CAUGHT became fatal, and the user saw a crash with the
real cause (a missing optional dependency) nowhere in sight.

Two tests, deliberately different in kind:

* :class:`TestAppLoggerAcceptsLoggingKwargs` pins the fix — every level method
  accepts what ``logging``'s own methods accept.
* :class:`TestNoCallSiteExceedsTheSignature` pins the CLASS of bug — it scans
  the package for ``logger.<level>(...)`` calls using keywords AppLogger does
  not forward. Narrow the signature again and this fails in the suite instead
  of in someone's launch.

Standard library only; logger.py is imported by file path so this runs in a
bare environment (see utils-init-scipy-block).
"""
import ast
import importlib.util
import logging
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.normpath(os.path.join(_HERE, ".."))
_MOD = os.path.join(_PKG, "utils", "logger.py")

try:
    _spec = importlib.util.spec_from_file_location("_bioscout_logger", _MOD)
    lg = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(lg)
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False

#: The level methods every caller uses.
LEVELS = ("debug", "info", "warning", "error", "critical")

#: Keyword arguments logging's own methods accept. AppLogger must forward all
#: of them; anything else at a call site is a genuine mistake.
LOGGING_KWARGS = {"exc_info", "stack_info", "stacklevel", "extra"}


@unittest.skipUnless(HAVE, "utils/logger.py not importable")
class TestAppLoggerAcceptsLoggingKwargs(unittest.TestCase):
    """Every level method takes what logging takes — no TypeError, ever."""

    @classmethod
    def setUpClass(cls):
        cls.log = lg.AppLogger()
        # Keep the suite quiet: this test cares that the calls RETURN, not
        # what they print.
        cls.log.logger.handlers = [logging.NullHandler()]
        cls.log.logger.propagate = False

    def _boom(self):
        try:
            raise ImportError("No module named 'psutil'")
        except ImportError:
            return sys.exc_info()

    def test_exc_info_true_inside_except(self):
        """The exact shape of the crash: exc_info=True from a handler."""
        for level in LEVELS:
            with self.subTest(level=level):
                try:
                    raise ImportError("No module named 'psutil'")
                except ImportError as e:
                    getattr(self.log, level)(
                        f"FAILED TO LOAD TAB 'Recording': {type(e).__name__}: {e}",
                        exc_info=True)          # must not raise

    def test_every_logging_kwarg(self):
        for level in LEVELS:
            for kw, val in (("exc_info", False), ("exc_info", self._boom()),
                            ("stack_info", False), ("stacklevel", 1),
                            ("extra", {"trial": "Squat_BW_01"})):
                with self.subTest(level=level, kwarg=kw):
                    getattr(self.log, level)("msg", **{kw: val})

    def test_percent_style_lazy_args(self):
        """logging's %-style deferred formatting must survive the wrapper."""
        for level in LEVELS:
            with self.subTest(level=level):
                getattr(self.log, level)("tab %s failed: %s", "Recording", "no psutil")

    def test_exception_and_log_helpers_exist(self):
        self.assertTrue(callable(getattr(self.log, "exception", None)))
        self.assertTrue(callable(getattr(self.log, "log", None)))
        try:
            raise ValueError("x")
        except ValueError:
            self.log.exception("handled")
        self.log.log(logging.WARNING, "explicit level")

    def test_a_failing_log_call_cannot_escape_a_handler(self):
        """The property that actually matters, stated as a property.

        Simulates the real control flow: an inner failure is caught, the
        handler logs it. The handler must complete, and the outer scope must
        see no exception.
        """
        reached_end = False
        try:
            try:
                raise ImportError("No module named 'psutil'")
            except ImportError as e:
                self.log.critical(f"caught: {e}", exc_info=True)
            reached_end = True
        except BaseException as escaped:                        # noqa: BLE001
            self.fail(f"logging call escaped the handler: "
                      f"{type(escaped).__name__}: {escaped}")
        self.assertTrue(reached_end)


class TestNoCallSiteExceedsTheSignature(unittest.TestCase):
    """No `logger.<level>(...)` in the package uses a kwarg we don't forward."""

    def _py_files(self):
        skip = {"__pycache__", "_to_delete", "tests"}
        for root, dirs, files in os.walk(_PKG):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for f in files:
                if f.endswith(".py"):
                    yield os.path.join(root, f)

    def test_call_sites_use_only_forwarded_kwargs(self):
        offenders = []
        for path in self._py_files():
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    tree = ast.parse(fh.read(), filename=path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute) and fn.attr in LEVELS):
                    continue
                if not (isinstance(fn.value, ast.Name)
                        and fn.value.id in ("logger", "log", "_logger")):
                    continue
                for kw in node.keywords:
                    if kw.arg is not None and kw.arg not in LOGGING_KWARGS:
                        offenders.append(
                            f"{os.path.relpath(path, _PKG)}:{node.lineno} "
                            f"logger.{fn.attr}(..., {kw.arg}=)")
        self.assertEqual(offenders, [], "logger call sites using a keyword "
                                        "AppLogger does not forward:\n  "
                                        + "\n  ".join(offenders))

    @unittest.skipUnless(HAVE, "utils/logger.py not importable")
    def test_signature_actually_forwards(self):
        """Guards the reverse direction: the signature must stay open.

        A future 'tidy-up' that pins these back to (self, message) would make
        every exc_info call site fatal again. This notices.
        """
        import inspect
        for level in LEVELS + ("exception",):
            with self.subTest(level=level):
                sig = inspect.signature(getattr(lg.AppLogger, level))
                kinds = {p.kind for p in sig.parameters.values()}
                self.assertIn(inspect.Parameter.VAR_KEYWORD, kinds,
                              f"AppLogger.{level} must accept **kwargs — "
                              f"21 call sites pass exc_info=True from inside "
                              f"an except block")


if __name__ == "__main__":
    unittest.main(verbosity=2)
