# `bioscout.session`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/__init__.py)

Everything ``bioscout session`` backs: a capture session on disk.

    recording.py        Session   -- one recording-session folder (bs.Session)  
    iteration.py        Iteration -- one model iteration: the runnable unit  
    config.py           session.yaml: read / write / scaffold, EMG maps, calibration  
    layout.py           where things live inside a session folder  
    validation.py       trial-folder checks (GUI)  
    form.py             the session.yaml form/scaffold  
    paths.py            path resolution helpers  
    exportC3D.py        `session export` -- c3d -> markers/GRF/EMG  
    motion_detect.py    find a capture's actual movement window  
    movement_detector/  `session classify`

``Session``/``Iteration``/... are re-exported lazily so  
``from bioscout.session import Session`` works without importing the whole  
scientific stack at package import time.
