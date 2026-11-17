# `bioscout.core.project_analysis`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py)

project_analysis.py — project-level analysis across subjects and sessions.

Sits above the session/trial level:

    Project  
    ├── Subject (P03, P05, …)        ← group membership, demographics  
    │   ├── Session (P03/)          ← one calibration / model  
    │   │   ├── Trial (sq_bw_01/)  
    │   │   └── Trial (sq_nw_01/)  
    │   └── Session (P03_follow_up/)  
    └── Subject (P08, …)

  
**Key entry points**

load_subject_results(subject_id, result_type)  
    → {trial_path: DataFrame}  for all sessions of that subject

load_group_results(group, result_type)  
    → {subject_id: {trial_path: DataFrame}}

compute_mean_curve(results)  
    → (mean, sd) as DataFrames/arrays, time-normalised to 0–100 %

compare_groups(groups, result_type, dof)  
    → {group: {"mean": arr, "sd": arr, "n": int}}

## Contents

- [`load_trial_result`](#load_trial_result) — Load a single result file from a trial directory.
- [`load_subject_results`](#load_subject_results) — Load result files for *all sessions and trials* of one subject.
- [`load_group_results`](#load_group_results) — Load results for all subjects belonging to *group*.
- [`time_normalise`](#time_normalise) — Interpolate a DataFrame to *n_points* equally spaced in 0–100 %.
- [`compute_mean_curve`](#compute_mean_curve) — Compute mean ± SD across a set of trials (time-normalised).
- [`compare_groups`](#compare_groups) — Compare group mean ± SD for a single DOF / variable.
- [`compare_subjects`](#compare_subjects) — Mean ± SD per-subject for a single variable (for individual comparisons).
- [`list_all_subjects`](#list_all_subjects) — Return {subject_id: group} for all registered subjects.
- [`list_groups`](#list_groups) — Return unique group labels across all registered subjects.

### `load_trial_result`

```python
load_trial_result(
    trial_dir: Union[str, Path],
    result_type: str
) -> Optional['pd.DataFrame']
```

| input | type | default |
|---|---|---|
| `trial_dir` | Union[str, Path] | required |
| `result_type` | str | required |

**returns** `Optional['pd.DataFrame']`

Load a single result file from a trial directory.

  
**Args**

    trial_dir: absolute path to the trial folder.  
    result_type: key from RESULT_FILES (e.g. 'ik', 'id', 'so_forces').

  
**Returns**

    DataFrame or None if the file is missing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L126)</sub>

### `load_subject_results`

```python
load_subject_results(
    subject_id: str,
    result_type: str,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None
) -> Dict[str, 'pd.DataFrame']
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `result_type` | str | required |
| `trials_to_skip` | List[str] | `None` |
| `simulations_dir` | Path | `None` |

**returns** `Dict[str, 'pd.DataFrame']`

Load result files for *all sessions and trials* of one subject.

  
**Returns**

    {str(trial_dir): DataFrame}  — keyed by the absolute trial path string.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L153)</sub>

### `load_group_results`

```python
load_group_results(
    group: str,
    result_type: str,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None
) -> Dict[str, Dict[str, 'pd.DataFrame']]
```

| input | type | default |
|---|---|---|
| `group` | str | required |
| `result_type` | str | required |
| `trials_to_skip` | List[str] | `None` |
| `simulations_dir` | Path | `None` |

**returns** `Dict[str, Dict[str, 'pd.DataFrame']]`

Load results for all subjects belonging to *group*.

  
**Returns**

    {subject_id: {trial_path: DataFrame}}

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L178)</sub>

### `time_normalise`

```python
time_normalise(df: 'pd.DataFrame', n_points: int = 101) -> 'np.ndarray'
```

| input | type | default |
|---|---|---|
| `df` | 'pd.DataFrame' | required |
| `n_points` | int | `101` |

**returns** `'np.ndarray'`

Interpolate a DataFrame to *n_points* equally spaced in 0–100 %.

Assumes the first column (or a column named 'time') is the time axis.  
Returns a (n_points × n_cols) array, with the time column dropped.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L200)</sub>

### `compute_mean_curve`

```python
compute_mean_curve(
    results: Dict[str, 'pd.DataFrame'],
    n_points: int = 101
) -> Tuple['np.ndarray', 'np.ndarray', List[str]]
```

| input | type | default |
|---|---|---|
| `results` | Dict[str, 'pd.DataFrame'] | required |
| `n_points` | int | `101` |

**returns** `Tuple['np.ndarray', 'np.ndarray', List[str]]`

Compute mean ± SD across a set of trials (time-normalised).

  
**Args**

    results: {any_key: DataFrame} — e.g. output of load_subject_results.  
    n_points: number of time-normalised points (default 101 = 0–100 %).

  
**Returns**

    (mean, sd, column_names)  each array is (n_points × n_dof).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L217)</sub>

### `compare_groups`

```python
compare_groups(
    groups: List[str],
    result_type: str,
    dof: str,
    n_points: int = 101,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None
) -> Dict[str, Dict]
```

| input | type | default |
|---|---|---|
| `groups` | List[str] | required |
| `result_type` | str | required |
| `dof` | str | required |
| `n_points` | int | `101` |
| `trials_to_skip` | List[str] | `None` |
| `simulations_dir` | Path | `None` |

**returns** `Dict[str, Dict]`

Compare group mean ± SD for a single DOF / variable.

  
**Args**

    groups: list of group labels (must match SubjectConfig.group).  
    result_type: e.g. 'ik', 'so_forces'.  
    dof: column name in the result file (e.g. 'hip_flexion_r').  
    n_points: time-normalisation points.

  
**Returns**

    {group_label: {"mean": array(n_points,), "sd": array(n_points,), "n": int}}

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L244)</sub>

### `compare_subjects`

```python
compare_subjects(
    subject_ids: List[str],
    result_type: str,
    dof: str,
    n_points: int = 101,
    trials_to_skip: List[str] = None,
    simulations_dir: Path = None
) -> Dict[str, Dict]
```

| input | type | default |
|---|---|---|
| `subject_ids` | List[str] | required |
| `result_type` | str | required |
| `dof` | str | required |
| `n_points` | int | `101` |
| `trials_to_skip` | List[str] | `None` |
| `simulations_dir` | Path | `None` |

**returns** `Dict[str, Dict]`

Mean ± SD per-subject for a single variable (for individual comparisons).

  
**Returns**

    {subject_id: {"mean": array, "sd": array, "n": int, "group": str}}

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L290)</sub>

### `list_all_subjects`

```python
list_all_subjects() -> Dict[str, str]
```

**returns** `Dict[str, str]`

Return {subject_id: group} for all registered subjects.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L330)</sub>

### `list_groups`

```python
list_groups() -> List[str]
```

**returns** `List[str]`

Return unique group labels across all registered subjects.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/project_analysis.py#L335)</sub>
