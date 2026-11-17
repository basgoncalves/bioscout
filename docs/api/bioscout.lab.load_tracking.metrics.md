# `bioscout.lab.load_tracking.metrics`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py)

Sports-science load metrics for the load-tracking module.

All metrics are well-established in the training-load literature:

    * **TRIMP** (Training Impulse) — internal load from heart rate.  
        - Banister TRIMP (HR-reserve weighted, exponential) when a continuous HR  
          trace + resting/max HR are available.  
        - Edwards summated-zone TRIMP (time in 5 HR zones × zone number) otherwise.  
    * **session-RPE load** = RPE(0-10) × duration(min)  [Foster, 2001].  
    * **ACWR** (acute:chronic workload ratio) — 7-day acute vs 28-day chronic load.  
      The "sweet spot" is ~0.8-1.3; >1.5 is associated with elevated injury risk  
      (Gabbett, 2016). Computed here with the EWMA variant (Williams et al., 2017).  
    * **Monotony** = mean daily load / SD daily load; **Strain** = weekly load ×  
      monotony  [Foster, 2001].  
    * **Banister fitness-fatigue** impulse-response model: fitness and fatigue as  
      exponentially-decaying sums of past load (τ_fitness≈42 d, τ_fatigue≈7 d).

These are heuristics, not measured muscle forces — see ``ml_interface.py`` for the  
hook that lets the real ML/OpenSim muscle-force model replace the muscle layer.

## Contents

- class [`DailyLoad`](#dailyload) — 
- [`hr_reserve_fraction`](#hr_reserve_fraction) — 
- [`banister_trimp`](#banister_trimp) — Banister TRIMP from a continuous HR trace.
- [`edwards_trimp`](#edwards_trimp) — Edwards summated heart-rate-zone TRIMP (zones at 50-60-70-80-90 %HRmax).
- [`srpe_load`](#srpe_load) — session-RPE load = RPE × duration(min). Needs a manual RPE (0-10).
- [`estimate_rpe_from_hr`](#estimate_rpe_from_hr) — Estimate session RPE (0-10) from %HR-reserve when RPE wasn't recorded.
- [`session_load`](#session_load) — Compute every per-session load metric. Returns a dict of named values.
- [`daily_series`](#daily_series) — Collapse sessions to one load value per calendar day (gaps filled with 0).
- [`ewma_acwr`](#ewma_acwr) — EWMA acute:chronic workload ratio (Williams et al., 2017).
- [`weekly_monotony_strain`](#weekly_monotony_strain) — Monotony & strain for the most recent rolling 7-day window.
- [`fitness_fatigue`](#fitness_fatigue) — Banister fitness-fatigue impulse-response model.
- [`acwr_status`](#acwr_status) — Map an ACWR value to (label, matplotlib colour).

<a id="dailyload"></a>

## class `DailyLoad`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L157)</sub>

### `hr_reserve_fraction`

```python
hr_reserve_fraction(hr: float, hr_rest: float, hr_max: float) -> float
```

| input | type | default |
|---|---|---|
| `hr` | float | required |
| `hr_rest` | float | required |
| `hr_max` | float | required |

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L37)</sub>

### `banister_trimp`

```python
banister_trimp(session: SessionData, athlete: AthleteProfile) -> Optional[float]
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `athlete` | AthleteProfile | required |

**returns** `Optional[float]`

Banister TRIMP from a continuous HR trace.

TRIMP = Σ_i Δt_min,i · HRr_i · 0.64·e^(b·HRr_i),  b=1.92 (M) / 1.67 (F).  
Returns None when there is no usable HR trace.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L42)</sub>

### `edwards_trimp`

```python
edwards_trimp(session: SessionData, athlete: AthleteProfile) -> Optional[float]
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `athlete` | AthleteProfile | required |

**returns** `Optional[float]`

Edwards summated heart-rate-zone TRIMP (zones at 50-60-70-80-90 %HRmax).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L73)</sub>

### `srpe_load`

```python
srpe_load(session: SessionData) -> Optional[float]
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |

**returns** `Optional[float]`

session-RPE load = RPE × duration(min). Needs a manual RPE (0-10).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L103)</sub>

### `estimate_rpe_from_hr`

```python
estimate_rpe_from_hr(session: SessionData, athlete: AthleteProfile) -> Optional[float]
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `athlete` | AthleteProfile | required |

**returns** `Optional[float]`

Estimate session RPE (0-10) from %HR-reserve when RPE wasn't recorded.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L110)</sub>

### `session_load`

```python
session_load(session: SessionData, athlete: AthleteProfile) -> dict
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `athlete` | AthleteProfile | required |

**returns** `dict`

Compute every per-session load metric. Returns a dict of named values.

``load`` is the unified internal-load figure used downstream (Banister TRIMP  
preferred; Edwards or sRPE as fallback) so that mixed HR/non-HR sessions are  
comparable on one axis.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L120)</sub>

### `daily_series`

```python
daily_series(sessions: list[SessionData], loads: list[float]) -> list[DailyLoad]
```

| input | type | default |
|---|---|---|
| `sessions` | list[SessionData] | required |
| `loads` | list[float] | required |

**returns** `list[DailyLoad]`

Collapse sessions to one load value per calendar day (gaps filled with 0).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L163)</sub>

### `ewma_acwr`

```python
ewma_acwr(daily: list[DailyLoad], acute_tc: int = 7, chronic_tc: int = 28) -> dict
```

| input | type | default |
|---|---|---|
| `daily` | list[DailyLoad] | required |
| `acute_tc` | int | `7` |
| `chronic_tc` | int | `28` |

**returns** `dict`

EWMA acute:chronic workload ratio (Williams et al., 2017).

Returns per-day acute load, chronic load, ACWR, plus the latest values.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L184)</sub>

### `weekly_monotony_strain`

```python
weekly_monotony_strain(daily: list[DailyLoad]) -> dict
```

| input | type | default |
|---|---|---|
| `daily` | list[DailyLoad] | required |

**returns** `dict`

Monotony & strain for the most recent rolling 7-day window.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L220)</sub>

### `fitness_fatigue`

```python
fitness_fatigue(
    daily: list[DailyLoad],
    tau_fitness: float = 42.0,
    tau_fatigue: float = 7.0,
    k_fit: float = 1.0,
    k_fat: float = 2.0
) -> dict
```

| input | type | default |
|---|---|---|
| `daily` | list[DailyLoad] | required |
| `tau_fitness` | float | `42.0` |
| `tau_fatigue` | float | `7.0` |
| `k_fit` | float | `1.0` |
| `k_fat` | float | `2.0` |

**returns** `dict`

Banister fitness-fatigue impulse-response model.

fitness(t) = Σ load(τ)·e^-(t-τ)/tau_fitness  
fatigue(t) = Σ load(τ)·e^-(t-τ)/tau_fatigue  
form(t)    = k_fit·fitness - k_fat·fatigue   (a.k.a. "performance potential")

Returns per-day series plus latest scalars. Fatigue decays ~7 d; fitness ~42 d.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L234)</sub>

### `acwr_status`

```python
acwr_status(acwr: Optional[float]) -> tuple[str, str]
```

| input | type | default |
|---|---|---|
| `acwr` | Optional[float] | required |

**returns** `tuple[str, str]`

Map an ACWR value to (label, matplotlib colour).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/metrics.py#L275)</sub>
