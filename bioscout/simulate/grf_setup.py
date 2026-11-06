"""GRF.xml (OpenSim ExternalLoads) from a GRF .mot -- plain XML, no OpenSim.

Moved out of bioscout.simulate.opensim (2026-11-03) so the pyosim engine can write the
same file without importing OpenSim; bioscout.simulate.opensim re-exports it."""
import os

from bioscout import utils

def create_grf_xml(grf_mot_path=None, output_xml_path=None,
                   marker_trc_path=None,
                   right_foot_markers=None, left_foot_markers=None,
                   right_foot_body='calcn_r', left_foot_body='calcn_l',
                   vert_force_threshold=10.0,
                   max_cop_foot_dist_mm=None,
                   filter_cutoff=6,
                   datafile=None):
    """
    Create a working OpenSim ExternalLoads XML (GRF.xml) from a GRF .mot file.

    Automatically detects force-plate column names, assigns each plate to the
    left or right foot using marker TRC data or COP Z-position heuristic, and
    writes a correctly-formatted GRF.xml.

    Parameters
    ----------
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
    """
    import re
    import xml.etree.ElementTree as ET

    if not os.path.exists(grf_mot_path):
        raise FileNotFoundError(f"GRF .mot file not found: {grf_mot_path}")

    if output_xml_path is None:
        output_xml_path = os.path.join(os.path.dirname(grf_mot_path), 'GRF.xml')

    if datafile is None:
        datafile = os.path.basename(grf_mot_path)

    # ------------------------------------------------------------------ #
    # 1. Load .mot and detect column name patterns per force plate
    # ------------------------------------------------------------------ #
    grf_df = utils.load_sto(grf_mot_path)
    cols = grf_df.columns.tolist()

    # plates[plate_number] = {'force_id': ..., 'point_id': ..., 'torque_id': ...}
    plates = {}

    for col in cols:
        if col.lower() == 'time':
            continue

        # Force columns: end in vx/vy/vz (e.g. ground_force3_vx)
        if re.search(r'vx$', col, re.IGNORECASE) and 'force' in col.lower():
            identifier = col[:-1]   # strip trailing 'x' → e.g. 'ground_force3_v'
            nums = re.findall(r'\d+', col)
            if nums:
                plates.setdefault(nums[0], {})['force_id'] = identifier
            continue

        # Point columns: end in px/py/pz (e.g. ground_force3_px)
        if re.search(r'px$', col, re.IGNORECASE) and 'force' in col.lower():
            identifier = col[:-1]   # → e.g. 'ground_force3_p'
            nums = re.findall(r'\d+', col)
            if nums:
                plates.setdefault(nums[0], {})['point_id'] = identifier
            continue

        # Torque columns: contain 'torque' and end in x (e.g. ground_torque3_x or ground_torque3_mx)
        if re.search(r'x$', col, re.IGNORECASE) and 'torque' in col.lower():
            identifier = col[:-1]   # → e.g. 'ground_torque3_' or 'ground_torque3_m'
            nums = re.findall(r'\d+', col)
            if nums:
                plates.setdefault(nums[0], {})['torque_id'] = identifier

    if not plates:
        raise ValueError("No force plate columns detected in the .mot file. "
                         "Expected columns like 'ground_force1_vx', 'ground_force1_px', etc.")

    print(f"Detected force plates: {sorted(plates.keys(), key=lambda x: int(x))}")
    for n, ids in sorted(plates.items(), key=lambda x: int(x[0])):
        print(f"  Plate {n}: force_id='{ids.get('force_id','')}', "
              f"point_id='{ids.get('point_id','')}', torque_id='{ids.get('torque_id','')}'")

    # ------------------------------------------------------------------ #
    # 2. Assign each plate to a foot
    # ------------------------------------------------------------------ #
    print("\nAssigning force plates to feet...")
    from bioscout.simulate.opensim import assign_grfs_to_feet  # lazy: avoids circular import
    plate_to_body = assign_grfs_to_feet(
        grf_mot_path=grf_mot_path,
        marker_trc_path=marker_trc_path,
        right_foot_markers=right_foot_markers,
        left_foot_markers=left_foot_markers,
        right_foot_body=right_foot_body,
        left_foot_body=left_foot_body,
        vert_force_threshold=vert_force_threshold,
        max_cop_foot_dist_mm=max_cop_foot_dist_mm,
    )

    # ------------------------------------------------------------------ #
    # 3. Build XML tree
    # ------------------------------------------------------------------ #
    root = ET.Element('OpenSimDocument')
    root.set('Version', '40000')

    ext_loads = ET.SubElement(root, 'ExternalLoads')
    ext_loads.set('name', 'externalloads')
    objects_el = ET.SubElement(ext_loads, 'objects')

    for plate_num in sorted(plates.keys(), key=lambda x: int(x)):
        ids = plates[plate_num]
        if 'force_id' not in ids or 'point_id' not in ids:
            continue

        # Only include plates that are actually in plate_to_body (have significant force data)
        if plate_num not in plate_to_body:
            continue

        body = plate_to_body[plate_num]
        side = 'r' if body == right_foot_body else 'l'
        force_name = f'grf_{side}_{plate_num}'

        ef = ET.SubElement(objects_el, 'ExternalForce')
        ef.set('name', force_name)
        ET.SubElement(ef, 'applied_to_body').text          = body
        ET.SubElement(ef, 'force_expressed_in_body').text  = 'ground'
        ET.SubElement(ef, 'point_expressed_in_body').text  = 'ground'
        ET.SubElement(ef, 'force_identifier').text         = ids['force_id']
        ET.SubElement(ef, 'point_identifier').text         = ids['point_id']
        ET.SubElement(ef, 'torque_identifier').text        = ids.get('torque_id', '')
        ET.SubElement(ef, 'data_source_name').text         = ''

    ET.SubElement(ext_loads, 'groups')
    ET.SubElement(ext_loads, 'datafile').text = datafile
    ET.SubElement(ext_loads, 'external_loads_model_kinematics_file').text = ''
    ET.SubElement(ext_loads, 'lowpass_cutoff_frequency_for_load_kinematics').text = str(filter_cutoff)

    # ------------------------------------------------------------------ #
    # 4. Save using utils pretty-printer
    # ------------------------------------------------------------------ #
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, output_xml_path)

    print(f"\nGRF XML saved to: {os.path.abspath(output_xml_path)}")
    print(f"Plates: {sorted(plates.keys(), key=lambda x: int(x))}  |  Data file: {datafile}")
    return os.path.abspath(output_xml_path)
