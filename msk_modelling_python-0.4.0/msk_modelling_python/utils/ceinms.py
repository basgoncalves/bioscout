import os
import sys
import shutil
import subprocess
import time
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET
import opensim as osim
import matplotlib.pyplot as plt
import pandas as pd
import scipy
import zipfile

_utils_dir = str(Path(__file__).parent)
_app_dir = str(Path(__file__).parent.parent)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
if _utils_dir in sys.path:
    sys.path.remove(_utils_dir)
sys.path.insert(0, _utils_dir)

import utils
import openSim
import settings

__version__ = '0.1.0'

MODEL_TYPE = 'Lernagopal' # 'Lernagopal', 'GPK', 'Catelli', 'Uhlrich'
EMG_MAPPING = 'Powerlifting_s1' # 'session1', 'session2', 'running_fai'


def upWorkingDirectory():
    current_dir = os.getcwd()
    parent_dir = os.path.dirname(current_dir)
    os.chdir(parent_dir)
    print(f"Changed working directory to: {parent_dir}")

def create_ceinms_model(osimModelPath=None, outputCEINMSModelPath=None, DOFs: list = None):
    """
    Create a CEINMS subject XML file with muscle parameters extracted from the OpenSim model.
    """
    if not osimModelPath:
        osimModelPath = input("Enter path to OpenSim model (.osim): ").strip('"')

    if not outputCEINMSModelPath:
        outputCEINMSModelPath = input("Enter path to output CEINMS model (.xml): ").strip('"')

    if DOFs is None:
        dof_raw = settings.CEINMSSettings.dof_set
        DOFs = dof_raw.split() if isinstance(dof_raw, str) else list(dof_raw)
        print(f"Using DOFs: {' '.join(DOFs)}")
        time.sleep(2)

    requested_dofs = list(DOFs)  # keep a copy before filtering

    print(f"Creating CEINMS model from OpenSim model")
    # Load the OpenSim model
    model = osim.Model(osimModelPath)
    model.initSystem()

    # Remove DOFs not in model dofset
    model_dofs = [model.getCoordinateSet().get(i).getName() for i in range(model.getCoordinateSet().getSize())]
    DOFs = [dof for dof in DOFs if dof in model_dofs]

    # Create the root element
    root = ET.Element("subject")
    
    # Add mtuDefault section with default curves and parameters
    mtu_default = ET.SubElement(root, "mtuDefault")
    
    # Add default parameters
    ET.SubElement(mtu_default, "emDelay").text = "0.015"
    ET.SubElement(mtu_default, "percentageChange").text = "0.15"
    ET.SubElement(mtu_default, "damping").text = "0.1"
    
    # Add default curves (using the curves from your example)
    curves_data = {
        "activeForceLength": {
            "xPoints": "-5 0 0.401 0.402 0.4035 0.52725 0.62875 0.71875 0.86125 1.045 1.2175 1.4387 1.6187 1.62 1.621 2.2 5",
            "yPoints": "0 0 0 0 0 0.22667 0.63667 0.85667 0.95 0.99333 0.77 0.24667 0 0 0 0 0"
        },
        "passiveForceLength": {
            "xPoints": "-5 0.998 0.999 1 1.1 1.2 1.3 1.4 1.5 1.6 1.601 1.602 5",
            "yPoints": "0 0 0 0 0.035 0.12 0.26 0.55 1.17 2 2 2 2"
        },
        "forceVelocity": {
            "xPoints": "-10 -1 -0.6 -0.3 -0.1 0 0.1 0.3 0.6 0.8 10",
            "yPoints": "0 0 0.08 0.2 0.55 1 1.4 1.6 1.7 1.75 1.75"
        },
        "tendonForceStrain": {
            "xPoints": " ".join([str(i/1000) for i in range(0, 101)]),
            "yPoints": "0 0.0012652 0.0073169 0.016319 0.026613 0.037604 0.049078 0.060973 0.073315 0.086183 0.099678 0.11386 0.12864 0.14386 0.15928 0.17477 0.19041 0.20658 0.22365 0.24179 0.26094 0.28089 0.30148 0.32254 0.34399 0.36576 0.38783 0.41019 0.43287 0.45591 0.4794 0.50344 0.52818 0.55376 0.58022 0.60747 0.63525 0.66327 0.69133 0.71939 0.74745 0.77551 0.80357 0.83163 0.85969 0.88776 0.91582 0.94388 0.97194 1 1.0281 1.0561 1.0842 1.1122 1.1403 1.1684 1.1964 1.2245 1.2526 1.2806 1.3087 1.3367 1.3648 1.3929 1.4209 1.449 1.477 1.5051 1.5332 1.5612 1.5893 1.6173 1.6454 1.6735 1.7015 1.7296 1.7577 1.7857 1.8138 1.8418 1.8699 1.898 1.926 1.9541 1.9821 2.0102 2.0383 2.0663 2.0944 2.1224 2.1505 2.1786 2.2066 2.2347 2.2628 2.2908 2.3189 2.3469 2.375 2.4031 2.4311"
        }
    }
    
    for curve_name, points in curves_data.items():
        curve = ET.SubElement(mtu_default, "curve")
        ET.SubElement(curve, "name").text = curve_name
        ET.SubElement(curve, "xPoints").text = points["xPoints"]
        ET.SubElement(curve, "yPoints").text = points["yPoints"]
    
    # Add mtuSet section
    mtu_set = ET.SubElement(root, "mtuSet")
    
    # Extract muscle parameters from OpenSim model
    muscle_set = model.getMuscles()
    for i in range(muscle_set.getSize()):
        muscle = muscle_set.get(i)
        
        # Create mtu element for each muscle
        mtu = ET.SubElement(mtu_set, "mtu")
        
        # Add muscle parameters
        ET.SubElement(mtu, "name").text = muscle.getName()
        ET.SubElement(mtu, "c1").text = "-0.5"
        ET.SubElement(mtu, "c2").text = "-0.5"
        ET.SubElement(mtu, "shapeFactor").text = "0.1"
        ET.SubElement(mtu, "optimalFibreLength").text = str(muscle.getOptimalFiberLength())
        ET.SubElement(mtu, "pennationAngle").text = str(muscle.getPennationAngleAtOptimalFiberLength())
        ET.SubElement(mtu, "tendonSlackLength").text = str(muscle.getTendonSlackLength())
        ET.SubElement(mtu, "maxIsometricForce").text = str(muscle.getMaxIsometricForce())
        ET.SubElement(mtu, "strengthCoefficient").text = "1"
    
    # Add dofSet section
    dof_set = ET.SubElement(root, "dofSet")
    dof_muscles = {}
    coordinates = model.getCoordinateSet()
    print('Adding muscles to DOFs...')
    if not DOFs:
        print('WARNING: No requested DOFs match the model coordinates!')
        print(f'Requested: {" ".join(requested_dofs)}')
        print(f'Model has: {" ".join(model_dofs)}')
        print('Update CEINMSSettings.dof_set in settings.py to match the above coordinate names.')
    else:
        print(f'DOFs selected for calibration: {DOFs}')
    for i in range(coordinates.getSize()):
        coord = coordinates.get(i)
        coord_name = coord.getName()
        
        if coord_name not in DOFs:
            continue
        
        # Get muscles that cross this coordinate
        muscles_for_coord = []
        for j in range(muscle_set.getSize()):
            muscle = muscle_set.get(j)
            state = model.initSystem()
            model.realizePosition(state)
            
            try:
                moment_arm = muscle.computeMomentArm(state, coord)
                if abs(moment_arm) > 1e-6:  # Small threshold for numerical precision
                    muscles_for_coord.append(muscle.getName())
            except:
                continue
                
        if muscles_for_coord:
            dof_muscles[coord_name] = muscles_for_coord
    
    # Create DOF elements
    for dof_name, muscle_names in dof_muscles.items():
        dof = ET.SubElement(dof_set, "dof")
        ET.SubElement(dof, "name").text = dof_name
        ET.SubElement(dof, "mtuNameSet").text = " ".join(muscle_names)
    
    # Add calibrationInfo section
    calibration_info = ET.SubElement(root, "calibrationInfo")
    uncalibrated = ET.SubElement(calibration_info, "uncalibrated")
    ET.SubElement(uncalibrated, "subjectID").text = os.path.basename(osimModelPath).replace('.osim', '')
    ET.SubElement(uncalibrated, "additionalInfo").text = ''
    
    # Add opensimModelFile reference
    ET.SubElement(root, "opensimModelFile").text = os.path.relpath(osimModelPath, os.path.dirname(outputCEINMSModelPath))

    # Create the XML tree and save
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, outputCEINMSModelPath)

    print(f"CEINMS subject file created: {outputCEINMSModelPath}")

def create_excitation_generator(osim_model_path=None, emg_path=None, save_path=None):
    """
    Create an excitation mapping from OpenSim model muscles to EMG data.
    
    Args:
        osim_model (osim.Model): The OpenSim model.
        emg_path (str): Path to the EMG data file.
        
    Returns:
        dict: A dictionary mapping muscle names to EMG labels.
    """
    if not osim_model_path:
        osim_model_path = input("Enter path to OpenSim model (.osim): ").strip('"')
        
    if not emg_path:
        emg_path = input("Enter path to EMG data file (.sto/.csv): ").strip('"')
        
    if not save_path:
        save_path = input("Enter path to save the excitation mapping XML file: ").strip('"')
    
    osim_model = osim.Model(osim_model_path)
    muscles = osim_model.getMuscles()
    muscleList = [muscle.getName() for muscle in muscles]
    
    emg_data = utils.load_any_data_file(emg_path)
    emg_labels = emg_data.columns.tolist()
    
    if 'time' in emg_labels:
        emg_labels.remove('time')

    # Create root element
    tree = ET.ElementTree()
    root = ET.Element('excitationGenerator')

    # Add inputSignals element
    input_signals = ET.SubElement(root, 'inputSignals', {'type': 'EMG'})
    input_signals.text = ' '.join(emg_labels)

    # Add mapping element
    mapping = ET.SubElement(root, 'mapping')
    mapping_dict = settings.EMG_muscle_mapping
    
    for muscle in muscleList:
        used = False
        for emg_input, items in mapping_dict.items(): 
            if muscle in items: used = True; break

        if used:
            emg_label = emg_input
            excitation = ET.SubElement(mapping, 'excitation', {'id': muscle})
            input_elem = ET.SubElement(excitation, 'input', {'weight': '1'})
            input_elem.text = emg_label
        else:
            excitation = ET.SubElement(mapping, 'excitation', {'id': muscle})
    
            
    # Write to XML file
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, os.path.abspath(save_path))
    print(f"XML saved to {os.path.abspath(save_path)}")

    return mapping_dict, emg_labels

def create_calibrationCfg(osimModelPath=None, inputPaths: list = [], outputPath: str = None):
    """
    Create a CEINMS calibration XML configuration from input parameters.
    
    Args:
    - osimModelPath (str): Path to the OpenSim model (.osim). Multiple trials allowed, path must be either full or relative to the calibrationCfgPath.
    - inputPaths (list): List of trial paths for "inputData.xml". 
    - outputPath (str): Path to save the generated calibration configuration XML file.

    Returns:
    - outputPath (str): The path to the saved calibration configuration XML file.
    """

    if not osimModelPath: 
        osimModelPath = input("Enter path to OpenSim model (.osim): ").strip('"')
    
    if not inputPaths:
        print

    if not outputPath:
        outputPath = input("Enter path to save the calibration configuration XML file: ")
    
    params = settings.CEINMSSettings
    root = ET.Element("calibration")

    # --- Optimiser ---
    optimiser = ET.SubElement(root, "optimiser")
    ET.SubElement(optimiser, "debug").text = "true"
    ET.SubElement(optimiser, "hybridCalibration").text = str(getattr(params, "hybridCalibration", "true"))
    ET.SubElement(optimiser, "learningRate").text = str(getattr(params, "learning_rate", "0.02"))
    ET.SubElement(optimiser, "maxIterations").text = str(getattr(params, "max_iterations", "1000"))

    earlyStopping = ET.SubElement(optimiser, "earlyStopping")
    ET.SubElement(earlyStopping, "minImprovement").text = str(getattr(params, "early_stopping_min_improvement", "0.1"))
    ET.SubElement(earlyStopping, "patience").text = str(getattr(params, "early_stopping_patience", "20"))

    ET.SubElement(optimiser, "numberOfSynergies").text = str(getattr(params, "num_synergies", 8))

    # --- Tendon ---
    tendon = ET.SubElement(root, "tendon")
    tendon.text = getattr(params, "tendonType", "elastic")

    # --- calibrationTargets ---
    calibrationTargets = ET.SubElement(root, "calibrationTargets")

    # parametersToCalibrate - only range parameters
    parametersToCalibrate = ET.SubElement(calibrationTargets, "parametersToCalibrate")
    
    # Calibration parameter ranges (name -> "min max" string)
    param_ranges = {
        "c1": getattr(params, "c1", "-0.99 -0.05"),
        "c2": getattr(params, "c2", "-0.95 -0.05"),
        "shapefactor": getattr(params, "shapefactor", "-2.999 -0.001"),
        "optimalFiberLength": getattr(params, "optimalFiberLength", "0.5 3"),
        "tendonSlackLength": getattr(params, "tendonSlackLength", "0.5 3"),
        "strengthCoefficient": getattr(params, "strengthCoefficient", "0.75 3.5"),
    }
    for name, value in param_ranges.items():
        param_elem = ET.SubElement(parametersToCalibrate, "parameter", name=name)
        param_elem.text = str(value)

    # ------- muscleGroups (BASED ON SETTINGS PLEASE EDIT THIS FOR DIFFERENT MUSCLE GROUPS) ------
    muscleGroups = ET.SubElement(parametersToCalibrate, "muscleGroups")

    for group, muscles in settings.Muscle_Groups.items():
        muscleGroup = ET.SubElement(muscleGroups, "muscles")
        muscleGroup.text = " ".join(muscles)

    # objectiveFunctions
    objectiveFunctions = ET.SubElement(calibrationTargets, "objectiveFunctions")
    for func in params.objective_functions:
        objFunc = ET.SubElement(objectiveFunctions, "objectiveFunction")
        for key, value in func.items():
            ET.SubElement(objFunc, key).text = str(value)

    # target muscles
    targetMuscles = ET.SubElement(calibrationTargets, "muscles")
    for muscle in params.target_muscles:
        ET.SubElement(targetMuscles, "muscle").text = muscle

    # --- trialSet ---
    trialSet = ET.SubElement(root, "trialSet")
    trialSet.text = " ".join(inputPaths)

    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, outputPath)
    print(f"Calibration configuration XML saved to: {os.path.abspath(outputPath)}")


    return outputPath

def create_calibrationSetupXML(uncalibratedCEINMSModelPath=None, 
                               excitationGeneratorFile=None,
                               calibrationCfgPath=None,
                               outputSubjectFile =None, 
                               outputDirectory=None,
                               setupXMLPath=None):
    
    if not uncalibratedCEINMSModelPath:
        uncalibratedCEINMSModelPath = input("Enter path to uncalibrated CEINMS model file: ").strip('"')
    
    if not calibrationCfgPath:
        calibrationCfgPath = input("Enter path to calibration config file: ").strip('"')
    
    if not excitationGeneratorFile:
        excitationGeneratorFile = input("Enter path to excitation generator file: ").strip('"')
    
    if not outputSubjectFile:
        outputSubjectFile = uncalibratedCEINMSModelPath.replace('.xml', '_calibrated.xml')
        
    if not outputDirectory:
        outputDirectory = os.path.join(os.path.dirname(calibrationCfgPath), 'calibrationOutput')
    
    root = ET.Element("ceinmsCalibration")

    setupXMLPathDir = os.path.dirname(setupXMLPath)
    
    subjectFile = ET.SubElement(root, "subjectFile")
    subjectFile.text = os.path.relpath(uncalibratedCEINMSModelPath, setupXMLPathDir)
    
    excitationGeneratorFileTag = ET.SubElement(root, "excitationGeneratorFile")
    excitationGeneratorFileTag.text = os.path.relpath(excitationGeneratorFile, setupXMLPathDir)

    calibrationFile = ET.SubElement(root, "calibrationFile")
    calibrationFile.text = os.path.relpath(calibrationCfgPath, setupXMLPathDir)

    outputSubjectFileTag = ET.SubElement(root, "outputSubjectFile")
    outputSubjectFileTag.text = os.path.relpath(outputSubjectFile, setupXMLPathDir)

    outputDirectoryTag = ET.SubElement(root, "outputDirectory")
    outputDirectoryTag.text = os.path.relpath(outputDirectory, setupXMLPathDir)
    
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, setupXMLPath)

def create_input_data(MAFolder=None, excitationsFile=None, motionFile=None, 
                      externalTorquesFile=None, externalLoadsFile=None,
                      startStopTime=None):
    
    if not MAFolder:
        MAFolder = input("Enter path to Muscle Analysis folder: ").strip('"')

    if not excitationsFile:
        excitationsFile = input("Enter path to excitations file: ").strip('"')
    
    if not motionFile:
        motionFile = input("Enter path to motion file: ").strip('"')
        
    if not externalTorquesFile:
        externalTorquesFile = input("Enter path to external torques file: ").strip('"')
    
    if not externalLoadsFile:
        externalLoadsFile = input("Enter path to external loads file: ").strip('"')
        
    if not startStopTime:
        start_time = float(input("Enter start time: ").strip())
        stop_time = float(input("Enter stop time: ").strip())
        startStopTime = (start_time, stop_time) 
    
    root = ET.Element("inputData")
    length_path = os.path.join(MAFolder, '_MuscleAnalysis_Length.sto')
    muscle_length_elem = ET.SubElement(root, "muscleTendonLengthFile")
    muscle_length_elem.text = os.path.relpath(length_path, start=os.path.dirname(MAFolder))

    excitations_elem = ET.SubElement(root, "excitationsFile")
    excitations_elem.text = os.path.relpath(excitationsFile, start=os.path.dirname(MAFolder))
    
    # Add moment arms files 
    moment_arms = ET.SubElement(root, "momentArmsFiles")
    for dof in settings.BatchSettings.dof_list:

        dof_path = os.path.join(MAFolder, f'_MuscleAnalysis_MomentArm_{dof}.sto')
        dof_elem = ET.SubElement(moment_arms, "momentArmsFile")
        dof_elem.set("dofName", dof)
        dof_elem.text = os.path.relpath(dof_path, start=os.path.dirname(MAFolder))  

    external_torques_elem = ET.SubElement(root, "externalTorquesFile")
    external_torques_elem.text = os.path.relpath(externalTorquesFile, start=os.path.dirname(MAFolder))

    motion_elem = ET.SubElement(root, "motionFile")
    motion_elem.text = os.path.relpath(motionFile, start=os.path.dirname(MAFolder))

    external_loads_elem = ET.SubElement(root, "externalLoadsFile")
    external_loads_elem.text = os.path.relpath(externalLoadsFile, start=os.path.dirname(MAFolder))

    startStop_elem = ET.SubElement(root, "startStopTime")
    startStop_elem.text = f"{startStopTime[0]} {startStopTime[1]}"
    
    savePath = os.path.join(os.path.dirname(MAFolder), 'inputData.xml')
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, savePath)

def check_input_times(setupXML_path=None):
    
    def load_file_from_tag(setupXML, tag_name):
        
        original_dir = os.getcwd()
        base_dir = os.path.dirname(setupXML_path)
        os.chdir(base_dir)
        file_tag = setupXML.find(tag_name)
        if file_tag is not None:
            os.chdir(original_dir)
            return utils.load_any_data_file(os.path.join(base_dir, file_tag.text))
        else:
            raise ValueError(f"Tag '{tag_name}' not found in setup XML.")
         
    def is_contained(df1, time_range):
        
        if df1 is None or not isinstance(df1, pd.DataFrame) or 'time' not in df1.columns:
            return False
        
        df1_start = df1['time'].iloc[0]
        df1_end = df1['time'].iloc[-1]
        if df1_start > time_range[0] or df1_end < time_range[1]:
            return False
        return True
    
    os.chdir(os.path.dirname(setupXML_path))
    setupXML = ET.parse(setupXML_path).getroot()
    inputDataPath = setupXML.find('inputDataFile').text 
    inputData = ET.parse(inputDataPath).getroot()
    
    # create output dict to store results logics
    output = {}
    
    # Get startStopTime from inputData -> CEINMS time range
    input_startStop = inputData.find('startStopTime').text.strip().split()
    ceinms_time_range = (float(input_startStop[0]), float(input_startStop[1]))   
    
    muscleTendonLength = load_file_from_tag(inputData, 'muscleTendonLengthFile')
    output['muscleTendonLength'] = is_contained(muscleTendonLength, ceinms_time_range)
    
    excitations = load_file_from_tag(inputData, 'excitationsFile')
    output['excitations'] = is_contained(excitations, ceinms_time_range)
    
    momentArmFiles = inputData.findall('.//momentArmsFile')
    for momentArmFile in momentArmFiles:
        momentArm_path = os.path.join(os.path.join(os.path.dirname(inputDataPath), momentArmFile.text))
        momentArms = utils.load_any_data_file(momentArm_path)
        dofName = momentArmFile.get('dofName')
        output[dofName] = is_contained(momentArms, ceinms_time_range)
        
    externalTorques = load_file_from_tag(inputData, 'externalTorquesFile')
    output['externalTorques'] = is_contained(externalTorques, ceinms_time_range)
    
    motion = load_file_from_tag(inputData, 'motionFile')
    output['motion'] = is_contained(motion, ceinms_time_range)
    
    return output
    

# Base run ceinms function
def ceinms_terminal(executable_path=None, setupXML_path=None):
    
    # change wd to parent dir of setupXML 
    parentDir = os.path.dirname(setupXML_path)
    os.chdir(parentDir) 
    
    # Unzip torch_cpu.zip if torch_cpu.dll is missing (first-run setup)
    exe_dir = os.path.dirname(os.path.abspath(executable_path))
    torch_cpu_dll = os.path.join(exe_dir, 'torch_cpu.dll')
    torch_cpu_zip = os.path.join(exe_dir, 'torch_cpu.zip')
    if not os.path.exists(torch_cpu_dll) and os.path.exists(torch_cpu_zip):
        print(f"Extracting torch_cpu.dll from {torch_cpu_zip}...")
        with zipfile.ZipFile(torch_cpu_zip, 'r') as zf:
            zf.extractall(exe_dir)
        print("torch_cpu.dll extracted.")

    for dll in ('torch.dll', 'torch_cpu.dll'):
        if not os.path.exists(os.path.join(exe_dir, dll)):
            print(f"WARNING: {dll} not found in {exe_dir}. CEINMS may not run correctly.")
        
    # load setupXML to get outputDirectory
    setupXML = ET.parse(setupXML_path).getroot()
    outputDirectory = setupXML.find("outputDirectory").text
    
    # check input data times cover CEINMS time range
    try:
        outputTimes = check_input_times(setupXML_path=setupXML_path)
    except Exception as e:
        outputTimes = {'good': True}
        
    for key, value in outputTimes.items():
        if not value:
            print(f"Warning: Input data '{key}' does not cover the CEINMS time range!")
            return False
    
    # create output directory if it doesn't exist
    os.makedirs(outputDirectory, exist_ok=True) 
    
    print("Setup XML path:", setupXML_path)

    log_file_path = os.path.join(os.path.abspath(outputDirectory), 'out.txt')
    if os.path.exists(log_file_path): os.remove(log_file_path)
    
    # run main command
    os.chdir(parentDir)
    exe_dir = os.path.dirname(executable_path)
    # Build PATH: exe dir + standalone OpenSim installation dir.
    # IMPORTANT: do NOT add the Python opensim package directory here.
    # The Python opensim package DLLs (miniconda) are compiled for Python bindings
    # and have different entry points than the standalone OpenSim DLLs that
    # CEINMS.exe was compiled against. Adding the Python dir first causes
    # STATUS_ENTRYPOINT_NOT_FOUND (0xC0000139) crashes.
    path_dirs = [exe_dir]
    for _candidate in [
        r'C:\OpenSim 4.5\bin', r'C:\OpenSim 4.4\bin', r'C:\OpenSim 4.3\bin',
        r'C:\Program Files\OpenSim 4.5\bin', r'C:\Program Files\OpenSim 4.4\bin',
    ]:
        if os.path.isdir(_candidate) and _candidate not in path_dirs:
            path_dirs.append(_candidate)
    path_str = ';'.join(path_dirs)
    print(f"[Debug] PATH for CEINMS.exe: {path_str}")
    try:
        # Dump setup XML so we can see exactly what CEINMS.exe receives
        print(f"[Debug] Setup XML ({setupXML_path}):")
        try:
            with open(setupXML_path, 'r', encoding='utf-8', errors='replace') as _f:
                print(_f.read())
        except Exception as _e:
            print(f"  (could not read: {_e})")

        # Also dump inputData.xml if we can find it
        _input_data_rel = ET.parse(setupXML_path).getroot().find('inputDataFile')
        if _input_data_rel is not None:
            _input_data_path = os.path.join(parentDir, _input_data_rel.text)
            print(f"[Debug] Input data XML ({_input_data_path}):")
            try:
                with open(_input_data_path, 'r', encoding='utf-8', errors='replace') as _f:
                    print(_f.read())
            except Exception as _e:
                print(f"  (could not read: {_e})")

        # Snapshot of files in trial dir before running
        print(f"[Debug] Trial dir contents before run ({parentDir}):")
        try:
            for _f in os.listdir(parentDir):
                print(f"  {_f}")
        except Exception as _e:
            print(f"  (could not list: {_e})")

        ps_script = f'''
            $ErrorActionPreference = "Continue"
            $env:PATH = "{path_str};$env:PATH"
            Set-Location "{parentDir}"
            & "{executable_path}" -S "{setupXML_path}"
            $ec = $LASTEXITCODE
            Write-Host "[PowerShell] CEINMS exit code: $ec"
            exit $ec
            '''

        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script]

        with open(log_file_path, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Stream output
            if process.stdout:
                for line in process.stdout:
                    print(line, end="")  # Print to terminal
                    log_file.write(line)
                    log_file.flush()

            process.wait()
        print(f"CEINMS process finished with exit code: {process.returncode}")

        # Look for out.log in exe dir and trial dir after run
        for _log_candidate in [
            os.path.join(exe_dir, 'out.log'),
            os.path.join(parentDir, 'out.log'),
            os.path.join(exe_dir, 'err.log'),
            os.path.join(parentDir, 'err.log'),
        ]:
            if os.path.exists(_log_candidate):
                try:
                    _mtime = os.path.getmtime(_log_candidate)
                    _run_start = os.path.getmtime(log_file_path) if os.path.exists(log_file_path) else 0
                    _age_tag = "(updated this run)" if _mtime >= _run_start - 5 else "(pre-existing)"
                    print(f"[Debug] Found log: {_log_candidate} {_age_tag}")
                    with open(_log_candidate, 'r', encoding='utf-8', errors='replace') as _lf:
                        _content = _lf.read()
                    print(f"--- {_log_candidate} (last 3000 chars) ---")
                    print(_content[-3000:])
                except Exception as _e:
                    print(f"  (could not read {_log_candidate}: {_e})")

        # List trial dir after run
        print(f"[Debug] Trial dir contents after run ({parentDir}):")
        try:
            for _f in os.listdir(parentDir):
                print(f"  {_f}")
        except Exception as _e:
            print(f"  (could not list: {_e})")

    except Exception as e:
        print(f"Error running CEINMS: {e}")

    print(f"Log file saved to: {log_file_path}")

    # if Calibration command — check if new calibrated model was created recently
    # (execution setup XML has no <outputSubjectFile> tag, so skip this check)
    try:
        calibratedModelEl = setupXML.find('outputSubjectFile')
        if calibratedModelEl is None:
            return True  # Not a calibration run — nothing to check
        calibratedModelPath = calibratedModelEl.text
        # Resolve relative path against the setupXML directory
        if not os.path.isabs(calibratedModelPath):
            calibratedModelPath = os.path.join(parentDir, calibratedModelPath)
        if not os.path.exists(calibratedModelPath):
            print(f"Calibrated model not found: {calibratedModelPath}")
            print("--- CEINMS output log ---")
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='replace') as lf:
                    print(lf.read()[-3000:])  # last 3000 chars
            except Exception:
                pass
            return False
        time_updated = os.path.getmtime(calibratedModelPath)
        if time_updated < os.path.getmtime(log_file_path):
            print("Calibrated model exists but predates this run — calibration may have failed.")
            return False
        return True
    except Exception as e:
        print(f"Error checking calibrated model: {e}")
        return False
    
# CEINMS calibration functions
def calibrate(setupXML_path=None):
    
    if not setupXML_path:
        setupXML_path = input("Enter path to setup XML file: ").strip('"')
    
    os.chdir(os.path.dirname(setupXML_path)) # change wd to parent dir of setupXML (needed for CEINMS)
    
    setupXML = ET.parse(setupXML_path).getroot()
    outputDirectory = setupXML.find("outputDirectory").text
    
    # Always strip any stale _run_ suffixes (from previous bad runs)
    base_name = outputDirectory.split('_run_')[0]
    outputDirectory = base_name

    if os.path.exists(outputDirectory):
        outputDirectory = base_name + f"_run_{time.strftime('%y_%m_%d_%H_%M')}"
        print(f"Output directory exists. Using timestamped name: {outputDirectory}")

    # Write the final name back to the XML so ceinms_terminal reads the right path
    setupXML.find("outputDirectory").text = outputDirectory
    utils.save_pretty_xml(ET.ElementTree(setupXML), setupXML_path)
    
    # Open setup file in default viewer
    try:
        os.startfile(setupXML_path)
    except Exception as e:
        print(f"Error opening setup XML file: {e}")

    os.makedirs(outputDirectory, exist_ok=True)
    
    print("Calibrating CEINMS model...")
    
    ceinms_terminal(executable_path=utils.CEINMS_CALIBRATION_EXE, setupXML_path=setupXML_path)

def calibrate_synergy_compare(setupXML_path=None, synergy_numbers: list = [3, 4, 5, 6]):
    if not setupXML_path:
        setupXML_path = input("Enter path to setup XML file: ").strip('"')
    
    base_dir = os.path.dirname(setupXML_path)
    
    for n in synergy_numbers:
        print(f"Calibrating with {n} synergies...")
        
        # Create a new setup XML with modified calibration config
        root = ET.parse(setupXML_path).getroot()

        outputDirectory = root.find("outputDirectory")
        outputDirectory.text = os.path.join(base_dir, f'calibrationOutput_synergies_{n}')
        
        utils.save_pretty_xml(ET.ElementTree(root), setupXML_path)

        # Load and modify calibration config and overwite cfg file
        calibrationFileTag = root.find('calibrationFile')
        calibrationCfgPath = calibrationFileTag.text
        calibrationCfgFullPath = os.path.join(base_dir, calibrationCfgPath)
        
        root_cfg = ET.parse(calibrationCfgFullPath).getroot()
        synergyTag = root_cfg.find('.//numberOfSynergies')
        synergyTag.text = str(n)

        tree = ET.ElementTree(root_cfg)
        utils.save_pretty_xml(tree, calibrationCfgFullPath)
        
        # Run calibration
        outputCalibration = calibrate(setupXML_path)
        
        # if new calibrated model is created, copy to outputDirectory with synergy number in filename
        calibratedModelPath = root.find('outputSubjectFile').text
        if outputCalibration:
            newCalibratedModelPath = os.path.join(outputDirectory, f"calibratedModel_synergies_{n}.xml")
            shutil.copy(calibratedModelPath, newCalibratedModelPath)

# CEINMS base exe function
def create_ceinms_cfg(ceinmsModelPath=None, alpha=1, beta=100, gamma=1000, dofSet=None, excitationGeneratorFilePath=None, outputPath=None):
    
    if not ceinmsModelPath:
        ceinmsModelPath = input("Enter path to CEINMS model file: ").strip('"')
    if not dofSet:
        dofSet = input("Enter DOF set (space-separated): ").strip()
    
    if not excitationGeneratorFilePath:
        excitationGeneratorFilePath = input("Enter path to excitation generator file: ").strip('"')
    
    execution = ET.ElementTree(ET.Element("execution")).getroot()
    nmsmodel = ET.SubElement(execution, "NMSmodel")
    type_tag = ET.SubElement(nmsmodel, "type")
    hybrid = ET.SubElement(type_tag, "hybrid")
    ET.SubElement(hybrid, "alpha").text = str(alpha)
    ET.SubElement(hybrid, "beta").text = str(beta)
    ET.SubElement(hybrid, "gamma").text = str(gamma)
    ET.SubElement(hybrid, "dofSet").text = dofSet
    
    # load CEINMS model and excitation generator to get muscle names
    model = ET.parse(ceinmsModelPath).getroot()
    muscle_names = [mtu.find('name').text for mtu in model.find('mtuSet').findall('mtu')]
    
    excitationGenerator = ET.parse(excitationGeneratorFilePath).getroot()
    mapping = excitationGenerator.find('mapping')
    
    synthMTUs = []
    adjustMTUs = []
    for muscle in muscle_names:    
        excitation = mapping.find(f".//excitation[@id='{muscle}']")
        if excitation is not None and excitation.find('input') is not None:
            adjustMTUs.append(muscle)
        else:
            synthMTUs.append(muscle)
    
    ET.SubElement(hybrid, "synthMTUs").text = " ".join(synthMTUs)
    ET.SubElement(hybrid, "adjustMTUs").text = " ".join(adjustMTUs)
    
    algorithm = ET.SubElement(hybrid, "algorithm")
    simulatedAnnealing = ET.SubElement(algorithm, "simulatedAnnealing")
    ET.SubElement(simulatedAnnealing, "noEpsilon").text = "4"
    ET.SubElement(simulatedAnnealing, "rt").text = "0.3"
    ET.SubElement(simulatedAnnealing, "T").text = "20000"
    ET.SubElement(simulatedAnnealing, "NS").text = "15"
    ET.SubElement(simulatedAnnealing, "NT").text = "5"
    ET.SubElement(simulatedAnnealing, "epsilon").text = "0.001"
    ET.SubElement(simulatedAnnealing, "maxNoEval").text = "200000"
    
    tendon = ET.SubElement(nmsmodel, "tendon")
    equilibriumElastic = ET.SubElement(tendon, "equilibriumElastic")
    ET.SubElement(equilibriumElastic, "tolerance").text = "1e-09"
    
    activation = ET.SubElement(nmsmodel, "activation")
    ET.SubElement(activation, "exponential")
    
    tree = ET.ElementTree(execution)
    if not outputPath:
        outputPath = input("Enter path to save CEINMS configuration XML file: ").strip('"')
    
    utils.save_pretty_xml(tree, os.path.abspath(outputPath))

def replace_ceinms_cfg_parameter(cfgXML_path=None, parameter_name=None, new_value=None):
    if not cfgXML_path:
        cfgXML_path = input("Enter path to CEINMS configuration XML file: ").strip('"')
    
    if not parameter_name:
        parameter_name = input("Enter parameter name to replace: ").strip()
    
    if new_value is None:
        new_value = input("Enter new value for the parameter: ").strip()
    
    tree = ET.parse(cfgXML_path)
    root = tree.getroot()
    
    paramTag = root.find(f'.//{parameter_name}')
    if paramTag is not None:
        paramTag.text = str(new_value)
        utils.save_pretty_xml(tree, cfgXML_path)
        print(f"Parameter '{parameter_name}' updated to '{new_value}' in {cfgXML_path}.")
    else:
        print(f"Parameter '{parameter_name}' not found in {cfgXML_path}.")
                   
def executable(setupXML_path=None):
    
    if not setupXML_path:
        setupXML_path = input("Enter path to setup XML file: ").strip('"')

    os.chdir(os.path.dirname(setupXML_path)) # change wd to parent dir of setupXML (needed for CEINMS)
    
    setupXML = ET.parse(setupXML_path).getroot()
    outputDirectory = setupXML.find("outputDirectory").text
    
    os.makedirs(outputDirectory, exist_ok=True)
    
    print("Running CEINMS executable...")
    ceinms_terminal(executable_path=utils.CEINMS_EXE, setupXML_path=setupXML_path)
    
    # plot results
    os.chdir(os.path.dirname(setupXML_path))
    plot_optimisation_results(outputDirectory)
    
    inputData = ET.parse(setupXML.find('inputDataFile').text).getroot()
    experimentalEMGPath = inputData.find('excitationsFile').text
    experimentalMomentsPath = inputData.find('externalTorquesFile').text
    
    # Debug: show what the exe produced
    if os.path.exists(outputDirectory):
        produced = os.listdir(outputDirectory)
        print(f"[Info] Execution output files in {outputDirectory}: {produced}")
        sto_files = [f for f in produced if f.endswith('.sto')]
        if not sto_files:
            print(f"[Warning] No .sto output files produced by CEINMS.exe.")
            log_path = os.path.join(outputDirectory, 'out.txt')
            if os.path.exists(log_path):
                print("--- CEINMS execution log (last 2000 chars) ---")
                with open(log_path, 'r', encoding='utf-8', errors='replace') as lf:
                    print(lf.read()[-2000:])
    else:
        print(f"[Warning] Output directory not created: {outputDirectory}")

    adjusted_emg = os.path.abspath(os.path.join(outputDirectory, 'AdjustedEmgs.sto'))
    torques_sto = os.path.abspath(os.path.join(outputDirectory, 'Torques.sto'))
    if os.path.exists(adjusted_emg) and os.path.exists(torques_sto):
        try:
            plot_experimental_vs_ceinms(emgFile=experimentalEMGPath,
                                    ceinmsExcitationsFile=adjusted_emg,
                                    excitationGeneratorFile=setupXML.find('excitationGeneratorFile').text,
                                    externalMomentsFile=os.path.abspath(experimentalMomentsPath),
                                    ceinmsTorquesFile=torques_sto)
        except Exception as e:
            print(f"Error plotting experimental vs CEINMS results: {e}")
    else:
        print(f"[Info] Skipping EMG vs CEINMS plot — output files not found in {outputDirectory}")
    
def executable_loop(setupXML_path=None, cfgXML_path=None, 
                    gammas: list = [1, 10, 100, 1000], 
                    betas: list = [1, 10, 100, 1000], 
                    alphas: list = [1, 10]):
    
    if not setupXML_path:
        setupXML_path = input("Enter path to setup XML file: ").strip('"')
    
    if not cfgXML_path:
        cfgXML_path = input("Enter path to CEINMS configuration XML file: ").strip('"')
        
    combinations = [(a, b, g) for a in alphas for b in betas for g in gammas]
    
    base_dir = os.path.dirname(setupXML_path)
    os.chdir(base_dir) # change wd to parent dir of setupXML (needed for CEINMS)
    
    setup = ET.parse(setupXML_path).getroot()
    ceinmsModelPath = setup.find('subjectFile').text
    excitationGeneratorFilePath = os.path.abspath(setup.find('excitationGeneratorFile').text)
    executionOutputDir = setup.find('outputDirectory').text
    for value in combinations:
        print(f"Running CEINMS with alpha={value[0]}, beta={value[1]}, gamma={value[2]}...")
        
        replace_ceinms_cfg_parameter(cfgXML_path, 'alpha', value[0])
        replace_ceinms_cfg_parameter(cfgXML_path, 'beta', value[1])
        replace_ceinms_cfg_parameter(cfgXML_path, 'gamma', value[2])
        
        outputDirectory = setup.find("outputDirectory")
        outputDirectory.text = executionOutputDir + f'_a{value[0]}_b{value[1]}_g{value[2]}'
        
        utils.save_pretty_xml(ET.ElementTree(setup), setupXML_path)
        
        # Run CEINMS executable
        executable(setupXML_path=setupXML_path)
        
    # Summarise results
    executable_loop_summarise_results(baseDir=base_dir, prefix=executionOutputDir)

def executable_loop_summarise_results(baseDir=None, prefix='Execution'):
    if not baseDir:
        baseDir = input("Enter base directory containing CEINMS output folders: ").strip('"')
    
    def excitation_dict(excitationGenerator):
        emgMapping = {}
        for excitation in excitationGenerator.find('mapping').findall('excitation'):
            if excitation.find('input') is not None:
                emgMapping[excitation.get('id')] = excitation.find('input').text
        return emgMapping
    
    os.chdir(baseDir)
    setupXML = ET.parse(utils.Inputs().ceinms_exe_setup).getroot()
    excitationGenerator = ET.parse(setupXML.find('excitationGeneratorFile').text).getroot()
    
    emgMapping = excitation_dict(excitationGenerator)
    
    externalMoments = utils.load_any_data_file(os.path.join(baseDir, utils.Inputs().id))
    externalMoments.columns = [col.replace('_moment', '') for col in externalMoments.columns]
    
    emgData = utils.load_any_data_file(os.path.join(baseDir, utils.Inputs().emg_normalised))
    results = pd.DataFrame(columns=['Alpha', 'Beta', 'Gamma', 'RMSE_Moments', 'R2_Moments', 'RMSE_Excitations', 'R2_Excitations'])
    for folder in os.walk(baseDir):
        
        if not os.path.basename(folder[0]).startswith(prefix):
            continue
        # if folder contains both 'AdjustedEmgs.sto' and 'Torques.sto' files
        if 'AdjustedEmgs.sto' in folder[2] and 'Torques.sto' in folder[2]:
            
            try:
                ceinmsTorques = utils.load_any_data_file(os.path.join(folder[0], 'Torques.sto'))
            except Exception as e:
                print(f"Error loading Torques.sto in {folder[0]}: {e}")
                continue
            ceinmsTimeRange = (ceinmsTorques['time'].iloc[0], ceinmsTorques['time'].iloc[-1])
            externalMoments = externalMoments[(externalMoments['time'] >= ceinmsTimeRange[0]) & (externalMoments['time'] <= ceinmsTimeRange[1])].reset_index(drop=True)
            id_norm = utils.time_normalise_df(externalMoments).drop(columns=['time'])
            ceinmsTorques_norm = utils.time_normalise_df(ceinmsTorques).drop(columns=['time'])
            
            stats = utils.compare_curves(id_norm, ceinmsTorques_norm)
            rmse_moments, r2_moments = stats['RMSE'], stats['R2'].mean()
            columns = [col for col in rmse_moments.index]
        
            rmse_moments = (rmse_moments / (id_norm[columns].max()-id_norm[columns].min()) *100).max()
            
            
            ceinmsExcitations = utils.load_any_data_file(os.path.join(folder[0], 'AdjustedEmgs.sto'))
            ceinms_start_time, ceinms_end_time = ceinmsExcitations['time'].iloc[0], ceinmsExcitations['time'].iloc[-1]
            emgData = emgData[(emgData['time'] >= ceinms_start_time) & (emgData['time'] <= ceinms_end_time)].reset_index(drop=True)
            
            ceinmsExcitations_norm = utils.time_normalise_df(ceinmsExcitations).drop(columns=['time'])
            emgData_norm = utils.time_normalise_df(emgData).drop(columns=['time'])
            stats = utils.compare_curves(emgData_norm, ceinmsExcitations_norm, emgMapping)
            
            rmse_excitations, r2_excitations = stats['RMSE'], stats['R2'].mean()
            columns = [col for col in rmse_excitations.index]
            rmse_excitations = (rmse_excitations / (ceinmsExcitations_norm[columns].max()-ceinmsExcitations_norm[columns].min()) *100).mean()
            
            # extract alpha, beta, gamma from folder name
            folder_name = os.path.basename(folder[0])
            alpha = int(folder_name.split('_a')[1].split('_')[0])
            beta = int(folder_name.split('_b')[1].split('_')[0])
            gamma = int(folder_name.split('_g')[1].split('_')[0])
            
            results = pd.concat([results, pd.DataFrame({
                'Alpha': [alpha],
                'Beta': [beta],
                'Gamma': [gamma],
                'RMSE_Moments': [rmse_moments],
                'R2_Moments': [r2_moments],
                'RMSE_Excitations': [rmse_excitations],
                'R2_Excitations': [r2_excitations]
            })], ignore_index=True)
            
    results_path = os.path.join(baseDir, 'CEINMS_Executable_Results_Summary.csv')
    results.to_csv(results_path, index=False)
    print(f"Results summary saved to: {results_path}")
    try:
        plot_loop_results(results_path)
    except Exception as e:
        print(f"Error plotting loop results: {e}")
   
def plot_loop_results(CSVresultsPath=None):
    
    if not CSVresultsPath:
        CSVresultsPath = input("Enter path to CEINMS executable results CSV file: ").strip('"')
        
    df = pd.read_csv(CSVresultsPath)

    alphas = df['Alpha'].unique()
    betas = df['Beta'].unique()
    gammas = df['Gamma'].unique()
    combinations = [(a, b) for a in alphas for b in betas]
    
    # Set up the figure with 2x2 subplots
    fig, axes = plt.subplots(len(combinations), 2, figsize=(16, 12))
    fig.suptitle('Effects of Parameters on Model Performance', fontsize=16)
    axes = axes.flatten()
    
    for i, (alpha, beta) in enumerate(combinations): 
        cropped_df = df[(df['Alpha'] == alpha) & (df['Beta'] == beta)]
        
        # Plot RMSE
        ax_rmse = axes[i*2]
        ax_rmse.scatter(cropped_df['Gamma'], cropped_df['RMSE_Moments'], c='blue', label=f'Moments', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_rmse.scatter(cropped_df['Gamma'], cropped_df['RMSE_Excitations'], c='red', label='Excitations', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_rmse.set_ylabel('RMSE (%)')
        ax_rmse.set_xticklabels([])
        ax_rmse.grid(True, alpha=0.3)
        # ax_rmse.set_xscale('log')   
        
        # add text box with alpha and beta values
        textstr = f'Alpha: {alpha}\nBeta: {beta}'
        props = dict(boxstyle='round', facecolor='white', alpha=0.5)
        ax_rmse.text(0.05, 0.95, textstr, transform=ax_rmse.transAxes, fontsize=10, verticalalignment='top', bbox=props)
        ax_rmse.set_xticks(gammas)
        
        if i == 0:
            ax_rmse.legend()
        
        if i == len(combinations) - 1:
            ax_rmse.set_xlabel('Gamma')
            ax_rmse.set_xticklabels(gammas)
        else:
            ax_rmse.set_xticklabels([])
            
        
        # Plot R²
        ax_r2 = axes[i*2 + 1]
        ax_r2.scatter(cropped_df['Gamma'], cropped_df['R2_Moments'], c='blue', label='Moments', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_r2.scatter(cropped_df['Gamma'], cropped_df['R2_Excitations'], c='red', label='Excitations', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_r2.set_ylabel('R²')
        ax_r2.set_xticklabels([])
        ax_r2.grid(True, alpha=0.3)
        # ax_r2.set_xscale('log')
        ax_r2.set_ylim(0, 1)
        ax_r2.set_xticks(gammas)
        
        
        if i == len(combinations) - 1:
            ax_r2.set_xlabel('Gamma')
            ax_r2.set_xticklabels(gammas)
        else:
            ax_r2.set_xticklabels([])
    
    plt.tight_layout()
    
    # Print summary statistics
    print("Parameter Effects Summary:")
    print("="*50)
    print(f"Best RMSE_Moments: {df['RMSE_Moments'].min():.3f} - {df.loc[df['RMSE_Moments'].idxmin(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    print(f"Best R2_Moments: {df['R2_Moments'].max():.3f} - {df.loc[df['R2_Moments'].idxmax(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    print(f"Best RMSE_Excitations: {df['RMSE_Excitations'].min():.3f} - {df.loc[df['RMSE_Excitations'].idxmin(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    print(f"Best R2_Excitations: {df['R2_Excitations'].max():.3f} - {df.loc[df['R2_Excitations'].idxmax(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    
    # calculate overall best as sum of ranks
    df['RMSE_Sum'] = df['RMSE_Moments'] + df['RMSE_Excitations']
    df['R2_Sum'] = df['R2_Moments'] + df['R2_Excitations']
    
    # 1. Create a rank for RMSE_Sum (lower is better, so rank 1 is the lowest sum)
    df['Rank_RMSE'] = df['RMSE_Sum'].rank(ascending=True)

    # 2. Create a rank for R2_Sum (higher is better, so rank 1 is the highest sum)
    df['Rank_R2'] = df['R2_Sum'].rank(ascending=False)

    # 3. Combine ranks. The best row will have the lowest total rank (e.g., 1 + 1 = 2)
    df['Overall_Rank'] = df['Rank_RMSE'] + df['Rank_R2']
    df_sorted = df.sort_values(by='Overall_Rank')
    
    print("Top 5 best combinations based on low RMSE_Sum and high R2_Sum:\n")
    print(df_sorted[['Alpha', 'Beta', 'Gamma', 'RMSE_Sum', 'R2_Sum', 'Overall_Rank']].head())

    # Get the single best row
    best_combination = df_sorted.iloc[0]

    print("\n--------------------------------------------------")
    print("Best overall combination:")
    print(f"  Alpha: {best_combination['Alpha']}")
    print(f"  Beta: {best_combination['Beta']}")
    print(f"  Gamma: {best_combination['Gamma']}")
    print(f"  Combined RMSE (Sum): {best_combination['RMSE_Sum']:.2f}")
    print(f"  Combined R2 (Sum): {best_combination['R2_Sum']:.2f}")
    print("--------------------------------------------------")

    # add title with best iteration settings
    fig.suptitle(f"Best Overall - Alpha: {int(best_combination['Alpha'])}, Beta: {int(best_combination['Beta'])}, Gamma: {int(best_combination['Gamma'])}\nCombined RMSE: {best_combination['RMSE_Sum']:.2f}, Combined R²: {best_combination['R2_Sum']:.2f}", fontsize=16)    
    
    plt.tight_layout()
    savepath = CSVresultsPath.replace('.csv', '.png')
    plt.savefig(savepath)
    print(f"Parameter effects plot saved to: {savepath}")

# Optimisation functions
def create_optimise_setupFiles(ceinmsModelPath=None, 
                            inputDataFile=None,
                             calibrationCfgPath=None,
                             excitationGeneratorFilePath=None,
                             outputDirectory=None,
                             setupXMLPath=None,
                             templateCfgXMLPath=None):
    '''
    create CEINMS setup and configuration XML files for optimisation
    
    use settings.CEINMSParameters() for parameter ranges
    '''

    if not ceinmsModelPath:
        ceinmsModelPath = input("Enter path to CEINMS model file: ").strip('"')

    if not inputDataFile:
        inputDataFile = input("Enter path to input data file: ").strip('"')

    if not calibrationCfgPath:
        calibrationCfgPath = input("Enter path to calibration configuration file: ").strip('"')

    if not outputDirectory:
        outputDirectory = input("Enter path to output directory: ").strip('"')

    baseDir = os.path.dirname(setupXMLPath)
    root = ET.Element("ceinms")
    
    subjectFile = ET.SubElement(root, "subjectFile")
    subjectFile.text =  os.path.relpath(ceinmsModelPath, baseDir)
    
    inputData = ET.SubElement(root, "inputDataFile")
    inputData.text = os.path.relpath(inputDataFile, baseDir)
    
    executionFileTag = ET.SubElement(root, "executionFile")
    executionFileTag.text = os.path.relpath(calibrationCfgPath, baseDir)
    
    excitationGeneratorFile = ET.SubElement(root, "excitationGeneratorFile")
    excitationGeneratorFile.text = os.path.relpath(excitationGeneratorFilePath, baseDir)
    
    outputDirectoryTag = ET.SubElement(root, "outputDirectory")
    outputDirectoryTag.text = os.path.relpath(outputDirectory, baseDir)
    
    betaMinTag = ET.SubElement(root, "betaMin")
    betaMinTag.text = str(settings.CEINMSSettings.beta_min)
        
    betaMaxTag = ET.SubElement(root, "betaMax")
    betaMaxTag.text = str(settings.CEINMSSettings.beta_max)

    betaDeltaTag = ET.SubElement(root, "betaDelta")
    betaDeltaTag.text = str(settings.CEINMSSettings.beta_delta)

    gammaMinTag = ET.SubElement(root, "gammaMin")
    gammaMinTag.text = str(settings.CEINMSSettings.gamma_min)

    gammaMaxTag = ET.SubElement(root, "gammaMax")
    gammaMaxTag.text = str(settings.CEINMSSettings.gamma_max)

    gammaDeltaTag = ET.SubElement(root, "gammaDelta")
    gammaDeltaTag.text = str(settings.CEINMSSettings.gamma_delta)

    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, setupXMLPath)
    
    print(f"Optimization setup XML saved to: {os.path.abspath(setupXMLPath)}")

    # --- Create cfg file
    cfgTemplate = ET.parse(templateCfgXMLPath).getroot()
    
    # apply DOFs from CEINMS model
    ceinmsModel = ET.parse(ceinmsModelPath).getroot()
    dofSet = ceinmsModel.findall('.//dofSet')
    dofSet_cfg = cfgTemplate.findall('.//dofSet')[0]
    
    dofs = dofSet[0].findall('dof')
    dof_list = []
    for dof in dofs:
        dof_list.append(dof.find('name').text)
    
    dofSet_cfg.text = ' '.join(dof_list)
    
    # Lists to store muscle names
    synth_mtus = []
    adjust_mtus = []
    
    # Find all excitation elements
    exc_root = ET.parse(excitationGeneratorFilePath).getroot()
    
    mapping = exc_root.find('mapping')
    if mapping is not None:
        for excitation in mapping.findall('excitation'):
            muscle_id = excitation.get('id')

            # Check if excitation has input elements (non-empty)
            inputs = excitation.findall('input')
            if len(inputs) > 0:
                # Has EMG input - add to adjustMTUs
                adjust_mtus.append(muscle_id)
            else:
                # No EMG input - add to synthMTUs
                synth_mtus.append(muscle_id)
    
    # Sort the lists for consistent output
    synth_mtus.sort()
    adjust_mtus.sort()
    
    synthMTUsTag = cfgTemplate.findall('.//synthMTUs')[0]
    synthMTUsTag.text = ' '.join(synth_mtus)

    adjustMTUsTag = cfgTemplate.findall('.//adjustMTUs')[0]
    adjustMTUsTag.text = ' '.join(adjust_mtus)

    tree = ET.ElementTree(cfgTemplate)
    utils.save_pretty_xml(tree, calibrationCfgPath)
    print(f"Optimisation configuration XML saved to: {calibrationCfgPath}")
    
def optimise(setupXML_path=None):

    if not setupXML_path:
        setupXML_path = input("Enter path to setup XML file: ").strip('"')

    parentDir = os.path.dirname(setupXML_path)
    os.chdir(parentDir) # change wd to parent dir of setupXML (needed for CEINMS)
    
    root = ET.parse(setupXML_path).getroot()
    outputDirectory = root.find("outputDirectory").text

    # create output directory if it doesn't exist
    os.makedirs(outputDirectory, exist_ok=True)
    
    print("Optimizing CEINMS model...")
    ceinms_terminal(executable_path=utils.CEINMS_OPTIMISE_EXE, setupXML_path=setupXML_path)

# Plotting
def plot_ceinms_model_parameters(ceinmsModelPath=None):

    if not ceinmsModelPath:
        ceinmsModelPath = input("Enter path to optimised CEINMS model file: ").strip('"')

    def load_mtuSet(modelPath):
        root = ET.parse(modelPath).getroot()
        mtus = root.find('mtuSet').findall('mtu')
        
        # turn into DataFrame
        columns  = []
        for col in mtus[0].findall('*'): columns.append(col.tag)
        
        df = pd.DataFrame()
        for mtu in mtus:    
            name = mtu.find('name').text
            for col in columns:
                if col == 'name': continue
                if col not in df.columns:
                    df[col] = []
            for col in columns:
                if col == 'name': continue
                df.at[name, col] = float(mtu.find(col).text)
        
        return df

    mtuSet = load_mtuSet(ceinmsModelPath)
    muscle_names = mtuSet.index.tolist()
    parameters = mtuSet.columns.tolist()
    if len(parameters) == 10:    n_cols = 5
    else:                        n_cols = 4
    
    n_rows = (len(parameters) + n_cols - 1) // n_cols
    fig, axs = plt.subplots(n_rows, n_cols, figsize=(10, n_rows*3))
    plt.suptitle(f'Optimised Muscle Parameters: {ceinmsModelPath}', fontsize=16)
    axs = axs.flatten()

    for i, param in enumerate(parameters):
        
        # convert to numeric
        mtuSet[param] = pd.to_numeric(mtuSet[param], errors='coerce')   
        
        # plot bars left leg in red and right leg in blue
        colors = ['red' if name.endswith('_l') else 'blue' for name in muscle_names]
        axs[i].bar(muscle_names, mtuSet[param], color=colors)
        axs[i].set_title(param)
        axs[i].set_xticklabels(muscle_names, rotation=90)
        
    # set legend left leg on top right leg on bottom
    red_patch = plt.Line2D([0], [0], color='red', lw=4, label='Left Leg')
    blue_patch = plt.Line2D([0], [0], color='blue', lw=4, label='Right Leg')
    plt.legend(handles=[red_patch, blue_patch], loc='upper right')

    # make figure fullsize and tight layout
    plt.gcf().set_size_inches(18, 10)
    plt.tight_layout()
    
    # save figure
    fig_path = ceinmsModelPath.replace('.xml', '_parameters.png')
    plt.savefig(fig_path)
    print(f"Muscle parameters plot saved to: {fig_path}")

def plot_compare_ceinms_models(uncalibratedModelPath=None, calibratedModelPath=None):
    ''' Plot comparison of muscle parameters between uncalibrated and calibrated CEINMS models 
    
    Output: 
    - Bar plots of each muscle parameter for uncalibrated vs calibrated models
    - Difference in optimal fibre length, pennation angle, and tendon slack length between calibrated and uncalibrated models

    '''
    
    def load_mtuSet(modelPath):
        root = ET.parse(modelPath).getroot()
        mtus = root.find('mtuSet').findall('mtu')
        
        # turn into DataFrame
        columns  = []
        for col in mtus[0].findall('*'): columns.append(col.tag)
        
        df = pd.DataFrame()
        for mtu in mtus:    
            name = mtu.find('name').text
            for col in columns:
                if col == 'name': continue
                if col not in df.columns:
                    df[col] = []
            for col in columns:
                if col == 'name': continue
                df.at[name, col] = float(mtu.find(col).text)
        
        return df

    if not uncalibratedModelPath:
        uncalibratedModelPath = input("Enter path to uncalibrated CEINMS model file: ").strip('"')
    
    if not calibratedModelPath:
        calibratedModelPath = input("Enter path to calibrated CEINMS model file: ").strip('"')
        
    
    mtuSet_uncalibrated = load_mtuSet(uncalibratedModelPath)
    mtuSet_calibrated = load_mtuSet(calibratedModelPath)
    
    muscle_names = mtuSet_uncalibrated.index.tolist()
    parameters = mtuSet_uncalibrated.columns.tolist()
    
    if len(parameters) == 10:    n_cols = 5
    else:                        n_cols = 4
    
    n_rows = (len(parameters) + n_cols - 1) // n_cols
    fig, axs = plt.subplots(n_rows, n_cols, figsize=(10, n_rows*3))
    
    
    plt.suptitle(f'Compare: uncalibrated vs calibrated', fontsize=16)
    axs = axs.flatten()

    for i, param in enumerate(parameters):
        
        # convert to numeric
        mtuSet_uncalibrated[param] = pd.to_numeric(mtuSet_uncalibrated[param], errors='coerce')   
        mtuSet_calibrated[param] = pd.to_numeric(mtuSet_calibrated[param], errors='coerce')
        
        # plot bars left leg in red and right leg in blue
        colors = ['red' if name.endswith('_l') else 'blue' for name in muscle_names]
        if param in ['optimalFibreLength', 'pennationAngle', 'tendonSlackLength']:
            diff = mtuSet_calibrated[param] - mtuSet_uncalibrated[param]
            axs[i].bar(muscle_names, diff, color=colors)
            axs[i].set_title(f'Difference in {param} (Calibrated - Uncalibrated)')
            axs[i].set_xticklabels(muscle_names, rotation=90)
        else:            
            axs[i].bar(muscle_names, mtuSet_calibrated[param], color=colors)
            axs[i].set_title(param)
            axs[i].set_xticklabels(muscle_names, rotation=90)
            
    # set legend left leg on top right leg on bottom
    red_patch = plt.Line2D([0], [0], color='red', lw=4, label='Left Leg')
    blue_patch = plt.Line2D([0], [0], color='blue', lw=4, label='Right Leg')
    plt.legend(handles=[red_patch, blue_patch], loc='upper right')

    # make figure fullsize and tight layout
    plt.gcf().set_size_inches(18, 10)
    plt.tight_layout()
    
    # save figure
    fig_path = calibratedModelPath.replace('.xml', '_vs_uncalibrated.png')
    plt.savefig(fig_path)
    print(f"Muscle parameters plot saved to: {os.path.abspath(fig_path)}")

def plot_moments_calibration_results(momentResultsCSV=None):
    
    if not momentResultsCSV:
        momentResultsCSV = input("Enter path to moment calibration results CSV file: ").strip('"')

    moments_df = utils.load_any_data_file(momentResultsCSV)
    columns = moments_df.columns.tolist()
    data_columns = [col for col in columns if col != 'time']
    data_columns.sort()
    
    # get dof names by removing '_id' from id_columns
    dof_pairs = []
    for col in data_columns:
        moment_col = col + '_id'
        if moment_col in data_columns:
            dof_pairs.append((col, moment_col))

    n_dofs = len(dof_pairs)
    ncols = 2  # 2 columns for better layout
    nrows = int(np.ceil(n_dofs / ncols))
    
    # Create the figure and subplots
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4*nrows))
    if n_dofs == 1:
        axes = [axes]
    elif nrows == 1:
        axes = axes.reshape(1, -1)
    axes = axes.flatten()
    
    # Plot each DOF pair
    for i, (dof, dof_id) in enumerate(dof_pairs):
        ax = axes[i]
        
        # Plot the DOF angle
        line1 = ax.plot(moments_df['time'], moments_df[dof], 'b-', linewidth=2, label=f'ceinms)')
        line2 = ax.plot(moments_df['time'], moments_df[dof_id], 'r-', linewidth=2, label=f'inverse dynamics')

        # Set labels and title
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Moment (Nm)')
        ax.set_title(dof)
        ax.tick_params(axis='y')
        ax.grid(True, alpha=0.3)
        
        # Add legend (only on first subplot to avoid clutter)
        if i == 0:
            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax.legend(lines, labels, loc='upper right')
    
    # Hide any unused subplots
    for i in range(n_dofs, len(axes)):
        axes[i].set_visible(False)
    
    # Adjust layout
    plt.tight_layout()
    plt.suptitle('DOF Angles and Moments Comparison', fontsize=16, y=1.02)
    
    # Save the figure
    savePath = momentResultsCSV.replace('.csv', '.png')
    plt.savefig(savePath, dpi=300, bbox_inches='tight')
    print(f"DOF comparison plot saved as '{savePath}'")

    return fig, axes, dof_pairs
  
def plot_ceinms_calibration_results(setupXML_path=None):

    if not setupXML_path:
        setupXML_path = input("Enter path to calibration setup XML file: ").strip('"')

    setupXML = ET.parse(setupXML_path).getroot()
    calibrationOutputDir = setupXML.find('outputDirectory').text
    calibrationOutputDir = os.path.join(os.path.dirname(setupXML_path), calibrationOutputDir)

    # find all files ending with _calibrationResults.sto
    result_files = os.listdir(calibrationOutputDir)
    result_files = [os.path.join(calibrationOutputDir, f) for f in result_files if f.endswith('.csv')]
    for result_file in result_files:
        data = utils.load_any_data_file(result_file)

        time_col = 'time' if 'time' in data.columns else data.columns[0]
        signal_names = [col for col in data.columns if col != time_col]

        if not signal_names:
            print(f"No signal columns found in {result_file}, skipping.")
            continue

        ncols = min(4, len(signal_names))
        nrows = int(np.ceil(len(signal_names) / ncols))
        fig, axs = plt.subplots(nrows, ncols, figsize=(ncols * 4, nrows * 3), squeeze=False)
        axs_flat = axs.flatten()

        plt.suptitle(f'Calibration Results: {os.path.basename(result_file)}', fontsize=14)
        for i, signal in enumerate(signal_names):
            axs_flat[i].plot(data[time_col], data[signal])
            axs_flat[i].set_title(signal, fontsize=9)
            axs_flat[i].set_xlabel('Time')

        # hide unused subplots
        for j in range(len(signal_names), len(axs_flat)):
            axs_flat[j].set_visible(False)

        plt.tight_layout()

        # save figure
        fig_path = result_file.replace('.csv', '.png')
        plt.savefig(fig_path, dpi=150, bbox_inches='tight')
        print(f"Calibration results plot saved to: {fig_path}")
        plt.close()

def plot_optimisation_results(optimisationOutputDir=None):

    if not optimisationOutputDir:
        optimisationOutputDir = input("Enter path to optimisation output directory: ").strip('"')

    # find all files ending with _optimisationResults.sto
    result_files = os.listdir(optimisationOutputDir)
    result_files = [os.path.join(optimisationOutputDir, f) for f in result_files if f.endswith('.sto')]
    muscleGroups = settings.Muscle_Groups
    for result_file in result_files:
        data = utils.load_any_data_file(result_file)
        
        muscle_names = [col for col in data.columns if col != 'time']

        n_muscle_groups = len(muscleGroups)
        fig, axs = plt.subplots(n_muscle_groups, 1, figsize=(10, n_muscle_groups*3))
        plt.suptitle(f'Optimisation Results: {os.path.basename(result_file)}', fontsize=16)
        for i, (muscle_group, muscles) in enumerate(muscleGroups.items()):
            ax = axs[i] if n_muscle_groups > 1 else axs
            for muscle in muscles:
                if muscle in muscle_names:
                    ax.plot(data['time'], data[muscle], label=muscle)
            ax.set_title(f'Optimisation Results for Muscle Group: {muscle_group}')
            
            # if not last subplot, remove x labels
            if i < n_muscle_groups - 1:
                ax.set_xticklabels([])
            else:
                ax.set_xlabel('Time (%)')
                
            ax.legend()
            
        
        # save figure
        fig_path = result_file.replace('.sto', '.png')
        plt.savefig(fig_path)
        print(f"Optimisation results plot saved to: {fig_path}")
        plt.close()

def plot_experimental_vs_ceinms(emgFile=None,        
                                ceinmsExcitationsFile=None,excitationGeneratorFile=None,externalMomentsFile=None, ceinmsTorquesFile=None):

    if not emgFile:
        emgFile = input("Enter path to EMG data file: ").strip('"')

    if not ceinmsExcitationsFile:
        ceinmsExcitationsFile = input("Enter path to CEINMS excitations file: ").strip('"')
    
    if not excitationGeneratorFile:
        excitationGeneratorFile = input("Enter path to excitation generator file: ").strip('"')
    
    if not externalMomentsFile:
        externalMomentsFile = input("Enter path to external moments data file: ").strip('"')

    if not ceinmsTorquesFile:
        ceinmsTorquesFile = input("Enter path to CEINMS torques data file: ").strip('"')

    emg_data = utils.load_any_data_file(emgFile)
    ceinms_data = utils.load_any_data_file(ceinmsExcitationsFile)
    
    ceinms_time_range  = [ceinms_data['time'].iloc[0],ceinms_data['time'].iloc[-1]]
    emg_data = emg_data[(emg_data['time'] >= ceinms_time_range[0]) & (emg_data['time'] <= ceinms_time_range[1])]
    
    emg_time_range  = [emg_data['time'].iloc[0],emg_data['time'].iloc[-1]]

    # time normalise both datasets to the same length
    emg_data = utils.time_normalise_df(emg_data)
    ceinms_data = utils.time_normalise_df(ceinms_data)
    
    emg_mapping = ET.parse(excitationGeneratorFile).getroot().find('mapping')

    muscle_mapping = {}
    for excitation in emg_mapping.findall('excitation'):
        muscle_id = excitation.get('id')
        input_elems = excitation.findall('input')
        if len(input_elems) > 0:
            for input_elem in input_elems:
                signal = input_elem.text
                if signal not in muscle_mapping:
                    muscle_mapping[signal] = []
                muscle_mapping[signal].append(muscle_id)
    
    # -- Plot EMG vs CEINMS excitations -- #     
    n_muscles = len(muscle_mapping)
    fig, axs = plt.subplots(n_muscles, 1, figsize=(10, n_muscles*3))
    plt.suptitle(f'EMG vs CEINMS Excitations', fontsize=16)
    for i, (signal, muscles) in enumerate(muscle_mapping.items()):
        ax = axs[i] if n_muscles > 1 else axs
        line_emg = ax.plot(emg_data['time'], emg_data[signal], label=signal, color='blue')
        lines_ceinms = []   
        lineStyles = ['-', '--', '-.', ':','-', '--', '-.', ':']
        for j, muscle in enumerate(muscles):
            if muscle in ceinms_data.columns:
                r2 = utils.rsquared(emg_data[signal], ceinms_data[muscle])
                range_signal = emg_data[signal].max() - emg_data[signal].min()
                rmse = utils.rmse(emg_data[signal], ceinms_data[muscle])
                rmse_percent = (rmse / range_signal) * 100 if range_signal != 0 else 0
                lines_ceinms.append(ax.plot(ceinms_data['time'],ceinms_data[muscle], 
                                            linestyle=lineStyles[j % len(lineStyles)],
                                            label=f'{muscle} (R²: {r2:.2f}, RMSE: {rmse:.2f}/{rmse_percent:.0f}%)', color='red'))
                ax.set_ylabel('Excitation')
                if i < n_muscles - 1:
                    ax.set_xticklabels([])
                else:
                    ax.set_xlabel('Time (%)')
            else:
                print(f"Muscle {muscle} not found in CEINMS excitations data.")
        
        # legend with all lines
        handles = [line_emg[0]] + [line[0] for line in lines_ceinms]
        labels = [signal] + [f'{muscle} (R²: {utils.rsquared(emg_data[signal], ceinms_data[muscle]):.2f}, RMSE: {utils.rmse(emg_data[signal], ceinms_data[muscle]):.2f})' for muscle in muscles if muscle in ceinms_data.columns]
        ax.legend(handles, labels)
    
    # save figure
    ext = os.path.splitext(ceinmsExcitationsFile)[1]
    fig_path = ceinmsExcitationsFile.replace(ext, 'vs_emg.png')
    plt.savefig(fig_path)
    print(f"EMG vs CEINMS excitations plot saved to: {fig_path}")
    plt.close()

    # -- Plot external moments vs CEINMS torques -- #
    
    ext_moments_data = utils.load_any_data_file(externalMomentsFile)
    ceinms_torques_data = utils.load_any_data_file(ceinmsTorquesFile)
    
    # allign times and time normalise
    time_range_torques  = [ceinms_torques_data['time'].iloc[0],ceinms_torques_data['time'].iloc[-1]]
    ext_moments_data = ext_moments_data[(ext_moments_data['time'] >= time_range_torques[0]) & (ext_moments_data['time'] <= time_range_torques[1])]

    ext_moments_data = utils.time_normalise_df(ext_moments_data)
    ceinms_torques_data = utils.time_normalise_df(ceinms_torques_data)

    dof_names = [col for col in ceinms_torques_data.columns if col != 'time']
    
