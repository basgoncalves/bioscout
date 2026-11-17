# `bioscout.core.analysis_runner`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py)

Analysis runner that integrates with existing analysis modules.

## Contents

- class [`AnalysisStep`](#analysisstep) — Available analysis steps.
- class [`AnalysisConfig`](#analysisconfig) — Configuration object for analysis.
  - [`AnalysisConfig.get`](#analysisconfigget) — 
  - [`AnalysisConfig.trial_path`](#analysisconfigtrial_path) — 
  - [`AnalysisConfig.replace_existing`](#analysisconfigreplace_existing) — 
  - [`AnalysisConfig.steps`](#analysisconfigsteps) — 
  - [`AnalysisConfig.parameters`](#analysisconfigparameters) — 
- class [`AnalysisRunner`](#analysisrunner) — Runs analysis steps using the existing Analyse class.
  - [`AnalysisRunner.run_analysis`](#analysisrunnerrun_analysis) — Run complete analysis workflow.
  - [`AnalysisRunner.stop_analysis`](#analysisrunnerstop_analysis) — Stop the currently running analysis.
  - [`AnalysisRunner.prepare_analysis`](#analysisrunnerprepare_analysis) — Prepare analysis by loading the Analyse class.
  - [`AnalysisRunner.run_step`](#analysisrunnerrun_step) — Run a single analysis step.

<a id="analysisstep"></a>

## class `AnalysisStep`(Enum)

Available analysis steps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L19)</sub>

<a id="analysisconfig"></a>

## class `AnalysisConfig`

```python
AnalysisConfig(
    trial_path: str = None,
    steps: List[str] = None,
    parameters: Dict[str, Any] = None,
    replace_existing: bool = False,
    **kwargs
)
```

| input | type | default |
|---|---|---|
| `trial_path` | str | `None` |
| `steps` | List[str] | `None` |
| `parameters` | Dict[str, Any] | `None` |
| `replace_existing` | bool | `False` |
| `**kwargs` | – | – |

Configuration object for analysis.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L40)</sub>

<a id="analysisconfigget"></a>

### `AnalysisConfig.get`

```python
AnalysisConfig.get(key: str, default=None)
```

| input | type | default |
|---|---|---|
| `key` | str | required |
| `default` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L61)</sub>

<a id="analysisconfigtrial_path"></a>

### `AnalysisConfig.trial_path`

```python
AnalysisConfig.trial_path()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L65)</sub>

<a id="analysisconfigreplace_existing"></a>

### `AnalysisConfig.replace_existing`

```python
AnalysisConfig.replace_existing()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L69)</sub>

<a id="analysisconfigsteps"></a>

### `AnalysisConfig.steps`

```python
AnalysisConfig.steps()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L73)</sub>

<a id="analysisconfigparameters"></a>

### `AnalysisConfig.parameters`

```python
AnalysisConfig.parameters()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L77)</sub>

<a id="analysisrunner"></a>

## class `AnalysisRunner`

```python
AnalysisRunner(
    callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
)
```

| input | type | default |
|---|---|---|
| `callback` | Optional[Callable] | `None` |
| `progress_callback` | Optional[Callable] | `None` |

Runs analysis steps using the existing Analyse class.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L81)</sub>

<a id="analysisrunnerrun_analysis"></a>

### `AnalysisRunner.run_analysis`

```python
AnalysisRunner.run_analysis(config: AnalysisConfig) -> tuple[bool, str]
```

| input | type | default |
|---|---|---|
| `config` | AnalysisConfig | required |

**returns** `tuple[bool, str]`

Run complete analysis workflow.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L91)</sub>

<a id="analysisrunnerstop_analysis"></a>

### `AnalysisRunner.stop_analysis`

```python
AnalysisRunner.stop_analysis() -> None
```

**returns** `None`

Stop the currently running analysis.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L139)</sub>

<a id="analysisrunnerprepare_analysis"></a>

### `AnalysisRunner.prepare_analysis`

```python
AnalysisRunner.prepare_analysis(config: AnalysisConfig) -> tuple[bool, str]
```

| input | type | default |
|---|---|---|
| `config` | AnalysisConfig | required |

**returns** `tuple[bool, str]`

Prepare analysis by loading the Analyse class.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L143)</sub>

<a id="analysisrunnerrun_step"></a>

### `AnalysisRunner.run_step`

```python
AnalysisRunner.run_step(
    step: AnalysisStep,
    step_config: Dict[str, Any]
) -> tuple[bool, str]
```

| input | type | default |
|---|---|---|
| `step` | AnalysisStep | required |
| `step_config` | Dict[str, Any] | required |

**returns** `tuple[bool, str]`

Run a single analysis step.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis_runner.py#L186)</sub>
