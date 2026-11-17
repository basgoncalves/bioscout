# `bioscout.simulate.grf_setup`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/grf_setup.py)

GRF.xml (OpenSim ExternalLoads) from a GRF .mot -- plain XML, no OpenSim.

Moved out of bioscout.simulate.opensim (2026-11-03) so the pyosim engine can write the  
same file without importing OpenSim; bioscout.simulate.opensim re-exports it.

## Contents

- [`create_grf_xml`](#create_grf_xml) — Create a working OpenSim ExternalLoads XML (GRF.xml) from a GRF .mot file.

### `create_grf_xml`

```python
create_grf_xml(
    grf_mot_path=None,
    output_xml_path=None,
    marker_trc_path=None,
    right_foot_markers=None,
    left_foot_markers=None,
    right_foot_body='calcn_r',
    left_foot_body='calcn_l',
    vert_force_threshold=10.0,
    max_cop_foot_dist_mm=None,
    filter_cutoff=6,
    datafile=None
)
```

| input | type | default |
|---|---|---|
| `grf_mot_path` | – | `None` |
| `output_xml_path` | – | `None` |
| `marker_trc_path` | – | `None` |
| `right_foot_markers` | – | `None` |
| `left_foot_markers` | – | `None` |
| `right_foot_body` | – | `'calcn_r'` |
| `left_foot_body` | – | `'calcn_l'` |
| `vert_force_threshold` | – | `10.0` |
| `max_cop_foot_dist_mm` | – | `None` |
| `filter_cutoff` | – | `6` |
| `datafile` | – | `None` |

Create a working OpenSim ExternalLoads XML (GRF.xml) from a GRF .mot file.

Automatically detects force-plate column names, assigns each plate to the  
left or right foot using marker TRC data or COP Z-position heuristic, and  
writes a correctly-formatted GRF.xml.

  
**Parameters**

grf_mot_path : str  
    Path to the GRF .mot file containing force plate data.  
output_xml_path : str, optional  
    Output XML path. Defaults to GRF.xml next to the .mot file.  
marker_trc_path : str, optional  
    Marker TRC file used to assign plates to feet by comparing COP  
    positions to foot marker Z-positions.  
right_foot_markers : list of str, optional  
    Marker names for the right foot (e.g. ['RHEE', 'RTOE']).  
    If None, common names are tried automatically.  
left_foot_markers : list of str, optional  
    Marker names for the left foot (e.g. ['LHEE', 'LTOE']).  
    If None, common names are tried automatically.  
right_foot_body : str  
    OpenSim body for the right foot (default 'calcn_r').  
left_foot_body : str  
    OpenSim body for the left foot (default 'calcn_l').  
vert_force_threshold : float  
    Minimum vertical force (N) to consider a plate active (default 10.0).  
filter_cutoff : float  
    Low-pass filter cut-off for load kinematics in the XML (default 6 Hz).  
datafile : str, optional  
    Value for the <datafile> tag. Defaults to the basename of grf_mot_path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/grf_setup.py#L9)</sub>
