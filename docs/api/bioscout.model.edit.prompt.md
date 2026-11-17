# `bioscout.model.edit.prompt`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/prompt.py)

Interactive prompt helpers, in one place.

``change_moment_arms/cli.py`` and ``__main__.py``'s ``run_tps_mode`` each carry  
their own byte-identical copy of ``_ask`` and ``_pick``. This is that code,  
once, with the model-aware bits added: a parameter can name a  
``choices_from`` and the prompt fills the option list from the model in hand.

The house conventions these preserve, because users have learned them:  
defaults shown in ``[brackets]``, Enter accepts, numbered pick lists, and  
nothing is written until a confirmation step.

## Contents

- [`ask`](#ask) — Free-text question with a default and optional validation.
- [`pick`](#pick) — Numbered chooser. Returns a string, or a list when ``allow_multiple``.
- [`confirm`](#confirm) — 
- [`ask_param`](#ask_param) — Ask for one :class:`~bioscout.model.edit.spec.Param`, typed and validated.
- [`ask_params`](#ask_params) — Walk every parameter of an op. Presets are shown as the default.

### `ask`

```python
ask(
    prompt: str,
    default: Optional[str] = None,
    choices: Optional[Sequence[str]] = None
) -> str
```

| input | type | default |
|---|---|---|
| `prompt` | str | required |
| `default` | Optional[str] | `None` |
| `choices` | Optional[Sequence[str]] | `None` |

**returns** `str`

Free-text question with a default and optional validation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/prompt.py#L22)</sub>

### `pick`

```python
pick(
    prompt: str,
    options: Sequence[str],
    default: Optional[str] = None,
    allow_multiple: bool = False,
    allow_all: bool = False
) -> Any
```

| input | type | default |
|---|---|---|
| `prompt` | str | required |
| `options` | Sequence[str] | required |
| `default` | Optional[str] | `None` |
| `allow_multiple` | bool | `False` |
| `allow_all` | bool | `False` |

**returns** `Any`

Numbered chooser. Returns a string, or a list when ``allow_multiple``.

Accepts numbers or the names themselves, because a list of 100 muscles is  
faster to type than to count through.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/prompt.py#L38)</sub>

### `confirm`

```python
confirm(prompt: str, default: bool = False) -> bool
```

| input | type | default |
|---|---|---|
| `prompt` | str | required |
| `default` | bool | `False` |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/prompt.py#L71)</sub>

### `ask_param`

```python
ask_param(param, model=None, current=None)
```

| input | type | default |
|---|---|---|
| `param` | – | required |
| `model` | – | `None` |
| `current` | – | `None` |

Ask for one :class:`~bioscout.model.edit.spec.Param`, typed and validated.

This is the function that makes the registry pay off: every op gets a  
correct prompt, with the right option list and the right coercion, without  
anyone writing prompt code per op.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/prompt.py#L76)</sub>

### `ask_params`

```python
ask_params(op, model=None, preset=None) -> dict
```

| input | type | default |
|---|---|---|
| `op` | – | required |
| `model` | – | `None` |
| `preset` | – | `None` |

**returns** `dict`

Walk every parameter of an op. Presets are shown as the default.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/prompt.py#L129)</sub>
