# `bioscout.utils.analyse`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/analyse.py)

Command-line entry point: run Analyse methods on a trial folder.

    python -m bioscout.utils.analyse <trial_dir> [method ...] [--project DIR]

  
**Examples**

    # default: regenerate the JRA SO-vs-CEINMS comparison figure  
    python -m bioscout.utils.analyse simulations/Athlete_03_Cateli/25_03_31/Walking_02

    # run several plotting methods in one go  
    python -m bioscout.utils.analyse .../Walking_02 plot_jra_comparison plot_so plot_ik_id_summary

    # bind an explicit project (otherwise the nearest parent settings.py is used)  
    python -m bioscout.utils.analyse .../Walking_02 --project C:/Users/Basilio/ucloud/Powerlifiting

If ``--project`` is omitted, the nearest parent directory containing a  
``settings.py`` is bound via ``bioscout.Project`` so that project-level config  
(JRA_COLUMNS, literature styling, model paths, log location, ...) comes from YOUR  
project rather than the bundled template.

## Contents

- [`main`](#main) — 

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/analyse.py#L37)</sub>
