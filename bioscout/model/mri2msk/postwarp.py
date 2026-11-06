"""Post-Warp pipeline on a BioScout session.

    <participant>/<session>/             e.g. TD13/session1
        session.yaml                     subject, session, body_mass, static_trial,
                                         trials, iterations: {mri_lernagopal: ...}
        1_c3dfiles/<trial>.c3d           raw captures (BioScout convention)
        2_experimental/<trial>/          exported TRC / GRF / EMG      (step 0)
        3_iterations/mri_lernagopal/
            <subject>_mri_scaled.osim    our scaled model               (step 1)
            <trial>/external_biomechanics/joint_angles.mot, inverse_dynamics.sto
                    static_optimisation/*StaticOptimization_force.sto
                    joint_contact_forces/output_so.sto, contributions_so.sto/.png

Steps 0 and 2-6 are BioScout's own (``Session.export`` and the per-trial
``run_ik / run_id / run_so / run_jra / run_jra_contributions``), so results are
identical to a BioScout run. Step 1 (scaling) is MRI2MSK-specific: the warped
(MRI) segments keep scale 1, only feet/torso/arms are scaled from markers
(template ``templates/scale_setup_unwarped_segments.xml``). The iteration
declares the result as ``model_scaled`` without ``model_generic``, so BioScout
uses it as given and never rescales it.

The iteration name contains "lernagopal" on purpose: BioScout picks the knee
contact-force columns from the iteration folder name.
"""
from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

PKG = Path(__file__).resolve().parent
SCALE_TEMPLATE = PKG / "templates" / "scale_setup_unwarped_segments.xml"
ITERATION = "mri_lernagopal"
POST_STEPS = ("export", "scale", "ik", "id", "so", "jra", "jcf")
TRIAL_STEPS = ("ik", "id", "so", "jra", "jcf")
POST_LABELS = {"export": "0  Export C3D (BioScout)", "scale": "1  Scale unwarped segments",
               "ik": "2  Inverse kinematics", "id": "3  Inverse dynamics", "so": "4  Static optimisation",
               "jra": "5  Joint reaction analysis", "jcf": "6  JCF muscle contributions"}

os.environ.setdefault("BIOSCOUT_OPEN_LOG", "0")   # our console shows the output


# =========================================================================== discovery
def latest_warped_model(participant_folder: Path) -> Path | None:
    w = Path(participant_folder) / "warpedModel"
    for pat in ("*_MKA.osim", "*_massCentersCorrected.osim", "*_torsionCorrected.osim", "warpedModel.osim"):
        hits = sorted(w.glob(pat)) if w.is_dir() else []
        if hits:
            return hits[-1]
    return None


def find_sessions(participant_folder: Path) -> list[Path]:
    """Sub-folders that look like BioScout sessions (session.yaml or 1_c3dfiles)."""
    p = Path(participant_folder)
    if not p.is_dir():
        return []
    return sorted(d for d in p.iterdir() if d.is_dir() and
                  ((d / "session.yaml").is_file() or (d / "1_c3dfiles").is_dir() or (d / "c3dfiles").is_dir()))


def c3d_dir(session_dir: Path) -> Path:
    for n in ("1_c3dfiles", "c3dfiles"):
        if (Path(session_dir) / n).is_dir():
            return Path(session_dir) / n
    return Path(session_dir) / "1_c3dfiles"


def trc_time_range(trc: Path) -> tuple[float, float]:
    t = []
    for line in Path(trc).read_text(errors="ignore").splitlines()[5:]:
        parts = line.split("\t")
        if len(parts) > 1:
            try:
                t.append(float(parts[1]))
            except ValueError:
                pass
    return (t[0], t[-1]) if t else (0.0, 0.0)


# =========================================================================== body mass
def c3d_body_mass(c3d_file: Path) -> float | None:
    """PROCESSING:BODYMASS (Vicon/Nexus) from a C3D file, if present."""
    try:
        import c3d
        with open(c3d_file, "rb") as fh:
            r = c3d.Reader(fh)
            for gname in ("PROCESSING", "SUBJECTS", "SUBJECT"):
                g = r.get(gname)
                if g is None:
                    continue
                for pname in ("BODYMASS", "Bodymass", "MASS", "WEIGHT"):
                    p = g.get(pname)
                    if p is not None:
                        v = float(p.float_value)
                        if 1 < v < 400:
                            return v
    except Exception:  # noqa: BLE001
        return None
    return None


def spreadsheet_body_mass(participant_folder: Path, participant_id: str | None = None):
    """('Weight (kg)', file) for the participant ID from an .xlsx/.csv in the
    participant folder or up to two parents (e.g. 'Anthroprometrische Daten.xlsx')."""
    import pandas as pd
    p = Path(participant_folder)
    pid = (participant_id or p.name).strip().lower()
    for d in (p, p.parent, p.parent.parent):
        for f in sorted(d.glob("*.xlsx")) + sorted(d.glob("*.csv")):
            if f.name.startswith("~$"):
                continue
            try:
                df = pd.read_excel(f) if f.suffix == ".xlsx" else pd.read_csv(f)
            except Exception:  # noqa: BLE001
                continue
            wcol = next((c for c in df.columns if str(c).lower().startswith(("weight", "mass", "gewicht"))), None)
            if wcol is None:
                continue
            for c in df.columns:
                hit = df[df[c].astype(str).str.strip().str.lower() == pid]
                if len(hit):
                    try:
                        return float(hit.iloc[0][wcol]), f
                    except (TypeError, ValueError):
                        pass
    return None


def detect_body_mass(participant_folder: Path, session_dir: Path | None = None, log=print) -> float | None:
    """Static C3D PROCESSING:BODYMASS first, then a participant spreadsheet."""
    p = Path(participant_folder)
    c3d_mass = None
    for root in ([Path(session_dir)] if session_dir else []) + [p]:
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*.c3d")):
            if "static" in f.stem.lower():
                c3d_mass = c3d_body_mass(f)
                if c3d_mass:
                    log(f"[mass] {c3d_mass:g} kg from {f.name} (PROCESSING:BODYMASS)")
                    break
        if c3d_mass:
            break
    sheet = spreadsheet_body_mass(p)
    if sheet:
        log(f"[mass] {sheet[0]:g} kg from {sheet[1].name}")
    if c3d_mass and sheet and abs(c3d_mass - sheet[0]) > 0.5:
        log(f"[mass] WARNING: C3D ({c3d_mass:g} kg) and spreadsheet ({sheet[0]:g} kg) differ - using the "
            f"C3D value; edit the Mass field if the spreadsheet is right.")
    return c3d_mass or (sheet[0] if sheet else None)


# =========================================================================== session
class PostWarpSession:
    def __init__(self, session_dir, participant_folder, warped_model=None, mass=None,
                 marker_placer=True, log=print):
        self.dir = Path(session_dir)
        self.participant = Path(participant_folder)
        self.warped_model = Path(warped_model) if warped_model else None
        self.mass = mass
        self.marker_placer = marker_placer
        self.log = log
        self._s = None

    # ------------------------------------------------------------ paths
    @property
    def yaml(self) -> Path:
        return self.dir / "session.yaml"

    @property
    def iter_dir(self) -> Path:
        return self.dir / "3_iterations" / ITERATION

    @property
    def scaled_model(self) -> Path:
        return self.iter_dir / f"{self.participant.name}_mri_scaled.osim"

    def exists(self) -> bool:
        return self.yaml.is_file()

    def read_yaml(self) -> dict:
        import yaml
        if not self.yaml.is_file():
            return {}
        return yaml.safe_load(self.yaml.read_text()) or {}

    def write_yaml(self, d: dict):
        import yaml
        self.yaml.write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True))

    def c3d_files(self) -> list[Path]:
        d = c3d_dir(self.dir)
        return sorted(d.glob("*.c3d")) if d.is_dir() else []

    def static_trial(self) -> str | None:
        y = self.read_yaml()
        if y.get("static_trial"):
            return str(y["static_trial"])
        return next((f.stem for f in self.c3d_files() if f.stem.lower().startswith("static")), None)

    def trials(self) -> list[str]:
        """Dynamic trials (session.yaml order, else the c3d files), static excluded."""
        y = self.read_yaml()
        st = self.static_trial()
        tri = y.get("trials") or {}
        names = list(tri.keys()) or [f.stem for f in self.c3d_files()]
        return [n for n in names if n != st and str((tri.get(n) or {}).get("type", "")).lower() != "static"]

    def static_trc(self) -> Path | None:
        st = self.static_trial()
        p = self.dir / "2_experimental" / st / "marker_experimental.trc" if st else None
        return p if p and p.is_file() else None

    # ------------------------------------------------------------ create / update
    def create(self, c3d_sources: list[Path] | None = None) -> Path:
        """Make the session folder + session.yaml (BioScout scaffold) + MRI iteration."""
        try:                                   # BioScout 3.x
            from bioscout.session import scaffold_session_yaml
        except ImportError:                    # BioScout 2.x / git checkout
            from bioscout.utils.session import scaffold_session_yaml
        d = c3d_dir(self.dir)
        d.mkdir(parents=True, exist_ok=True)
        for src in c3d_sources or []:
            shutil.copy2(src, d / Path(src).name)
        if not self.c3d_files():
            raise FileNotFoundError(f"No .c3d files in {d} - add the captures first.")
        path = scaffold_session_yaml(str(self.dir), body_mass=self.mass, static_trial=None, overwrite=False)
        self.log(f"[session] {'created' if path else 'kept existing'} {self.yaml}")
        self.update_yaml()
        return self.yaml

    def update_yaml(self):
        """Ensure project_dir, body_mass and the MRI iteration (model_scaled, no rescaling)."""
        y = self.read_yaml()
        y.setdefault("subject", self.participant.name)
        y.setdefault("session", self.dir.name)
        y["project_dir"] = ".."                       # participant folder holds logs / results
        if self.mass:
            y["body_mass"] = float(self.mass)
        st = self.static_trial()
        tri = y.get("trials") or {}
        for f in self.c3d_files():
            tri.setdefault(f.stem, {})
        if st:
            y["static_trial"] = st
            tri[st] = {**(tri.get(st) or {}), "type": "static"}
        y["trials"] = tri
        its = y.get("iterations") or {}
        it = its.get(ITERATION) or {}
        it.update({"model_scaled": str(self.scaled_model.resolve()), "muscle_opt": False,
                   "label": "MRI personalised (MRI2MSK)"})
        it.pop("model_generic", None)
        if self.mass:
            it["body_mass"] = float(self.mass)
        its[ITERATION] = it
        y["iterations"] = its
        self.write_yaml(y)

    # ------------------------------------------------------------ BioScout objects
    def session(self):
        if self._s is None:
            from bioscout import Session
            cwd = os.getcwd()
            try:
                try:                     # BioScout 3.x
                    self._s = Session(str(self.dir), project_dir=str(self.participant))
                except TypeError:        # BioScout 2.x / git checkout
                    self._s = Session.open(str(self.dir), project_dir=str(self.participant))
            finally:
                os.chdir(cwd)
        return self._s

    def iteration(self):
        return self.session().iteration(ITERATION)

    # ------------------------------------------------------------ steps
    def run_export(self, replace=False):
        self.update_yaml()
        self._s = None
        cwd = os.getcwd()
        try:
            self.session().export(replace=replace)
            st = self.static_trial()
            if st and not self.static_trc():          # BioScout skips static trials by default
                try:
                    self.session().export(trials=[st], replace=replace)
                except Exception as e:  # noqa: BLE001
                    self.log(f"[export] BioScout static export failed ({e}); using OpenSim C3D adapter")
        finally:
            os.chdir(cwd)
        if self.static_trial() and not self.static_trc():
            self._export_static_trc()
        if self.mass:   # BioScout may write a GRF-weighed mass; keep the one shown in the GUI
            self.update_yaml()

    def _export_static_trc(self):
        """Static C3D -> 2_experimental/<static>/marker_experimental.trc (OpenSim, mm)."""
        import opensim as osim
        st = self.static_trial()
        src = next((f for f in self.c3d_files() if f.stem == st), None)
        if src is None:
            raise FileNotFoundError(f"static C3D '{st}' not in {c3d_dir(self.dir)}")
        out = self.dir / "2_experimental" / st / "marker_experimental.trc"
        out.parent.mkdir(parents=True, exist_ok=True)
        ad = osim.C3DFileAdapter()
        tables = ad.read(str(src))
        markers = ad.getMarkersTable(tables) if hasattr(ad, "getMarkersTable") else tables["markers"]
        osim.TRCFileAdapter().write(markers, str(out))
        self.log(f"[export] static TRC written: {out}")
        return out

    def run_scale(self) -> Path:
        """ScaleTool: measurement scaling for unwarped segments, scale 1 for warped ones."""
        import opensim as osim
        if not self.warped_model or not self.warped_model.is_file():
            raise FileNotFoundError("Warped model not set or not found.")
        trc = self.static_trc()
        if trc is None and self.static_trial():
            trc = self._export_static_trc()      # export the static C3D on demand
        if trc is None:
            raise FileNotFoundError("Static trial not exported yet - run step 0 (Export C3D).")
        if not self.mass:
            raise ValueError("Participant mass (kg) is required for scaling.")
        out = self.scaled_model
        out.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.parse(SCALE_TEMPLATE)
        st = tree.getroot().find("ScaleTool")
        st.set("name", self.participant.name)
        t0, t1 = trc_time_range(trc)
        tr = f"{t0} {min(t1, t0 + 0.5)}"
        st.find("mass").text = str(self.mass)
        st.find("GenericModelMaker/model_file").text = str(self.warped_model.resolve())
        st.find("GenericModelMaker/marker_set_file").text = "Unassigned"
        shutil.copyfile(trc, out.parent / "static.trc")       # OpenSim resolves these next to the setup
        ms = st.find("ModelScaler")
        ms.find("marker_file").text = "static.trc"
        ms.find("time_range").text = tr
        ms.find("output_model_file").text = out.name
        ms.find("output_scale_file").text = "scale_factors.xml"
        mp = st.find("MarkerPlacer")
        mp.find("apply").text = "true" if self.marker_placer else "false"
        mp.find("marker_file").text = "static.trc"
        mp.find("time_range").text = tr
        mp.find("output_model_file").text = out.name
        mp.find("output_motion_file").text = "static_pose.mot"
        mp.find("output_marker_file").text = "static_markers_placed.xml"
        setup = out.parent / "scale_setup_mri2msk.xml"
        tree.write(setup, encoding="utf-8", xml_declaration=True)
        self.log(f"[scale] setup -> {setup}")
        if not osim.ScaleTool(str(setup)).run():
            raise RuntimeError("OpenSim ScaleTool failed - see the console.")
        self.update_yaml()
        self._s = None
        cwd = os.getcwd()
        try:   # BioScout: no model_generic -> nothing to scale, only writes its SO model copy
            self.iteration().scale_model()
        except Exception as e:  # noqa: BLE001
            self.log(f"[scale] note: BioScout scale_model step skipped ({e})")
        finally:
            os.chdir(cwd)
        self.log(f"[scale] scaled model -> {out}")
        return out

    def run_trial(self, step: str, trial: str, replace=True):
        cwd = os.getcwd()
        try:
            t = self.iteration().trial(trial)
            if step == "ik":
                t.run_ik(replace=replace)
            elif step == "id":
                t.run_id(replace=replace)
            elif step == "so":
                t.run_so(replace=replace)
            elif step == "jra":
                t.run_jra(replace=replace)
            elif step == "jcf":
                out = t.run_jra_contributions(forces_type="so", replace=replace)
                df = (out or {}).get("so") if isinstance(out, dict) else None
                if df is not None and hasattr(df, "groupby"):
                    self.log(f"[{trial}] {summary_peaks(df, self.mass)}")
            else:
                raise ValueError(step)
        finally:
            os.chdir(cwd)

    # ------------------------------------------------------------ status
    def trial_dir(self, trial: str) -> Path:
        return self.iter_dir / trial

    def exported(self, trial: str) -> bool:
        return (self.dir / "2_experimental" / trial / "marker_experimental.trc").is_file()

    def trial_status(self, trial: str) -> dict[str, bool]:
        d = self.trial_dir(trial)
        eb, so, jcf = d / "external_biomechanics", d / "static_optimisation", d / "joint_contact_forces"
        return {"export": self.exported(trial),
                "ik": (eb / "joint_angles.mot").is_file(),
                "id": (eb / "inverse_dynamics.sto").is_file(),
                "so": so.is_dir() and any(so.glob("*StaticOptimization_force.sto")),
                "jra": (jcf / "output_so.sto").is_file(),
                "jcf": (jcf / "contributions_so.sto").is_file() or (jcf / "contributions_so.png").is_file()}


def bioscout_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("bioscout") is not None


def summary_peaks(df, mass=None) -> str:
    """Peak total JCF per joint (N and BW) from a contributions DataFrame or csv."""
    import pandas as pd
    if not hasattr(df, "groupby"):
        df = pd.read_csv(df)
    bw = float(mass) * 9.81 if mass else None
    parts = []
    for j, g in df.groupby("joint"):
        peak = g.groupby("time")["total_mag"].first().max()
        parts.append(f"{j}: {peak:.0f} N" + (f" ({peak / bw:.2f} BW)" if bw else ""))
    return "peak JCF  " + "; ".join(parts)
