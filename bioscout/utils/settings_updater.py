"""Migrate a project's settings.py to the current schema version.

Reads the project's existing settings.py, extracts user-customised values
(PROJECT_ROOT, SUBJECTS, EMG mappings, DOF lists, model paths, …) and injects
them into a fresh copy of the source (bioscout/settings.py) template, so the
project gets all new fields while keeping every value the user had set.

Public API
----------
    build_updated_settings(project_settings_path) -> str
        Returns the text of the updated settings.py.

    write_updated_settings(project_settings_path) -> list[str]
        Writes the file in-place (backs up the old one first) and returns a
        list of human-readable lines describing what was preserved.
"""

from __future__ import annotations

import ast
import re
import shutil
import datetime
from pathlib import Path
from typing import Optional

# The canonical (source) settings.py — always up-to-date
_SRC_SETTINGS = Path(__file__).parent.parent / "settings.py"

# ── AST helpers ──────────────────────────────────────────────────────────────

def _node_src(lines: list[str], node: ast.AST) -> str:
    """Return the raw source text of an AST node."""
    s = node.lineno - 1
    e = node.end_lineno - 1
    if s == e:
        return lines[s][node.col_offset : node.end_col_offset]
    parts = [lines[s][node.col_offset :]]
    for i in range(s + 1, e):
        parts.append(lines[i])
    parts.append(lines[e][: node.end_col_offset])
    return "\n".join(parts)


def _top_assignment_value(tree: ast.Module, lines: list[str],
                          name: str) -> Optional[str]:
    """Extract value source text of a top-level ``name = <value>`` assignment."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return _node_src(lines, node.value)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return _node_src(lines, node.value)
    return None


def _class_attr_value(tree: ast.Module, lines: list[str],
                      class_name: str, attr_name: str) -> Optional[str]:
    """Extract value source text of ``class_name.attr_name = <value>``."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name) and t.id == attr_name:
                            return _node_src(lines, item.value)
    return None


# ── Template replacement helpers ─────────────────────────────────────────────

def _replace_top_assignment(template: str, name: str, new_val: str) -> str:
    """Replace the RHS of a simple top-level assignment in template text.

    Handles single-line values only; multi-line values (dicts/lists) are
    handled by _replace_class_attr which uses AST offsets.
    """
    # Match the first occurrence:  NAME  =  <rest of line>
    pattern     = rf"^({re.escape(name)}\s*=\s*)(.+)$"
    replacement = rf"\g<1>{new_val}"
    updated = re.sub(pattern, replacement, template, count=1, flags=re.MULTILINE)
    return updated


def _replace_in_template(template: str, class_name: Optional[str],
                         attr_name: str, new_val: str) -> str:
    """Replace an assignment value in the template using AST-precise offsets.

    Works for both top-level assignments (class_name=None) and class body
    assignments.  Re-parses after the replacement so subsequent calls stay
    accurate.
    """
    try:
        tree  = ast.parse(template)
        lines = template.splitlines(keepends=True)
    except SyntaxError:
        return template

    def _find_node() -> Optional[ast.Assign]:
        if class_name is None:
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == attr_name:
                            return node
        else:
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for t in item.targets:
                                if isinstance(t, ast.Name) and t.id == attr_name:
                                    return item
        return None

    assign = _find_node()
    if assign is None:
        return template

    val   = assign.value
    vs    = val.lineno - 1        # 0-indexed start line
    ve    = val.end_lineno - 1    # 0-indexed end line
    vc    = val.col_offset
    vce   = val.end_col_offset

    if vs == ve:
        # Single-line replacement
        line = lines[vs]
        lines[vs] = line[:vc] + new_val + line[vce:]
    else:
        # Multi-line: replace all lines of the old value
        first = lines[vs]
        last  = lines[ve]
        lines[vs] = first[:vc] + new_val + "\n"
        for i in range(vs + 1, ve + 1):
            lines[i] = ""
        # last line's remainder (anything after the old value end) is lost;
        # for dicts/lists the closing bracket is included in end_col_offset

    return "".join(lines)


# ── Inventory of values to preserve ─────────────────────────────────────────

# (class_name or None for top-level, attr_name, description)
_PRESERVE: list[tuple[Optional[str], str, str]] = [
    # Top-level
    (None, "PROJECT_ROOT",     "Project root path"),
    (None, "PROJECT_NAME",     "Project name"),
    (None, "SUBJECTS",          "Subject ID list"),
    # Analysis / comparison config
    (None, "SESSION",             "Session name"),
    (None, "trial_list",          "Trials to analyse"),
    (None, "SUBJECTS",            "Subjects (Subject objects)"),
    (None, "CONTRASTS",           "Comparison contrasts"),
    (None, "MODELS_TO_FLIP_KNEE", "Knee sign-flip models"),
    (None, "MUSCLE_GROUPS",       "Muscle groups"),
    (None, "DOFS",                "Degrees of freedom"),
    # BatchSettings
    ("BatchSettings", "generic_model",       "OpenSim model path"),
    ("BatchSettings", "markerset",           "Marker set file"),
    ("BatchSettings", "dof_list",            "Degrees of freedom"),
    ("BatchSettings", "emg_muscle_mapping",  "EMG → muscle mapping"),
    ("BatchSettings", "emg_sampling_freq",   "EMG sampling frequency"),
    ("BatchSettings", "emg_label_default",   "EMG label default"),
    ("BatchSettings", "emg_string_list",     "EMG string list"),
    ("BatchSettings", "right_foot_markers",  "Right foot markers"),
    ("BatchSettings", "left_foot_markers",   "Left foot markers"),
    ("BatchSettings", "trc_lateral_axis",    "TRC lateral axis"),
    ("BatchSettings", "trc_vertical_axis",   "TRC vertical axis"),
    ("BatchSettings", "trc_ap_axis",         "TRC A/P axis"),
    ("BatchSettings", "trials_to_skip",      "Trials to skip"),
    ("BatchSettings", "grf_axis_map",        "GRF axis map"),
    ("BatchSettings", "grf_cop_scale_to_m",  "GRF CoP scale"),
    ("BatchSettings", "grf_moment_scale",    "GRF moment scale"),
    ("BatchSettings", "grf_moment_sign",     "GRF moment sign"),
    # CEINMSSettings
    ("CEINMSSettings", "calibration_trial_names", "CEINMS calibration trials"),
    ("CEINMSSettings", "emg_muscle_mapping",       "CEINMS EMG → muscle mapping"),
    ("CEINMSSettings", "num_synergies",             "Number of synergies"),
    ("CEINMSSettings", "dof_set",                   "CEINMS DOF set"),
    # UISettings
    ("UISettings", "DEFAULT_TAB_ON_LAUNCH",         "Default launch tab"),
    # RecordingSettings
    ("RecordingSettings", "DEFAULT_VIDEO_ANALYSIS_MODEL", "Default pose model"),
    ("RecordingSettings", "DEFAULT_POSE_MAX_DELTA_PX",    "Pose smoothing delta"),
]


# ── Public API ────────────────────────────────────────────────────────────────

def build_updated_settings(project_settings_path: Path) -> tuple[str, list[str]]:
    """Return (updated_text, preserved_descriptions).

    updated_text            — full text of the new settings.py
    preserved_descriptions  — human-readable list of what was carried forward
    """
    old_src   = project_settings_path.read_text(encoding="utf-8", errors="replace")
    old_lines = old_src.splitlines()
    try:
        old_tree = ast.parse(old_src)
    except SyntaxError as e:
        raise ValueError(f"Cannot parse existing settings.py: {e}") from e

    template = _SRC_SETTINGS.read_text(encoding="utf-8", errors="replace")
    preserved: list[str] = []

    for cls, attr, desc in _PRESERVE:
        if cls is None:
            val_src = _top_assignment_value(old_tree, old_lines, attr)
        else:
            val_src = _class_attr_value(old_tree, old_lines, cls, attr)

        if val_src is None:
            continue  # old file didn't have this — skip (template default used)

        try:
            template = _replace_in_template(template, cls, attr, val_src)
            preserved.append(f"  ✓  {desc}  ({(cls + '.') if cls else ''}{attr})")
        except Exception:
            preserved.append(f"  ⚠  {desc}  ({(cls + '.') if cls else ''}{attr}) — skipped (parse error)")

    return template, preserved


def write_updated_settings(project_settings_path: Path) -> list[str]:
    """Write updated settings.py in-place, backing up the original first.

    Returns the list of preserved-value description lines.
    """
    new_text, preserved = build_updated_settings(project_settings_path)

    # Back up original
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = project_settings_path.with_name(f"settings.py.bak_{ts}")
    shutil.copy2(project_settings_path, bak)

    project_settings_path.write_text(new_text, encoding="utf-8")
    return preserved
