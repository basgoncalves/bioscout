# Changelog

All notable changes to BioScout are documented here.

## [1.2.0] — 2026-06-14

Big release: a full **energetics** path, a **`--summary`** reporting module, an
EMG time‑base fix, and a first **basketball shot‑analysis** prototype
(computer‑vision → kinematics → muscle forces).

### Added — OpenSim energetics
- `utils.openSim.run_energetics`: attaches an **Umberger (2010)** metabolic‑energy
  probe set to the scaled model and runs a `ProbeReporter`
  (`energetics_ProbeReporter_probes.sto`).
- `Analyse.run_energetics` wrapper and an `enable_energetics` switch wired into
  batch mode (`bioscout/__main__.py`).
- Batch mode now **fails fast with a clear message** when OpenSim is not
  importable, instead of erroring on every step.

### Added — `python -m bioscout --summary`
- New `utils/summary.py`: per‑trial **and** overall (grouped by movement type)
  kinematics / kinetics / muscle summaries.
- One **column per joint** with left + right overlaid (left = red, right = blue).
- Rows: joint **angle** (with per‑joint, per‑side **marker‑error** box), **EMG**,
  joint **moment** vs summed muscle moment, **moment arms**, **muscle forces**,
  **activations** (EMG shaded behind), **energetics** — empty panels where data
  is absent. Per‑muscle rows show **agonist (+MA) / antagonist (−MA)** means.
- EMG uses `emg_filtered_normalised.mot` (falls back to filtered, then raw).
- CLI: optional settings path (`--summary "<proj>/settings.py"`), `-s` (player),
  `-t` (single trial), `-overall`. New `SummarySettings` class in `settings.py`.

### Fixed — EMG processing
- `Analyse.run_emg_filter` now derives the EMG **sampling rate from the data's own
  time column** (true analog rate) instead of a fixed setting, and no longer
  overwrites a valid time vector — fixes degenerate (all‑zero) timestamps that
  flattened the EMG in the summary.

### Added — Basketball shot analysis (prototype) — `python -m bioscout --shots VIDEO`
- 2‑D pose via BioScout's MediaPipe tracker; per‑shot segmentation.
- Three detection paths: pose **ball‑flight**, and an **avishah3‑style hoop**
  method (ball + hoop → up/down/through‑rim **attempt + make** scoring) with a
  **YOLO** (`--yolo-model`) detector or an HSV + manual `--hoop CX,CY,W,H` fallback.
  (after Shah, *AI Basketball Shot Detection Tracker*.)
- Per‑shot **kinematics on a smooth 0–100 %** axis (1000 pts, configurable).
- **Kinematics‑only muscle‑force surrogate** (`models/kinematics_only_model.pkl`,
  numpy MLP) — *low fidelity, see limitations.*
- **Assisted made/missed tagging** (`shots.csv`), release thumbnails, annotated
  **score frames** (rim + predicted path + IN/OUT), and a combined per‑shot
  **card**: release (stick figure + joint angles + **release angle**) | shot path.
- `--fps`, `--min-gap`, `--n-points`, `--hoop-side`, `--shooting-hand` CLI flags.

![Shot analysis card](bioscout/utils/shot_analysis_card.png)

*Per‑shot card: stick figure + joint/release angles on the left, ball path and
IN/OUT on the right (stick figure shown is a placeholder; a real run uses MediaPipe).*

### Known limitations / still missing
- **Shot detection needs ~30–60 fps.** At 5 fps the ball crosses the rim in ~1
  frame, so the hoop method misses rim passes; use a high‑fps clip.
- **Ball identification needs YOLO.** HSV alone can't isolate the game ball from
  the ball rack / court logos; a trained ball+hoop model is required for robust,
  fully‑automatic detection.
- **Muscle forces from video are low fidelity.** A kinematics‑only model can't
  recover absolute force (cross‑subject R² is poor — force scales with subject
  strength/size). Needs richer inputs (moments/EMG) or per‑athlete calibration.
- **2‑D joint angles** are image‑plane only — valid when the shooter is roughly
  side‑on to the camera; wide/distant broadcast footage degrades pose badly.
- **Energetics probe API** not validated across all OpenSim versions; **CEINMS**
  depends on external executables being installed.
- Hoop is static/manual or per‑frame YOLO; no automatic rim auto‑detection yet.

## [1.1.x] — earlier
- PyPI packaging, image URL fixes, batch pipeline, GUI, OpenSim C3D→CEINMS pipeline.
