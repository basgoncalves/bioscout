# from logging import root
from glob import glob
import math
import os
import shutil
import subprocess
import time
import sys
import re
from pathlib import Path

import webbrowser

# GUI toolkits are optional: importing utils for analysis/headless use must not
# require (or stall on) a display. The GUI widgets import these themselves.
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
except Exception:
    tk = None
    filedialog = messagebox = simpledialog = None
try:
    import customtkinter as ctk
except Exception:
    ctk = None

import numpy as np
import pandas as pd

# Handle matplotlib import with graceful fallback for circular import issues
try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.offsetbox import AnchoredText
    HAS_MATPLOTLIB = True
except ImportError as e:
    # If matplotlib fails to import (circular import or missing), provide fallback
    HAS_MATPLOTLIB = False
    class FakeMatplotlib:
        pyplot = None
        backends = None
        offsetbox = None
    matplotlib = FakeMatplotlib()
    plt = None
    PdfPages = None
    AnchoredText = None

# scipy
try:
    import scipy
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

import xml.etree.ElementTree as ET
import xml.dom.minidom

try:
    import opensim as osim
    HAS_OPENSIM = True
except ImportError:
    HAS_OPENSIM = False
    osim = None

# c3d
try:
    import c3d
    HAS_C3D = True
except ImportError:
    HAS_C3D = False
    c3d = None

# Ensure utils dir and app dir are on sys.path for standalone execution.

_utils_dir = str(Path(__file__).parent)
_app_dir = str(Path(__file__).parent.parent)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
if _utils_dir in sys.path:
    sys.path.remove(_utils_dir)
sys.path.insert(0, _utils_dir)

# ceinms and openSim are imported at BOTTOM of this file to break circular imports
# (ceinms.py and openSim.py both import utils, so importing them here causes deadlock)
openSim = None
ceinms = None
HAS_CEINMS = False

# settings
try:
    import settings
except Exception as e:
    print(f"Error importing settings module: {e}")
    settings = None

# emg_normalise imported at BOTTOM to break circular import chain
# (emg_normalise -> openSim -> exportC3D -> utils)
emg_normalise = None
HAS_EMG_NORMALISE = False


__version__ = '1.3.0'

# Project directories
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(UTILS_DIR)


def _resolve_project_dir():
    """Locate the project root (the folder holding models/ simulations/ results/).

    Priority:
      1. BIOSCOUT_PROJECT_DIR environment variable
      2. current working directory, if it looks like a project
         (has settings.py or a models/ or simulations/ folder)
      3. PROJECT_ROOT from an imported project settings.py (if it exists on disk)
      4. the folder containing the bioscout package (legacy default)
    """
    env = os.environ.get('BIOSCOUT_PROJECT_DIR')
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    cwd = os.getcwd()
    if (os.path.exists(os.path.join(cwd, 'settings.py')) or
            any(os.path.isdir(os.path.join(cwd, d))
                for d in ('simulations', 'Simulations', 'models', 'Models'))):
        return cwd
    try:
        _pr = getattr(settings, 'PROJECT_ROOT', None)
        if _pr and os.path.isdir(str(_pr)):
            return os.path.abspath(str(_pr))
    except Exception:
        pass
    return os.path.dirname(APP_DIR)


PROJECT_DIR = _resolve_project_dir()

# For compatibility with different projects
CODE_DIR = UTILS_DIR
MODULE_DIR = APP_DIR
POWERLIFTING_DIR = PROJECT_DIR
MODELS_DIR = os.path.join(PROJECT_DIR, 'Models') if os.path.exists(os.path.join(PROJECT_DIR, 'Models')) else os.path.join(PROJECT_DIR, 'models')
SIMULATIONS_DIR = os.path.join(PROJECT_DIR, 'Simulations') if os.path.exists(os.path.join(PROJECT_DIR, 'Simulations')) else os.path.join(PROJECT_DIR, 'simulations')
RESULTS_DIR = os.path.join(PROJECT_DIR, 'Results') if os.path.exists(os.path.join(PROJECT_DIR, 'Results')) else os.path.join(PROJECT_DIR, 'results')
TASK_FIGURES_DIR = os.path.join(RESULTS_DIR, 'task_figures')

CEINMS_DIR = os.path.join(UTILS_DIR, 'ceinms')
CEINMS_EXE = os.path.join(CEINMS_DIR, 'CEINMS.exe')
CEINMS_OPTIMISE_EXE = os.path.join(CEINMS_DIR, 'CEINMSoptimise.exe')
CEINMS_CALIBRATION_EXE = os.path.join(CEINMS_DIR, 'ceinms-nn-calibrate.exe')

PRINT_TERMINAL = False



def normalise_emg_across_session(trial_objects):
    """
    Session-level EMG amplitude normalisation.
    Finds max per channel across all trials, divides each trial's
    emg_filtered.mot by that max -> emg_filtered_normalised.mot.
    Updates trial.ceinms_excitations on each Analyse instance.
    """
    trial_dfs = {}
    for trial in trial_objects:
        filt_path = os.path.join(trial.path, 'emg_filtered.mot')
        if os.path.exists(filt_path):
            try:
                trial_dfs[trial] = load_any_data_file(filt_path)
            except Exception as e:
                print_to_log(f"[Warning] Could not load {filt_path}: {e}")

    if not trial_dfs:
        print_to_log("[Warning] No filtered EMG files found — skipping session normalisation")
        return

    first_df = next(iter(trial_dfs.values()))
    emg_cols = [c for c in first_df.columns if c.lower() != 'time']

    # Session-wide max per channel
    session_max = {}
    for col in emg_cols:
        vals = []
        for df in trial_dfs.values():
            if col in df.columns:
                vals.extend(pd.to_numeric(df[col], errors='coerce').dropna().values)
        session_max[col] = float(np.max(vals)) if vals else 1.0

    print_to_log(f"Session EMG max: { {k: round(v,4) for k,v in session_max.items()} }")

    for trial, df in trial_dfs.items():
        out_path = os.path.join(trial.path, 'emg_filtered_normalised.mot')
        norm = df.copy()
        for col in emg_cols:
            if col in norm.columns:
                mx = session_max.get(col, 1.0)
                if mx <= 0:
                    mx = 1.0  # zero channel — keep as-is, avoid 0/0 → NaN
                norm[col] = (pd.to_numeric(norm[col], errors='coerce') / mx).clip(0.0, 1.0)
        emg_normalise.write_sto_file(norm, out_path)
        trial.update_trial_attribute('ceinms_excitations', 'emg_filtered_normalised.mot')
        print_to_log(f"[Success] EMG normalised -> {out_path}", trial=trial.trial)


class Analyse(settings.Inputs):
    '''
    Contains paths from the user settings and functions to implement in the OpenSim/Ceinms analysis
    
    subject_name: Name of the subject (or the trial path if session_name and trial_name are None)

    Usage:
        - Create an instance of the Analyse class with the trial path:


    '''
    def __init__(self, trialPath=None):

        if trialPath is None:
            trialPath = input("Enter the path to the trial directory: ").strip('"')  # Remove quotes if the path is copied with them
        
        self.replace = getattr(settings.BatchSettings, 'replace_existing', False)
        self.path = os.path.abspath(trialPath)
        self.trial = os.path.basename(self.path)  # set early so _log works before settings load
        self.settingsXML = 'trial_settings.xml'

        if not os.path.exists(trialPath):
            self._log(f"Trial path not found: {trialPath}")
            os.makedirs(trialPath)
            self._reset_settings_xml()
            model_dir = os.path.join(MODELS_DIR, *os.path.normpath(self.path).split(os.sep)[-3:-1])
            if not os.path.exists(model_dir):
                os.makedirs(model_dir)
                self._log(f"Created model directory: {model_dir}")
            return
        
        else:
            os.chdir(self.path)
            
            try:
                # Check file size of settings XML to ensure it's not empty or corrupted
                if os.path.exists(self.settingsXML) and os.path.getsize(self.settingsXML) > 0 and os.path.getsize(self.settingsXML) < 1 * 1024 * 1024:  # limit 1 MB
                    self.load_settings(self.settingsXML)
                    self.replace = getattr(settings.BatchSettings, 'replace_existing', False)
                else:
                    self._log("Settings XML is missing, empty, or too large. Creating new settings XML.")
                    self._reset_settings_xml()
            except:
                self._log("Settings XML not found or could not be loaded. Creating new settings XML.")
                self._reset_settings_xml()
        
        # time.sleep(1)
                  
    def _reset_settings_xml(self):
        '''Create a settings xml for the trial at the specified path'''
        os.chdir(self.path)
        # delete existing settings xml if it exists
        if os.path.exists(self.settingsXML):
            os.remove(self.settingsXML)
            self._log(f"Existing settings XML deleted: {self.settingsXML}")
        
        path_parts = os.path.normpath(self.path).split(os.sep)
        self.subject = path_parts[-3]
        self.session = path_parts[-2]
        self.trial = path_parts[-1]

        self.parentdir = os.path.dirname(self.path)

        self._update_model()
        
        self.body_mass = None # Placeholder, will be updated from the model if possible
        self.time_range = 'None' # Placeholder, will be updated from data if possible
        
        # add each Input to the trial settings
        inputs = settings.Inputs(parentdir=self.path)
        for varInput in inputs.__dict__.items():
            filepath = os.path.join(self.path, varInput[1])
            if varInput[0] in ['model_dir', 'model_name']:
                continue
            if os.path.exists(filepath):
                setattr(self, varInput[0], os.path.relpath(filepath, self.path))
            else:
                setattr(self, varInput[0], varInput[1])
                  
        # Update body mass and time range from data available (.trc, .c3d, events.csv) 
        try:
            self.body_mass = self.get_body_mass()  
            self.time_range = self.get_time_range()
        except Exception as e:
            self._log(f"Error updating from data: {e}", terminal=True)
        
        self._update_emg_tag() 
        self._update_input_files()
        self._to_xml()

    def _to_xml(self):
        '''Print all settings for the trial to an xml in trial.path'''
        os.chdir(self.path)
        root = ET.Element("TrialSettings")
        for attr, value in self.__dict__.items():

            # Skip pandas DataFrames and Series - they have __dict__ but shouldn't be serialized
            if isinstance(value, (pd.DataFrame, pd.Series)):
                continue
            
            if isinstance(value, (str, int, float, bool, list, dict)):
                child = ET.SubElement(root, attr)
                if os.path.exists(str(value)):
                    child.text = os.path.relpath(str(value), self.path)
                else:
                    child.text = str(value)
            else:
                if not hasattr(value, '__dict__'):
                    continue

                for sub_attr, sub_value in value.__dict__.items():
                    child = ET.SubElement(root, f"{sub_attr}")
                    if os.path.exists(str(sub_value)):
                        child.text = os.path.relpath(str(sub_value), self.path)
                    else:
                        child.text = str(sub_value)
                
        tree = ET.ElementTree(root)
        save_pretty_xml(tree, self.settingsXML)
        print(f"Trial settings saved to: {os.path.abspath(self.settingsXML)}")
    
    def _update_input_files(self):
        '''Update input file paths in the trial settings to match the expected names and save to XML'''

        # change .mot file to match the self.grf_mot
        if os.path.exists(os.path.join(self.path, self.trial + '.mot')):
            os.rename(os.path.join(self.path, self.trial + '.mot'), os.path.join(self.path, self.grf_mot))
            print(f"Renamed {self.trial + '.mot'} to {self.grf_mot}")

        # change .trc file to match the self.markers
        if os.path.exists(os.path.join(self.path, self.trial + '.trc')):
            os.rename(os.path.join(self.path, self.trial + '.trc'), os.path.join(self.path, self.markers))
            print(f"Renamed {self.trial + '.trc'} to {self.markers}")

        # change .c3d file to match the self.c3d
        if os.path.exists(os.path.join(self.path, self.trial + '.c3d')):
            os.rename(os.path.join(self.path, self.trial + '.c3d'), os.path.join(self.path, self.c3d))
            print(f"Renamed {self.trial + '.c3d'} to {self.c3d}")

    def _update_model(self):
        '''
        update the model path in the xml settings based on the name of the subject, and save to XML. Models should be located in MODELS_DIR/subject/session/
        '''
        if self.subject == 'Athlete_03':
            self.update_model('scaled_12_05_2026.osim')

        elif self.subject == 'Athlete_03_Lernagopal':
            self.update_model('scaled_89_opt_N10.osim')

        elif self.subject == 'Athlete_03_Lernagopal_optimised':
            self.update_model('lernagopal_with_wrapings_scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_MRI_Katya':
            self.update_model('scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_GPK':
            self.update_model('GPK_scaled.osim')
        
        elif self.subject == 'Athlete_03_GPK_MRI':
            self.update_model('GPK_MRI_scaled.osim')

        elif self.subject == '022':
            self.update_model('022_Rajagopal2015_FAI_originalMass_opt_N10_hans.osim')
        
        elif self.subject in ['HC835B']:
            self.update_model('GPK_generic_Lukas_scaled.osim')
            
        else:
            self.update_model('scaled.osim')

    def _update_emg_tag(self):
        '''Update settingd XML with specific EMG types for a trial if needed'''
        if os.path.exists(os.path.join(self.path, 'EMG_filtered_normalised_scaled_0.70.sto')):
            emg_name = 'EMG_filtered_normalised_scaled_0.70.sto'
        elif os.path.exists(os.path.join(self.path, 'EMG_filtered_normalised.sto')):
            emg_name = 'EMG_filtered_normalised.sto'
        else:
            emg_name = settings.Inputs().emg

        self.update_trial_attribute('emg', emg_name)
        self.update_trial_attribute('ceinms_excitations', emg_name)

    def _remove_outputs(self):
        '''Remove existing output files from the trial directory to ensure a clean slate for the analysis'''
        input_files = [self.emg, self.c3d, self.grf_mot, self.markers, self.events]
        # walk through the trial directory and delete any files that are not in the input_files list
        for root, dirs, files in os.walk(self.path):
            for file in files:
                if file not in input_files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        print(f"Deleted existing output file: {file_path}")
                    except Exception as e:
                        print(f"Failed to delete file {file_path}: {e}")

    def _trial_type(self):

        if self.trial.lower().__contains__('squat'):
            return 'squatting'

    def convert_to_dict(self, attr_name):
        '''Convert a specific attribute of the trial to a dictionary'''
        attr_value = getattr(self, attr_name, None)
        if attr_value is None:
            print(f"Attribute {attr_name} not found.")
            return None
        
        if isinstance(attr_value, dict):
            return attr_value
        elif isinstance(attr_value, str):
            try:
                # Attempt to evaluate the string as a dictionary
                attr_dict = eval(attr_value)
                if isinstance(attr_dict, dict):
                    return attr_dict
                else:
                    print(f"Attribute {attr_name} is not a dictionary.")
                    return None
            except:
                print(f"Failed to convert attribute {attr_name} to dictionary.")
                return None
        else:
            print(f"Attribute {attr_name} is not a string or dictionary.")
            return None
    
    def load_settings(self, settingsXML):
        '''Load all settings for the trial from an xml in trial.path'''
        tree = ET.parse(settingsXML)
        root = tree.getroot()
        
        self.settingsXML = settingsXML
        
        for variable in root:
            var_name = variable.tag
            var_value = variable.text
            
            # Check if the attribute already exists
            if hasattr(self, var_name):
                current_attr = getattr(self, var_name)
            else:
                current_attr = None
                
            if var_name == 'time_range':
                try:
                    converted_value = [float(t) for t in var_value.strip('[]').split(', ')]
                except (ValueError, AttributeError, TypeError):
                    converted_value = None
            elif var_value.startswith('[') and var_value.endswith(']'):
                converted_value = var_value.strip('[]').split(', ')
            elif isinstance(current_attr, bool):
                converted_value = var_value.lower() == 'true'
            elif isinstance(current_attr, int):
                converted_value = int(var_value)
            elif isinstance(current_attr, float):
                converted_value = float(var_value)
            elif isinstance(current_attr, list):
                # Assuming list of strings separated by commas
                converted_value = var_value.strip('[]').split(', ')
            else:
                converted_value = var_value
            
            setattr(self, var_name, converted_value)
            
            # update self.path if path variable
            if var_name == "path":
                parent_dir = os.path.dirname(self.settingsXML)
                self.path = os.path.abspath(os.path.join(parent_dir, converted_value))
                

        print(f"Settings loaded from: {os.path.abspath(self.settingsXML)}")
    
    def load_results(self, tag, time_normalise=False):
        '''Load results from a specific output file in the trial directory based on the tag
        
        Options available same as settings.Inputs output file names (e.g 'ik', 'id', 'so_forces', 'ceinms_forces', etc.)

        '''

        # check if tag is valid (i.e present in the settings XML as an attribute)
        if not hasattr(self, tag):
            print(f"Tag '{tag}' not found in trial settings.")
            return None

        try:
            results = load_any_data_file(os.path.join(self.path, getattr(self, tag)))
        except Exception as e:
            print(f"Error loading results for tag '{tag}'")
            return None
        
        if time_normalise and 'time' in results.columns:
            try:
                results = time_normalise_df(results)
            except Exception as e:
                print(f"Error time normalising results for tag '{tag}': {e}")

        return results

    def get(self, attr_name):
        
        self = self.load_settings(self.settingsXML)
        
        return getattr(self, attr_name, None)
    
    def get_time_range_from_eventDetector(self):
        '''Get time range from event detector'''

        os.chdir(self.path)
        try:
            detector = EventDetector()
            events = detector.analyze_task(trc_file=self.markers, grf_file=self.grf_mot, kinematics_file=self.ik, task=self._trial_type())
            return events
        
        except Exception as e:
            print(f"Error determining time range from events: {e}")
            return False

    def get_time_range(self):
        os.chdir(self.path)

        try:
            event_data = pd.read_csv(self.events, index_col=None, header=None)
            self.time_range = [event_data.iloc[:, 1].min(), event_data.iloc[:, 1].max()]
            return self.time_range
        except:
            pass

        try:
            if os.path.exists(self.markers):
                marker_data = load_any_data_file(self.markers)
                # load_trc returns a MultiIndex DataFrame; df['time'] gives a sub-DataFrame
                # whose .min() would be a Series. Flatten to get scalar floats.
                time_col = marker_data['time']
                time_vals = time_col.values.flatten().astype(float)
                self.time_range = [float(time_vals.min()), float(time_vals.max())]
                return self.time_range
        except:
            pass

        try:
            if os.path.exists(self.c3d):
                c3d_data = load_any_data_file(self.c3d)
                time_col = c3d_data['time']
                time_vals = time_col.values.flatten().astype(float)
                self.time_range = [float(time_vals.min()), float(time_vals.max())]
                return self.time_range
        except:
            pass
    
    def get_markers(self):
        '''
        return a dataFrame with the name of each marker in the model and it's parent body
        '''

        os.chdir(self.path)
        try:
            model = osim.Model(self.model_dir)
            state = model.initSystem()
            markers = model.getMarkerSet()
            marker_data = []
            for i in range(markers.getSize()):
                marker = markers.get(i)
                marker_data.append({'Marker': marker.getName(), 'Parent Body': marker.getBodyName()})
            return pd.DataFrame(marker_data)
        except Exception as e:
            print(f"Error loading model or markers: {e}")
            return None

    def update_trial_attribute(self, attr_name, new_value):      
        '''Update a specific attribute of the trial and save to XML'''
        setattr(self, attr_name, new_value)
        self._log(f'Updated {attr_name} to {new_value} for trial at {self.path}')
        self._to_xml()
    
    def delete_trial_attribute(self, attr_name):
        '''Delete a specific attribute of the trial and save to XML'''
        if hasattr(self, attr_name):
            delattr(self, attr_name)
            self._log(f'Deleted attribute {attr_name} for trial at {self.path}')
            self._to_xml()
        else:
            self._log(f'Attribute {attr_name} not found in trial at {self.path}')

    def copy_input_files(self, src_subject, replace=False):
        """
        Copy input files from a template subject to the trial directory if they don't already exist or if replace is True.

        src_subject: name of the subject to copy input files from (should be located in SIMULATIONS_DIR/subject/session/)
        replace: whether to replace existing files in the trial directory (default is False)

        """
        input_files = [
            'trial_settings.xml','EMG_filtered_normalised.sto','EMG_filtered_normalised_scaled_0.70.sto','marker_experimental.trc','events.csv','c3dfile.c3d','GRF.xml', 'grf.mot'
        ]
        
        trial = self.trial
        src_trial_path = os.path.join(SIMULATIONS_DIR, src_subject, self.session, trial)
        dest_trial_path = self.path
        
        os.makedirs(dest_trial_path, exist_ok=True)
        
        for file_name in input_files:
            src_file = os.path.join(src_trial_path, file_name)
            dest_file = os.path.join(dest_trial_path, file_name)
            if os.path.exists(src_file) or replace:
                shutil.copy2(src_file, dest_file)
                print(f"Copied {src_file} to {dest_file}")
            else:
                print(f"Warning: {src_file} does not exist and was not copied.")

    # Model manipulation functions
    def update_model(self, new_model_name):
        '''Update the model path for the trial and save to XML
        
        new_model_name: str with just the name of the new model file (should be located in MODELS_DIR/subject/session/)

        Example usage:
            analysis = utils.Analyse(trialPath='main_dir/Subject/Session/trial')
            analysis.update_model('scaled_opt_N10_muscles_copied.osim')

        Output:
            Updated model path to main_dir/models/Subject/Session/scaled_opt_N10_muscles_copied.osim for trial at main_dir/Subject/Session/trial
        
        '''
        
        model_path = os.path.join(MODELS_DIR, self.subject, self.session, new_model_name)
        rel_model_path = os.path.relpath(model_path, self.path)

        self.model_name = new_model_name
        self.model_dir = rel_model_path
        self._log(f'Updated model path to {model_path} for trial at {self.path}')
        self._to_xml()

        return self.model_dir

    def increase_muscle_force(self, factor: float = 1.0, muscle_list: list = ['all']):
        """Increase muscle force in the scaled model by a given factor.
        
        Args:
            factor (float): Factor to increase muscle force by. Default is 1.5.
            replace (bool): Whether to replace existing modified model. Default is False.
        """
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        
        model_path = os.path.join(self.path, self.model_dir)
        new_model_path = model_path.replace('.osim', f'_increased_{factor:.2f}.osim')


        if not os.path.exists(model_path):
            print(f"Scaled model not found: {self.model_dir}")
            return

        if os.path.exists(new_model_path) and not self.replace:
            print(f"Increased model already used: {self.model_dir}")
            return

        if muscle_list != ['all']:
            new_model_path = new_model_path.replace('.osim', f'_selected_muscles.osim')
        
        if os.path.exists(new_model_path) or not self.replace:
            print(f"Modified model already exists: {new_model_path}")
            self.model_dir = new_model_path
            return
        
        # Load the model
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        # Increase max isometric force for each muscle
        for i in range(model.getMuscles().getSize()):
            muscle = model.getMuscles().get(i)
            if muscle_list == ['all'] or muscle.getName() in muscle_list:
                original_force = muscle.getMaxIsometricForce()
                new_force = original_force * factor
                muscle.setMaxIsometricForce(new_force)
                print(f"Muscle: {muscle.getName()}, Original Force: {original_force:.2f}, New Force: {new_force:.2f}")
        
        # Save the modified model
        model.printToXML(new_model_path)
        print(f"Modified model saved to: {os.path.abspath(new_model_path)}")
        
        # Update the used model path
        self.model_dir = new_model_path
        self._to_xml()

    def get_body_mass(self):
        """Retrieve body mass from the scaled model using OpenSim API funtion getTotalMass, and update the trial settings if it differs from the current body mass.
        
        Returns:
            float: Body mass in kg.
        """
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        
        if not os.path.exists(self.model_dir):
            print(f"Scaled model not found: {self.model_dir}")
            return 'Unknown'

        # Load the model
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        body_mass = model.getTotalMass(state)
        print(f"Body mass from model: {body_mass:.2f} kg")

        if body_mass != self.body_mass:
            self.body_mass = body_mass
            self._to_xml()

        return body_mass

    def get_body_mass_from_grf(self, update=False):
        '''Calculate body mass from GRF data if available.'''
        os.chdir(self.path)

        try:
            grf_data = load_any_data_file(self.grf_mot)
            vz_columns = [col for col in grf_data.columns if 'ground_force_' in col and col.endswith('_vy')]
            if 'time' in grf_data.columns and vz_columns:

                mean_1000ms = grf_data[vz_columns].iloc[:1000]
                body_mass = mean_1000ms.sum(axis=1).mean() / 9.81  
                print(f"Estimated body mass from GRF: {body_mass:.2f} kg")
                if update:
                    self.body_mass = body_mass
                    self._to_xml()
                return body_mass
        except Exception as e:
            print(f"Error calculating body mass from GRF: {e}")
            return None

    def get_muscle_list(self):
        """Retrieve list of muscles from the model_dir.
        
        Returns:
            list: List of muscle names.
        """
        os.chdir(self.path)
        
        if not os.path.exists(self.model_dir):
            print(f"Model not found: {self.model_dir}")
            return None

        # Load the model
        osim.Logger.setLevelString("error")
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        muscle_list = [model.getMuscles().get(i).getName() for i in range(model.getMuscles().getSize())]
        # print(f"Muscles in model: {muscle_list}")
        return muscle_list

    def edit_model_range_coordinates(self, coordinate_name, new_range: list):
        """Change the range of motion for a specific degree of freedom in the model.
        
        Args:
            coordinate_name (str): Name of the coordinate to modify. 
            new_range (list): New range of motion as [min, max] in radians.
        """
        os.chdir(self.path)
        
        if not os.path.exists(self.model_dir):
            print(f"Model not found: {self.model_dir}")
            return
        
        openSim.edit_model_range_coordinates(osim_modelPath=self.model_dir, coordinate_name=coordinate_name, new_range=new_range, save_path=self.model_dir)

    # analyses to run
    def scale_emg(self, scale_factor=1.0):
        """Scale EMG data by a given factor and save to a new file.
        
        Args:
            scale_factor (float): Factor to scale EMG data by. Default is 1.0.
        """
        os.chdir(self.path)
        if not os.path.exists(os.path.abspath(self.emg_normalised)):
            print(f"EMG normalised file not found: {self.emg_normalised}")
            return
        
        emg_data = load_any_data_file(self.emg_normalised)
        
        # Scale all columns except 'time'
        for col in emg_data.columns:
            if col != 'time':
                emg_data[col] *= scale_factor
        
        scaled_emg_path = self.emg_normalised.replace('.sto', f'_scaled_{scale_factor:.2f}.sto')
        write_sto_file(emg_data, os.path.abspath(scaled_emg_path))
        print(f"Scaled EMG data saved to: {os.path.abspath(scaled_emg_path)}")

        # Update the EMG normalised path
        self.update_trial_attribute('emg_normalised', scaled_emg_path)
        self.update_trial_attribute('emg_plot', scaled_emg_path)
        self.update_trial_attribute('ceinms_excitations', scaled_emg_path)
        
    def _log(self, message, terminal=False):
        """Log with trial name prefix."""
        print_to_log(message, trial=self.trial, terminal=terminal)

    def export_c3d(self, create_folder=None, emg_string_list=settings.BatchSettings.emg_string_list):
        '''
        Export C3D file using the exportC3D script, which extracts EMG data and saves it in a format compatible with CEINMS.

            create_folder: True/False to force subfolder creation; None (default) = auto-detect:
                           uses create_folder=True when the C3D is outside self.path so that
                           outputs land in the trial subdir regardless of where the C3D lives.

            emg_string_list: list of strings to identify EMG channels in the C3D file.
        '''
        import exportC3D

        print("Exporting C3D file...")

        os.chdir(self.path)
        c3d_abs = os.path.abspath(self.c3d)
        if not os.path.exists(c3d_abs):
            print(f"C3D file not found: {c3d_abs}")
            return

        if create_folder is None:
            # Auto: if the C3D is in a different directory than self.path,
            # tell exportC3D to create a subfolder (named after the C3D stem)
            # so all outputs land inside self.path.
            create_folder = (
                os.path.normcase(os.path.dirname(c3d_abs)) !=
                os.path.normcase(os.path.abspath(self.path))
            )

        time_range = exportC3D.main(c3d_filepath=c3d_abs, emg_string_list=emg_string_list, create_folder=create_folder)

        # Update start_time / end_time in trial_settings.xml from actual C3D data
        if time_range is not None:
            self.start_time = f"{time_range[0]:.4f}"
            self.end_time   = f"{time_range[1]:.4f}"
            self.time_range = list(time_range)
            self._to_xml()
            print(f"[{self.trial}] Time range updated: {self.start_time} – {self.end_time} s")

    @staticmethod
    def _get_openSim():
        """Return the openSim module, attempting a late import if it is still None."""
        global openSim
        if openSim is not None:
            return openSim
        try:
            from . import openSim as _os_mod
            openSim = _os_mod
            return openSim
        except Exception:
            pass
        try:
            import importlib.util as _ilu, os as _os_m
            _p = _os_m.path.join(_os_m.path.dirname(_os_m.path.abspath(__file__)), 'openSim.py')
            _spec = _ilu.spec_from_file_location('utils.openSim', _p)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            openSim = _mod
            return openSim
        except Exception as _e:
            raise RuntimeError(f"openSim module unavailable: {_e}") from _e

    def run_ik(self):
        os.chdir(os.path.abspath(self.path))
        self.load_settings(self.settingsXML)

        # Guard: IK requires a TRC file. If marker export failed (e.g. C3D has no 3D point data),
        # skip IK rather than hanging on an input() prompt or crashing inside osim.Storage().
        if not os.path.exists(self.markers):
            self._log(f'[SKIP] IK skipped — marker TRC not found: {self.markers}')
            return

        # Refresh time_range from data — TRC may not have existed when settings XML was first written.
        # Also catches the 'None' string produced when the XML was saved before export.
        _tr = getattr(self, 'time_range', None)
        if _tr is None or str(_tr).strip() in ('None', '[]', ''):
            self.time_range = self.get_time_range()

        # Create IK setup file if it doesn't exist or if replace is True
        _os = self._get_openSim()
        if not os.path.exists(self.setup_ik) or self.replace:
            _os.create_setup_IK(osim_modelPath=self.model_dir,
                                marker_trc=self.markers,
                                ik_output=self.ik,
                                taskSetPath=None,
                                time_range=self.time_range,
                                saveXMLPath=self.setup_ik)
        else:
            self._log(f'Inverse Kinematics output already exists: {self.ik}')
            return

        if os.path.exists(self.ik) and not self.replace:
            print(f'Inverse Kinematics output already exists: {self.ik}')
            return

        # Run IK using OpenSim API
        try:
            _os.run_ik(osim_modelPath=self.model_dir,
                    setup_xml=self.setup_ik,
                    resultsDir=self.path)
            self._log(f'[Success] Inverse Kinematics completed. Results are saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during Inverse Kinematics: {e}')
            raise  # propagate so _run_step logs it to the batch logger
        
        # Plot IK results and marker errors
        try:
            self.plot_ik()
            self.compare_marker_locations()
            self._log(f'[Success] IK results plotted and saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during IK plotting: {e}')

    def run_id(self):
        os.chdir(self.path)
        _os = self._get_openSim()
        if not os.path.exists(self.setup_grf) or self.replace:
            try:
                _os.create_grf_xml(grf_mot_path=self.grf_mot, 
                        output_xml_path=self.setup_grf,
                        marker_trc_path=self.markers,
                        right_foot_markers=getattr(settings.BatchSettings, 'right_foot_markers', None),
                        left_foot_markers=getattr(settings.BatchSettings, 'left_foot_markers', None),
                        right_foot_body='calcn_r', left_foot_body='calcn_l',
                        vert_force_threshold=10.0, filter_cutoff=6, datafile=None)
            except Exception as e:
                template_grf_path = os.path.join(self.setup_dir, self.setup_grf)
                if os.path.abspath(template_grf_path) != os.path.abspath(self.setup_grf):
                    shutil.copyfile(template_grf_path, self.setup_grf)

        if os.path.exists(self.id) and not self.replace:
            self._log(f'Inverse Dynamics output already exists: {self.id}')
            return
        
        # Run ID using OpenSim API
        try:
            _os.run_id(osimModelPath=self.model_dir,
                    ikOutputPath=self.ik,
                    grfXmlPath=self.setup_grf,
                    setupXmlPath=self.setup_id)
            
            self._log(f'[Success] Inverse Dynamics completed. Results are saved in {self.id}')
        except Exception as e:
            self._log(f'[Error] during Inverse Dynamics: {e}')
            raise

        # Plot ID results
        try:
            self.plot_id()
            self._log(f'[Success] ID results plotted and saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during ID plotting: {e}')

    def run_ma(self):
        
        os.chdir(self.path)
        if os.path.exists(self.ma) and not self.replace:
            self._log(f'Muscle Analysis output already exists: {self.ma}')
            return

        _os = self._get_openSim()
        try:
            _os.run_ma(osim_modelPath=self.model_dir,
                        ik_output=os.path.join(self.path, self.ik),
                        grf_xml=os.path.join(self.path, self.setup_grf))
            self._log(f'[Success] Muscle Analysis completed. Results are saved in {self.ma}')
        except Exception as e:
            self._log(f'[Error] during Muscle Analysis: {e}')
            raise
    
    def run_so(self):
        os.chdir(self.path)
        _os = self._get_openSim()

        # Resolve all paths to absolute so openSim.run_so never hits a
        # relative-path issue regardless of working directory changes.
        actuators_abs  = os.path.join(self.path, self.actuators_so)
        ik_abs         = os.path.join(self.path, self.ik)
        grf_abs        = os.path.join(self.path, self.setup_grf)
        setup_so_abs   = os.path.join(self.path, self.setup_so)

        if not os.path.exists(actuators_abs):
            # Copy template from the global setup folder
            template_dir = getattr(settings.BatchSettings, 'setup_files_folder',
                                   os.path.join(APP_DIR, 'config'))
            template_actuators_path = os.path.join(template_dir, self.actuators_so)
            if os.path.exists(template_actuators_path):
                shutil.copyfile(template_actuators_path, actuators_abs)
            else:
                raise FileNotFoundError(
                    f"Actuators template not found: {template_actuators_path}")

        if os.path.exists(os.path.join(self.path, self.so_forces)) and not self.replace:
            self._log(f'Static Optimization output already exists: {self.so_forces}')
            return

        try:
            _os.run_so(osim_modelPath=self.model_dir,
                    ik_output=ik_abs,
                    grf_xml=grf_abs,
                    setup_xml=setup_so_abs,
                    actuators=actuators_abs,
                    resultsDir=self.path)
            
            self._log(f'[Success] Static Optimization completed. Results are saved in:')
            self._log(f' - Forces: {os.path.abspath(self.so_forces)}')
            self._log(f' - Activations: {os.path.abspath(self.so_activations)}')
        except Exception as e:
            self._log(f'[Error] during Static Optimization: {e}')
            raise
        
        # Plot SO results
        try:
            self.plot_so()
            self._log(f'[Success] SO results plotted and saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during SO plotting: {e}')

    def run_energetics(self):
        """Run Metabolic Cost (Energetics) analysis for this trial.

        Wraps utils.openSim.run_energetics, which attaches an Umberger (2010)
        metabolic-energy probe set to the scaled model and runs a ProbeReporter.
        Needs the IK coordinates (kinematics) and, ideally, the Static
        Optimization activations (SO_StaticOptimization_activation.sto) so the
        probe evaluates real per-frame muscle activations.

        Output: energetics_ProbeReporter_probes.sto in the trial folder.
        """
        os.chdir(self.path)
        _os = self._get_openSim()

        ik_abs     = os.path.join(self.path, self.ik)
        so_act_abs = os.path.join(self.path, self.so_activations)
        out_abs    = os.path.join(self.path, 'energetics_ProbeReporter_probes.sto')

        if os.path.exists(out_abs) and not self.replace:
            self._log(f'Energetics output already exists: {out_abs}')
            return

        if not os.path.exists(ik_abs):
            raise FileNotFoundError(
                f'IK output required for energetics not found: {ik_abs}')

        if not os.path.exists(so_act_abs):
            self._log(f'[Warning] SO activation file not found ({so_act_abs}); '
                      f'energetics will use default activation.')
            so_act_abs = None

        try:
            _os.run_energetics(osim_modelPath=self.model_dir,
                               ik_output=ik_abs,
                               muscle_activations=so_act_abs,
                               setup_xml=None,
                               results_dir=self.path)
            self._log(f'[Success] Energetics completed. Results saved in {self.path}')
        except Exception as e:
            self._log(f'[Error] during Energetics: {e}')
            raise

    def run_jra(self):
        os.chdir(self.path)
        self.load_settings(self.settingsXML)
        _os = self._get_openSim()

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, self.setup_jra)
            shutil.copyfile(template_jra_path, self.setup_jra)
             
        if os.path.exists(self.jra) and not self.replace:
            return
        try:
            _os.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra,
                     actuators=None,
                     muscle_force_path=self.jra_forces,
                     saveFileName=self.jra)
        
            self._log(f"JRA analysis complete. Results saved {os.path.abspath(self.jra)}")
        except Exception as e:
            self._log(f'[Error] during Joint Reaction Analysis: {e}')
            
    def run_jra_ceinms(self):
        os.chdir(self.path)
        self.load_settings(self.settingsXML)

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, self.setup_jra)
            shutil.copyfile(template_jra_path, self.setup_jra)

        if os.path.exists(self.jra_ceinms) and not self.replace:
            self._log(f'JRA CEINMS output already exists: {self.jra_ceinms} and replace is set to False.')
            return
        
        try:
            openSim.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra,
                     actuators=None,
                     muscle_force_path=self.jra_forces_ceinms,
                     saveFileName=self.jra_ceinms)
            
            self._log(f"JRA CEINMS analysis complete. Results saved {os.path.abspath(self.jra_ceinms)}")
        except Exception as e:
            self._log(f'[Error] during Joint Reaction Analysis CEINMS: {e}')
        

    def run_emg_filter(self):
        """Per-trial: filter raw EMG -> emg_filtered.mot."""
        os.chdir(self.path)
        emg_path = os.path.join(self.path, self.emg)
        if not os.path.exists(emg_path):
            self._log(f"[Warning] EMG file not found: {emg_path}")
            return
        out_path = os.path.join(self.path, 'emg_filtered.mot')
        if os.path.exists(out_path) and not self.replace:
            self._log(f"EMG filtered file already exists: {out_path}")
            return
        try:
            data = load_any_data_file(emg_path)
            emg_cols = [c for c in data.columns if c.lower() != 'time']
            if not emg_cols:
                self._log("[Warning] No EMG columns found in emg.mot")
                return

            # --- Reliable EMG time vector + sampling frequency ---
            # Derive the sampling frequency from the EMG file's OWN time column
            # (the true analog rate) rather than a fixed setting, which is often
            # wrong (e.g. configured 1000 Hz while the data is 200 Hz). Only when
            # that time column is invalid (non-monotonic / all-zeros) do we rebuild
            # it, aligning to the trial's kinematic window so it matches IK/ID/GRF.
            data = data.copy()
            fs_setting = getattr(settings.BatchSettings, 'emg_sampling_freq', None)
            n = len(data)
            t = (pd.to_numeric(data['time'], errors='coerce').values.astype(float)
                 if 'time' in data.columns else np.array([]))
            time_ok = n >= 2 and np.all(np.isfinite(t)) and np.all(np.diff(t) > 0)
            if time_ok:
                fs = 1.0 / ((t[-1] - t[0]) / (n - 1))
            else:
                fs = fs_setting or 1000.0
                try:
                    start_t = float(self.time_range[0])
                    end_t = float(self.time_range[1])
                    if not (end_t > start_t):
                        raise ValueError
                    data['time'] = np.linspace(start_t, end_t, n)
                except Exception:
                    data['time'] = np.arange(n) / fs
                self._log(f'[Info] EMG time column invalid — rebuilt '
                          f'({n} samples @ ~{fs:.0f} Hz, '
                          f'{data["time"].iloc[0]:.4f}..{data["time"].iloc[-1]:.4f}s)',
                          terminal=True)

            # Auto-detect prefix — use the longest common prefix of EMG columns,
            # falling back to empty string (filters all non-time columns)
            prefix = 'EMG_Channels_EMG'
            if not any(c.startswith(prefix) for c in emg_cols):
                prefix = ''   # let filter_emg handle whatever names are present

            filtered = emg_normalise.filter_emg(data, emg_prefix=prefix, sampling_freq=fs)
            env_cols = [c for c in filtered.columns if c.endswith('_envelope')]
            if not env_cols:
                self._log("[Warning] filter_emg produced no envelope columns — check EMG prefix")
                return
            result = filtered[['time']].copy()
            for col in env_cols:
                base = col.replace('_bandpass_rectified_envelope', '').replace('_envelope', '')
                result[base] = filtered[col].values
            emg_normalise.write_sto_file(result, out_path)
            # Report which channels have zero signal (electrode not connected?)
            zero_chs = [c for c in result.columns if c != 'time'
                        and pd.to_numeric(result[c], errors='coerce').abs().max() < 1e-9]
            if zero_chs:
                self._log(f"[Info] {len(zero_chs)} channel(s) have zero signal "
                          f"(electrode not connected?): {', '.join(zero_chs)}", terminal=True)
            self._log(f"[Success] EMG filtered ({len(env_cols)} channels, "
                      f"{len(env_cols) - len(zero_chs)} non-zero) -> {out_path}")
        except Exception as e:
            self._log(f"[Error] EMG filter failed: {e}")

    def run_emg_normalise(self):
        
        os.chdir(self.path)
        emg_normalise_list = []
        
        for trialName in os.listdir(self.parentdir):
            emgPath = os.path.join(self.parentdir, trialName, self.emg)
            if os.path.exists(emgPath):
                emg_normalise_list.append(emgPath)
                
        if not emg_normalise_list:
            self._log(f'[Error] No EMG files found to normalise in {self.parentdir}')
            return
        
        openSim.run_emg_normalise(target_emg_path= str(self.emg),
                                normalise_emg_list=emg_normalise_list)
        
        self._log(f'[Success] EMG normalisation completed. Normalised EMG saved to {self.emg}')

        new_emg_name = os.path.basename(self.emg).replace('.mot', '_normalised.mot')

        self.update_trial_attribute('emg', new_emg_name)
        self.update_trial_attribute('ceinms_excitations', new_emg_name)
    
    def convert_mot_to_sto(self, attr=None):

        os.chdir(self.path)
        if attr:
            mot_file = getattr(self, attr)
        
        sto_file_path = mot_file.replace('.mot', '.sto')
        if os.path.exists(sto_file_path) and not self.replace:
            self._log(f'STO file already exists: {sto_file_path}')
            return
        
        sto_file_path = openSim.convert_mot_to_sto(mot_file_path=os.path.abspath(mot_file))

        self.update_trial_attribute(attr, os.path.relpath(sto_file_path, self.path))

    def muscles_per_coordinate(self, osimModel=None, coord_name=None):

        if osimModel is None:
            osimModel = osim.Model(self.model_dir)

        muscles = []
        indexes = []
        coord = osimModel.getCoordinateSet().get(coord_name)
        state = osimModel.initSystem()
        osimModel.realizePosition(state)

        for i in range(osimModel.getMuscles().getSize()):
            muscle = osimModel.getMuscles().get(i)
            if abs(muscle.computeMomentArm(state, coord)) > 1e-4:
                muscles.append(muscle.getName())
                indexes.append(i)

        return muscles, indexes
    
    def calculate_muscle_moments(self, forces_type = 'so'):
        '''Calculate muscle moments by multiplying muscle forces by their moment arms for each coordinate.
        
        forces_type: 'so' for static optimization forces, 'ceinms' for CEINMS muscle forces (default is 'so')
        '''

        if forces_type == 'so':
            muscle_forces = load_any_data_file(self.so_forces)
        elif forces_type == 'ceinms':
            muscle_forces = load_any_data_file(self.jra_forces_ceinms)

        dofNames = settings.BatchSettings.dof_list
        
        for dof_name in dofNames:
            moment_arms = load_any_data_file(os.path.join(self.path,self.ma, f"_MuscleAnalysis_MomentArm_{dof_name}.sto"))

            muscle_moments = pd.DataFrame()
            for muscle in muscle_forces.columns:
                if muscle in moment_arms.columns:
                    muscle_moments[muscle] = muscle_forces[muscle] * moment_arms[muscle]
                else:
                    print(f"Moment arm for muscle {muscle} not found in {moment_arms.columns}")

            # save muscle moments to a new file
            moments_file_path = os.path.join(self.path, self.ma, f"_MuscleMoments_{dof_name}_{forces_type}.sto")
            write_sto_file(muscle_moments, moments_file_path)
            print(f"Muscle moments saved to: {os.path.abspath(moments_file_path)}")
            time.sleep(1)  # ensure file is saved before updating trial attribute

        return muscle_moments

    #--- Valid
    def compare_marker_locations(self):
        os.chdir(self.path)
        try:
            openSim.compare_marker_locations(marker_experimental_path=os.path.abspath(self.markers),marker_virtual_path=os.path.abspath('.\\_ik_model_marker_locations.sto'))
        
            self._log(f'[Success] Marker location comparison completed: {self.model_markers} vs {self.markers}')
        except Exception as e:
            self._log(f'[Error] during marker location comparison: {e}')

    def check_moment_arms(self):
        ''' Using the openSim.py function checkMomentArms to plot moment arms for each coordinate and muscle, and compare to expected patterns based on muscle geometry.'''

        os.chdir(self.path)

        results = {}
        for leg in ['l', 'r']:
            try:
                wrong, disc, action, frames = openSim.checkMuscleMomentArms(
                    model_file_path=self.model_dir,
                    ik_file_path=self.ik,
                    leg=leg,
                    threshold=0.005)
                results[leg] = {'wrong': bool(wrong), 'muscle_action': action, 'frames': frames}
            except Exception as e:
                self._log(f'[Error] during moment arm check for {leg} leg: {e}')
                results[leg] = {'wrong': False, 'muscle_action': [], 'frames': []}

        return results

    def adjust_moment_arms(self, radius_step: float = 0.002, max_iter: int = 20, skip_frames: int = 2):
        """
        Iteratively increases wrapping-surface radii for muscles that have moment-arm
        discontinuities beyond the first `skip_frames` frames, then re-runs the moment-arm
        check.  Stops when no qualifying discontinuities remain or `max_iter` is reached.
        The modified model is saved in place; a .bak copy is created on the first iteration.
        """
        import shutil
        import opensim as osim

        os.chdir(self.path)

        # Make a one-time backup of the original model
        backup_path = self.model_dir.replace('.osim', '_original_backup.osim')
        if not os.path.exists(backup_path):
                shutil.copy2(self.model_dir, backup_path)
                print(f'Backup saved: {backup_path}')

        for iteration in range(max_iter):
                print(f'\n--- Moment arm check: iteration {iteration + 1}/{max_iter} ---')
                results = self.check_moment_arms()

                # Collect muscles whose discontinuities occur after the skip window
                problem_muscles: set = set()
                for leg in ['l', 'r']:
                        leg_data = results.get(leg, {})
                        for action_str, frames in zip(leg_data.get('muscle_action', []),
                                                      leg_data.get('frames', [])):
                                real_frames = [int(f) for f in frames if int(f) >= skip_frames]
                                if real_frames:
                                        muscle_name = action_str.split(' ')[0]
                                        problem_muscles.add(muscle_name)

                if not problem_muscles:
                        print(f'No significant discontinuities after {iteration} iteration(s). Done.')
                        return

                print(f'  Muscles with discontinuities: {sorted(problem_muscles)}')
                print(f'  Increasing wrap-object radii by {radius_step} m ...')

                model = osim.Model(self.model_dir)
                model.initSystem()

                adjusted_wraps: set = set()
                for muscle_name in problem_muscles:
                        try:
                                muscle = model.getMuscles().get(muscle_name)
                        except Exception:
                                print(f'  [warn] muscle "{muscle_name}" not found in model – skipped')
                                continue

                        wrap_set = muscle.getGeometryPath().getWrapSet()
                        for w in range(wrap_set.getSize()):
                                wrap_name = wrap_set.get(w).getWrapObjectName()
                                if wrap_name in adjusted_wraps:
                                        continue  # already increased this iteration

                                # Search every body for the named wrap object
                                body_set = model.getBodySet()
                                for b in range(body_set.getSize()):
                                        body = model.updBodySet().get(b)
                                        wo_set = body.updWrapObjectSet()
                                        for k in range(wo_set.getSize()):
                                                wo = wo_set.get(k)
                                                if wo.getName() != wrap_name:
                                                        continue
                                                # Try WrapCylinder
                                                cyl = osim.WrapCylinder.safeDownCast(wo)
                                                if cyl is not None:
                                                        new_r = cyl.get_radius() + radius_step
                                                        cyl.set_radius(new_r)
                                                        adjusted_wraps.add(wrap_name)
                                                        print(f'    {muscle_name}: WrapCylinder "{wrap_name}" radius -> {new_r:.4f} m')
                                                        continue
                                                # Try WrapSphere
                                                sph = osim.WrapSphere.safeDownCast(wo)
                                                if sph is not None:
                                                        new_r = sph.get_radius() + radius_step
                                                        sph.set_radius(new_r)
                                                        adjusted_wraps.add(wrap_name)
                                                        print(f'    {muscle_name}: WrapSphere "{wrap_name}" radius -> {new_r:.4f} m')

                if not adjusted_wraps:
                        print('  No wrap objects found for the problem muscles – stopping.')
                        return

                model.printToXML(self.model_dir)
                print(f'  Model saved: {self.model_dir}')

        print(f'Max iterations ({max_iter}) reached – some discontinuities may remain.')

    def calculate_emg_activation_errors(self):
        '''Calculate errors between EMG activations and CEINMS excitations, and save to a new file.'''
        os.chdir(self.path)

        emg_data = load_any_data_file(self.emg_normalised)
        ceinms_activations = load_any_data_file(self.jra_forces_ceinms.replace('MuscleForces.sto', 'Activations.sto'))  
        so_activations = load_any_data_file(self.so_activations)

        error_df = pd.DataFrame()

    def calculate_mean_marker_error(self):
        '''
        Load the _ik_marker_errors.sto file and calculate the mean marker error across all markers and time frames, and save to a new file.
        '''
        os.chdir(self.path)
        marker_errors = load_any_data_file('.\\_ik_marker_errors.sto')
        mean_error = marker_errors.drop(columns='time').mean().mean()
        mean_error_df = pd.DataFrame({'mean_marker_error': [mean_error]})

        return mean_error_df

    def calculate_moment_errors(self, forces_type='so'):
        '''
        Calculate errors between muscle moments calculated from SO or CEINMS forces and the inverse dynamics joint moments, and save to a new file.
        '''
        os.chdir(self.path)
        
        id_moments = load_any_data_file(self.id)
        muscle_forces = load_any_data_file(self.so_forces) if forces_type == 'so' else load_any_data_file(self.jra_forces_ceinms)
        dofNames = id_moments.columns.drop('time')

        moment_errors = pd.DataFrame(columns=['RMSE', 'RMSE %', 'R2'], index=dofNames)

        for dof_name in dofNames:
            try:
                moment_arms = load_any_data_file(os.path.join(self.path,self.ma, f"_MuscleAnalysis_MomentArm_{dof_name}.sto"))
            except Exception as e:
                print(f"Error loading moment arms for {dof_name}: {e}")
                continue
            
            muscle_moments = pd.DataFrame()
            for muscle in muscle_forces.columns:
                if muscle in moment_arms.columns:
                    muscle_moments[muscle] = muscle_forces[muscle] * moment_arms[muscle]
                else:
                    print(f"Moment arm for muscle {muscle} not found in {moment_arms.columns}")
            
            total_muscle_moment = muscle_moments.sum(axis=1)
            id_moment = id_moments[dof_name]

            rmse = np.sqrt(np.mean((total_muscle_moment - id_moment) ** 2))
            rmse_pct = (rmse / np.abs(id_moment).max()) * 100
            ss_res = np.sum((id_moment - total_muscle_moment) ** 2)
            ss_tot = np.sum((id_moment - np.mean(id_moment)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else np.nan
            
            moment_errors.loc[dof_name] = [rmse, rmse_pct, r2]
        
        return moment_errors 

    def scale_moment_arm(self, coordinate_name, muscles, factor):
        """
        Scale the moment arm of the given muscle(s) by *factor* and save a new .sto.

        Parameters
        ----------
        sto_path : path to the MomentArm .sto file (e.g. _MuscleAnalysis_MomentArm_hip_flexion_r.sto)
        muscles  : muscle name or list of muscle names matching column headers
        factor   : multiplicative scale factor (e.g. 1.5 increases moment arm by 50 %)

        Returns
        -------
        Path to the written output file.
        """
        if isinstance(muscles, str):
            muscles = [muscles]

        sto_path = os.path.join(self.ma, f"_MuscleAnalysis_MomentArm_{coordinate_name}.sto")
        data = load_any_data_file(sto_path)

        missing = [m for m in muscles if m not in data.columns]
        if missing:
            available = [c for c in data.columns if c != "time"]
            raise ValueError(
                f"Muscle(s) not found in {sto_path.name}: {missing}\n"
                f"Available muscles: {available}"
            )

        data = data.copy()
        for muscle in muscles:
            data[muscle] = data[muscle] * factor

        output_path = sto_path.replace(".sto", ".sto")

        write_sto_file(dataFrame=data, file_path=output_path)
        print(f"Saved scaled moment arm to: {output_path}")
        return output_path

        

    def plot_create_subplot(self, n_muscles, fig=None):
        ncols = int(math.ceil(math.sqrt(n_muscles)))
        nrows = int(math.ceil(n_muscles / ncols))
        if fig is None:
            fig, axes = plt.subplots(nrows, ncols, figsize=(ncols*5, nrows*4), constrained_layout=True)
            axes = axes.flatten()
        else:
            axes = fig.get_axes()

        # Hide any unused subplots
        for i in range(n_muscles, len(axes)):
            axes[i].axis('off')
        
        return fig, axes
      
    def plot_moment_arms(self, coord_name: str = None, fig=None):
        
        os.chdir(self.path)
        fileList = os.listdir(self.ma)
        fileList = [file for file in fileList if file.startswith('_MuscleAnalysis_MomentArm') and file.endswith('.sto')]
        
        for file in fileList:
            filepath = os.path.join(self.ma, file)
            if coord_name in file:
                break
            else:
                continue
        
        dof = file.replace('.sto','').replace('_MuscleAnalysis_MomentArm_','')
        print(f"Loading moment arms for DOF: {dof} from {file}")
        moment_arms = load_any_data_file(filepath)
        muscleList,muscleIdx = self.muscles_per_coordinate(osim.Model(self.model_dir), dof)
        
        n_muscles = len(muscleList)
        if n_muscles == 0:
            print(f"No muscles found for DOF: {dof}")
            return None, None
        
        ncols = int(math.ceil(math.sqrt(n_muscles)))
        nrows = int(math.ceil(n_muscles / ncols))
        if fig is None:
            fig, axes = self.plot_create_subplot(n_muscles)
        else:
            axes = fig.get_axes()
        

        fig.suptitle(f"Moment Arms for DOF: {dof}", fontsize=16)
        line_label = f'{self.subject}_{self.session}_{self.trial}'
        for muscle in muscleList:
            ax = axes[muscleList.index(muscle)]
            ax.plot(moment_arms[muscle], label=line_label)
            ax.set_title(f"{muscle}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Moment Arm")
        
        axes[0].legend()

        return fig, axes

    def plot_ik(self, columns_to_plot='all'):
        os.chdir(self.path)
        self.joint_angles = load_any_data_file(self.ik)
        
        if columns_to_plot == 'all':
            columns_to_plot = list(self.joint_angles.columns)
            columns_to_plot.remove('time')
        
        n_vars = len(columns_to_plot)
        fig, axes = self.plot_create_subplot(n_vars)
        
        fig.suptitle(f"Inverse Kinematics Joint Angles", fontsize=16)
        for var in columns_to_plot:
            ax = axes[columns_to_plot.index(var)]
            ax.plot(self.joint_angles['time'], self.joint_angles[var], label='')
            ax.set_title(f"{var}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Angle (degrees)")
        
        axes[0].legend()
        
        # save figure and return
        save_path = os.path.join(self.path, f"{self.ik.replace('.mot', '.png')}")
        plt.savefig(save_path)
        print(f'Figure saved to {save_path}')
        
        return fig, axes
    
    def plot_id(self, columns_to_plot='all'):
        self.inverse_dynamics = load_any_data_file(self.id)
        
        if columns_to_plot == 'all':
            columns_to_plot = list(self.inverse_dynamics.columns)
            columns_to_plot.remove('time')
        
        n_vars = len(columns_to_plot)
        fig, axes = self.plot_create_subplot(n_vars)
        
        fig.suptitle(f"Inverse Dynamics Joint Moments", fontsize=16)
        for var in columns_to_plot:
            ax = axes[columns_to_plot.index(var)]
            ax.plot(self.inverse_dynamics['time'], self.inverse_dynamics[var], label='')
            ax.set_title(f"{var}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Moment (Nm)")
        
        axes[0].legend()
        
        # save figure and return
        save_path = os.path.join(self.path, os.path.splitext(self.id)[0] + '.png')
        plt.savefig(save_path)
        print(f'Figure saved to {save_path}')
        
        return fig, axes
    
    def plot_so(self, ):
        os.chdir(self.path)
        so_forces = load_any_data_file(self.so_forces)
        so_activations = load_any_data_file(self.so_activations)
        emg_normalised = load_any_data_file(self.emg)

        # crop to time range of the trial
        time_range = self.get_time_range()
        so_forces = so_forces[(so_forces['time'] >= time_range[0]) & (so_forces['time'] <= time_range[1])]
        so_activations = so_activations[(so_activations['time'] >= time_range[0]) & (so_activations['time'] <= time_range[1])]
        emg_normalised = emg_normalised[(emg_normalised['time'] >= time_range[0]) & (emg_normalised['time'] <= time_range[1])]


        # Coordinate names must match the OpenSim model (knee is 'knee_angle',
        # and the model has no 'knee_adduction').
        coordinates = {'hip_flexion': None, 'hip_adduction': None, 'hip_rotation': None,
                        'knee_angle': None,
                        'ankle_angle': None}
        
        muscleGroups = {}
        for coord in list(coordinates.keys()):
            for leg in ['_r', '_l']:
                coord_name = coord + leg
                try:
                    muscles, indexes = self.muscles_per_coordinate(osim.Model(self.model_dir), coord_name)
                    muscleGroups[coord_name] = muscles
                except Exception as e:
                    # remove the key from the dictionary if there is an error (e.g. coordinate not found in model)
                    print(f"Error finding muscles for coordinate {coord}: {e}")
                    coordinates.pop(coord, None)

        n_vars = len(muscleGroups)
        fig, axes = plt.subplots(n_vars//2, 2, figsize=(26, 14))
        
        fig.suptitle(f"Static Optimization Muscle Forces", fontsize=16)
        for irow, (coord, _) in enumerate(coordinates.items()):
            for icol, leg in enumerate(['_r', '_l']):
                coord_name = coord + leg
                muscles = muscleGroups.get(coord_name, [])
                if not muscles:
                    continue
                
                ax = axes[irow, icol]
                for muscle in muscles:
                    line1 = ax.plot(so_forces['time'], so_forces[muscle], label=muscle)
                    # on a secondary y-axis plot activations
                    activations = so_activations[muscle]

                ax.set_title(f"{coord_name}")
                ax.set_xlabel("Time")

                if icol == 0:
                    ax.set_ylabel("Force (N)")
        
        # Legend: collect actual handles from any subplot that has lines
        handles, labels = [], []
        for ax in axes.flat:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h)
                    labels.append(l)

        n_legend_cols = min(len(handles), 10)
        fig.legend(handles, labels, loc='lower center', ncol=n_legend_cols, fontsize='small',
                   bbox_to_anchor=(0.5, 0.0), bbox_transform=fig.transFigure)

        # save figure and return
        save_path = os.path.join(self.path, f"{self.trial}_SO_Muscle_Forces.png")
        plt.tight_layout(rect=[0, 0.18, 1, 1])  # reserve bottom 18% for legend
        plt.savefig(save_path, bbox_inches='tight')
        print(f'Figure saved to {save_path}')
        
        # save interactive figure
        interactive_save_path = save_path.replace('.png', '.html')
        # convert_to_interactive_fig(fig, interactive_save_path)

        return fig, axes
    
    def plot_jra(self, origin='SO'):
        os.chdir(self.path)
        if origin == 'CEINMS':
            self.jra_results = load_any_data_file(self.jra_ceinms)
        else:
            self.jra_results = load_any_data_file(self.jra)
        
        joints = {'Hip': ['hip_r_on_femur_r_in_femur_r_fx',         'hip_r_on_femur_r_in_femur_r_fy', 'hip_r_on_femur_r_in_femur_r_fz'],
            'Knee': ['walker_knee_r_on_tibia_r_in_tibia_r_fx', 'walker_knee_r_on_tibia_r_in_tibia_r_fy', 'walker_knee_r_on_tibia_r_in_tibia_r_fz'],
            'Ankle': ['ankle_r_on_talus_r_in_talus_r_fx', 'ankle_r_on_talus_r_in_talus_r_fy', 'ankle_r_on_talus_r_in_talus_r_fz']}

        n_vars = len(joints)
        fig, axes = self.plot_create_subplot(n_vars*4)
        
        fig.suptitle(f"Joint Reaction Analysis", fontsize=16)
        i_subplot = -1
        for row, (joint, components) in enumerate(joints.items()):
                        
            # 3d sum of reaction forces
            x = self.jra_results[components[0]]
            y = self.jra_results[components[1]]
            z = self.jra_results[components[2]]
            resultant = sum3d(self.jra_results, components)
            
            i_subplot += 1  
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], x, label='X')
            ax.set_title(f"{joint} - X Reaction Force")
            ax.set_ylabel("Reaction Force (N)")
            
            i_subplot += 1
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], y, label='Y')
            ax.set_title(f"{joint} - Y Reaction Force")
            
            i_subplot += 1
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], z, label='Z')
            ax.set_title(f"{joint} - Z Reaction Force")
            
            i_subplot += 1
            ax = axes[i_subplot]
            ax.plot(self.jra_results['time'], resultant, label='Resultant')
            ax.set_title(f"{joint} - Resultant Reaction Force")

            ax.set_ylabel("Reaction Force (N)")

            if row == 0:
                ax.legend(loc='upper right')
                
            if row == n_vars - 1:
                ax.set_xlabel("Time")
        
        # save figure and return
        savePath = os.path.join(self.path, f"{self.trial}_JRA_Results_{origin}.png")
        plt.savefig(savePath)
        print(f'Figure saved to {savePath}')

        return fig, axes
    
    def plot_emg(self):
        
        os.chdir(self.path)
        emg_file_path = os.path.abspath(self.emg)
        if not os.path.exists(emg_file_path):
            print(f"EMG file not found: {emg_file_path}")
            return
        
        self.emg_data = load_any_data_file(emg_file_path)
        
        muscles = self.emg_data.columns

        n_vars = len(muscles)
        fig, axes = self.plot_create_subplot(n_vars)
        
        fig.suptitle(f"EMG Excitations", fontsize=16)
        for i, muscle in enumerate(muscles):
            ax = axes[i]
            ax.plot(self.emg_data['time'], self.emg_data[muscle], label=muscle)

            ax.set_title(f"{muscle}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Excitation")
            # ax.set_ylim([0, 1])
            
            if i == 0:
                ax.legend(loc='upper right')
        
        # save figure and return
        savePath = emg_file_path.replace('.sto', '.png').replace('.mot', '.png')
        plt.savefig(savePath)
        print(f'Figure saved to {savePath}')

        return fig, axes
    
    def plot_summary(self):
        '''
        Plot summary of results for a trial and settings DOFs, including:

                - row 1 IK angles
                - row 2 ID moments + Muscle contributions to moments (Static Optimisation)
                - row 3 ID moments + Muscle contributions to moments (CEINMS)
                - row 4 EMG vs SO excitations vs CEINMS excitations (with RMSE and R2 metrics)
                - row 5 JRA reaction loads (SO vs CEINMS)
        '''

        def calculate_muscle_moments(muscle_forces, moment_arms):
                # Ensure muscle forces and moment arms have the same columns
                common_muscles = sorted(set(muscle_forces.columns) & set(moment_arms.columns))
                if not common_muscles:
                        raise ValueError("No common muscles found between forces and moment arms.")
                
                # Build all columns at once to avoid fragmentation warning
                cols = {muscle: muscle_forces[muscle].values * moment_arms[muscle].values for muscle in common_muscles}

                # add time column if exists in muscle_forces
                if 'time' in muscle_forces.columns:
                        cols['time'] = muscle_forces['time'].values

                return pd.DataFrame(cols, index=muscle_forces.index)
        
        def create_colors_for_muscles(muscle_names):
                import matplotlib
                color_palette = matplotlib.colormaps['tab20'].resampled(max(len(muscle_names), 1))
                colors = {muscle: color_palette(i) for i, muscle in enumerate(muscle_names)}
                return colors
        
        def plot_muscle_moments(ax, id_moments, muscle_moments, dof, colors, label_prefix):
                line, = ax.plot(id_moments['time'], id_moments[f'{dof}_moment'], label='ID', color=colors['externalBiomech'])
                if 'ID' not in legend_handles:
                        legend_handles['ID'] = line

                colors_muscles = create_colors_for_muscles(muscle_moments.columns)
                for muscle in muscle_moments.columns:
                        line, = ax.plot(muscle_moments['time'], muscle_moments[muscle], label=muscle, color=colors_muscles[muscle], linestyle='-')
                        if muscle not in legend_handles:
                                legend_handles[muscle] = line

                total_muscle_moment = muscle_moments.sum(axis=1)
                line, = ax.plot(muscle_moments['time'], total_muscle_moment, label=f'{label_prefix} Total', color='black', linestyle='--')
                if f'{label_prefix} Total' not in legend_handles:
                        legend_handles[f'{label_prefix} Total'] = line

                # add space in the y axis to display metrics RMSE and R2
                y_min, y_max = ax.get_ylim()
                ax.set_ylim(y_min, y_max + abs(y_max - y_min)*0.5)
                rmse_moment = rmse(id_moments[f'{dof}_moment'], total_muscle_moment)
                r2_moment = rsquared(id_moments[f'{dof}_moment'], total_muscle_moment)

                rmse_percentage = (rmse_moment / (y_max - y_min)) * 100 if (y_max - y_min) != 0 else 0

                ax.text(0.05, 0.95, f'RMSE: {rmse_moment:.2f} (% {rmse_percentage:.2f})\nR2: {r2_moment:.2f}', transform=ax.transAxes, fontsize=6, verticalalignment='top')

        def plot_emg_vs_activations(ax, analysis: Analyse, emg, muscle_activations_so, muscle_activations_ceinms, dof, colors):
                emg_mapping = settings.EMG_muscle_mapping

                try:
                        muscles = analysis.muscles_per_coordinate(coord_name=dof)
                        muscles_for_coord = set(muscles[0]) if muscles and muscles[0] else set()
                except Exception:
                        muscles_for_coord = set()

                # Find EMG channels that map to muscles active in this DOF
                filtered_emg_mapping = {
                        channel: filtered
                        for channel, muscle_list in emg_mapping.items()
                        if (filtered := [m for m in muscle_list if m in muscles_for_coord])
                }

                # Plot relevant EMG envelope columns
                if emg is not None:
                    for emg_col, mapped_muscles in filtered_emg_mapping.items():
                        

                        
                        # Plot EMG col
                        emg_line, = ax.plot(emg['time'], emg[emg_col], label=f'EMG {emg_col}', color=colors['EMG'], alpha=0.6)

                        # Plot SO activations per muscle for this DOF
                        so_act_line = ax.plot(so_activations['time'], so_activations[mapped_muscles].mean(axis=1), label='SO Activations', color=colors['SO'], alpha=0.6, linestyle='-')  # placeholder for legend

                        # Plot CEINMS activations per muscle for this DOF
                        ceinms_act_line = ax.plot(ceinms_activations['time'], ceinms_activations[mapped_muscles].mean(axis=1), label='CEINMS Activations', color=colors['CEINMS'], alpha=0.6, linestyle='-')  # placeholder for legend

                # Add space in the y axis to display metrics RMSE and R2
                y_min, y_max = ax.get_ylim()
                ax.set_ylim(y_min, y_max + abs(y_max - y_min)*0.5)
                if emg is not None and (muscle_activations_so is not None or muscle_activations_ceinms is not None):
                    if muscle_activations_so is not None:
                        total_activation_so = muscle_activations_so[[m for m in muscles_for_coord if m in muscle_activations_so.columns]].mean(axis=1)
                        rmse_so = rmse(emg[emg_col], total_activation_so)
                        r2_so = rsquared(emg[emg_col], total_activation_so)
                        rmse_percentage_so = (rmse_so / (y_max - y_min)) * 100 if (y_max - y_min) != 0 else 0
                        ax.text(0.05, 0.90, f'SO Activations vs EMG\nRMSE: {rmse_so:.2f} (% {rmse_percentage_so:.2f})\nR2: {r2_so:.2f}', transform=ax.transAxes, fontsize=6, verticalalignment='top')

                    if muscle_activations_ceinms is not None:
                        total_activation_ceinms = muscle_activations_ceinms[[m for m in muscles_for_coord if m in muscle_activations_ceinms.columns]].mean(axis=1)
                        rmse_ceinms = rmse(emg[emg_col], total_activation_ceinms)
                        r2_ceinms = rsquared(emg[emg_col], total_activation_ceinms)
                        rmse_percentage_ceinms = (rmse_ceinms / (y_max - y_min)) * 100 if (y_max - y_min) != 0 else 0
                        ax.text(0.05, 0.80, f'CEINMS Activations vs EMG\nRMSE: {rmse_ceinms:.2f} (% {rmse_percentage_ceinms:.2f})\nR2: {r2_ceinms:.2f}', transform=ax.transAxes, fontsize=6, verticalalignment='top')
        
        dofs = settings.BatchSettings.dof_list
        n_rows = 5
        n_cols = len(dofs)
        colors = {'externalBiomech':'blue','SO': 'green', 'CEINMS': 'red', 'EMG': 'gray'}

        fig, ax = plt.subplots(nrows=int(n_rows), ncols=int(n_cols), figsize=(18, 8), constrained_layout=False)
        plt.suptitle('Summary of Results', y=1.02, fontsize=16)

        ik_angles = self.load_results('ik', time_normalise=True)
        id_moments = self.load_results('id', time_normalise=True)
        so_forces = self.load_results('so_muscle_forces', time_normalise=True)
        ceinms_forces = self.load_results('ceinms_muscle_forces', time_normalise=True)

        so_activations = self.load_results('so_activations', time_normalise=True)
        ceinms_activations = self.load_results('ceinms_activations', time_normalise=True)
        emg = self.load_results('emg', time_normalise=True)

        jra_so = self.load_results('jra_so', time_normalise=True)
        jra_ceinms = self.load_results('jra_ceinms', time_normalise=True)

        row_ylabels = ['Angle (°)', 'Moment - SO (Nm)', 'Moment - CEINMS (Nm)', 'EMG', 'JRA (N)']

        # Collect unique legend handles/labels for the muscle moment rows
        legend_handles = {}  # label -> handle, deduplicated
        jra_plotted = []
        for col_idx, dof in enumerate(dofs):
                col_name = f'{dof}_angle' if ik_angles is not None and f'{dof}_angle' in ik_angles.columns else dof

                # load moment arms for this DOF
                moment_arms = load_any_data_file(os.path.join(self.path, self.ma, f"_MuscleAnalysis_MomentArm_{dof}.sto"))
                moment_arms = time_normalise_df(moment_arms) 

                # calculate SO muscle moments for this DOF
                try:
                        muscle_moments_so = calculate_muscle_moments(so_forces, moment_arms) if so_forces is not None and moment_arms is not None else None
                except Exception as e:
                        print(f"Failed to calculate SO muscle moments for {dof}")
                        muscle_moments_so = None

                # calculate CEINMS muscle moments for this DOF
                try:
                        muscle_moments_ceinms = calculate_muscle_moments(ceinms_forces, moment_arms) if ceinms_forces is not None and moment_arms is not None else None
                except Exception as e:
                        print(f"Failed to calculate CEINMS muscle moments for {dof}")
                        muscle_moments_ceinms = None

                # plot IK angles
                if ik_angles is not None and col_name in ik_angles.columns:
                        ax[0, col_idx].plot(ik_angles['time'], ik_angles[col_name], color='blue')
                        ax[0, col_idx].set_title(dof, fontsize=8)
                
                # plot ID moments and muscle contributions to moments (SO)
                if id_moments is not None and f'{dof}_moment' in id_moments.columns and muscle_moments_so is not None:
                        plot_muscle_moments(ax[1, col_idx], id_moments, muscle_moments_so, dof, colors, label_prefix='SO')

                # plot ID moments and muscle contributions to moments (CEINMS)
                if id_moments is not None and f'{dof}_moment' in id_moments.columns and muscle_moments_ceinms is not None:
                        plot_muscle_moments(ax[2, col_idx], id_moments, muscle_moments_ceinms, dof, colors, label_prefix='CEINMS')

                # plot EMG vs SO excitations vs CEINMS excitations (with RMSE and R2 metrics)
                if emg is not None or so_activations is not None or ceinms_activations is not None:
                        plot_emg_vs_activations(ax[3, col_idx], self, emg, so_activations, ceinms_activations, dof, colors)

                # plot JRA reaction loads (SO vs CEINMS)
                jra_groups = settings.JCF_Groups
                joint = dof.split('_')[0]  # extract joint name from DOF (e.g. 'hip' from 'hip_flexion_r')
                if jra_so is not None and jra_ceinms is not None and not jra_plotted.__contains__(joint):
                        
                    current_group = jra_groups[joint]

                    x_so = jra_so[current_group[0]]
                    y_so = jra_so[current_group[1]]
                    z_so = jra_so[current_group[2]]
                    resultant_so = sum3d(jra_so, current_group)
                    
                    x_ceinms = jra_ceinms[current_group[0]]
                    y_ceinms = jra_ceinms[current_group[1]]
                    z_ceinms = jra_ceinms[current_group[2]]
                    resultant_ceinms = sum3d(jra_ceinms, current_group)

                    ax[4, col_idx].plot(jra_so['time'], resultant_so, label='SO Resultant', color=colors['externalBiomech'], linestyle='--')

                    ax[4, col_idx].plot(jra_ceinms['time'], resultant_ceinms, label='CEINMS Resultant', color=colors['CEINMS'], linestyle='--')
                    
                    if col_idx == 0:
                        ax[4, col_idx].set_ylabel("Reaction Load (N)")
                    
                    if col_idx == len(dofs) - 1:
                        ax[4, col_idx].legend(loc='upper right', fontsize=6)

                    ax[4, col_idx].set_xlabel("Time")

                    jra_plotted.append(joint)

        # y-labels on first column only
        for row_idx, ylabel in enumerate(row_ylabels):
                ax[row_idx, 0].set_ylabel(ylabel)

        # Single legend on the right side of the figure for muscle moment rows
        if legend_handles:
                fig.legend(
                        handles=list(legend_handles.values()),
                        labels=list(legend_handles.keys()),
                        loc='center right',
                        fontsize=6,
                        title='Muscles',
                        title_fontsize=7,
                        framealpha=0.9,
                )
                plt.subplots_adjust(right=0.85)

        mmfn(fig, n_rows, n_cols)

        # Re-apply right margin after tight_layout to keep legend in position
        if legend_handles:
                plt.subplots_adjust(right=0.85)

        # save figure
        save_path = os.path.join(self.path, 'summary_plot.png')
        plt.savefig(save_path, bbox_inches='tight')
        print(f'Summary plot saved to: {save_path}')

      
    # ceinms
    def create_ceinms_model(self):
        os.chdir(self.path)
        if os.path.exists(self.ceinms_uncalibrated_model) and not self.replace:
            self._log(f'CEINMS uncalibrated model already exists: {os.path.abspath(self.ceinms_uncalibrated_model)}')
            return
        # Stale calibrated model must be regenerated after uncalibrated is rebuilt
        if os.path.exists(self.ceinms_calibrated_model):
            try:
                os.remove(self.ceinms_calibrated_model)
                self._log(f'Removed stale calibrated model: {self.ceinms_calibrated_model}')
            except Exception:
                pass
        try:
            ceinms.create_ceinms_model(osimModelPath=self.model_dir,
                                   outputCEINMSModelPath=self.ceinms_uncalibrated_model)
            self._log(f'[Success] CEINMS uncalibrated model created: {os.path.abspath(self.ceinms_uncalibrated_model)}')
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS uncalibrated model: {e}')
    
    def _fix_emg_timestamps(self, emg_file: str) -> str:
        """
        If the EMG file has wrong timestamps (common C3D export bug), reconstruct
        the time column using BatchSettings.emg_sampling_freq and the IK start time.
        Returns the (possibly corrected) filename to use.
        """
        emg_sampling_freq = getattr(settings.BatchSettings, 'emg_sampling_freq', None)
        if not emg_sampling_freq:
            return emg_file

        emg_path = os.path.join(self.path, emg_file)
        if not os.path.exists(emg_path):
            self._log(f'[Warning] EMG file not found: {emg_path}  '
                      f'-- run C3D export first (enable_c3d_export = True)', terminal=True)
            return emg_file

        try:
            df = load_any_data_file(emg_path)
            if df is None or 'time' not in df.columns or len(df) < 2:
                return emg_file

            n = len(df)
            actual_dt = (df['time'].iloc[-1] - df['time'].iloc[0]) / (n - 1)
            expected_dt = 1.0 / emg_sampling_freq

            self._log(f'EMG timestamps: n={n}, dt={actual_dt:.6f}s '
                      f'(expected {expected_dt:.6f}s at {emg_sampling_freq} Hz), '
                      f'time {df["time"].iloc[0]:.4f}..{df["time"].iloc[-1]:.4f}s', terminal=True)

            # If time increment is off by more than 20%, fix it
            if abs(actual_dt - expected_dt) / expected_dt < 0.20:
                return emg_file  # timestamps already correct

            # Reconstruct: start at IK start time, step at 1/emg_sampling_freq
            try:
                start_t = float(self.time_range[0]) if self.time_range else 0.0
            except Exception:
                start_t = 0.0

            df = df.copy()
            df['time'] = start_t + np.arange(n) / emg_sampling_freq
            self._log(f'[Info] Fixed EMG timestamps -> {df["time"].iloc[0]:.4f}..{df["time"].iloc[-1]:.4f}s', terminal=True)

            # Overwrite the source file in-place — no extra emg_ceinms.mot created
            emg_normalise.write_sto_file(df, emg_path)
            return emg_file
        except Exception as e:
            self._log(f'[Warning] Could not fix EMG timestamps: {e}', terminal=True)
            return emg_file

    def create_ceinms_input_data(self):
        os.chdir(self.path)
        # Remove legacy temp file from older pipeline versions
        legacy_tmp = os.path.join(self.path, 'emg_ceinms.mot')
        if os.path.exists(legacy_tmp):
            try:
                os.remove(legacy_tmp)
                self._log('[Info] Removed legacy emg_ceinms.mot')
            except Exception:
                pass
        # Always use the best available EMG — normalised > filtered > raw.
        # This bypasses whatever trial_settings.xml says (which may be stale).
        for candidate in ('emg_filtered_normalised.mot', 'emg_filtered.mot', self.emg):
            if os.path.exists(os.path.join(self.path, candidate)):
                excitations = candidate
                break
        else:
            excitations = self.emg  # absolute fallback

        self._log(f"CEINMS excitations: selected '{excitations}' "
                  f"(exists={os.path.exists(os.path.join(self.path, excitations))}), "
                  f"time_range={self.time_range}", terminal=True)

        # Fix EMG timestamps if the C3D export produced wrong time values
        excitations = self._fix_emg_timestamps(excitations)

        # Cap startStopTime to the actual EMG data range to avoid
        # "Input data does not cover CEINMS time range" warnings
        try:
            _emg_df = load_any_data_file(os.path.join(self.path, excitations))
            if _emg_df is not None and 'time' in _emg_df.columns and len(_emg_df) > 0:
                _emg_start = float(_emg_df['time'].iloc[0])
                _emg_end = float(_emg_df['time'].iloc[-1])
                _tr = self.time_range if isinstance(self.time_range, (list, tuple)) else [0.0, 1e9]
                input_time_range = [max(float(_tr[0]), _emg_start), min(float(_tr[1]), _emg_end)]
            else:
                input_time_range = self.time_range
        except Exception:
            input_time_range = self.time_range

        try:
            ceinms.create_input_data(MAFolder=self.ma,
                                     excitationsFile=excitations,
                                     motionFile=self.ik,
                                     externalTorquesFile=self.id,
                                     externalLoadsFile=self.setup_grf,
                                     startStopTime=input_time_range)
            self._log(f'[Success] CEINMS input data created: {os.path.abspath(self.ceinms_input_data)}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS input data: {e}', terminal=True)
    
    def create_ceinms_calibration_cfg(self, calibration_trial_names=None):
        """
        Create ceinms_cfg_calibration.xml for CEINMS calibration.
        """
        
        os.chdir(self.path)
        inputPaths = []
        for trial_name in calibration_trial_names:
            filepath = os.path.join(self.parentdir, trial_name, settings.Inputs().ceinms_input_data)
            inputPaths.append(os.path.relpath(filepath, self.parentdir))
        
        ceinms.create_calibrationCfg(osimModelPath=self.model_dir,
                                     inputPaths=inputPaths,
                                     outputPath=self.ceinms_calibration_cfg)

    def create_excitation_generator(self):
        import traceback as _tb
        os.chdir(self.path)
        _abs_eg = os.path.abspath(self.ceinms_excitation_generator)
        self._log(f'CEINMS excitation generator path: {_abs_eg} (exists={os.path.exists(_abs_eg)})', terminal=True)
        if os.path.exists(_abs_eg) and not self.replace:
            self._log(f'CEINMS excitation generator already exists: {_abs_eg}', terminal=True)
            return
        
        try:
            ceinms.create_excitation_generator(osim_model_path=self.model_dir,
                                               emg_path=self.ceinms_excitations,
                                               save_path=self.ceinms_excitation_generator
            )
            self._log(f'[Success] CEINMS excitation generator created: {_abs_eg}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS excitation generator: {e}\n{_tb.format_exc()}', terminal=True)
                
    def create_ceinms_cfg_from_excitation_generator(self):
        """
        Create ceinms_cfg_optimise.xml based on excitationGenerator.xml
        
        Args:
            excitation_file: Path to excitationGenerator.xml
            output_file: Path for output ceinms_cfg_optimise.xml
        """
        os.chdir(self.path)
        excitation_file = self.ceinms_excitation_generator
        output_file = self.ceinms_exe_cfg
        
        # Parse the excitation generator XML
        tree = ET.parse(excitation_file)
        root = tree.getroot()
        
        # Lists to store muscle names
        synth_mtus = []
        adjust_mtus = []
        
        # Find all excitation elements
        mapping = root.find('mapping')
        if mapping is not None:
            for excitation in mapping.findall('excitation'):
                muscle_id = excitation.get('id')
                
                # Check if excitation has input elements (non-empty)
                inputs = excitation.findall('input')
                if inputs and len(inputs) > 0:
                    # Has EMG input - add to adjustMTUs
                    adjust_mtus.append(muscle_id)
                else:
                    # No EMG input - add to synthMTUs
                    synth_mtus.append(muscle_id)
        
        # Sort the lists for consistent output
        synth_mtus.sort()
        adjust_mtus.sort()
        
        # Create the XML structure
        execution = ET.Element('execution')
        
        # Add XML declaration attributes
        execution.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        
        nms_model = ET.SubElement(execution, 'NMSmodel')
        type_elem = ET.SubElement(nms_model, 'type')
        hybrid = ET.SubElement(type_elem, 'hybrid')
        
        # Add hybrid parameters
        ET.SubElement(hybrid, 'alpha').text = '1'
        ET.SubElement(hybrid, 'beta').text = '4'
        ET.SubElement(hybrid, 'gamma').text = '120'
        
        # Add DOF set (you may need to adjust this based on your model)
        dof_set = ET.SubElement(hybrid, 'dofSet')
        dof_set.text = settings.CEINMSSettings.dof_set
        
        # Add synthMTUs
        synth_mtus_elem = ET.SubElement(hybrid, 'synthMTUs')
        synth_mtus_elem.text = ' '.join(synth_mtus)
        
        # Add adjustMTUs
        adjust_mtus_elem = ET.SubElement(hybrid, 'adjustMTUs')
        adjust_mtus_elem.text = ' '.join(adjust_mtus)
        
        # Add algorithm section
        algorithm = ET.SubElement(hybrid, 'algorithm')
        sim_annealing = ET.SubElement(algorithm, 'simulatedAnnealing')
        ET.SubElement(sim_annealing, 'noEpsilon').text = '4'
        ET.SubElement(sim_annealing, 'rt').text = '0.3'
        ET.SubElement(sim_annealing, 'T').text = '20000'
        ET.SubElement(sim_annealing, 'NS').text = '15'
        ET.SubElement(sim_annealing, 'NT').text = '5'
        ET.SubElement(sim_annealing, 'epsilon').text = '0.001'
        ET.SubElement(sim_annealing, 'maxNoEval').text = '200000'
        
        # Add tendon section
        tendon = ET.SubElement(nms_model, 'tendon')
        equilibrium = ET.SubElement(tendon, 'equilibriumElastic')
        ET.SubElement(equilibrium, 'tolerance').text = '1e-09'
        
        # Add activation section
        activation = ET.SubElement(nms_model, 'activation')
        ET.SubElement(activation, 'exponential')
        
        # Create tree and write to file
        tree = ET.ElementTree(execution)
        save_pretty_xml(tree, output_file)
        
        print(f"Created {output_file}")
        print(f"synthMTUs: {len(synth_mtus)} muscles")
        print(f"adjustMTUs: {len(adjust_mtus)} muscles")
    
    def create_ceinms_calibration_setup(self):
        os.chdir(self.path)
        ceinms.create_calibrationSetupXML(uncalibratedCEINMSModelPath=self.ceinms_uncalibrated_model,
                                           excitationGeneratorFile=self.ceinms_excitation_generator,
                                           calibrationCfgPath=self.ceinms_calibration_cfg,
                                           outputSubjectFile=self.ceinms_calibrated_model,
                                           outputDirectory=self.ceinms_calibration_dir,
                                           setupXMLPath=self.ceinms_calibration_setup)

    def create_ceinms_optimise_setup(self):
        os.chdir(self.path)
        
        if os.path.exists(self.ceinms_optimise_setup) and not self.replace:
            self._log(f'CEINMS optimisation setup already exists: {os.path.abspath(self.ceinms_optimise_setup)}', terminal=True)
            return
        
        ceinms.create_optimise_setupFiles(ceinmsModelPath=self.ceinms_calibrated_model,
                                          inputDataFile=self.ceinms_input_data,
                                          calibrationCfgPath=self.ceinms_optimise_cfg,
                                          excitationGeneratorFilePath=self.ceinms_excitation_generator,
                                          outputDirectory=self.ceinms_optimisation_dir,
                                          setupXMLPath=self.ceinms_optimise_setup,
                                          templateCfgXMLPath=os.path.join(self.setup_dir, self.ceinms_optimise_cfg))

    def create_ceinms_exe_setup(self):

        root = ET.Element('ceinms')
        ET.SubElement(root, 'subjectFile').text = os.path.relpath(self.ceinms_calibrated_model, self.path)
        ET.SubElement(root, 'inputDataFile').text = os.path.relpath(self.ceinms_input_data, self.path)
        ET.SubElement(root, 'executionFile').text = os.path.relpath(self.ceinms_exe_cfg, self.path)
        ET.SubElement(root, 'excitationGeneratorFile').text = os.path.relpath(self.ceinms_excitation_generator, self.path)
        ET.SubElement(root, 'outputDirectory').text = os.path.relpath(self.ceinms_exe_dir, self.path)
        # Create tree and write to file
        tree = ET.ElementTree(root)
        save_pretty_xml(tree, self.ceinms_exe_setup)
        print(f"Created {os.path.abspath(self.ceinms_exe_setup)}")

    def create_ceinms_exe_cfg(self):
        os.chdir(self.path)
        
        try:
            dofSet = ' '.join(settings.BatchSettings.dof_list)
            ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_calibrated_model,
                                 alpha=self.alpha,
                                 beta=self.beta,
                                    gamma=self.gamma,
                                    dofSet=dofSet,
                                    excitationGeneratorFilePath=self.ceinms_excitation_generator,
                                    outputPath=self.ceinms_exe_cfg)
            self._log(f'[Success] CEINMS exe cfg created: {os.path.abspath(self.ceinms_exe_cfg)}')
        except Exception as e:
            self._log(f'[Error] Failed to create CEINMS executable configuration: {e}', terminal=True)

    def get_muscle_excitation_mapping(self, muscle_name):
        """
        Check if a muscle is present in the excitation mapping of the excitation generator XML.
        
        Args:
            muscle_name (str): Name of the muscle to check.
        """
        tree = ET.parse(self.ceinms_excitation_generator)
        root = tree.getroot()
        
        mapping = root.find('mapping')
        if mapping is not None:
            for excitation in mapping.findall('excitation'):
                if excitation.get('id') == muscle_name:
                    inputs = excitation.findall('input')
                    if inputs:
                        return [inp.text for inp in inputs]
        return []

    # --- run ceinms analyses
    def run_ceinms_calibration(self):
        """
        Run the full CEINMS calibration pipeline for this session.

        Steps (each is idempotent — skipped if output exists and replace=False):
          1. create_ceinms_model        — build uncalibrated XML from .osim
          2. create_excitation_generator — EMG→muscle mapping XML
          3. create_ceinms_input_data   — motion/force data for this trial
          4. create_ceinms_calibration_cfg — collects all sibling trial inputs
          5. create_ceinms_calibration_setup
          6. run calibration executable
        """
        os.chdir(self.path)

        # -- Prerequisites --
        self._log("CEINMS calibration: building prerequisites...")
        self.create_ceinms_model()
        if not os.path.exists(self.ceinms_uncalibrated_model):
            self._log("[Error] CEINMS calibration aborted: uncalibrated model could not be created.", terminal=True)
            return
        self.create_excitation_generator()
        self.create_ceinms_input_data()

        # Collect all sibling trial directories that have input data
        allowed = getattr(settings.CEINMSSettings, 'calibration_trial_names', None)
        calib_trials = []
        input_data_name = settings.Inputs().ceinms_input_data
        for entry in sorted(os.listdir(self.parentdir)):
            if allowed and entry not in allowed:
                continue
            candidate = os.path.join(self.parentdir, entry, input_data_name)
            if os.path.exists(candidate):
                calib_trials.append(entry)
        if not calib_trials:
            self._log("[Warning] No CEINMS input data found — calibrating with current trial only.")
            calib_trials = [self.trial]

        self._log(f"CEINMS calibration trials: {calib_trials}")
        self.create_ceinms_calibration_cfg(calibration_trial_names=calib_trials)
        self.create_ceinms_calibration_setup()

        # -- Run calibration --
        start_time = time.time()
        os.chdir(self.path)

        if os.path.exists(self.ceinms_uncalibrated_model):
            ceinms.plot_ceinms_model_parameters(self.ceinms_uncalibrated_model)

        calibrationSetupPath = os.path.abspath(self.ceinms_calibration_setup)

        edit_xml_tag_value(calibrationSetupPath, 'outputDirectory', 'calibrationOutput')
        ceinms.calibrate(setupXML_path=calibrationSetupPath)

        # update calibrated model from setupXML
        setupXML = ET.parse(calibrationSetupPath).getroot()
        self.ceinms_calibrated_model = os.path.join(os.path.dirname(calibrationSetupPath), setupXML.find('outputSubjectFile').text)
        self._to_xml()

        # if date modified of calibrated model is after start time, assume success
        os.chdir(self.path)
        if not os.path.exists(self.ceinms_calibrated_model):
            self._log(f'[ERROR] CEINMS calibration failed: calibrated model not found at {self.ceinms_calibrated_model}. Check calibrationOutput/out.txt for details.', terminal=True)
            raise FileNotFoundError(f'Calibrated model not produced: {self.ceinms_calibrated_model}')
        mod_time = os.path.getmtime(self.ceinms_calibrated_model)
        if mod_time >= start_time:
            self._log(f'CEINMS calibration completed successfully in {mod_time - start_time:.2f} seconds.')
            ceinms.plot_ceinms_model_parameters(self.ceinms_calibrated_model)
            
            # plot moments vs ceinms results
            try:
                ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
                ceinms.plot_moments_calibration_results(momentResultsCSV=ceinmsTorquesFile)
                self._log(f'[Success] Plotted moments vs CEINMS results.')
            except:
                self._log(f'[ERROR] Could not plot moments vs CEINMS results.')
            
            # plot emg vs ceinms excitations using uncalibrated model as reference
            try:
                ceinms.plot_compare_ceinms_models(uncalibratedModelPath=self.ceinms_uncalibrated_model,calibratedModelPath=self.ceinms_calibrated_model)
                self._log(f'[Success] Plotted EMG vs CEINMS results for calibrated model: {self.ceinms_calibrated_model}')
            except:
                self._log(f'[ERROR] Could not plot EMG vs CEINMS results for calibrated model: {self.ceinms_calibrated_model}')
        else:
            self._log(f'[WARNING] CEINMS calibration may have failed: calibrated model not updated.')
            
    def run_ceinms_exe(self):
        os.chdir(self.path)
        self.load_settings(settingsXML=self.settingsXML)

        # Ensure per-trial prerequisites exist
        self.create_ceinms_input_data()
        if not os.path.exists(self.ceinms_exe_cfg) or self.replace:
            self.create_ceinms_exe_cfg()
        if not os.path.exists(self.ceinms_exe_setup):
            self.create_ceinms_exe_setup()

        if not os.path.exists(self.ceinms_exe_cfg):
            self._log(f"[Error] CEINMS execution aborted: {self.ceinms_exe_cfg} not found "
                      f"(run calibration first to produce a calibrated model).", terminal=True)
            return
        if not os.path.exists(self.ceinms_exe_setup):
            self._log(f"[Error] CEINMS execution aborted: {self.ceinms_exe_setup} not found.", terminal=True)
            return

        cfg = ET.parse(self.ceinms_exe_cfg).getroot()
        setup = ET.parse(self.ceinms_exe_setup).getroot()

        setup.find('outputDirectory').text = f'{self.ceinms_exe_dir}_a{self.alpha}_b{self.beta}_g{self.gamma}'

        save_pretty_xml(ET.ElementTree(setup), self.ceinms_exe_setup)

        # replace alpha, beta, gamma in cfg from settings file
        ceinms.replace_ceinms_cfg_parameter(cfgXML_path=self.ceinms_exe_cfg,parameter_name='alpha',new_value=str(self.alpha))
        ceinms.replace_ceinms_cfg_parameter(cfgXML_path=self.ceinms_exe_cfg,parameter_name='beta',new_value=str(self.beta))
        ceinms.replace_ceinms_cfg_parameter(cfgXML_path=self.ceinms_exe_cfg,parameter_name='gamma',new_value=str(self.gamma))

        # run ceinms executable
        try:
            ceinms.executable(setupXML_path=os.path.abspath(self.ceinms_exe_setup))
            self._log(f'CEINMS executable run completed for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during CEINMS executable run: {e}')

        # update jra ceinms forces path from setup output directory
        self.update_trial_attribute('jra_forces_ceinms', os.path.join(setup.find('outputDirectory').text, 'MuscleForces.sto'))

        # check if ceinms forces file exists before trying to add so columns
        if not os.path.exists(self.jra_forces_ceinms):
            self._log(f'[Error] CEINMS forces file not found: {self.jra_forces_ceinms}')
            return

        # add so columns to ceinms forces
        try:
            self.add_so_columns_to_ceinms_results()
            self._log(f'Added SO columns to CEINMS forces for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during adding SO columns to CEINMS forces: {e}')

    def run_ceinms_optimise(self):
        
        os.chdir(self.path)
        setupAbsPath = os.path.abspath(self.ceinms_optimise_setup)
        ceinms.optimise(setupXML_path=setupAbsPath)

        try:    
            adjustedEMG_path = os.path.join(self.ceinms_optimisation_dir, 'AdjustedEmgs.sto')
            torqueCEINMS_path = os.path.join(self.ceinms_optimisation_dir, 'Torques.sto')
            ceinms.plot_experimental_vs_ceinms(emgFile=self.emg_normalised,
                                               ceinmsExcitationsFile=adjustedEMG_path,
                                               excitationGeneratorFile=self.ceinms_excitation_generator,
                                                externalMomentsFile=self.id,
                                                ceinmsTorquesFile=torqueCEINMS_path)
            self._log(f'Plotted Experimental vs CEINMS results {self.path}')
        except:
            self._log(f'Could not plot EMG vs CEINMS results {self.path}')
    
    def run_ceinms_exe_loop(self):        
        
        os.chdir(self.path)
        if not os.path.exists(self.ceinms_exe_setup):
            self.create_ceinms_exe_setup()
        
        if not os.path.exists(self.ceinms_exe_cfg):
            ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_calibrated_model, alpha=self.alpha, beta=self.beta, gamma=self.gamma, dofSet=' '.join(self.DofSet),excitationGeneratorFilePath=self.ceinms_excitation_generator, outputPath=self.ceinms_exe_cfg)
        
        try:
            self.load_settings(settingsXML=self.settingsXML)
            alpha_values = [int(x) for x in self.alphas.split(' ')]
            beta_values = [int(x) for x in self.betas.split(' ')]
            gamma_values = [int(x) for x in self.gammas.split(' ')]

            # change output directory in setup to match base name
            setup = ET.parse(self.ceinms_exe_setup).getroot()
            setup.find('outputDirectory').text = self.ceinms_exe_dir
            
            # run ceinms executable loop
            ceinms.executable_loop(setupXML_path=os.path.abspath(self.ceinms_exe_setup), cfgXML_path=os.path.abspath(self.ceinms_exe_cfg), alphas =alpha_values, betas=beta_values, gammas=gamma_values)

        except Exception as e:
                self._log(f'[Error] during CEINMS executable loop: {e}')

    def check_best_ceinms_results(self):
        ''' loop through ceinms exe results and find best alpha, beta, gamma based on RMS error for joint moments and EMG vs CEINMS excitations '''
        os.chdir(self.path)

        self.load_settings(settingsXML=self.settingsXML)
        best_params_csv = os.path.join(self.path, 'best_ceinms_parameters.csv')

        if os.path.exists(best_params_csv) and not self.replace:
            self._log(f'Loading existing best CEINMS parameters from {best_params_csv}')
            best_params_df = pd.read_csv(best_params_csv)
        else:
            best_params_df = pd.DataFrame(columns=['alpha', 'beta', 'gamma', 'moment_rms_error', 'emg_rms_error'])
            best_params_df.to_csv(best_params_csv, index=False)
            self._log(f'Saved best CEINMS parameters to {best_params_csv}')

    def add_so_columns_to_ceinms_results(self):

        try:
            so_forces = load_any_data_file(self.jra_forces)
            ceinms_forces = load_any_data_file(self.jra_forces_ceinms)
        except Exception as e:
            self._log(f'[Error] loading SO or CEINMS forces for adding columns: {e}')
            return

        # Find columns in SO forces that are not in CEINMS forces
        missing_columns = [col for col in so_forces.columns if col not in ceinms_forces.columns]

        # Create new dataframe starting with CEINMS forces
        updated_forces = ceinms_forces.copy()

        # Add missing columns from SO forces
        for col in missing_columns:
            updated_forces[col] = so_forces[col]

        # Save to new .sto file
        write_sto_file(updated_forces, self.jra_forces_ceinms)
        self._log(f'[Success] Added SO columns to CEINMS forces for trial: {self.trial}')
        print(f"Updated forces saved to: {self.jra_forces_ceinms}")
        print(f"Added {len(missing_columns)} columns from SO forces")

    #--- Plot ceinms
    def plot_ceinms_calibration_results(self):

        try:
            ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
            ceinms.plot_moments_calibration_results(momentResultsCSV=ceinmsTorquesFile)
            self._log(f'[Success] Plotted CEINMS calibration results for trial: {self.trial}')
        except Exception as e:
            self._log(f'[Error] during plotting CEINMS calibration results: {e}')

    def plot_ceinms_vs_so_muscle_moments(self):
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go

        ik_columns = ['hip_flexion_r', 'hip_adduction_r', 'hip_rotation_r', 'knee_angle_r', 'ankle_angle_r']
        id_columns = ['hip_flexion_r_moment', 'hip_adduction_r_moment', 'hip_rotation_r_moment', 'knee_angle_r_moment', 'ankle_angle_r_moment']

        id = load_any_data_file(os.path.join(self.path, self.id))
        so_forces = load_any_data_file(os.path.join(self.path, self.so_forces))
        ceinms_forces = load_any_data_file(os.path.join(self.path, self.jra_forces_ceinms))

        fig, ax = plt.subplots(nrows=len(ik_columns), ncols=2, figsize=(28, 16))
        fontsize = 25

        fig_int = make_subplots(rows=len(ik_columns), cols=2, shared_xaxes=True,
                                subplot_titles=[f"{dof} - SO" if i % 2 == 0 else f"{dof} - CEINMS"
                                                for dof in ik_columns for i in range(2)])

        for count, dof in enumerate(ik_columns):
            ma = load_any_data_file(os.path.join(self.path, self.ma, f'_MuscleAnalysis_MomentArm_{dof}.sto'))

            muscle_list = [col for col in so_forces.columns if col != 'time']
            muscles = openSim.find_non_zero_mom_arm_muscles(ma, muscle_list)
            print(f"Non-zero moment arm muscles for {dof}: {muscles}")

            colors = plt.cm.tab20(np.linspace(0, 1, max(len(muscles), 1)))

            if count == 0:
                ax[count, 0].set_title('SO', fontsize=fontsize)
                ax[count, 1].set_title('CEINMS', fontsize=fontsize)

            # Plot ID (static)
            ax[count, 0].plot(id['time'], id[f'{dof}_moment'], label='ID', color='blue')
            ax[count, 0].set_ylabel(f'{dof} (Nm)', fontsize=fontsize)
            ax[count, 0].tick_params(labelsize=fontsize)

            ax[count, 1].plot(id['time'], id[f'{dof}_moment'], label='ID', color='blue')
            ax[count, 1].tick_params(labelsize=fontsize)

            
            # Plot muscle moments SO (static)
            for i, m in enumerate(muscles):
                ax[count, 0].plot(so_forces['time'], so_forces[m] * ma[m],
                                label=m, color=colors[i], linestyle='--')

            sum_moments_so = so_forces[muscles].mul(ma[muscles], axis=0).sum(axis=1)
            ax[count, 0].fill_between(so_forces['time'], 0, sum_moments_so, color='grey', alpha=0.2, label='Sum')

            # Plot muscle moments CEINMS (static)
            for i, m in enumerate(muscles):
                ax[count, 1].plot(ceinms_forces['time'], ceinms_forces[m] * ma[m],
                                label=m, color=colors[i], linestyle='--')
            
            sum_moments_ce = ceinms_forces[muscles].mul(ma[muscles], axis=0).sum(axis=1)
            ax[count, 1].fill_between(ceinms_forces['time'], 0, sum_moments_ce, color='grey', alpha=0.2, label='Sum')

            # add RMSE and R2 values between ID and SO, and ID and CEINMS
            rmse_so = rmse(id[f'{dof}_moment'], sum_moments_so)
            r2_so = rsquared(id[f'{dof}_moment'], sum_moments_so)
            rmse_ce = rmse(id[f'{dof}_moment'], sum_moments_ce)
            r2_ce = rsquared(id[f'{dof}_moment'], sum_moments_ce)
            textstr_so = f'RMSE={rmse_so:.2f} Nm\nR²={r2_so:.3f}'
            textstr_ce = f'RMSE={rmse_ce:.2f} Nm\nR²={r2_ce:.3f}'
            ax[count, 0].text(0.95, 0.95, textstr_so, transform=ax[count, 0].transAxes, fontsize=fontsize,
                            verticalalignment='top', horizontalalignment='right',
                            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            ax[count, 1].text(0.95, 0.95, textstr_ce, transform=ax[count, 1].transAxes, fontsize=fontsize,
                            verticalalignment='top', horizontalalignment='right',
                            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))    


        plt.tight_layout()
        save_path = os.path.join(self.path, 'muscle_moments.png')
        plt.savefig(save_path)
        print(f"Muscle moments comparison plot saved: {save_path}")

        convert_to_interactive_fig(fig, html_path=os.path.join(self.path, 'muscle_moments_interactive.html'))

    #--- git integration
    def git_status(self):
        '''Check git status of the trial and subject directories
        
        Outputs uncommitted changes in trial and subject directories to log.
        
        Returns a dictionary with boolean values indicating if trial and subject directories are clean (no uncommitted changes).

            git_status() -> {'trial_dir': bool, 'subject_dir': bool}

            True: No uncommitted changes in the directory
            False: Uncommitted changes present in the directory

        '''
        os.chdir(self.path)

        isClean = {'trial_dir': True, 'subject_dir': True}
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], check=True, stdout=subprocess.PIPE, text=False, cwd=os.getcwd())

            if result.stdout:
                self._log(f'[Git Status] Uncommitted changes in trial directory: {self.path}')
                isClean['trial_dir'] = False
            else:
                self._log(f'[Git Status] No uncommitted changes in trial directory: {self.path}')
                isClean['trial_dir'] = True
            subject_path = updir(self.path, levels=2)
            result_subject = subprocess.run(['git', 'status', '--porcelain'], check=True, stdout=subprocess.PIPE, text=False, cwd=subject_path)
            if result_subject.stdout:
                self._log(f'[Git Status] Uncommitted changes in subject directory: {subject_path}')
                isClean['subject_dir'] = False
            else:
                self._log(f'[Git Status] No uncommitted changes in subject directory: {subject_path}', terminal=True)
                isClean['subject_dir'] = True
        except subprocess.CalledProcessError as e:
            self._log(f'[Error] Failed to check git status: {e}')

        return isClean
    
    def push_trial_results_to_git(self):
        """Push trial results to git after completion"""
        os.chdir(self.path)
        try:
          
            # Add all changes in the trial directory
            subprocess.run(['git', 'add', self.path], check=True, cwd=os.getcwd())

            # Add changes to model directory if it exists
            if os.path.exists(os.path.dirname(self.model_dir)):
                subprocess.run(['git', 'add', os.path.dirname(self.model_dir)], check=True, cwd=os.getcwd())

            # Commit with descriptive message
            commit_message = f"[RESULT] {self.subject}/{self.trial}"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError as e:
            self._log(f'[Warning] Failed to commit to git: {e}')

        try:
            subprocess.run(['git', 'push'], check=True, cwd=os.getcwd())
            self._log(f'[Success] Results pushed to git for: {self.subject} / {self.trial}')
        except subprocess.CalledProcessError:
            try:
                # set upstream for current branch then push
                branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=os.getcwd(), text=True).strip()
                subprocess.run(['git', 'push', '--set-upstream', 'origin', branch], check=True, cwd=os.getcwd())
                self._log(f'[Success] Results pushed to git for: {self.subject} / {self.trial}')
            except subprocess.CalledProcessError as e:
                self._log(f'[Warning] Failed to push to git: {e}')
            except Exception as e:
                self._log(f'[Warning] Git operation failed: {e}')

    def push_subject_results_to_git(self):
        """Push subject results to git after completion"""
        os.chdir(self.parentdir)
        subject_path = updir(self.path, levels=2)  # Move up to subject directory
        subject_model_dir = os.path.join(MODELS_DIR, self.subject)

        status = self.git_status()
        if status['subject_dir']:
            print(f'[Git] No uncommitted changes in trial or subject directories for {self.subject}. Skipping git push.')
            time.sleep(2)  
            return
        
        try:
            # Add all changes in the subject directory
            subprocess.run(['git', 'add', subject_path], check=True, cwd=os.getcwd())
            subprocess.run(['git', 'add', subject_model_dir], check=True, cwd=os.getcwd())

            # Commit with descriptive message
            commit_message = f"[RESULT] {self.subject}"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError as e:
            self._log(f'[Warning] Failed to commit to git: {e}')

        try:
            subprocess.run(['git', 'push'], check=True, cwd=os.getcwd())
            self._log(f'[Success] Results pushed to git for subject: {self.subject}')
        except subprocess.CalledProcessError:
            try:
                # set upstream for current branch then push
                branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=os.getcwd(), text=True).strip()
                subprocess.run(['git', 'push', '--set-upstream', 'origin', branch], check=True, cwd=os.getcwd())
                self._log(f'[Success] Results pushed to git for subject: {self.subject}')
            except subprocess.CalledProcessError as e:
                self._log(f'[Warning] Failed to push to git: {e}')
            except Exception as e:
                self._log(f'[Warning] Git operation failed: {e}')

class Summarize():
    '''
    Build a master long-format CSV of all available trial results.

    Walks simulations/<subject>/<session>/<trial>/ and loads every result file
    that exists (IK, ID, SO forces/activations, CEINMS forces/activations).
    All time series are time-normalised to N_POINTS (0–100 %) via interpolation.

    Output columns: subject, session, trial, data_type, variable, time_pct, value

    Usage:
        s = Summarize()
        df = s.create_master_df()               # processes everything
        df = s.create_master_df(subjects=['Athlete_03'], sessions=['25_03_31'])
    '''

    N_POINTS = 101  # 0 % … 100 %

    inputs = settings.Inputs()
    # result file tags → attribute name on Analyse
    _FILE_TAGS = {
        'IK':                 inputs.ik,
        'ID':                 inputs.id,
        'SO_forces':          inputs.so_forces,
        'SO_activations':     inputs.so_activations,
        'CEINMS_forces':      inputs.ceinms_muscle_forces,
        'CEINMS_activations': inputs.ceinms_activations
    }

    def __init__(self):
        self._rows = []

        self.subjects = settings.session_list
        self.sessions = settings.session_list
        self.trials = settings.trial_list

        self.summary_df = pd.DataFrame(columns=['subject', 'session', 'trial', 'time'])
    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def add_trial(self, trial):
        """Update the master DataFrame with all available data from a trial."""
        for tag, attr in self._FILE_TAGS.items():
            if attr is None:
                continue  # skip derived data types for now
            file_path = getattr(trial, attr, None)
            if file_path and os.path.exists(file_path):
                try:
                    data = load_any_data_file(file_path)
                    time = data['time']
                    for col in data.columns:
                        if col == 'time':
                            continue
                        values = data[col]
                        time_pct = np.linspace(0, 100, len(time))
                        for t_pct, val in zip(time_pct, values):
                            self._rows.append({
                                'subject': trial.subject,
                                'session': trial.session,
                                'trial': trial.trial,
                                'data_type': tag,
                                'variable': col,
                                'time_pct': t_pct,
                                'value': val
                            })
                except Exception as e:
                    self._log(f'[Warning] Failed to process {tag} for {trial.path}: {e}')

    def create_master_df(self, filename='master_summary.csv'):
        """
        Walk the simulations directory tree and process every trial that has a
        trial_settings.xml.  Optional keyword filters (lists of strings) restrict
        which subjects / sessions / trial names are included.

        Returns the resulting DataFrame and saves it to results/<filename>.
        """
        pattern = os.path.join(SIMULATIONS_DIR, '**', 'trial_settings.xml')
        settings_files = glob(pattern, recursive=True)

        if not settings_files:
            print(f'[Warning] No trial_settings.xml files found under {SIMULATIONS_DIR}')
            return None

        discovered = skipped = 0
        for settings_path in sorted(settings_files):
            parts = os.path.normpath(settings_path).split(os.sep)
            # expected: …/simulations/<subject>/<session>/<trial>/trial_settings.xml
            try:
                idx = parts.index(os.path.basename(SIMULATIONS_DIR))
                subject_name = parts[idx + 1]
                session_name = parts[idx + 2]
                trial_name   = parts[idx + 3]
            except (ValueError, IndexError):
                skipped += 1
                continue

            if self.subjects and subject_name not in self.subjects:
                skipped += 1
                continue
            if self.sessions and session_name not in self.sessions:
                skipped += 1
                continue
            if self.trials and trial_name not in self.trials:
                skipped += 1
                continue

            trial_dir = os.path.dirname(settings_path)
            print(f'Processing: {subject_name}/{session_name}/{trial_name}')
            try:
                t = Analyse(trial_dir)
                self.add_trial(t)
                discovered += 1
            except Exception as e:
                self._log(f'[Warning] Skipping {trial_dir}: {e}')
                skipped += 1

        print(f'\nDone — {discovered} trials processed, {skipped} skipped.')
        return self.save(filename)

    def save(self, filename='master_summary.csv'):
        """Write accumulated rows to a long-format CSV and return the DataFrame."""
        if not self._rows:
            self._log('No data accumulated — nothing saved.')
            return pd.DataFrame()
        df = pd.DataFrame(self._rows)
        output_path = os.path.join(RESULTS_DIR, filename)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        df.to_csv(output_path, index=False)
        self._log(f'Master summary saved: {output_path} ({len(df):,} rows)', terminal=True)
        return df

    # backward-compat aliases
    def add_trial_data_to_master_df(self, trial): self.add_trial(trial)
    def add_trial_to_summary(self, trial):         self.add_trial(trial)
    def save_master_df(self, filename='master_summary.csv'): return self.save(filename)

class Plot():
    def __init__(self, session='25_03_31', trialName='Squat_bw_01', results_dir=RESULTS_DIR):

        model_config = settings.model_config

        self.trialName = trialName
        subject_names = {k: v['subject'] for k, v in model_config.items()}
        self.colors = {k: v['color'] for k, v in model_config.items()}
        self.forces_type = {k: v['force_type'] for k, v in model_config.items()}
        self.lineStyles = {k: v['line_style'] for k, v in model_config.items()}
        labels = list(model_config.keys())

        self.results_dir = results_dir       
        os.makedirs(self.results_dir, exist_ok=True)

        # self.trials is a dictionary that must contain an Analyse object for each trial to be plotted, with keys matching the labels in model_config
        self.trials = {}
        for label, subject in zip(labels, subject_names.values()):
            trialPath = os.path.join(SIMULATIONS_DIR, subject, session, trialName)
            self.trials[label] = Analyse(trialPath)

        print(f'Results to be saved to: {self.results_dir}')

    def _refresh_results_summary(self):
        """Keep the markdown summary in sync with generated output files."""
        self.write_results_markdown_summary(self.results_dir)

    def marker_error(self):
        '''
        Plots marker error for each trial on the provided axes.
        '''
        body_segments = settings.marker_weights.keys()
        dofs = settings.BatchSettings.dof_list


        for trial_name, trial in self.trials.items():
            if not isinstance(trial, Analyse):
                continue

            marker_errors = load_any_data_file('.\\_ik_marker_errors_all.sto')
            markers = trial.get_markers()
            for segment in body_segments:
                for dof in dofs:
                    col_name = f'{segment}_{dof}_error'
                    if col_name in marker_errors.columns:
                        plt.plot(marker_errors['time'], marker_errors[col_name], label=f'{trial_name} - {segment} {dof}', color=self.colors[trial_name], linestyle=self.lineStyles[trial_name])
                    else:
                        print(f"Column {col_name} not found in {trial_name} marker error data.")




    def external_biomechanics(self):

        ik_columns = settings.BatchSettings.dof_list
        n_cols = len(ik_columns)
        n_rows = 2
        fig, ax = plt.subplots(nrows=int(n_rows), ncols=int(n_cols), figsize=(2*n_cols, 3*n_rows), sharex='col')
        plt.suptitle('Comparison', y=0.98, fontsize=10)

        models_to_flip = ['Lernagopal', 'Scaled (GPK)']  # Add model names that require flipping here
        models_to_flip = ['Lernagopal', 'GPK']

        for trial_name, trial in self.trials.items():
            angles = load_any_data_file(os.path.join(trial.path, trial.ik))
            moments = load_any_data_file(os.path.join(trial.path, trial.id)) 
            for col_idx, col_name in enumerate(ik_columns):
                
                if col_name == 'time':
                    continue
                
                if any(model in trial_name for model in models_to_flip) and col_name.__contains__('knee_angle'):
                    print(trial_name + '_ flipped') 
                    flip_values = -1
                else:
                    flip_values = 1
                
                try:
                    ax[0, col_idx].plot(angles['time'], angles[col_name] * flip_values, label=trial_name, color=self.colors[trial_name], linestyle=self.lineStyles[trial_name])
                    ax[1, col_idx].plot(moments['time'], moments[col_name+'_moment']* flip_values, label=trial_name, color=self.colors[trial_name], linestyle=self.lineStyles[trial_name])
                except KeyError:
                    print(f"Column {col_name} not found in {trial_name} data.")
                
                ax[0, col_idx].set_title(f'{col_name}', fontsize=8)
                ax[1, col_idx].set_xlabel('Time (s)')
                if col_idx == 0:
                    ax[0, col_idx].set_ylabel('Angle (deg)')
                    ax[1, col_idx].set_ylabel('Moment (Nm)')           
                
        # add legend outside of the plot        
        white_right_margin = 0.2
        handles, labels_legend = ax[0, 0].get_legend_handles_labels()
        plt.tight_layout()
        plt.subplots_adjust(right=1 - white_right_margin)
        fig.legend(handles, labels_legend, loc='center left', bbox_to_anchor=(1 - white_right_margin + 0.02, 0.5))

        save_path = os.path.join(self.results_dir, f'external_biomech_{self.trialName}.png')
        plt.savefig(save_path)
        print(f"Inverse kinematics comparison plot saved: {save_path}")
        self._refresh_results_summary()

    def muscle_moments(self):

        '''
        Plots muscle moments for a given degree of freedom (DOF) on the provided axes.
        Parameters:
            - ax: The matplotlib axes to plot on.
            - trial: The trial data containing paths to the necessary files.
            - dof: The degree of freedom for which to plot the muscle moments (e.g., 'hip_flexion_r').
            - forces: The type of muscle forces to use ('so' for static optimization or 'ceinms' for electromyography informed optimization).
        '''

        def create_muscle_moments_csv(trial: Analyse, dof: str, forces: str = 'so'):

            output_csv_path = os.path.join(trial.path, f'muscle_moments_{dof}_{forces}.csv')

            if os.path.exists(output_csv_path):
                print(f"Muscle moments CSV already exists: {output_csv_path}")
                return pd.read_csv(output_csv_path)
            
            moments = load_any_data_file(os.path.join(trial.path, trial.id))

            if forces.lower() == 'so':
                muscle_forces = load_any_data_file(os.path.join(trial.path, trial.so_forces))
            elif forces.lower() == 'ceinms':
                muscle_forces = load_any_data_file(os.path.join(trial.path, trial.jra_forces_ceinms))
            else:
                return

            ma_path = os.path.join(trial.path, trial.ma, f'_MuscleAnalysis_MomentArm_{dof}.sto')
            if not os.path.exists(ma_path):
                print(f"Moment arm file for {dof} not found in {trial.path}. Skipping muscle moment plot for this DOF.")
                return

            try:
                moment_arms = load_any_data_file(ma_path)
            except Exception:
                print(f"Moment arm file for {dof} not found in {trial.path}. Skipping muscle moment plot for this DOF.")
                return

            muscle_list = muscle_forces.columns.drop('time')
            muscles = openSim.find_non_zero_mom_arm_muscles(moment_arms, muscle_list)

            muscle_moments = muscle_forces.multiply(moment_arms, axis=0)
            muscle_moments['time'] = muscle_forces['time']

            
            muscle_moments.to_csv(output_csv_path, index=False)
            print(f"Muscle moments CSV created: {output_csv_path}")

            return muscle_moments

        def plot_muscle_moments(ax: plt.Axes, trial: Analyse, dof: str, forces: str = 'so', model_name: str = '', flip: float = 1.0):

            muscle_moments = create_muscle_moments_csv(trial, dof, forces)
            if muscle_moments is None:
                return

            muscles = muscle_moments.columns.drop('time')
            moments = load_any_data_file(os.path.join(trial.path, trial.id))

            id_col = dof + '_moment'
            if id_col not in moments.columns:
                ax.set_title(f'{dof}\n(no ID data)', fontsize=7)
                return

            # Plot individual muscle contributions
            for muscle in muscles:
                ax.plot(muscle_moments['time'], muscle_moments[muscle] * 1, label=muscle, linestyle='--')

            # Plot inverse dynamics moment
            ax.plot(moments['time'], moments[id_col] * 1,
                    label=f'Inverse Dynamics {model_name}',
                    color=self.colors.get(model_name, 'black'), linewidth=2)

            total_muscle_moment = muscle_moments[muscles].sum(axis=1)*1

            # Fill area under total muscle moment
            ax.fill_between(muscle_moments['time'], total_muscle_moment, alpha=0.3, color='gray')

            # Dashed outline of total muscle moment
            ax.plot(muscle_moments['time'], total_muscle_moment,
                    color='black', linestyle='--', linewidth=2, label='Total Muscle Moment')

            if trial.subject == 'Athlete_03' and dof == 'knee_angle_r':
                pass
                
            # Residual annotation
            inverse_dynamics_moment = moments[id_col] * flip
            moment_diff = total_muscle_moment - inverse_dynamics_moment
            moment_diff_mean = moment_diff.mean()
            moment_diff_std = moment_diff.std()
            mm_range = total_muscle_moment.max() - total_muscle_moment.min()
            moment_diff_mean_pct = (moment_diff_mean / mm_range) * 100 if mm_range != 0 else np.nan
            moment_diff_std_pct = (moment_diff_std / mm_range) * 100 if mm_range != 0 else np.nan

            text_str = (f'Mean Residual: {moment_diff_mean:.2f} Nm ({moment_diff_mean_pct:.2f}%)\n'
                        f'Std: {moment_diff_std:.2f} Nm ({moment_diff_std_pct:.2f}%)')
            ax.text(0.02, 0.98, text_str, transform=ax.transAxes, fontsize=6,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))


        _models_to_flip = ['Lernagopal', 'GPK']

        ik_columns = settings.BatchSettings.dof_list
        n_rows = len(ik_columns)
        n_cols = len(self.trials)
        fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols,
                                 figsize=(2 * n_cols, 3 * n_rows), sharex='col')

        for irow, dof in enumerate(ik_columns):
            for icol, model_name in enumerate(self.trials.keys()):
                ax = axes[irow, icol]
                flip = -1.0 if ('knee_angle' in dof and any(m in model_name for m in _models_to_flip)) else 1.0
                try:
                    plot_muscle_moments(ax, self.trials[model_name], dof,
                                        forces=self.forces_type[model_name],
                                        model_name=model_name,
                                        flip=flip)
                except Exception as e:
                    print(f"Error plotting muscle moments for {model_name}, {dof}: {e}")
                    print(f'check folder {self.trials[model_name].path} for missing files.')

                if icol == 0:
                    ax.set_ylabel(f'{dof} (Nm)')

                if irow == len(ik_columns) - 1:
                    ax.set_xlabel('Time (s)')
                elif irow == 0:
                    ax.set_title(f'{model_name}', fontsize=8)

        # Single figure legend using the last populated subplot's handles
        handles, labels_leg = axes[0, -1].get_legend_handles_labels()
        fig.legend(handles, labels_leg, loc='center left',
                   bbox_to_anchor=(1.0, 0.5), fontsize=6, ncol=1)

        fig.suptitle('Muscle Moments Comparison', fontsize=12)

        # Sync y-axis limits per row
        for row_idx in range(n_rows):
            y_min = min(axes[row_idx, col_idx].get_ylim()[0] for col_idx in range(n_cols))
            y_max = max(axes[row_idx, col_idx].get_ylim()[1] for col_idx in range(n_cols))
            for col_idx in range(n_cols):
                axes[row_idx, col_idx].set_ylim(y_min, y_max)

        fig.tight_layout()
        save_path = os.path.join(self.results_dir, f'muscle_moments_{self.trialName}.png')
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Muscle moments comparison plot saved: {save_path}")
        self._refresh_results_summary()

    def moment_arms(self):
        '''Plots moment arms for all DOFs in settings.py.
        One figure per DOF. One subplot per muscle (with non-zero moment arm in any model).
        Each line in a subplot represents one model.

        Output: results/moment_arms_<dof>.png
        '''

        dofs = settings.BatchSettings.dof_list

        for dof in dofs:
            # --- collect moment arm data for every model ---
            model_data = {}  # model_name -> DataFrame
            for model_name, trial in self.trials.items():
                if not isinstance(trial, Analyse):
                    continue
                ma_path = os.path.join(trial.path, trial.ma, f'_MuscleAnalysis_MomentArm_{dof}.sto')
                if not os.path.exists(ma_path):
                    print(f"Moment arm file for {dof} not found in {trial.path}. Skipping model {model_name}.")
                    continue
                try:
                    model_data[model_name] = load_any_data_file(ma_path)
                except Exception as e:
                    print(f"Could not load moment arm file for {model_name}, {dof}: {e}")

            if not model_data:
                print(f"No moment arm data found for {dof}. Skipping.")
                continue

            # --- find muscles that have non-zero moment arms in any model ---
            muscles_with_data = set()
            for df in model_data.values():
                muscle_cols = df.columns.drop('time')
                nonzero = openSim.find_non_zero_mom_arm_muscles(df, muscle_cols)
                muscles_with_data.update(nonzero)
            muscles_with_data = sorted(muscles_with_data)

            if not muscles_with_data:
                print(f"No muscles with non-zero moment arms for {dof}. Skipping.")
                continue

            # --- create subplots: one per muscle ---
            n_muscles = len(muscles_with_data)
            n_cols = 4
            n_rows = -(-n_muscles // n_cols)  # ceiling division
            fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols,
                                     figsize=(3 * n_cols, 2.5 * n_rows), sharex=True)
            axes_flat = axes.flatten()

            for i, muscle in enumerate(muscles_with_data):
                ax = axes_flat[i]
                for model_name, df in model_data.items():
                    if muscle in df.columns:
                        ax.plot(df['time'], df[muscle],
                                label=model_name,
                                color=self.colors.get(model_name),
                                linestyle=self.lineStyles.get(model_name, '-'))
                ax.set_title(muscle, fontsize=7)
                ax.axhline(0, color='k', linewidth=0.5, linestyle=':')
                if i % n_cols == 0:
                    ax.set_ylabel('Moment Arm (m)', fontsize=7)
                if i >= n_cols * (n_rows - 1):
                    ax.set_xlabel('Time (s)', fontsize=7)

            # hide unused axes
            for j in range(n_muscles, len(axes_flat)):
                axes_flat[j].set_visible(False)

            # single legend
            handles, labels_leg = axes_flat[0].get_legend_handles_labels()
            fig.legend(handles, labels_leg, loc='lower right', fontsize=7, ncol=2)

            fig.suptitle(f'Moment Arms — {dof}', fontsize=10)
            fig.tight_layout()

            save_path = os.path.join(self.results_dir, f'moment_arms_{dof}.png')
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"Moment arms plot saved: {save_path}")
                
                    
          
        # Summary plot with all dofs and models in one figure
        n_cols = 6 
        n_rows = len(dofs) // n_cols + (len(dofs) % n_cols > 0)
        fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(3 * n_cols, 2.5 * n_rows), sharex=True)
        axes_flat = axes.flatten()
        for i, dof in enumerate(dofs):
            # plot spider plot of moment arms for this dof across all models
            ax = axes_flat[i]
            ax.set_title(dof, fontsize=8)
            ax.set_visible(True)

        # hide unused axes
        for j in range(len(dofs), len(axes_flat)):
            axes_flat[j].set_visible(False)

        fig.suptitle('Moment Arms Summary — All DOFs', fontsize=10)
        fig.tight_layout()
        
        save_path = os.path.join(self.results_dir, 'moment_arms_summary.png')
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Moment arms summary plot saved: {save_path}")
        self._refresh_results_summary()

    def summary_errors(self):
        '''Plots summary of errors between models for each DOF'''

        dofs = settings.BatchSettings.dof_list
        n_cols = len(dofs) + 1 # Add an extra column for the mean box plot across DOFs
        n_rows = 5 # IK errors, RMSE and r2 for both Moments and EMG 
        fig, ax = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(3*n_cols, 3*n_rows), sharex='col')

        # Create summary dataframe to hold error metrics for each model and DOF
        summary_df = pd.DataFrame(columns=['Model', 'DOF', 'Marker_Errors_RMSE_mm', 'Moment_RMSE_percent', 'Moment_R2', 'EMG_RMSE_percent', 'EMG_R2'])

        for model_name, trial in self.trials.items():
            if not isinstance(trial, Analyse):
                print(f"Trial for model {model_name} is not an instance of Analyse. Skipping error summary for this model.")
                continue

            marker_errors = trial.calculate_mean_marker_error()
            moment_errors = trial.calculate_moment_errors()


    def write_results_markdown_summary(self, summary_name: str = 'summary.md') -> str:
        """Create a markdown summary that embeds moment-arm figures and key outputs."""

        def _pretty_coord_name(stem: str) -> str:
            name = stem.replace('moment_arms_', '')
            if name.endswith('_r'):
                name = name[:-2] + ' right'
            elif name.endswith('_l'):
                name = name[:-2] + ' left'
            name = name.replace('_', ' ')
            return name.strip().title()

        def _add_image_block(markdown_lines: list, image_name: str, alt_prefix: str = 'Figure'):
            stem = os.path.splitext(image_name)[0]
            title = _pretty_coord_name(stem)
            markdown_lines.append(f'## {title}')
            markdown_lines.append(f'![{alt_prefix} {title}]({image_name})')
            markdown_lines.append('')

        results_dir = self.results_dir
        os.makedirs(results_dir, exist_ok=True)

        summary_path = os.path.join(results_dir, summary_name)
        file_names = [
            name for name in os.listdir(results_dir)
            if os.path.isfile(os.path.join(results_dir, name)) and name != summary_name
        ]

        png_files = sorted([f for f in file_names if f.lower().endswith('.png')])
        csv_files = sorted([f for f in file_names if f.lower().endswith('.csv')])
        html_files = sorted([f for f in file_names if f.lower().endswith('.html')])

        moment_arm_files = [
            f for f in png_files
            if f.lower().startswith('moment_arms_') and f.lower() != 'moment_arms_summary.png'
        ]

        lines = [
            '# GPK Validation Summary',
            '',
            f'Updated: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            '## Overview',
            f'- Total files: {len(file_names)}',
            f'- Moment arm figures: {len(moment_arm_files)}',
            f'- Other figures: {len(png_files) - len(moment_arm_files)}',
            f'- CSV files: {len(csv_files)}',
            f'- HTML files: {len(html_files)}',
            '',
            '# Moment arms',
            '',
        ]

        if moment_arm_files:
            for image_name in moment_arm_files:
                _add_image_block(lines, image_name, alt_prefix='Moment arms')
        else:
            lines.append('No moment arm figures found.')
            lines.append('')

        moment_arm_summary = 'moment_arms_summary.png'
        if moment_arm_summary in png_files:
            lines.append('## Moment Arms Summary')
            lines.append(f'![Moment arms summary]({moment_arm_summary})')
            lines.append('')

        other_png_files = [
            f for f in png_files
            if f not in moment_arm_files and f.lower() != 'moment_arms_summary.png'
        ]
        lines.append('# Other figures')
        lines.append('')
        if other_png_files:
            for image_name in other_png_files:
                _add_image_block(lines, image_name, alt_prefix='Figure')
        else:
            lines.append('No additional figure files found.')
            lines.append('')

        lines.append('# CSV outputs')
        lines.append('')
        if csv_files:
            for csv_name in csv_files:
                csv_path = os.path.join(results_dir, csv_name)
                lines.append(f'## {csv_name}')
                try:
                    df = pd.read_csv(csv_path)
                    lines.append(f'- Rows: {len(df)}')
                    lines.append(f'- Columns: {len(df.columns)}')
                    cols_preview = ', '.join(df.columns[:8])
                    if len(df.columns) > 8:
                        cols_preview += ', ...'
                    lines.append(f'- First columns: {cols_preview}')
                except Exception as exc:
                    lines.append(f'- Could not read CSV: {exc}')
                lines.append('')
        else:
            lines.append('No CSV files found.')
            lines.append('')

        if html_files:
            lines.append('# HTML outputs')
            lines.append('')
            for html_name in html_files:
                lines.append(f'- [{html_name}]({html_name})')
            lines.append('')

        with open(summary_path, 'w', encoding='utf-8') as file:
            file.write('\n'.join(lines).rstrip() + '\n')

        self._log(f'Summary markdown updated: {summary_path}', terminal=True)
        return summary_path

def _update():
    '''
    update the version of the present .utils package in the simulations directory with the current version of the .utils package in the code directory.

    1. Ask the user what version they want to update to 
    2. Changes the version number in the present .utils package 
    3. Commites the changes to git with a message indicating the update

    '''
    os.chdir(CODE_DIR)
    
    current_version = __version__
    print(f'Current version: {current_version}')

    new_version = input(f'Enter the new version number to update to (current: {current_version}): ')
    if new_version == current_version:
        print('New version is the same as current version. No update needed.')
        return
    
    # update version in __init__.py
    current_file = os.path.abspath(__file__)
    with open(current_file, 'r') as file:
        lines = file.readlines()
    with open(current_file, 'w') as file:
        for line in lines:
            if line.startswith('__version__'):
                file.write(f"__version__ = '{new_version}'\n")
            else:
                file.write(line)
    
    print(f'Updated version to {new_version} in {current_file}')

    # commit changes to git
    try:
        subprocess.run(['git', 'add', current_file], check=True, cwd=os.getcwd())
        commit_message = f"Update .utils version to {new_version}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=os.getcwd())
        print(f'[Success] Updated .utils version to {new_version} and pushed to git.')
    except subprocess.CalledProcessError as e:
        print(f'[Error] Failed to commit version update to git: {e}')

def create_session(subject, session):

    subject_path = os.path.join(SIMULATIONS_DIR, subject)
    session_path = os.path.join(SIMULATIONS_DIR, subject, session)
    
    model_path = os.path.join(MODELS_DIR, subject, session)

    if not os.path.exists(session_path):
        try:
            os.makedirs(session_path, exist_ok=True)
            self._log(f'[Success] Created session directory: {session_path}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create session directory: {e}', terminal=True)

    if not os.path.exists(model_path):
        try:
            os.makedirs(model_path, exist_ok=True)
            self._log(f'[Success] Created model directory: {model_path}', terminal=True)
        except Exception as e:
            self._log(f'[Error] Failed to create model directory: {e}', terminal=True)


    return session_path

## Utility functions
def updir(path, levels=1):
    """Move up a directory path by a specified number of levels."""
    for _ in range(levels):
        path = os.path.dirname(path)
    return path

def print_to_log(message, terminal=PRINT_TERMINAL, trial=None):
    """
    Prints a message to the console and logs it to a file.

    Args:
        message (str): The message to print and log.
        trial (str): Optional trial name shown before the message.
    """
    timestamp = time.strftime('%d.%m.%Y_%H:%M:%S', time.localtime()) + f":{int((time.time() % 1) * 1000):03d}"
    prefix = f'[{trial}] ' if trial else ''

    with open(CODE_DIR + '\\log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f'{timestamp}: {prefix}{message}\n')

    if terminal:
        print(f'{prefix}{message}')

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

    # read the file into a pandas DataFrame, skipping the header
    try:
        columns = []
        offset = -3
        while 'time' not in columns:
            try:    
                data = pd.read_csv(path, sep=r'\s+', header=i+offset)
                columns = data.columns
                offset += 1
                if offset > 100:
                    print(f"Error: Could not find 'time' column in the file {path}. Please check the file format.")
                    return None
            except pd.errors.ParserError:
                offset += 1
                
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
            """Saves the XML tree to a file with proper indentation and no blank lines."""
            rough_string = ET.tostring(tree.getroot(), 'utf-8')
            reparsed = xml.dom.minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="   ")
            # Remove blank lines
            pretty_xml_no_blanks = "\n".join([line for line in pretty_xml.splitlines() if line.strip()])
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

# plotting
def save_fig(fig, save_path):
    """Saves the figure to the specified path."""
    if not os.path.exists(os.path.dirname(save_path)):
        os.makedirs(os.path.dirname(save_path))
    fig.savefig(save_path, bbox_inches='tight')
    print(f"Figure saved to {save_path}")

def get_screen_size():

    try:
        import tkinter as tk
        root = tk.Tk()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception as e:
        print(f"Error getting screen size: {e}")
        return None

def calculate_nRows_nCols(n_subplots):
    """
    Calculate the number of rows and columns for subplots based on the number of subplots.

    Args:
        n_subplots (int): The total number of subplots.

    Returns:
        tuple: (nrows, ncols) where nrows is the number of rows and ncols is the number of columns.
    """
    import numpy as np
    # Find the smallest nrows and ncols such that nrows * ncols >= n_subplots and (nrows-1) * ncols < n_subplots
    ncols = int(np.ceil(np.sqrt(n_subplots)))
    nrows = int(np.ceil(n_subplots / ncols))
    while (nrows - 1) * ncols >= n_subplots:
        nrows -= 1
    return nrows, ncols

def figure_suplots_grid(n_subplots, fig_size=(12, 8)):
    """
    Create a figure with subplots arranged in a grid based on the number of subplots.

    Args:
        n_subplots (int): The total number of subplots.
        fig_size (tuple): The size of the figure.

    Returns:
        tuple: (fig, axes) where fig is the figure object and axes is an array of subplot axes.
    """
    nrows, ncols = calculate_nRows_nCols(n_subplots)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=fig_size)
    axes = axes.flatten()  # Flatten in case of multiple rows/columns
    return fig, axes

def mmfn(fig: plt.Figure, n_rows: int, n_cols: int):
    '''make my figure nice

    - remove x-tick labels from all but last row
    - remove title from all but first row
    - if an ax is empty (no data), remove ax
    - y labels only on first column

    '''
    axes = fig.get_axes()
    if len(axes) != n_rows * n_cols:
        raise ValueError(f'Number of axes ({len(axes)}) does not match n_rows * n_cols ({n_rows * n_cols})')
    
    for idx, ax in enumerate(axes):
        row = idx // n_cols
        col = idx % n_cols
        
        # Remove x-tick labels from all but last row
        if row < n_rows - 1:
            ax.set_xticklabels([])
            ax.set_xlabel('')

        # Remove title from all but first row
        # if row > 0:
        #     ax.set_title('')

        # Y labels only on first column
        if col > 0:
            ax.set_yticklabels([])
            ax.set_ylabel('')
    
    # delete empty axes
    axes_to_delete = []
    for idx, ax in enumerate(axes):
        if not ax.has_data():
            axes_to_delete.append(idx)

    for idx in reversed(axes_to_delete):  # delete from the end to avoid index shift
        fig.delaxes(axes[idx])

    plt.tight_layout()
    return fig

def plot_mean_error_shade(ax: plt.Axes, df_list: list, xcol: str, ycol: str, color: str, label: str = ''):
    '''Plot mean and error shade for a list of dataframes
    '''
    # Interpolate all data to common time vector
    df_mean = get_mean_across_trial_dfs(df_list, mode='mean')
    df_error = get_mean_across_trial_dfs(df_list, mode='stdev')

    # breakpoint()
    ax.plot(df_mean[xcol], df_mean[ycol], color=color, label=label)
    
    ax.fill_between(df_mean[xcol], 
                    df_mean[ycol] - df_error[ycol],
                    df_mean[ycol] + df_error[ycol],
                    color=color, alpha=0.3)

    return ax

def add_picture_to_ax(ax: plt.Axes, image_path: str, scale: float = 1.0):
    from scipy.ndimage import zoom

    if os.path.exists(image_path):
            img = plt.imread(image_path)
            ax.imshow(img)
            # Scale image if needed
            if scale != 1.0:
                img = zoom(img, (scale, scale, 1), order=1)
            ax.imshow(img)
            ax.axis('off')
    else:
            print(f"Warning: Image file not found at {image_path}. Adding task name text instead.")
            ax.text(0.5, 0.5, "Image not found", ha='center', va='center', fontsize=12)
            ax.axis('off')

def convert_to_interactive_fig(fig: plt.Figure, html_path: str, launch_browser: bool = True):
    """
    Convert Matplotlib figure to Plotly and:
    1) show each legend label only once
    2) toggle all traces with that label across all subplots
    3) order legend labels alphabetically
    """
    import plotly.io as pio
    import plotly.tools as tls

    plotly_fig = tls.mpl_to_plotly(fig)

    # Keep suptitle if present
    if fig._suptitle is not None:
        plotly_fig.update_layout(title=fig._suptitle.get_text(), title_x=0.5)

    # Ensure all traces have a name
    for trace in plotly_fig.data:
        if not trace.name:
            trace.name = "Unnamed"

    # Sort traces alphabetically by label
    sorted_traces = sorted(plotly_fig.data, key=lambda t: t.name.lower())

    # Merge repeated legend labels and link traces by legendgroup
    seen = set()
    for trace in sorted_traces:
        name = trace.name
        trace.legendgroup = name
        trace.showlegend = name not in seen
        seen.add(name)

    # Apply sorted order back to figure
    plotly_fig.data = tuple(sorted_traces)

    # Clicking one legend item toggles the whole group (all subplots)
    plotly_fig.update_layout(
        legend=dict(groupclick="togglegroup", traceorder="normal")
    )
    
    # # add a button so all plots reset to ylims of each row
    # plotly_fig.update_layout(
    #     updatemenus=[
    #         dict(
    #             type="buttons",
    #             direction="right",
    #             x=0.7,
    #             y=1.2,
    #             buttons=list([
    #                 dict(
    #                     label="Reset Y-Limits",
    #                     method="relayout",
    #                     args=[{"yaxis.autorange": True}]
    #                 )
    #             ])
    #         )
    #     ]
    # )

    pio.write_html(plotly_fig, file=html_path, full_html=True, auto_open=False)

    print(f"Interactive plot saved: {html_path}")

    if launch_browser:
        webbrowser.open("file://" + os.path.abspath(html_path))

# EMG processing
def filter_emg(emg_path=None, highcut_bp=95, lowcut_bp=20, order_bp=4, lowcut_lp=6, order_lp=4):
    """
    Apply bandpass filter, rectify, and lowpass filter to EMG signals in a .sto file.

    Inputs:
        - emg_path: The path to the .sto file containing EMG signals.
        - highcut_bp: High cutoff frequency for the bandpass filter.
        - lowcut_bp: Low cutoff frequency for the bandpass filter.
        - order_bp: Order of the bandpass filter.
        - lowcut_lp: Low cutoff frequency for the lowpass filter.
        - order_lp: Order of the lowpass filter.

    Returns:
        - data: A DataFrame containing the original and processed EMG signals.
    """
    if emg_path is None:
        emg_path = input("Please provide the path to the .sto file containing EMG signals: ")

    data = load_any_data_file(emg_path)

    # Calculate sampling frequency from the time column (default 1000 Hz).
    sampling_freq = 1000.0
    if 'time' in data.columns and len(data['time']) > 1:
        try:
            dt = float(data['time'].iloc[1]) - float(data['time'].iloc[0])
            if dt > 0:
                sampling_freq = 1.0 / dt
        except Exception:
            sampling_freq = 1000.0
        if not (100 <= sampling_freq <= 10000):
            print(f"Warning: unusual EMG sampling freq ({sampling_freq:.1f} Hz) — defaulting to 1000 Hz")
            sampling_freq = 1000.0
    print(f"EMG Sampling Frequency: {sampling_freq:.1f} Hz")

    emg_cols = [col for col in data.columns if col.startswith('emg')]

    # --- 1. Bandpass Filter ---
    nyquist = 0.5 * sampling_freq
    low = lowcut_bp / nyquist
    high = highcut_bp / nyquist

    if low >= high:
        print("Warning: Bandpass filter low cutoff is greater than or equal to high cutoff after normalization.")
        print("Adjusting cutoff frequencies or sampling frequency may be necessary.")
    elif low >= 1.0 or high >= 1.0:
        print("Warning: Bandpass filter cutoff frequency is at or above Nyquist frequency.")
        print("This might lead to unexpected filter behavior. Check sampling frequency and cutoff values.")

    b, a = scipy.signal.butter(order_bp, [low, high], btype='band')

    print(f"\nApplying bandpass filter ({lowcut_bp}-{highcut_bp} Hz, Order {order_bp})...")
    for col in emg_cols:
        filtered_col_name = f"{col}_bandpass"
        data[filtered_col_name] = scipy.signal.filtfilt(b, a, data[col].values)
    print("Bandpass filtering complete.")

    # --- 2. Rectify ---
    print("\nRectifying bandpass-filtered signals...")
    bandpass_emg_cols = [col for col in data.columns if col.endswith('_bandpass')]
    for col in bandpass_emg_cols:
        rectified_col_name = col.replace('_bandpass', '_rectified')
        data[rectified_col_name] = np.abs(data[col].values)
    print("Rectification complete.")

    # --- 3. Lowpass Filter (Envelope) ---
    nyquist = 0.5 * sampling_freq
    low_lp = lowcut_lp / nyquist

    if low_lp >= 1.0:
        print("Warning: Lowpass filter cutoff frequency is at or above Nyquist frequency.")
        print("This might lead to unexpected filter behavior. Check sampling frequency and cutoff values.")

    b_lp, a_lp = scipy.signal.butter(order_lp, low_lp, btype='low')

    print(f"\nApplying lowpass filter ({lowcut_lp} Hz, Order {order_lp}) for envelope detection...")
    rectified_emg_cols = [col for col in data.columns if col.endswith('_rectified')]
    for col in rectified_emg_cols:
        envelope_col_name = col.replace('_rectified', '_envelope')
        data[envelope_col_name] = scipy.signal.filtfilt(b_lp, a_lp, data[col].values)
    print("Lowpass filtering complete.")

    print("\nFiltered data processing complete.")

    # save new file 
    ext = os.path.splitext(emg_path)[1]
    new_emg_path = emg_path.replace(ext, f"_filtered{ext}")
    write_sto_file(data, new_emg_path)
    print(f"Filtered EMG data saved to: {new_emg_path}")

    return data

def amplitude_normalise_emg(main_dir=None, trials_to_normalise=None, normalisation_trials=None, emg_filename="emg.mot"):
    '''
    Normalise EMG envelope amplitudes across trials to the maximum value found
    in the normalisation trials, then save new files and plots.

    Args:
        main_dir: Root directory containing per-trial subdirectories.
        trials_to_normalise: List of trial folder names to normalise. Defaults to all subdirs.
        normalisation_trials: List of trial folder names used to find the max EMG. Defaults to trials_to_normalise.
        emg_filename: Name of the EMG file inside each trial folder (must contain _envelope columns).
    '''

    if main_dir is None:
        main_dir = input("Please provide the path to the main directory containing trial subdirectories: ").strip('"')

    if trials_to_normalise is None:
        trials_to_normalise = os.listdir(main_dir)
        trials_to_normalise = [trial for trial in trials_to_normalise if os.path.isdir(os.path.join(main_dir, trial))]
    
    if normalisation_trials is None:
        normalisation_trials = trials_to_normalise
        

    # load normalisation trial data
    max_emg = {}
    envelope_columns = []
    for trial in normalisation_trials:
        emg_path = f'{main_dir}/{trial}/{emg_filename}'
        emg_data = load_sto(emg_path)
        envelope_columns = [col for col in emg_data.columns if col.endswith('_envelope')]
        if not max_emg:
            for col in envelope_columns:
                max_emg[col] = 0
        for col in envelope_columns:
            max_emg[col] = max(max_emg[col], emg_data[col].max())

    # normalise each trial to max and save new file
    for trial in trials_to_normalise:
        emg_path = f'{main_dir}/{trial}/{emg_filename}'
        emg_data = load_sto(emg_path)

        for col in envelope_columns:
            emg_data[col] = emg_data[col] / max_emg[col]

        new_filepath = emg_path.replace('.mot', '_normalised_amplitude.mot')
        write_sto_file(emg_data, new_filepath)
        print(f'Saved normalised amplitude data to {new_filepath}')

        n_cols = 4
        n_rows = int(np.ceil(len(envelope_columns) / n_cols))
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 3 * n_rows), sharex=True)
        axes = axes.flatten() if n_rows > 1 else [axes]
        for i, col in enumerate(envelope_columns):
            ax = axes[i]
            ax.plot(emg_data['time'], emg_data[col], label=col)
            ax.set_title(f"{trial} - {col}", fontsize=10)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Normalised Amplitude')

        plt.tight_layout()
        mmfn(fig, n_rows, n_cols)

        save_path = f'{main_dir}/{trial}/emg_normalised_amplitude_plot.png'
        plt.savefig(save_path)
        print(f'Saved normalised amplitude plot to {save_path}')

def emg_processing_file(filepath=None, highcut_bp=95, lowcut_bp=20, order_bp=4, lowcut_lp=6, order_lp=4, emg_prefix='EMG_Channels_EMG'):
    if filepath is None:
        filepath = input("Please provide the path to the EMG file to be processed: ").strip('"')
    
    # save processed file
    df = load_any_data_file(filepath)
    filtered_df = filter_emg_df(df, highcut_bp, lowcut_bp, order_bp, lowcut_lp, order_lp)

    
    processed_filepath = filepath.replace('.mot', '_processed.mot')
    write_sto_file(filtered_df, processed_filepath)
    print(f'Saved processed EMG data to {processed_filepath}')

# data manipulation
def time_normalise_df(df, fs=''):

    if not type(df) == pd.core.frame.DataFrame:
        raise Exception('Input must be a pandas DataFrame')

    if 'time' not in df.columns:
        raise Exception('Input DataFrame must contain a column named "time"')

    normalised_df = pd.DataFrame(columns=df.columns)

    timeTrial = df['time'].values

    Tnorm = np.linspace(timeTrial[0], timeTrial[-1], 101)

    for column in df.columns:
        normalised_df[column] = np.zeros(101)

        currentData = df[column].values.astype(float)

        # replace NaNs with interpolated values where possible, else 0
        nan_mask = np.isnan(currentData)
        if nan_mask.all():
            currentData = np.zeros(len(timeTrial))
        elif nan_mask.any():
            currentData[nan_mask] = np.interp(
                timeTrial[nan_mask], timeTrial[~nan_mask], currentData[~nan_mask]
            )

        normalised_df[column] = np.interp(Tnorm, timeTrial, currentData)

    return normalised_df

def time_normalise_file(filepath=None, fs=None):
    
    if filepath is None:
        filepath = input("Please provide the path to the file to be time-normalised: ").strip('"')
    
    df = load_any_data_file(filepath)
    if fs is None:
        fs = 1/(df['time'][1]-df['time'][0])
    normalised_df = time_normalise_df(df, fs)
    # save normalised file
    normalised_filepath = filepath.replace('.sto', '_timeNormalised.sto')
    write_sto_file(normalised_df, normalised_filepath)

def get_mean_across_trial_dfs(df_list, mode = 'mean') -> pd.DataFrame:
    """
    Groups a list of DataFrames by their row position and returns the mean.
    
    Args:
        df_list (list): List of DataFrames (one per trial)
        mode (str): 'mean' to calculate mean, 'median' to calculate median, 'stdev' for standard deviation.
        
    Returns:
        pd.DataFrame: A single DataFrame of 101 rows (mean of all trials)
    """
    processed_dfs = []
    
    for i, df in enumerate(df_list):
        temp_df = df.copy()
        
        # 1. Add a trial ID for tracking
        temp_df['trial_id'] = i
        
        # 2. Create a 'sample_index' (0, 1, 2...) to align trials
        # This ensures row 1 of Trial A matches row 1 of Trial B
        temp_df['sample_index'] = range(len(temp_df))
        
        processed_dfs.append(temp_df)
    
    # Combine all trials into one large DataFrame
    combined_df = pd.concat(processed_dfs, axis=0)
    
    # Group by the sample_index and calculate mean
    # We drop 'trial_id' because averaging IDs isn't useful
    if mode == 'mean':
        result_df = combined_df.groupby('sample_index').mean().drop(columns=['trial_id'], errors='ignore')
    elif mode == 'median':
        result_df = combined_df.groupby('sample_index').median().drop(columns=['trial_id'], errors='ignore')
    elif mode == 'stdev':
        result_df = combined_df.groupby('sample_index').std().drop(columns=['trial_id'], errors='ignore')
    else:
        raise ValueError("Invalid mode. Choose from 'mean', 'median', or 'stdev'.")
    
    # Reset index to make sample_index a regular column
    result_df = result_df.reset_index(drop=True)
    
    return result_df

def get_unique_names(paths):
    # Split each path into parts
    split_paths = [p.split(os.sep) for p in paths]

    # Transpose to compare columns
    columns = list(zip(*split_paths))

    # Find the indices where not all elements are the same
    diff_indices = [i for i, col in enumerate(columns) if len(set(col)) > 1]

    # Create unique names using the differing parts
    unique_names = []
    for parts in split_paths:
        unique = "_".join([parts[i] for i in diff_indices])
        unique_names.append(unique)
    return unique_names

def create_color_and_style_dict(labels):
    """Creates a color and style dictionary based on unique labels.
    Args:
        labels (list): List of unique labels.
        Returns:
        tuple: Two dictionaries, one for colors and one for styles.
            
    Example:
        labels = ['Athlete_03_sq_70', 'Athlete_03_sq_75', 'Athlete_03_sq_80']
        color_dict, style_dict = create_color_and_style_dict(labels)
        
    """
    
    
    color_dict = {}
    style_dict = {}
    # Extract the number (e.g., 70, 75, 80, 85, 90) from each label for color assignment
    # Assume the number is always at the end after an underscore
    numbers = [label.split('_')[-1] for label in labels]
    unique_numbers = sorted(set(numbers), key=lambda x: int(x))
    color_map = matplotlib.colormaps['tab10']
    number_to_color = {num: color_map.colors[i % 10] for i, num in enumerate(unique_numbers)}
    for label, num in zip(labels, numbers):
        color_dict[label] = number_to_color[num]
        if 'mri' in label.lower():
            style_dict[label] = '--'
        else:
            style_dict[label] = '-'
    return color_dict, style_dict

def rsquared(y_true, y_pred):
    """Calculate the R-squared value between true and predicted values.
    
    Args:
        y_true (array-like): The true values.
        y_pred (array-like): The predicted values.
    """
    r = np.corrcoef(y_true, y_pred)[0, 1]
    return r ** 2

def rmse(y_true, y_pred):
    """Calculate the Root Mean Square Error (RMSE) between true and predicted values.
    
    Args:
        y_true (array-like): The true values.
        y_pred (array-like): The predicted values.
    """
    return np.sqrt(np.mean((y_true - y_pred) ** 2))    

def compare_curves(dataFrame1, dataFrame2, mapping=None):
    """Calculate RMSE and R-squared the common columns between two dataFrames.
    
    mapping: dict
        A dictionary mapping column names from dataFrame1 to dataFrame2.
        
    """
    
    if mapping is None:
        common_columns = dataFrame1.columns.intersection(dataFrame2.columns)
        mapping = dict(common_columns.to_series())
    else:
        common_columns = list(mapping.keys())
        
    results = pd.DataFrame(columns=['RMSE', 'R2'], index=common_columns)
    for col in common_columns:
        mapped_col = mapping.get(col, col)
        y_true_col = dataFrame1[mapped_col].values
        y_pred_col = dataFrame2[col].values
        rmse_value = rmse(y_true_col, y_pred_col)
        r2_value = rsquared(y_true_col, y_pred_col)
        results.loc[col] = [rmse_value, r2_value]
    
    return results

def sum3d(df, columns):
    x = df[columns[0]]
    y = df[columns[1]]
    z = df[columns[2]]
    sum = np.sqrt(x**2 +  y**2 + z**2)
    return sum

# dir manipulation
def rename_all_files_in_dir(dir_path, old_str, new_str):
    """
    Renames all files in the specified directory by replacing old_str with new_str in their names.
    
    Args:
        dir_path (str): The path to the directory containing the files.
        old_str (str): The substring to be replaced in the file names.
        new_str (str): The substring to replace old_str with.
    """
    if not os.path.isdir(dir_path):
        raise ValueError(f"The provided path '{dir_path}' is not a valid directory.")
    
    for filename in os.listdir(dir_path):
        if old_str in filename:
            new_filename = filename.replace(old_str, new_str)
            try:
                os.rename(os.path.join(dir_path, filename), os.path.join(dir_path, new_filename))
                print(f"Renamed '{filename}' to '{new_filename}'")
            except Exception as e:
                print(f"Error renaming '{filename}': {e}")


class gitTools():
    def __init__(self, local_repo_path):
        self.local_repo_path = local_repo_path
        try:
            self.repo = Repo(local_repo_path)
        except Exception as e:
            print(f"Error initializing git repository at {local_repo_path}: {e}")
            self.repo = None

# ------------------------------------------------

# Katya funtions TPS
class osimTools():
    """A collection of utility functions for OpenSim and data processing.
    
    functions with '_' the object to be created first because they refer to self
    Example:
        tools = osimTools()
        tools._printHello()
        
        osimTools.calculate_emg_linear_envelope(x)
        # katya
        # Utility functions.
        #
        # author: Dimitar Stanev <jimstanev@gmail.com>
        ##
    
    """
    
    def __init__(self, filepath=None):
        self.filepath = filepath

    def _printHello(self):
        print("Hello from osimTools!")

    def calculate_emg_linear_envelope(x, f_sampling=1000, f_band_low=30,
                                    f_band_high=300, f_env=6, to_normalize=True,
                                    plot=False):
        """Calculates the EMG linear envelope by applying the following
        transformations to the raw signal:

        1) Remove mean
        2) Band-pass 4th order Butterworth filter to remove low and high frequencies
        3) Full rectification (use of abs)
        4) Normalization based on max value (if to_normalize=True)
        5) Low-pass filter to calculate the envelope
        6) (optional) plot the raw and envelop signals (if plot=True); does not show plot just in the background

        """
        f_nyq = f_sampling / 2
        # 1) remove mean
        y = x - x.mean()
        # 2) band-pass
        b, a = signal.butter(4, [f_band_low / f_nyq, f_band_high / f_nyq], 'band')
        y = signal.filtfilt(b, a, y)
        # 3) rectify
        y = np.abs(y)
        # 4) normalize
        if to_normalize:
            y = y / y.max()

        # 5) low-pass
        b, a = signal.butter(2, f_env / f_nyq, 'low')
        env = signal.filtfilt(b, a, y)
        if plot:
            plt.figure()
            plt.plot(y, label='raw')
            plt.plot(env, label='envelop')
            plt.legend()
            
        return env

    def normalize_interpolate_dataframe(df, interp_column='time', method='linear'):
        """Normalizes time between [0, 1] and then re-samples data frame at
        constant interval.

        """
        # normalize between 0, 1
        time_old = df.time.to_numpy()
        time_new = (time_old - time_old[0]) / (time_old[-1] - time_old[0])
        df.loc[:, 'time'] = time_new
        # re-sample time with specific interval
        df = df.set_index(interp_column)
        at = np.arange(0, 1.01, 0.01)
        df = df.reindex(df.index | at)
        df = df.interpolate(method=method).loc[at]
        df = df.reset_index()
        df = df.rename(columns={'index': interp_column})
        return df

    def osim_vector_to_list(array):
        """Convert SimTK::Vector to Python list.
        """
        temp = []
        for i in range(array.size()):
            temp.append(array[i])

        return temp

    def vector_vec3_to_nparray(vector):
        temp = []
        for i in range(vector.size()):
            temp.append([vector[i][0], vector[i][1], vector[i][2]])

        return np.array(temp)


    def osim_array_to_list(array):
        """Convert OpenSim::Array<T> to Python list.
        """
        temp = []
        for i in range(array.getSize()):
            temp.append(array.get(i))

        return temp


    def list_to_osim_array_str(self, list_str):
        """Convert Python list of strings to OpenSim::Array<string>."""
        arr = osim.ArrayStr()
        for element in list_str:
            arr.append(element)

        return arr


    def np_array_to_simtk_matrix(array):
        """Convert numpy array to SimTK::Matrix"""
        n, m = array.shape
        M = osim.Matrix(n, m)
        for i in range(n):
            for j in range(m):
                M.set(i, j, array[i, j])

        return M


    def rotate_data_table(table, axis, deg):
        """Rotate OpenSim::TimeSeriesTableVec3 entries using an axis and angle.

        Parameters
        ----------
        table: OpenSim.common.TimeSeriesTableVec3

        axis: 3x1 vector

        deg: angle in degrees

        """
        R = osim.Rotation(np.deg2rad(deg),
                          osim.Vec3(axis[0], axis[1], axis[2]))
        for i in range(table.getNumRows()):
            vec = table.getRowAtIndex(i)
            vec_rotated = R.multiply(vec)
            table.setRowAtIndex(i, vec_rotated)


    def mm_to_m(table, label):
        """Scale from units in mm for units in m.

        Parameters
        ----------
        label: string containing the name of the column you want to convert

        """
        c = table.updDependentColumn(label)
        for i in range(c.size()):
            c[i] = osim.Vec3(c[i][0] * 0.001, c[i][1] * 0.001, c[i][2] * 0.001)


    def mirror_z(table, label):
        """Mirror the z-component of the vector.

        Parameters
        ----------
        label: string containing the name of the column you want to convert

        """
        c = table.updDependentColumn(label)
        for i in range(c.size()):
            c[i] = osim.Vec3(c[i][0], c[i][1], -c[i][2])


    def lowess_bell_shape_kern(x, y, tau=0.0005):
        """lowess_bell_shape_kern(x, y, tau = .005) -> y_est Locally weighted
        regression: fits a nonparametric regression curve to a scatterplot. The
        arrays x and y contain an equal number of elements; each pair (x[i], y[i])
        defines a data point in the scatterplot. The function returns the estimated
        (smooth) values of y.  The kernel function is the bell shaped function with
        parameter tau. Larger tau will result in a smoother curve.

        """
        n = len(x)
        y_est = np.zeros(n)

        # initializing all weights from the bell shape kernel function
        w = np.array([np.exp(- (x - x[i]) ** 2 / (2 * tau)) for i in range(n)])

        # looping through all x-points
        for i in range(n):
            weights = w[:, i]
            b = np.array([np.sum(weights * y), np.sum(weights * y * x)])
            A = np.array([[np.sum(weights), np.sum(weights * x)],
                        [np.sum(weights * x), np.sum(weights * x * x)]])
            theta = np.linalg.solve(A, b)
            y_est[i] = theta[0] + theta[1] * x[i]

        return y_est

    def _storage_to_dataframe(self, sto):
        print('Converting OpenSim Storage to pandas DataFrame')
        
        # for i in range(sto.getSize()):print(sto.getStateVector(i).getTime())
        for i in range(sto.getSize()):print(sto.getData(i))
        sto.printToFile()
        
        
    def _create_opensim_storage(self, time, data, column_names):
        """Creates a OpenSim::Storage.

        Parameters
        ----------
        time: SimTK::Vector

        data: SimTK::Matrix

        column_names: list of strings

        Returns
        -------
        sto: OpenSim::Storage

        """
        sto = osim.Storage()
        sto.setColumnLabels(osimTools().list_to_osim_array_str(['time'] + column_names))
        for i in range(data.nrow()):
            row = osim.ArrayDouble()
            for j in range(data.ncol()):
                value = data.getElt(i, j)
                if np.isnan(value):
                    value = 0
                row.append(value)
            sto.append(time[i], row)
        
        # self._storage_to_dataframe(sto)
        return sto


    def annotate_plot(ax, text):
        """Annotate a figure by adding a text.
        """
        at = AnchoredText(text, frameon=True, loc='upper left')
        at.patch.set_boxstyle('round, pad=0, rounding_size=0.2')
        ax.add_artist(at)


    def rmse_metric(s1, s2):
        """Root mean squared error between two time series.

        """
        # Signals are sampled with the same sampling frequency. Here time
        # series are first aligned.
        # if s1.index[0] < 0:
        #     s1.index = s1.index - s1.index[0]

        # if s2.index[0] < 0:
        #     s2.index = s2.index - s2.index[0]

        t1_0 = s1.index[0]
        t1_f = s1.index[-1]
        t2_0 = s2.index[0]
        t2_f = s2.index[-1]
        t_0 = np.round(np.max([t1_0, t2_0]), 3)
        t_f = np.round(np.min([t1_f, t2_f]), 3)
        x = s1[(s1.index >= t_0) & (s1.index <= t_f)].to_numpy()
        y = s2[(s2.index >= t_0) & (s2.index <= t_f)].to_numpy()
        return np.round(np.sqrt(np.mean((x - y) ** 2)), 3)


    def refine_ground_reaction_wrench(self,data_table, label_triplet, stance_threshold,
                                    tau, debug=True):
        """Clean and filter raw ground reaction forces at a single leg as specified by
        label triplet. This algorithm checks when the foot is in touch with the
        ground (stance phase). When the foot is not in touch then the original data
        contain noise with very small SNR. Therefore, the data is either set to zero
        or to nan. Then, the data is interpolated in case of nan. Finally, the
        signals are low pass filtered using lowess_bell_shape_kern.

        Parameters
        ----------

        data_table: OpenSim::DataTable<Vec3> containing [force, point, moment] for
        each leg

        label_triplet: column identifiers for the wrench triplet (e.g., ['f1', 'p1', 'm1'])

        stance_threshold: values to consider the foot in touch with the ground

        tau: kernel standard divination (filtering)

        debug: Boolean to visualize filtering result

        Returns
        -------

        This function mutates the original data_table

        """
        # get data of single leg
        t = np.array(data_table.getIndependentColumn())
        f = data_table.updDependentColumn(label_triplet[0])
        p = data_table.updDependentColumn(label_triplet[1])
        m = data_table.updDependentColumn(label_triplet[2])
        f_l = self.vector_vec3_to_nparray(f)
        p_l = self.vector_vec3_to_nparray(p)
        m_l = self.vector_vec3_to_nparray(m)

        # debugging
        if debug:
            plt.figure()
            f1 = plt.gca()
            f1.plot(t, f_l)
            plt.figure()
            f2 = plt.gca()
            f2.plot(t, p_l)
            plt.figure()
            f3 = plt.gca()
            f3.plot(t, m_l)

        # remove information when the foot is not touching the ground
        t0 = None
        tf = None
        for i in range(len(f_l)):
            # remove noise
            if f_l[i, 1] < stance_threshold:
                for j in range(3):
                    f_l[i, j] = 0
                    p_l[i, j] = np.nan
                    m_l[i, j] = 0

            # detect heel strike
            if t0 is None and f_l[i, 1] >= stance_threshold:
                t0 = t[i]

            # detect toe off
            if tf is None and t0 is not None and f_l[i, 1] <= stance_threshold:
                tf = t[i]

        # interpolate nan values for points and moments
        f_l = pd.DataFrame(f_l).interpolate(limit_direction="both", kind="cubic").to_numpy()
        p_l = pd.DataFrame(p_l).interpolate(limit_direction="both", kind="cubic").to_numpy()
        m_l = pd.DataFrame(m_l).interpolate(limit_direction="both", kind="cubic").to_numpy()

        # filter data
        for j in range(3):
            # f_l[:, j] = signal.medfilt(f_l[:, j], median)
            f_l[:, j] = self.lowess_bell_shape_kern(t, f_l[:, j], tau)
            p_l[:, j] = self.lowess_bell_shape_kern(t, p_l[:, j], tau)
            m_l[:, j] = self.lowess_bell_shape_kern(t, m_l[:, j], tau)

        # debugging
        if debug:
            f1.plot(t, f_l)
            f2.plot(t, p_l)
            f3.plot(t, m_l)

        # update columns in the original data
        for i in range(f_l.shape[0]):
            f[i] = osim.Vec3(f_l[i, 0], f_l[i, 1], f_l[i, 2])
            p[i] = osim.Vec3(p_l[i, 0], p_l[i, 1], p_l[i, 2])
            m[i] = osim.Vec3(m_l[i, 0], m_l[i, 1], m_l[i, 2])

        return t0, tf, p_l.mean(axis=0)

    def read_from_storage(self, file_name, sampling_interval=0.01,
                        to_filter=False):
        """Read OpenSim.Storage files.

        Parameters
        ----------
        file_name: (string) path to file

        sampling_interval: resample the data with a given interval (0.01)

        to_filter: use low pass 4th order FIR filter with 6Hz cut off
        frequency

        Returns
        ------- 
        df: pandas data frame

        """
        sto = osim.Storage(file_name)
        sto.resampleLinear(sampling_interval)
        if to_filter:
            sto.lowpassFIR(4, 6)

        labels = self.osim_array_to_list(sto.getColumnLabels())
        time = osim.ArrayDouble()
        sto.getTimeColumn(time)
        time = self.osim_array_to_list(time)
        data = []
        for i in range(sto.getSize()):
            temp = self.osim_array_to_list(sto.getStateVector(i).getData())
            temp.insert(0, time[i])
            data.append(temp)

        df = pd.DataFrame(data, columns=labels)
        df.index = df.time
        return df


    def index_containing_substring(list_str, pattern):
        """For a given list of strings finds the index of the element that
        contains the substring.

        Parameters
        ----------
        list_str: list of str

        pattern: str
            pattern


        Returns
        -------
        indices: list of int
            the indices where the pattern matches

        """
        return [i for i, item in enumerate(list_str)
                if re.search(pattern, item)]


    def _plot_sto_file(self, file_name, plot_file, plots_per_row=4, pattern=None,
                    title_function=lambda x: x):
        """Plots the .sto file (OpenSim) by constructing a grid of subplots.

        Parameters
        ----------
        sto_file: str
            path to file
        plot_file: str
            path to store result
        plots_per_row: int
            subplot columns
        pattern: str, optional, default=None
            plot based on pattern (e.g. only pelvis coordinates)
        title_function: lambda
            callable function f(str) -> str
        """
        df = osimTools().read_from_storage(file_name)
        labels = df.columns.to_list()
        data = df.to_numpy()

        if pattern is not None:
            indices = self.index_containing_substring(labels, pattern)
        else:
            indices = range(1, len(labels))

        n = len(indices)
        ncols = int(plots_per_row)
        nrows = int(np.ceil(float(n) / plots_per_row))
        pages = int(np.ceil(float(nrows) / ncols))
        if ncols > n:
            ncols = n

        with PdfPages(plot_file) as pdf:
            for page in range(0, pages):
                fig, ax = plt.subplots(nrows=ncols, ncols=ncols,
                                    figsize=(8, 8))
                ax = ax.flatten()
                for pl, col in enumerate(indices[page * ncols ** 2:page *
                                                ncols ** 2 + ncols ** 2]):
                    ax[pl].plot(data[:, 0], data[:, col])
                    ax[pl].set_title(title_function(labels[col]))

                fig.tight_layout()
                pdf.savefig(fig)
                plt.close()


    def adjust_model_mass(model_file, mass_change):
        """Given a required mass change adjust all body masses accordingly.

        """
        rra_model = osim.Model(model_file)
        rra_model.setName('model_adjusted')
        state = rra_model.initSystem()
        current_mass = rra_model.getTotalMass(state)
        new_mass = current_mass + mass_change
        mass_scale_factor = new_mass / current_mass
        for body in rra_model.updBodySet():
            body.setMass(mass_scale_factor * body.getMass())

        # save model with adjusted body masses
        rra_model.printToXML(model_file)


    def replace_thelen_muscles_with_millard(model_file, target_folder):
        """Replaces Thelen muscles with Millard muscles so that we can disable
        tendon compliance and perform MuscleAnalysis to compute normalized
        fiber length/velocity without spikes.

        """
        model = osim.Model(model_file)
        new_force_set = osim.ForceSet()
        force_set = model.getForceSet()
        for i in range(force_set.getSize()):
            force = force_set.get(i)
            muscle = osim.Muscle.safeDownCast(force)
            millard_muscle = osim.Millard2012EquilibriumMuscle.safeDownCast(
                force)
            thelen_muscle = osim.Thelen2003Muscle.safeDownCast(force)
            if muscle is None:
                new_force_set.adoptAndAppend(force.clone())
            elif millard_muscle is not None:
                millard_muscle = millard_muscle.clone()
                millard_muscle.set_ignore_tendon_compliance(True)
                new_force_set.adoptAndAppend(millard_muscle)
            elif thelen_muscle is not None:
                millard_muscle = osim.Millard2012EquilibriumMuscle()
                # properties
                millard_muscle.set_default_activation(
                    thelen_muscle.getDefaultActivation())
                millard_muscle.set_activation_time_constant(
                    thelen_muscle.get_activation_time_constant())
                millard_muscle.set_deactivation_time_constant(
                    thelen_muscle.get_deactivation_time_constant())
                # millard_muscle.set_fiber_damping(0)
                # millard_muscle.set_tendon_strain_at_one_norm_force(
                #     thelen_muscle.get_FmaxTendonStrain())
                millard_muscle.setName(thelen_muscle.getName())
                millard_muscle.set_appliesForce(thelen_muscle.get_appliesForce())
                millard_muscle.setMinControl(thelen_muscle.getMinControl())
                millard_muscle.setMaxControl(thelen_muscle.getMaxControl())
                millard_muscle.setMaxIsometricForce(
                    thelen_muscle.getMaxIsometricForce())
                millard_muscle.setOptimalFiberLength(
                    thelen_muscle.getOptimalFiberLength())
                millard_muscle.setTendonSlackLength(
                    thelen_muscle.getTendonSlackLength())
                millard_muscle.setPennationAngleAtOptimalFiberLength(
                    thelen_muscle.getPennationAngleAtOptimalFiberLength())
                millard_muscle.setMaxContractionVelocity(
                    thelen_muscle.getMaxContractionVelocity())
                # millard_muscle.set_ignore_tendon_compliance(
                #     thelen_muscle.get_ignore_tendon_compliance())
                millard_muscle.set_ignore_tendon_compliance(True)
                millard_muscle.set_ignore_activation_dynamics(
                    thelen_muscle.get_ignore_activation_dynamics())
                # muscle path
                pathPointSet = thelen_muscle.getGeometryPath().getPathPointSet()
                geomPath = millard_muscle.updGeometryPath()
                for j in range(pathPointSet.getSize()):
                    pathPoint = pathPointSet.get(j).clone()
                    geomPath.updPathPointSet().adoptAndAppend(pathPoint)

                # append
                new_force_set.adoptAndAppend(millard_muscle)
            else:
                raise RuntimeError(
                    'cannot handle the type of muscle: ' + force.getName())

        new_force_set.printToXML(os.path.join(target_folder, 'muscle_set.xml'))


    def subject_specific_isometric_force(generic_model_file, subject_model_file,
                                        height_generic, height_subject):
        """Adjust the max isometric force of the subject-specific model based on results
        from Handsfield et al. 2014 [1] (equation from Fig. 5A). Function adapted
        from Rajagopal et al. 2015 [2].

        Given the height and mass of the generic and subject models, we can
        calculate the total muscle volume [1]:

        V_total = 47.05 * mass * height + 1289.6

        Since we can calculate the muscle volume and the optimal fiber length of the
        generic and subject model, respectively, we can calculate the force scale
        factor to scale the maximum isometric force of each muscle:

        scale_factor = (V_total_subject / V_total_generic) / (l0_subject / l0_generic)

        F_max_i = scale_factor * F_max_i

        [1] http://dx.doi.org/10.1016/j.jbiomech.2013.12.002
        [2] http://dx.doi.org/10.1109/TBME.2016.2586891

        """
        model_generic = osim.Model(generic_model_file)
        state_generic = model_generic.initSystem()
        mass_generic = model_generic.getTotalMass(state_generic)

        model_subject = osim.Model(subject_model_file)
        state_subject = model_subject.initSystem()
        mass_subject = model_subject.getTotalMass(state_subject)

        # formula for total muscle volume
        V_total_generic = 47.05 * mass_generic * height_generic + 1289.6
        V_total_subject = 47.05 * mass_subject * height_subject + 1289.6

        for i in range(0, model_subject.getMuscles().getSize()):
            muscle_generic = model_generic.updMuscles().get(i)
            muscle_subject = model_subject.updMuscles().get(i)

            l0_generic = muscle_generic.getOptimalFiberLength()
            l0_subject = muscle_subject.getOptimalFiberLength()

            force_scale_factor = (V_total_subject / V_total_generic) / (l0_subject /
                                                                        l0_generic)
            muscle_subject.setMaxIsometricForce(force_scale_factor *
                                                muscle_subject.getMaxIsometricForce())

        model_subject.printToXML(subject_model_file)

    def hide_muscles(self, model_file_path, hide = True):
        
        """Hide or show all muscles in the OpenSim model file.

        Parameters
        ----------
        model_file_path: str
            path to the OpenSim model file (.osim)
        hide: bool
            True to hide muscles, False to show muscles

        """
        model = osim.Model(model_file_path)
        for i in range(model.getMuscles().getSize()):
            muscle = model.updMuscles().get(i)

        model.printToXML(model_file_path)    
    ####


# Project specific command line interface
class Organise():
    def __init__(self):
        pass

    def open_dir_in_explorer(self):
        'Open the models and simulations directory in file explorer in the same window'

        try:
            # Open the first directory
            os.startfile(POWERLIFTING_DIR)
            time.sleep(0.5)  # Small delay to ensure first window opens

        except Exception as e:
            print(f"Error opening directories: {e}")


    def rename_files_in_dir(self):
        dir_path = input("Enter directory path: ").strip('"')
        old_str = input("Enter string to be replaced: ")
        new_str = input("Enter new string: ")
        rename_all_files_in_dir(dir_path, old_str, new_str)

# Deferred imports to break circular dependency
# (these modules import utils, so they must load AFTER utils is fully defined)
try:
    from . import openSim as _openSim_mod
    openSim = _openSim_mod
except (ImportError, ValueError):
    try:
        import importlib.util as _ilu
        _op_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openSim.py')
        _op_spec = _ilu.spec_from_file_location('openSim', _op_path)
        _op_mod = _ilu.module_from_spec(_op_spec)
        sys.modules['openSim'] = _op_mod
        _op_spec.loader.exec_module(_op_mod)
        openSim = _op_mod
    except Exception:
        openSim = None

try:
    # Load utils/ceinms.py explicitly — `import ceinms` would grab the
    # utils/ceinms/ binary package instead (package takes precedence over
    # the .py module when both share the same name).
    import importlib.util as _ilu_c
    _ceinms_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ceinms.py')
    _ceinms_spec = _ilu_c.spec_from_file_location('ceinms_py', _ceinms_py_path)
    _ceinms_mod = _ilu_c.module_from_spec(_ceinms_spec)
    _ceinms_spec.loader.exec_module(_ceinms_mod)
    ceinms = _ceinms_mod
    HAS_CEINMS = True
except Exception:
    HAS_CEINMS = False
    ceinms = None

try:
    import emg_normalise as _emg_mod
    emg_normalise = _emg_mod
    HAS_EMG_NORMALISE = True
except ImportError:
    HAS_EMG_NORMALISE = False
    emg_normalise = None
