# `bioscout.model.verify`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py)

Verify that every ``.osim`` in a tree can find every mesh it references.

One model::

    from bioscout.model import verify_model  
    report = verify_model("subject021.osim")  
    print(report.headline)          # "3 refs unresolved — OpenSim will draw no bone"

A whole project::

    report = verify_tree(["models", "generic models"])  
    print(format_text(report))  
    raise SystemExit(report.exit_code())

The result objects are plain dataclasses with ``to_dict()``, so the same run can  
be printed for a human and written as ``model_geometry.json`` next to the log —  
machine-readable status is what makes a 29-subject batch auditable.

## Contents

- class [`ModelReport`](#modelreport) — 
  - [`ModelReport.n_refs`](#modelreportn_refs) — 
  - [`ModelReport.by_tier`](#modelreportby_tier) — 
  - [`ModelReport.failing`](#modelreportfailing) — 
  - [`ModelReport.warning`](#modelreportwarning) — 
  - [`ModelReport.worst_tier`](#modelreportworst_tier) — Worst tier present, or ``local`` for a clean model with geometry.
  - [`ModelReport.ok`](#modelreportok) — 
  - [`ModelReport.headline`](#modelreportheadline) — 
  - [`ModelReport.to_dict`](#modelreportto_dict) — 
- class [`TreeReport`](#treereport) — 
  - [`TreeReport.with_geometry`](#treereportwith_geometry) — 
  - [`TreeReport.broken`](#treereportbroken) — 
  - [`TreeReport.not_portable`](#treereportnot_portable) — 
  - [`TreeReport.ok`](#treereportok) — 
  - [`TreeReport.exit_code`](#treereportexit_code) — 
  - [`TreeReport.to_dict`](#treereportto_dict) — 
- [`find_models`](#find_models) — Every ``.osim`` under the given files/folders, deduplicated and sorted.
- [`verify_model`](#verify_model) — Resolve every geometry reference in one model, from that model's folder.
- [`verify_tree`](#verify_tree) — Verify every model under ``roots``.
- [`format_text`](#format_text) — Human-readable report. Clean models are one line each unless ``verbose``.

<a id="modelreport"></a>

## class `ModelReport`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L37)</sub>

<a id="modelreportn_refs"></a>

### `ModelReport.n_refs`

```python
ModelReport.n_refs() -> int
```

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L44)</sub>

<a id="modelreportby_tier"></a>

### `ModelReport.by_tier`

```python
ModelReport.by_tier() -> Dict[str, List[GeometryRef]]
```

**returns** `Dict[str, List[GeometryRef]]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L47)</sub>

<a id="modelreportfailing"></a>

### `ModelReport.failing`

```python
ModelReport.failing() -> List[GeometryRef]
```

**returns** `List[GeometryRef]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L54)</sub>

<a id="modelreportwarning"></a>

### `ModelReport.warning`

```python
ModelReport.warning() -> List[GeometryRef]
```

**returns** `List[GeometryRef]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L58)</sub>

<a id="modelreportworst_tier"></a>

### `ModelReport.worst_tier`

```python
ModelReport.worst_tier() -> str
```

**returns** `str`

Worst tier present, or ``local`` for a clean model with geometry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L63)</sub>

<a id="modelreportok"></a>

### `ModelReport.ok`

```python
ModelReport.ok(strict: bool = False) -> bool
```

| input | type | default |
|---|---|---|
| `strict` | bool | `False` |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L72)</sub>

<a id="modelreportheadline"></a>

### `ModelReport.headline`

```python
ModelReport.headline() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L80)</sub>

<a id="modelreportto_dict"></a>

### `ModelReport.to_dict`

```python
ModelReport.to_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L95)</sub>

<a id="treereport"></a>

## class `TreeReport`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L113)</sub>

<a id="treereportwith_geometry"></a>

### `TreeReport.with_geometry`

```python
TreeReport.with_geometry() -> List[ModelReport]
```

**returns** `List[ModelReport]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L119)</sub>

<a id="treereportbroken"></a>

### `TreeReport.broken`

```python
TreeReport.broken() -> List[ModelReport]
```

**returns** `List[ModelReport]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L123)</sub>

<a id="treereportnot_portable"></a>

### `TreeReport.not_portable`

```python
TreeReport.not_portable() -> List[ModelReport]
```

**returns** `List[ModelReport]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L127)</sub>

<a id="treereportok"></a>

### `TreeReport.ok`

```python
TreeReport.ok() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L130)</sub>

<a id="treereportexit_code"></a>

### `TreeReport.exit_code`

```python
TreeReport.exit_code() -> int
```

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L133)</sub>

<a id="treereportto_dict"></a>

### `TreeReport.to_dict`

```python
TreeReport.to_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L136)</sub>

### `find_models`

```python
find_models(roots: Iterable, recursive: bool = True) -> List[Path]
```

| input | type | default |
|---|---|---|
| `roots` | Iterable | required |
| `recursive` | bool | `True` |

**returns** `List[Path]`

Every ``.osim`` under the given files/folders, deduplicated and sorted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L150)</sub>

### `verify_model`

```python
verify_model(model_path, extra_search: Optional[Sequence] = None) -> ModelReport
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `extra_search` | Optional[Sequence] | `None` |

**returns** `ModelReport`

Resolve every geometry reference in one model, from that model's folder.

Drops the directory index first, so a second call in the same process sees  
a tree you have just repaired. Within one call — and within one  
``verify_tree`` — the index is kept, which is where the speed comes from.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L165)</sub>

### `verify_tree`

```python
verify_tree(
    roots: Iterable,
    extra_search: Optional[Sequence] = None,
    strict: bool = False,
    recursive: bool = True
) -> TreeReport
```

| input | type | default |
|---|---|---|
| `roots` | Iterable | required |
| `extra_search` | Optional[Sequence] | `None` |
| `strict` | bool | `False` |
| `recursive` | bool | `True` |

**returns** `TreeReport`

Verify every model under ``roots``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L189)</sub>

### `format_text`

```python
format_text(report: TreeReport, verbose: bool = False, max_examples: int = 4) -> str
```

| input | type | default |
|---|---|---|
| `report` | TreeReport | required |
| `verbose` | bool | `False` |
| `max_examples` | int | `4` |

**returns** `str`

Human-readable report. Clean models are one line each unless ``verbose``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/verify.py#L223)</sub>
