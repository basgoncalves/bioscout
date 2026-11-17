# `bioscout.model.inspect.compare_settings`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/compare_settings.py)

compare_settings.py

Run the moment-arm inspection pipeline across RANGES of each setting -- one  
setting at a time, others held at baseline -- and write figures into per-setting  
subfolders, so you can see how each setting affects DISCONTINUITY DETECTION (and,  
for fix settings, whether the jumps actually get removed).

Edit CONFIG_BASE (baseline) and SETTINGS_TO_TRY (the ranges), then run:  
    python compare_settings.py

Output layout (under CONFIG_BASE["out"]):  
    <setting>/<setting>=<value>/          per-value figures (red x = detected)  
    <setting>/_summary_<quantity>_<coord>.png   ALL values OVERLAID per coordinate  
    <setting>/_muscles_flagged.png        # flagged muscles vs the setting's value  
    _overview.txt                         text summary incl. RMSD% vs the original

RMSD% = root-mean-square difference between this iteration's curves and the  
ORIGINAL (baseline before) curves, as a % of each curve's range, averaged over  
muscles. ~0 means the iteration barely changed the model; large means big edits.  
(Detection settings don't change the curves, so their RMSD% is 0; 'n' changes  
the sample count so it's reported as n/a.)

COST: detection settings (min_jump_mm, k_d2, k_local, k_global) are CHEAP -- they  
reuse one baseline sweep. 'n' re-sweeps per value. Fix settings  
(max_displacement_mm, margin_base_mm, margin_frac, n_pose) run a full fix +  
re-sweep per value, so keep those ranges short. Subset `coords` to go faster.

## Contents

- [`main`](#main) — 

### `main`

```python
main()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/compare_settings.py#L247)</sub>
