# API reference

The browsable reference is **[docs/api/index.md](api/index.md)**: every module, with a clickable list of its functions and classes, each with its call, inputs (type, default), return value, docstring and source link.

Regenerate it after changing docstrings:

```
python -m bioscout.devtools.api_docs
```

```{eval-rst}
.. autosummary::
   :toctree: _autosummary
   :recursive:

   bioscout.session
   bioscout.core
   bioscout.simulate
   bioscout.model
   bioscout.emg
   bioscout.plot
   bioscout.utils
   bioscout.config
   bioscout.cli
   bioscout.pipeline
```
