# `bioscout.model`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/__init__.py)

Model integrity: does every ``.osim`` still find its bones?

OpenSim resolves a mesh filename relative to the folder holding the ``.osim``.  
Move a model — or move the geometry out from under it, which is what tidying a  
``models/`` folder does, and what writing a personalised model into a new  
subfolder does — and OpenSim loads it with every muscle, marker and joint  
intact and **no bones at all**, with no exception and nothing in the log.

This package is the check for that, plus the two quieter variants of it:  
handling only one of the OpenSim 3 / OpenSim 4 mesh tags, and filename case  
differences that resolve on Windows and fail everywhere else.

    from bioscout.model import verify_model, verify_tree, format_text

    print(verify_model("subject021.osim").headline)  
    report = verify_tree(["models", "generic models"])  
    print(format_text(report))  
    raise SystemExit(report.exit_code())

Command line::

    python -m bioscout.model --verify  
    bioscout --model --verify --strict

Pure stdlib — no OpenSim, no numpy — so it runs during preflight and in a bare  
environment.

## Available as `bioscout.model.<name>`

- [`bioscout.model.GEOMETRY_TAGS`](bioscout.model.geometry.md#geometry_tags) — from `bioscout.model.geometry`
- [`bioscout.model.PASSING_TIERS`](bioscout.model.geometry.md#passing_tiers) — from `bioscout.model.geometry`
- [`bioscout.model.TIER_ORDER`](bioscout.model.geometry.md#tier_order) — from `bioscout.model.geometry`
- [`bioscout.model.GeometryRef`](bioscout.model.geometry.md#geometryref) — from `bioscout.model.geometry`
- [`bioscout.model.bundled_geometry_dir`](bioscout.model.geometry.md#bundled_geometry_dir) — from `bioscout.model.geometry`
- [`bioscout.model.geometry_refs`](bioscout.model.geometry.md#geometry_refs) — from `bioscout.model.geometry`
- [`bioscout.model.resolve_ref`](bioscout.model.geometry.md#resolve_ref) — from `bioscout.model.geometry`
- [`bioscout.model.search_roots_for`](bioscout.model.geometry.md#search_roots_for) — from `bioscout.model.geometry`
- [`bioscout.model.ModelReport`](bioscout.model.verify.md#modelreport) — from `bioscout.model.verify`
- [`bioscout.model.TreeReport`](bioscout.model.verify.md#treereport) — from `bioscout.model.verify`
- [`bioscout.model.find_models`](bioscout.model.verify.md#find_models) — from `bioscout.model.verify`
- [`bioscout.model.format_text`](bioscout.model.verify.md#format_text) — from `bioscout.model.verify`
- [`bioscout.model.verify_model`](bioscout.model.verify.md#verify_model) — from `bioscout.model.verify`
- [`bioscout.model.verify_tree`](bioscout.model.verify.md#verify_tree) — from `bioscout.model.verify`
