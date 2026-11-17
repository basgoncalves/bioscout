# `bioscout.model.mri2msk.cli`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/cli.py)

`bioscout model mri2msk`: the MRI2MSK steps from the command line.

bioscout model mri2msk gui                 the desktop GUI (steps 1-8 + Post-Warp tab)  
bioscout model mri2msk status --participant DIR --base-model FILE  
bioscout model mri2msk <step> --participant DIR --base-model FILE  
bioscout model mri2msk 3 --participant DIR --base-model FILE --n 25  
    (auto landmarks; --n one number for all bones or e.g. pelvis=30,tibia_l=20)  
bioscout model mri2msk post --participant DIR --base-model FILE [--session DIR] [--mass KG]  
    (Post-Warp on a BioScout session: export, scale, IK, ID, SO, JRA, JCF contributions)

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

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/cli.py#L26)</sub>
