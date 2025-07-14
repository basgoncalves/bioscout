# python version of Batch OpenSim Processing Scripts (BOPS)
# Author: Basilio Goncalves, University of Vienna
# originally by Bruno L. S. Bedo, Alice Mantoan, Danilo S. Catelli, Willian Cruaud, Monica Reggiani & Mario Lamontagne (2021):
# BOPS: a Matlab toolbox to batch musculoskeletal data processing for OpenSim, Computer Methods in Biomechanics and Biomedical Engineering
# DOI: 10.1080/10255842.2020.1867978

__testing__ = False
__version__ = '0.2.0'

# import needed libraries
import os
import json
import time
import unittest
import numpy as np
import pandas as pd
import c3d
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog



# import opensim if installed
try:
    import opensim as osim
except:
    print('OpenSim not installed.')
    osim = None


# define Global variables
BOPS_PATH = os.path.dirname(os.path.realpath(__file__))
SETTINGS_PATH = os.path.join(BOPS_PATH,'settings.json')
SETTINGS = json.load(open(SETTINGS_PATH))  
# update SETTINGS["bops"]["instalation"] path on the file
SETTINGS["bops"]["installation"] = BOPS_PATH
SETTINGS["__version__"] = __version__

SIMULATIONS_PATH = os.path.dirname(SETTINGS["current_project"])
try:
    PROJECT = json.load(open(SETTINGS["current_project"]))
except:
    PROJECT = None
    print('No project loaded.')

SUBJECTS_PATH = os.path.join(SIMULATIONS_PATH,PROJECT["subjects"][0])
SUBJECTS = os.listdir(SUBJECTS_PATH)[0]
    
    
# save json settings
json.dump(SETTINGS, open(SETTINGS_PATH, 'w'), indent=4)

breakpoint()
def create_subject_settings(subject_path):
    
    subject_info = json.load(open(subject_path + '/settings.json'))

def about():
    '''
    Function to print the version of the package and the authors
    '''
    print('BOPSpy - Batch OpenSim Processing Scripts Python')
    print('Authors: Basilio Goncalves')
    print('ispired by BOPS: MATALB DOI: 10.1080/10255842.2020.1867978 - https://pubmed.ncbi.nlm.nih.gov/33427495/')
    print('Python version by Bas Goncalves')

def greet():
    print("Are you ready to run openSim?!")
 
def is_setup_file(file_path, type = 'OpenSimDocument', print_output=False):
    '''
    Function to check if a file is an OpenSim setup file. 
    The function reads the file and checks if the type is present in the file.
    
    '''
    is_setup = False
    try:
        with open(file_path, 'r') as file:
            for line in file:
                if type in line:
                    is_setup = True
                    break
                
                #if is last line and no match, return false
                if line == None:
                    is_setup = False
                    
    except Exception as e:
        print(f"Error reading file: {e}")
    
    if print_output and is_setup:
        print(f"{file_path} is a setup file")
    elif print_output and not is_setup:
        print(f"{file_path} is not a setup file")
        
    return is_setup  

def check_file_path(filepath, prompt = 'Select file'):
    """
    bops.check_file_path(filepath, prompt = 'Select file')
    
    Use to check if a file path is valid. If not, it will open a file dialog to select the file.
    """
    if not filepath:
        root = tk.Tk(); root.withdraw()
        filepath = filedialog.askopenfilename(title=prompt)
        
        root.destroy()
        
    return filepath

def check_folder_path(folderpath, prompt = 'Select folder'):
    if not folderpath or not os.path.isdir(folderpath):
        root = ctk.CTk(); root.withdraw()
        folderpath = ctk.filedialog.askdirectory(title=prompt)
        root.destroy()
        
    return folderpath

def export_c3d(c3dFilePath):
    
    c3dFilePath = check_file_path(c3dFilePath, prompt = 'Select c3d file')
    
    analog_file_path = os.path.join(os.path.dirname(c3dFilePath),'analog.csv')
    
    # if the file already exists, return the file
    if os.path.isfile(analog_file_path):
        df = pd.read_csv(analog_file_path)
        return df
    
    print('Exporting analog data to csv ...')
    
    # read c3d file
    reader = c3d.Reader(open(c3dFilePath, 'rb'))

    # get analog labels, trimmed and replace '.' with '_'
    analog_labels = reader.analog_labels
    analog_labels = [label.strip() for label in analog_labels]
    analog_labels = [label.replace('.', '_') for label in analog_labels]

    # get analog labels, trimmed and replace '.' with '_'
    first_frame = reader.first_frame
    num_frames = reader.frame_count
    fs = reader.analog_rate

    # add time to dataframe
    initial_time = first_frame / fs
    final_time = (first_frame + num_frames-1) / fs
    time = np.arange(first_frame / fs, final_time, 1 / fs) 

    df = pd.DataFrame(index=range(num_frames),columns=analog_labels)
    df['time'] = time
    
    # move time to first column
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]    
    
    # loop through frames and add analog data to dataframe
    for i_frame, points, analog in reader.read_frames():
        
        # get row number and print loading bar
        i_row = i_frame - reader.first_frame
        # msk.ut.print_loading_bar(i_row/num_frames)
        
        # convert analog data to list
        analog_list  = analog.data.tolist()
        
        # loop through analog channels and add to dataframe
        for i_channel in range(len(analog_list)):
            channel_name = analog_labels[i_channel]
            
            # add channel to dataframe
            df.loc[i_row, channel_name] = analog[i_channel][0]
    
    # save emg data to csv   
    df.to_csv(analog_file_path)
    print('analog.csv exported to ' + analog_file_path)  
    
    return df

def export_analog(c3dFilePath=None, columns_to_mot='all'):
    
    c3dFilePath = check_file_path(c3dFilePath, prompt = 'Select c3d file')
    
    reader = c3d.Reader(open(c3dFilePath, 'rb'))

    # get analog labels, trimmed and replace '.' with '_'
    analog_labels = reader.analog_labels
    analog_labels = [label.strip() for label in analog_labels]
    analog_labels = [label.replace('.', '_') for label in analog_labels]
    
    # remove those not in columns_to_mot (fix: use column names to filter and get indices)
    if columns_to_mot != 'all':
        indices = [i for i, label in enumerate(analog_labels) if label in columns_to_mot]
        analog_labels = [analog_labels[i] for i in indices]
    else:
        indices = list(range(len(analog_labels)))
        columns_to_mot = analog_labels

    # get analog labels, trimmed and replace '.' with '_'
    fs = reader.analog_rate

    # add time to dataframe
    marker_fs = reader.point_rate  # This is the actual frame rate for kinematics
   

    first_time = reader.first_frame / marker_fs
    final_time = (reader.first_frame + reader.frame_count - 1) / marker_fs
    time = np.arange(first_time, final_time + 1 / marker_fs, 1 / marker_fs)
  
    num_frames = len(time)
    df = pd.DataFrame(index=range(num_frames), columns=analog_labels)
    df['time'] = time

    # move time to first column
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols] 

    # loop through frames and add analog data to dataframe
    for i_frame, points, analog in reader.read_frames():
        
        # get row number and print loading bar
        i_row = i_frame - reader.first_frame
        # msk.ut.print_loading_bar(i_row/num_frames)
        
        # loop through selected analog channels and add to dataframe (fix: iterate over filtered indices)
        for idx, i_channel in enumerate(indices):
            channel_name = analog_labels[idx]
            df.loc[i_row, channel_name] = analog[i_channel][0]
    
    # remove rows with NaN values
    df = df.dropna()
    
    # save emg data to csv
    analog_csv_path = c3dFilePath.replace('.c3d', '_analog.csv')
    df.to_csv(analog_csv_path, index=False)
    
    # save to mot
    # self.csv_to_mot()
    
    return analog_csv_path

def header_mot(df,name):

        num_rows = len(df)
        num_cols = len(df.columns) 
        inital_time = df['time'].iloc[0]
        final_time = df['time'].iloc[-1]
        df_range = f'{inital_time}  {final_time}'


        return f'name {name}\nnRows={num_rows}\nnColumns={num_cols}\n \nendheader'

def csv_to_mot(emg_csv, columns = 'all'):
    '''
    '''
    
    emg_data = pd.read_csv(emg_csv)
    
    try:
        time = emg_data['time']
    except:
        time = emg_data['Time']

    # start time from new time point
    start_time = time.iloc[0]
    end_time = time.iloc[-1]

    num_samples = len(emg_data)
    new_time = np.linspace(start_time, end_time, num_samples)

    # remove columns not in columns_to_mot
    if columns != 'all':
        emg_data = emg_data[columns]

    emg_data['time'] = new_time
    # Ensure 'time' column is the first column
    cols = emg_data.columns.tolist()
    cols.insert(0, cols.pop(cols.index('time')))
    emg_data = emg_data[cols]

    # Define a new file path 
    new_file_path = os.path.join(emg_csv.replace('.csv', '.mot'))

    # Save the modified DataFrame
    emg_data.to_csv(new_file_path, index=False)  # index=False prevents adding an extra index column

    # save to mot
    header = header_mot(emg_data, "processed_emg_signals")

    mot_path = new_file_path.replace('.csv','.mot')
    with open(mot_path, 'w') as f:
        f.write(header + '\n')  
        # print column names 
        f.write('\t'.join(map(str, emg_data.columns)) + '\n')
        for index, row in emg_data.iterrows():
            f.write('\t'.join(map(str, row.values)) + '\n')  
    
    print(f"File saved: {mot_path}")
    
    return mot_path

def time_normalised_df(df, fs=None):
    if not isinstance(df, pd.DataFrame):
        raise Exception('Input must be a pandas DataFrame')
    
    if not fs:
        try:
            fs = 1 / (df['time'][1] - df['time'][0])  # Ensure correct time column
        except KeyError:
            raise Exception('Input DataFrame must contain a column named "time"')
        
    normalised_df = pd.DataFrame(columns=df.columns)

    for column in df.columns:
        normalised_df[column] = np.zeros(101)

        currentData = df[column].dropna()  # Remove NaN values

        timeTrial = np.linspace(0, len(currentData) / fs, len(currentData))  # Original time points
        Tnorm = np.linspace(0, timeTrial[-1], 101)  # Normalize to 101 points

        normalised_df[column] = np.interp(Tnorm, timeTrial, currentData)  # Interpolate

    return normalised_df

def load_settings(settings_file_json=None):
    if not settings_file_json:
        settings_file_json = os.path.join(BOPS_PATH,'settings.json')
    
    return read.json(settings_file_json)

class settings:
    def __init__(self, settings_file_json=None):
        if not settings_file_json:
            settings_file_json = os.path.join(BOPS_PATH,'settings.json')
        
        self.settings = read.json(settings_file_json)
        
        # Check if contains all the necessary variables
        try:
            for var in self.settings:
                if var not in self.settings:
                    self.settings[var] = None
                    print(f'{var} not in settings. File might be corrupted.')
            
        except Exception as e:
            print('Error checking settings variables')
            
        # save the json file path
        try:
            self.settings['jsonfile'] = settings_file_json
            self.settings.pop('jsonfile', None)
        except:
            print('Error saving json file path')
                   
class log:
    def error(error_message):
        try:
            with open(os.path.join(BOPS_PATH,"error_log.txt"), 'a') as file:
                date = time.strftime("%Y-%m-%d %H:%M:%S")
                file.write(f"{date}: {error_message}\n")
        except:
            print("Error: Could not log the error")
            return

class read: 
    '''
    Class to store data from different file types
    
    Usage: 
    c3d_data = msk.bops.reader.c3d(filepath) # read c3d file and return data as a dictionary    
    json_data = msk.bops.reader.json(filepath) # read json file and return data as a dictionary
    
    '''
    def c3d(filepath=None):
        ''''
        Function to read a c3d file and return the data as a dictionary
        '''
        filepath = check_file_path(filepath, prompt = 'select your .c3d file')
        
        try:
            data = c3d.Reader(open(filepath, 'rb'))
        
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
        
        # add dataframe to the reader class
        try:
            df = export_c3d(filepath)
            data.__setattr__('dataframe', df)
            
        except Exception as e:
            print(f"Error converting data to dataframe: {e}")
        
        return data
                              
    def json(filepath=None):
        
        filepath = check_file_path(filepath, prompt = 'select your .json file')
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        return data
    
    def mot(filepath= None):
        '''
        Function to read a .mot file and return the data as a dictionary (should work for .sto files too)
        
        data = msk.bops.reader.mot(filepath)
        '''
        filepath = check_file_path(filepath, prompt = 'select your .mot or .sto file')
        # find the line containins "endheader"
        with open(filepath, 'r') as file:
            line_count = 0
            for line in file:
                line_count += 1
                if 'endheader' in line:
                    break
        
        # if not found, return None
        if not line:
            print('endheader not found')
            return None
        
        try:
            data = pd.read_csv(filepath, sep='\t', skiprows=line_count)
        except Exception as e:
            print('Error reading file: ' + str(e))
        
        return data
    
    def file(filepath):
        
        filepath = check_file_path(filepath, prompt = 'select your file')
        data=[]
        try:
            with open(filepath, 'r') as file:
                for line in file:
                    data.append(line)
                    
        except Exception as e:
            print(f"Error reading file: {e}")
        
        return data

    def project_settings(settings_file_json):    
        '''
        open the json file and check if all the necessary variables are present
        valid_vars = ['project_folder','subjects','emg_labels','analog_labels','filters']
        
        '''
        
        valid_vars = ['project_folder','subjects','emg_labels','analog_labels','filters']
        
        
        # Open settings file
        try:
            with open(settings_file_json, 'r') as f:
                settings = json.load(f)
        except:
            print('Error loading settings file')  
            
                        
        # Check if contains all the necessary variables
        try:
            for var in valid_vars:
                if var not in settings:
                    settings[var] = None
                    print(f'{var} not in settings. File might be corrupted.')
            
            # look for subjects in the simulations folder and update list
            if settings['project_folder']:
                settings['subjects'] = get_subject_folders(settings['project_folder'])
                
        except Exception as e:
            print('Error checking settings variables')
            
        
        # save the json file path
        try:
            settings['jsonfile'] = settings_file_json
            settings.pop('jsonfile', None)
        except:
            print('Error saving json file path')

class write:
    def json(data, file_path=None):
        if not file_path:
            file_path = filedialog.asksaveasfilename(defaultextension=".json")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error writing JSON file: {e}")
            
    def mot(data, file_path=None):
        if not file_path:
            file_path = filedialog.asksaveasfilename(defaultextension=".mot")
        
        try:
            data.to_csv(file_path, sep='\t', index=False)
        except Exception as e:
            print(f"Error writing MOT file: {e}")
            
    def xml(data, file_path=None):
        if not file_path:
            file_path = filedialog.asksaveasfilename(defaultextension=".xml")
        
        try:
            with open(file_path, 'w') as f:
                f.write(data)
        except Exception as e:
            print(f"Error writing XML file: {e}")
               
class convert:
    def c3d_to_osim(file_path=None):
        
        if not file_path:
            file_path = filedialog.askopenfilename()
            
        print('Converting c3d to osim...')
        
        print('NOT FINISHED...')

class create:
    def grf_xml(grf_mot_path, save_path, nforceplates=3):
        try:
            with open(save_path, 'w') as file:
                file.write('<?xml version="1.0"?>\n')
                file.write('<OpenSimDocument Version="30000">\n')
                file.write('  <Model>\n')
                file.write('    <ForceSet>\n')
                
                for i in range(nforceplates):
                    file.write(f'      <GroundReactionForcePlate{i+1}>\n')
                    file.write(f'        <File>{grf_mot_path}</File>\n')
                    file.write('      </GroundReactionForcePlate>\n')
                
                file.write('    </ForceSet>\n')
                file.write('  </Model>\n')
                file.write('</OpenSimDocument>')
        except Exception as e:
            print(f"Error creating XML file: {e}")
            return
    
    def grf_mot(grf_path, save_path, headerlines=6):
        try:
            grf_data = pd.read_csv(grf_path, sep='\t', skiprows=headerlines)
            grf_data.to_csv(save_path, sep='\t', index=False)
        except Exception as e:
            print(f"Error reading or writing GRF file: {e}")
            return
          
class run:
    def __init__(self):
        pass
    
    def c3d_to_trc(c3d_file, trc_file, headerlines=6):
        try:
            c3d_data = c3d.Reader(open(c3d_file, 'rb'))
        except Exception as e:
            print(f"Error reading c3d file: {e}")
            return
        
        try:
            with open(trc_file, 'w') as file:
                file.write("PathFileType\t4\t(X/Y/Z)\t" + c3d_file + "\n")
                file.write("DataRate\t" + str(c3d_data['parameters']['POINT']['DATA_RATE']) + "\n")
                file.write("Frame#\tTime\tX1\tY1\tZ1\n")
                
                for i in range(c3d_data['parameters']['POINT']['NANALOG']):
                    file.write(str(i) + "\t" + str(c3d_data['parameters']['POINT']['DATA'][i]) + "\n")
        except Exception as e:
            print(f"Error writing trc file: {e}")
            return
    
    def inverse_kinematics(model_path, marker_path, output_folder, setup_template_path):
        try:
            print('Running inverse kinematics ...')
            
            
        except Exception as e:
            print(f"Error running inverse kinematics: {e}")
    
    def inverse_dynamics(model_path=None, ik_mot_path=None, output_folder=None, grf_xml_path=None, time_range=None, xml_setup_path=None):
        '''
        bops.inverse_dynamics(model_path, ik_mot_path, output_folder, grf_xml_path, time_range, xml_setup_path)
        '''
                
        try:
            model = osim.Model(model_path)
        except Exception as e:
            print(f"Error loading model: {e}")
            return    
        
        try:
            print('Running inverse dynamics ...')
            
            coordinates = osim.CoordinateSet(ik_mot_path)
            
            id_tool = osim.InverseDynamicsTool()
            id_tool.setModel(model)
            id_tool.setCoordinatesFileName(ik_mot_path)
            id_tool.setOutputGenForceFileName(os.path.join(output_folder, 'inverse_dynamics.sto'))
            id_tool.setExternalLoadsFileName(grf_xml_path)
            id_tool.setStartTime(time_range[0])
            id_tool.setEndTime(time_range[1])
            id_tool.printToXML(os.path.join(output_folder, 'inverse_dynamics_setup.xml'))
            
            id_tool.run()
            
            
        except Exception as e:
            print(f"Error running inverse dynamics: {e}")
    
    def muscle_analysis(model_path, ik_mot_path, output_folder, grf_xml_path, time_range=None, xml_setup_path=None):
        
        if os.path.isfile(xml_setup_path):
            ma_tool = osim.AnalysisTool(xml_setup_path)
            ma_tool.setModel(model_path)
            ma_tool.setCoordinatesFileName(ik_mot_path)
            ma_tool.setOutputGenForceFileName(os.path.join(output_folder, 'muscle_analysis.sto'))
            ma_tool.run()    
        
        
        try:
            print('Running muscle analysis ...')
            
            model = osim.Model(model_path)
            
            coordinates = osim.CoordinateSet(ik_mot_path)
            
            ma_tool = osim.MuscleAnalysisTool()
            ma_tool.setModel(model)
            ma_tool.setCoordinatesFileName(ik_mot_path)
            ma_tool.setOutputGenForceFileName(os.path.join(output_folder, 'muscle_analysis.sto'))
            ma_tool.setExternalLoadsFileName(grf_xml_path)
            ma_tool.setStartTime(time_range[0])
            ma_tool.setEndTime(time_range[1])
            ma_tool.printToXML(os.path.join(output_folder, 'muscle_analysis_setup.xml'))
            
            ma_tool.run()
            
        except Exception as e:
            print(f"Error running muscle analysis: {e}")
    
    def ceinms_calibration(xml_setup_file=None):
        '''
        msk.bops.run.ceinms_calibration(xml_setup_file)
        '''

        if not os.path.isfile(xml_setup_file):
            print('The path provided does not exist')
            return
        
        try:        
            ceinms_install_path = os.path.join(BOPS_PATH, 'src', 'ceinms2', 'src')
            command = " ".join([ceinms_install_path + "\CEINMScalibrate.exe -S", xml_setup_file])
            print(command)
            # result = subprocess.run(command, capture_output=True, text=True, check=True)
            result = None
            return result
        except Exception as e:
            print(e)
            return None
    
    def ceinms_execution(xml_setup_file=None):
        '''
        msk.bops.run.ceinms_run(xml_setup_file)
        
        
        '''
        
        if xml_setup_file is None:
            print('Please provide the path to the xml setup file for calibration')
            return
        elif not os.path.isfile(xml_setup_file):
            print('The path provided does not exist')
            return
        
        try:        
            ceinms_path = os.path.join(BOPS_PATH, 'src', 'ceinms2',)
            ceinms_install_path = os.path.join(BOPS_PATH, 'src', 'ceinms2', 'src')
            command = " ".join([ceinms_install_path + "\CEINMSrun.exe -S", xml_setup_file])
            print(command)
            # result = subprocess.run(command, capture_output=True, text=True, check=True)
            result = None
            return result
        except Exception as e:
            print(e)
            return None
      
class Trial:
    '''
    Class to store trial information and file paths, and export files to OpenSim format
    
    Inputs: trial_path (str) - path to the trial folder
    
    Attributes:
    path (str) - path to the trial folder
    name (str) - name of the trial folder
    og_c3d (str) - path to the original c3d file
    c3d (str) - path to the c3d file in the trial folder
    markers (str) - path to the marker trc file
    grf (str) - path to the ground reaction force mot file
    ...
    
    Methods: use dir(Trial) to see all methods
    
    '''
    def __init__(self, trial_path, trial_settings = None):      
        
        if trial_settings:
            settings = load_settings(trial_settings)
            self.path = settings['path']
            self.name = settings['name']
            self.og_c3d = settings['og_c3d']
            self.c3d = settings['c3d']
            self.markers = settings['markers']
            self.grf = settings['grf']
            self.emg = settings['emg']
            self.model = settings['model']
            self.ik = settings['ik']
            self.id = settings['id']
            self.so_force = settings['so_force']
            self.so_activation = settings['so_activation']
            self.jra = settings['jra']
            self.grf_xml = settings['grf_xml']
            self.settings_json = settings['settings_json']
            self.time_range = settings['time_range']
            
        else:
            self.path = trial_path
            self.name = os.path.basename(trial_path)
            self.c3d = os.path.join(os.path.dirname(trial_path), self.name + '.c3d')
            self.markers = os.path.join(trial_path,'markers_experimental.trc')
            self.grf = os.path.join(trial_path,'grf.mot')
            self.emg = os.path.join(trial_path,'emg.csv')
            self.model = os.path.join(trial_path,'model.osim')
            self.ik = os.path.join(trial_path,'ik.mot')
            self.id = os.path.join(trial_path,'inverse_dynamics.sto')
            self.so_force = os.path.join(trial_path,'static_optimization_force.sto')
            self.so_activation = os.path.join(trial_path,'static_optimization_activation.sto')
            self.jra = os.path.join(trial_path,'joint_reacton_loads.sto')
            self.grf_xml = os.path.join(trial_path,'grf.xml')
            self.settings_json = os.path.join(self.path,'settings.json')
        
            # add time range from c3d
            try:
                c3d_data = read.c3d(self.c3d)
                self.time_range = [c3d_data['first_frame'], c3d_data['last_frame']]
            except Exception as e:
                print(f"Error reading c3d file: {e}")
                self.time_range = None
        
        self.file_check = {}
        for file in os.listdir(self.path):
            file_path = os.path.join(self.path, file)
            self.file_check[file] = os.path.isfile(file_path)
            
    def check_files(self):
        '''
        Output: True if all files exist, False if any file is missing
        '''
        files = self.__dict__.values()
        all_files_exist = True
        for file in files:
            if not os.path.isfile(file):
                print('File not found: ' + file)
                all_files_exist = False
                
        return all_files_exist
    
    def create_settings_json(self, overwrite=False):
        if os.path.isfile(self.settings_json) and not overwrite:
            print('settings.json already exists')
            return
        
        settings_dict = self.__dict__
        msk.bops.save_json_file(settings_dict, self.settings_json)
        print('trial settings.json created in ' + self.path)
    
    def exportC3D(self):
        msk.bops.c3d_osim_export(self.og_c3d) 

    def create_grf_xml(self):
        osim.create_grf_xml(self.grf, self.grf_xml)

    def run_ik(self, setup_xml=None):
        
        if setup_xml:
            try:
                ik_tool = osim.InverseKinematicsTool(setup_xml)                
                ik_tool.run()
                
            except Exception as e:
                print(f"Error running inverse kinematics: {e}")
        else:
            print('No setup xml file provided.')
            return
        
        try:
            print('Running inverse kinematics ...')
            
            ik_tool = osim.InverseKinematicsTool()
            ik_tool.setModel(osim.Model(self.model_path))
            ik_tool.setMarkerFileName(self.markers)
            ik_tool.setOutputMotionFileName(self.ik)
            
            ik_tool.setStartTime(self.time_range[0])
            ik_tool.setEndTime(self.time_range[1])
            
            ik_tool.setOutputMotionFileName(self.ik)
            ik_tool.setMarkerFileName(self.markers)
            ik_tool.setOutputMotionFileName(self.ik)
            
            ik_tool.printToXML(os.path.join(self.path, 'setup_ik.xml'))
            print('setup_ik.xml created in ' + self.path)
            
            print('Running inverse kinematics ...')
            ik_tool.run()
            
            print('Inverse kinematics completed')   
            
        except:
            print('Inverse kinematics already run')
    
    def write_to_json(self):
        '''
        Write the trial settings to a json file
        '''
        try:
            with open(self.settings_json, 'w') as f:
                json.dump(self.__dict__, f, indent=4)
                
            print('Trial settings written to ' + self.settings_json)
        except Exception as e:
            print(f"Error writing JSON file: {e}")
    
class Subject:
    def __init__(self, subject_json):
        self = read.json(subject_json)

class Project:
    
    def __init__(self, file_path=None):        
        # load settings
        try:
            if file_path.endswith('.json'):
                self.settings = read.json(file_path)
            else:
                self.settings = read.json(os.path.join(file_path,'settings.json'))
        except Exception as e:
            print(f"Error loading project settings: {e}")
                   
    def start(self, project_folder=''):
    
        if not project_folder:
            settings = settings.read()
        else:
            pass
        
        print('NOT FINISHED....')
                   

#%% ######################################################  TESTING  #####################################################################
class test(unittest.TestCase):
    
    def test_start(self):
        print("Starting tests...")
        self.assertTrue(True, "Test passed")
    
    def test_identifier(self):
        self.assertEqual(SETTINGS['identifier'], 'msk_modelling_python')
    
    def test_print_settings(self):
        self.assertIn("bops", SETTINGS, "SETTINGS should contain a field called 'bops'")
        self.assertIsNotNone(SETTINGS, "SETTINGS should not be None")
    
    def test_current_project(self):
        self.assertIsNotNone(SETTINGS['current_project'], "SETTINGS should contain a field called 'current_project'")
        self.assertIsInstance(SETTINGS['current_project'], str, "current_project should be a string")
        self.assertTrue(os.path.isfile(SETTINGS['current_project']), "current_project should be a valid directory")

if __name__ == "__main__":
    #if tests are all ok continue
    results = unittest.main()
    
    if results.result.wasSuccessful():
        print("All tests passed.")
        
    



#%% END