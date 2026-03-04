# from logging import root
import math
import os
import shutil
import subprocess
import time
import sys
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.offsetbox import AnchoredText
import webbrowser

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk

import numpy as np
import pandas as pd

import xml.etree.ElementTree as ET
import xml.dom.minidom

import opensim as osim

import c3d
from scipy import signal

import ceinms
import openSim


CODE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(CODE_DIR)

# For new projects, create a new folder in SetupFiles and update the path here 
SETUP_DIR = os.path.join(CODE_DIR, 'SetupFiles')
POWERLIFTING_DIR = os.path.dirname(CODE_DIR)
MODELS_DIR = os.path.join(POWERLIFTING_DIR, 'models')

SIMULATIONS_DIR = os.path.join(POWERLIFTING_DIR, 'simulations')
RESULTS_DIR = os.path.join(POWERLIFTING_DIR, 'results')
TASK_FIGURES_DIR = os.path.join(RESULTS_DIR, 'task_figures')

CEINMS_DIR = os.path.join(CODE_DIR, 'executables')
CEINMS_EXE = os.path.join(CEINMS_DIR, 'CEINMS.exe')
CEINMS_OPTIMISE_EXE = os.path.join(CEINMS_DIR, 'CEINMSoptimise.exe')
CEINMS_CALIBRATION_EXE = os.path.join(CEINMS_DIR, 'ceinms-nn-calibrate.exe')   

PRINT_TERMINAL = False

class Inputs:
    def __init__(self, parentdir=None):
        
        self.setup_dir = os.path.join(SETUP_DIR, 'Purzel')
        self.model_name = 'scaled.osim'
        self.model_dir = ''
        self.time_range = '0.00 1.00'
        self.c3d = 'c3dfile.c3d'
        self.emg = 'emg.mot'
        self.grf_mot = 'grf.mot'
        self.markers = 'marker_experimental.trc'
        self.events = 'events.csv'
        
        # setups 
        self.setup_ik = 'setup_IK.xml'
        self.setup_grf = 'GRF.xml'   
        self.setup_id = 'setup_ID.xml'
        self.setup_ma = 'setup_MA.xml'
        self.actuators_so = 'actuators_so.xml' 
        self.setup_so = 'setup_SO.xml'
        self.jra_forces = 'SO_StaticOptimization_force.sto'
        self.setup_jra = 'setup_JRA.xml'
        
        self.ceinms_excitations = self.emg
        self.ceinms_uncalibrated_model= '..\subjectUncalibrated.xml'
        self.ceinms_calibrated_model = '..\subjectCalibrated.xml'
        self.ceinms_calibration_cfg = '..\calibrationCfg.xml'
        self.ceinms_calibration_setup = '..\calibrationSetup.xml'
        self.ceinms_input_data = 'inputData.xml'
        self.ceinms_excitation_generator = '..\excitationGenerator.xml'
        
        self.ceinms_optimise_setup = 'ceinms_setup_optimise.xml'
        self.ceinms_optimise_cfg = 'ceinms_cfg_optimise.xml'
        
        self.ceinms_exe_cfg = 'ceinms_cfg.xml'
        self.ceinms_exe_setup = 'ceinms_setup.xml'
        
        self.ik = 'joint_angles.mot'
        self.model_markers = '_ik_model_marker_locations.sto'
        self.id = 'inverse_dynamics.sto'
        self.ma = 'muscleAnalysis'
        self.so_forces = 'SO_StaticOptimization_force.sto'
        self.so_activations = 'SO_StaticOptimization_activation.sto'
        self.jra = 'Analyse_JRA_ReactionLoads_SO.sto'
        
        self.ceinms_calibration_dir = '..\calibrationOutput'
        self.ceinms_optimisation_dir = 'Optimised'
        self.ceinms_exe_dir = 'Execution'
        
        self.jra_forces_ceinms = os.path.join(self.ceinms_optimisation_dir, 'MuscleForces.sto')
        self.jra_ceinms = 'Analyse_JRA_ReactionLoads_CEINMS.sto'
        
        if parentdir:
            for attr, filename in self.__dict__.items():
                # filepath = os.path.join(parentdir, filename)
                filepath = Path(parentdir) / filename
                try:
                    relpath = os.path.relpath(filepath, parentdir)
                except Exception as e:
                    breakpoint()
                # relpath = os.path.relpath(filepath, parentdir)
                setattr(self, attr, relpath)
                
    def check(self, parentdir):
        fileExist = {}
        for attr, filename in self.__dict__.items():
            filepath = os.path.join(parentdir, filename)
            
            if not os.path.exists(filepath):
                print(f'Warning: Input file {filename} not found in {parentdir}')
                fileExist[attr] = False
            else:
                fileExist[attr] = True
        
        return fileExist    

class Analyse(Inputs):
    '''
    Contains paths from the user settings and functions to implement in the OpenSim/Ceinms analysis
    
    subject_name: Name of the subject (or the trial path if session_name and trial_name are None)
    '''
    def __init__(self, trialPath=None):
        
        self.replace = False
        self.path = os.path.abspath(trialPath)
        self.settingsXML = 'trial_settings.xml'
        
        if not os.path.exists(trialPath):
            print_to_log(f"Trial path not found: {trialPath}")
            os.makedirs(trialPath)
            self.reset_settings_xml()
            return
        
        else:
            os.chdir(self.path)
            
            try:
                self.load_settings(self.settingsXML)
            except:
                print_to_log("Settings XML not found or could not be loaded. Creating new settings XML.")
                self.reset_settings_xml()
        
        time.sleep(1)
                  
    def reset_settings_xml(self):
        '''Create a settings xml for the trial at the specified path'''
        os.chdir(self.path)
        # delete existing settings xml if it exists
        if os.path.exists(self.settingsXML):
            os.remove(self.settingsXML)
            print_to_log(f"Existing settings XML deleted: {self.settingsXML}")
        
        path_parts = os.path.normpath(self.path).split(os.sep)
        self.subject = path_parts[-3]
        self.session = path_parts[-2]
        self.trial = path_parts[-1]

        self.parentdir = os.path.dirname(self.path)

        self._update_model()
        self._update_emg_tag() 
        
        self.body_mass = None # Placeholder, will be updated from the model if possible
        self.time_range = None
        
        # add each Input to the trial settings
        inputs = Inputs(parentdir=self.path)
        for varInput in inputs.__dict__.items():
            filepath = os.path.join(self.path, varInput[1])
            if varInput[0] in ['model_dir', 'model_name']:
                continue
            if os.path.exists(filepath):
                setattr(self, varInput[0], os.path.relpath(filepath, self.path))
            else:
                setattr(self, varInput[0], varInput[1])
            
        # add each of the CEINMS parameters
        ceinms_params = ceinms.TemplateParameters()
        for varParam in ceinms_params.__dict__.items():
            setattr(self, varParam[0], varParam[1])
        

        # Update from data 
        try:
            self.body_mass = self.get_body_mass()  
            self.time_range = self.get_time_range()
        except Exception as e:
            print_to_log(f"Error updating from data: {e}", terminal=True)

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
    
    def _update_model(self):
        '''
        update the model path in the xml settings
        '''

        if self.subject == 'Athlete_03':
            self.update_model('scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_Lernagopal':
            self.update_model('scaled_lockedCoords_opt_N10_unlockedCoords_increased_3.00.osim')

        elif self.subject == 'Athlete_03_Lernagopal_optimised':
            self.update_model('lernagopal_with_wrapings_scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_MRI_Katya':
            self.update_model('scaled_opt_N10_increased_3.00.osim')

        elif self.subject == 'Athlete_03_GPK':
            self.update_model('GPK_scaled.osim')

        elif self.subject == '022':
            self.update_model('022_Rajagopal2015_FAI_originalMass_opt_N10_hans.osim')
        else:
            self.update_model('scaled.osim')

    def _update_emg_tag(self):
        '''Update settingd XML with specific EMG types for a trial if needed'''
        if os.path.exists(os.path.join(self.path, 'EMG_filtered_normalised_scaled_0.70.sto')):
            emg_name = 'EMG_filtered_normalised_scaled_0.70.sto'
        elif os.path.exists(os.path.join(self.path, 'EMG_filtered_normalised.sto')):
            emg_name = 'EMG_filtered_normalised.sto'
        else:
            emg_name = Inputs().emg

        self.update_trial_attribute('emg', emg_name)
        self.update_trial_attribute('ceinms_excitations', emg_name)

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
                converted_value = [float(t) for t in var_value.strip('[]').split(', ')]
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
    
    def _trial_type(self):

        if self.trial.lower().__contains__('squat'):
            return 'squatting'

    def get_time_range(self):
        os.chdir(self.path)

        try:
            event_data = pd.read_csv(self.events, index_col=None, header=None)
            self.time_range = [event_data.iloc[:, 1].min(), event_data.iloc[:, 1].max()]
            return self.time_range
        except:
            pass

        try:
            marker_data = load_any_data_file(self.markers)
            self.time_range = [marker_data['time'].min(), marker_data['time'].max()]
            return self.time_range
        except:
            pass

        try:
            if os.path.exists(self.c3d):
                c3d_data = load_any_data_file(self.c3d)
                self.time_range = [c3d_data['time'].min(), c3d_data['time'].max()]
                return self.time_range
        except:
            pass

    def update_trial_attribute(self, attr_name, new_value):      
        '''Update a specific attribute of the trial and save to XML'''
        setattr(self, attr_name, new_value)
        print_to_log(f'Updated {attr_name} to {new_value} for trial at {self.path}')
        self._to_xml()
    
    def delete_trial_attribute(self, attr_name):
        '''Delete a specific attribute of the trial and save to XML'''
        if hasattr(self, attr_name):
            delattr(self, attr_name)
            print_to_log(f'Deleted attribute {attr_name} for trial at {self.path}')
            self._to_xml()
        else:
            print_to_log(f'Attribute {attr_name} not found in trial at {self.path}')

    def copy_input_files(self, src_subject, replace=False):
        """
        Copy input files from a template subject to the trial directory if they don't already exist or if replace is True.

        

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
        
        new_model_name: name of the new model file (should be located in MODELS_DIR/subject/session/)
        
        '''
        
        model_path = os.path.join(MODELS_DIR, self.subject, self.session, new_model_name)
        rel_model_path = os.path.relpath(model_path, self.path)

        self.model_name = new_model_name
        self.model_dir = rel_model_path
        print_to_log(f'Updated model path to {model_path} for trial at {self.path}')
        self._to_xml()

        return self.model_dir

    def increase_muscle_force(self, factor=1):
        """Increase muscle force in the scaled model by a given factor.
        
        Args:
            factor (float): Factor to increase muscle force by. Default is 1.5.
            replace (bool): Whether to replace existing modified model. Default is False.
        """
        os.chdir(self.path)
        
        if not os.path.exists(self.model_dir):
            print(f"Scaled model not found: {self.model_dir}")
            return

        new_model_path = self.model_dir.replace('.osim', f'_increased_{factor:.2f}.osim')
        
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
            original_force = muscle.getMaxIsometricForce()
            new_force = original_force * factor
            muscle.setMaxIsometricForce(new_force)
            print(f"Muscle: {muscle.getName()}, Original Force: {original_force:.2f}, New Force: {new_force:.2f}")
        
        # Save the modified model
        model.printToXML(new_model_path)
        print(f"Modified model saved to: {new_model_path}")
        
        # Update the used model path
        self.model_dir = new_model_path
        self._to_xml()

    def get_body_mass(self):
        """Retrieve body mass from the scaled model.
        
        Returns:
            float: Body mass in kg.
        """
        os.chdir(self.path)
        
        if not os.path.exists(self.model_dir):
            print(f"Scaled model not found: {self.model_dir}")
            return 'Unknown'

        # Load the model
        model = osim.Model(self.model_dir)
        state = model.initSystem()
        
        body_mass = model.getTotalMass(state)
        print(f"Body mass from model: {body_mass:.2f} kg")
        return body_mass
    
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
            new_range (list): New range of motion as [min, max] in degrees.
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
        
    def export_c3d(self):
        import exportC3D
        
        print("Exporting C3D file...")
        
        os.chdir(self.path) 
        if not os.path.exists(self.C3D):
            print(f"C3D file not found: {self.C3D}")
            return
        exportC3D.main(trial=self.C3D)
        
    def run_ik(self):
        os.chdir(os.path.abspath(self.path))
 
        # Create IK setup file if it doesn't exist or if replace is True
        if not os.path.exists(self.setup_ik) or self.replace:  
               
            openSim.create_setup_IK(osim_modelPath=self.model_dir,
                                marker_trc=self.markers,
                                ik_output=self.ik,
                                taskSetPath=None,
                                time_range=self.time_range,
                                saveXMLPath=self.setup_ik)
        else:
            print_to_log(f'Inverse Kinematics output already exists: {self.ik}')
            return
        
        if os.path.exists(self.ik) and not self.replace:
            print(f'Inverse Kinematics output already exists: {self.ik}')
            return

        # Run IK using OpenSim API
        try:
            openSim.run_ik(osim_modelPath=self.model_dir,
                    marker_trc=self.markers,
                    ik_output=self.ik,
                    setup_xml=self.setup_ik,
                    time_range=self.time_range,
                    resultsDir=self.path)
            
            print_to_log(f'[Success] Inverse Kinematics completed. Results are saved in {self.path}')
        except Exception as e:
            print_to_log(f'[Error] during Inverse Kinematics: {e}')
        
        # Plot IK results and marker errors
        try:
            self.plot_ik()
            self.compare_marker_locations()
            print_to_log(f'[Success] IK results plotted and saved in {self.path}')
        except Exception as e:
            print_to_log(f'[Error] during IK plotting: {e}')

    def run_id(self):
        
        os.chdir(self.path)

        if not os.path.exists(self.setup_grf):            
            template_grf_path = os.path.join(self.setup_dir, self.setup_grf)
            shutil.copyfile(template_grf_path, self.setup_grf)

        if os.path.exists(self.id) and not self.replace:
            print_to_log(f'Inverse Dynamics output already exists: {self.id}')
            return
        
        # Run ID using OpenSim API
        try:
            openSim.run_id(osimModelPath=self.model_dir,
                    ikOutputPath=self.ik,
                    grfXmlPath=self.setup_grf,
                    setupXmlPath=self.setup_id)
            
            print_to_log(f'[Success] Inverse Dynamics completed. Results are saved in {self.id}')
        except Exception as e:
            print_to_log(f'[Error] during Inverse Dynamics: {e}')

        # Plot ID results
        try:
            self.plot_id()
            print_to_log(f'[Success] ID results plotted and saved in {self.path}')
        except Exception as e:
            print_to_log(f'[Error] during ID plotting: {e}')

    def run_ma(self):
        
        os.chdir(self.path)
        if os.path.exists(self.ma) and not self.replace:
            print_to_log(f'Muscle Analysis output already exists: {self.ma}')
            return
        
        try:
            openSim.run_ma(osim_modelPath=self.model_dir,
                        ik_output=self.ik,
                        grf_xml=self.setup_grf)
            print_to_log(f'[Success] Muscle Analysis completed. Results are saved in {self.ma}')
        except Exception as e:
            print_to_log(f'[Error] during Muscle Analysis: {e}')
    
    def run_so(self):
        os.chdir(self.path)

        if not os.path.exists(self.actuators_so):          
            template_actuators_path = os.path.join(self.setup_dir, self.actuators_so)
            shutil.copyfile(template_actuators_path, self.actuators_so)
        
        if os.path.exists(self.so_forces) and not self.replace:
            print_to_log(f'Static Optimization output already exists: {self.so_forces}')
            return
        
        try:
            openSim.run_so(osim_modelPath=self.model_dir,
                    ik_output=self.ik,
                    grf_xml=self.setup_grf,
                    setup_xml=self.setup_so,
                    actuators=self.actuators_so,
                    resultsDir=self.path)
            
            print_to_log(f'[Success] Static Optimization completed. Results are saved in:')
            print_to_log(f' - Forces: {os.path.abspath(self.so_forces)}')
            print_to_log(f' - Activations: {os.path.abspath(self.so_activations)}')
        except Exception as e:
            print_to_log(f'[Error] during Static Optimization: {e}')
        
        # Plot SO results
        try:
            self.plot_so()
            print_to_log(f'[Success] SO results plotted and saved in {self.path}')
        except Exception as e:
            print_to_log(f'[Error] during SO plotting: {e}')

    def run_jra(self):
        os.chdir(self.path)
        self.load_settings(self.settingsXML)

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, self.setup_jra)
            shutil.copyfile(template_jra_path, self.setup_jra)
             
        if os.path.exists(self.jra) and not self.replace:
            return
        try:
            openSim.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra,
                     actuators=None,
                     muscle_force_path=self.jra_forces,
                     saveFileName=self.jra)
        
            print_to_log(f"JRA analysis complete. Results saved {os.path.abspath(self.jra)}")
        except Exception as e:
            print_to_log(f'[Error] during Joint Reaction Analysis: {e}')
            
    def run_jra_ceinms(self):
        os.chdir(self.path)
        self.load_settings(self.settingsXML)

        if not os.path.exists(self.setup_jra):
            template_jra_path = os.path.join(self.setup_dir, self.setup_jra)
            shutil.copyfile(template_jra_path, self.setup_jra)

        if os.path.exists(self.jra_ceinms) and not self.replace:
            print_to_log(f'JRA CEINMS output already exists: {self.jra_ceinms} and replace is set to False.')
            return
        
        try:
            openSim.run_jra(osim_modelPath=self.model_dir,
                     ik_output=self.ik,
                     grf_xml=self.setup_grf,
                     setup_xml=self.setup_jra,
                     actuators=None,
                     muscle_force_path=self.jra_forces_ceinms,
                     saveFileName=self.jra_ceinms)
            
            print_to_log(f"JRA CEINMS analysis complete. Results saved {os.path.abspath(self.jra_ceinms)}")
        except Exception as e:
            print_to_log(f'[Error] during Joint Reaction Analysis CEINMS: {e}')
        
    def run_emg_normalise(self):
        
        os.chdir(self.path)
        emg_normalise_list = []
        
        for trialName in os.listdir(self.parentdir):
            emgPath = os.path.join(self.parentdir, trialName, self.emg_filtered)
            if os.path.exists(emgPath):
                emg_normalise_list.append(emgPath)
                
        if not emg_normalise_list:
            print_to_log(f'[Error] No EMG files found to normalise in {self.parentdir}')
            return
        
        openSim.run_emg_normalise(target_emg_path= str(self.emg_filtered),
                                normalise_emg_list=emg_normalise_list)
    
    def convert_mot_to_sto(self, attr=None):

        os.chdir(self.path)
        if attr:
            mot_file = getattr(self, attr)
        
        sto_file_path = mot_file.replace('.mot', '.sto')
        if os.path.exists(sto_file_path) and not self.replace:
            print_to_log(f'STO file already exists: {sto_file_path}')
            return
        
        sto_file_path = openSim.convert_mot_to_sto(mot_file_path=os.path.abspath(mot_file))

        self.update_trial_attribute(attr, os.path.relpath(sto_file_path, self.path))

    @staticmethod
    def muscles_per_coordinate(osimModel, coord_name):
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
    
    #--- Valid
    def compare_marker_locations(self):
        os.chdir(self.path)
        try:
            openSim.compare_marker_locations(marker_experimental_path=os.path.abspath(self.markers),marker_virtual_path=os.path.abspath('.\\_ik_model_marker_locations.sto'))
        
            print_to_log(f'[Success] Marker location comparison completed: {self.model_markers} vs {self.markers}')
        except Exception as e:
            print_to_log(f'[Error] during marker location comparison: {e}')
    
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
        
        fig.suptitle(f"Inverse Kinematics Joint Angles: {self.trial}", fontsize=16)
        for var in columns_to_plot:
            ax = axes[columns_to_plot.index(var)]
            ax.plot(self.joint_angles['time'], self.joint_angles[var], label=self.trial)
            ax.set_title(f"{var}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Angle (degrees)")
        
        axes[0].legend()
        
        # save figure and return
        plt.savefig(os.path.join(self.path, f"{self.trial}_IK_Joint_Angles.png"))
        print(f'Figure saved to {os.path.join(self.path, f"{self.trial}_IK_Joint_Angles.png")}')
        
        return fig, axes
    
    def plot_id(self, columns_to_plot='all'):
        self.inverse_dynamics = load_any_data_file(self.id)
        
        if columns_to_plot == 'all':
            columns_to_plot = list(self.inverse_dynamics.columns)
            columns_to_plot.remove('time')
        
        n_vars = len(columns_to_plot)
        fig, axes = self.plot_create_subplot(n_vars)
        
        fig.suptitle(f"Inverse Dynamics Joint Moments: {self.trial}", fontsize=16)
        for var in columns_to_plot:
            ax = axes[columns_to_plot.index(var)]
            ax.plot(self.inverse_dynamics['time'], self.inverse_dynamics[var], label=self.trial)
            ax.set_title(f"{var}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Moment (Nm)")
        
        axes[0].legend()
        
        # save figure and return
        plt.savefig(os.path.join(self.path, f"{self.trial}_ID_Joint_Moments.png"))
        print(f'Figure saved to {os.path.join(self.path, f"{self.trial}_ID_Joint_Moments.png")}')
        
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


        coordinates = {'hip_flexion': None, 'hip_adduction': None, 'hip_rotation': None,
                        'knee_flexion': None, 'knee_adduction': None, 'knee_rotation': None,
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
        fig, axes = plt.subplots(n_vars//2, 2, figsize=(26, 10), constrained_layout=True)
        
        fig.suptitle(f"Static Optimization Muscle Forces: {self.trial}", fontsize=16)
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
        
        # Legend only for unique muscle names across all subplots
        unique_muscles = set(muscle for muscles in muscleGroups.values() for muscle in muscles)
        handles = [plt.Line2D([0], [0], color='C0', label=muscle) for muscle in unique_muscles]
        axes[0, 0].legend(handles=handles, loc='upper right', fontsize='small')
        
        # save figure and return
        save_path = os.path.join(self.path, f"{self.trial}_SO_Muscle_Forces.png")
        plt.savefig(save_path)
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
        
        fig.suptitle(f"Joint Reaction Analysis: {self.trial}", fontsize=16)
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
        emg_file_path = os.path.abspath(self.emg_plot)
        if not os.path.exists(emg_file_path):
            print(f"EMG file not found: {emg_file_path}")
            return
        
        self.emg_data = load_any_data_file(emg_file_path)
        
        muscles = self.emg_data.columns

        n_vars = len(muscles)
        fig, axes = self.plot_create_subplot(n_vars)
        
        fig.suptitle(f"EMG Excitations: {self.trial}", fontsize=16)
        for i, muscle in enumerate(muscles):
            ax = axes[i]
            ax.plot(self.emg_data['time'], self.emg_data[muscle], label=muscle)

            ax.set_title(f"{muscle}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Excitation")
            ax.set_ylim([0, 1])
            
            if i == 0:
                ax.legend(loc='upper right')
        
        # save figure and return
        savePath = emg_file_path.replace('.sto', '.png').replace('.mot', '.png')
        plt.savefig(savePath)
        print(f'Figure saved to {savePath}')

        return fig, axes
    
    def plot_summary(self):
        '''
        plot summary of all analyses for the trial
        
        row 1 - IK joint angles
        row 2 - ID joint moments and CEINMS joint moments
        row 3 - SO muscle forces and CEINMS forces
        row 4 - EMG excitations, SO activations, CEINMS activations
        row 5 - Norm Fiber lengths
        row 6 - Joint Reaction Forces
        '''
        # load all data
        self.joint_angles = load_any_data_file(self.ik)
        self.inverse_dynamics = load_any_data_file(self.id)
        self.so_forces = load_any_data_file(self.so_forces)
        self.so_activations = load_any_data_file(self.so_activations)
        self.jra_results = load_any_data_file(self.jra)
        self.emg_data = load_any_data_file(self.emg_normalised)

        setupXML = ET.parse(self.ceinms_exe_setup).getroot()
        ceinms_output_dir = os.path.join(self.path, setupXML.find('outputDirectory').text)

        self.ceinms_activations = load_any_data_file(os.path.join(ceinms_output_dir, 'Activations.sto'))
        self.ceinms_forces = load_any_data_file(os.path.join(ceinms_output_dir, 'MuscleForces.sto'))
        
        # plott
        n_rows = 6
        fig, axes = plt.subplots(n_rows, 1, figsize=(15, n_rows*4), constrained_layout=True)
        
    # ceinms
    def create_ceinms_model(self):
        os.chdir(self.path)
        if os.path.exists(self.ceinms_uncalibrated_model) and not self.replace:
            print_to_log(f'CEINMS uncalibrated model already exists: {os.path.abspath(self.ceinms_uncalibrated_model)}')
            return
        try:
            ceinms.create_ceinms_model(osimModelPath=self.model_dir, 
                                   outputCEINMSModelPath=self.ceinms_uncalibrated_model)
            print_to_log(f'[Success] CEINMS uncalibrated model created: {os.path.abspath(self.ceinms_uncalibrated_model)}')
        except Exception as e:
            print_to_log(f'[Error] Failed to create CEINMS uncalibrated model: {e}')
    
    def create_ceinms_input_data(self):
        os.chdir(self.path)
        
        try:
            ceinms.create_input_data(MAFolder=self.ma,excitationsFile=self.ceinms_excitations,motionFile=self.ik, externalTorquesFile=self.id,externalLoadsFile=self.setup_grf,startStopTime=self.time_range)
            print_to_log(f'[Success] CEINMS input data created: {os.path.abspath(self.ceinms_input_data)}')
        except Exception as e:
            print_to_log(f'[Error] Failed to create CEINMS input data: {e}')
    
    def create_ceinms_calibration_cfg(self, calibration_trial_names=None):
        """
        Create ceinms_cfg_calibration.xml for CEINMS calibration.
        """
        
        os.chdir(self.path)
        inputPaths = []
        for trial_name in calibration_trial_names:
            filepath = os.path.join(self.parentdir, trial_name, Inputs().ceinms_input_data)
            inputPaths.append(os.path.relpath(filepath, self.parentdir))
        
        ceinms.create_calibrationCfg(osimModelPath=self.model_dir,
                                     inputPaths=inputPaths,
                                     outputPath=self.ceinms_calibration_cfg)

    def create_excitation_generator(self):
        os.chdir(self.path)
        if os.path.exists(self.ceinms_excitation_generator) and not self.replace:
            print_to_log(f'CEINMS excitation generator already exists: {os.path.abspath(self.ceinms_excitation_generator)}')
            return
        
        try:
            ceinms.create_excitation_generator(osim_model_path=self.model_dir,
                                               emg_path=self.ceinms_excitations,
                                               save_path=self.ceinms_excitation_generator
            )
            print_to_log(f'[Success] CEINMS excitation generator created: {self.ceinms_excitation_generator}')
        except Exception as e:  
            print_to_log(f'[Error] Failed to create CEINMS excitation generator: {e}')
                
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
        dof_set.text = ceinms.TemplateParameters().DofSet
        
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
            print_to_log(f'CEINMS optimisation setup already exists: {os.path.abspath(self.ceinms_optimise_setup)}', terminal=True)
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
            ceinms.create_ceinms_cfg(ceinmsModelPath=self.ceinms_calibrated_model,
                                 alpha=self.alpha,
                                 beta=self.beta,
                                    gamma=self.gamma,
                                    dofSet=self.DofSet,
                                    excitationGeneratorFilePath=self.ceinms_excitation_generator,
                                    outputPath=self.ceinms_exe_cfg)
            print_to_log(f'[Success] CEINMS exe cfg created: {os.path.abspath(self.ceinms_exe_cfg)}')
        except Exception as e:
            print_to_log(f'[Error] Failed to create CEINMS executable configuration: {e}', terminal=True)

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
        
        start_time = time.time()
        os.chdir(self.path)
        
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
        mod_time = os.path.getmtime(self.ceinms_calibrated_model)
        if mod_time >= start_time:
            print_to_log(f'CEINMS calibration completed successfully in {mod_time - start_time:.2f} seconds.')
            ceinms.plot_ceinms_model_parameters(self.ceinms_calibrated_model)
            
            # plot moments vs ceinms results
            try:
                ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
                ceinms.plot_moments_calibration_results(momentResultsCSV=ceinmsTorquesFile)
                print_to_log(f'[Success] Plotted moments vs CEINMS results.')
            except:
                print_to_log(f'[ERROR] Could not plot moments vs CEINMS results.')
            
            # plot emg vs ceinms excitations using uncalibrated model as reference
            try:
                ceinms.plot_compare_ceinms_models(uncalibratedModelPath=self.ceinms_uncalibrated_model,calibratedModelPath=self.ceinms_calibrated_model)
                print_to_log(f'[Success] Plotted EMG vs CEINMS results for calibrated model: {self.ceinms_calibrated_model}')
            except:
                print_to_log(f'[ERROR] Could not plot EMG vs CEINMS results for calibrated model: {self.ceinms_calibrated_model}')
        else:
            print_to_log(f'[WARNING] CEINMS calibration may have failed: calibrated model not updated.')
            
    def run_ceinms_exe(self):
        os.chdir(self.path)

        self.load_settings(settingsXML=self.settingsXML)

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
            print_to_log(f'CEINMS executable run completed for trial: {self.trial}')
        except Exception as e:
            print_to_log(f'[Error] during CEINMS executable run: {e}')

        # update jra ceinms forces path from setup output directory
        self.update_trial_attribute('jra_forces_ceinms', os.path.join(setup.find('outputDirectory').text, 'MuscleForces.sto'))

        # check if ceinms forces file exists before trying to add so columns
        if not os.path.exists(self.jra_forces_ceinms):
            print_to_log(f'[Error] CEINMS forces file not found: {self.jra_forces_ceinms}')
            return

        # add so columns to ceinms forces
        try:
            self.add_so_columns_to_ceinms_results()
            print_to_log(f'Added SO columns to CEINMS forces for trial: {self.trial}')
        except Exception as e:
            print_to_log(f'[Error] during adding SO columns to CEINMS forces: {e}')

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
            print_to_log(f'Plotted Experimental vs CEINMS results {self.path}')
        except:
            print_to_log(f'Could not plot EMG vs CEINMS results {self.path}')
    
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
                print_to_log(f'[Error] during CEINMS executable loop: {e}')

    def check_best_ceinms_results(self):
        ''' loop through ceinms exe results and find best alpha, beta, gamma based on RMS error for joint moments and EMG vs CEINMS excitations '''
        os.chdir(self.path)

        self.load_settings(settingsXML=self.settingsXML)
        best_params_csv = os.path.join(self.path, 'best_ceinms_parameters.csv')

        if os.path.exists(best_params_csv) and not self.replace:
            print_to_log(f'Loading existing best CEINMS parameters from {best_params_csv}')
            best_params_df = pd.read_csv(best_params_csv)
        else:
            best_params_df = pd.DataFrame(columns=['alpha', 'beta', 'gamma', 'moment_rms_error', 'emg_rms_error'])
            best_params_df.to_csv(best_params_csv, index=False)
            print_to_log(f'Saved best CEINMS parameters to {best_params_csv}')

    def add_so_columns_to_ceinms_results(self):

        try:
            so_forces = load_any_data_file(self.jra_forces)
            ceinms_forces = load_any_data_file(self.jra_forces_ceinms)
        except Exception as e:
            print_to_log(f'[Error] loading SO or CEINMS forces for adding columns: {e}')
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
        print_to_log(f'[Success] Added SO columns to CEINMS forces for trial: {self.trial}')
        print(f"Updated forces saved to: {self.jra_forces_ceinms}")
        print(f"Added {len(missing_columns)} columns from SO forces")

    #--- Plot ceinms
    def plot_ceinms_calibration_results(self):

        try:
            ceinmsTorquesFile = os.path.join(self.ceinms_calibration_dir, 'Moments_inputData.csv')
            ceinms.plot_moments_calibration_results(momentResultsCSV=ceinmsTorquesFile)
            print_to_log(f'[Success] Plotted CEINMS calibration results for trial: {self.trial}')
        except Exception as e:
            print_to_log(f'[Error] during plotting CEINMS calibration results: {e}')

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
                breakpoint()
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
                print_to_log(f'[Git Status] Uncommitted changes in trial directory: {self.path}')
                isClean['trial_dir'] = False
            else:
                print_to_log(f'[Git Status] No uncommitted changes in trial directory: {self.path}')
                isClean['trial_dir'] = True
            subject_path = updir(self.path, levels=2)
            result_subject = subprocess.run(['git', 'status', '--porcelain'], check=True, stdout=subprocess.PIPE, text=False, cwd=subject_path)
            if result_subject.stdout:
                print_to_log(f'[Git Status] Uncommitted changes in subject directory: {subject_path}')
                isClean['subject_dir'] = False
            else:
                print_to_log(f'[Git Status] No uncommitted changes in subject directory: {subject_path}', terminal=True)
                isClean['subject_dir'] = True
        except subprocess.CalledProcessError as e:
            print_to_log(f'[Error] Failed to check git status: {e}')

        return isClean
    
    def push_trial_results_to_git(self):
        """Push trial results to git after completion"""
        os.chdir(self.path)
        breakpoint()
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
            print_to_log(f'[Warning] Failed to commit to git: {e}')

        try:
            subprocess.run(['git', 'push'], check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError:
            # set upstream for current branch then push
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=os.getcwd(), text=True).strip()
            subprocess.run(['git', 'push', '--set-upstream', 'origin', branch],check=True, cwd=os.getcwd())

            print_to_log(f'[Success] Results pushed to git for: {self.subject} / {self.trial}')

        except subprocess.CalledProcessError as e:
            print_to_log(f'[Warning] Failed to push to git: {e}')
        except Exception as e:
            print_to_log(f'[Warning] Git operation failed: {e}')

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
            print_to_log(f'[Warning] Failed to commit to git: {e}')

        try:
            subprocess.run(['git', 'push'], check=True, cwd=os.getcwd())
        except subprocess.CalledProcessError:
            # set upstream for current branch then push
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=os.getcwd(), text=True).strip()
            subprocess.run(['git', 'push', '--set-upstream', 'origin', branch],check=True, cwd=os.getcwd())

            print_to_log(f'[Success] Results pushed to git for subject: {self.subject}')

        except subprocess.CalledProcessError as e:
            print_to_log(f'[Warning] Failed to push to git: {e}')
        except Exception as e:
            print_to_log(f'[Warning] Git operation failed: {e}')


class Compare():
    def __init__(self):
        pass

        

## Utility functions
def updir(path, levels=1):
    """Move up a directory path by a specified number of levels."""
    for _ in range(levels):
        path = os.path.dirname(path)
    return path

def print_to_log(message, terminal=PRINT_TERMINAL):
    """
    Prints a message to the console and logs it to a file.
    
    Args:
        message (str): The message to print and log.
    """
    timestamp = time.strftime('%d.%m.%Y_%H:%M:%S', time.localtime()) + f":{int((time.time() % 1) * 1000):03d}"
    
    with open(CODE_DIR + '\\log.txt', 'a') as log_file:
        log_file.write(f'{timestamp}: {message}\n')
        
    if terminal:
        print(message)

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
    
    df = pd.read_csv(path,sep='\t',skiprows=header_start_line,index_col=False)
    
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
    df = df.iloc[2:]
    
    # if needed make 'time' lower case (only)
    if 'Time' in df.columns:
        df = df.rename(columns={'Time': 'time'})
        
    # if needed combine headers
    if combine_headers:
        df.columns = df.columns.map(lambda x: f"{x[0]}_{x[1]}" if x[1] else x[0])

    if output == 1: print(df.columns)

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
                data = pd.read_csv(path, sep= '\s+', header=i+offset)
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
        data = pd.read_csv(path, sep= '\s+', header=i+1)
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
    """Edits the value of a specific XML tag given its path."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        elem_list = root.findall(tag)
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
        if row > 0:
            ax.set_title('')
    
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

# data manipulation
def time_normalise_df(df, fs=''):

    if not type(df) == pd.core.frame.DataFrame:
        raise Exception('Input must be a pandas DataFrame')
    
    if not fs:
        try:
            # mean sampling frequency over the time column
            fs = 1/((df['time'].iloc[-1]-df['time'].iloc[0])/(len(df)-1))
        except  KeyError as e:
            raise Exception('Input DataFrame must contain a column named "time"')
    
    normalised_df = pd.DataFrame(columns=df.columns)

    for column in df.columns:
        normalised_df[column] = np.zeros(101)

        currentData = df[column]
        currentData = currentData[~np.isnan(currentData)]
        
        if currentData.empty:
            currentData = np.zeros(len(df))
        
        # time trial length of trial
        timeTrial = np.arange(0, len(currentData)/fs, 1/fs)           
        if len(timeTrial) > len(currentData):
            timeTrial = np.arange(1/fs, len(currentData)/fs, 1/fs)           
            
        Tnorm = np.arange(0, timeTrial[-1], timeTrial[-1]/101)
        
        if len(Tnorm) == 102:
            Tnorm = Tnorm[:-1]
        
        if len(timeTrial) != len(currentData):
            breakpoint()
            
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
        
        breakpoint()
        
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
            breakpoint()

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

if __name__ == "__main__":
    
    LocalFuncs = [f for f in dir() if callable(globals()[f])]
    print("Available commands:", LocalFuncs)

    # Command loop
    while True:
        command = input("Enter command: ")

        if not command in LocalFuncs:
            print("Invalid command. Please try again.")
            continue

        try:
            globals()[command]()
        except Exception as e:
            print(f"Error executing {command}: {e}")
        
# END