# `bioscout.lab`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/__init__.py)

EXPERIMENTAL (3.x): the `bioscout lab` verb -- video and wearable tracking.

    load_tracking/     training-load tracking (`lab load-report`,  
                       `lab add-subject`, and `lab shots` via shot_analysis)  
    record/            video capture and pose tracking  
    subject_profile.py per-subject video-analysis profiles under  
                       ~/.powerlifting_app/subjects

NOT part of the OpenSim/CEINMS pipeline and not stable. Nothing is imported  
eagerly -- the tracking stack (cv2, mediapipe) stays unloaded until used.
