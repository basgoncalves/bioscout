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

# Access functions defined in utils/__init__.py
try:
    # Works when imported as package: app.utils.exportC3D
    from . import load_any_data_file, filter_emg, osimTools, write_mot
except (ImportError, ValueError):
    # Works when running file directly or dynamically loaded
    import sys
    from pathlib import Path
    _utils_path = str(Path(__file__).parent)
    if _utils_path not in sys.path:
        sys.path.insert(0, _utils_path)
    # Use the already-cached utils module to avoid re-executing __init__.py
    # (re-executing it would trigger circular imports again)
    import utils as _utils_mod
    load_any_data_file = _utils_mod.load_any_data_file
    filter_emg = _utils_mod.filter_emg
    osimTools = _utils_mod.osimTools
    write_mot = _utils_mod.write_mot


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
        
    # write events.csv file
    data = [['start', start_time],
            ['end', end_time]]
    events = pd.DataFrame(data)
    events.to_csv(os.path.dirname(trc_filepath) + '/events.csv', index=False, header=False)
    print(f"Successfully exported {os.path.dirname(trc_filepath) + '/events.csv'}")
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

def export_emg(c3d_filepath, emg_strings_list=['emg'], reset_time=True):
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
    analog_df = pd.DataFrame(rows, columns=analog_labels)
    analog_df.insert(0, 'time', time)

    if reset_time:
        analog_df['time'] = analog_df['time'] - analog_df['time'].iloc[0]

    # Save analog to csv
    analog_path = os.path.join(os.path.dirname(c3d_filepath), "analog.csv")
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

    emg_mot_path = os.path.join(os.path.dirname(c3d_filepath), "emg.mot")

    if emg_indices:
        emg_labels = [analog_labels[i] for i in emg_indices]
        write_mot(analog_df, emg_labels, emg_mot_path)
        print(f"Successfully exported {emg_mot_path}")

        # Filter emg mot only if it was created
        fs = 1 / (analog_df['time'].iloc[1] - analog_df['time'].iloc[0])
        highcut_bp = fs/2 * 0.9
        filter_emg(emg_path=emg_mot_path, highcut_bp=highcut_bp, lowcut_bp=20, lowcut_lp=6, order_bp=4, order_lp=4)
    else:
        print("Warning: No EMG channels found among available analog channels.")
        print(f"[DEBUG] Searched for {len(emg_strings_list)} patterns in {len(analog_labels)} available channels")
       
def export_markers(c3d_filepath, strings_to_remove=[]):
    print(f"Exporting markers for {c3d_filepath}")

    # OpenSim data adapters
    adapter = opensim.C3DFileAdapter()
    adapter.setLocationForForceExpression(
        opensim.C3DFileAdapter.ForceLocation_CenterOfPressure)
    trc_adapter = opensim.TRCFileAdapter()

    # get markers
    task = adapter.read(c3d_filepath)
    markers_task = adapter.getMarkersTable(task)
    output_dir = os.path.dirname(c3d_filepath)

    # process markers of task and save to .trc file
    rotate_data_table(markers_task, [1, 0, 0], -90)

    # remove unwanted strings from labels
    labels = list(markers_task.getColumnLabels())
    for s in strings_to_remove:
        labels = [re.sub(s, '', lbl) for lbl in labels]

    markers_task.setColumnLabels(labels)

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
    
def export_grf(c3d_filepath):

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
    rotate_data_table(forces_table, [1, 0, 0], 180)
    time = forces_table.getIndependentColumn()
    forces_table = forces_table.flatten(['x', 'y', 'z'])

    # replace f,p,m for ground_force_v, ground_force_p, ground_torque
    labels = transform_labels(list(forces_table.getColumnLabels()))
    osim_tools = osimTools()
    force_sto = osim_tools._create_opensim_storage(time, forces_table.getMatrix(), labels)
    force_sto.setName('grf')
    output_dir = os.path.dirname(c3d_filepath)
    grf_file = os.path.join(output_dir, 'grf.mot')
    force_sto.printResult(force_sto, 'grf', output_dir, 0.01, '.mot')
    print(f"Successfully exported {grf_file}")

    # Clean NaN rows from exported GRF file
    print(f"Cleaning NaN rows from GRF data...")
    crop_info = crop_nans(grf_file)
    if crop_info:
        rows_removed = crop_info['rows_removed_start'] + crop_info['rows_removed_end']
        if rows_removed > 0:
            print(f"  [OK] Removed {rows_removed} NaN rows from GRF file")
        else:
            print(f"  [OK] No NaN rows to remove (data is clean)")

def main(c3d_filepath, emg_string_list=['emg'], create_folder=False):
    
    # create a directory for the output files   
    output_dir = os.path.dirname(c3d_filepath)

    if create_folder:
        output_dir = os.path.join(output_dir, os.path.basename(c3d_filepath).replace('.c3d', ''))
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")

    # copy the c3d file to the output directory for reference
    c3d_output_path = os.path.join(output_dir, os.path.basename(c3d_filepath))
    if not os.path.exists(c3d_output_path):
        shutil.copy(c3d_filepath, c3d_output_path)
        print(f"Copied {c3d_filepath} to {c3d_output_path}")

    try:
        export_markers(c3d_output_path, strings_to_remove = [])
    except Exception as e:
        print(f"An error occurred while exporting markers")

    try:
        export_grf(c3d_output_path)
    except Exception as e:
        print(f"An error occurred while exporting ground reaction forces")
        
    try:
        export_emg(c3d_output_path, emg_strings_list=emg_string_list)
    except Exception as e:
        print(f"An error occurred while exporting EMG data")

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
    axes.set_xlabel('Time (s)')
    axes.set_ylabel('Force (N)')
    axes.set_title('Ground Reaction Forces by Plate (Fx, Fy, and Fz)')
    axes.grid(True, alpha=0.3)
    axes.legend(ncol=3, fontsize=8)


    plt.show()



if __name__ == "__main__":

    # c3d_filepath = input("Enter the path to the .c3d file: ").strip().strip('"')

    # grf_from_c3d(c3d_filepath)
    plot_GRF()

    exit()
    
    # Check if file exists
    if not os.path.exists(c3d_filepath):
        print(f"Error: File not found at {c3d_filepath}")
        exit(1)    
    
    # Check if it's a .c3d file
    if not c3d_filepath.lower().endswith('.c3d'):
        print(f"Error: File must be a .c3d file, got {c3d_filepath}")
        exit(1)
    
    print(f"Processing {c3d_filepath}")
    
    main(c3d_filepath, create_folder=False, emg_string_list='TIBANTR_EMG_1_v	SOLEUSL_EMG_10_v	GASLATL_EMG_11_v	VLL_EMG_12_v	RECFL_EMG_13_v	GMEDL_EMG_14_v	GMAXL_EMG_15_v	SEMITENL_EMG_16_v	SOLEUSR_EMG_2_v	GASLATR_EMG_3_v	VLR_EMG_4_v	RECFR_EMG_5_v	GMEDR_EMG_6_v	GMAXR_EMG_7_v	SEMITENR_EMG_8_v	TIBANTL_EMG_9_v'.split())

# END