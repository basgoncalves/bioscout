#!/usr/bin/env python3
"""
Build Digital_Athlete.osim: personalised lower limb (GPK_v4_016) + generic
upper body/spine/ball (Full_Body_with_ball) in one OpenSim model.

Strategy
--------
Full_Body_with_ball.osim already shares identical body/joint names and
architecture for the whole lower limb with GPK_v4_016.osim (same "Lerner
knee" template). So the merge is a text-level swap: take Full_Body_with_ball
as the base (it has the full muscle set, spine, arms, ball) and replace,
by name, every lower-limb Body / Joint / Muscle block with GPK_v4_016's
personalised version. Everything else (sacrum, lumbar1-5, torso, Abdomen,
shoulder girdle, arms, ball, and ~474 non-leg muscles) is kept untouched
from Full_Body_with_ball.

Checked before writing this script (see Digital Athlete/README.md):
  - all 101 GPK_v4_016 muscles exist under the same name in Full_Body_with_ball
  - no *kept* muscle references a wrap object that lives on a swapped body
  - the only kept joint touching the swap boundary is "sacrumjnt"
    (pelvis -> sacrum). Its offset frame keeps Full_Body_with_ball's
    generic translation, so the spine attachment is NOT re-scaled to the
    personalised pelvis -> check this visually in the OpenSim GUI.
"""
import re
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC = os.path.dirname(HERE)                       # bioscout/models/generic
GPK_PATH = os.path.join(GENERIC, "GPK", "GPK_v4_016.osim")
FB_PATH = os.path.join(GENERIC, "Full_Body_with_ball", "Full_Body_with_ball.osim")
OUT_PATH = os.path.join(HERE, "Digital_Athlete.osim")

BODY_TAG = "Body"
JOINT_TAG = r"CustomJoint|WeldJoint|PinJoint|BallJoint|FreeJoint|UniversalJoint"
MUSCLE_TAG = r"Millard2012EquilibriumMuscle|Thelen2003Muscle|Schutte1993Muscle"

LOWER_LIMB_BODIES = [
    "pelvis",
    "femur_r", "femoral_cond_r", "sagittal_articulation_frame_r", "med_cond_r",
    "lat_cond_r", "tibial_plat_r", "tibia_r", "patella_r", "talus_r",
    "calcn_r", "toes_r",
    "femur_l", "femoral_cond_l", "sagittal_articulation_frame_l", "med_cond_l",
    "lat_cond_l", "tibial_plat_l", "tibia_l", "patella_l", "talus_l",
    "calcn_l", "toes_l",
]

LOWER_LIMB_JOINTS = [
    "ground_pelvis",
    "hip_r", "femur_weld_r", "Lerner_knee_r", "med_cond_joint_r",
    "lat_cond_joint_r", "med_cond_weld_r", "tibial_plat_weld_r", "fem_pat_r",
    "ankle_r", "subtalar_r", "mtp_r",
    "hip_l", "femur_weld_l", "Lerner_knee_l", "med_cond_joint_l",
    "lat_cond_joint_l", "med_cond_weld_l", "tibial_plat_weld_l", "fem_pat_l",
    "ankle_l", "subtalar_l", "mtp_l",
]


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def find_block(text, tag_pattern, name):
    pat = re.compile(r'<(' + tag_pattern + r') name="' + re.escape(name) + r'">.*?</\1>', re.S)
    m = pat.search(text)
    if not m:
        raise ValueError(f"block not found: {tag_pattern!r} name={name!r}")
    return m.group(0), m.span()


def replace_named_block(text, tag_pattern, name, new_block):
    _, span = find_block(text, tag_pattern, name)
    return text[:span[0]] + new_block + text[span[1]:]


def gpk_muscle_names(gpk_text):
    return re.findall(r'<(?:' + MUSCLE_TAG + r') name="([^"]+)">', gpk_text)


def main():
    gpk = read(GPK_PATH)
    fb = read(FB_PATH)
    out = fb

    swapped = {"bodies": 0, "joints": 0, "muscles": 0}

    for name in LOWER_LIMB_BODIES:
        gblock, _ = find_block(gpk, BODY_TAG, name)
        out = replace_named_block(out, BODY_TAG, name, gblock)
        swapped["bodies"] += 1

    for name in LOWER_LIMB_JOINTS:
        gblock, _ = find_block(gpk, JOINT_TAG, name)
        out = replace_named_block(out, JOINT_TAG, name, gblock)
        swapped["joints"] += 1

    for name in gpk_muscle_names(gpk):
        gblock, _ = find_block(gpk, MUSCLE_TAG, name)
        out = replace_named_block(out, MUSCLE_TAG, name, gblock)
        swapped["muscles"] += 1

    out = out.replace(
        '<Model name="Full_Body_with_ball">',
        '<Model name="Digital_Athlete_GPKv4016_lowerlimb_FullBody_upperlimb">',
        1,
    )

    os.makedirs(HERE, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(out)

    print("swapped:", swapped)

    tree = ET.parse(OUT_PATH)
    root = tree.getroot()
    n_bodies = len(root.findall(".//BodySet/objects/Body"))
    n_joints = sum(len(root.findall(f".//JointSet/objects/{c}"))
                   for c in ["CustomJoint", "WeldJoint", "PinJoint", "BallJoint", "FreeJoint", "UniversalJoint"])
    n_muscles = sum(len(root.findall(f".//ForceSet/objects/{c}"))
                     for c in ["Millard2012EquilibriumMuscle", "Thelen2003Muscle", "Schutte1993Muscle"])
    print(f"XML OK. bodies={n_bodies} joints={n_joints} muscles={n_muscles}")
    print("wrote:", OUT_PATH)


if __name__ == "__main__":
    main()
