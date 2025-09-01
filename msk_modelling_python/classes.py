import os
import msk_modelling_python as msk
import pyperclip
import xml.dom.minidom
import xml.etree.ElementTree as ET
import unittest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.cm as cm

import tkinter as tk
import customtkinter as ctk

try:
    import opensim as osim
except:
    print('OpenSim not installed.')
    osim = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

#%% ############################################################# Basic functions #############################################################
def select_file(message = 'Select file'):
    root = tk.Tk(); root.withdraw()  # Hide the root window
    file_path = ctk.filedialog.askopenfilename(title=message)
    return file_path
class mcf: # make coding fancy
    
    def __init__(self):
        pass
            
    header = staticmethod(lambda: pyperclip.copy("#%% #############################################################\n" +
                                                 "#                        Description:                           # \n" +
                                                 "##################################################################"))

# create a class for each option so that we can print the option names
class cmd_function:
    def __init__(self, func):
        self.func = func

    def run(self, *args, **kwargs):
        self.func(*args, **kwargs)

# OSIM DATA CLASSES
class SubjectPaths:
    def __init__(self, data_folder,subject_code='default',trial_name='trial1'):

        # main paths
        self.main = data_folder
        self.setup_folder = os.path.join(self.main,'Setups')
        self.setup_ceinms = os.path.join(self.main,'Setups','ceinms')
        self.simulations = os.path.join(self.main,'Simulations')
        self.subject = os.path.join(self.simulations, subject_code)
        
        trial_path = os.path.join(self.subject, trial_name)
        self.trial = TrialPaths(trial_path)
        self.results = os.path.join(self.main, 'results')

class Project:
    '''
    
    '''
    def __init__(self, project_folder=''):

        if project_folder == 'example':
            c3dFilePath = msk.bops.get_testing_file_path()
            project_folder = os.path.abspath(os.path.join(c3dFilePath, '../../../../..'))

        elif not project_folder or not os.path.isdir(project_folder):
            msk.ut.pop_warning(f'Project folder does not exist on {project_folder}. Please select a new project folder')
            project_folder = msk.ui.select_folder('Please select project directory')
            
            if not os.path.isdir(project_folder):
                msk.ut.pop_warning(f'Project folder does not exist on {project_folder}.')             
                return
        
        self.main = project_folder
        self.simulations = os.path.join(self.main,'simulations')
        self.results = os.path.join(self.main,'results')
        self.models = os.path.join(self.main,'models')
        self.setup_files_path = os.path.join(self.main,'setupFiles')
        
        self.settings_json = os.path.join(self.main,'settings.json')

        try:
            self.subject_list = [f for f in os.listdir(self.simulations) if os.path.isdir(os.path.join(self.simulations, f))]
        except:
            self.subject_list = []
            msk.ui.select_file(message = 'No subjects in the current project folder')     

        # create a dictionary of setup files
        self.setup_files = dict()
        self.setup_files['scale'] = os.path.join(self.setup_files_path, 'setup_scale.xml')
        self.setup_files['ik'] = os.path.join(self.setup_files_path, 'setup_ik.xml')
        self.setup_files['id'] = os.path.join(self.setup_files_path, 'setup_id.xml')
        self.setup_files['so'] = os.path.join(self.setup_files_path, 'setup_so.xml')
        self.setup_files['jrf'] = os.path.join(self.setup_files_path, 'setup_jrf.xml')
        
        # analysis settings
        self.emg_labels = ['all']
        self.analog_labels = ['all']
        
        self.filters = dict()
        self.filters['emg_band_pass'] = [40,450]
        self.filters['emg_low_pass'] = [6]
        self.filters['emg_order'] = [4]
        self.filters['grf'] = None
        self.filters['markers'] = 6

        # create a list of subject paths
        self.subject_paths = []
        for subject in self.subject_list:
            self.subject_paths.append(os.path.join(self.simulations, subject))
                    
    def add_template_subject(self):
        print('Not implemented ...')
        if msk.__testing__:
            msk.bops.ghost.create_template_osim_subject(parent_dir=self.main)
        return None
    
    def create_settings_json(self):
        msk.ut.save_json_file(self.__dict__, self.settings_json)
        print('settings.json created in ' + self.main)

    def start(self, project_folder=''):
    
        if not project_folder:
            project_folder = msk.ui.select_folder('Please select project directory')
            new_project = True
        else:
            new_project = False
        
        msk.bops.create_new_project_folder(project_folder)
        
        self.main = project_folder
        
class Subject:
    # class to store subject information
    def __init__(self, subject_folder):
        self.folder = subject_folder
        self.id = os.path.basename(os.path.normpath(subject_folder))
        self.session_paths = [f.path for f in os.scandir(subject_folder) if f.is_dir()]
        self.settings_json = os.path.join(self.folder,'settings.json')
        
    def print(self):
        print('Subject ID: ' + self.id)
        print('Subject folder: ' + self.folder)
    
    def create_settings_json(self, overwrite=False):
        
        if os.path.isfile(self.settings_json) and not overwrite:
            print('settings.json already exists')
            return
        
        msk.bops.save_json_file(self.__dict__, self.settings_json)
        print('subject settings.json created in ' + self.folder)

    def get_session(self, session_name):
        if session_name is int():
            print('session name must be a string')
            return 
        else:
            session = Session(os.path.join(self.folder, session_name))
        return session

class Session:
    def __init__(self, session_path):
        self.path = session_path
        self.name = msk.src.os.path.basename(os.path.normpath(session_path))
        # get files in the session folder that are .c3d files
        self.c3d_paths = [f.path for f in os.scandir(session_path) if f.is_file() and f.name.endswith('.c3d')]
        
        # trial paths and names only for the c3d files
        self.trial_names = [os.path.basename(os.path.normpath(f)).replace('.c3d', '') for f in self.c3d_paths]
        
        self.settings_json = os.path.join(self.path,'settings.json')
        
    def create_settings_json(self, overwrite=False):        
        if os.path.isfile(self.settings_json) and not overwrite:
            print('settings.json already exists')
            return
        
        settings_dict = self.__dict__
        msk.bops.save_json_file(settings_dict, self.settings_json)
        print('session settings.json created in ' + self.path)

    def get_trial(self, trial_name):
        
        # if trial_name is an integer, use as index to get trial name
        if trial_name is int():
            trial_name = self.trial_names[trial_name]
            trial = Trial(os.path.join(self.path, trial_name))
            
        else:
            trial = Trial(os.path.join(self.path, trial_name))
            
        return trial

class Model:
    def __init__(self, model_path):
        self.osim_object = osim.Model(model_path)
        self.path = model_path
        self.xml = ET.parse(model_path)
        self.version = self.xml.getroot().get('Version') 
    
    def print(self):
        print('---')
        print('Model path: ' + self.path)
        print('Model version: ' + self.version)
        print('---')

class TrialPaths:
    def __init__(self, trial_path = ''):

        if not trial_path: 
            trial_path = msk.bops.select_folder('Select trial folder')
        
        # main paths
        self.path = trial_path
        
        # raw data paths
        self.c3d = os.path.join(self.path, 'c3dfile.c3d')
        self.grf = os.path.join(self.path, 'grf.mot')
        self.markers = os.path.join(self.path, 'marker_experimental.trc')
        self.emg = os.path.join(self.path, 'emg.csv')

        # model paths
        self.model_generic = None
        self.model_scaled = None
    
        # setup files
        self.grf_xml = os.path.join(self.path,'GRF.xml')
        self.setup_ik = os.path.join(self.path, 'setup_ik.xml')
        self.setup_id = os.path.join(self.path, 'setup_id.xml')
        self.setup_so = os.path.join(self.path, 'setup_so.xml')
        self.setup_ma = os.path.join(self.path, 'setup_ma.xml')
        self.setup_jra = os.path.join(self.path, 'setup_jra.xml')
        
        # output paths
        self.ik_output = os.path.join(self.path, 'ik.mot')
        self.id_output = os.path.join(self.path, 'inverse_dynamics.sto')
        self.ma_output_folder = os.path.join(self.path, 'muscle_analysis')

        self.so_output_forces = os.path.join(self.path, 'muscle_forces.sto')
        self.so_output_activations = os.path.join(self.path, 'muscle_activations.sto')
        self.so_actuators = os.path.join(self.path, 'actuators_so.xml')

        self.jra_output = os.path.join(self.path, 'joint_raction_loads.sto')
        
        # CEINMS paths
        current_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ceinms_src = os.path.join(current_folder, 'ceinms2')
        if not os.path.isdir(self.ceinms_src):
            raise Exception('CEINMS source folder not found: {}'.format(self.ceinms_src))

        # subject files (model, excitation generator, calibration setup, trial xml)
        self.uncalibrated_subject = os.path.join(self.path,'ceinms','ceinms_uncalibrated_subject.xml') 
        self.calibrated_subject = os.path.join(self.path,'ceinms','ceinms_calibrated_subject.xml')
        self.ceinms_exc_generator = os.path.join(self.path,'ceinms','ceinms_excitation_generator.xml')
        self.ceinms_calibration_setup = os.path.join(self.path,'ceinms' ,'ceinms_calibration_setup.xml')
        
        # trial files (trial xml, ceinms_exe_setup, ceinms_exe_cfg)
        self.ceinms_trial_exe = os.path.join(self.path,'ceinms_trial.xml')
        self.ceinms_trial_cal = os.path.join(self.path,'ceinms_trial_cal.xml')
        self.ceinms_exe_setup = os.path.join(self.path, 'ceinms_exe_setup.xml')
        self.ceinms_exe_cfg = os.path.join(self.path, 'ceinms_exe_cfg.xml')

        # results folder
        self.ceinms_results = os.path.join(self.path, 'ceinms_results')
        self.ceinms_results_forces = os.path.join(self.ceinms_results,'MuscleForces.sto')
        self.ceinms_results_activations = os.path.join(self.ceinms_results,'Activations.sto')

    def add_model_generic(self, model_path):
        self.model_generic = model_path
        
    def add_model_scaled(self, model_path):
        self.model_scaled = model_path

class osimTools:
    def __init__(self):
        pass
    
    def print_osim_info():
        print('Osim module version: ' + osim.__version__)
        print('Osim module path: ' + osim.__file__)
        
    def create_analysis_tool(coordinates_file, modelpath, results_directory, force_set_files=None):
        # Get mot data to determine time range
        motData = osim.Storage(coordinates_file)

        # Get initial and final time
        initial_time = motData.getFirstTime()
        final_time = motData.getLastTime()

        # Set the model
        model = osim.Model(modelpath)

        # Create AnalyzeTool
        analyzeTool = osim.AnalyzeTool()
        analyzeTool.setModel(model)
        analyzeTool.setModelFilename(model.getDocumentFileName())

        analyzeTool.setReplaceForceSet(False)
        analyzeTool.setResultsDir(results_directory)
        analyzeTool.setOutputPrecision(8)

        if force_set_files is not None:  # Set actuators file
            forceSet = osim.ArrayStr()
            forceSet.append(force_set_files)
            analyzeTool.setForceSetFiles(forceSet)

        # motData.print('.\states.sto')
        # states = osim.Storage('.\states.sto')
        # analyzeTool.setStatesStorage(states)
        analyzeTool.setInitialTime(initial_time)
        analyzeTool.setFinalTime(final_time)

        analyzeTool.setSolveForEquilibrium(False)
        analyzeTool.setMaximumNumberOfSteps(20000)
        analyzeTool.setMaxDT(1)
        analyzeTool.setMinDT(1e-008)
        analyzeTool.setErrorTolerance(1e-005)

        analyzeTool.setExternalLoadsFileName('.\GRF.xml')
        analyzeTool.setCoordinatesFileName(coordinates_file)
        analyzeTool.setLowpassCutoffFrequency(6)

        return analyzeTool

    def get_muscles_by_group_osim(xml_path, group_names = 'all'): # olny tested for Catelli model Opensim 3.3
        members_dict = {}

        try:
            with open(xml_path, 'r', encoding='utf-8') as file:
                tree = ET.parse(xml_path)
                root = tree.getroot()
        except Exception as e:
            print('Error parsing xml file: {}'.format(e))
            return members_dict
        
        if group_names == 'all':
            # Find all ObjectGroup names
            group_names = [group.attrib['name'] for group in root.findall(".//ObjectGroup")]


        members_dict['all_selected'] = []
        for group_name in group_names:
            members = []
            for group in root.findall(".//ObjectGroup[@name='{}']".format(group_name)):
                members_str = group.find('members').text
                members.extend(members_str.split())
            
            members_dict[group_name] = members
            members_dict['all_selected'] = members_dict['all_selected'] + members 

        return members_dict

    def get_muscle_per_coordinate(model_path, coordinates = 'all'):
        '''
        This function returns the muscles that are actuating the given coordinates. 
        The function uses the OpenSim API to get the coordinates and the muscles in the model.
        The function returns a dictionary with the coordinates as keys and the muscles as values.
        '''
        # Load the OpenSim model
        model = osim.Model(model_path)
        model.initSystem()

        # Get all coordinates in the model
        coordinate_set = model.getCoordinateSet()
        
        if coordinates == 'all':
            coordinates = [coordinate_set.get(i).getName() for i in range(coordinate_set.getSize())]

        # Get all muscles in the model
        muscle_set = model.getMuscles()
        
        # Create a dictionary to store muscles for each coordinate
        muscles_per_coordinate = {}

        # Loop through each coordinate and find its actuating muscles
        for coord_name in coordinates:
            coord = coordinate_set.get(coord_name)
            actuating_muscles = []
            for i in range(muscle_set.getSize()):
                muscle = muscle_set.get(i)
                if muscle.isActuating(coord):
                    actuating_muscles.append(muscle.getName())
            muscles_per_coordinate[coord_name] = actuating_muscles

        return muscles_per_coordinate
    
    def increase_max_isometric_force(self, model_path, factor): # opensim API
        # Load the OpenSim model
        model = osim.Model(model_path)

        # Loop through muscles and update their maximum isometric force
        for muscle in model.getMuscles():
            current_max_force = muscle.getMaxIsometricForce()
            new_max_force = current_max_force * factor
            muscle.setMaxIsometricForce(new_max_force)

        # Save the modified model
        output_model_path = model_path.replace('.osim', f'_increased_force_{factor}.osim')
        model.printToXML(output_model_path)

        print(f'Model with increased forces saved to: {output_model_path}')

    def update_max_isometric_force_xml(xml_file, factor,output_file = ''): # xml
        # Parse the XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Find all Millard2012EquilibriumMuscle elements
        muscles = root.findall('.//Millard2012EquilibriumMuscle')

        # Update max_isometric_force for each muscle
        n = 0
        for muscle in muscles:
            max_force_element = muscle.find('./max_isometric_force')
            if max_force_element is not None:
                current_max_force = float(max_force_element.text)
                new_max_force = current_max_force * factor
                max_force_element.text = str(new_max_force)
                n = 1
        if n == 0:
            print('No Millard2012EquilibriumMuscle elements found in the XML file.')
            
        # Save the modified XML file
        if not output_file:
            output_xml_file = xml_file.replace('.xml', f'_updated.xml')
        else:
            output_xml_file = output_file
            
        tree.write(output_xml_file)

        print(f'Modified XML saved to: {output_xml_file}')
        
    def reorder_markers(xml_path, order):
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Create a dictionary to store marker elements by name
        # markers_dict = {marker.find('name').text: marker for marker in root.findall('.//Marker')}

        # Create a new MarkerSet element to replace the existing one
        new_marker_set = ET.Element('MarkerSet')
        # Create the 'objects' element
        objects_element = ET.SubElement(new_marker_set, 'objects')    
        groups_element = ET.SubElement(new_marker_set, 'groups')    

        # Add Marker elements to the new MarkerSet in the specified order
        for marker_name in order:
            existing_marker = root.find('.//Marker[@name="' + marker_name + '"]')
            if existing_marker:
                objects_element.append(existing_marker)

        # Replace the existing MarkerSet with the new one
        existing_marker_set = root.find('.//MarkerSet')
        existing_marker_set.clear()
        existing_marker_set.extend(new_marker_set)

        # Save the modified XML back to a file
        tree.write(xml_path)

    def copy_marker_locations(model_path1,model_path2,marker_names='all',marker_common_frame='RASI'):
        '''
        This function copies the location of markers from model2 to model1. 
        The location of the marker in model1 is changed to the location of the marker in model2 
        in the frame of the common marker. 
        The location of the marker in model1 is changed back to the original parent frame. 
        The model with the changed marker locations is saved as a new model.
        '''
        # Load the OpenSim model
        model1 = osim.Model(model_path1)
        model1_version = model1.version
        model1_xml = model1.xml
        model1 = model1.osim_object
        markerset1 = model1.get_MarkerSet()
        state1 = model1.initSystem()

        model2 = osim.Model(model_path2)
        markerset2 = model2.get_MarkerSet()
        state2 = model2.initSystem()
        
        # if marker_names == 'all' then use all markers in model1
        if marker_names == 'all':
            marker_names = [markerset1.get(i).getName() for i in range(markerset1.getSize())]

        if marker_common_frame not in marker_names:
            raise ValueError('The marker_common_frame must be included in marker_names')

        # Loop through muscles and update their maximum isometric force
        for marker_name in marker_names:

            try:
                if markerset1.contains(marker_name):
                    marker1 = dict()
                    marker2 = dict()
                    
                    # get marker objects
                    marker1['marker'] = markerset1.get(marker_name)
                    marker2['marker'] = markerset2.get(marker_name)

                    # get location of markers
                    marker1['location'] = list(marker1['marker'].get_location().to_numpy())           
                    marker2['location'] = list(marker2['marker'].get_location().to_numpy())

                    # get parent frame of markers            
                    marker1['parent_frame'] = marker1['marker'].getParentFrame()
                    marker2['parent_frame'] = marker2['marker'].getParentFrame()

                    # get pelvis frame from marker_common_frame marker
                    marker1['pelvis_frame'] = markerset1.get(marker_common_frame).getParentFrame()
                    marker2['pelvis_frame'] = markerset2.get(marker_common_frame).getParentFrame()
                    
                    # get location of marker 2 in pelvis frame
                    marker2['marker'].changeFramePreserveLocation(state2,marker2['pelvis_frame'])
                    marker2['location_in_pelvis'] = marker2['marker'].get_location()
                    
                    # change location of marker 1 to marker 2 in pelvis frame
                    marker1['marker'].changeFramePreserveLocation(state1,marker1['pelvis_frame'])
                    marker1['marker'].set_location(marker2['location_in_pelvis'])

                    # change marker 1 back to original parent frame
                    marker1['marker'].changeFramePreserveLocation(state1,marker1['parent_frame'])
                    marker1['location'] = list(marker1['marker'].get_location().to_numpy())  

                    # if orginal model is 3.3 change the 
                    if int(model1_version[0]) == 3:
                        model1_xml.getroot().find('.//Marker[@name="' + marker_name + '"]/location').text = ' '.join(map(str, marker1['location']))

                    print(f'Location of marker {marker_name} changed')
            except Exception as e:
                print(f'Error changing location of marker {marker_name}: {e}')


        # Save the modified model
        if int(model1_version[0]) == 3:
            output_model_path = model_path1.replace('.osim', '_new.osim')
            model1_xml.write(model_path1.replace('.osim', '_new.osim'))
            print(f'Model saved to: {model_path1}')
        else:    
            output_model_path = model_path1.replace('.osim', '_new.osim')
            model1.printToXML(output_model_path)
            print(f'Model saved to: {output_model_path}')

    def find_file_endheader_line(file_path):
        #Read .mot files
        with open(file_path, "r") as file:
            lines = file.readlines()

        # Find the line where actual data starts (usually after 'endheader')
        start_row = next((i + 1 for i, line in enumerate(lines) if "endheader" in line), 0)
        
        return start_row
        
    # Operations    
    def sum_body_mass(model_path):
        '''
        This function sums the body mass of the model
        '''
        # Load the OpenSim model
        model = model(model_path)
        mass = 0
        for i in range(model.osim_object.getBodySet().getSize()):
            mass += model.osim_object.getBodySet().get(i).getMass()
        print(f'The total mass of the model is: {mass} kg')
        return mass       

    def sum_df_columns(df, groups = {}):
        # Function to sum columns of a dataframe based on a dictionary of groups
        # groups = {group_name: [column1, column2, column3]}
        summed_df = msk.src.pd.DataFrame()

        if not groups:
            groups = {'all': df.columns}

        for group_name, group_columns in groups.items():
            group_sum = df[group_columns].sum(axis=1)
            summed_df[group_name] = group_sum

        return summed_df

        if not os.path.isfile(muscle_force_sto):
            print_terminal_spaced('File not found:', muscle_force_sto)
            return

        if not os.path.isfile(model_path):
            print_terminal_spaced('File not found:', model_path)
            return
        
        if not os.path.isfile(muscle_length_sto):
            print_terminal_spaced('File not found:', muscle_length_sto)
            return
        

        # muscle_work 
        muscle_work = calculate_muscle_work(muscle_length_sto,muscle_force_sto, save = False, save_path = None)
        muscle_work.to_csv(os.path.join(os.path.dirname(muscle_force_sto),'MuscleWork.csv'), index=False)
        
        # force curce normalise to weight and save as csv
        muscle_force = time_normalise_df(import_sto_data(muscle_force_sto))
        muscle_force_normalised_to_weight = normalise_df(muscle_force,body_weight)
        muscle_force_normalised_to_weight.to_csv(os.path.join(os.path.dirname(muscle_force_sto),'MuscleForces_normalised.csv'), index=False)

        # muscle work normalised to weight and save as csv
        muscle_work_normalised_to_weight = normalise_df(muscle_work,body_weight)
        muscle_work_normalised_to_weight.to_csv(os.path.join(os.path.dirname(muscle_force_sto),'MuscleWork_normalised.csv'), index=False)

        muscles_r_hip_flex = osimSetup.get_muscles_by_group_osim(model_path,['hip_flex_r','hip_add_r','hip_inrot_r'])
        muscles_r_hip_ext = osimSetup.get_muscles_by_group_osim(model_path,['hip_ext_r','hip_abd_r','hip_exrot_r'])
        muscles_r_knee_flex = osimSetup.get_muscles_by_group_osim(model_path,['knee_flex_r'])
        muscles_r_knee_ext = osimSetup.get_muscles_by_group_osim(model_path,['knee_ext_r'])
        muscles_r_ankle_df = osimSetup.get_muscles_by_group_osim(model_path,['ankle_df_r'])
        muscles_r_ankle_pf = osimSetup.get_muscles_by_group_osim(model_path,['ankle_pf_r'])

        muscles_l_hip_flex = osimSetup.get_muscles_by_group_osim(model_path,['hip_flex_l','hip_add_l','hip_inrot_l'])
        muscles_l_hip_ext = osimSetup.get_muscles_by_group_osim(model_path,['hip_ext_l','hip_abd_l','hip_exrot_l'])
        muscles_l_knee_flex = osimSetup.get_muscles_by_group_osim(model_path,['knee_flex_l'])
        muscles_l_knee_ext = osimSetup.get_muscles_by_group_osim(model_path,['knee_ext_l'])
        muscles_l_ankle_df = osimSetup.get_muscles_by_group_osim(model_path,['ankle_df_l'])
        muscles_l_ankle_pf = osimSetup.get_muscles_by_group_osim(model_path,['ankle_pf_l'])

        groups = {  'RightHipFlex': muscles_r_hip_flex['all_selected'],
                    'RightHipExt': muscles_r_hip_ext['all_selected'],
                    'RightKneeFlex': muscles_r_knee_flex['all_selected'],
                    'RightKneeExt': muscles_r_knee_ext['all_selected'],
                    'RightAnkleDF': muscles_r_ankle_df['all_selected'],
                    'RightAnklePF': muscles_r_ankle_pf['all_selected'],
                    'LeftHipFlex': muscles_l_hip_flex['all_selected'],
                    'LeftHipExt': muscles_l_hip_ext['all_selected'],
                    'LeftKneeFlex': muscles_l_knee_flex['all_selected'],
                    'LeftKneeExt': muscles_l_knee_ext['all_selected'],
                    'LeftAnkleDF': muscles_l_ankle_df['all_selected'],
                    'LeftAnklePF': muscles_l_ankle_pf['all_selected']
        }
        # Perform grouping and summing for each group
        muscle_work_summed = sum_df_columns(muscle_work_normalised_to_weight,groups)
        # sum the work per group 
        muscle_work_summed= muscle_work_summed.sum(axis=0)
        return muscle_work_summed

    def calculate_muscle_work(muscle_length_sto,muscle_force_sto, save = True, save_path = None):

        try:
            length = msk.bops.time_normalise_df(msk.bops.import_sto_data(muscle_length_sto))
            force = msk.bops.time_normalise_df(msk.bops.import_sto_data(muscle_force_sto))
        except:
            print('Error importing files')
            return
        
        work = msk.src.pd.DataFrame()
        
        for muscle in length.columns:
            if muscle == 'time':
                work['time'] = length['time']
            elif muscle in force.columns:
                work_series = length[muscle] * force[muscle]
                work[muscle] = work_series.sum(axis=0) 
            else:
                print('Muscle', muscle, 'not found in forces')
        work = work.iloc[[0]]
        if save and not save_path:
            work.to_csv(os.path.join(os.path.dirname(muscle_force_sto),'results'),'muscle_work.csv')
            print('Data saved to', os.path.join(os.path.dirname(muscle_force_sto),'results'),'muscle_work.csv')
        elif save and save_path:
            work.to_csv(save_path)
            print('Data saved to', save_path)

        return work

    def get_muscle_groups(model_path, forces_file):
        '''
        Function to get the muscle groups from the model and save them to a csv file. Also returns the muscle groups as a DataFrame.
        
        Example usage:
        model_path = r"C:\Git\research_data\Projects\runbops_FAIS_phd\models\009\009_Rajagopal2015_FAI_originalMass_opt_N10_hans.osim"
        forces_file = r"C:\Git\research_data\Projects\runbops_FAIS_phd\simulations\009\pre\sprint_1\muscle_forces.sto"
        muscle_groups = ger_muscle_groups(model_path, forces_file)
        
        '''
        model = osim.Model(model_path)
        force_set = model.getForceSet()
        muscle_groups = {}
        for i in range(force_set.getNumGroups()):
            group = force_set.getGroup(i)    
            
            # save place holder XML (at the moment cannot get the groups from the API)
            path = SCRIPT_DIR + '\groups.xml'
            group.printToXML(path)
                   
            # Parse the XML file to get the members of the group            
            root = ET.parse(path).getroot()
            child = root.find('ObjectGroup')
            list_of_members = child.find('members').text.split()
            members= []
            for member in list_of_members:
                        members.append(member.strip())
            
            # Add the group name and its members to the dictionary
            muscle_groups[group.getName()] = members
            
            # Delete xml file
            if os.path.exists(path):
                os.remove(path)
            
        # Print the muscle groups and their members to a CSV file
        muscle_groups_df = pd.DataFrame.from_dict(muscle_groups, orient='index').transpose()
        muscle_groups_df.to_csv(SCRIPT_DIR + '\muscle_groups.csv', index=False, header=True)
        print('Muscle groups saved to ' + SCRIPT_DIR + '\muscle_groups.csv')
        
        return muscle_groups_df

    # RUN OSIM TOOLS
    def run_ik_tool(model, folder, marker_file = None, output_file = None, results_directory = None, task_set = None , run_tool = True):
        # Find marker file and task set file
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.endswith(".trc"):
                    marker_file = os.path.join(root, file)
                elif "taskset" in file:
                    task_set = os.path.join(root, file)
            # Define output file   
            output_file = os.path.join(root, "IK" + ".mot") 
            # Define results dir
            results_directory = root
        # Add time ranges
        # Create inverse kinematics tool, set parameters and run
        ik_tool = osim.InverseKinematicsTool()
        ik_tool.setModel(model)
        ik_tool.set_marker_file(marker_file)
        ik_tool.set_output_motion_file(output_file)
        ik_tool.set_results_directory(results_directory)
        ik_task_set = osim.IKTaskSet(task_set)
        ik_tool.set_IKTaskSet(ik_task_set)
        ik_tool.printToXML(os.path.join(folder, "setup_IK.xml"))
        
        if run_tool:
            ik_tool.run()

    def run_ik_tool_from_xml(model_path, setup_file_path, run_tool = True):
        # Create inverse kinematics tool, set parameters and run
        ik_tool = osim.InverseKinematicsTool(setup_file_path)
        model = osim.Model(model_path)
        ik_tool.setModel(model)

        model.addAnalysis(ik_tool)

        
        if run_tool:
            ik_tool.run()

    def run_id_tool(model, folder, LowpassCutoffFrequency = 6, run_tool = True):
        
        for root, dirs, files in os.walk(folder):
            # Find coordinates file
            for file in files:
                if file == "IK.mot":
                    coordinates_file = os.path.join(root, file)
            # Find external loads file
                elif file == "externalloads.xml":
                    external_loads_file = os.path.join(root, file)
            # Set output file
            output_file = os.path.join(root, "ID.sto")
        
        # Setup for excluding muscles from ID
        exclude = osim.ArrayStr()
        exclude.append("Muscles")
        # Setup for setting time range
        IKData = osim.Storage(coordinates_file)

        # Create inverse dynamics tool, set parameters and run
        id_tool = osim.InverseDynamicsTool()
        id_tool.setModel(model)
        id_tool.setCoordinatesFileName(coordinates_file)
        id_tool.setExternalLoadsFileName(external_loads_file)
        id_tool.setOutputGenForceFileName(output_file)
        id_tool.setLowpassCutoffFrequency(LowpassCutoffFrequency)
        id_tool.setStartTime(IKData.getFirstTime())
        id_tool.setEndTime(IKData.getLastTime())
        id_tool.setExcludedForces(exclude)
        id_tool.setResultsDir(folder)
        id_tool.printToXML(os.path.join(folder, "setup_ID.xml"))
        
        if run_tool:
            id_tool.run()

    def run_so_tool(model, folder, run_tool = True):
        model = osim.Model(model)
        state = model.initSystem()

        # Finding data
        for root, dirs, files in os.walk(folder):
            # Find coordinates file
            for file in files:
                if file == "IK.mot":
                    coordinates_file = os.path.join(root, file)
                    coordinates_file_sto = osim.Storage(coordinates_file)
            # Find external loads file
                elif file == "externalloads.xml":
                    external_loads_file = os.path.join(root, file)
            # Find actuators file
                elif file == "actuators_so.xml":
                    actuators_file = os.path.join(root, file)
                    try:
                        if os.path.exists(actuators_file):
                            actuators = osim.ArrayStr()
                            actuators.append(actuators_file)

                    except: 
                        print("No actuators file found")
            # Set results directory
            results_directory = root
        


        #Create the AnalyzeTool
        analyze_tool = osim.AnalyzeTool()
        analyze_tool.setModel(model)
        # analyze_tool.setLowpassCutoffFrequency(6)
        analyze_tool.setStatesFromMotion(state, coordinates_file_sto, True)
        analyze_tool.setStartTime(coordinates_file_sto.getFirstTime())
        analyze_tool.setFinalTime(coordinates_file_sto.getLastTime())
        analyze_tool.setReplaceForceSet(False)
        analyze_tool.setSolveForEquilibrium(False)
    
    # Initialize the StaticOptimization
        static_opt = osim.StaticOptimization()
        static_opt.setName("StaticOptimization")
        static_opt.setUseModelForceSet(True)
        static_opt.setStartTime(coordinates_file_sto.getFirstTime())
        static_opt.setEndTime(coordinates_file_sto.getLastTime())

        #analyze
        analysis_set = analyze_tool.getAnalysisSet()
        analysis_set.cloneAndAppend(static_opt)
        analyze_tool.addAnalysisSetToModel()
        analyze_tool.setCoordinatesFileName(coordinates_file)
        analyze_tool.setExternalLoadsFileName(external_loads_file)
        analyze_tool.setForceSetFiles(actuators)
        # analyze_tool.setStatesFileName()

        # Save setup and results
        analyze_tool.setResultsDir(results_directory)
        analyze_tool.printToXML(os.path.join(folder, "setup_so.xml"))
        
        if run_tool:

            analyze_tool.run()

            # Change naming of output files
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if "force" in file:
                        os.rename(os.path.join(root, file), os.path.join(root, "so_forces.sto"))
                    elif "activation" in file:
                        os.rename(os.path.join(root, file), os.path.join(root, "so_activation.sto"))
                    elif "controls" in file:
                        os.rename(os.path.join(root, file), os.path.join(root, "so_controls.xml"))
    
class SimpleProject:
    '''
    class for later to use in a simple project data structure
    '''
    class Trial:
        def __init__(self,path):
            self.path = path    
            if not os.path.isfile(path):
                print(f"Error not found: {path}")
                
            else:
                print(f"Loading: {path}")
                
                if path.__contains__('angles.csv'):
                    self.angles = msk.bops.import_file(path)
                    
                elif path.__contains__('muscle_forces.sto'):
                    new_path = path.replace('.sto','.csv')
                    msk.bops.shutil.copy(path,new_path)
                    self.muscleForces = msk.bops.import_file(new_path)
                    # remove time offset and time normalise
                    self.muscleForces['time'] = self.muscleForces['time'] - self.muscleForces['time'][0]
                    muscleForces_timeNorm = msk.bops.time_normalise_df(self.muscleForces)
                    muscleForces_timeNorm.to_csv(new_path.replace('.csv','_normalised.csv'), index=False)
                    
                elif path.__contains__('muscle_forces.csv'):
                    self.muscleForces = msk.bops.import_file(path)
                    
                elif path.__contains__('joint_loads.csv'):
                    self.jointLoads = msk.bops.import_file(path)

    class Task:
        # For each task, create a class that contains the Trial objects
        # check example folder structure: C:\Project\Subject\Task\Trial
        def __init__(self, taskPath):
            self.path = taskPath
            self.folders = os.listdir(taskPath)
            
            for folder in self.folders:
                folderPath = os.path.join(taskPath, folder)
                self.__dict__[folder] = msk.Trial(folderPath)
                self.trials = self.__dict__.keys()
                
    class Subject:
        # For each subject, create a class that contains the Task objects
        # check example folder structure: C:\Project\Subject\Task\Trial
        def __init__(self, path):
            self.path = path
            self.tasks = os.listdir(path)
            
            for task in self.tasks:
                taskPath = os.path.join(path, task)
                if os.path.isdir(taskPath):
                    self.__dict__[task] = msk.Task(taskPath)
            
    class Project:
        # For each project, create a class that contains the Subject objects
        # check example folder structure: C:\Project\Subject\Task\Trial
        def __init__(self, projectPath=''):        
            self.path = projectPath
            self.dataPath = os.path.join(projectPath, 'Data')
            
            msk.bops.create_folder(self.dataPath)
            
            self.subjects = []
            
            for subject in os.listdir(self.dataPath):
                subjectPath = os.path.join(self.dataPath, subject)
                if os.path.isdir(subjectPath):
                    self.__dict__[subject] = msk.SubjectSimple(subjectPath)    
                    self.subjects.append(subject)
        

    def isTrial(self,var):
        return isinstance(var, self.Trial)

    def isTask(self, var):
        return isinstance(var, self.Task)

    def isSubject(self, var):
        return isinstance(var, self.Subject)

    def isProject(self, var):
        return isinstance(var, self.Project)

class NormalizationSet:
    def __init__(self,name,path, extension, columns_to_normalise = 'all'):
        '''
        Class to store information about a set of files to normalise data
        '''
        self.name = name
        self.path = path
        self.ext = extension
        self.df = msk.bops.import_file(path + name + extension)
        
        if columns_to_normalise == 'all':
            self.columns = self.df.columns
        else:
            if columns_to_normalise not in self.df.columns:
                print('Column not found in data')
                return
            else:
                self.columns = columns_to_normalise
        
class C3DData:
    def __init__(self, filepath = None):
        
        # print warning not finished 
        input('this object is not finished. Contue testing mode? (CTRL+C to Stop)')
        
        if not filepath:
            print('No path provided. C3DData object created without path')
            
        self.path = filepath
        try:
            r = c3d.Reader(open(filepath, 'rb'))
            self.header = r.header
            self.markers = []
            self.analog = []
            self.df = pd.DataFrame()
            for frame_no, points, analog in r.read_frames():
                self.markers.append(points)
                self.analog.append(analog)
            # convert markers to a pandas dataframe with first row marker names and second row columns x,y,z
            self.markers = np.array(self.markers)
            self.markers = np.swapaxes(self.markers, 0, 1)
            self.markers = np.swapaxes(self.markers, 1, 2)

            self.df = pd.DataFrame(self.markers)
            import pdb ; pdb.set_trace()
            
        except Exception as e:
            print(e)
                        
        return self
    
    
    def _to_trc(self):
        
        self.df = pd.DataFrame(self.markers)
        # add headings
        self.df.columns = self.header['point_labels']
        
        return self.df
    
    def _to_osim(self): 
        
        # create .trc 
        self.markers = np.array(self.markers)
        print('not finished ...')
        
        raise Exception('Not finished')
        
        return self.markers
    
    def _to_json(self):
        print(' not implemented')
               
class XMLTools:
    """
    A class to load and create XML files for OpenSim and CEINMS.
    usage:
    xml_tool = XMLTools()
    tree = xml_tool.load("example.xml")
    ...
    """
    def __init__(self,xml_file=None):
        try:
            self.tree = ET.parse(xml_file)
        except Exception as e:
            print(f"Error loading XML file: {e}")
            self.tree = None
        
        self.osim_model = None
    
    def load(self, xml_file):
        try:
            self.tree = ET.parse(xml_file)
            return self.tree
        except Exception as e:
            print(f"Error loading XML file: {e}")
            return None
    
    def save_pretty_xml(self, tree, save_path):
            """Saves the XML tree to a file with proper indentation."""
            # Convert to string and format with proper indents
            rough_string = ET.tostring(tree.getroot(), 'utf-8')
            reparsed = xml.dom.minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="   ")

            # Write to file
            with open(save_path, 'w') as file:
                file.write(pretty_xml)
    
    def dir_find_containing(self, var, name_to_find):
        for i in dir(var):
            if i.__contains__(name_to_find):
                print(f"Found {name_to_find} in {var.__class__.__name__}")
                return i
        
        print(f"Could not find {name_to_find} in {var.__class__.__name__}")
        return None
    
    class ceinms: 
        try:
            from msk_modelling_python import osim
        except:
            pass
        
        # Get data from OSIM model / xml
        
        def get_muscles_by_group_osim(self, model_path, group_names = 'all'):
            '''
            Function to get the muscle groups from the model and save them to a csv file. Also returns the muscle groups as a DataFrame.
            
            Example usage:
            model_path = r"C:\Git\research_data\Projects\runbops_FAIS_phd\models\009\009_Rajagopal2015_FAI_originalMass_opt_N10_hans.osim"
            group_names = ['hip_flex_r','hip_add_r','hip_inrot_r']
            muscles = get_muscles_by_group_osim(model_path, group_names)
            
            '''
            # Load the OpenSim model
            model = osim.Model(model_path)
            
            # Get the muscle groups from the model
            force_set = model.getForceSet()
            for i in range(forse_set.getSize()):
                group = force_set.getGroup(i)    
                
                # save place holder XML (at the moment cannot get the groups from the API)
                path = SCRIPT_DIR + '\groups.xml'
                group.printToXML(path)
                       
                # Parse the XML file to get the members of the group            
                root = ET.parse(path).getroot()
                child = root.find('ObjectGroup')
                list_of_members = child.find('members').text.split()
                members= []
                for member in list_of_members:
                            members.append(member.strip())
                
                # Add the group name and its members to the dictionary
                muscle_groups[group.getName()] = members
                
                # Delete xml file
                if os.path.exists(path):
                    os.remove(path)
            
            # Get the muscle groups from the model
            members_dict = self.get_muscle_groups_from_xml(force_set, group_names)
            
            return members_dict
        
        # Create CEINMS xmls
        def create_calibration_setup(self, save_path = None):
            root = ET.Element("ceinmsCalibration")
            
            subject_file = ET.SubElement(root, "subjectFile")
            subject_file.text = ".\\uncalibrated.xml"
            
            excitation_generator_file = ET.SubElement(root, "excitationGeneratorFile")
            excitation_generator_file.text = ".\\excitation_generator.xml"
            
            calibration_file = ET.SubElement(root, "calibrationFile")
            calibration_file.text = ".\\calibration_cfg.xml"
            
            output_subject_file = ET.SubElement(root, "outputSubjectFile")
            output_subject_file.text = ".\\calibratedSubject.xml"
            
            tree = ET.ElementTree(root)
            if save_path is not None:
                XMLTools().save_pretty_xml(tree, save_path)
                
            return tree

        def create_calibration_cfg(self, save_path=None, osimModelFile=None):

            if osimModelFile is not None:
                model = osim.Model(osimModelFile)
                coordinate_set = model.getCoordinateSet()
                muscles = model.getMuscles()
                muscle_groups = []
                for muscle in muscles:
                    muscle_groups.append(muscle.getName())
                    
                dofs = []
                for coordinate in coordinate_set:
                    dofs.append(coordinate.getName())
                
                dofs = ' '.join(dofs)
                
            else:
                print("\033[93mNo OpenSim model file provided. Muscle groups will be from template.\033[0m")
                print("\033[93mDOFs will be added from template\033[0m")
                
                muscle_groups = ["addbrev_r addlong_r addmagDist_r addmagIsch_r addmagMid_r addmagProx_r grac_r",
                    "bflh_r semimem_r semiten_r",
                    "bfsh_r",
                    "glmax1_r glmax2_r glmax3_r",
                    "glmed1_r glmed2_r glmed3_r",
                    "glmin1_r glmin2_r glmin3_r",
                    "sart_r recfem_r tfl_r",
                    "iliacus_r psoas_r",
                    "perbrev_r perlong_r tibant_r tibpost_r",
                    "edl_r ehl_r fdl_r fhl_r",
                    "soleus_r gaslat_r gasmed_r",
                    "vasint_r vaslat_r vasmed_r"]        

                dofs = "hip_flexion_r hip_adduction_r hip_rotation_r knee_angle_r ankle_angle_r"
            
            
            
            root = ET.Element("calibration", attrib={"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
            
            algorithm = ET.SubElement(root, "algorithm")
            simulated_annealing = ET.SubElement(algorithm, "simulatedAnnealing")
            ET.SubElement(simulated_annealing, "noEpsilon").text = "4"
            ET.SubElement(simulated_annealing, "rt").text = "0.3"
            ET.SubElement(simulated_annealing, "T").text = "200000"
            ET.SubElement(simulated_annealing, "NS").text = "15"
            ET.SubElement(simulated_annealing, "NT").text = "5"
            ET.SubElement(simulated_annealing, "epsilon").text = "1.E-5"
            ET.SubElement(simulated_annealing, "maxNoEval").text = "200000"
            
            nms_model = ET.SubElement(root, "NMSmodel")
            model_type = ET.SubElement(nms_model, "type")
            ET.SubElement(model_type, "openLoop")
            tendon = ET.SubElement(nms_model, "tendon")
            ET.SubElement(tendon, "equilibriumElastic")
            activation = ET.SubElement(nms_model, "activation")
            ET.SubElement(activation, "exponential")
            
            calibration_steps = ET.SubElement(root, "calibrationSteps")
            step = ET.SubElement(calibration_steps, "step")
            ET.SubElement(step, "dofs").text = dofs
            
            objective_function = ET.SubElement(step, "objectiveFunction")
            torque_error_normalised = ET.SubElement(objective_function, "torqueErrorNormalised")
            ET.SubElement(torque_error_normalised, "targets").text = "all"
            ET.SubElement(torque_error_normalised, "weight").text = "1"
            ET.SubElement(torque_error_normalised, "exponent").text = "1"
            
            penalty = ET.SubElement(objective_function, "penalty")
            ET.SubElement(penalty, "targets").text = "all"
            ET.SubElement(penalty, "targetsType").text = "normalisedFibreLength"
            ET.SubElement(penalty, "weight").text = "100"
            ET.SubElement(penalty, "exponent").text = "2"
            ET.SubElement(penalty, "range").text = "0.6 1.4"
            
            parameter_set = ET.SubElement(step, "parameterSet")
                    
            parameters = [
                {"name": "c1", "range": "-0.95 -0.05"},
                {"name": "c2", "range": "-0.95 -0.05"},
                {"name": "shapeFactor", "range": "-2.999 -0.001"},
                {"name": "tendonSlackLength", "range": "0.85 1.15", "relative": True},
                {"name": "optimalFibreLength", "range": "0.85 1.15", "relative": True},
                {"name": "strengthCoefficient", "range": "0.8 2", "muscleGroups": muscle_groups}
            ]
            
            for param in parameters:
                parameter = ET.SubElement(parameter_set, "parameter")
                ET.SubElement(parameter, "name").text = param["name"]
                ET.SubElement(parameter, "single")
                if "relative" in param and param["relative"]:
                    relative = ET.SubElement(parameter, "relativeToSubjectValue")
                    ET.SubElement(relative, "range").text = param["range"]
                else:
                    absolute = ET.SubElement(parameter, "absolute")
                    ET.SubElement(absolute, "range").text = param["range"]
                if "muscleGroups" in param:
                    muscle_groups = ET.SubElement(parameter, "muscleGroups")
                    for muscles in param["muscleGroups"]:
                        ET.SubElement(muscle_groups, "muscles").text = muscles
            
            ET.SubElement(root, "trialSet").text = ".\\trial.xml"
            
            tree = ET.ElementTree(root)
            if save_path is not None:
                XMLTools().save_pretty_xml(tree=tree, save_path=save_path)
            
            return tree

        def create_subject_uncalibrated(self, save_path=None, osimModelFile=None):
            if osimModelFile == None:
                print("\033[93mNo OpenSim model not file provided. FAILED!!\033[0m")
                return None
            else:
                try:
                    model = osim.Model(osimModelFile)
                    coordinate_set = model.getCoordinateSet()
                    muscles = model.getMuscles()
                except Exception as e:
                    print(f"Error loading OpenSim model: {e}")
                    return None
                
            root = ET.Element("subject", attrib={"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
            
            mtu_default = ET.SubElement(root, "mtuDefault")
            ET.SubElement(mtu_default, "emDelay").text = "0.015"
            ET.SubElement(mtu_default, "percentageChange").text = "0.15"
            ET.SubElement(mtu_default, "damping").text = "0.1"
            
            curves = [
                {
                    "name": "activeForceLength",
                    "xPoints": "-5 0 0.401 0.402 0.4035 0.52725 0.62875 0.71875 0.86125 1.045 1.2175 1.4387 1.6187 1.62 1.621 2.2 5",
                    "yPoints": "0 0 0 0 0 0.22667 0.63667 0.85667 0.95 0.99333 0.77 0.24667 0 0 0 0 0"
                },
                {
                    "name": "passiveForceLength",
                    "xPoints": "-5 0.998 0.999 1 1.1 1.2 1.3 1.4 1.5 1.6 1.601 1.602 5",
                    "yPoints": "0 0 0 0 0.035 0.12 0.26 0.55 1.17 2 2 2 2"
                },
                {
                    "name": "forceVelocity",
                    "xPoints": "-10 -1 -0.6 -0.3 -0.1 0 0.1 0.3 0.6 0.8 10",
                    "yPoints": "0 0 0.08 0.2 0.55 1 1.4 1.6 1.7 1.75 1.75"
                },
                {
                    "name": "tendonForceStrain",
                    "xPoints": "0 0.001 0.002 0.003 0.004 0.005 0.006 0.007 0.008 0.009 0.01 0.011 0.012 0.013 0.014 0.015 0.016 0.017 0.018 0.019 0.02 0.021 0.022 0.023 0.024 0.025 0.026 0.027 0.028 0.029 0.03 0.031 0.032 0.033 0.034 0.035 0.036 0.037 0.038 0.039 0.04 0.041 0.042 0.043 0.044 0.045 0.046 0.047 0.048 0.049 0.05 0.051 0.052 0.053 0.054 0.055 0.056 0.057 0.058 0.059 0.06 0.061 0.062 0.063 0.064 0.065 0.066 0.067 0.068 0.069 0.07 0.071 0.072 0.073 0.074 0.075 0.076 0.077 0.078 0.079 0.08 0.081 0.082 0.083 0.084 0.085 0.086 0.087 0.088 0.089 0.09 0.091 0.092 0.093 0.094 0.095 0.096 0.097 0.098 0.099 0.1",
                    "yPoints": "0 0.0012652 0.0073169 0.016319 0.026613 0.037604 0.049078 0.060973 0.073315 0.086183 0.099678 0.11386 0.12864 0.14386 0.15928 0.17477 0.19041 0.20658 0.22365 0.24179 0.26094 0.28089 0.30148 0.32254 0.34399 0.36576 0.38783 0.41019 0.43287 0.45591 0.4794 0.50344 0.52818 0.55376 0.58022 0.60747 0.63525 0.66327 0.69133 0.71939 0.74745 0.77551 0.80357 0.83163 0.85969 0.88776 0.91582 0.94388 0.97194 1 1.0281 1.0561 1.0842 1.1122 1.1403 1.1684 1.1964 1.2245 1.2526 1.2806 1.3087 1.3367 1.3648 1.3929 1.4209 1.449 1.477 1.5051 1.5332 1.5612 1.5893 1.6173 1.6454 1.6735 1.7015 1.7296 1.7577 1.7857 1.8138 1.8418 1.8699 1.898 1.926 1.9541 1.9821 2.0102 2.0383 2.0663 2.0944 2.1224 2.1505 2.1786 2.2066 2.2347 2.2628 2.2908 2.3189 2.3469 2.375 2.4031 2.4311"
                }
            ]
            
            for curve in curves:
                curve_element = ET.SubElement(mtu_default, "curve")
                ET.SubElement(curve_element, "name").text = curve["name"]
                ET.SubElement(curve_element, "xPoints").text = curve["xPoints"]
                ET.SubElement(curve_element, "yPoints").text = curve["yPoints"]
            
            mtu_set = ET.SubElement(root, "mtuSet")
            
            try:
                mtus = []
                for muscle in muscles:
                    mtu = {
                        "name": muscle.getName(),
                        "c1": "-0.5",
                        "c2": "-0.5",
                        "shapeFactor": "0.1",
                        "optimalFibreLength": muscle.getOptimalFiberLength(),
                        "pennationAngle": muscle.getPennationAngleAtOptimalFiberLength(),
                        "tendonSlackLength": muscle.getTendonSlackLength(),
                        "tendonSlackLength": muscle.getTendonSlackLength(),
                        "maxIsometricForce": muscle.getMaxIsometricForce(),
                        "strengthCoefficient": "1"
                        }
                    mtus.append(mtu)
            except Exception as e:
                print(f"Error adding opensim muscles: {e}")
                return None
                            
            for mtu in mtus:
                mtu_element = ET.SubElement(mtu_set, "mtu")
                ET.SubElement(mtu_element, "name").text = mtu["name"]
                ET.SubElement(mtu_element, "c1").text = mtu["c1"]
                ET.SubElement(mtu_element, "c2").text = mtu["c2"]
                ET.SubElement(mtu_element, "shapeFactor").text = mtu["shapeFactor"]
                ET.SubElement(mtu_element, "optimalFibreLength").text = mtu["optimalFibreLength"]
                ET.SubElement(mtu_element, "pennationAngle").text = mtu["pennationAngle"]
                ET.SubElement(mtu_element, "tendonSlackLength").text = mtu["tendonSlackLength"]
                ET.SubElement(mtu_element, "maxIsometricForce").text = mtu["maxIsometricForce"]
                ET.SubElement(mtu_element, "strengthCoefficient").text = mtu["strengthCoefficient"]
            
            
            
            dof_set = ET.SubElement(root, "dofSet")
            
            import pdb; pdb.set_trace()
            dofs = []
            for coordinate in coordinate_set:
                dof = {
                    "name": coordinate.getName(),
                    "mtuNameSet": "addbrev_r addlong_r addmagDist_r addmagIsch_r addmagMid_r addmagProx_r grac_r"
                }
                dofs.append(dof)
            dofs = [
                {"name": "hip_flexion_r", "mtuNameSet": "addbrev_r addlong_r addmagDist_r addmagIsch_r addmagMid_r addmagProx_r bflh_r glmax1_r glmax2_r glmax3_r glmed1_r glmed2_r glmed3_r glmin1_r glmin2_r glmin3_r grac_r iliacus_r piri_r psoas_r recfem_r sart_r semimem_r semiten_r tfl_r"},
                {"name": "hip_adduction_r", "mtuNameSet": "addbrev_r addlong_r addmagDist_r addmagIsch_r addmagMid_r addmagProx_r bflh_r glmax1_r glmax2_r glmax3_r glmed1_r glmed2_r glmed3_r glmin1_r glmin2_r glmin3_r grac_r iliacus_r piri_r psoas_r recfem_r sart_r semimem_r semiten_r tfl_r"},
                # Add other DOFs here...
            ]
            
            for dof in dofs:
                dof_element = ET.SubElement(dof_set, "dof")
                ET.SubElement(dof_element, "name").text = dof["name"]
                ET.SubElement(dof_element, "mtuNameSet").text = dof["mtuNameSet"]
            
            calibration_info = ET.SubElement(root, "calibrationInfo")
            uncalibrated = ET.SubElement(calibration_info, "uncalibrated")
            ET.SubElement(uncalibrated, "subjectID").text = "9"
            ET.SubElement(uncalibrated, "additionalInfo").text = "TendonSlackLength and OptimalFibreLength scaled with Winby-Modenese"
            
            ET.SubElement(root, "contactModelFile").text = ".\\contact_model.xml"
            ET.SubElement(root, "opensimModelFile").text = "..\\rajagopal_scaled.osim"
            
            tree = ET.ElementTree(root)
            if save_path is not None:
                self.save_pretty_xml(tree, save_path)
            
            return tree


# Plotting 

class Plot():
    def create_sto_plot(stoFilePath=False):
        # Specify the path to the .sto file
        if not stoFilePath:
            stoFilePath = msk.bops.get_testing_file_path('id')

        # Read the .sto file into a pandas DataFrame
        data = msk.bops.import_sto_data(stoFilePath)

        # Get the column names excluding 'time'
        column_names = [col for col in data.columns if col != 'time']

        # Calculate the grid size
        num_plots = len(column_names)
        grid_size = int(num_plots ** 0.5) + 1

        # Get the screen width and height
        user32 = msk.src.ctypes.windll.user32
        screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

        fig_width = screensize[0] * 0.9
        fig_height = screensize[1] * 0.9

        # Create the subplots
        fig, axs = msk.ui.plt.subplots(grid_size, grid_size, figsize=(10, 10))

        # Flatten the axs array for easier indexing
        axs = axs.flatten()

        # Create a custom color using RGB values (r,g,b)
        custom_color = (0.8, 0.4, 0.5)

        num_cols = data.shape[1]
        num_rows = int(msk.src.np.ceil(num_cols / 3))  # Adjust the number of rows based on the number of columns

        # Iterate over the column names and plot the data
        for i, column in enumerate(column_names):
            ax = axs[i]
            ax.plot(data['time'], data[column], color=custom_color, linewidth=1.5)
            ax.set_title(column, fontsize=8)
            
            if i % 3 == 0:
                ax.set_ylabel('Moment (Nm)',fontsize=9)
                ax.set_yticks(msk.src.np.arange(-3, 4))

            if i >= num_cols - 3:
                ax.set_xlabel('time (s)', fontsize=8)
                ax.set_xticks(msk.src.np.arange(0, 11, 2))
            
            ax.grid(True, linestyle='--', linewidth=0.5)
            ax.tick_params(labelsize=8)

        # Remove any unused subplots
        if num_plots < len(axs):
            for i in range(num_plots, len(axs)):
                fig.delaxes(axs[i])

        # Adjust the spacing between subplots
        msk.ui.plt.tight_layout()

        return fig

    def create_example_emg_plot(c3dFilePath=False):
        # Specify the path to the .sto file
        if not c3dFilePath:
            c3dFilePath = msk.bops.get_testing_file_path('c3d')

        # Read the .sto file into a pandas DataFrame
        data = msk.bops.import_c3d_analog_data(c3dFilePath)
        data_filtered = msk.bops.emg_filter(c3dFilePath)

        # Get the column names excluding 'time'
        column_names = [col for col in data.columns if col != 'time']

        # Calculate the grid size
        num_plots = len(column_names)
        grid_size = int(num_plots ** 0.5) + 1

        # Get the screen width and height
        user32 = msk.src.ctypes.windll.user32
        screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        fig_width = screensize[0] * 0.9
        fig_height = screensize[1] * 0.9

        # Create the subplots
        fig, axs = msk.plot.plt.subplots(grid_size, grid_size, figsize=(10, 10))

        # Flatten the axs array for easier indexing
        axs = axs.flatten()

        # Create a custom color using RGB values (r,g,b)
        custom_color = (0.8, 0.4, 0.5)

        num_cols = data.shape[1]
        num_rows = int(msk.src.np.ceil(num_cols / 3))  # Adjust the number of rows based on the number of columns

        # Iterate over the column names and plot the data
        for i, column in enumerate(column_names):
            ax = axs[i]
            ax.plot(data['time'], data[column], color=custom_color, linewidth=1.5)
            ax.plot(data_filtered['time'], data_filtered[column], color=custom_color, linewidth=1.5)
            ax.set_title(column, fontsize=8)
            
            if i % 3 == 0:
                ax.set_ylabel('Moment (Nm)',fontsize=9)
                ax.set_yticks(msk.src.np.arange(-3, 4))

            if i >= num_cols - 3:
                ax.set_xlabel('time (s)', fontsize=8)
                ax.set_xticks(msk.src.np.arange(0, 11, 2))
            
            ax.grid(True, linestyle='--', linewidth=0.5)
            ax.tick_params(labelsize=8)

        # Remove any unused subplots
        if num_plots < len(axs):
            for i in range(num_plots, len(axs)):
                fig.delaxes(axs[i])

        # Adjust the spacing between subplots
        msk.plot.plt.tight_layout()

        return fig     

    def calculate_axes_number(num_plots):
        if num_plots  > 2:
            ncols = msk.math.ceil(msk.math.sqrt(num_plots))
            nrows = msk.math.ceil(num_plots / ncols)
        else:
            ncols = num_plots
            nrows = 1

        return ncols, nrows

    def plot_line_df(df,sep_subplots = True, columns_to_plot='all',xlabel=' ',ylabel=' ', legend=['data1'],save_path='', title=''):
        
        # Check if the input is a file path
        if type(df) == str and os.path.isfile(df):
            df = msk.bops.import_sto_data(df)
            pass
        
        if columns_to_plot == 'all':
            columns_to_plot = df.columns
        
        # Create a new figure and subplots
        if sep_subplots:
            ncols, nrows = msk.bops.calculate_axes_number(len(columns_to_plot))
            fig, axs = msk.plot.plt.subplots(nrows, ncols, figsize=(15, 5))
            
            for row, ax_row in enumerate(axs):
                for col, ax in enumerate(ax_row):
                    ax_count = row * ncols + col

                    heading = columns_to_plot[ax_count]    
                    if heading not in df.columns:
                        print(f'Heading not found: {heading}')
                        continue    
                    
                    # Plot data
                    ax.plot(df[heading])
                    ax.set_title(f'{heading}')
                    
                    if row == 1:
                        ax.set_xlabel(xlabel)
                    if col == 0:
                        ax.set_ylabel(ylabel)
        
            msk.plot.plt.legend(legend)
            msk.plot.plt.xlabel(xlabel)
            msk.plot.plt.ylabel(ylabel)
            msk.plot.plt.title(title)
        
        else:
            fig, axs = msk.plot.plt.subplots(1, 1, figsize=(15, 5))
            for column in columns_to_plot:
                axs.plot(df[column])
                axs.set_title(f'{column}')
                axs.set_xlabel(xlabel)
                axs.set_ylabel(ylabel)
            
            msk.plot.plt.title(title)
            axs.legend(columns_to_plot,ncols=2)
        
        fig.set_tight_layout(True)

        if save_path:
            msk.plot.save_fig(fig,save_path)
        
        return fig, axs

    def plot_bar_df(df,transpose = False):

        # Transpose the DataFrame to have rows as different bar series
        if transpose:
            df = df.transpose()

        # Plot the bar chart
        ax = df.plot(kind='bar', figsize=(10, 6), colormap='viridis')

        # Customize the plot
        ax.set_xlabel(' ')
        ax.set_ylabel(' ')
        ax.set_title(' ')
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45)

        # Adjust subplot layout to make room for x-axis tick labels
        plt.subplots_adjust(bottom=0.2)

        return plt.gcf(), plt.gca()

    def plot_line_list(data, labels = '', xlabel=' ', ylabel=' ', title=' ', save_path=''):
        # Create a new figure
        fig, ax = plt.subplots(figsize=(10, 6))

        if not labels:
            labels = [f'Data {i}' for i in range(len(data))]

        # Plot the data
        ax.plot(data, label=labels)

        # Customize the plot
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        

        return fig, ax

    def plot_from_txt(file_path='', xlabel=' ', ylabel=' ', title=' ', save_path=''):
        
        if not file_path:
            file_path = select_file()
        
        # Read the data from the text file
        data = msk.src.np.loadtxt(file_path)

        # plot simple line plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(data)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
                
        fig.set_tight_layout(True)

        if save_path:
            save_fig(fig,save_path)
        
        return fig, ax


#%% Platypus class for testing stuff
class Platypus:
    '''
    Platypus class to test the bops package
    usage:
        platypus = Platypus() # create an instance of the Platypus class
        platypus.run_tests() # run all tests
        platypus.print_happy() # print a happy platypus
        platypus.print_sad() # print a sad platypus
    '''
    def __init__(self):
        self.name = 'Platypus'
        self.mood = 'sad'
        self.output = None
        self.images_path = os.path.join(SCRIPT_DIR, 'src')
        self.current_image_path = None
        self.photo = None
        
    def greet(self):
        print(f"Hello, my name is {self.name}!")
        
    def happy(self, message = ''):
        try:
            print(message) 
            self.current_image_path = os.path.join(self.images_path, 'platypus.jpg')
            self.show_image()
            self.mood = 'happy'
        except Exception as e:
            self.mood = 'sad'
            print('happy platypus image not found in ' + self.current_image_path)
            print(e)
        
    def sad(self):
        try:
            self.current_image_path = os.path.join(self.images_path, 'platypus_sad.jpg')
            self.show_image()
            self.mood = 'sad'
        except Exception as e:  
            print('sad platypus image not found in ' + self.current_image_path)
            print(e)
        
    def show_image(self):
        # Create a Tkinter window
        window = tk.Tk()
        
        # Load the image using PIL
        image = Image.open(self.current_image_path)
        # Create a Tkinter PhotoImage from the PIL image
        photo = ImageTk.PhotoImage(image)
        
        label = tk.Label(window, image=photo)
        label.image = photo
        label.pack()
        
        # center image on the screen
        try:
            window_width = window.winfo_reqwidth()
            window_height = window.winfo_reqheight()
            position_right = int((window.winfo_screenwidth()/2 - window_width*3)) 
            position_down = int((window.winfo_screenheight()/2 - window_height*2))
            window.geometry("+{}+{}".format(position_right, position_down))
        except Exception as e:
            msk.log_error('Error bops.Platypus: ' + e)
            print('Could not center image on screen: ' + str(e))
            
        # Start the image loop
        window.mainloop()
    
    def run_tests(self):
        print('running all tests ...')
        unittest.main()
        
        if self.mood == 'sad':
            self.sad()
        else:
            self.happy()

if __name__ == '__main__':
    unittest.main()

# END