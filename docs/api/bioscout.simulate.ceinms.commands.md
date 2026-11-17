# `bioscout.simulate.ceinms.commands`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py)

bioscout.simulate.ceinms.commands — Running the CEINMS executables: the terminal wrapper, calibration,  
execution, the weight loop and CEINMSoptimise.

Split out of the former flat `utils/ceinms.py`; see the package  
__init__ for why. The shared header (imports, the live `settings`  
proxy) comes from `.shared`.

## Contents

- [`ceinms_terminal`](#ceinms_terminal) — 
- [`calibrate`](#calibrate) — 
- [`calibrate_synergy_compare`](#calibrate_synergy_compare) — 
- [`executable`](#executable) — 
- [`executable_loop`](#executable_loop) — 
- [`executable_loop_summarise_results`](#executable_loop_summarise_results) — 
- [`optimise`](#optimise) — 

### `ceinms_terminal`

```python
ceinms_terminal(executable_path=None, setupXML_path=None)
```

| input | type | default |
|---|---|---|
| `executable_path` | – | `None` |
| `setupXML_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L14)</sub>

### `calibrate`

```python
calibrate(setupXML_path=None)
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L193)</sub>

### `calibrate_synergy_compare`

```python
calibrate_synergy_compare(setupXML_path=None, synergy_numbers: list = [3, 4, 5, 6])
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |
| `synergy_numbers` | list | `[3, 4, 5, 6]` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L227)</sub>

### `executable`

```python
executable(setupXML_path=None)
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L266)</sub>

### `executable_loop`

```python
executable_loop(
    setupXML_path=None,
    cfgXML_path=None,
    gammas: list = [1, 10, 100, 1000],
    betas: list = [1, 10, 100, 1000],
    alphas: list = [1, 10]
)
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |
| `cfgXML_path` | – | `None` |
| `gammas` | list | `[1, 10, 100, 1000]` |
| `betas` | list | `[1, 10, 100, 1000]` |
| `alphas` | list | `[1, 10]` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L323)</sub>

### `executable_loop_summarise_results`

```python
executable_loop_summarise_results(baseDir=None, prefix='Execution')
```

| input | type | default |
|---|---|---|
| `baseDir` | – | `None` |
| `prefix` | – | `'Execution'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L366)</sub>

### `optimise`

```python
optimise(setupXML_path=None)
```

| input | type | default |
|---|---|---|
| `setupXML_path` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/commands.py#L451)</sub>
