"""
Markerless single-camera movement analysis: video -> pose -> kinematics ->
reps -> inverse dynamics -> muscle-force estimate.

This is the desktop source of truth for the BioScout Web browser app
(https://github.com/basgoncalves/bioscout-web), whose ``pullupkit.js`` is a
line-by-line port of these modules. The two are held together by a fixture,
``reference.json``, checked from both sides in that repository's CI -- see its
*Verification* section. Change anything numerical in here and that check will
fail until the fixture and the port are updated with it.

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

Usage
-----
    from bioscout.movement_detector.markerless import analyse, load_poses

    poses, fps = load_poses("poses.json")
    result = analyse(poses, fps, height_m=1.78, activity="squat")
"""
from .session import ACTIVITIES, analyse           # noqa: F401
from .pose import load_poses, PoseBackendUnavailable  # noqa: F401

__all__ = ["ACTIVITIES", "analyse", "load_poses", "PoseBackendUnavailable"]
