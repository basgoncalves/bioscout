"""
Markerless single-camera movement analysis: video -> pose -> kinematics ->
reps -> inverse dynamics -> muscle-force estimate.

Layout
------
``kinematics.py``  what every movement shares: landmark naming, angle and
                   smoothing helpers, pixel-to-metre scaling, view quality.
``pullup.py``      the pull-up activity.
``squat.py``       the squat activity.
``session.py``     orchestration; ``ACTIVITIES`` is the registry, and adding a
                   movement means adding an entry there plus a module beside
                   pullup.py -- not editing ``analyse()``.
``pose.py``        MediaPipe extraction, kept behind a thin interface.
``dynamics.py``    sagittal inverse dynamics; GRF derived, not assumed.
``forces.py``      pluggable force model (the bundled surrogate is NOT valid
                   for these activities -- see models/MODEL_CARD.md).

No activity owns the generic names. That is deliberate: this arrived as
"pullupkit", where the pull-up held ``build_features``/``find_reps``/
``DRIVEN_COORDS`` in the shared module and the squat had to qualify all of its
own, so "the pipeline" silently meant "the pull-up pipeline" and a third
movement had nowhere obvious to go.

Relationship to the rest of ``movement_detector``
-------------------------------------------------
The surrounding package works from marker-based mocap. This subpackage works
from 2-D image landmarks off a single camera, which is a different measurement
with different failure modes: no left/right separation, no out-of-plane motion,
and a pixel scale that depends on the subject's stated height.

There is an overlap to resolve: ``movement_detector/pullup.py`` on the
``pull_ups`` branch counts pull-up reps by a different route, built on
``features``/``detector``. It is unmerged and does not do kinematics export or
dynamics. Two rep counters should not both survive -- pick one before either
ships.

Relationship to BioScout Web
----------------------------
This is the desktop source of truth for the browser app
(https://github.com/basgoncalves/bioscout-web), whose ported JavaScript is a
line-by-line translation of these modules. The two are held together by a
fixture, ``reference.json``, checked from both sides in that repository's CI.
Change anything numerical here and that check fails until the fixture and the
port are updated with it.

Usage
-----
    from bioscout.movement_detector.markerless import analyse, load_poses

    poses, fps = load_poses("poses.json")
    result = analyse(poses, fps, height_m=1.78, activity="squat")
"""
from .session import ACTIVITIES, analyse           # noqa: F401
from .pose import load_poses, PoseBackendUnavailable  # noqa: F401

__all__ = ["ACTIVITIES", "analyse", "load_poses", "PoseBackendUnavailable"]
