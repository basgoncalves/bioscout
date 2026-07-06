# Conversation of .c3d files to OpenSim marker.trc and ground reaction forces
# grf.mot for the Sinergia data set. This script can be used for other data sets
# as well, however, the column names and transformation conventions may be
# different. Also, note that here we do not distinguish between left and right
# foot, therefore the setup_grf.xml file has to be manually updated.
#
# author: Dimitar Stanev <jimstanev@gmail.com>
# contributors: Celine Provins, George Papoulias
##
import os
import re
import shutil
import warnings
from matplotlib import pyplot as plt
import opensim
import pandas as pd
import c3d
import numpy as np

# Access functions defined in utils/__init__.py.
#
# These names are resolved LAZILY (PEP 562 module __getattr__) rather than bound
# at import time. Binding them eagerly created a circular dependency:
#   utils/__init__  ->  openSim  ->  exportC3D  ->  utils.filter_emg_file
# but filter_emg_file is bound near the END of utils/__init__ (from .emg), so at
# the moment exportC3D was imported the utils module was only partially
# initialized and the attribute did not exist yet (AttributeError). This is what
# broke `python -m bioscout`.
#
# Deferring the lookup until first *use* removes all import-time access to utils,
# so exportC3D now imports cleanly regardless of order, while utils is always
# fully initialized by the time these are actually called.
# NOTE: write_mot is intentionally NOT proxied here — this module defines its own
# write_mot() below.
#
# They are exposed as thin WRAPPER FUNCTIONS (not a module __getattr__): PEP 562
# __getattr__ only fires for `module.attr` access, NOT for bare-name lookups
# inside this module's own functions (e.g. `osimTools()`), which would raise
# NameError. Real module-level functions resolve correctly as globals and still
# defer the utils lookup to call time, so import stays cycle-free.
import sys as _sys
from pathlib import Path as _Path


def _resolve_utils():
    """Return the initialized utils module, whether it was loaded as a package
    submodule (bioscout.utils) or as a top-level module (utils)."""
    for _key in ("bioscout.utils", "utils"):
        _mod = _sys.modules.get(_key)
        if _mod is not None:
            return _mod
    _utils_path = str(_Path(__file__).parent)
    if _utils_path not in _sys.path:
        _sys.path.insert(0, _utils_path)
    import utils as _u
    return _u


def load_any_data_file(*args, **kwargs):
    return _resolve_utils().load_any_data_file(*args, **kwargs)


def filter_emg(*args, **kwargs):
    return _resolve_utils().filter_emg_file(*args, **kwargs)


def osimTools(*args, **kwargs):
    return _resolve_utils().osimTools(*args, **kwargs)


def _crop_trc_file_text_based(filepath, nan_threshold=0.5):
    """
    Crop NaN rows from TRC file using direct text parsing.

    This preserves the exact file format without any column manipulation.
    """
    try:
        # Read the entire file
        with open(filepath, 'r') as f:
            lines = f.readlines()

        # Find the header lines
        data_start_idx = -1
        for i, line in enumerate(lines):
            if 'Frame#' in line:
                data_start_idx = i
                break

        if data_start_idx < 0:
            print(f"Error: Could not find Frame# line in {filepath}")
            return None

        # Header: lines 0 to data_start_idx (inclusive of units line)
        # Line data_start_idx is: Frame# ...
        # Line data_start_idx + 1 is: units row
        # Line data_start_idx + 2 is: blank line (usually)
        # Data starts at data_start_idx + 3 or later

        # Determine where data actually starts (skip blank lines)
        header_end = data_start_idx + 2
        while header_end < len(lines) and lines[header_end].strip() == '':
            header_end += 1

        header_lines = lines[:header_end]
        # Ensure there's a blank line at the end of header
        if header_lines and header_lines[-1].strip() != '':
            header_lines.append('\n')

        data_lines = lines[header_end:]

        if len(data_lines) == 0:
            print(f"No data rows in {filepath}")
            return None

        # Parse data rows and find NaN rows
        valid_line_indices = []

        for idx, line in enumerate(data_lines):
            parts = line.strip().split('\t')
            if len(parts) < 3:  # Frame# + Time + at least one marker value
                continue

            # Count NaN values (skip Frame# and Time columns)
            nan_count = 0
            data_parts = parts[2:]  # Skip Frame# and Time
            for val in data_parts:
                try:
                    float(val)
                except (ValueError, TypeError):
                    if str(val).upper() in ['', 'NAN', 'NaN', '-1.#IND', '-1.#QNAN', '-1.#IND00000000']:
                        nan_count += 1

            nan_fraction = nan_count / len(data_parts) if data_parts else 0

            if nan_fraction <= nan_threshold:
                valid_line_indices.append(idx)

        if not valid_line_indices:
            print(f"No valid rows in {filepath}")
            return None

        # Find first and last valid indices
        start_idx = valid_line_indices[0]
        end_idx = valid_line_indices[-1] + 1

        rows_removed_start = start_idx
        rows_removed_end = len(data_lines) - end_idx

        # Get time values from first and last valid rows
        first_row_parts = data_lines[start_idx].strip().split('\t')
        last_row_parts = data_lines[end_idx - 1].strip().split('\t')

        try:
            start_time = float(first_row_parts[1])
            end_time = float(last_row_parts[1])
        except:
            start_time = 0.0
            end_time = 0.0

        # Check if we need to crop
        if rows_removed_start > 0 or rows_removed_end > 0:
            print(f"Cropping {filepath}:")
            print(f"  Removed {rows_removed_start} rows from beginning")
            print(f"  Removed {rows_removed_end} rows from end")
            print(f"  Kept {len(data_lines) - rows_removed_start - rows_removed_end} rows")

            # Reconstruct the file with new frame numbers
            new_data_lines = []
            for new_frame_num, orig_idx in enumerate(valid_line_indices, 1):
                parts = data_lines[orig_idx].strip().split('\t')
                # Replace frame number with new sequential number
                parts[0] = str(new_frame_num)
                new_data_lines.append('\t'.join(parts) + '\n')

            # Update NumFrames in metadata line (line 2)
            # Format: DataRate\tCameraRate\tNumFrames\tNumMarkers...
            metadata_line = header_lines[2]
            import re
            metadata_line = re.sub(r'(NumFrames\t)(\d+)', fr'\g<1>{len(new_data_lines)}', metadata_line)
            header_lines[2] = metadata_line

            # Write the file back
            with open(filepath, 'w') as f:
                f.writelines(header_lines)
                f.writelines(new_data_lines)

            print(f"  Saved cropped TRC file with {len(new_data_lines)} frames")

            return {
                'start_idx': start_idx,
                'end_idx': end_idx,
                'start_time': start_time,
                'end_time': end_time,
                'rows_removed_start': rows_removed_start,
                'rows_removed_end': rows_removed_end
            }
        else:
            print(f"No rows to crop in {filepath} (all within threshold)")
            return {
                'start_idx': 0,
                'end_idx': len(data_lines),
                'start_time': start_time,
                'end_time': end_time,
                'rows_removed_start': 0,
                'rows_removed_end': 0
            }

    except Exception as e:
        print(f"Error in _crop_trc_file_text_based: {e}")
        import traceback
        traceback.print_exc()
        return None


def crop_nans(filepath, nan_threshold=None):
    """
    Crop NaN values from the beginning and end of TRC/MOT/STO files.

    For TRC files, uses direct text parsing to preserve exact format.
    For other files, uses pandas DataFrames.

    Parameters
    ----------
    filepath : str
        Path to TRC, MOT, or STO file to crop
    nan_threshold : float, optional
        If provided, removes rows where NaN fraction > threshold.
        If None (default), uses 0.5 (50%) for TRC files.

    Returns
    -------
    dict or None
        Dictionary with crop information or None if error/no cropping needed.
    """
    import os
    from pathlib import Path

    file_ext = Path(filepath).suffix.lower()

    # Use text-based parsing for TRC files to preserve exact format
    if file_ext == '.trc':
        return _crop_trc_file_text_based(filepath, nan_threshold=nan_threshold or 0.5)

    # For MOT/STO files, load the data using pandas
    try:
        data = load_any_data_file(filepath)
    except Exception as e:
        print(f"Warning: Could not load {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None

    if data is None or len(data) == 0:
        print(f"Warning: No data in {filepath}")
        return None

    # For MOT/STO files: placeholder for future implementation
    print(f"Note: MOT/STO file cropping not yet implemented for {filepath}")
    return None


def _write_trc_file(filepath, data):
    """Write data back to TRC file, preserving header format and updating frame count."""
    try:
        # Read original file to extract header
        with open(filepath, 'r') as f:
            lines = f.readlines()

        # Find data start (Frame# line)
        frame_line_idx = -1
        for i, line in enumerate(lines):
            if 'Frame#' in line:
                frame_line_idx = i
                break

        if frame_line_idx < 0:
            print(f"Error: Could not find Frame# line in {filepath}")
            return

        # Data starts at frame_line_idx + 2 (skip Frame# line and units line)
        data_start_line = frame_line_idx + 2

        # Get expected column count from original header
        orig_header_line = lines[frame_line_idx].strip().split('\t')
        expected_col_count = len(orig_header_line)

        # Update NumFrames in metadata line (line 2, which is index 2 in 0-indexed array)
        # Line format: DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\t...
        if len(lines) > 2:
            metadata_line = lines[2]
            # Use regex to replace NumFrames value
            import re
            # Match "NumFrames\t<digits>" and replace with new count
            updated_line = re.sub(r'(NumFrames\t)(\d+)', fr'\g<1>{len(data)}', metadata_line)
            lines[2] = updated_line

        # Debug: Check column structure
        print(f"Debug _write_trc_file: DataFrame has {len(data.columns)} columns")
        if isinstance(data.columns, pd.MultiIndex):
            print(f"  Columns are MultiIndex: {len(data.columns)} tuples")
            # Print first few column names for debugging
            for i, col in enumerate(data.columns[:5]):
                print(f"    Col {i}: {col}")
        else:
            print(f"  Columns are flat: {list(data.columns[:5])}")
        print(f"  Expected {expected_col_count} columns")

        # Write new TRC file
        with open(filepath, 'w', encoding='utf-8') as f:
            # Write header lines (everything up to and including the units line)
            f.writelines(lines[:data_start_line])

            # Write data rows
            for frame_num, (_, row) in enumerate(data.iterrows(), 1):
                values = []

                # Handle MultiIndex columns (from TRC files loaded with load_trc)
                if isinstance(data.columns, pd.MultiIndex):
                    for idx, col in enumerate(data.columns):
                        # First column is Frame# - replace with sequential number
                        if idx == 0 and isinstance(col, tuple) and 'Frame' in str(col[0]):
                            values.append(str(frame_num))
                        else:
                            val = row[col]
                            # Format numeric values to 8 decimal places (standard for TRC)
                            if isinstance(val, (int, float)):
                                values.append(f"{val:16.8f}")
                            else:
                                values.append(str(val))
                else:
                    # Handle flat columns (shouldn't happen if crop_nans preserves MultiIndex)
                    for idx, (col, val) in enumerate(zip(data.columns, row.values)):
                        if idx == 0 and 'Frame' in str(col):
                            values.append(str(frame_num))
                        else:
                            if isinstance(val, (int, float)):
                                values.append(f"{val:16.8f}")
                            else:
                                values.append(str(val))

                # Sanity check
                if len(values) != expected_col_count:
                    print(f"Warning: Line {frame_num} has {len(values)} columns, expected {expected_col_count}")

                f.write("\t".join(values) + "\n")

        print(f"  Saved cropped TRC file with {len(data)} frames ({expected_col_count} columns)")
    except Exception as e:
        print(f"Error writing TRC file {filepath}: {e}")
        import traceback
        traceback.print_exc()


def _write_sto_file(filepath, data, labels):
    """Write data back to STO file, preserving header format."""
    try:
        labels = ['time'] + labels

        with open(filepath, 'w') as f:
            # Header (OpenSim format)
            f.write(f"{os.path.splitext(os.path.basename(filepath))[0]}\n")
            f.write("version=1\n")
            f.write(f"nRows={len(data)}\n")
            f.write(f"nColumns={len(labels)}\n")
            f.write("inDegrees=no\n")
            f.write("endheader\n")

            # Column labels
            f.write("\t".join(labels) + "\n")

            # Data rows
            for _, row in data.iterrows():
                values_str = "\t".join([f"{val:16.8f}" for val in row.values])
                f.write(values_str + "\n")

        print(f"  Saved cropped data to {filepath}")
    except Exception as e:
        print(f"Error writing STO file {filepath}: {e}")


def define_time_range(trc_filepath, markers, algorithm):
    
    data = load_any_data_file(trc_filepath)

    # Define time range based on markers and algorithm
    if algorithm == 'min-max':
        start_time = data['time'].min()
        end_time = data['time'].max()
    elif algorithm == 'deadlift':
        
        start_frame = int(data[markers].idxmin())
        
        # end frame is the first frame with minimal derivative after the start frame
        end_frame = int(data[markers].iloc[start_frame:].diff().idxmin())
        
        start_time = data['Time'].iloc[start_frame]
        end_time = data['Time'].iloc[end_frame]

    # Events (start/end window) are persisted by the caller into the <events>
    # subtree of trial_settings.xml — there is no separate events file.
    return start_time, end_time

def write_mot(analog_df, labels, mot_file):
    """
    Write analog data (samples, n_channels) to MOT in OpenSim format.
    
    inputs:
        labels: The labels for the analog channels (not including time).
        analog_df: The DataFrame containing the analog data (must include 'time' column).
        mot_file: Output file path.
        
    """
    
    # make sure labels include time
    labels = ['time'] + labels

    # Crop dataframe to include only labels and replace NaN with 0.0
    analog_df = analog_df[labels].fillna(0.0)
    num_samples, num_columns = analog_df.shape
    
    # create writer
    with open(mot_file, "w") as writer:
        # Header (OpenSim format)
        writer.write(f"{os.path.splitext(os.path.basename(mot_file))[0]}\n")
        writer.write("version=1\n")
        writer.write(f"nRows={num_samples}\n")
        writer.write(f"nColumns={num_columns}\n")  # num_columns already includes time
        writer.write("inDegrees=no\n")
        writer.write("endheader\n")

        # Column labels (tab-separated)
        writer.write("\t".join(labels) + "\n")
    
        # Data rows (right-aligned with 8 decimal places, tab-separated)
        for i, row in analog_df.iterrows():
            values_str = "\t".join([f"{val:16.8f}" for val in row.values])
            writer.write(values_str + "\n")

def rotate_data_table(table, axis, deg):
    """Rotate OpenSim::TimeSeriesTableVec3 entries using an axis and angle.

    Parameters
    ----------
    table: OpenSim.common.TimeSeriesTableVec3

    axis: 3x1 vector

    deg: angle in degrees

    """
    R = opensim.Rotation(np.deg2rad(deg),
                         opensim.Vec3(axis[0], axis[1], axis[2]))
    for i in range(table.getNumRows()):
        vec = table.getRowAtIndex(i)
        vec_rotated = R.multiply(vec)
        table.setRowAtIndex(i, vec_rotated)

def export_emg(c3d_filepath, emg_strings_list=['emg'], reset_time=True, output_dir=None):
    output_dir = output_dir or os.path.dirname(c3d_filepath)
    print(f"Reading C3D file: {c3d_filepath}")
    try:
        reader = c3d.Reader(open(c3d_filepath, "rb"))
    except Exception as e:
        print(f"Error: Could not open or read the C3D file. {e}")
        return 1

    # Rates and frames
    marker_rate = float(reader.header.frame_rate)
    first_frame = int(reader.header.first_frame)
    num_frames = int(reader.frame_count)

    # Labels
    analog_labels = [str(l or "").strip() for l in reader.analog_labels]

    # Create time vector
    initial_time = first_frame / marker_rate
    final_time = (first_frame + num_frames - 1) / marker_rate
    time = np.linspace(initial_time, final_time, num_frames)

    # Collect all analog frames into a list first (much faster than row-by-row loc assignment)
    # Suppress the 'No point data found' warning that fires for EMG-only C3D files
    rows = []
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='No point data found', category=UserWarning)
        for frame_no, points, analog in reader.read_frames():
            rows.append([analog[i][0] for i in range(len(analog_labels))])

    # replace . and spaces in labels with underscores
    analog_labels = [re.sub(r'[.\s]', '_', lbl) for lbl in analog_labels]
    # Make labels unique — C3D files frequently repeat a placeholder name
    # (e.g. 'Voltage_not_used' x11). Duplicate column names create a DataFrame
    # where label selection returns a 2-D frame, which breaks write_mot /
    # filter_emg downstream. Suffix repeats with _2, _3, ...
    _seen: dict = {}
    _uniq_labels = []
    for _lbl in analog_labels:
        if _lbl in _seen:
            _seen[_lbl] += 1
            _uniq_labels.append(f"{_lbl}_{_seen[_lbl]}")
        else:
            _seen[_lbl] = 1
            _uniq_labels.append(_lbl)
    analog_labels = _uniq_labels
    analog_df = pd.DataFrame(rows, columns=analog_labels)
    analog_df.insert(0, 'time', time)

    if reset_time:
        analog_df['time'] = analog_df['time'] - analog_df['time'].iloc[0]

    # Save analog to csv
    analog_path = os.path.join(output_dir, "analog.csv")
    analog_df.to_csv(analog_path, index=False)
    print(f"Successfully exported {analog_path}")

    # Write EMG MOT
    emg_indices = []
    print(f"[DEBUG] Looking for EMG patterns: {emg_strings_list}")
    print(f"[DEBUG] Available analog labels: {analog_labels[:10]}...")  # Show first 10 labels

    for i, label in enumerate(analog_labels):
        for emg_str in emg_strings_list:
            if label.lower().__contains__(emg_str.lower()):
                emg_indices.append(i)
                print(f"Found EMG channel: '{label}' at index {i}")

    emg_mot_path = os.path.join(output_dir, "emg.mot")

    if emg_indices:
        emg_labels = [analog_labels[i] for i in emg_indices]
        write_mot(analog_df, emg_labels, emg_mot_path)
        print(f"Successfully exported {emg_mot_path}")

        # Filter emg mot only if it was created. Keep the raw emg.mot even if
        # filtering fails (e.g. non-physiological 'Voltage_*' channels), and
        # report the real reason instead of silently failing.
        try:
            fs = 1 / (analog_df['time'].iloc[1] - analog_df['time'].iloc[0])
            highcut_bp = fs/2 * 0.9
            filter_emg(emg_path=emg_mot_path, highcut_bp=highcut_bp, lowcut_bp=20, lowcut_lp=6, order_bp=4, order_lp=4)
        except Exception as _fe:
            print(f"Warning: EMG filtering skipped ({type(_fe).__name__}: {_fe}); raw emg.mot kept.")
    else:
        print("Warning: No EMG channels found among available analog channels.")
        print(f"[DEBUG] Searched for {len(emg_strings_list)} patterns in {len(analog_labels)} available channels")
       
def export_markers(c3d_filepath, strings_to_remove=[], output_dir=None):
    print(f"Exporting markers for {c3d_filepath}")

    # OpenSim data adapters
    adapter = opensim.C3DFileAdapter()
    adapter.setLocationForForceExpression(
        opensim.C3DFileAdapter.ForceLocation_CenterOfPressure)
    trc_adapter = opensim.TRCFileAdapter()

    # get markers
    task = adapter.read(c3d_filepath)
    markers_task = adapter.getMarkersTable(task)
    output_dir = output_dir or os.path.dirname(c3d_filepath)

    # process markers of task and save to .trc file
    rotate_data_table(markers_task, [1, 0, 0], -90)

    # remove unwanted strings from labels
    labels = list(markers_task.getColumnLabels())
    # Strip any capture namespace prefix ("Subject:RASI" -> "RASI"). Some trials
    # (e.g. the squat/static captures) store markers with a namespace while others
    # (walking) don't; without this the TRC labels don't match the OpenSim model
    # markers and IK fails with "Marker data does not correspond to any model
    # markers". Bare labels are unaffected by the split.
    labels = [lbl.split(':')[-1].strip() for lbl in labels]
    for s in strings_to_remove:
        labels = [re.sub(s, '', lbl) for lbl in labels]
    print(f"  [markers] {len(labels)} labels e.g. {labels[:8]}")

    markers_task.setColumnLabels(labels)

    # TRCFileAdapter.write() requires 'DataRate' and 'CameraRate' metadata.
    # C3DFileAdapter doesn't always populate these, so compute from the time column.
    time_col = markers_task.getIndependentColumn()
    if len(time_col) > 1 and (time_col[1] - time_col[0]) > 0:
        data_rate = round(1.0 / (time_col[1] - time_col[0]))
    else:
        data_rate = 100.0
    if not markers_task.hasTableMetaDataKey('DataRate'):
        markers_task.addTableMetaDataString('DataRate', str(data_rate))
    if not markers_task.hasTableMetaDataKey('CameraRate'):
        markers_task.addTableMetaDataString('CameraRate', str(data_rate))
    if not markers_task.hasTableMetaDataKey('Units'):
        markers_task.addTableMetaDataString('Units', 'mm')

    trc_adapter = opensim.TRCFileAdapter()
    marker_trc_file = os.path.join(output_dir, 'marker_experimental.trc')
    trc_adapter.write(markers_task, marker_trc_file)
    print(f"Successfully exported {marker_trc_file}")

    # Clean NaN rows from exported marker file
    print(f"Cleaning NaN rows from marker data...")
    crop_info = crop_nans(marker_trc_file)
    if crop_info:
        rows_removed = crop_info['rows_removed_start'] + crop_info['rows_removed_end']
        if rows_removed > 0:
            print(f"  [OK] Removed {rows_removed} NaN rows from marker file")
        else:
            print(f"  [OK] No NaN rows to remove (data is clean)")
    
def _remap_grf_axes(grf_file, axis_map=None, cop_scale=0.001,
                    moment_scale=0.001, moment_sign=-1.0):
    """Convert GRF columns from the mocap/C3D lab frame to the OpenSim frame.

    axis_map maps each OpenSim axis to (source_mocap_axis, sign), e.g.
        {'x': ('x', 1.0), 'y': ('z', 1.0), 'z': ('y', -1.0)}   (90 deg about X)
    applied to every plate's force (v), CoP position (p) and moment (m) vectors.
    Then:
      - CoP positions  are scaled by `cop_scale`     (mm -> m),
      - free moments   are scaled by `moment_scale`  (N*mm -> N*m) and multiplied
        by `moment_sign` (some systems flip the free-moment sign).
    Column names/order are preserved — only the values change.
    """
    if not axis_map:
        axis_map = {'x': ('x', 1.0), 'y': ('z', 1.0), 'z': ('y', -1.0)}

    with open(grf_file, 'r', errors='replace') as f:
        lines = f.readlines()

    hi = 0
    for i, ln in enumerate(lines):
        if ln.strip().lower() == 'endheader':
            hi = i + 1
            break
    while hi < len(lines) and not lines[hi].strip():
        hi += 1
    cols = lines[hi].split()
    df = pd.read_csv(grf_file, sep=r'\s+', skiprows=hi + 1, names=cols, engine='python')
    new = df.copy()

    # Group columns by '<prefix>_<type><axis>', type in {v,p,m}, axis in {x,y,z}.
    # v = force (no scale), p = CoP position (mm->m), m = free moment (N*mm->N*m).
    type_scale = {'v': 1.0, 'p': float(cop_scale), 'm': float(moment_scale) * float(moment_sign)}
    patt = re.compile(r'^(.*_)([vpm])([xyz])$')
    bases = {(m.group(1), m.group(2)) for c in cols
             for m in [patt.match(c)] if m}
    for prefix, typ in bases:
        scale = type_scale.get(typ, 1.0)
        for osim_axis, (src_axis, sign) in axis_map.items():
            out_col = f"{prefix}{typ}{osim_axis}"
            src_col = f"{prefix}{typ}{src_axis}"
            if out_col in df.columns and src_col in df.columns:
                new[out_col] = (sign * scale) * df[src_col]

    def _fmt(v):
        return f"{v:.8f}" if v == v else "nan"   # v==v is False for NaN

    new = new[cols]
    with open(grf_file, 'w', newline='') as f:
        f.writelines(lines[:hi + 1])             # header + column-names line
        for _row in new.itertuples(index=False):
            f.write('\t'.join(_fmt(v) for v in _row) + '\n')


def _apply_plate_force_sign(grf_file, plate_sign):
    """Flip the sign of specific force components for individual plates in a
    grf.mot. ``plate_sign`` = {plate_id: {axis: sign}}, e.g. {1: {'vx': -1}}
    negates ``ground_force_1_vx`` (plate 1 anterior-posterior force)."""
    import pandas as _pd
    from bioscout import utils as _u
    df = _u.load_any_data_file(grf_file)
    for pid, axes in plate_sign.items():
        for axis, sign in axes.items():
            col = f"ground_force_{pid}_{axis}"
            if col in df.columns:
                df[col] = float(sign) * _pd.to_numeric(df[col], errors="coerce")
    _u.write_sto_file(df, os.path.abspath(grf_file))


def export_grf(c3d_filepath, output_dir=None):

    def transform_labels(labels):
        """
        Transforms a list of labels from a compact format to a more descriptive format.
        Example: 'f1x' -> 'ground_force_1_vx'
        """
        transformed = []
        # Define a mapping for the prefixes and their corresponding replacements.
        # The key is the original prefix (e.g., 'f'), and the value is a tuple
        # containing the new prefix (e.g., 'ground_force') and the new suffix (e.g., 'v').
        mapping = {
            'f': ('ground_force', 'v'),
            'p': ('ground_force', 'p'),
            'm': ('ground_moment', 'm'),
        }

        for label in labels:
            # Check if the label is at least 3 characters long and matches the pattern
            if len(label) >= 3 and label[0] in mapping and label[-1] in 'xyz':
                # Extract the original prefix (e.g., 'f'), number (e.g., '1'), and axis (e.g., 'x')
                original_prefix = label[0]
                number = label[1:-1]
                axis = label[-1]

                # Get the new prefix and suffix from the mapping
                new_prefix, new_suffix = mapping[original_prefix]

                # Construct the new label
                new_label = f'{new_prefix}_{number}_{new_suffix}{axis}'
                transformed.append(new_label)
            else:
                # If the label doesn't match the expected pattern, add it as is
                transformed.append(label)

        return transformed

    print(f"Exporting ground reaction forces for {c3d_filepath}")
    adapter = opensim.C3DFileAdapter()
    adapter.setLocationForForceExpression(opensim.C3DFileAdapter.ForceLocation_CenterOfPressure)

    c3d_data = adapter.read(c3d_filepath)
    forces_table = adapter.getForcesTable(c3d_data)
    # NOTE: do NOT rotate here. The previous `rotate_data_table([1,0,0],180)`
    # negated Y and Z, which flipped the vertical force sign and left the data
    # in the mocap frame. Instead we export in the raw mocap/C3D frame and then
    # remap to the OpenSim frame below using BatchSettings.grf_axis_map.
    time = forces_table.getIndependentColumn()
    forces_table = forces_table.flatten(['x', 'y', 'z'])

    # replace f,p,m for ground_force_v, ground_force_p, ground_torque
    labels = transform_labels(list(forces_table.getColumnLabels()))
    osim_tools = osimTools()
    force_sto = osim_tools._create_opensim_storage(time, forces_table.getMatrix(), labels)
    force_sto.setName('grf')
    output_dir = output_dir or os.path.dirname(c3d_filepath)
    grf_file = os.path.join(output_dir, 'grf.mot')
    force_sto.printResult(force_sto, 'grf', output_dir, 0.01, '.mot')
    print(f"Successfully exported {grf_file}")

    # Convert force/CoP/moment vectors from the mocap/C3D frame to the OpenSim
    # frame using the configurable mapping (mocap is Z-up, OpenSim is Y-up).
    _axis_map = None
    _cop_scale, _moment_scale, _moment_sign = 0.001, 0.001, -1.0
    try:
        import settings as _settings_mod
        _bs = _settings_mod.BatchSettings
        _axis_map = getattr(_bs, 'grf_axis_map', None)
        _cop_scale = getattr(_bs, 'grf_cop_scale_to_m', _cop_scale)
        _moment_scale = getattr(_bs, 'grf_moment_scale', _moment_scale)
        _moment_sign = getattr(_bs, 'grf_moment_sign', _moment_sign)
    except Exception:
        pass
    try:
        _remap_grf_axes(grf_file, _axis_map, cop_scale=_cop_scale,
                        moment_scale=_moment_scale, moment_sign=_moment_sign)
        print(f"  [OK] Remapped GRF to OpenSim frame "
              f"(map: {_axis_map or 'default'}, CoP*{_cop_scale}, moment*{_moment_scale})")
    except Exception as _re_err:
        print(f"  [WARN] GRF axis remap skipped: {_re_err}")

    # Per-PLATE sign correction for individually mis-wired plates (e.g. one plate
    # whose AP force channel is inverted). settings.BatchSettings.grf_plate_force_sign
    # = {plate_id: {axis: sign}}, e.g. {1: {'vx': -1}} flips plate 1's AP force.
    try:
        _plate_sign = getattr(_bs, 'grf_plate_force_sign', None)
    except Exception:
        _plate_sign = None
    if _plate_sign:
        try:
            _apply_plate_force_sign(grf_file, _plate_sign)
            print(f"  [OK] Applied per-plate force sign correction: {_plate_sign}")
        except Exception as _ps_err:
            print(f"  [WARN] per-plate sign correction skipped: {_ps_err}")

    # Clean NaN rows from exported GRF file
    print(f"Cleaning NaN rows from GRF data...")
    crop_info = crop_nans(grf_file)
    if crop_info:
        rows_removed = crop_info['rows_removed_start'] + crop_info['rows_removed_end']
        if rows_removed > 0:
            print(f"  [OK] Removed {rows_removed} NaN rows from GRF file")
        else:
            print(f"  [OK] No NaN rows to remove (data is clean)")

def get_time_range_from_c3d(c3d_filepath):
    """Return (start_time, end_time) in seconds from a C3D file.

    Tries the forces/analog table first (present even when there are no markers),
    then falls back to the markers table.  Returns None if both fail.
    """
    try:
        adapter = opensim.C3DFileAdapter()
        task = adapter.read(c3d_filepath)
        # Forces table uses analog rate — always available when GRF channels exist
        for getter in (adapter.getForcesTable, adapter.getMarkersTable):
            try:
                table = getter(task)
                tc = table.getIndependentColumn()
                if len(tc) > 1:
                    return (float(tc[0]), float(tc[-1]))
            except Exception:
                continue
    except Exception:
        pass
    return None


def main(c3d_filepath, emg_string_list=['emg'], create_folder=False, output_dir=None):
    """Export C3D data to TRC / GRF.mot / EMG.mot files.

    Parameters
    ----------
    output_dir : str, optional
        Explicit destination folder (created if needed). In the session-centric
        layout this is ``<session>/experimental/<trial>/``. If omitted, exports
        next to the c3d — optionally in a per-trial subfolder (``create_folder``).

    Returns
    -------
    tuple or None
        (start_time, end_time) in seconds read from the C3D, or None if
        the time range could not be determined.
    """

    # Destination: explicit output_dir wins; else next to the c3d (optionally in
    # a per-trial subfolder named after the c3d).
    if output_dir is None:
        output_dir = os.path.dirname(c3d_filepath)
        if create_folder:
            output_dir = os.path.join(output_dir, os.path.basename(c3d_filepath).replace('.c3d', ''))
    os.makedirs(output_dir, exist_ok=True)
    print(f"Exporting c3d -> {output_dir}")

    # Read time range before exports (C3D file intact, forces table is reliable)
    time_range = get_time_range_from_c3d(c3d_filepath)

    try:
        export_markers(c3d_filepath, strings_to_remove=[], output_dir=output_dir)
    except BaseException as e:
        import traceback as _tb
        print(f"An error occurred while exporting markers: {type(e).__name__}: {e}")
        _tb.print_exc()

    try:
        export_grf(c3d_filepath, output_dir=output_dir)
    except BaseException as e:
        import traceback as _tb
        print(f"An error occurred while exporting ground reaction forces: {type(e).__name__}: {e}")
        _tb.print_exc()

    try:
        export_emg(c3d_filepath, emg_strings_list=emg_string_list, output_dir=output_dir)
    except BaseException as e:
        import traceback as _tb
        print(f"An error occurred while exporting EMG data: {type(e).__name__}: {e}")
        _tb.print_exc()

    return time_range


def _qc_figures(tdir):
    """Established-style QC figures for one experimental trial folder, replicated
    standalone (no Analyse): emg_processing.png (raw grey vs filtered+normalised
    red on a twin axis, per channel) and grf_events.png (per-foot vertical GRF)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from xml.etree import ElementTree as ET
    import re as _re
    from bioscout import utils as _u
    trial = os.path.basename(tdir)

    # ---- EMG: raw vs filtered+normalised (matches Analyse.plot_emg_processing) ----
    try:
        raw = _u.load_any_data_file(os.path.join(tdir, "emg.mot"))
        try:
            norm = _u.load_any_data_file(os.path.join(tdir, "emg_filtered_normalised.mot"))
        except Exception:
            norm = None
        tr = pd.to_numeric(raw["time"], errors="coerce").to_numpy(float)
        tn = (pd.to_numeric(norm["time"], errors="coerce").to_numpy(float)
              if norm is not None else None)
        chans = [c for c in raw.columns if c.lower() != "time" and "emg" in c.lower()
                 and any(k.isalpha() for k in str(c).split("EMG")[-1])] or \
                [c for c in raw.columns if c.lower() != "time"]
        if norm is not None:
            chans = [c for c in chans if c in norm.columns] or chans
        ncol = 3; nrow = int(np.ceil(len(chans) / ncol))
        fig, axg = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 2.4 * nrow), squeeze=False)
        for i, ch in enumerate(chans):
            a = axg[i // ncol][i % ncol]
            a.plot(tr, pd.to_numeric(raw[ch], errors="coerce"), color="0.6", lw=0.4)
            if norm is not None and ch in norm.columns:
                a2 = a.twinx()
                a2.plot(tn, pd.to_numeric(norm[ch], errors="coerce"), color="tab:red", lw=1.5)
                a2.set_ylim(-0.05, 1.05); a2.tick_params(labelsize=7, colors="tab:red")
                a2.set_ylabel("norm", fontsize=7, color="tab:red")
            a.set_title(str(ch).replace("EMG_Channels_", ""), fontsize=8)
            a.tick_params(labelsize=7); a.set_ylabel("raw", fontsize=7); a.margins(x=0)
        for j in range(len(chans), nrow * ncol):
            axg[j // ncol][j % ncol].axis("off")
        h = [plt.Line2D([], [], color="0.6", lw=1, label="raw EMG"),
             plt.Line2D([], [], color="tab:red", lw=1.5, label="filtered + session-normalised (0-1)")]
        fig.legend(handles=h, loc="lower center", ncol=2, fontsize=10, frameon=False)
        fig.suptitle(f"{trial} — EMG: raw vs filtered-normalised", fontsize=13)
        fig.tight_layout(rect=[0, 0.03, 1, 0.98])
        fig.savefig(os.path.join(tdir, "emg_processing.png"), dpi=130); plt.close(fig)
    except Exception as e:
        print(f"[export_session] {trial}: EMG figure warn — {e}")

    # ---- GRF: per-foot vertical force (core of Analyse.plot_grf_events) ----
    try:
        grf = _u.load_any_data_file(os.path.join(tdir, "grf.mot"))
        t = pd.to_numeric(grf["time"], errors="coerce").to_numpy(float)
        foot = {}
        try:
            root = ET.parse(os.path.join(tdir, "GRF.xml")).getroot()
            for ef in root.iter("ExternalForce"):
                body = (ef.findtext("applied_to_body") or "").strip()
                m = _re.search(r"(\d+)", (ef.findtext("force_identifier") or ""))
                if m and body.startswith("calcn_"):
                    foot[int(m.group(1))] = body.split("_")[-1]
        except Exception:
            pass

        def _sum(side):
            cols = [f"ground_force_{p}_vy" for p, s in foot.items()
                    if s == side and f"ground_force_{p}_vy" in grf.columns]
            return (np.sum([pd.to_numeric(grf[cN], errors="coerce").to_numpy(float)
                            for cN in cols], axis=0) if cols else np.zeros_like(t))

        vyR, vyL = _sum("r"), _sum("l")

        # detect foot contact / foot off per side (as Analyse.detect_events_from_grf)
        threshold, min_stance_s = 20.0, 0.05
        n = len(t)

        def _runs(mask):
            out, i = [], 0
            while i < n:
                if mask[i]:
                    j = i
                    while j < n and mask[j]:
                        j += 1
                    out.append((i, j - 1)); i = j
                else:
                    i += 1
            return out

        def _cross(i_lo, i_hi, vy):
            y0, y1 = vy[i_lo], vy[i_hi]
            return float(t[i_hi]) if y1 == y0 else \
                float(t[i_lo] + (threshold - y0) / (y1 - y0) * (t[i_hi] - t[i_lo]))

        events = []
        for side, label, vy in (("r", "Right", vyR), ("l", "Left", vyL)):
            if not np.any(np.asarray(vy) > threshold):
                continue
            for a, b in _runs(np.asarray(vy) > threshold):
                if (t[b] - t[a]) < min_stance_s:
                    continue
                if a > 0:
                    events.append({"name": f"{label} Foot Contact", "time": round(_cross(a - 1, a, vy), 3),
                                   "side": side, "contact": True})
                if b < n - 1:
                    events.append({"name": f"{label} Foot Off", "time": round(_cross(b, b + 1, vy), 3),
                                   "side": side, "contact": False})

        fig, ax = plt.subplots(figsize=(11, 5.2))
        ax.plot(t, vyR, color="tab:red", lw=1.8, label="Right foot Fy")
        ax.plot(t, vyL, color="tab:blue", lw=1.8, label="Left foot Fy")
        ax.axhline(threshold, color="0.6", ls=":", lw=1, label=f"{threshold:.0f} N")
        ymax = float(max(np.max(vyR), np.max(vyL)) or 1.0)
        ax.set_ylim(-40, ymax * 1.28)
        for i, e in enumerate(sorted(events, key=lambda x: x["time"])):
            col = "tab:red" if e["side"] == "r" else "tab:blue"
            tt = e["time"]; yv = float(np.interp(tt, t, vyR if e["side"] == "r" else vyL))
            ax.axvline(tt, color=col, ls="-" if e["contact"] else "--", lw=1.0, alpha=0.5)
            ax.plot(tt, yv, marker="^" if e["contact"] else "v", color=col, ms=11,
                    mec="k", mew=0.6, zorder=6)
            ax.annotate(f"{i+1}. {e['name']} ({tt:.2f}s)",
                        (tt, ymax * (1.02 + 0.075 * (i % 3))), ha="center", va="bottom",
                        fontsize=7.2, color=col,
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, alpha=0.9))
        ax.set_xlabel("Time (s)"); ax.set_ylabel("Vertical GRF Fy (N)")
        ax.set_title(f"{trial} — vertical GRF per foot + gait events"); ax.legend(fontsize=9)
        fig.tight_layout(); fig.savefig(os.path.join(tdir, "grf_events.png"), dpi=130)
        plt.close(fig)
    except Exception as e:
        print(f"[export_session] {trial}: GRF figure warn — {e}")


def export_session(session_dir, emg_string_list=None, c3d_dirname="c3dfiles",
                   out_dirname="experimental", normalise=True):
    """Export EVERY c3d of a session-centric session into per-trial folders.

    New layout (model-INDEPENDENT data, produced ONCE and shared by all model
    iterations)::

        <session_dir>/<c3d_dirname>/<trial>.c3d          # raw input
        <session_dir>/<out_dirname>/<trial>/             # created here
            marker_experimental.trc  grf.mot  GRF.xml
            emg.mot  emg_filtered.mot  emg_filtered_normalised.mot

    EMG amplitude normalisation is SESSION-WIDE (per-channel max across all
    trials = MVC reference) and writes columns in canonical SORTED order
    (time, EMG01..EMGnn) so CEINMS pairs the excitation generator with each
    trial's excitations consistently. Returns the list of exported trial names.
    """
    import glob
    import numpy as np
    import pandas as pd
    from bioscout import utils as _u
    from bioscout.utils import emg_normalise as _en

    emg_string_list = emg_string_list or ['emg']
    c3d_dir = os.path.join(session_dir, c3d_dirname)
    out_dir = os.path.join(session_dir, out_dirname)

    trials = []
    for c3d in sorted(glob.glob(os.path.join(c3d_dir, "*.c3d"))):
        trial = os.path.basename(c3d)[:-4]
        tdir = os.path.join(out_dir, trial)
        try:
            main(c3d, emg_string_list=emg_string_list, output_dir=tdir)
            trials.append(trial)
        except Exception as e:
            print(f"[export_session] {trial}: export failed — {type(e).__name__}: {e}")
            continue
        # GRF.xml (external loads) — model-independent, so build it here once with
        # the raw data (previously created lazily inside ID). Lives in experimental/.
        try:
            from bioscout import utils as _u
            from bioscout.utils import openSim as _os
            _bs = getattr(_u, "settings", None)
            _bs = getattr(_bs, "BatchSettings", None)
            _os.create_grf_xml(
                grf_mot_path=os.path.join(tdir, "grf.mot"),
                output_xml_path=os.path.join(tdir, "GRF.xml"),
                marker_trc_path=os.path.join(tdir, "marker_experimental.trc"),
                right_foot_markers=getattr(_bs, "right_foot_markers", None),
                left_foot_markers=getattr(_bs, "left_foot_markers", None),
                right_foot_body="calcn_r", left_foot_body="calcn_l",
                vert_force_threshold=10.0, filter_cutoff=6, datafile=None)
        except Exception as e:
            print(f"[export_session] {trial}: GRF.xml build warn — {type(e).__name__}: {e}")

    if normalise and trials:
        dfs = {}
        for t in trials:
            fp = os.path.join(out_dir, t, "emg_filtered.mot")
            if os.path.exists(fp):
                try:
                    dfs[t] = _u.load_any_data_file(fp)
                except Exception as e:
                    print(f"[export_session] {t}: load emg_filtered failed — {e}")
        if dfs:
            chans = sorted({c for df in dfs.values()
                            for c in df.columns if c.lower() != 'time'})
            session_max = {}
            for c in chans:
                vals = []
                for df in dfs.values():
                    if c in df.columns:
                        vals.extend(pd.to_numeric(df[c], errors='coerce').dropna().values)
                m = float(np.max(vals)) if len(vals) else 1.0
                session_max[c] = m if m > 1e-9 else 1.0
            for t, df in dfs.items():
                out = df[['time']].copy() if 'time' in df.columns else pd.DataFrame()
                for c in chans:                       # canonical sorted order
                    if c in df.columns:
                        out[c] = (pd.to_numeric(df[c], errors='coerce') / session_max[c]).clip(0.0, 1.0)
                _en.write_sto_file(out, os.path.join(out_dir, t, "emg_filtered_normalised.mot"))
            print(f"[export_session] normalised EMG across {len(dfs)} trials "
                  f"(canonical sorted columns).")

    # QC figures need the normalised EMG + GRF.xml, so build them AFTER
    # session normalisation, reusing the established Analyse plot methods.
    for t in trials:
        try:
            _qc_figures(os.path.join(out_dir, t))
        except Exception as e:
            print(f"[export_session] {t}: QC figures warn — {e}")

    print(f"[export_session] exported {len(trials)} trial(s) -> {out_dir}")
    return trials


def transform_labels(labels):
        """
        Transforms a list of labels from a compact format to a more descriptive format.
        Example: 'f1x' -> 'ground_force_1_vx'
        """
        transformed = []
        # Define a mapping for the prefixes and their corresponding replacements.
        # The key is the original prefix (e.g., 'f'), and the value is a tuple
        # containing the new prefix (e.g., 'ground_force') and the new suffix (e.g., 'v').
        mapping = {
            'f': ('ground_force', 'v'),
            'p': ('ground_force', 'p'),
            'm': ('ground_moment', 'm'),
        }

        for label in labels:
            # Check if the label is at least 3 characters long and matches the pattern
            if len(label) >= 3 and label[0] in mapping and label[-1] in 'xyz':
                # Extract the original prefix (e.g., 'f'), number (e.g., '1'), and axis (e.g., 'x')
                original_prefix = label[0]
                number = label[1:-1]
                axis = label[-1]

                # Get the new prefix and suffix from the mapping
                new_prefix, new_suffix = mapping[original_prefix]

                # Construct the new label
                new_label = f'{new_prefix}_{number}_{new_suffix}{axis}'
                transformed.append(new_label)
            else:
                # If the label doesn't match the expected pattern, add it as is
                transformed.append(label)

        return transformed

def grf_from_c3d(c3d_filepath):

    
    import matplotlib.pyplot as plt
    adapter = opensim.C3DFileAdapter()
    adapter.setLocationForForceExpression(opensim.C3DFileAdapter.ForceLocation_CenterOfPressure)
    
    c3d_data = adapter.read(c3d_filepath)
    forces_table = adapter.getForcesTable(c3d_data)
    rotate_data_table(forces_table, [1, 0, 0], 180)
    time = forces_table.getIndependentColumn()
    forces_table = forces_table.flatten(['x', 'y', 'z'])
    
    raw_labels = list(forces_table.getColumnLabels())
    labels = transform_labels(raw_labels)

    # create a dataframe for plotting
    matrix = forces_table.getMatrix()
    matrix_data = [
        [matrix.getElt(row_idx, col_idx) for col_idx in range(matrix.ncol())]
        for row_idx in range(matrix.nrow())
    ]
    grf_df = pd.DataFrame(matrix_data, columns=labels)
    grf_df.insert(0, 'time', time)
    print(grf_df.head())

    # Build grouped channels by force plate id (e.g., ground_force_1_vx, ground_force_1_px)
    force_pattern = re.compile(r"ground_force_(\d+)_v([xyz])$")
    cop_pattern = re.compile(r"ground_force_(\d+)_p([xy])$")

    plate_ids = sorted({
        int(m.group(1))
        for col in labels
        for m in [force_pattern.match(col), cop_pattern.match(col)]
        if m
    })

    total_fx = pd.Series(0.0, index=grf_df.index)
    total_fy = pd.Series(0.0, index=grf_df.index)
    total_fz = pd.Series(0.0, index=grf_df.index)

    for pid in plate_ids:
        fx_col = f"ground_force_{pid}_vx"
        fy_col = f"ground_force_{pid}_vy"
        fz_col = f"ground_force_{pid}_vz"
        fx_series = grf_df[fx_col].fillna(0.0) if fx_col in grf_df.columns else pd.Series(0.0, index=grf_df.index)
        fy_series = grf_df[fy_col].fillna(0.0) if fy_col in grf_df.columns else pd.Series(0.0, index=grf_df.index)
        fz_series = grf_df[fz_col].fillna(0.0) if fz_col in grf_df.columns else pd.Series(0.0, index=grf_df.index)

        total_fx += fx_series
        total_fy += fy_series
        total_fz += fz_series

    contact_force_threshold = 20.0

    # Weighted COP using |Fz| as weight to avoid cancellation between plates
    weighted_x = np.zeros(len(grf_df))
    weighted_y = np.zeros(len(grf_df))
    total_weight = np.zeros(len(grf_df))

    for pid in plate_ids:
        px_col = f"ground_force_{pid}_px"
        py_col = f"ground_force_{pid}_py"
        fz_col = f"ground_force_{pid}_vz"
        if px_col in grf_df.columns and py_col in grf_df.columns and fz_col in grf_df.columns:
            px = grf_df[px_col].to_numpy()
            py = grf_df[py_col].to_numpy()
            wz = np.abs(grf_df[fz_col].fillna(0.0).to_numpy())
            valid = np.isfinite(px) & np.isfinite(py) & (wz > contact_force_threshold)
            weighted_x[valid] += px[valid] * wz[valid]
            weighted_y[valid] += py[valid] * wz[valid]
            total_weight[valid] += wz[valid]

    total_cop_x = np.full(len(grf_df), np.nan)
    total_cop_y = np.full(len(grf_df), np.nan)
    valid_total = total_weight > 0
    total_cop_x[valid_total] = weighted_x[valid_total] / total_weight[valid_total]
    total_cop_y[valid_total] = weighted_y[valid_total] / total_weight[valid_total]

    fig, axes = plt.subplots(3, 1, figsize=(13, 14))

    # Row 1: forces separated by force plate number (Fy and Fz)
    for pid in plate_ids:
        fy_col = f"ground_force_{pid}_vy"
        fz_col = f"ground_force_{pid}_vz"
        if fy_col in grf_df.columns:
            axes[0].plot(grf_df['time'], grf_df[fy_col], linewidth=1.0, label=f'Plate {pid} Fy')
        if fz_col in grf_df.columns:
            axes[0].plot(grf_df['time'], grf_df[fz_col], linewidth=1.6, label=f'Plate {pid} Fz')

    axes[0].plot(grf_df['time'], total_fy, color='k', linewidth=1.8, linestyle='--', label='Sum Fy')
    axes[0].plot(grf_df['time'], total_fz, color='k', linewidth=2.0, label='Sum Fz')
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Force (N)')
    axes[0].set_title('Ground Reaction Forces by Plate (Fy and Fz)')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(ncol=3, fontsize=8)

    # Row 2: force plates + point of application in top view (px vertical)
    from matplotlib.patches import Rectangle

    has_cop = False
    plate_colors = plt.cm.tab10(np.linspace(0, 1, max(len(plate_ids), 1)))
    for color_idx, pid in enumerate(plate_ids):
        px_col = f"ground_force_{pid}_px"
        py_col = f"ground_force_{pid}_py"
        fz_col = f"ground_force_{pid}_vz"
        if px_col in grf_df.columns and py_col in grf_df.columns and fz_col in grf_df.columns:
            plate_mask = (
                grf_df[[px_col, py_col, fz_col]].notna().all(axis=1)
                & (grf_df[fz_col].abs() > contact_force_threshold)
            )
            valid = grf_df.loc[plate_mask, [px_col, py_col]]
            if not valid.empty:
                px_vals = valid[px_col].to_numpy()
                py_vals = valid[py_col].to_numpy()

                # Draw a plate footprint from COP bounds (x-axis = py, y-axis = px)
                py_min, py_max = np.nanmin(py_vals), np.nanmax(py_vals)
                px_min, px_max = np.nanmin(px_vals), np.nanmax(px_vals)
                py_pad = max((py_max - py_min) * 0.08, 1.0)
                px_pad = max((px_max - px_min) * 0.08, 1.0)
                rect = Rectangle(
                    (py_min - py_pad, px_min - px_pad),
                    (py_max - py_min) + 2 * py_pad,
                    (px_max - px_min) + 2 * px_pad,
                    edgecolor=plate_colors[color_idx],
                    facecolor=plate_colors[color_idx],
                    alpha=0.12,
                    linewidth=1.5,
                    label=f'Plate {pid} area'
                )
                axes[1].add_patch(rect)

                # COP path on the plate (px on vertical axis)
                axes[1].plot(py_vals, px_vals, color=plate_colors[color_idx], linewidth=1.3, label=f'Plate {pid} COP')
                axes[1].scatter(py_vals[0], px_vals[0], color=plate_colors[color_idx], s=14)
                has_cop = True

    if np.isfinite(total_cop_x).any() and np.isfinite(total_cop_y).any():
        axes[1].plot(total_cop_y, total_cop_x, color='k', linewidth=2.2, label='Weighted total COP')
        has_cop = True

    axes[1].set_xlabel('Point of Application py')
    axes[1].set_ylabel('Point of Application px')
    axes[1].set_title('Force Plates and COP Paths (Top View)')
    axes[1].set_aspect('equal', adjustable='datalim')
    axes[1].grid(True, alpha=0.3)
    if has_cop:
        handles, legend_labels = axes[1].get_legend_handles_labels()
        dedup = dict(zip(legend_labels, handles))
        axes[1].legend(dedup.values(), dedup.keys(), loc='best', fontsize=8)

    # Row 3: butterfly plot in force space using summed Fy-Fz (no COP coordinates)
    fy_sum = total_fy.to_numpy()
    fz_sum = total_fz.to_numpy()
    force_valid = np.isfinite(fy_sum) & np.isfinite(fz_sum) & (np.abs(fz_sum) > contact_force_threshold)

    if force_valid.any():
        fy_path = fy_sum[force_valid]
        fz_path = fz_sum[force_valid]

        # Downsample vectors for readability
        step = max(len(fy_path) // 260, 1)
        fy_plot = fy_path[::step]
        fz_plot = fz_path[::step]
        if len(fy_plot) > 1:
            u = np.diff(fy_plot, prepend=fy_plot[0])
            v = np.diff(fz_plot, prepend=fz_plot[0])
            axes[2].plot(fy_path, fz_path, color='0.72', linewidth=1.0, label='Summed Fy-Fz path')
            axes[2].quiver(fy_plot, fz_plot, u, v, angles='xy', scale_units='xy', scale=1.0, width=0.0022, color='tab:blue', alpha=0.9)
            axes[2].legend(loc='best')
        else:
            axes[2].plot(fy_plot, fz_plot, 'o', color='tab:blue')
    else:
        axes[2].text(0.5, 0.5, 'No valid Fy-Fz samples for butterfly plot', ha='center', va='center', transform=axes[2].transAxes)

    axes[2].set_xlabel('Summed Fy (Anterior-Posterior Force)')
    axes[2].set_ylabel('Summed Fz (Vertical Force)')
    axes[2].set_title('GRF Butterfly Plot (Summed Fy and Fz)')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()
    
def plot_GRF():

    adapter = opensim.C3DFileAdapter()
    adapter.setLocationForForceExpression(opensim.C3DFileAdapter.ForceLocation_CenterOfPressure)

    c3d_filepath = input("Enter the path to the .c3d file: ").strip().strip('"')
    
    c3d_data = adapter.read(c3d_filepath)
    forces_table = adapter.getForcesTable(c3d_data)
    rotate_data_table(forces_table, [1, 0, 0], 180)
    time = forces_table.getIndependentColumn()
    forces_table = forces_table.flatten(['x', 'y', 'z'])
    
    raw_labels = list(forces_table.getColumnLabels())
    labels = transform_labels(raw_labels)

    # create a dataframe for plotting
    matrix = forces_table.getMatrix()
    matrix_data = [
        [matrix.getElt(row_idx, col_idx) for col_idx in range(matrix.ncol())]
        for row_idx in range(matrix.nrow())
    ]
    grf_df = pd.DataFrame(matrix_data, columns=labels)
    grf_df.insert(0, 'time', time)


    # Build grouped channels by force plate id (e.g., ground_force_1_vx, ground_force_1_px)
    force_pattern = re.compile(r"ground_force_(\d+)_v([xyz])$")
    cop_pattern = re.compile(r"ground_force_(\d+)_p([xy])$")

    plate_ids = sorted({
        int(m.group(1))
        for col in labels
        for m in [force_pattern.match(col), cop_pattern.match(col)]
        if m
    })

    total_fx = pd.Series(0.0, index=grf_df.index)
    total_fy = pd.Series(0.0, index=grf_df.index)
    total_fz = pd.Series(0.0, index=grf_df.index)

    plate_force_series = {}
    for pid in plate_ids:
        fx_col = f"ground_force_{pid}_vx"
        fy_col = f"ground_force_{pid}_vy"
        fz_col = f"ground_force_{pid}_vz"
        plate_force_series[pid] = {
            'vx': grf_df[fx_col].fillna(0.0) if fx_col in grf_df.columns else pd.Series(0.0, index=grf_df.index),
            'vy': grf_df[fy_col].fillna(0.0) if fy_col in grf_df.columns else pd.Series(0.0, index=grf_df.index),
            'vz': grf_df[fz_col].fillna(0.0) if fz_col in grf_df.columns else pd.Series(0.0, index=grf_df.index),
        }

        total_fx += plate_force_series[pid]['vx']
        total_fy += plate_force_series[pid]['vy']
        total_fz += plate_force_series[pid]['vz']

    contact_force_threshold = 20.0

    # Weighted COP using |Fz| as weight to avoid cancellation between plates
    weighted_x = np.zeros(len(grf_df))
    weighted_y = np.zeros(len(grf_df))
    total_weight = np.zeros(len(grf_df))

    for pid in plate_ids:
        px_col = f"ground_force_{pid}_px"
        py_col = f"ground_force_{pid}_py"
        fz_col = f"ground_force_{pid}_vz"
        if px_col in grf_df.columns and py_col in grf_df.columns and fz_col in grf_df.columns:
            px = grf_df[px_col].to_numpy()
            py = grf_df[py_col].to_numpy()
            wz = np.abs(grf_df[fz_col].fillna(0.0).to_numpy())
            valid = np.isfinite(px) & np.isfinite(py) & (wz > contact_force_threshold)
            weighted_x[valid] += px[valid] * wz[valid]
            weighted_y[valid] += py[valid] * wz[valid]
            total_weight[valid] += wz[valid]

    total_cop_x = np.full(len(grf_df), np.nan)
    total_cop_y = np.full(len(grf_df), np.nan)
    valid_total = total_weight > 0
    total_cop_x[valid_total] = weighted_x[valid_total] / total_weight[valid_total]
    total_cop_y[valid_total] = weighted_y[valid_total] / total_weight[valid_total]

    fig, axes = plt.subplots(1, 1, figsize=(13, 14))

    plate_colors = {pid: plt.cm.tab10((pid - 1) % 10) for pid in plate_ids}
    component_specs = [
        ('x', 'vx', '-', 1.0, 'Fx'),
        ('y', 'vy', '--', 1.2, 'Fy'),
        ('z', 'vz', ':', 1.6, 'Fz'),
    ]

    # Same plate keeps the same color; each force component gets its own line style.
    for pid in plate_ids:
        plate_color = plate_colors[pid]
        for axis_name, column_suffix, line_style, line_width, label_prefix in component_specs:
            column_name = f"ground_force_{pid}_{column_suffix}"
            series = grf_df[column_name].fillna(0.0) if column_name in grf_df.columns else pd.Series(0.0, index=grf_df.index)
            axes.plot(
                grf_df['time'],
                series,
                linewidth=line_width,
                linestyle=line_style,
                color=plate_color,
                label=f'Plate {pid} {label_prefix}',
            )

    axes.plot(grf_df['time'], total_fx, color='k', linewidth=1.4, linestyle='-.', label='Sum Fx')
    axes.plot(grf_df['time'], total_fy, color='k', linewidth=1.8, linestyle='--', label='Sum Fy')
    axes.plot(grf_df['time'], total_fz, color='k', linewidth=2.0, linestyle='-', label='Sum Fz')