# `bioscout.user_settings`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/user_settings.py)

bioscout's own settings for this computer (not a project's): ``bioscout -settings``.

One YAML file, ``~/.bioscout/settings.yaml`` (``BIOSCOUT_SETTINGS`` points elsewhere),  
read at the start of every ``bioscout`` command. Each setting maps to the environment  
variable bioscout already reads; a variable you set yourself in the shell wins over the  
file, the file wins over bioscout's default.

    bioscout -settings            open the file in your editor (written with defaults first)  
    bioscout -settings --show     print the values in effect and where each comes from  
    bioscout -settings --reset    rewrite the file with the defaults

## Contents

- [`path`](#path) — 
- [`write_default`](#write_default) — 
- [`load`](#load) — -> {name: value} from the file (missing names: default).
- [`apply`](#apply) — Put the file's values into the environment (a variable already set wins). -> values.
- [`command`](#command) — ``bioscout -settings [--show | --reset]``.

### `path`

```python
path()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/user_settings.py#L34)</sub>

### `write_default`

```python
write_default(p=None)
```

| input | type | default |
|---|---|---|
| `p` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/user_settings.py#L46)</sub>

### `load`

```python
load()
```

-> {name: value} from the file (missing names: default).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/user_settings.py#L58)</sub>

### `apply`

```python
apply()
```

Put the file's values into the environment (a variable already set wins). -> values.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/user_settings.py#L72)</sub>

### `command`

```python
command(args)
```

| input | type | default |
|---|---|---|
| `args` | – | required |

``bioscout -settings [--show | --reset]``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/user_settings.py#L87)</sub>
