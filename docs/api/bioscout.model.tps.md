# `bioscout.model.tps`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/__init__.py)

bioscout.model.tps  
========================

Thin-plate-spline (TPS) personalisation of OpenSim musculoskeletal models from  
segmented MRI bone geometry.

Originally a refactor of the notebook pipeline by Ekaterina Stansfield  
(katya-stanzy/thin-plate-spline_personalised_muscoloskeletal_model), brought  
into bioscout with three changes that make it usable across model families:

* **OpenSim 3.x and 4.x** ``.osim`` files are both read and written  
  (``osim_format``). Rajagopal2015 as distributed is a Version 30000 document;  
  the original only handled Version 40000+.  
* **No third-party TPS dependency** — ``_tps_backend`` implements the same  
  spline in numpy, used automatically when the ``thin-plate-spline`` package  
  isn't installed.  
* **Frame-compatibility checking** (``model_compat``) so one bone-landmark  
  template can be reused across generic models *and fail loudly* when the  
  frames don't actually match, rather than silently producing a wrong warp.

Importing this package has no side effects. Heavy dependencies (``opensim``,  
``pyvista``) are imported lazily by the modules that need them, so this works  
in a plain numpy/pandas environment — bone meshes simply aren't warped when  
``pyvista`` is missing (logged, not fatal).

  
**Typical use**

Standalone::

    from bioscout.model.tps import PersonalisationConfig, Personaliser  
    Personaliser(PersonalisationConfig.from_yaml("config.yaml")).run()

From a bioscout session::

    from bioscout.model.tps import personalise_iteration  
    personalise_iteration("simulations/Athlete_03/25_03_31", "rajagopal",  
                          mri_landmarks=".../landmarks.mrk.json")

Command line::

    python -m bioscout.model.tps --config config.yaml

## Available as `bioscout.model.tps.<name>`

- [`bioscout.model.tps.PersonalisationConfig`](bioscout.model.tps.config.md#personalisationconfig) — from `bioscout.model.tps.config`
- [`bioscout.model.tps.SubjectInfo`](bioscout.model.tps.config.md#subjectinfo) — from `bioscout.model.tps.config`
- [`bioscout.model.tps.OneBodyTPS`](bioscout.model.tps.tps.md#onebodytps) — from `bioscout.model.tps.tps`
- [`bioscout.model.tps.Personaliser`](bioscout.model.tps.pipeline.md#personaliser) — from `bioscout.model.tps.pipeline`
- [`bioscout.model.tps.PersonalisationResult`](bioscout.model.tps.pipeline.md#personalisationresult) — from `bioscout.model.tps.pipeline`
- [`bioscout.model.tps.personalise_iteration`](bioscout.model.tps.bioscout_adapter.md#personalise_iteration) — from `bioscout.model.tps.bioscout_adapter`
- [`bioscout.model.tps.compare_bone_frames`](bioscout.model.tps.model_compat.md#compare_bone_frames) — from `bioscout.model.tps.model_compat`
