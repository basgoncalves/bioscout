# `bioscout.simulate.fast_ma`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/fast_ma.py)

Fast muscle analysis: MTU length + moment arms only, by finite differences.

OpenSim's MuscleAnalysis computes every moment arm with a separate  
MomentArmSolver call (muscles x coordinates x frames) plus fibre outputs and  
moments we never use. Here, per frame: pose the model once (IK, 6 Hz low-pass  
like the AnalyzeTool), read all lengths, then for each coordinate perturb it  
+/-h (constraints enforced, so couplers move with it) and take  
r = -dL/dq for ALL muscles at once.

Writes _MuscleAnalysis_Length.sto and _MuscleAnalysis_MomentArm_<coord>.sto  
(same names/columns as OpenSim) to --out.

  python fast_ma.py MODEL.osim IK.mot --out DIR [--coords hip_flexion_r ...]  
  python fast_ma.py --compare REF_DIR NEW_DIR

## Contents

- [`write_sto`](#write_sto) — 
- [`run`](#run) — 
- [`read_sto`](#read_sto) — 
- [`compare`](#compare) — 

### `write_sto`

```python
write_sto(path, t, names, data, name)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `t` | – | required |
| `names` | – | required |
| `data` | – | required |
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/fast_ma.py#L23)</sub>

### `run`

```python
run(model_path, ik_path, out, coords=None, h=0.0001, lowpass=6.0, min_wraps=2)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `ik_path` | – | required |
| `out` | – | required |
| `coords` | – | `None` |
| `h` | – | `0.0001` |
| `lowpass` | – | `6.0` |
| `min_wraps` | – | `2` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/fast_ma.py#L32)</sub>

### `read_sto`

```python
read_sto(p)
```

| input | type | default |
|---|---|---|
| `p` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/fast_ma.py#L136)</sub>

### `compare`

```python
compare(ref, new)
```

| input | type | default |
|---|---|---|
| `ref` | – | required |
| `new` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/fast_ma.py#L143)</sub>
