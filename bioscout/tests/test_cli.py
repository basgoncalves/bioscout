"""Tests for :mod:`bioscout.cli` — the verb surface and its legacy translation.

The translation table is the risky part of this refactor: a wrong entry does not
crash, it silently runs the wrong command. So every verb is pinned to the exact
legacy argv it produces.

Stdlib only, no filesystem, no OpenSim — like the CLI itself.
"""
from __future__ import annotations

import argparse
import ast
import io
import contextlib
import sys
import unittest
from pathlib import Path

from bioscout import cli


class TestParser(unittest.TestCase):
    def test_root_help_is_ten_verbs(self):
        p = cli.build_parser()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            p.print_help()
        text = out.getvalue()
        for verb in cli.VERBS:
            self.assertIn(verb, text, f"{verb} missing from root help")

    def test_every_verb_has_its_own_help(self):
        """`bioscout <verb> --help` must work for all of them, and exit 0."""
        p = cli.build_parser()
        for verb in cli.VERBS:
            if verb == "help":
                continue
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()):
                p.parse_args([verb, "--help"])
            self.assertEqual(cm.exception.code, 0, verb)

    def test_verbs_with_actions_show_help_when_given_none(self):
        for verb in ("session", "model", "utils", "lab"):
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()):
                cli.route([verb])
            self.assertEqual(cm.exception.code, 0, verb)

    def test_help_verb(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.route(["help"]), ("exit", 0))
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            cli.route(["help", "run"])

    def test_unknown_verb_is_rejected(self):
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            cli.route(["frobnicate"])
        self.assertNotEqual(cm.exception.code, 0)


class TestTranslation(unittest.TestCase):
    """Each verb -> the exact legacy argv. Pinned, because a wrong entry is silent."""

    def legacy(self, argv):
        kind, value = cli.route(argv)
        self.assertEqual(kind, "legacy", f"{argv} did not translate")
        return value

    def test_init_and_gui(self):
        self.assertEqual(self.legacy(["init", "myproj"]), ["--init", "myproj"])
        self.assertEqual(self.legacy(["init"]), ["--init", "."])
        self.assertEqual(self.legacy(["gui"]), ["--gui"])

    def test_run(self):
        self.assertEqual(self.legacy(["run"]), ["--run_subject"])
        self.assertEqual(self.legacy(["run", "021"]), ["--run_subject", "021"])
        self.assertEqual(
            self.legacy(["run", "021", "--session", "pre,post", "--replace"]),
            ["--run_subject", "021", "--session", "pre,post", "--REPLACE"])
        self.assertEqual(
            self.legacy(["run", "021", "--trial", "RunA1", "--export", "--reset"]),
            ["--run_subject", "021", "--trial", "RunA1", "--export", "--reset"])

    def test_run_batch_wins(self):
        """--batch is a different entry point; it must not be mixed with --run_subject."""
        self.assertEqual(self.legacy(["run", "--batch", "settings.py"]), ["-b", "settings.py"])

    def test_session_new(self):
        """--no-gui, so the test never tries to open a window.

        Without it this verb goes to the dialog on a machine with a display and
        to the flag path on one without, which is a test that depends on where
        it runs.
        """
        self.assertEqual(self.legacy(["session", "new", "s/021/pre", "--no-gui"]),
                         ["--new-session", "s/021/pre"])
        self.assertEqual(
            self.legacy(["session", "new", "s/022/pre", "--no-gui", "--from",
                         "s/021/pre", "--body-mass", "61.3"]),
            ["--new-session", "s/022/pre", "--from-session", "s/021/pre",
             "--body-mass", "61.3"])

    def test_session_new_falls_back_to_flags_when_headless(self):
        """No display must not mean 'exit 0 having written nothing'.

        Patches ``session_editor`` — the module ``cli._direct`` imports from.
        Patching the ``new_session_dialog`` shim instead did nothing, so on a
        machine WITH a display this test opened the editor and blocked the whole
        suite on a modal window. ``open_session_editor`` is stubbed to raise as
        well, so the failure mode is a red test rather than a hung run.
        """
        import bioscout.cli as _c
        try:
            from bioscout.gui import session_editor as _se
        except Exception:
            self.skipTest("GUI module not importable here")
        real_avail, real_open = _se.gui_available, _se.open_session_editor

        def _must_not_open(*_a, **_kw):
            raise AssertionError("the test suite must never open a window")

        _se.gui_available = lambda: False
        _se.open_session_editor = _must_not_open
        try:
            kind, value = _c.route(["session", "new", "s/021/pre"])
        finally:
            _se.gui_available, _se.open_session_editor = real_avail, real_open
        self.assertEqual((kind, value), ("legacy", ["--new-session", "s/021/pre"]))

    def test_no_verb_can_open_a_window_without_no_gui_in_tests(self):
        """Guard: every session verb the suite routes must be window-free.

        `session new` and `session edit` are the only verbs that can raise a
        dialog. Anything routed here without --no-gui on a developer machine
        would hang the suite instead of failing it.
        """
        import bioscout.cli as _c
        try:
            from bioscout.gui import session_editor as _se
        except Exception:
            self.skipTest("GUI module not importable here")
        real_avail, real_open = _se.gui_available, _se.open_session_editor
        _se.gui_available = lambda: False
        _se.open_session_editor = lambda *a, **k: 0
        try:
            for argv in (["session", "new", "p", "--no-gui"],
                         ["session", "edit", "p", "--no-gui"]):
                kind, _ = _c.route(argv)
                self.assertEqual(kind, "legacy", argv)
        finally:
            _se.gui_available, _se.open_session_editor = real_avail, real_open

    def test_session(self):
        self.assertEqual(self.legacy(["session", "export", "s/021/pre"]),
                         ["--c3d-export", "s/021/pre"])
        self.assertEqual(
            self.legacy(["session", "classify", "s/021/pre", "--no-plots", "--write-yaml"]),
            ["--classifier", "s/021/pre", "--no-plots", "--write-session-yaml"])
        self.assertEqual(
            self.legacy(["session", "ingest", "raw/", "--subject", "022", "--session", "pre"]),
            ["--ingest-c3d", "raw/", "--subject", "022", "--session", "pre"])
        self.assertEqual(
            self.legacy(["session", "reset", "--subject", "021", "--dry-run", "--raw"]),
            ["--reset", "--subject", "021", "--reset-dry-run", "--reset-raw"])

    def test_model_edit_ma_compare_jc(self):
        self.assertEqual(self.legacy(["model", "edit"]), ["--model-edit"])
        self.assertEqual(self.legacy(["model", "edit", "proj"]), ["--model-edit", "proj"])
        self.assertEqual(self.legacy(["model", "ma", "proj"]), ["--change-moment-arms", "proj"])
        self.assertEqual(self.legacy(["model", "compare", "a.osim", "b.osim"]),
                         ["--compare-models", "a.osim", "b.osim"])
        self.assertEqual(
            self.legacy(["model", "compare", "models/", "-o", "t.xlsx", "--figures"]),
            ["--compare-models", "models/", "-o", "t.xlsx", "--figures"])
        self.assertEqual(
            self.legacy(["model", "compare", "models/", "--figures", "figs/"]),
            ["--compare-models", "models/", "--figures", "figs/"])
        self.assertEqual(self.legacy(["model", "joint-centres", "static.trc"]),
                         ["--joint-centres", "static.trc"])
        self.assertEqual(self.legacy(["model", "jc", "static.trc", "-o", "out.trc"]),
                         ["--joint-centres", "static.trc", "-o", "out.trc"])

    def test_tps_and_plot(self):
        self.assertEqual(self.legacy(["tps"]), ["--tps"])
        self.assertEqual(self.legacy(["plot", "summary", "proj"]), ["--summary", "proj"])
        self.assertEqual(
            self.legacy(["plot", "summary", "--subject", "021", "--overall"]),
            ["--summary", "-overall", "-s", "021"])
        self.assertEqual(
            self.legacy(["plot", "collings", "sess/", "--top", "12", "--side", "_l"]),
            ["--collings", "sess/", "--side", "_l", "--top", "12"])

    def test_utils(self):
        self.assertEqual(self.legacy(["utils", "install"]), ["--install"])
        self.assertEqual(self.legacy(["utils", "pylance"]), ["--pylance-fix"])
        self.assertEqual(
            self.legacy(["utils", "md2pdf", "a.md", "b.md", "--toc", "--outdir", "pdf/"]),
            ["--md2pdf", "a.md", "b.md", "--outdir", "pdf/", "--toc"])

    def test_lab(self):
        got = self.legacy(["lab", "shots", "clip.mp4", "--shooting-hand", "left"])
        self.assertEqual(got[:2], ["--shots", "clip.mp4"])
        self.assertIn("--shooting-hand", got)
        self.assertEqual(got[got.index("--shooting-hand") + 1], "left")
        got = self.legacy(["lab", "load-report", "exports/", "--age", "34", "--zepp-pull"])
        self.assertEqual(got[:2], ["--load-report", "exports/"])
        self.assertIn("--zepp-pull", got)
        self.assertEqual(self.legacy(["lab", "add-subject"]), ["--add_subject"])

    def test_optional_flags_are_omitted_when_unset(self):
        """An unset option must not reach the legacy argv as an empty string."""
        for argv in (["run", "021"], ["model", "compare", "a.osim"],
                     ["plot", "collings"], ["utils", "md2pdf", "a.md"]):
            for token in self.legacy(argv):
                self.assertNotEqual(token, "", argv)
                self.assertNotEqual(token, "None", argv)


class TestLegacyHint(unittest.TestCase):
    def test_names_the_replacement(self):
        self.assertIn("bioscout run", cli.legacy_hint(["--run_subject", "021"]))
        self.assertIn("bioscout model edit", cli.legacy_hint(["--model-edit"]))
        self.assertIn("bioscout utils env", cli.legacy_hint(["--env"]))
        self.assertIn("bioscout plot collings", cli.legacy_hint(["--collings", "s/"]))

    def test_silent_for_unmapped_and_new_style(self):
        self.assertIsNone(cli.legacy_hint(["--REPLACE"]))
        self.assertIsNone(cli.legacy_hint(["run", "021"]))
        self.assertIsNone(cli.legacy_hint([]))

    def test_handles_equals_form(self):
        self.assertIn("bioscout init", cli.legacy_hint(["--init=proj"]))

    def test_every_mapped_flag_names_a_real_verb(self):
        for flag, new in cli._LEGACY.items():
            verb = new.split()[1]
            self.assertIn(verb, cli.VERBS, f"{flag} -> {new}: '{verb}' is not a verb")


class TestStaysLight(unittest.TestCase):
    """`bioscout -h` must not need the scientific stack.

    Checked structurally rather than by import side effects, because by the time
    this test runs numpy is loaded anyway — the question is whether *this module*
    pulls it in at import time.
    """

    STDLIB_OK = {"argparse", "sys", "os", "typing", "__future__", "runpy",
                 "pathlib", "re", "json", "textwrap", "shutil"}

    def test_module_level_imports_are_stdlib(self):
        src = Path(cli.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        offenders = []
        for node in tree.body:                      # module level only
            if isinstance(node, ast.Import):
                offenders += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                offenders.append(node.module.split(".")[0])
        bad = [m for m in offenders if m not in self.STDLIB_OK]
        self.assertEqual(bad, [], f"bioscout.cli imports {bad} at module level")

    def test_bioscout_is_not_imported_at_module_level(self):
        src = Path(cli.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in tree.body:
            mod = getattr(node, "module", None) or ""
            names = [a.name for a in getattr(node, "names", [])]
            self.assertNotIn("bioscout", mod.split("."),
                             "bioscout.cli must import bioscout lazily")
            for n in names:
                self.assertFalse(n.startswith("bioscout"),
                                 "bioscout.cli must import bioscout lazily")


if __name__ == "__main__":
    unittest.main(verbosity=2)
