# `bioscout.model.edit.recipe`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/recipe.py)

A model build, written down.

A recipe is a YAML file: a base model and an ordered list of operations. Each  
step's output feeds the next unless the step says ``from:``, which is what makes  
the SO/CEINMS pair expressible -- they are a *branch*, not a chain:

    scaled.osim -> scaled_opt_N10.osim ------------------> (CEINMS model)  
                                        \  
                                         -> _mvicx3.00.osim (SO model)

Today that sequence lives as imperative code in the project's ``settings.py``  
and as an interactive session for the moment-arm variants, which is why the  
``gpk_optimised`` models could not be rebuilt from their provenance -- there was  
none. A recipe is re-runnable, diffable, and reviewable.

Example::

    base: "generic models/GPK_v4/GPK_v4_016.osim"  
    out_dir: "simulations/Athlete_03/25_03_31/3_iterations/gpk"  
    steps:  
      - op: scale  
        static_trc: "../../2_experimental/Static_01/marker_experimental.trc"  
        marker_set: "setupFiles/markers_powerlifter.xml"  
        mass: 91.01  
        save_as: scaled.osim  
      - op: muscle_opt  
        n_eval: 10  
        save_as: scaled_opt_N10.osim          # the CEINMS model  
      - op: mvic  
        factor: 3.0  
        save_as: scaled_opt_N10_mvicx3.00.osim  # the SO model  
      - op: check_paths                        # verify, from the CEINMS model  
        from: scaled_opt_N10.osim

Paths are resolved against ``root`` (the project directory), or against the  
recipe file's own folder when no root is given, so a recipe is portable.

## Contents

- class [`RecipeError`](#recipeerror) — 
- [`load`](#load) — 
- [`validate_recipe`](#validate_recipe) — Check the whole recipe before running any of it.
- [`describe`](#describe) — Human-readable plan, including which steps need OpenSim.
- [`run`](#run) — Execute a recipe. Stops at the first failure and says which step it was.

<a id="recipeerror"></a>

## class `RecipeError`(ValueError)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/recipe.py#L52)</sub>

### `load`

```python
load(path) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Dict[str, Any]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/recipe.py#L56)</sub>

### `validate_recipe`

```python
validate_recipe(doc: Dict[str, Any], root: Path) -> List[str]
```

| input | type | default |
|---|---|---|
| `doc` | Dict[str, Any] | required |
| `root` | Path | required |

**returns** `List[str]`

Check the whole recipe before running any of it.

A recipe that fails on step 7 after step 3 spent an hour on muscle  
optimisation is worse than useless, so every op name, every parameter name  
and every ``from:`` reference is checked up front.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/recipe.py#L78)</sub>

### `describe`

```python
describe(doc: Dict[str, Any], root: Path) -> List[str]
```

| input | type | default |
|---|---|---|
| `doc` | Dict[str, Any] | required |
| `root` | Path | required |

**returns** `List[str]`

Human-readable plan, including which steps need OpenSim.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/recipe.py#L126)</sub>

### `run`

```python
run(
    path,
    root=None,
    dry_run: bool = False,
    overwrite: bool = False,
    log=print
) -> List[OpResult]
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `root` | – | `None` |
| `dry_run` | bool | `False` |
| `overwrite` | bool | `False` |
| `log` | – | `print` |

**returns** `List[OpResult]`

Execute a recipe. Stops at the first failure and says which step it was.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/recipe.py#L145)</sub>
