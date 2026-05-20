import os
from xml.etree import ElementTree as ET
import time
from . import utils
from . import openSim
from . import ceinms

SUBJECTS_TO_ANALYSE =  ['Athlete_03','Athlete_03_MRI_Katya', 'Athlete_03_Lernagopal','Athlete_03_Lernagopal_optimised']  # ,'Athlete_03_MRI_Katya','Athlete_03_Lernagopal'
SESSIONS_TO_ANALYSE = ['25_03_31'] 
TRIALS_TO_ANALYSE =  ['Walking_03','Squat_35kg_01', 'Squat_35kg_02', 'Squat_bw_01', 'Squat_bw_02'] #Walking_02 Squat_bw_02 Squat_35kg_01
CEINMS_CALIBRATION_TRIALS = ['Walking_02'] 

class Execute:
    ''' Logics for which analyses to execute '''
    def __init__(self):
        
        self.replace = True

        self.INCREASE_MUSCLE_FORCE = False
        self.SCALE_FACTOR = 3

        self.IK = False
        self.ID = False
        self.MA = False
        self.SO = False
        self.JRA = False
        
        self.EMG_NORMALISE = False
        self.SCALE_EMG = False
        self.EMG_SCALE_FACTOR = 0.7
        
        self.CREATE_CEINMS_FILES = False
        self.CREATE_CEINMS_MODEL = False
        
        self.CEINMS_CALIBRATION = False
        self.CEINMS_CALIBRATION_PLOTS = False
        
        self.CEINMS_OPTIMISATION = False
        self.CEINMS_EXE = False
        self.CEINMS_EXE_LOOP = False
        
        self.JRA_CEINMS = False
        
        self.CREATE_PLOTS = False
        
        self.PLOT_IK = False
        self.PLOT_ID = False
        self.PLOT_MA = False
        self.PLOT_SO = False
        self.PLOT_JRA = False
        self.PLOT_EMG = False
          
        self.push_trial_to_git = False
        self.push_subject_to_git = True

def run_all_step(analyse: utils.Analyse):

    # Run IK
    if Execute().IK:
        analyse.run_ik()

    # Run ID
    if Execute().ID: 
        analyse.run_id()

    # Run muscle analysis
    if Execute().MA: 
        analyse.run_ma()

    # Run Static Optimization
    if Execute().SO:
        analyse.run_so()

    # Run Joint Reaction Analysis
    if Execute().JRA:
        analyse.run_jra()
        
    # Normalise EMG data
    if Execute().EMG_NORMALISE:

        utils.print_to_log(f'Normalising EMG data for: {analyse.subject} / {analyse.trial}')
        emg_normalise_list = []

        for name in TRIALS_TO_ANALYSE:

            abs_path_emg = str(analyse.emg)
            if os.path.exists(abs_path_emg):
                emg_normalise_list.append(abs_path_emg)
            else:
                print(f"EMG file not found: {abs_path_emg}")

        openSim.run_emg_normalise(target_emg_path=str(analyse.emg), 
                    normalise_emg_list=emg_normalise_list)

        utils.print_to_log(f'EMG data normalised. Results are saved in {analyse.emg}')

    if Execute().SCALE_EMG:
        analyse.scale_emg(scale_factor=Execute().EMG_SCALE_FACTOR)
        
    # Create CEINMS setup files
    if Execute().CREATE_CEINMS_FILES:

        # # in case model is different for CEINMS  and SO
        # if analyse.model_dir.__contains__('_increased_3.00.osim'):
        #     new_model_name = analyse.model_dir.replace('_increased_3.00.osim', f'.osim')
        #     analyse.update_model(new_model_name)

        analyse.create_ceinms_model()

        analyse.create_ceinms_input_data()
        
        analyse.create_ceinms_calibration_cfg(calibration_trial_names=CEINMS_CALIBRATION_TRIALS)

        analyse.create_ceinms_calibration_setup()

        analyse.create_excitation_generator()

        analyse.create_ceinms_exe_cfg()

        analyse.create_ceinms_exe_setup()
                
    # CEINMS calibration and optimization
    if Execute().CEINMS_CALIBRATION and analyse.trial in CEINMS_CALIBRATION_TRIALS:
        
        try:        
            analyse.run_ceinms_calibration()
        
        except Exception as e:
            print(f"Error during CEINMS calibration: {e}")
            utils.print_to_log(f'Error during CEINMS calibration: {e}')

    # CEINMS optimisation
    if Execute().CEINMS_OPTIMISATION:
        try:
            analyse.run_ceinms_optimise()
        except Exception as e:
            utils.print_to_log(f'Error during CEINMS optimisation: {e}')

    if Execute().CEINMS_EXE:
        try:
           analyse.run_ceinms_exe()
        except Exception as e:
            utils.print_to_log(f'Error during CEINMS executable run: {e}')

        # Run Joint Reaction Analysis for CEINMS
    
    if Execute().CEINMS_EXE_LOOP:
        analyse.run_ceinms_exe_loop()
    
    # Run Joint Reaction Analysis with CEINMS muscle forces
    if Execute().JRA_CEINMS:
        analyse.run_jra_ceinms()
    
class GUI:
    ''' Logics for GUI '''
    def __init__(self):
        pass

if __name__ == "__main__":
    
    utils.print_to_log("Starting analysis...")

    start_time = time.time()
    
    print(f'Check settings in {utils.__file__}')
    time.sleep(1)
    for subject in SUBJECTS_TO_ANALYSE:
        for session in SESSIONS_TO_ANALYSE:
            for trial_name in TRIALS_TO_ANALYSE:
                
                trialPath = os.path.join(utils.SIMULATIONS_DIR, subject, session, trial_name)                
                analysis = utils.Analyse(trialPath=trialPath) 

                template_subject = '_'.join(subject.split('_')[0:2])
                analysis.copy_input_files(src_subject=template_subject, replace=False) 
                
                analysis.update_trial_attribute('replace', Execute().replace)
                
                utils.print_to_log(f'Running analysis for: {trialPath}')

                ###########---Run main analysis function---########################
                run_all_step(analyse=analysis)

                ###################################################################

                utils.print_to_log(f'Analysis completed for: {trialPath}')

                
                if Execute().push_trial_to_git:
                    analysis.push_trial_results_to_git()
        
        if Execute().push_subject_to_git:
            analysis.push_subject_results_to_git()

        
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    utils.print_to_log(f"Total analysis time: {elapsed_time:.2f} seconds \n \n")

