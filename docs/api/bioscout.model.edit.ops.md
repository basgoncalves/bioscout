# `bioscout.model.edit.ops`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/__init__.py)

Importing this package populates :data:`bioscout.model.edit.spec.REGISTRY`.

Every module here must be importable WITHOUT OpenSim — the ``import opensim``  
lives inside each op function, never at module scope. That is what lets the CLI  
list operations, validate a recipe and build a GUI form on a machine that cannot  
run them, and it is why ``Op.needs_opensim`` is a declared fact rather than  
something discovered by a failed import.

## Available as `bioscout.model.edit.ops.<name>`

- [`bioscout.model.edit.ops.coordinates`](bioscout.model.edit.ops.md#coordinates) — from `bioscout.model.edit.ops`
- [`bioscout.model.edit.ops.inspect`](bioscout.model.edit.ops.md#inspect) — from `bioscout.model.edit.ops`
- [`bioscout.model.edit.ops.markers`](bioscout.model.edit.ops.md#markers) — from `bioscout.model.edit.ops`
- [`bioscout.model.edit.ops.moment_arms`](bioscout.model.edit.ops.md#moment_arms) — from `bioscout.model.edit.ops`
- [`bioscout.model.edit.ops.reserves`](bioscout.model.edit.ops.md#reserves) — from `bioscout.model.edit.ops`
- [`bioscout.model.edit.ops.scale`](bioscout.model.edit.ops.md#scale) — from `bioscout.model.edit.ops`
- [`bioscout.model.edit.ops.strength`](bioscout.model.edit.ops.md#strength) — from `bioscout.model.edit.ops`
