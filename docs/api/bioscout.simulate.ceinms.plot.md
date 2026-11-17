# `bioscout.simulate.ceinms.plot`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py)

bioscout.simulate.ceinms.plot — Figures made from CEINMS output — calibration parameters, model  
comparisons, moment tracking, optimisation results and muscle forces.

Split out of the former flat `utils/ceinms.py`; see the package  
__init__ for why. The shared header (imports, the live `settings`  
proxy) comes from `.shared`.

## Contents

- [`plot_loop_results`](#plot_loop_results) — 
- [`plot_ceinms_model_parameters`](#plot_ceinms_model_parameters) — 
- [`plot_compare_ceinms_models`](#plot_compare_ceinms_models) — Plot comparison of muscle parameters between uncalibrated and calibrated CEINMS models
- [`plot_moments_calibration_results`](#plot_moments_calibration_results) — 
- [`plot_ceinms_calibration_results`](#plot_ceinms_calibration_results) — 
- [`plot_optimisation_results`](#plot_optimisation_results) — 
- [`plot_experimental_vs_ceinms`](#plot_experimental_vs_ceinms) — 
- [`plot_ceinms_muscle_forces`](#plot_ceinms_muscle_forces) — 
- [`plot_calibration_parameters`](#plot_calibration_parameters) — Dumbbell figure: open = uncalibrated, filled = calibrated, one x slot per side x muscle group. Writes <calibrated dir>/calibration_parameters.png and a matching .csv (per-muscle values, both models).
- [`plot_ceinms_summary`](#plot_ceinms_summary) — <outputDirectory>/summary.png (2026-10-21), one ROW PER DOF (CEINMS dofSet + subtalar when its moment arms exist), four columns:

### `plot_loop_results`

```python
plot_loop_results(CSVresultsPath=None)
```

| input | type | default |
|---|---|---|
| `CSVresultsPath` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L11)</sub>

### `plot_ceinms_model_parameters`

```python
plot_ceinms_model_parameters(ceinmsModelPath=None)
```

| input | type | default |
|---|---|---|
| `ceinmsModelPath` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L122)</sub>

### `plot_compare_ceinms_models`

```python
plot_compare_ceinms_models(uncalibratedModelPath=None, calibratedModelPath=None)
```

| input | type | default |
|---|---|---|
| `uncalibratedModelPath` | – | `None` |
| `calibratedModelPath` | – | `None` |

Plot comparison of muscle parameters between uncalibrated and calibrated CEINMS models 

  
**Output**

- Bar plots of each muscle parameter for uncalibrated vs calibrated models  
- Difference in optimal fibre length, pennation angle, and tendon slack length between calibrated and uncalibrated models

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L185)</sub>

### `plot_moments_calibration_results`

```python
plot_moments_calibration_results(momentResultsCSV=None)
```

| input | type | default |
|---|---|---|
| `momentResultsCSV` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L271)</sub>

### `plot_ceinms_calibration_results`

```python
plot_ceinms_calibration_results(setupXML_path=None)
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L340)</sub>

### `plot_optimisation_results`

```python
plot_optimisation_results(optimisationOutputDir=None)
```

| input | type | default |
|---|---|---|
| `optimisationOutputDir` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L386)</sub>

### `plot_experimental_vs_ceinms`

```python
plot_experimental_vs_ceinms(
    emgFile=None,
    ceinmsExcitationsFile=None,
    excitationGeneratorFile=None,
    externalMomentsFile=None,
    ceinmsTorquesFile=None
)
```

| input | type | default |
|---|---|---|
| `emgFile` | – | `None` |
| `ceinmsExcitationsFile` | – | `None` |
| `excitationGeneratorFile` | – | `None` |
| `externalMomentsFile` | – | `None` |
| `ceinmsTorquesFile` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L427)</sub>

### `plot_ceinms_muscle_forces`

```python
plot_ceinms_muscle_forces(ceinmsForcesFile=None)
```

| input | type | default |
|---|---|---|
| `ceinmsForcesFile` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L549)</sub>

### `plot_calibration_parameters`

```python
plot_calibration_parameters(
    uncalibratedModelPath,
    calibratedModelPath,
    out_png=None,
    title=None
)
```

| input | type | default |
|---|---|---|
| `uncalibratedModelPath` | – | required |
| `calibratedModelPath` | – | required |
| `out_png` | – | `None` |
| `title` | – | `None` |

Dumbbell figure: open = uncalibrated, filled = calibrated, one x slot per  
side x muscle group. Writes <calibrated dir>/calibration_parameters.png and a  
matching .csv (per-muscle values, both models).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L677)</sub>

### `plot_ceinms_summary`

```python
plot_ceinms_summary(outputDirectory, setupXML_path, save_name='summary.png', n_major=6)
```

| input | type | default |
|---|---|---|
| `outputDirectory` | – | required |
| `setupXML_path` | – | required |
| `save_name` | – | `'summary.png'` |
| `n_major` | – | `6` |

<outputDirectory>/summary.png (2026-10-21), one ROW PER DOF (CEINMS dofSet  
+ subtalar when its moment arms exist), four columns:

  1  ID moment (black), CEINMS torque (red) and the muscle moments  
     (force x moment arm) stacked by muscle group underneath  
  2  CEINMS activation of the major muscles crossing that DOF (solid) and  
     their measured EMG where a channel drives them (dotted, same colour)  
  3  normalised fibre length of the same muscles  
  4  their moment arm about that DOF (cm)

"Major" = the `n_major` muscles with the largest peak |F*r| at the DOF,  
among those crossing it (|r| > 1 mm). Colours = muscle group (as the JCF  
stacks); line style separates muscles of one group. x = % CEINMS window.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/plot.py#L757)</sub>
