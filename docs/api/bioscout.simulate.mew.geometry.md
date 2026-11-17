# `bioscout.simulate.mew.geometry`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py)

MTU geometry: moment arms r(q) and MTU length l_mt(q).

Three providers behind one interface, in increasing speed and decreasing  
fidelity:

    OpenSimGeometry    live OpenSim API   accurate, slow, needs opensim  
    TableGeometry      MuscleAnalysis     accurate, fast, needs a prior MA run  
    SurrogateGeometry  fitted polynomial  fast enough for real time

``OpenSimGeometry`` is also where MuscleParameters are read off the .osim, and  
where the XML fallback lives so parameters can be read with no opensim install.

## Contents

- class [`GeometryProvider`](#geometryprovider) — Interface. ``muscles`` and ``dofs`` fix the array ordering everywhere.
  - [`GeometryProvider.moment_arms`](#geometryprovidermoment_arms) — (nt, ndof, nm) moment arms in metres.
  - [`GeometryProvider.mtu_lengths`](#geometryprovidermtu_lengths) — (nt, nm) musculotendon lengths in metres.
  - [`GeometryProvider.parameters`](#geometryproviderparameters) — 
- class [`TableGeometry`](#tablegeometry) — Moment arms and lengths from OpenSim MuscleAnalysis .sto output.
  - [`TableGeometry.moment_arms`](#tablegeometrymoment_arms) — 
  - [`TableGeometry.mtu_lengths`](#tablegeometrymtu_lengths) — 
  - [`TableGeometry.parameters`](#tablegeometryparameters) — 
- class [`OpenSimGeometry`](#opensimgeometry) — Query the model directly. Accurate and slow; the reference implementation.
  - [`OpenSimGeometry.moment_arms`](#opensimgeometrymoment_arms) — 
  - [`OpenSimGeometry.mtu_lengths`](#opensimgeometrymtu_lengths) — 
  - [`OpenSimGeometry.parameters`](#opensimgeometryparameters) — 
- class [`SurrogateGeometry`](#surrogategeometry) — Polynomial surrogate of r(q) and l_mt(q), fitted from any other provider.
  - [`SurrogateGeometry.fit`](#surrogategeometryfit) — 
  - [`SurrogateGeometry.poor_fits`](#surrogategeometrypoor_fits) — 
  - [`SurrogateGeometry.mtu_lengths`](#surrogategeometrymtu_lengths) — 
  - [`SurrogateGeometry.moment_arms`](#surrogategeometrymoment_arms) — 
- [`read_model_parameters`](#read_model_parameters) — Parse MTU parameters out of an .osim by XML. No OpenSim import required.
- [`build_geometry`](#build_geometry) — Pick a provider: MA tables if present (fast + identical to the CEINMS run), else the OpenSim API, and say which was chosen.

<a id="geometryprovider"></a>

## class `GeometryProvider`

Interface. ``muscles`` and ``dofs`` fix the array ordering everywhere.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L25)</sub>

<a id="geometryprovidermoment_arms"></a>

### `GeometryProvider.moment_arms`

```python
GeometryProvider.moment_arms(q: pd.DataFrame) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `q` | pd.DataFrame | required |

**returns** `np.ndarray`

(nt, ndof, nm) moment arms in metres.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L32)</sub>

<a id="geometryprovidermtu_lengths"></a>

### `GeometryProvider.mtu_lengths`

```python
GeometryProvider.mtu_lengths(q: pd.DataFrame) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `q` | pd.DataFrame | required |

**returns** `np.ndarray`

(nt, nm) musculotendon lengths in metres.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L36)</sub>

<a id="geometryproviderparameters"></a>

### `GeometryProvider.parameters`

```python
GeometryProvider.parameters() -> MuscleParameters
```

**returns** `MuscleParameters`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L40)</sub>

<a id="tablegeometry"></a>

## class `TableGeometry`(GeometryProvider)

```python
TableGeometry(ma_dir, muscles=None, dofs=None)
```

| input | type | default |
|---|---|---|
| `ma_dir` | – | required |
| `muscles` | – | `None` |
| `dofs` | – | `None` |

Moment arms and lengths from OpenSim MuscleAnalysis .sto output.

A bioscout trial that has run ``run_ma`` already has this directory:  
``<trial>/muscle_analysis/`` with ``*_MomentArm_<dof>.sto`` and  
``*_Length.sto``. Reusing it costs one file read instead of thousands of  
API calls, and it is the SAME geometry the CEINMS run used -- which is what  
makes the tier-2/3 comparison against CEINMS a like-for-like test.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L104)</sub>

<a id="tablegeometrymoment_arms"></a>

### `TableGeometry.moment_arms`

```python
TableGeometry.moment_arms(q: pd.DataFrame) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `q` | pd.DataFrame | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L149)</sub>

<a id="tablegeometrymtu_lengths"></a>

### `TableGeometry.mtu_lengths`

```python
TableGeometry.mtu_lengths(q: pd.DataFrame) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `q` | pd.DataFrame | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L154)</sub>

<a id="tablegeometryparameters"></a>

### `TableGeometry.parameters`

```python
TableGeometry.parameters() -> MuscleParameters
```

**returns** `MuscleParameters`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L157)</sub>

<a id="opensimgeometry"></a>

## class `OpenSimGeometry`(GeometryProvider)

```python
OpenSimGeometry(osim_path, muscles=None, dofs=None)
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |
| `muscles` | – | `None` |
| `dofs` | – | `None` |

Query the model directly. Accurate and slow; the reference implementation.

Imports opensim lazily so the rest of the package stays importable without it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L166)</sub>

<a id="opensimgeometrymoment_arms"></a>

### `OpenSimGeometry.moment_arms`

```python
OpenSimGeometry.moment_arms(q)
```

| input | type | default |
|---|---|---|
| `q` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L222)</sub>

<a id="opensimgeometrymtu_lengths"></a>

### `OpenSimGeometry.mtu_lengths`

```python
OpenSimGeometry.mtu_lengths(q)
```

| input | type | default |
|---|---|---|
| `q` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L225)</sub>

<a id="opensimgeometryparameters"></a>

### `OpenSimGeometry.parameters`

```python
OpenSimGeometry.parameters() -> MuscleParameters
```

**returns** `MuscleParameters`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L228)</sub>

<a id="surrogategeometry"></a>

## class `SurrogateGeometry`(GeometryProvider)

```python
SurrogateGeometry(muscles, dofs, degree=3)
```

| input | type | default |
|---|---|---|
| `muscles` | – | required |
| `dofs` | – | required |
| `degree` | – | `3` |

Polynomial surrogate of r(q) and l_mt(q), fitted from any other provider.

Fitting is a one-off cost per model; evaluation is a matrix product, which  
is what puts the camera-driven pipeline inside a frame budget. Fit quality  
is reported per muscle so a bad fit is visible rather than silent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L235)</sub>

<a id="surrogategeometryfit"></a>

### `SurrogateGeometry.fit`

```python
SurrogateGeometry.fit(
    provider: GeometryProvider,
    q_samples: pd.DataFrame
) -> 'SurrogateGeometry'
```

| input | type | default |
|---|---|---|
| `provider` | GeometryProvider | required |
| `q_samples` | pd.DataFrame | required |

**returns** `'SurrogateGeometry'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L266)</sub>

<a id="surrogategeometrypoor_fits"></a>

### `SurrogateGeometry.poor_fits`

```python
SurrogateGeometry.poor_fits(threshold=0.99) -> Dict[str, float]
```

| input | type | default |
|---|---|---|
| `threshold` | – | `0.99` |

**returns** `Dict[str, float]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L285)</sub>

<a id="surrogategeometrymtu_lengths"></a>

### `SurrogateGeometry.mtu_lengths`

```python
SurrogateGeometry.mtu_lengths(q)
```

| input | type | default |
|---|---|---|
| `q` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L293)</sub>

<a id="surrogategeometrymoment_arms"></a>

### `SurrogateGeometry.moment_arms`

```python
SurrogateGeometry.moment_arms(q)
```

| input | type | default |
|---|---|---|
| `q` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L297)</sub>

### `read_model_parameters`

```python
read_model_parameters(
    osim_path,
    muscles: Optional[Sequence[str]] = None
) -> MuscleParameters
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |
| `muscles` | Optional[Sequence[str]] | `None` |

**returns** `MuscleParameters`

Parse MTU parameters out of an .osim by XML. No OpenSim import required.

This is deliberately not routed through the OpenSim API: reading a model's  
numbers should never depend on a DLL loading.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L59)</sub>

### `build_geometry`

```python
build_geometry(
    osim=None,
    ma_dir=None,
    muscles=None,
    dofs=None,
    prefer='auto'
) -> GeometryProvider
```

| input | type | default |
|---|---|---|
| `osim` | – | `None` |
| `ma_dir` | – | `None` |
| `muscles` | – | `None` |
| `dofs` | – | `None` |
| `prefer` | – | `'auto'` |

**returns** `GeometryProvider`

Pick a provider: MA tables if present (fast + identical to the CEINMS run),  
else the OpenSim API, and say which was chosen.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/geometry.py#L303)</sub>
