"""Tests for :mod:`bioscout.model` — geometry resolution on both schemas.

Stdlib only, synthetic fixtures written to a temp dir, so this runs anywhere:
no OpenSim, no numpy, no real models, no network. That is deliberate — this is
the check that is supposed to work in a bare CI environment.

Run:  python -m unittest bioscout.tests.test_model -v
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bioscout.model import (format_text, geometry_refs, verify_model,
                                 verify_tree)
from bioscout.model import geometry as _geometry
from bioscout.model.cli import main as cli_main

# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
V3_MODEL = """<?xml version="1.0" encoding="UTF-8"?>
<OpenSimDocument Version="30000">
  <Model name="v3">
    <BodySet>
      <objects>
        <Body name="pelvis">
          <VisibleObject>
            <GeometrySet>
              <objects>
                <DisplayGeometry>
                  <geometry_file>{pelvis}</geometry_file>
                </DisplayGeometry>
                <DisplayGeometry>
                  <geometry_file>{sacrum}</geometry_file>
                </DisplayGeometry>
              </objects>
            </GeometrySet>
          </VisibleObject>
        </Body>
        <Body name="femur_r">
          <VisibleObject>
            <GeometrySet>
              <objects>
                <DisplayGeometry>
                  <geometry_file>{femur}</geometry_file>
                </DisplayGeometry>
              </objects>
            </GeometrySet>
          </VisibleObject>
        </Body>
      </objects>
    </BodySet>
  </Model>
</OpenSimDocument>
"""

V4_MODEL = """<?xml version="1.0" encoding="UTF-8"?>
<OpenSimDocument Version="40000">
  <Model name="v4">
    <BodySet>
      <objects>
        <Body name="pelvis">
          <attached_geometry>
            <Mesh name="pelvis_geom">
              <mesh_file>{pelvis}</mesh_file>
            </Mesh>
          </attached_geometry>
        </Body>
      </objects>
    </BodySet>
    <ComponentSet>
      <objects>
        <!-- a ground mesh, deliberately OUTSIDE any Body: a checker that only
             walks <Body> subtrees reports this model clean -->
        <Mesh name="floor">
          <mesh_file>{floor}</mesh_file>
        </Mesh>
      </objects>
    </ComponentSet>
  </Model>
</OpenSimDocument>
"""

NO_GEOMETRY_MODEL = """<?xml version="1.0" encoding="UTF-8"?>
<OpenSimDocument Version="40000">
  <Model name="bare">
    <BodySet>
      <objects>
        <Body name="pelvis">
          <attached_geometry>
            <Mesh name="none"><mesh_file></mesh_file></Mesh>
          </attached_geometry>
        </Body>
      </objects>
    </BodySet>
  </Model>
</OpenSimDocument>
"""


class _Tree(unittest.TestCase):
    """Builds a throwaway project tree; subclasses lay out the pieces."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bioscout_model_check_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

        # The fixtures must not inherit THIS MACHINE's geometry. bioscout ships
        # a Geometry/ folder that really does contain pelvis.vtp, sacrum.vtp and
        # femur.vtp, and OPENSIM_HOME may point at another. Without this, a
        # fixture asserting "missing" resolves through the bundle and the suite
        # passes in a bare checkout while failing inside the installed package —
        # which is precisely the environment-dependent green the checker exists
        # to stop us shipping.
        for patch in (
            mock.patch.object(_geometry, "bundled_geometry_dir", lambda: None),
            mock.patch.dict(os.environ, {}, clear=False),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("OPENSIM_HOME", None)
        _geometry.clear_cache()
        self.addCleanup(_geometry.clear_cache)

    def mesh(self, *parts, content: str = "vtp") -> Path:
        p = self.tmp.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def model(self, *parts, template: str = V3_MODEL, **refs) -> Path:
        p = self.tmp.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(template.format(**refs), encoding="utf-8")
        return p


# --------------------------------------------------------------------------- #
class TestReading(_Tree):
    def test_v3_and_v4_tags_are_both_found(self):
        m3 = self.model("a", "v3.osim", pelvis="pelvis.vtp", sacrum="sacrum.vtp",
                        femur="femur.vtp")
        m4 = self.model("b", "v4.osim", template=V4_MODEL,
                        pelvis="pelvis.vtp", floor="floor.vtp")
        self.assertEqual({r.tag for r in geometry_refs(m3)}, {"geometry_file"})
        self.assertEqual({r.tag for r in geometry_refs(m4)}, {"mesh_file"})
        self.assertEqual(len(geometry_refs(m3)), 3)

    def test_geometry_outside_a_body_is_not_missed(self):
        """The ground mesh in ComponentSet must be reported, with body None."""
        m = self.model("b", "v4.osim", template=V4_MODEL,
                       pelvis="pelvis.vtp", floor="floor.vtp")
        refs = {r.raw: r for r in geometry_refs(m)}
        self.assertIn("floor.vtp", refs)
        self.assertIsNone(refs["floor.vtp"].body)
        self.assertEqual(refs["pelvis.vtp"].body, "pelvis")

    def test_empty_mesh_element_is_not_a_reference(self):
        m = self.tmp / "bare.osim"
        m.write_text(NO_GEOMETRY_MODEL, encoding="utf-8")
        self.assertEqual(geometry_refs(m), [])
        rep = verify_model(m)
        self.assertTrue(rep.ok())
        self.assertEqual(rep.headline, "no geometry referenced")

    def test_repeated_reference_is_counted_once_but_tallied(self):
        m = self.model("a", "dup.osim", pelvis="pelvis.vtp", sacrum="pelvis.vtp",
                       femur="femur.vtp")
        refs = {r.raw: r for r in geometry_refs(m)}
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs["pelvis.vtp"].count, 2)


# --------------------------------------------------------------------------- #
class TestTiers(_Tree):
    def test_local_beside_the_model(self):
        self.model("a", "m.osim", pelvis="pelvis.vtp", sacrum="sacrum.vtp",
                   femur="femur.vtp")
        for n in ("pelvis", "sacrum", "femur"):
            self.mesh("a", f"{n}.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"local"})
        self.assertTrue(rep.ok(strict=True))
        self.assertIn("all 3", rep.headline)

    def test_local_via_the_implicit_Geometry_subfolder(self):
        self.model("a", "m.osim", pelvis="pelvis.vtp", sacrum="sacrum.vtp",
                   femur="femur.vtp")
        for n in ("pelvis", "sacrum", "femur"):
            self.mesh("a", "Geometry", f"{n}.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"local"})

    def test_reference_carrying_its_own_subpath(self):
        self.model("a", "m.osim", pelvis="Geometry/pelvis.vtp",
                   sacrum="Geometry/sacrum.vtp", femur="Geometry/femur.vtp")
        for n in ("pelvis", "sacrum", "femur"):
            self.mesh("a", "Geometry", f"{n}.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"local"})

    def test_windows_backslash_reference_resolves_on_any_os(self):
        self.model("a", "m.osim", pelvis="Geometry\\pelvis.vtp",
                   sacrum="pelvis.vtp", femur="pelvis.vtp")
        self.mesh("a", "Geometry", "pelvis.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"local"})

    def test_parent_geometry_is_a_warning_not_a_pass(self):
        """models/<subject>/m.osim + models/Geometry — the common project shape."""
        self.model("models", "s021", "m.osim", pelvis="pelvis.vtp",
                   sacrum="sacrum.vtp", femur="femur.vtp")
        for n in ("pelvis", "sacrum", "femur"):
            self.mesh("models", "Geometry", f"{n}.vtp")
        rep = verify_model(self.tmp / "models" / "s021" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"parent"})
        self.assertTrue(rep.ok(), "resolves, so a plain run passes")
        self.assertFalse(rep.ok(strict=True), "not portable, so --strict fails")
        self.assertIn("not portable", rep.headline)

    def test_absolute_path_resolves_but_warns(self):
        target = self.mesh("elsewhere", "pelvis.vtp")
        self.model("a", "m.osim", pelvis=str(target), sacrum=str(target),
                   femur=str(target))
        rep = verify_model(self.tmp / "a" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"absolute"})
        self.assertTrue(rep.ok())
        self.assertFalse(rep.ok(strict=True))

    def test_absolute_path_that_does_not_exist_is_missing(self):
        self.model("a", "m.osim", pelvis="/no/such/pelvis.vtp",
                   sacrum="/no/such/sacrum.vtp", femur="/no/such/femur.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        self.assertEqual({r.tier for r in rep.refs}, {"missing"})
        self.assertFalse(rep.ok())

    def test_explicit_search_dir_resolves_as_search(self):
        self.model("a", "m.osim", pelvis="pelvis.vtp", sacrum="sacrum.vtp",
                   femur="femur.vtp")
        for n in ("pelvis", "sacrum", "femur"):
            self.mesh("shared_geometry", f"{n}.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim",
                           extra_search=[self.tmp / "shared_geometry"])
        self.assertEqual({r.tier for r in rep.refs}, {"search"})
        self.assertTrue(rep.ok())
        self.assertFalse(rep.ok(strict=True))

    def test_missing_geometry_is_the_headline_failure(self):
        self.model("a", "m.osim", pelvis="pelvis.vtp", sacrum="sacrum.vtp",
                   femur="femur.vtp")
        self.mesh("a", "pelvis.vtp")          # only one of the three exists
        rep = verify_model(self.tmp / "a" / "m.osim")
        tiers = {r.raw: r.tier for r in rep.refs}
        self.assertEqual(tiers["pelvis.vtp"], "local")
        self.assertEqual(tiers["sacrum.vtp"], "missing")
        self.assertFalse(rep.ok())
        self.assertIn("WITHOUT those bones", rep.headline)

    def test_zero_byte_mesh_counts_as_broken_not_resolved(self):
        self.model("a", "m.osim", pelvis="pelvis.vtp", sacrum="sacrum.vtp",
                   femur="femur.vtp")
        self.mesh("a", "pelvis.vtp", content="")
        self.mesh("a", "sacrum.vtp")
        self.mesh("a", "femur.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        tiers = {r.raw: r.tier for r in rep.refs}
        self.assertEqual(tiers["pelvis.vtp"], "empty")
        self.assertFalse(rep.ok())

    @unittest.skipIf(sys.platform.startswith("win") or sys.platform == "darwin",
                     "needs a case-sensitive filesystem to be meaningful")
    def test_case_only_match_is_reported_as_its_own_tier(self):
        """The model that works on Windows and breaks for the collaborator."""
        self.model("a", "m.osim", pelvis="Pelvis.vtp", sacrum="sacrum.vtp",
                   femur="femur.vtp")
        self.mesh("a", "pelvis.vtp")
        self.mesh("a", "sacrum.vtp")
        self.mesh("a", "femur.vtp")
        rep = verify_model(self.tmp / "a" / "m.osim")
        tiers = {r.raw: r.tier for r in rep.refs}
        self.assertEqual(tiers["Pelvis.vtp"], "case")
        self.assertTrue(rep.ok(), "it does resolve, on some filesystems")
        self.assertFalse(rep.ok(strict=True))

    def test_local_wins_over_parent_when_both_exist(self):
        self.model("models", "s021", "m.osim", pelvis="pelvis.vtp",
                   sacrum="pelvis.vtp", femur="pelvis.vtp")
        self.mesh("models", "Geometry", "pelvis.vtp", content="wrong")
        self.mesh("models", "s021", "pelvis.vtp", content="right")
        rep = verify_model(self.tmp / "models" / "s021" / "m.osim")
        ref = rep.refs[0]
        self.assertEqual(ref.tier, "local")
        self.assertEqual(ref.resolved.read_text(), "right")


# --------------------------------------------------------------------------- #
class TestTree(_Tree):
    def _mixed_tree(self):
        # good: geometry beside the model
        self.model("models", "good.osim", pelvis="p.vtp", sacrum="s.vtp",
                   femur="f.vtp")
        for n in ("p", "s", "f"):
            self.mesh("models", f"{n}.vtp")
        # not portable: resolves only from ../Geometry
        self.model("models", "sub", "warn.osim", pelvis="p.vtp", sacrum="s.vtp",
                   femur="f.vtp")
        for n in ("p", "s", "f"):
            self.mesh("models", "Geometry", f"{n}.vtp")
        # broken: the classic "moved the model" case. It has to live where no
        # ../Geometry rescues it — nesting it under models/ would have resolved
        # via the sibling Geometry folder above and quietly made this a WARN.
        self.model("models", "moved", "deeper", "broken.osim", pelvis="p.vtp",
                   sacrum="s.vtp", femur="f.vtp")

    def test_counts_and_exit_code(self):
        self._mixed_tree()
        rep = verify_tree([self.tmp / "models"])
        self.assertEqual(len(rep.models), 3)
        self.assertEqual(len(rep.broken), 1)
        self.assertEqual(len(rep.not_portable), 1)
        self.assertFalse(rep.ok())
        self.assertEqual(rep.exit_code(), 1)

    def test_strict_promotes_not_portable_to_failure(self):
        self.model("models", "sub", "warn.osim", pelvis="p.vtp", sacrum="s.vtp",
                   femur="f.vtp")
        for n in ("p", "s", "f"):
            self.mesh("models", "Geometry", f"{n}.vtp")
        self.assertTrue(verify_tree([self.tmp / "models"]).ok())
        self.assertFalse(verify_tree([self.tmp / "models"], strict=True).ok())

    def test_unreadable_model_is_reported_not_raised(self):
        bad = self.tmp / "models" / "corrupt.osim"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("<OpenSimDocument><Model>", encoding="utf-8")
        rep = verify_tree([self.tmp / "models"])
        self.assertEqual(len(rep.broken), 1)
        self.assertIn("parse error", rep.models[0].error)
        self.assertFalse(rep.ok())

    def test_text_report_names_the_broken_model_and_the_consequence(self):
        self._mixed_tree()
        text = format_text(verify_tree([self.tmp / "models"]))
        self.assertIn("BROKEN", text)
        self.assertIn("broken.osim", text)
        self.assertIn("NO BONES", text)

    def test_json_round_trip(self):
        self._mixed_tree()
        d = verify_tree([self.tmp / "models"]).to_dict()
        again = json.loads(json.dumps(d))
        self.assertEqual(again["n_broken"], 1)
        self.assertFalse(again["ok"])

    def test_a_repaired_tree_is_seen_on_the_next_run(self):
        """The directory index must not outlive a verification run.

        Directories are listed once per run for speed. Someone runs the check,
        copies the missing meshes in, and runs it again in the same process —
        the GUI and the test suite both do exactly that — and a cached listing
        would keep reporting the repaired tree as broken.
        """
        self.model("models", "m.osim", pelvis="p.vtp", sacrum="s.vtp", femur="f.vtp")
        self.assertFalse(verify_tree([self.tmp / "models"]).ok())
        for n in ("p", "s", "f"):
            self.mesh("models", f"{n}.vtp")
        self.assertTrue(verify_tree([self.tmp / "models"]).ok())
        self.assertTrue(verify_model(self.tmp / "models" / "m.osim").ok())

    def test_no_models_found_is_not_a_failure(self):
        (self.tmp / "empty").mkdir()
        rep = verify_tree([self.tmp / "empty"])
        self.assertEqual(rep.models, [])
        self.assertTrue(rep.ok())
        self.assertIn("no .osim files found", format_text(rep))


# --------------------------------------------------------------------------- #
class TestCli(_Tree):
    def test_exit_codes(self):
        self.model("models", "broken.osim", pelvis="p.vtp", sacrum="s.vtp",
                   femur="f.vtp")
        self.assertEqual(cli_main(["--verify", "-q", str(self.tmp / "models")]), 1)
        for n in ("p", "s", "f"):
            self.mesh("models", f"{n}.vtp")
        self.assertEqual(cli_main(["--verify", "-q", str(self.tmp / "models")]), 0)

    def test_json_file_is_written(self):
        self.model("models", "m.osim", pelvis="p.vtp", sacrum="s.vtp", femur="f.vtp")
        out = self.tmp / "out" / "geometry.json"
        cli_main(["--verify", "-q", "--json", str(out), str(self.tmp / "models")])
        self.assertTrue(out.is_file())
        self.assertEqual(json.loads(out.read_text())["n_broken"], 1)

    def test_default_roots_come_from_the_project(self):
        self.model("models", "m.osim", pelvis="p.vtp", sacrum="s.vtp", femur="f.vtp")
        for n in ("p", "s", "f"):
            self.mesh("models", f"{n}.vtp")
        self.assertEqual(cli_main(["--verify", "-q", "--project", str(self.tmp)]), 0)


# --------------------------------------------------------------------------- #
class TestRunPathWarning(_Tree):
    """The warn-level check wired into ``Analyse.load_model``.

    Skips where the full analysis stack cannot import (the Linux bridge VM has
    no scipy/customtkinter/opensim); it runs on any machine that can actually
    solve, which is where the wiring matters.
    """

    def setUp(self):
        super().setUp()
        try:
            from bioscout.utils import analysis as _a
        except Exception as exc:                      # pragma: no cover
            self.skipTest(f"bioscout.utils.analysis unavailable here: {exc}")
        self._a = _a
        _a._GEOMETRY_CHECKED.clear()
        self.addCleanup(_a._GEOMETRY_CHECKED.clear)

    def _broken(self):
        return self.model("models", "s021.osim", pelvis="p.vtp", sacrum="s.vtp",
                          femur="f.vtp")

    def test_warns_once_and_keeps_the_verdict(self):
        m = self._broken()
        self.assertFalse(self._a.warn_if_geometry_unresolved(m))
        # second call must be silent but must NOT flip the answer to "clean"
        self.assertFalse(self._a.warn_if_geometry_unresolved(m))

    def test_clean_model_is_quiet(self):
        self.model("models", "ok.osim", pelvis="p.vtp", sacrum="s.vtp", femur="f.vtp")
        for n in ("p", "s", "f"):
            self.mesh("models", f"{n}.vtp")
        self.assertTrue(self._a.warn_if_geometry_unresolved(self.tmp / "models" / "ok.osim"))

    def test_never_raises_on_a_bad_path(self):
        self.assertTrue(self._a.warn_if_geometry_unresolved(self.tmp / "nope.osim"))
        self.assertTrue(self._a.warn_if_geometry_unresolved(""))

    def test_a_model_with_no_geometry_is_not_warned_about(self):
        m = self.tmp / "bare.osim"
        m.write_text(NO_GEOMETRY_MODEL, encoding="utf-8")
        self.assertTrue(self._a.warn_if_geometry_unresolved(m))


if __name__ == "__main__":
    unittest.main(verbosity=2)
