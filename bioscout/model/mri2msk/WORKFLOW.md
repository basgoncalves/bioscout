# MRI2MSK (bioscout) – step-by-step workflow

How to go from MRI bone segmentations to a personalised OpenSim model with the
Python GUI. Paths assume the project lives in `C:\Users\Basilio\Desktop\WilliOSC`.

---

## 0. One-time setup

1. **Create the conda environment** (Git Bash or Anaconda Prompt):

   ```bash
   conda activate msk311                          # or any env with opensim + bioscout
   pip install -e "C:/Git/bioscout[mri2msk]"      # trimesh, fast-simplification, openpyxl, customtkinter
   ```

2. **Check it works:**

   ```bash
   python -c "import opensim, trimesh, fast_simplification; print(opensim.__version__)"
   ```

3. **Install OpenSim Creator** (0.7.3 or newer) from <https://opensimcreator.com>.
   The GUI finds it in `C:\Program Files\OpenSimCreator\bin\osc.exe`.

> If `conda activate` fails in Git Bash, run `eval "$(conda shell.bash hook)"`
> first, or use the Anaconda Prompt.

---

## 1. Prepare the participant folder

Create one folder per participant, e.g. `WilliOSC\TD13`, containing:

```
TD13/
├── stls/
│   ├── *pelvis*.stl          required
│   ├── *femur_l*.stl         required  (l_femur also accepted)
│   ├── *femur_r*.stl         required
│   ├── *tibia_l*.stl         required  (l_tibia also accepted)
│   ├── *tibia_r*.stl         required
│   └── skin/                 optional: *left_thigh*, *right_thigh*,
│                             *left_shank*, *right_shank*, *pelvis*.stl
```

- STLs must be in **millimetres** (normal MRI segmentation output).
- Exactly **one** file per bone in `stls/` (besides files the pipeline creates).

---

## 2. Start the GUI

```bash
conda activate msk311
bioscout model mri2msk gui
```

In the **Configuration** panel:

1. **Participant folder → Browse**, select e.g. `TD13`.
   The participant name fills in automatically.
2. **Base model** – defaults to
   `BaseModel_Lernagopal/LernagopalLaiUhlrich2025_CGM2.osim`; change if needed.
3. Tick **Include skin** only if you have a `stls/skin/` folder.
4. Leave **Set mechanical knee axis** ticked unless you don't want step 8.
5. Optional: **Save Config** → writes `warpingConfig.json` in the participant
   folder; it is loaded automatically next time you select that folder.

Each step's status shows *Not started / Ready / Waiting for user… / Done ✓*.
A step only unlocks when the steps before it are done. Progress is detected from
the files on disk, so you can close the GUI and continue later.

---

## 3. Workflow steps

### Step 1 – Rescale & align bones  *(automatic)*

Click **Run**. For each bone it finds the joint coordinate system (Python port
of STAPLE), aligns the bone to the OpenSim frame and scales it to the base bone.

Creates in `stls/`:
- `*_resizedToOpenSim_inOpenSimCS.stl` (one per bone)
- `preAligningToOpenSim.json`

Takes ~10 s. The log lists one resize factor per bone.

### Step 2 – Align skin & add to base model  *(optional, automatic)*

Only with **Include skin**. Click **Run**. Transforms the skin meshes with the
bone alignment and attaches them to the base model for visual reference.

Creates `stls/skin/skin_*.stl` and `BaseModelWithSkin/<name>_unscaled_withSkin.osim`.
**View Model** opens it in OpenSim Creator.

### Step 3 – Create landmarks  *(automatic or manual, then check in OpenSim Creator)*

Click **Helper**. This copies all meshes into `landmarks/meshes/` as
`base_<bone>.stl` / `participant_<bone>.stl` and opens the
**Mesh Warper helper** window.

#### Option A – automatic landmarks (recommended start)

1. In the **# auto landmarks** column set how many landmarks you want per bone
   (default 25; use **set all to → Apply** to change all at once). More points
   give a tighter warp but take longer; 20–30 per bone is a good range.
2. Click **Auto-generate landmarks**. Per bone (~25 s each) the GUI spreads the
   chosen number of points evenly over the base bone, fits the base bone onto
   the participant bone (Coherent Point Drift: affine, then non-rigid) and
   moves the points along. It writes all 10 CSVs to `landmarks/`.
3. **Check them** in OpenSim Creator (**Open OpenSim Creator**): per bone
   **+ → Mesh Warping**, import the two meshes (Source/Destination path
   buttons), then import the matching CSVs as landmarks. In the *Result* pane
   tick *warp* + *overlay destination mesh*. Move any point that sits badly and
   re-export the CSV under the same name.

On `exampleParticipant` the automatic points land on average **5–9 mm** from
the manually placed ones (`python C:/Git/bioscout/bioscout/tests/mri2msk/validate_landmarks.py`). The manual
points have click error too, but **always check the result visually** before
warping.

#### Option B – manual landmarks

For each of the 5 bones (pelvis, femur_l, femur_r, tibia_l, tibia_r):

1. In OpenSim Creator: **+ → Mesh Warping** (new tab).
2. Helper: **Source path** → OSC *Source Mesh → import* → paste (Ctrl+V) → open.
3. Helper: **Destination path** → OSC *Destination Mesh → import* → paste → open.
4. Click matching anatomical landmarks on both meshes (e.g. condyle peaks,
   trochanter, malleoli, ASIS/PSIS), same number on both sides. In the
   *Result* pane tick *scale / warp / overlay destination mesh* to check live.
5. Helper: **Source CSV path** → OSC *Source Mesh → export → landmarks to CSV*
   → paste as file name → save.
6. Helper: **Destination CSV path** → same for *Destination Mesh*.
7. The helper row turns **✓ saved**.

When all 10 CSVs exist in `landmarks/`, step 3 turns **Done ✓** automatically.

### Step 4 – Create warp setup  *(automatic)*

Click **Run**. Fills the OpenSim Creator warp template with the scale factors,
landmark file paths and marker lists.

Creates `warp_setup.xml` in the participant folder and the empty folders
`warpedModel/` and `warpedModel/warpedGeometry/`.

### Step 5 – Warp the model  *(automatic)*

Click **Run**. The Python Model Warper applies `warp_setup.xml` to the model
(the skin model from step 2 if skin is on – the `_markersAdjusted` version if
present – otherwise the base model). It warps bone meshes, joint frames,
muscle points, markers and wrap cylinders exactly like the OpenSim Creator
Model Warper (validated: < 0.001 mm / 0.003° difference on `exampleParticipant`).

Creates `warpedModel/warpedModel.osim` and `warpedModel/warpedGeometry/*.obj`
in ~5 s. **View Model** opens it in OpenSim Creator for a visual check.

> The manual route still works: warp in OpenSim Creator's Model Warper and save
> as `warpedModel/warpedModel.osim` (warped geometry into
> `warpedModel/warpedGeometry`) – the GUI detects it the same way.

### Step 6 – Replace skin in warped model  *(optional, automatic)*

Only with **Include skin**. Click **Run**. Swaps the scaled skin meshes for the
participant's real skin surfaces.

Creates `warpedModel/warpedModel_skinUpd.osim`.

### Step 7 – Correct torsion & mass centres  *(automatic)*

Click **Run**. Measures femoral/tibial torsion in base vs warped model and
rotates bone meshes, muscle points, wrap objects and markers back; fixes hip,
knee and ankle offsets; sets mass centres from the warped *MassCenter* markers;
scales the patellofemoral and knee splines.

Creates `warpedModel/…_torsionCorrected.osim` and
`warpedModel/…_torsionCorrected_massCentersCorrected.osim`, plus `*_rotated.obj`
meshes in `warpedGeometry/`. **View Model** opens the corrected model.

### Step 8 – Set mechanical knee axis  *(optional, automatic + confirm)*

Click **Run**. A window shows the pelvis/femur/tibia frames in 3D and the
left/right ab-/adduction angles.

- **Continue** → writes `…_massCentersCorrected_MKA.osim`.
- **Cancel** → nothing is written; the suggested values go to the log.

**Run all automatic steps up to the next user step** runs consecutive automatic
steps in one click and stops at step 3 or step 8.

---

## 4. Output overview

```
TD13/
├── stls/preAligningToOpenSim.json              step 1
├── stls/*_resizedToOpenSim_inOpenSimCS.stl     step 1
├── BaseModelWithSkin/                          step 2 (optional)
├── landmarks/meshes/*.stl                      step 3 helper
├── landmarks/base_*.csv, participant_*.csv     step 3 (auto-generated and/or you)
├── warp_setup.xml                              step 4
└── warpedModel/
    ├── warpedGeometry/                         step 5 (you) + step 7
    ├── warpedModel.osim                        step 5 (you)
    ├── warpedModel_skinUpd.osim                step 6 (optional)
    ├── …_torsionCorrected.osim                 step 7
    ├── …_massCentersCorrected.osim             step 7  ← use this
    └── …_massCentersCorrected_MKA.osim         step 8  ← or this, if step 8 was run
```

---

## 5. Post-Warp Pipeline  *(BioScout session: export → scale → IK → ID → SO → JRA → JCF contributions)*

The **Post-Warp Pipeline** page (left sidebar) runs the analysis on a
**BioScout session**, with BioScout's own functions, so results match a
BioScout run. One-time install in the environment:

```bash
pip install bioscout customtkinter
```

### Session layout (BioScout convention)

```
TD13/session1/
  1_c3dfiles/static01.c3d, gait03.c3d, gait05.c3d   ← your captures
  session.yaml                                       ← created by "Create session"
  2_experimental/<trial>/marker_experimental.trc, grf.mot, GRF.xml, emg…   ← step 0
  3_iterations/mri_lernagopal/
      TD13_mri_scaled.osim                           ← step 1
      <trial>/external_biomechanics/joint_angles.mot, inverse_dynamics.sto
              static_optimisation/…StaticOptimization_force.sto
              joint_contact_forces/output_so.sto, contributions_so.sto/.png
```

`session.yaml` gets an iteration **`mri_lernagopal`** whose `model_scaled` is
the MRI2MSK scaled model and that has **no `model_generic`** – BioScout then
uses the model as given and never rescales it. (The name contains
"lernagopal" on purpose: BioScout picks the knee contact-force columns from it.)

### Steps

1. **Session folder** – *Auto-detect* (or Browse) picks `TD13/session1`.
   No session yet? Click **Create session**: it creates the folder and
   `1_c3dfiles/` (asks for the C3D files if the folder is empty) and writes
   `session.yaml` with BioScout's scaffold plus the MRI iteration.
   **Update session** re-writes mass / model / iteration in an existing yaml.
2. **Warped model** – auto-detected (`…_MKA.osim`, else `…_massCentersCorrected.osim`).
3. **Body mass** – *Auto-detect* also reads `PROCESSING:BODYMASS` from the static C3D,
   else the participant's row in a spreadsheet next to the participant folder
   (e.g. `Anthroprometrische Daten.xlsx`, column "Weight (kg)"). If both exist
   and differ, the C3D value is used and both are printed in the console.
4. **0 Export C3D** – BioScout `Session.export`: TRC, GRF, EMG (filtered,
   normalised) and movement detection for every capture.
5. **1 Scale unwarped segments** – OpenSim ScaleTool with the MRI2MSK
   template: feet, torso and arms scaled from marker distances, every warped
   segment (pelvis, femurs, tibias, condyles, plateaus, patellae) kept at 1,
   markers placed on the static trial.
6. Select trials in the table (all by default) and run **2 IK, 3 ID, 4 SO,
   5 JRA, 6 JCF contributions** – BioScout's `run_ik`, `run_id`, `run_so`,
   `run_jra`, `run_jra_contributions(forces_type="so")` – or
   **Run all steps (selected trials)**.
7. The table ticks each step per trial. **JCF contributions** opens the
   stacked contribution figure, **All plots** lists every figure BioScout made,
   **Open trial folder** opens the trial results; the console prints the peak
   hip / knee / ankle contact force per trial (N and BW).

Still MATLAB-only: muscle-path check (PhysiologicalMusclePaths) and muscle
parameter optimisation.

## 6. Command-line alternative

Every step also runs without the GUI:

```bash
BASE=../BaseModel_Lernagopal/LernagopalLaiUhlrich2025_CGM2.osim
P=../TD13
bioscout model mri2msk status --participant $P --base-model $BASE
bioscout model mri2msk 1  --participant $P --base-model $BASE
bioscout model mri2msk 3  --participant $P --base-model $BASE --n 25      # auto landmarks
#   per bone: --n pelvis=30,femur_l=25,femur_r=25,tibia_l=20,tibia_r=20
#   -> check them in OpenSim Creator before step 4
bioscout model mri2msk 4  --participant $P --base-model $BASE
bioscout model mri2msk 5  --participant $P --base-model $BASE      # warp model
bioscout model mri2msk 7a --participant $P --base-model $BASE
bioscout model mri2msk 7b --participant $P --base-model $BASE
bioscout model mri2msk 8  --participant $P --base-model $BASE --yes
bioscout model mri2msk post --participant $P --base-model $BASE --session $P/session1   # export..JCF (BioScout)
```

Validation against MATLAB / manual landmarks:

```bash
python C:/Git/bioscout/bioscout/tests/mri2msk/validate_step1.py ../MRI2MSK/exampleParticipant/stls
python C:/Git/bioscout/bioscout/tests/mri2msk/validate_landmarks.py ../MRI2MSK/exampleParticipant ../BaseModel_Lernagopal
python C:/Git/bioscout/bioscout/tests/mri2msk/validate_warp.py ../MRI2MSK/exampleParticipant
```

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `No module named trimesh` | `pip install -e "C:/Git/bioscout[mri2msk]"` |
| `No module named opensim` | activate the conda env with opensim (msk311) first |
| Step 1: *Too many … files* | Only one STL per bone in `stls/` |
| Step 1 error on one bone | Check that mesh is closed and in mm; the MATLAB Kai2014 fallbacks are not ported yet |
| Warp template "(template not found)" | Base model folder must contain the `Base_LernagopalLaiUhlrich_warping_setup_template*.xml` files |
| Step 3 never turns Done | All 10 CSVs must be directly in `landmarks/` with the helper's names |
| Auto landmark sits off the bone feature | Move it in the OSC Mesh Warper and re-export the CSV under the same name |
| Auto landmarks: warp looks distorted | Try fewer landmarks (e.g. 15–20) or fix the worst points manually |
| Auto landmarks overwrote my manual ones | The GUI asks first; keep a copy of `landmarks/` before re-running |
| Step 5 not detected | The file must be named exactly `warpedModel/warpedModel.osim` |
| Step 5: *Mesh file not found* | Base model folder needs its `Geometry/` folder next to the `.osim` |
| Post-Warp buttons greyed out | `pip install bioscout`, pick the session folder and click Create session |
| Scaling fails | Mass and static trial are required; marker names must match the model |
| OpenSim Creator does not open | Install it, or add `osc.exe` to PATH |
