# `bioscout.model.moment_arms.solve`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/solve.py)

Solve for the wrap radius that produces a requested moment-arm change.

Moment arm is ``dL/dq`` and, once a path wraps, a nonlinear function of the  
geometry — so there is no closed form for "the radius that adds 5 mm". This  
brackets and bisects on a caller-supplied ``measure(radius) -> curve`` instead,  
which keeps every OpenSim call on the caller's side of the seam and makes the  
search itself unit-testable against an analytic stub.

The objective is the **mean** change across the sweep rather than the change at  
one pose, because the request is "shift the whole curve up", and a single-pose  
match can be achieved by a radius that distorts the rest of the range.

## Contents

- class [`SolveResult`](#solveresult) — 
  - [`SolveResult.error_mm`](#solveresulterror_mm) — 
- [`solve_scalar_for_target`](#solve_scalar_for_target) — Generic 1-D search for the parameter that hits a moment-arm target.
- [`solve_radius_for_offset`](#solve_radius_for_offset) — Find the radius whose mean moment arm sits ``offset_mm`` above baseline.

<a id="solveresult"></a>

## class `SolveResult`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/solve.py#L24)</sub>

<a id="solveresulterror_mm"></a>

### `SolveResult.error_mm`

```python
SolveResult.error_mm() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/solve.py#L34)</sub>

### `solve_scalar_for_target`

```python
solve_scalar_for_target(
    measure: Callable[[float], Sequence[float]],
    x0: float,
    baseline: Sequence[float],
    scale: Optional[float] = None,
    offset_mm: Optional[float] = None,
    step: float = 1.0,
    additive: bool = True,
    tol_mm: float = 0.2,
    max_iter: int = 20,
    max_span: float = 50.0
) -> SolveResult
```

| input | type | default |
|---|---|---|
| `measure` | Callable[[float], Sequence[float]] | required |
| `x0` | float | required |
| `baseline` | Sequence[float] | required |
| `scale` | Optional[float] | `None` |
| `offset_mm` | Optional[float] | `None` |
| `step` | float | `1.0` |
| `additive` | bool | `True` |
| `tol_mm` | float | `0.2` |
| `max_iter` | int | `20` |
| `max_span` | float | `50.0` |

**returns** `SolveResult`

Generic 1-D search for the parameter that hits a moment-arm target.

``measure(x)`` returns the moment-arm curve (metres) for parameter ``x``.  
The parameter can be anything monotonic-ish in moment arm: a wrap radius, or  
the magnitude of a path-point translation.

Two target kinds, and the distinction matters for a whole-model change:

* ``scale=k``   -> mean moment arm becomes ``k * baseline mean``. Sign is  
  preserved, so abductors (negative here) and adductors (positive) both grow  
  in magnitude. This is the right target for "the muscles are bigger".  
* ``offset_mm`` -> mean moment arm becomes ``baseline mean + offset``. Signed,  
  so for a muscle whose moment arm is negative a positive offset *shrinks*  
  its magnitude. Use ``scale`` unless you mean exactly this.

``additive`` brackets by ``x +/- step`` (a translation starting from 0);  
otherwise it brackets multiplicatively (a radius, which cannot cross zero).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/solve.py#L52)</sub>

### `solve_radius_for_offset`

```python
solve_radius_for_offset(
    measure: Callable[[float], Sequence[float]],
    r0: float,
    offset_mm: float,
    tol_mm: float = 0.2,
    max_iter: int = 20,
    max_factor: float = 3.0
) -> SolveResult
```

| input | type | default |
|---|---|---|
| `measure` | Callable[[float], Sequence[float]] | required |
| `r0` | float | required |
| `offset_mm` | float | required |
| `tol_mm` | float | `0.2` |
| `max_iter` | int | `20` |
| `max_factor` | float | `3.0` |

**returns** `SolveResult`

Find the radius whose mean moment arm sits ``offset_mm`` above baseline.

``measure(radius)`` returns the moment-arm curve (in metres) for that  
radius; ``measure(r0)`` defines the baseline.

Growing a wrap cylinder normally increases the moment arm monotonically, so  
this expands the bracket geometrically and then bisects. A non-monotonic or  
unreachable request stops with ``ok=False`` and the closest radius found —  
the caller reports it rather than silently shipping a model that missed the  
target.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/solve.py#L188)</sub>
