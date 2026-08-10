# settings.py — the long version

Every explanatory comment that used to live in the project's
`settings.py`, extracted verbatim so the file itself can stay short.
Line numbers refer to the pre-streamline file, kept beside it as
`settings.py.pre_streamline`.

`settings.py` is per-project configuration plus a single-session runner.
The config classes (`BatchSettings`, `CEINMSSettings`, `SummarySettings`,
`PlottingSettings`, `UISettings`, `RecordingSettings`) are read by
bioscout at run time through a live `sys.modules['settings']` proxy —
see `bioscout/utils/ceinms.py`'s `_LiveSettings`.

---

### line 17

```
```
 Headless batch: pick the non-interactive matplotlib backend BEFORE anything
 imports pyplot. bioscout cannot force this itself — its GUI needs a real
 backend (FigureCanvasTkAgg) — but a batch run has no display, and an
 interactive backend allocates GUI resources per figure that are never freed.
```

### line 32

```
```
 The settings-SCHEMA version this file is written against — NOT the bioscout
 package version. check_settings_version() compares this to
 bioscout.settings.__version__ (the bundled template), so mirroring the
 package number here made that check disagree on every patch release.
```

### line 39

```
```
 False since the summarize_results.py shim was deleted: bioscout.pipeline
 .run_summary() looks for that exact filename and, not finding it, silently runs
 the PACKAGE summary (bioscout.utils.summary) instead of results.py. Run the
 real summary yourself:  python results.py   (and  python results.py --master
 for the cross-session tables). Set back to True only after pointing
 bioscout's run_summary()/summarize_results() at results.py.
```

### line 46

```
```
 scale each subject's generic model (scale -> opt -> MVIC)
```

### line 49

```
```
 Console/log verbosity:
   "detailed" — everything (default; per-trial dumps, debug listings, tool chatter)
   "minimal"  — section headers, [Success]/[skip]/[ERROR], and warnings only
   "quiet"    — errors and final summary only
```

### line 55

```
```
 ---- project paths & session (GLOBAL — single source of truth) -------------
 bioscout reads these as module-level settings.<NAME> (with a BatchSettings
 fallback), so they live here rather than inside BatchSettings.
```

### line 60

```
```
 Deliberately points at a folder that NO LONGER EXISTS. The old per-variant
 model library was archived to _archive_models_pre_2026-07/ on 2026-07-29:
 every model the pipeline uses now lives in the iteration folder
 (3_iterations/<iteration>/scaled*.osim) or in "generic models/".
 bioscout reads settings.MODELS_DIR and searches it FIRST when resolving a
 model path, so leaving it aimed at the archive would let a stale 2026-04 file
 shadow a current one. Aimed at a missing path it simply never matches —
 bioscout guards every use with os.path.exists / os.path.isdir.
 intentionally absent
```

### line 73

```
```
 ---- the ACTIVE capture ----------------------------------------------------
 The runner globs simulations/*/<SESSION>/session.yaml, so this one line picks
 subject AND session. Everything that is a property of ONE CAPTURE rather than
 of the study lives in CAPTURES below and is selected from it — see the comment
 there for why that separation matters.
 "25_03_31" = Athlete_03 | "22_07_13" = Athlete_06
```

### line 81

```
```
 ---- per-capture configuration ---------------------------------------------
 Electrode sets, plate wiring, sampling rates and trial names belong to the DAY
 THE DATA WAS COLLECTED, not to the project. Keeping them as bare module-level
 values meant switching SESSION silently carried the other athlete's EMG map and
 force-plate sign correction into the new session — wrong, and invisible in the
 output. Each key below is read exactly once, lower down, via CAPTURE[...].

 Per-ITERATION recipe (generic model, labels, colours, mvic/opt_neval, CEINMS
 a/b/g, trial windows) is NOT here — that is session.yaml's job.
```

### line 91

```
```
 -------------------------------------------------- Athlete_03 / 25_03_31
```

### line 95

```
```
 runner defaults
 the six iterations session.yaml actually defines ("gpk_optimised"
 was not one of them and had no effect)
```

### line 103

```
```
 figures / legacy batch
 Walking_02 REMOVED 2026-08-04: unusable. Static optimisation drove all
 10 reserve actuators to the 50 Nm cap in gpk, lernagopal,
 lernagopal_mri and cateli_mri, so SO could not reproduce inverse
 dynamics and the force split it returned is arbitrary.
 See qa_gate.py and things_to_fix.md.
```

### line 111

```
```
 capture hardware
 200 Hz points x 10 analog sub-frames = 2000 Hz (read from the c3d).
 The original settings.py said 1000, contradicting its own comment; this
 is only a FALLBACK (every live path derives fs from emg.mot's own time
 column), so the correction changes no result.
```

### line 117

```
```
 fs 2000 -> Nyquist 1000, plenty of margin
 Plate 1's anterior-posterior (vx) force is inverted in the raw C3D.
```

### line 120

```
```
 Channels EMG01-12 were labelled at capture; EMG13-16 came through
 unnamed and are unused. Keys are the EXPORTED emg.mot column names.
```

### line 123

```
```
 left
```

### line 129

```
```
 right
```

### line 140

```
```
 -------------------------------------------------- Athlete_06 / 22_07_13
 Loaded squats + deadlifts at 70-90 %. No walking trials, no MRI variant
 (alex_mrts/athlete_06 has 20 landmarks against the 107 the TPS template
 needs — see mri/README.md). body_mass 69.0 kg lives in session.yaml.
```

### line 151

```
```
 No walking here, so the Athlete_03 calibration names match nothing and
 bioscout's _resolve_calibration_trials() would fall back to "every
 trial with squat in the name" — a plausible-looking calibration on the
 wrong trials. Pinned.
```

### line 159

```
```
 fs 1000 -> Nyquist 500. 450 Hz is 0.90 of Nyquist; 400 keeps margin for
 the 4th-order Butterworth. Only affects the export-time
 emg_filtered.mot — the CEINMS envelope path uses filter_emg's own
 20-95 Hz band.
```

### line 164

```
```
 2 Kistler plates: right foot -> plate 1, left -> plate 2 (confirmed
 from the foot-marker / plate-corner geometry, and matches the original
 MATLAB GRF.xml). The AP sign was NOT verified, so nothing is flipped —
 check ground_force_1_vx against the squat's fore-aft lean on the GRF QC
 figure before trusting it.
```

### line 170

```
```
 Exported column names are Voltage_EMG<n>_* (c3d ANALOG labels
 'Voltage.EMG1_vast_lat_l' with '.' -> '_'), NOT EMG_Channels_EMG<nn>_*.
 Gluteus MAXIMUS here, not medius. NOT mapped, deliberately:
   EMG11/12 lat_dor  - no latissimus in these models, and the signal is
                       railed (rms ~2.2 V, ptp 6.5 V of a 6.5 V range)
                       even in the static trial.
   EMG13/14 add_mag  - dead. rms 0.0100 V, identical to the unused
                       EMG15/16_free (~0.0098). Mapping them would feed
                       CEINMS noise as adductor magnus excitation.
 session.yaml's emg_map carries the same 10 channels and outranks this
 (bioscout >= 2.4.1); this copy is what utils/summary.py's cross-model
 figures read, so keep the two in step.
```

### line 183

```
```
 left
```

### line 189

```
```
 right
```

### line 196

```
```
 no 107-landmark set for this athlete
```

### line 209

```
```
 ---- model/group templates -------------------------------------------------
 One template per distinct generic + scaled-name convention (NOT per subject).
 A registry row is auto-built for each simulations/<subject>/<session>/ folder
 and stamped with its group's template. Shared fields (model_so/model_ceinms
 names, static_trial, setup_folder) live here once. Scaling for THIS session's
 validation compares 5 model variants of one athlete, so each variant is a group.
```

### line 227

```
```
 GPK_generic_modWO.osim has not existed for some time -- this row
 pointed at a missing file. The model names also disagreed with
 session.yaml, which runs gpk WITHOUT the Modenese muscle-opt
 ("opt_N" absent from ceinms_model is how bioscout reads that intent).
```

### line 236

```
```
 Validated MRI/TPS model is the template itself (geometry AND muscle-tendon
 params already personalised). linear_scaling off (keep MRI segment geometry),
 marker_placer ON so markers register to the static pose (fixes IK). Muscle-opt
 is SKIPPED — the generic's OFL/TSL are kept — so CEINMS uses the plain
 marker-registered scaled.osim and SO uses it with isometric force x MVIC.
```

### line 246

```
```
 MRI (TPS-personalised bone geometry) variants of the other three generics.
 Same recipe as gpk_mri: the *_tps_Athlete_03.osim model already carries the
 subject's bone geometry, so linear_scaling is off, marker_placer is on and
 muscle-opt is skipped. Generate the models with bioscout.tps_personalise.
```

### line 262

```
```
 49-athlete backlog: add ONE default template (their shared generic) here,
 e.g. "athlete": dict(generic_model="Rajagopal2015_FAI_os4.osim", ...), and set
 default_group="athlete" below — then just drop their folders into simulations/.
```

### line 267

```
```
 Which group each subject folder belongs to (unmapped subjects use default_group;
 None = skip). For the backlog, map new athletes here or set default_group.
```

### line 287

```
```
 None = skip unmapped subjects
 only the active session
```

### line 302

```
```
 ---- session & trials ------------------------------------------------
 Paths + SESSION are module-level globals above (single source of truth);
 bioscout resolves them via settings.<NAME>. Referenced unqualified below.
 Run the walking trials first (all models) to complete the walking figures.
 Full set: ["Squat_35kg_01","Squat_35kg_02","Squat_BW_01","Squat_BW_02",
            "Walking_03"]      # the second walking trial was dropped 2026-08-04
```

### line 311

```
```
 ---- subjects --------------------------------------------------------
 Subject metadata now lives in the `Subjects` registry above; edit it there.
 Choose which to process with RUN_/SKIP_ (names or indices).
```

### line 316

```
```
 was ['Athlete_03_Cateli'], which left results.py
 and manuscript.py reporting one model variant
 e.g. ["Athlete_03_Cateli"] or [0]
```

### line 325

```
```
 session map {path: static_trial} — Project also derives this at runtime.
```

### line 328

```
```
 ---- analysis / comparison config ------------------------------------
 NOTE: the DOFs to PLOT / SUMMARISE now live in SummarySettings.dofs.
 The single processing DOF set (IK / ID / CEINMS, bilateral) is dof_list below.
```

### line 342

```
```
 Both legs defined; the muscle-group plot filters by the trial's `side`
 (walking -> one leg, squat -> both).
```

### line 367

```
```
 Time-normalise (downsample) exported inputs/results to this many frames.
 0 = native sampling. ~100 is near-lossless for kinematics/moments.
```

### line 371

```
```
 ---- batch / IK / GRF / EMG processing -------------------------------
 NOTE: generic_model moved onto each Subject (Subject.generic_model).
```

### line 384

```
```
 knee_adduction_l/r included for models with a free frontal-plane knee
 coordinate (e.g. Lerner/GPK-MRI knee). create_ceinms_model() auto-drops any
 DOF the model lacks, and any DOF no muscle spans (|moment arm| < 1e-6), so
 models without it (or with it locked) are unaffected.
```

### line 393

```
```
 Markers excluded from IK entirely (belt / noise markers). Their IK task is
 disabled so they don't pull the fit. Matched case-insensitively.
```

### line 396

```
```
 session.yaml is the single source of truth for per-trial config; do NOT
 write per-trial trial_settings.xml scratch files. Set True to restore them.
```

### line 399

```
```
 Quiet OpenSim's C++ [info]/[warning] spam (missing display-geometry meshes,
 etc.) by raising its log level. "Error" hides info+warnings but keeps errors;
 set None / "Warn" to see them again.
 "off" hides everything; "error" keeps errors; "warning" shows all
 Channel -> muscles for THIS capture (see CAPTURES at the top). Keys are the
 EXPORTED emg.mot column names, i.e. the c3d ANALOG labels with '.' and
 spaces replaced by '_' — that prefix belongs to the FILE, not to bioscout.
 session.yaml's `emg_map` outranks this for a session's trials
 (bioscout >= 2.4.1); this is the fallback and what the cross-model summary
 figures still read.
```

### line 425

```
```
 Per-plate force-sign correction for individually mis-wired plates,
 {plate_id: {axis: sign}} — a property of ONE capture, so it comes from
 CAPTURES. Applying Athlete_03's plate-1 flip to another lab session would
 silently invert a perfectly good AP force.
```

### line 431

```
```
 EMG linear-envelope filtering (applied during export). Lower the envelope
 low-pass for a smoother envelope (4 Hz suits walking/squat; raise for fast
 tasks). emg_bandpass_high_hz=None -> auto 0.9*Nyquist.
```

### line 435

```
```
 per capture: must stay clear of Nyquist
 linear-envelope lowpass; lower = smoother
 (3 Hz suits slow heavy lifts; 2.5 = even smoother)
```

### line 450

```
```
 isometric-force x factor -> model_so (*_mvicx3.00)
 Modenese muscle-opt sampling -> scaled_opt_N10.osim
 Static trial to scale FROM, per session (name of the trial folder / c3d stem).
```

### line 459

```
```
 Per-trial end-of-run validation (muscle-length/strength sweeps + literature
 overlay). This re-tracks markers frame-by-frame through the constrained model
 and is the slow, silent step that dominates wall time. Off for fast/preview
 runs; turn back on when you want the QC figures.
```

### line 465

```
```
 Model constraint-assembly tolerance used when loading models for IK/ID/MA/SO/JRA.
 Coupled-knee models (GPK/Lernagopal patella couplers) miss OpenSim's ultra-tight
 default and print "Unable to achieve required assembly error tolerance"; 1e-8 is
 physically negligible for moments/JCF and silences it.
```

### line 471

```
```
 Literature JCF overlay styling on the JRA |resultant| panels.
 shaded band opacity (0-1)
 dashed reference-line opacity (0-1)
 dashed reference-line width
```

### line 476

```
```
 ---- helpers (as static methods, not loose functions) ----------------
```

### line 491

```
```
 case-insensitive: folder names are lowercase (lernagopal, gpk, gpk_mri)
```

### line 495

```
```
 Lerner knee: gpk / gpk_mri / lernagopal (the new GPK_generic_modWO_tps
 MRI model ALSO uses the Lerner sagittal-articulation knee). cateli /
 rajagopal use the standard walker_knee.
```

### line 513

```
```
 Per capture — Athlete_03's names match nothing in a session with no
 walking trials, and bioscout then falls back to "every squat" silently.
```

### line 554

```
```
 ---- what to summarise -----------------------------------------------
 DOFs to PLOT / SUMMARISE (subset — usually the right-side dominant limb).
 The full processing DOF set (IK/ID/CEINMS, bilateral) is BatchSettings.dof_list.
 Both legs (right=blue, left=red — merged onto the same column by
 plot_kin_mom_summary) plus the pelvis DOFs.
```

### line 566

```
```
 Default leg to include in per-trial summary plots (kinematics_moments.png):
 "both" | "r" | "l". Override per trial by adding <analysis_leg>r</analysis_leg>
 to that trial's trial_settings.xml.
```

### line 570

```
```
 Reference model (name or label) that others are compared against (RMSE/R2).
```

### line 573

```
```
 Extra trials to include on top of BatchSettings.trial_list (if present on disk).
```

### line 575

```
```
 time-normalisation points for every curve
```

### line 578

```
```
 ---- output ----------------------------------------------------------
 under PROJECT_ROOT; figures go in <subdir>/figures
 "minimal" | "poster" | "journal"
```

### line 582

```
```
 write metrics_long.csv + metrics_wide.csv for JASP
```

### line 584

```
```
 ---- which figures to build ------------------------------------------
```

### line 587

```
```
 02 — kinematics + moments (+ R2/RMSE text boxes)
 02b
 04 — activations(+EMG bg)/lengths/forces + EMG R2/RMSE
 05b — joint reaction force components
 05 — catchy summary + hypothesis verdict
```

### line 593

```
```
 draw EMG as a grey filled background on activations
 R2/RMSE text boxes on kin/mom + muscle figures
```

### line 596

```
```
 ---- hypothesis (stated, and answered from the data in the poster) ---
```

### line 600

```
```
 ---- styling ---------------------------------------------------------
```

### line 629

```
```
 multiply default figure sizes by this
```

### line 631

```
```
 (rows, cols) multipliers by the number of subplots (e.g. 2x3 grid = 2x3 bigger than a single plot)
```

### line 634

```
```
 color picker - https://share.google/Va9O7umqecaS1dthG
 (R, G, B) 0-255
 black
 blue
 red
 grey
 dark grey
 red
```

### line 643

```
```
 Any source not listed above falls back to utils.DEFAULT_PLOT_STYLE.
```

### line 694

```
```
 it.scale_model(static_trial="Static_01",
                marker_placer=True,
                linear_scaling=True,
                muscle_opt=True, n_eval=10,
                mvic_factor=3,
                replace=True)
```

### line 701

```
```
 2) Re-run external biomechanics (IK -> ID -> MA) so the IK marker error is recomputed.
```

### line 708

```
```
 calibrating on a reserve-saturated trial teaches CEINMS to reproduce
 an arbitrary force split — see qa_gate.py
```

### line 725

```
```
 Numbered layout since 2026-07-29; resolve rather than hard-code so this
 keeps working on older flat sessions too.
```

### line 728

```
```
 holds Deadlift_35kg_01/02.c3d
```

### line 735

```
```
 Export ONCE — model-independent raw inputs -> experimental/<trial>/
 s.export(trials=TRIALS,
         export_src=C3D_SRC,
         replace=True)
```

### line 743

```
```
 already done at the session level
```

### line 747

```
```
 it.plot_summary(trials=TRIALS, figures=["jra"])
```

### line 750

```
```
 =====================================================================
 SINGLE-SESSION RUNNER
       conda activate msk311
       python settings.py

 settings.py is the ONLY project file you edit/run. Everything above this
 block is configuration; everything below is the run. It needs bioscout
 installed in the env and the session data under
       simulations/<athlete>/<SESSION>/3_iterations/<iteration>/<trial>/

 Per-iteration recipe (generic model, time windows, CEINMS a/b/g, labels,
 colours) lives in that session's session.yaml — not here.
 =====================================================================
```

### line 766

```
```
 =====================================================================
 1. WHAT TO RUN — turn exactly one (or TPS + the batch) on
 =====================================================================
 (re)build the MRI/TPS-personalised models
 run the pipeline over ITERATIONS below
 one iteration, for debugging
 housekeeping; done 2026-07-29
 ---- the 2026-07-31 re-scale (see section 2b below) -------------------
 Flags rather than edit-then-run, so the overnight job cannot be started
 with a stale switch left True from the previous run:
     python settings.py --check-scaling
     python settings.py --rescale-all
```

### line 792

```
```
 --sessions 25_03_31        restrict the plan (run the two sessions as two
                            parallel processes -- separate session folders,
                            so they never write the same file)
 --skip cateli gpk          leave finished iterations alone
 --reuse-models             keep scaled.osim / scaled_opt_N*.osim if they
                            already exist. The Modenese muscle optimisation
                            is BY FAR the longest step (see below), so this
                            is what makes a restart cheap.
```

### line 804

```
```
 These two do their own thing and exit; the normal batch must not also
 fire, or the session picked by SESSION gets re-run on top of them.
```

### line 808

```
```
 =====================================================================
 2. PIPELINE CONFIG — used by RUN_SESSION_ITERATIONS

 These are the generic stage switches: they apply to whichever models
 ITERATIONS names, MRI or not. Scaling and analysis are separate stages
 because scaling invalidates everything downstream of it.
 =====================================================================
 WHAT to run over. Defaults come from CAPTURES[SESSION] at the top of this
 file, so switching SESSION switches the model list, the trial list and the
 calibration trials together — no chance of running Athlete_03's trial names
 against Athlete_06's data. Override any of them right here for a one-off.
```

### line 822

```
```
 overwrite existing outputs (False = skip finished work)
```

### line 824

```
```
 ---- stage switches -------------------------------------------------
 A FULL first run of a session needs every one of these True, in this order.
 Scaling invalidates everything downstream of it, which is why it is its own
 stage. Set the earlier ones False to resume part-way.
 2_experimental/ already built for 25_03_31 — set True
 only for a session whose c3d have not been exported yet
 None = <session>/1_c3dfiles
```

### line 832

```
```
 DO_SCALE was False for the gpk_optimised iteration, which shipped
 already-scaled models and no longer exists. It must be True now: the
 generics were rebuilt with the reserve/residual actuators, and every
 scaled*.osim on disk predates that.
 generic + static -> scaled.osim (per iteration)
```

### line 838

```
```
 NOT a single switch any more. cateli and lernagopal run the Modenese2015
 muscle optimisation; gpk and all three MRI iterations must NOT -- their
 session.yaml `ceinms_model` is plain `scaled.osim`, and bioscout reads
 that intent from the absence of "opt_N" in the name. One global here
 either skipped it for the two that need it or -- far worse -- ran it for
 the four that must not, which on the GPK model has taken over a day at
 n_eval=10 and would have discarded the MRI models' personalised
 muscle-tendon parameters.
   None = derive per iteration from session.yaml (correct)
   True/False = force it for every iteration (debugging only)
```

### line 850

```
```
 OFF: this re-run changes the models only by adding sixteen actuators.
 Segment geometry, markers and muscle paths are untouched, so marker
 tracking and net joint moments cannot move -- and re-running them rewrites
 session-level files every other iteration reads. True for a genuinely new
 session, or after a geometry change.
 IK -> ID
 Muscle Analysis (lengths + moment arms)
 Static Optimisation -> muscle moments -> JRA
 CEINMS execution -> muscle forces -> JRA
 gpk_optimised has never been calibrated, and its wrap
 changes alter every moment arm, so the calibration
 from gpk does NOT transfer. Leave True for the first
 run; set False to reuse
 3_iterations/gpk_optimised/ceinms_calibration/.
 Pinned per capture. bioscout reads CEINMSSettings.calibration_trial_names
 and, when nothing matches, falls back to "every trial with squat in the
 name" — a plausible-looking calibration on the wrong trials. session.yaml's
 `calibration_trials` is documentation only; bioscout does not read it.
```

### line 870

```
```
 ---- for a GPK range-convergence pass on Athlete_03 (25_03_31) ------
 Widening a coordinate changes the IK solution, so ranges must stop moving
 BEFORE anything downstream runs:
     python fix_gpk.py --rom-only --apply
     DO_MA = DO_SO = DO_CEINMS = False, then python settings.py
     python fix_gpk.py --rom-only       <- still pinned? repeat both
 When nothing pins, turn the three back on and re-run.
```

### line 878

```
```
 per-trial figures inside each trial folder
 {"kin_mom", "summary", "jra"}
 cross-model overlays -> results/<session>/
```

### line 882

```
```
 =====================================================================
 3. TPS / MRI PERSONALISATION CONFIG — used by RUN_TPS_PERSONALISE

 Only these two are MRI-specific: which models to warp, and the landmark
 file to warp them onto. Writes "<generic stem>_tps_<subject>.osim" beside
 each generic — the filename the *_mri iterations in session.yaml expect.
 Re-run whenever the landmarks or bioscout's TPS code change.
 =====================================================================
```

### line 891

```
```
 Sweep the warped model's moment arms afterwards and save the plots. Also
 writes a wrap-corrected "<model>_modWO.osim" beside it as an EXTRA to
 compare against — the personalised model itself is left untouched and
 session.yaml keeps pointing at it. Needs opensim; adds a few minutes per
 model, so turn it off for a quick rebuild.
```

### line 897

```
```
 From CAPTURES — hard-coding Athlete_03's landmarks here would warp another
 athlete's model onto Athlete_03's bones without a word of complaint.
```

### line 902

```
```
 =====================================================================
 4. HOUSEKEEPING CONFIG — used by RUN_PRUNE_LEGACY_INPUTS

 Drops the pre-YAML per-iteration inputs/ folders (each model used to keep
 its own copy of the raw c3d/markers/GRF/EMG). Only removes a folder when
 the shared 2_experimental/ export for that trial exists, so it can never
 delete the last copy. Set PRUNE_ARCHIVE = None to delete outright.
 =====================================================================
```

### line 913

```
```
 =====================================================================
 THE RUN
 =====================================================================
 Report what is enabled. With every switch off this script used to print
 nothing at all and return to the prompt — indistinguishable from a crash.
```

### line 937

```
```
 =====================================================================
 2b. RE-SCALE AND RE-ANALYSE EVERYTHING  (2026-07-31)

 WHY THIS EXISTS
 ---------------
 Every "scaled" model built before 2026-07-31 was generic geometry carrying
 only the subject's mass. openSim.scale_model() built its ScaleTool from
 scratch and never populated a MeasurementSet; OpenSim accepts an empty one
 in silence and scales every body by exactly 1.0. Nothing in the logs said
 so, and the output file was still called scaled.osim, so IK, ID, MA, SO,
 CEINMS and JRA all ran happily on the wrong bones. Segment lengths, mass
 distribution, muscle moment arms and therefore every joint moment and
 contact force in those results are affected.

 The fix (bioscout.utils.scale_measurements) computes the joint centres the
 motion capture cannot see -- Harrington hips, midpoint knees and ankles --
 into a scaling-only copy of the static TRC, builds a MeasurementSet from
 the marker pairs that exist in BOTH the model marker set and that TRC, and
 verifies afterwards that the bodies actually changed size.

 HOW TO RUN
   1. python settings.py --check-scaling      (~1 min)
      Scale stage only, into logs/_scale_check/ -- no iteration folder is
      touched and nothing downstream runs. Read the printed factors:
      anything outside roughly 0.85-1.15 wants a look.
   2. python settings.py --rescale-all        (overnight)

 NOT INCLUDED, deliberately: gpk_ma and gpk_optimised. Those iterations are
 not scaled from a generic -- they are byte copies of the gpk scaled models
 with edited wrap surfaces, so they inherit the OLD broken geometry and
 re-running them here would just re-analyse it. Once gpk has been re-scaled,
 rebuild them from the new models with `bioscout --change-moment-arms` and
 then analyse them. (While you are there: PS_at_brim_l was never given the
 x1.0312 its right-side twin got, so the psoas wrap is left-right asymmetric.)
 =====================================================================
```

### line 973

```
```
 session      iterations to (re)build          scale from the generic?
```

### line 975

```
```
 geometry kept;
   linear_scaling is false in session.yaml, so the scale stage now only
   applies the measured body mass -- the MRI models were carrying the
   generic's 75.34 kg while every result was normalised by ~91 kg.
```

### line 980

```
```
   Same mass-only pass. These two were left out of the plan by
   oversight, so they still carry 75.34 kg while Session.summarise
   divides their joint contact forces by 89.9 -- a 19 % error landing
   directly on the MRI side of the MRI-vs-scaled contrast, i.e. on the
   headline 2x2 figure. Nothing about their geometry is touched.
```

### line 986

```
```
 do_scale=False: gpk_optimised is the gpk scaled models with grown wrap
 surfaces, NOT something scaled from a generic. Scaling it would throw
 the wrap change away. Rebuild the two .osim onto the freshly re-scaled
 gpk with `python rebuild_gpk_ma.py apply` BEFORE enabling this line.
```

### line 1005

```
```
 ---- scale only, into a scratch folder --------------------------
 Nothing in 3_iterations/ is touched: this writes to logs/_scale_check/
 so the factors can be inspected without leaving a half-built model (or
 a NON-muscle-optimised file named scaled_opt_N10.osim) behind.
```

### line 1033

```
```
 _resolve_model_file lives on Iteration, not Session.
```

### line 1064

```
```
 ---- the real thing ------------------------------------------------
```

### line 1083

```
```
 CEINMS calibrates on the MA/EMG outputs of trials this run produced.
 A cal_trial absent from `trials` either fails or silently falls
 back to "every trial with squat in the name", so analyse the
 calibration trials too.
```

### line 1108

```
```
 muscle_opt is NOT a free choice. session.yaml's
 `ceinms_model` name encodes it: `scaled_opt_N10.osim`
 means the Modenese2015 optimisation runs, plain
 `scaled.osim` means it must NOT -- an MRI/TPS model
 carries personalised muscle-tendon parameters, and
 re-fitting them against the generic reference throws
 away the very personalisation that iteration exists to
 test (and costs hours). Override per iteration in
 session.yaml with `muscle_opt: true|false`.
```

### line 1126

```
```
 scale_model returns None on failure. Running the analysis
 anyway produces hundreds of per-trial errors that bury the
 one line saying why — so stop this iteration here.
```

### line 1141

```
```
 One bad iteration must not cost the whole night.
```

### line 1165

```
```
 The old fallback pointed at Athlete_03 regardless of SESSION, so a typo
 in SESSION silently ran the wrong athlete. Fail instead.
```

### line 1176

```
```
 ---- housekeeping ---------------------------------------------------
```

### line 1187

```
```
 ---- build the MRI/TPS models ---------------------------------------
```

### line 1194

```
```
 A *_mri iteration's `generic` already NAMES the *_tps_*.osim file,
 so warp its non-MRI sibling: "cateli_mri" -> "cateli".
```

### line 1201

```
```
 Rebuilding a model without re-running it leaves that iteration's
 results describing the OLD model, with nothing marking them stale.
```

### line 1214

```
```
 ---- one iteration, for debugging -----------------------------------
```

### line 1225

```
```
 ---- the batch ------------------------------------------------------
```

### line 1233

```
```
 ---- 1. EXPORT: model-INDEPENDENT, run ONCE for the whole session ----
 markers/GRF/EMG live in 2_experimental/<trial>/ and are shared by every
 iteration, so exporting per-iteration just repeats identical work. This
 also runs the session-wide EMG normalisation that the CEINMS excitations
 come from (the session-max reference spans every trial).

 TRIALS must be named explicitly on a FIRST run: Iteration._trial_names()
 only sees trials whose folder already exists, so it returns [] until the
 c3d have been ingested. EXPORT_SRC must be ABSOLUTE — ingest_c3d globs
 relative to the process cwd and defaults to the session root, not
 1_c3dfiles.
```

### line 1247

```
```
 The STATIC trial must be exported too, and it is deliberately NOT in
 TRIALS (TRIALS is the analysis list; session.yaml marks the static one
 `type: static`, and bioscout excludes it from _trial_names()). Scaling
 reads 2_experimental/<static>/marker_experimental.trc, so leaving it out
 of the export gives no scaled model and every later stage fails.
```

### line 1257

```
```
 ---- 2..5. per iteration: scale -> IK/ID -> MA -> SO -> CEINMS -------
```

### line 1265

```
```
 MUSCLE_OPT is None by default -> read the intent from this
 iteration's own ceinms_model name (see the MUSCLE_OPT comment).
```

### line 1275

```
```
 static_trial is passed explicitly: scale_model's default is the
 literal "Static_01" and it does NOT read session.yaml's
 `static_trial` key.
```

### line 1280

```
```
 scale_model returns None on failure. Without this guard IK, MA, SO
 and CEINMS all run anyway and fail per-trial, burying the one line
 that said why in hundreds of downstream errors.
```

### line 1288

```
```
 ScaleTool is not documented to preserve non-muscle actuators. If
 it drops them, SO runs with nothing to absorb the muscle-moment vs
 ID-moment difference and silently inflates the muscle forces --
 measured once as a 26 BW walking hip against a true 5.4, with no
 error anywhere. Cheaper to stop here than to find out from a
 figure four hours later.
```

### line 1323

```
```
 -> results/<subject>/<session>/summary_*.png
```

### line 1325

```
```
