# `bioscout.cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/cli.py)

The bioscout command line: ten verbs instead of sixty-six flags.

    bioscout                 the verb list (the desktop GUI was removed in 3.1:  
                             use BioScout Web, https://basgoncalves.github.io/bioscout-web/)  
    bioscout help [VERB]     this, or one verb's detail  
    bioscout init            start a project (folders, models, project.yaml)  
    bioscout web             open BioScout Web in the browser (--local: a local checkout)  
    bioscout settings        this computer's settings (~/.bioscout/settings.yaml); also -settings  
    bioscout model           check / edit / compare / tune-ma / scale / tps / mri2msk  
    bioscout simulate        run an OpenSim/CEINMS stage on a session (or mrs)  
    bioscout session         new / export / classify / check-grf / ingest /  
                             reset -- reads  
                             the results `simulate` writes, so it comes after it  
    bioscout plot            figures, summaries, Collings ranking  
    bioscout utils           env / install / md2pdf / qr_code / pylance

  
**Why this module exists**

The flat parser had grown to 66 options. Nineteen of them were basketball shot  
detection and fitness-tracker imports; of the remaining forty-seven, **twenty-five  
existed only to modify another flag** — their help text literally began  
``With --X:``. ``--top``, ``--side``, ``--metric`` and ``--skip`` mean nothing  
without ``--collings``; ``--toc``, ``--bib`` and ``--keep-docx`` mean nothing  
without ``--md2pdf``. A subcommand tree makes all twenty-five disappear from the  
root help without deleting a single one: they live under the verb they belong to.

Two design rules, both load-bearing:

1. **This module imports nothing but the standard library.** ``bioscout -h`` used  
   to run the conda env check and import ``utils.openSim`` before it could print  
   a help screen. Help must be instant and must work in a broken environment —  
   it is what you reach for when nothing else runs.  
2. **The old flags still work.** They are hidden from help and print one line  
   naming the new form. Two real projects drive bioscout by flag from shell  
   scripts; breaking them to tidy a help screen is a bad trade. Drop the aliases  
   one release after everything has migrated.

  
**How a verb reaches the old code**

Most verbs are *translated*: the parsed subcommand is rewritten into the legacy  
flag argv, and ``__main__.py`` proceeds exactly as before, reading it off the  
module-global ``args`` the same way it always did. Verbs whose implementation  
is already self-contained and dependency-light (``model check``, ``utils env``)  
are dispatched directly and never load the scientific stack at all.

## Contents

- [`build_parser`](#build_parser) — 
- [`legacy_hint`](#legacy_hint) — One-line nudge for the first legacy flag in ``argv``, or None.
- [`route`](#route) — Decide what a new-style argv means.
- [`main`](#main) — Standalone entry: ``python -m bioscout.cli <verb> ...``.

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/cli.py#L93)</sub>

### `legacy_hint`

```python
legacy_hint(argv: Sequence[str]) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `argv` | Sequence[str] | required |

**returns** `Optional[str]`

One-line nudge for the first legacy flag in ``argv``, or None.

Deliberately a hint and not a warning: these still work, and a script that  
prints a WARNING on every run trains people to ignore warnings.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/cli.py#L580)</sub>

### `route`

```python
route(argv: Sequence[str]) -> Tuple[str, object]
```

| input | type | default |
|---|---|---|
| `argv` | Sequence[str] | required |

**returns** `Tuple[str, object]`

Decide what a new-style argv means.

Returns ``("exit", code)`` when the verb is finished, or  
``("legacy", [flags])`` when ``__main__`` should carry on with the old  
machinery using the translated argv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/cli.py#L1025)</sub>

### `main`

```python
main(argv: Optional[Sequence[str]] = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | Optional[Sequence[str]] | `None` |

**returns** `int`

Standalone entry: ``python -m bioscout.cli <verb> ...``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/cli.py#L1130)</sub>
