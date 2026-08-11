"""
bioscout.utils.io — motion-capture file I/O (TRC / MOT / STO / C3D) and XML
helpers. Extracted from utils/__init__.py.

Pure os/re/numpy/pandas/xml (+ c3d when installed); no bioscout-global state.
"""
import os
import re
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom

try:
    import c3d
except ImportError:
    c3d = None


def check_path(path, create=False, isdir=False):
    """Check if a path exists and is a directory."""
    if not os.path.exists(path):        
        if create:
            try:
                os.makedirs(path)
                print("[INFO] Created directory:", path)
            except Exception as e:
                print("[ERROR] Could not create directory:", path, "Error:", e)
        else:
            print("[ERROR] Path does not exist:", path)
    if isdir and not os.path.isdir(path):
        print("[ERROR] Path is not a directory:", path)

    return path, os.path.isdir(path)

# loading data files
def load_c3d(path=None, output=0):
    """
    Load a .c3d file into a pandas DataFrame.

    Args:
        path (str): The path to the .c3d file. If None, prompts for input.
        output (int): If 1, prints the columns of the DataFrame.

    Returns:
        pd.DataFrame: The loaded data from the .c3d file.
    """
    
    if not check_path(path):
        path = input("Please provide the path to the .c3d file: ")

    try:
        reader = c3d.Reader(open(path, 'rb'))

        # turn into pandas DataFrame
        points = []
        for frame in reader.read_frames():
            points.append(frame[1])
        points = np.array(points)
        columns = [f'Marker_{i+1}_{coord}' for i in range(points.shape[1]) for coord in ['X', 'Y', 'Z', 'Residual']]
        reader = pd.DataFrame(points.reshape(points.shape[0], -1), columns=columns)
        if output == 1: print(reader.columns)
        
        return reader 
    except Exception as e:
        print(f"Error: Could not read the file at {path}. Please check the file format and try again.")
        print(f"Details: {e}")
        return None
        
def load_trc(path=None, output=False, combine_headers=False):
    
    if not check_path(path):
        path = input("Please provide the path to the .trc file: ")

    # find line with '#Frame' to skip the header
    try:
        with open(path, 'r') as file:
            for i, line in enumerate(file):
                if 'Frame#' in line:
                    header_start_line = i
                    break
    except:
        print(f"Error: Could not read the file at {path}. Please check the path and try again.")
        return None
    
    header_start_line += 0
    df = pd.read_csv(path,sep='\t',skiprows=header_start_line,index_col=False)
    # print(df.head())
    # Create a temporary frame from the multi-index, forward-fill, and get values
    markers = df.columns.tolist()
    coordinates = df.iloc[0].to_list()  # First row contains sub-headers

    # replace Unnamed with empty cells
    for idx, marker in enumerate(markers):
        if marker.startswith('Unnamed'):
            markers[idx] = markers[idx-1]
    
    coordinates = [coord if not pd.isna(coord) else '' for coord in coordinates]

    # create multi-index dataFrame and delete row 0
    df.columns = pd.MultiIndex.from_tuples(zip(markers, coordinates), names=['Marker', 'Coordinate'])
    df = df.iloc[1:]
    
    # print(df.head())
    # if needed make 'time' lower case (only)
    if 'Time' in df.columns:
        df = df.rename(columns={'Time': 'time'})
        
    # if needed combine headers
    if combine_headers:
        df.columns = df.columns.map(lambda x: f"{x[0]}_{x[1]}" if x[1] else x[0])

    if output == 1: print(df.columns)
    # print(df.head())
    # breakpoint()
    return df

def load_sto(path=None, output=0):
    """
    Load a .sto file into a pandas DataFrame.

    Args:
        path (str): The path to the .sto file. If None, prompts for input.
        output (int): If 1, prints the columns of the DataFrame.

    Returns:
        pd.DataFrame: The loaded data from the .sto file.
    """
    
    if not check_path(path):
        path = input("Please provide the path to the .sto file: ")

    # find line with 'endheader' to skip the header
    try:
        with open(path, 'r') as file:
            for i, line in enumerate(file):
                if 'endheader' in line or i > 100:  # Limit to first 100 lines to avoid long files
                        break
    except:
        print(f"Error: Could not read the file at {path}. Please check the path and try again.")
        return None

    # read the file into a pandas DataFrame, skipping the header. Search downward for
    # the row holding the 'time' column. A wrong-guess header row can raise MORE than
    # just ParserError (many-column files — e.g. a 33-col deadlift emg.mot with extra
    # force-plate/analog channels — raise other pandas errors), so catch ANY read
    # error and advance; otherwise a perfectly valid file is wrongly rejected as None.
    # low_memory=False avoids mixed-type column inference on large multi-column files.
    try:
        columns = []
        offset = -3
        while 'time' not in columns:
            try:
                data = pd.read_csv(path, sep=r'\s+', header=i+offset, low_memory=False)
                columns = data.columns
            except Exception:
                pass
            offset += 1
            if offset > 100:
                print(f"Error: Could not find 'time' column in the file {path}. Please check the file format.")
                return None
    except Exception as e:
        print(f"Error: Could not read the file at {path}. Please check the file format and try again.")
        print(f"Details: {e}")
        return None

    if output == 1: print(data.columns)

    return data

def load_grf_mot(path=None, output=0):
    
    if not check_path(path):
        path = input("Please provide the path to the .mot file: ")

    # find line with 'endheader' to skip the header
    try:
        with open(path, 'r') as file:
            for i, line in enumerate(file):
                if 'endheader' in line:
                        break
    except:
        print(f"Error: Could not read the file at {path}. Please check the path and try again.")
        return None

    # read the file into a pandas DataFrame, skipping the header
    try:
        data = pd.read_csv(path, sep=r'\s+', header=i+1)
    except Exception as e:
        print(f"Error: Could not read the file at {path}. Please check the file format and try again.")
        print(f"Details: {e}")
        return None

    if output == 1: print(data.columns)

    return data

def load_data_file(file_path):
    """
    Loads the motion capture data file into a pandas DataFrame.

    This function reads the header to extract metadata and then loads the
    actual data into a structured DataFrame.

    Args:
        file_path (str): The path to the data file.

    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: The loaded data.
            - dict: A dictionary with the file's metadata.
    """
    metadata = {}
    header_lines = []
    
    # Read the header part of the file first to extract metadata
    with open(file_path, 'r') as f:
        for i in range(5):  # First 5 lines are metadata or headers
            line = f.readline().strip()
            header_lines.append(line)
            if i < 2: # The first two lines contain key-value metadata
                parts = line.split('\t')
                for j in range(0, len(parts), 2):
                    if j + 1 < len(parts) and parts[j]:
                        metadata[parts[j]] = parts[j+1]

    # The 4th line contains the main column headers (FHD, RBHD, etc.)
    # The 5th line contains the sub-column headers (X1, Y1, etc.)
    main_headers = re.split(r'\s+', header_lines[3].strip())[2:] # Skip first two empty items
    sub_headers = re.split(r'\s+', header_lines[4].strip())[2:] # Skip first two items

    # Create a MultiIndex (hierarchical column names) for the DataFrame
    # This matches your file's structure (e.g., FHD -> X1, Y1, Z1)
    header_tuples = []
    i = 0
    for main_header in main_headers:
        if main_header: # Check if it's not an empty string
            # Each main header corresponds to a set of sub-headers (e.g., X, Y, Z coordinates)
            num_sub_headers = 3 # Assuming X, Y, Z for markers. Adjust if needed.
            for j in range(num_sub_headers):
                header_tuples.append((main_header, sub_headers[i]))
                i += 1

    # Define the column names for the first two columns
    final_column_names = [('Frame', '#'), ('Time', '')] + header_tuples

    # Load the actual data, skipping the header rows
    data = pd.read_csv(
        file_path,
        sep='\t',        # Data is separated by tabs
        header=None,     # We are providing our own column names
        skiprows=6,      # Skip the metadata and header lines we already processed
        engine='python'  # Use python engine for more flexibility with separators
    )
    
    # Assign the hierarchical column names to the DataFrame
    data.columns = pd.MultiIndex.from_tuples(final_column_names)

    return data, metadata

def load_any_data_file(file_path):
    """
    Loads any data file (TRC, MOT, STO, C3D) into a pandas DataFrame.

    Args:
        file_path (str): The path to the data file.

    Returns:
        pd.DataFrame: The loaded data.
    """
    
    if file_path.endswith('.trc'):
        return load_trc(file_path)
    
    elif file_path.endswith('.mot'):
        return load_sto(file_path)
    
    elif file_path.endswith('.sto'):
        return load_sto(file_path)
    
    elif file_path.endswith('.c3d'):
        return load_c3d(file_path)
    
    elif file_path.endswith('.csv'):
        return pd.read_csv(file_path)
        
    elif file_path.endswith('.txt'):
        # Assuming these are plain text files with tab-separated values
        return pd.read_csv(file_path, sep='\t', header=0)
    
    elif file_path.endswith('.xml'):
        # For XML files, we can use the XML_tools module to read them
        tree = ET.parse(file_path)
        if tree is not None:
            return tree
        else:
            raise ValueError(f"Could not read XML file: {file_path}")
    
    else:
        try:
            # Try to read as a generic text file
            with open(file_path, 'r') as f:
                data = f.readlines()
            # Assuming the first line is a header
            header = data[0].strip().split('\t')
            # Load the rest of the data into a DataFrame
            data = [line.strip().split('\t') for line in data[1:]]
            return pd.DataFrame(data, columns=header)
        
        except Exception as e:
            print(f"Error: Could not read the file at {file_path}. Please check the file format and try again.")
            print(f"Details: {e}")

def load_any_data_file_time_normalized(file_path, time_column='time'):
    """
    Loads any data file (TRC, MOT, STO, C3D) into a pandas DataFrame and normalizes the time column.

    Args:
        file_path (str): The path to the data file.
        time_column (str): The name of the time column to normalize.
    Returns:
        pd.DataFrame: The loaded and time-normalized data.
    """
    data = load_any_data_file(file_path)
    
    if time_column in data.columns:
        from bioscout.utils import time_normalise_df  # lazy: lives in __init__
        data = time_normalise_df(data)
    else:
        print(f"Warning: Time column '{time_column}' not found in data.")
    
    return data

# Saving data files
def save_data_file(file_path, data, metadata):
    """
    Saves the DataFrame back to a file in the original format.

    Args:
        file_path (str): The path where the file will be saved.
        data (pd.DataFrame): The DataFrame to save.
        metadata (dict): The metadata to write to the header.
    """
    with open(file_path, 'w') as f:
        # Write metadata lines
        # This part reconstructs the first two header lines from the metadata dictionary
        # It's a bit manual to match the format exactly.
        f.write(f"PathFileType\t4\t(X/Y/Z)\t{metadata.get('PathFileType', '')}\n")
        f.write(f"DataRate\t{metadata.get('DataRate', '')}\tCameraRate\t{metadata.get('CameraRate', '')}\tNumFrames\t{metadata.get('NumFrames', '')}\tNumMarkers\t{metadata.get('NumMarkers', '')}\tUnits\t{metadata.get('Units', '')}\tOrigDataRate\t{metadata.get('OrigDataRate', '')}\tOrigDataStartFrame\t{metadata.get('OrigDataStartFrame', '')}\tOrigNumFrames\t{metadata.get('OrigNumFrames', '')}\n")
        f.write('\n') # The empty line
        
        # Reconstruct the column headers
        main_headers = data.columns.get_level_values(0)
        sub_headers = data.columns.get_level_values(1)
        
        # Write main headers line
        f.write("Frame#\tTime\t")
        unique_main_headers = main_headers.unique()
        # This logic ensures each main header is printed once and padded correctly
        header_line = ""
        last_main = ""
        for main in main_headers[2:]: # Skip Frame and Time
            if main != last_main:
                header_line += f"{main}\t\t\t" # Assuming 3 sub-columns, hence 3 tabs
                last_main = main
        f.write(header_line.strip() + '\n')

        # Write sub-headers line
        f.write("\t\t") # Align with the data columns
        f.write('\t'.join(sub_headers[2:]) + '\n')
        f.write('\n') # The final empty line before data

    # Append the data to the file
    data.to_csv(
        file_path,
        mode='a',          # Append to the file we just created with the header
        header=False,      # Don't write DataFrame headers again
        index=False,       # Don't write the DataFrame index
        sep='\t',          # Use tabs as separators
        float_format='%.6f'# Format floats to 6 decimal places
    )

def load_sto_header(file_path):
    """
    Loads the header of a .sto file and returns it as a list of strings.

    Args:
        file_path (str): The path to the .sto file.

    Returns:
        list: A list of strings representing the header lines.
    """
    header = []
    break_next = False
    with open(file_path, 'r') as f:
        for line in f:
            if break_next:
                break
            if 'endheader' in line:
                break_next = True
            header.append(line.strip())
    
    return header

def write_trc(markers_df, trc_file, units, frame_rate, first_frame):
    """
    Write marker data (frames, n_markers, 3) to TRC.

    inputs:
        markers_df: The DataFrame containing the marker data with a multi-index for columns (Marker, Coordinate). (use load_trc to read in the data and get the correct format) - DO NOT INCLUDE #FRAME column

        trc_file: The path to the output TRC file.

        units: The units for the marker data (e.g., 'mm' or 'm').

        frame_rate: The frame rate of the data (e.g., 100 for 100 Hz).

    """
    
    # remove time column
    time = markers_df["time"]
    markers_df = markers_df.drop(columns=["time"])
    
    num_frames = markers_df.shape[0]
    marker_labels = markers_df.columns.droplevel(1).to_list()
    
    # only unique labels
    marker_labels = list(dict.fromkeys(marker_labels))
    n_markers = len(marker_labels)

    with open(trc_file, "w") as writer:
        # Header
        writer.write(f"PathFileType\t4\t(X/Y/Z)\t{os.path.basename(writer.name)}\n")
        writer.write("DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n")
        writer.write(f"{frame_rate}\t{frame_rate}\t{num_frames}\t{n_markers}\t{units}\t{frame_rate}\t{first_frame}\t{num_frames}\n")

        # Marker names
        header = "Frame#\tTime\t" + "\t".join([f"{name}\t\t" for name in marker_labels]) + "\n"
        writer.write(header)

        # Coordinate labels
        coord_line = "\t\t" + "\t".join([f"X{i+1}\tY{i+1}\tZ{i+1}" for i in range(n_markers)]) + "\n"
        writer.write(coord_line)

        # add an empty line
        writer.write("\n")

        markers_df = markers_df.apply(pd.to_numeric, errors="coerce")
        # Data rows
        for i in range(num_frames):
            frame_num = first_frame + i
            time_val = time.iloc[i]
            row = [f"{frame_num}", f"{time_val:.6f}"]
            row.extend([f"{coord:.6f}" for coord in markers_df.iloc[i].values])
            writer.write("\t".join(row) + "\n")

    print(f"Saved TRC file to: {os.path.abspath(trc_file)}")

def write_mot(analog_df, labels, mot_file):
    """
    Write analog data (samples, n_channels) to MOT.
    
    inputs:
        labels: The labels for the analog channels.
        analog_df: The DataFrame containing the analog data.
        
    """
    
    # make sure labels include time
    labels = ['time'] + labels

    # Crop dataframe to include only labels
    analog_df = analog_df[labels]
    num_samples, num_columns = analog_df.shape
    
    # create writer
    with open(mot_file, "w") as writer:
        # Header
        writer.write(f"{os.path.basename(writer.name)}\n")
        writer.write("version=1\n")
        writer.write(f"nRows={num_samples}\n")
        writer.write(f"nColumns={num_columns}\n") 
        writer.write("in_degrees=yes\n")
        writer.write("endheader\n")

        # Column labels
        writer.write("\t".join(labels) + "\n")
    
        # Data rows
        for i, row in analog_df.iterrows():
            # breakpoint()
            writer.write(f"{row['time']:.6f}\t" + "\t".join([f"{val:.6f}" for val in row[1:]]) + "\n")

def write_sto_header(writer, dataFrame):
    """
    Writes the header for a .sto file.

    Args:
        writer (TextIOWrapper): The file writer object.
        dataFrame (pd.DataFrame): The DataFrame containing the data.
    """
    writer.write(f"{os.path.basename(writer.name)}\n")
    writer.write("version=1\n")
    writer.write(f"nRows={dataFrame.shape[0]}\n")
    writer.write(f"nColumns={dataFrame.shape[1]}\n")
    writer.write("in_degrees=yes\n")
    writer.write("endheader\n")

def write_sto_file(dataFrame, file_path):
    """
    Writes a pandas DataFrame to a .sto file with a specified header.

    Args:
        dataFrame (pd.DataFrame): The DataFrame to write.
        file_path (str): The path where the .sto file will be saved.
        header (list): A list of strings representing the header lines to write.
    """
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))
        print(f"Created directory: {os.path.dirname(file_path)}")
        
    # make time lowercase
    if 'Time' in dataFrame.columns:
        dataFrame = dataFrame.rename(columns={"Time": "time"})
        

    with open(file_path, 'w', newline='') as f:
        # Write the header lines
        write_sto_header(f, dataFrame)

        # bring time column to front
        dataFrame = dataFrame[['time'] + [col for col in dataFrame.columns if col != 'time']]

        # Write the data without extra line spaces
        dataFrame.to_csv(f, sep='\t', index=False, float_format='%.6f')

# XML handling
def read_xml(path):
    """
    Reads an XML file and returns its content as a string.

    Args:
        path (str): The path to the XML file.

    Returns:
        str: The content of the XML file.
    """
    try:
        tree = ET.parse(path)
        return tree
    except FileNotFoundError:
        print(f"Error: The file at {path} does not exist.")
        return None
    except Exception as e:
        print(f"Error reading the file at {path}: {e}")
        return None

def dict_to_xml(parent_elem, data_dict):
    """
    Convert nested dictionary to XML elements recursively.
    Each dictionary key becomes an XML tag, handles unlimited nesting depth.
    """
    for key, value in data_dict.items():
        elem = ET.SubElement(parent_elem, key)

        if isinstance(value, dict):
            # Recursive call for nested dictionaries
            dict_to_xml(elem, value)
        elif isinstance(value, list):
            # Handle lists - each item becomes a separate element with same tag
            for item in value:
                if isinstance(item, dict):
                    dict_to_xml(elem, item)
                else:
                    item_elem = ET.SubElement(elem, "item")
                    item_elem.text = str(item)
        else:
            # If value is not a dict or list, set it as text content
            elem.text = str(value)

def save_pretty_xml(tree, save_path):
            """Saves the XML tree to a file with proper indentation and no blank lines.

            Creates the parent directory if it is missing. Every caller here
            has already decided where the file goes, so a missing folder is
            never the answer -- and it used to be a real failure: an
            UNCALIBRATED CEINMS arm writes excitationGenerator.xml into
            `ceinms_calibration/`, which only the CALIBRATION path had ever
            created. The arm died with FileNotFoundError, bioscout logged it
            instead of raising, and the run reported success in 30 seconds
            having produced nothing.
            """
            rough_string = ET.tostring(tree.getroot(), 'utf-8')
            reparsed = xml.dom.minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="   ")
            # Remove blank lines
            pretty_xml_no_blanks = "\n".join([line for line in pretty_xml.splitlines() if line.strip()])
            _parent = os.path.dirname(os.path.abspath(save_path))
            if _parent:
                os.makedirs(_parent, exist_ok=True)
            with open(save_path, 'w') as file:
                file.write(pretty_xml_no_blanks)

def edit_xml_tag_value(xml_path, tag, new_value): 
    """Edits the value of a specific XML tag given its path.
    
    Args:
        xml_path (str): The path to the XML file.
        tag (str): The tag whose value needs to be edited. 
        new_value (str): The new value to set for the specified tag.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        elem_list = root.findall(f".//{tag}")
        
        if elem_list:
            for elem in elem_list:
                elem.text = str(new_value)
            save_pretty_xml(tree, xml_path)  # Save back to the original file
            print(f"Updated tag '{tag}' to new value: {new_value}")
        else:
            print(f"Error: Tag '{tag}' not found in the XML tree.")
    except Exception as e:
        print(f"Error editing XML tag '{tag}': {e}")
