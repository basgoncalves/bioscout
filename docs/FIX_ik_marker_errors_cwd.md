# Fix: `_ik_marker_errors.sto` written into the project root

## Symptom
Every `bioscout run` / `settings.py` run kept re-creating
`C:\Users\Basilio\ucloud\Powerlifiting\_ik_marker_errors.sto`
(and overwriting it, so it always belonged to whichever model ran last).

## Cause
`openSim.place_markers_via_ik()` (the standalone marker-registration IK used
when `marker_placer=True`, i.e. the MRI/TPS models where ScaleTool's
MarkerPlacer crashes) built an `osim.InverseKinematicsTool()` and never set a
results directory.

OpenSim defaults:
- `results_directory = './'` → **the process CWD**, which is the project root
- `report_errors = True` → writes `_ik_marker_errors.sto` there

`run_ik()` had already been fixed this way (2026-08-24); this second IK call
was missed. Only the errors file appeared, not
`_ik_model_marker_locations.sto`, because `report_marker_locations` defaults
to False — that is the fingerprint that identified this call site.

## Fix
`bioscout/utils/openSim.py` — in `place_markers_via_ik()`, right after
`ik.setOutputMotionFileName(_mot)`:

```python
_ik_res = os.path.dirname(os.path.abspath(_mot))
os.makedirs(_ik_res, exist_ok=True)
try:
    ik.setResultsDir(_ik_res)
except Exception:
    pass
```

The file now lands beside the registration `.mot`, i.e. in
`models/personalised/<Athlete>/` (or `work_dir`).

Also `bioscout/utils/analysis.py` — `Analyse.calculate_mean_marker_error()`
read the hard-coded relative `'.\\_ik_marker_errors.sto'`, which only worked
because of an earlier `os.chdir`. Now reads
`os.path.join(self.path, '_ik_marker_errors.sto')`.

## Verify
```bash
cd C:\Users\Basilio\ucloud\Powerlifiting
python settings.py --only gpkv4_mri     # any iteration with marker_placer=True
ls _ik_marker_errors.sto                # must NOT exist
ls models/personalised/Athlete_03/_ik_marker_errors.sto   # here instead
```

The stale root copy was moved to `_to_delete/_ik_marker_errors_stray_20260828.sto`.

## Remaining CWD hazards
Only three `InverseKinematicsTool` sites exist; all three now set an absolute
results dir. Other OpenSim tools (`ID`, `MA`, `SO`, `JRA`) set their results
dir relative to their own setup XML, which is correct. The wider issue — ~20
bare `os.chdir(self.path)` calls in `analysis.py` that never restore — is
still open (see `docs/PROPOSAL_models_and_cwd.md` §3).
