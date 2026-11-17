# `bioscout.simulate.ceinms.shared`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/shared.py)

bioscout.simulate.ceinms — CEINMS (Calibrated EMG-Informed Neuromusculoskeletal  
Modelling) helpers: build the excitation generator, subject/calibration/execution  
XMLs and input data, run the CEINMS calibration + execution binaries, and plot  
the results. Driven by the project settings (EMG->muscle mapping, muscle groups,  
calibration parameters) and the per-trial Analyse objects in  
:mod:`bioscout.core.analysis`.

## Contents

- [`upWorkingDirectory`](#upworkingdirectory) — 
- [`check_input_times`](#check_input_times) — 
- [`abg_base_name`](#abg_base_name) — Strip any trailing _a<A>_b<B>_g<G> blocks so the base name never nests.
- [`abg_from_name`](#abg_from_name) — (alpha, beta, gamma) from the LAST suffix block; tolerates nested names.

### `upWorkingDirectory`

```python
upWorkingDirectory()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/shared.py#L84)</sub>

### `check_input_times`

```python
check_input_times(setupXML_path=None)
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/shared.py#L91)</sub>

### `abg_base_name`

```python
abg_base_name(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

Strip any trailing _a<A>_b<B>_g<G> blocks so the base name never nests.

executable_loop writes its mutated <outputDirectory> back into the setup  
XML, so before this fix every re-run appended another suffix  
(Execution_a10_b1_g1000_a10_b1_g5000_a10_b1_g1 ...).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/shared.py#L150)</sub>

### `abg_from_name`

```python
abg_from_name(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

(alpha, beta, gamma) from the LAST suffix block; tolerates nested names.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/shared.py#L160)</sub>
