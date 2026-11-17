# `bioscout.utils.io`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py)

bioscout.utils.io — motion-capture file I/O (TRC / MOT / STO / C3D) and XML  
helpers. Extracted from utils/__init__.py.

Pure os/re/numpy/pandas/xml (+ c3d when installed); no bioscout-global state.

## Contents

- [`check_path`](#check_path) — Check if a path exists and is a directory.
- [`load_c3d`](#load_c3d) — Load a .c3d file into a pandas DataFrame.
- [`load_trc`](#load_trc) — 
- [`load_sto`](#load_sto) — Load a .sto file into a pandas DataFrame.
- [`load_grf_mot`](#load_grf_mot) — 
- [`load_data_file`](#load_data_file) — Loads the motion capture data file into a pandas DataFrame.
- [`load_any_data_file`](#load_any_data_file) — Loads any data file (TRC, MOT, STO, C3D) into a pandas DataFrame.
- [`load_any_data_file_time_normalized`](#load_any_data_file_time_normalized) — Loads any data file (TRC, MOT, STO, C3D) into a pandas DataFrame and normalizes the time column.
- [`save_data_file`](#save_data_file) — Saves the DataFrame back to a file in the original format.
- [`load_sto_header`](#load_sto_header) — Loads the header of a .sto file and returns it as a list of strings.
- [`write_trc`](#write_trc) — Write marker data (frames, n_markers, 3) to TRC.
- [`write_mot`](#write_mot) — Write analog data (samples, n_channels) to MOT.
- [`write_sto_header`](#write_sto_header) — Writes the header for a .sto file.
- [`write_sto_file`](#write_sto_file) — Writes a pandas DataFrame to a .sto file with a specified header.
- [`read_xml`](#read_xml) — Reads an XML file and returns its content as a string.
- [`dict_to_xml`](#dict_to_xml) — Convert nested dictionary to XML elements recursively. Each dictionary key becomes an XML tag, handles unlimited nesting depth.
- [`save_pretty_xml`](#save_pretty_xml) — Saves the XML tree to a file with proper indentation and no blank lines.
- [`edit_xml_tag_value`](#edit_xml_tag_value) — Edits the value of a specific XML tag given its path.

### `check_path`

```python
check_path(path, create=False, isdir=False)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `create` | – | `False` |
| `isdir` | – | `False` |

Check if a path exists and is a directory.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L20)</sub>

### `load_c3d`

```python
load_c3d(path=None, output=0)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |
| `output` | – | `0` |

Load a .c3d file into a pandas DataFrame.

  
**Args**

    path (str): The path to the .c3d file. If None, prompts for input.  
    output (int): If 1, prints the columns of the DataFrame.

  
**Returns**

    pd.DataFrame: The loaded data from the .c3d file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L37)</sub>

### `load_trc`

```python
load_trc(path=None, output=False, combine_headers=False)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |
| `output` | – | `False` |
| `combine_headers` | – | `False` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L70)</sub>

### `load_sto`

```python
load_sto(path=None, output=0)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |
| `output` | – | `0` |

Load a .sto file into a pandas DataFrame.

  
**Args**

    path (str): The path to the .sto file. If None, prompts for input.  
    output (int): If 1, prints the columns of the DataFrame.

  
**Returns**

    pd.DataFrame: The loaded data from the .sto file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L118)</sub>

### `load_grf_mot`

```python
load_grf_mot(path=None, output=0)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |
| `output` | – | `0` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L192)</sub>

### `load_data_file`

```python
load_data_file(file_path)
```

| input | type | default |
|---|---|---|
| `file_path` | – | required |

Loads the motion capture data file into a pandas DataFrame.

This function reads the header to extract metadata and then loads the  
actual data into a structured DataFrame.

  
**Args**

    file_path (str): The path to the data file.

  
**Returns**

    tuple: A tuple containing:  
        - pd.DataFrame: The loaded data.  
        - dict: A dictionary with the file's metadata.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L219)</sub>

### `load_any_data_file`

```python
load_any_data_file(file_path)
```

| input | type | default |
|---|---|---|
| `file_path` | – | required |

Loads any data file (TRC, MOT, STO, C3D) into a pandas DataFrame.

  
**Args**

    file_path (str): The path to the data file.

  
**Returns**

    pd.DataFrame: The loaded data.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L282)</sub>

### `load_any_data_file_time_normalized`

```python
load_any_data_file_time_normalized(file_path, time_column='time')
```

| input | type | default |
|---|---|---|
| `file_path` | – | required |
| `time_column` | – | `'time'` |

Loads any data file (TRC, MOT, STO, C3D) into a pandas DataFrame and normalizes the time column.

  
**Args**

    file_path (str): The path to the data file.  
    time_column (str): The name of the time column to normalize.

**Returns**

    pd.DataFrame: The loaded and time-normalized data.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L335)</sub>

### `save_data_file`

```python
save_data_file(file_path, data, metadata)
```

| input | type | default |
|---|---|---|
| `file_path` | – | required |
| `data` | – | required |
| `metadata` | – | required |

Saves the DataFrame back to a file in the original format.

  
**Args**

    file_path (str): The path where the file will be saved.  
    data (pd.DataFrame): The DataFrame to save.  
    metadata (dict): The metadata to write to the header.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L356)</sub>

### `load_sto_header`

```python
load_sto_header(file_path)
```

| input | type | default |
|---|---|---|
| `file_path` | – | required |

Loads the header of a .sto file and returns it as a list of strings.

  
**Args**

    file_path (str): The path to the .sto file.

  
**Returns**

    list: A list of strings representing the header lines.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L404)</sub>

### `write_trc`

```python
write_trc(markers_df, trc_file, units, frame_rate, first_frame)
```

| input | type | default |
|---|---|---|
| `markers_df` | – | required |
| `trc_file` | – | required |
| `units` | – | required |
| `frame_rate` | – | required |
| `first_frame` | – | required |

Write marker data (frames, n_markers, 3) to TRC.

  
**inputs**

    markers_df: The DataFrame containing the marker data with a multi-index for columns (Marker, Coordinate). (use load_trc to read in the data and get the correct format) - DO NOT INCLUDE #FRAME column

    trc_file: The path to the output TRC file.

    units: The units for the marker data (e.g., 'mm' or 'm').

    frame_rate: The frame rate of the data (e.g., 100 for 100 Hz).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L426)</sub>

### `write_mot`

```python
write_mot(analog_df, labels, mot_file)
```

| input | type | default |
|---|---|---|
| `analog_df` | – | required |
| `labels` | – | required |
| `mot_file` | – | required |

Write analog data (samples, n_channels) to MOT.

  
**inputs**

    labels: The labels for the analog channels.  
    analog_df: The DataFrame containing the analog data.  
    

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L480)</sub>

### `write_sto_header`

```python
write_sto_header(writer, dataFrame)
```

| input | type | default |
|---|---|---|
| `writer` | – | required |
| `dataFrame` | – | required |

Writes the header for a .sto file.

  
**Args**

    writer (TextIOWrapper): The file writer object.  
    dataFrame (pd.DataFrame): The DataFrame containing the data.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L516)</sub>

### `write_sto_file`

```python
write_sto_file(dataFrame, file_path)
```

| input | type | default |
|---|---|---|
| `dataFrame` | – | required |
| `file_path` | – | required |

Writes a pandas DataFrame to a .sto file with a specified header.

  
**Args**

    dataFrame (pd.DataFrame): The DataFrame to write.  
    file_path (str): The path where the .sto file will be saved.  
    header (list): A list of strings representing the header lines to write.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L554)</sub>

### `read_xml`

```python
read_xml(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Reads an XML file and returns its content as a string.

  
**Args**

    path (str): The path to the XML file.

  
**Returns**

    str: The content of the XML file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L584)</sub>

### `dict_to_xml`

```python
dict_to_xml(parent_elem, data_dict)
```

| input | type | default |
|---|---|---|
| `parent_elem` | – | required |
| `data_dict` | – | required |

Convert nested dictionary to XML elements recursively.  
Each dictionary key becomes an XML tag, handles unlimited nesting depth.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L604)</sub>

### `save_pretty_xml`

```python
save_pretty_xml(tree, save_path)
```

| input | type | default |
|---|---|---|
| `tree` | – | required |
| `save_path` | – | required |

Saves the XML tree to a file with proper indentation and no blank lines.

Creates the parent directory if it is missing. Every caller here  
has already decided where the file goes, so a missing folder is  
never the answer -- and it used to be a real failure: an  
UNCALIBRATED CEINMS arm writes excitationGenerator.xml into  
`ceinms_calibration/`, which only the CALIBRATION path had ever  
created. The arm died with FileNotFoundError, bioscout logged it  
instead of raising, and the run reported success in 30 seconds  
having produced nothing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L627)</sub>

### `edit_xml_tag_value`

```python
edit_xml_tag_value(xml_path, tag, new_value)
```

| input | type | default |
|---|---|---|
| `xml_path` | – | required |
| `tag` | – | required |
| `new_value` | – | required |

Edits the value of a specific XML tag given its path.

  
**Args**

    xml_path (str): The path to the XML file.  
    tag (str): The tag whose value needs to be edited.   
    new_value (str): The new value to set for the specified tag.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/io.py#L650)</sub>
