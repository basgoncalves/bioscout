import os
import subprocess
from xml.etree import ElementTree as ET
import time
from . import utils
from .utils import load_any_data_file
import matplotlib.pyplot as plt
from . import openSim
from . import ceinms
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score




if __name__ == "__main__":
        
        calibration_trials = ['Walking_02']

        subject  = 'Athlete_03_Lernagopal' # Athlete_03_Lernagopal Athlete_03_MRI_Katya Athlete_03_Lernagopal_optimised Athlete_03_GPK Athlete_03_Uhlrich
        session = '25_03_31'
        trialList = ['Walking_02', 'Walking_03', 'Squat_35kg_02'] #'Squat_BW_01' Squat_35kg_01 Walking_02

        for trial in trialList[0:1]:
                trialPath = os.path.join(utils.SIMULATIONS_DIR, subject, session, trial)
                print(f'Analyzing trial at path: {trialPath}')        

                # Assume
                analysis = utils.Analyse(trialPath=os.path.join(utils.SIMULATIONS_DIR, subject, session, trial))
                analysis._update_model()

                # time_range = analysis.get_time_range_from_eventDetector()
                # print(f"Determined time range for analysis: {time_range}")
                
                # Reset settings XML to ensure a clean slate for the analysis
                analysis.copy_input_files(src_subject='Athlete_03') 
                analysis.time_range = analysis.get_time_range()
                analysis.reset_settings_xml()
                
                os.startfile(analysis.settingsXML)
                
                # run the full analysis pipeline
                analysis.update_trial_attribute('replace', 'True')
        
                analysis.run_ik()
                analysis.run_id()
                analysis.run_ma()
                analysis.run_so()
                analysis.run_jra()
                
                analysis.create_ceinms_input_data()
                analysis.create_excitation_generator()

                if any(trial in analysis.path for trial in calibration_trials):
                        analysis.create_ceinms_model()
                        analysis.create_ceinms_calibration_cfg(calibration_trial_names=calibration_trials)
                        analysis.create_ceinms_calibration_setup()
                        analysis.run_ceinms_calibration()

                
                analysis.create_ceinms_optimise_setup()
                analysis.run_ceinms_optimise()

                analysis.create_ceinms_exe_cfg()
                analysis.create_ceinms_exe_setup()
                analysis.create_ceinms_cfg_from_excitation_generator()

                analysis.run_ceinms_exe()

                analysis.run_jra_ceinms()
                
        analysis.push_subject_results_to_git()




# END       