# `bioscout.results.kinds`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py)

Which result files exist, and what each one is called.

One ordered rule list maps a file (its path relative to the trial folder) to a  
*variable* name. The first matching rule wins; a rule whose name is ``None``  
marks files that are never results (setups, marker locations, .trc).

Add an output to every loader, plot and export with one call::

    from bioscout.results import register_file  
    register_file("rra_kinematics", r"residual_reduction/.*_Kinematics_q\.sto$",  
                  unit="deg", aliases=("rra",), description="RRA-adjusted kinematics")

## Contents

- class [`FileKind`](#filekind) — 
  - [`FileKind.group`](#filekindgroup) — Name without the per-file part: 'moment_arms/{1}' -> 'moment_arms'.
- [`register_file`](#register_file) — Add a file kind. ``first=True`` puts it ahead of the built-ins (use it to override how an existing file is named).
- [`variable_for`](#variable_for) — 
- [`resolve`](#resolve) — User names -> glob patterns on variable names. Accepts a variable ('muscle_forces_so'), an alias ('so_forces', 'ik', 'jcf'), a group ('moment_arms' = every coordinate) or a glob ('joint_*').
- [`describe`](#describe) — The registry as a table (what ``session.results.files`` shows).

<a id="filekind"></a>

## class `FileKind`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py#L27)</sub>

<a id="filekindgroup"></a>

### `FileKind.group`

```python
FileKind.group() -> Optional[str]
```

**returns** `Optional[str]`

Name without the per-file part: 'moment_arms/{1}' -> 'moment_arms'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py#L39)</sub>

### `register_file`

```python
register_file(name, pattern, unit='', description='', aliases=(), first=False)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `pattern` | – | required |
| `unit` | – | `''` |
| `description` | – | `''` |
| `aliases` | – | `()` |
| `first` | – | `False` |

Add a file kind. ``first=True`` puts it ahead of the built-ins (use it to  
override how an existing file is named).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py#L48)</sub>

### `variable_for`

```python
variable_for(rel: str) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `rel` | str | required |

**returns** `Optional[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py#L156)</sub>

### `resolve`

```python
resolve(requested) -> Optional[List[str]]
```

| input | type | default |
|---|---|---|
| `requested` | – | required |

**returns** `Optional[List[str]]`

User names -> glob patterns on variable names. Accepts a variable  
('muscle_forces_so'), an alias ('so_forces', 'ik', 'jcf'), a group  
('moment_arms' = every coordinate) or a glob ('joint_*').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py#L174)</sub>

### `describe`

```python
describe() -> pd.DataFrame
```

**returns** `pd.DataFrame`

The registry as a table (what ``session.results.files`` shows).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/kinds.py#L217)</sub>
