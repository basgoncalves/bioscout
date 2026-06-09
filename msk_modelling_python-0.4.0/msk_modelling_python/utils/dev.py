import sys
from pathlib import Path
import os
from xml.etree import ElementTree as ET
import time
import matplotlib.pyplot as plt
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util

# Load __init__.py as 'utils' and register it so siblings can find it
_spec = importlib.util.spec_from_file_location('utils', Path(__file__).parent / '__init__.py')
utils_spec = importlib.util.module_from_spec(_spec)
sys.modules['utils'] = utils_spec
_spec.loader.exec_module(utils_spec)

###############################################################################################
# Check settings.py before running this script
import settings
import utils
###############################################################################################

def _parallell_worker(trial, subject, session):
        """Top-level function required for multiprocessing pickling."""
        import utils, os

        try:
                trialPath = os.path.join(utils.SIMULATIONS_DIR, subject, session, trial)
                analysis = utils.Analyse(trialPath=trialPath)
                analysis._reset_settings_xml()
                analysis.update_trial_attribute('replace', 'True')
        except Exception as e:
                return trial, str(e)

        try:
                run_all_step(analysis)
                return trial, None
        except Exception as e:
                return trial, str(e)

def run_all_step(analysis: utils.Analyse):

        analysis._update_model() 
        analysis.update_trial_attribute('replace', True)
        analysis.increase_muscle_force(factor=3.0)

        # analysis.copy_input_files(src_subject='Athlete_03')
        # analysis.reset_settings_xml()

        # analysis.export_c3d(create_folder=False)

        analysis.run_ik()
        analysis.run_id()

        analysis.run_ma()
        analysis.check_moment_arms()
        # analysis.adjust_moment_arms()
        # scale_moment_arm_based_on_emg(analysis)

        # if not analysis.model_dir.__contains__('_increased_3.00.osim'):
        #     new_model_name = analysis.model_name.replace('.osim', '_increased_3.00.osim')
        #     analysis.update_model(new_model_name)
        # analysis.run_so()
        # analysis.run_jra()

        # analysis.calculate_muscle_moments(forces_type='so')

        # analysis.run_emg_normalise()
        # analysis.plot_emg()

        # analysis.create_ceinms_input_data()
        # analysis.create_excitation_generator()
        
        calibration_trial_names = settings.calibration_trials
        if analysis.trial in calibration_trial_names[0:1]:
                analysis.create_ceinms_model()
                analysis.create_ceinms_calibration_cfg(calibration_trial_names=calibration_trial_names)
                analysis.create_ceinms_calibration_setup()
                analysis.run_ceinms_calibration()


        # analysis.create_ceinms_optimise_setup()
        # analysis.run_ceinms_optimise()

        # analysis.create_ceinms_exe_cfg()
        # analysis.create_ceinms_exe_setup()
        # analysis.create_ceinms_cfg_from_excitation_generator()

        # analysis.run_ceinms_exe()

        # analysis.run_jra_ceinms()

        # analysis.plot_summary()

        # analysis.push_subject_results_to_git()

def scale_moment_arm_based_on_emg(analysis: utils.Analyse):
        """
        Scale moment arms time-point-by-time-point based on the corresponding EMG activation.

        Algorithm: factor(t) = 1 + emg(t)
        → every 10% of normalised EMG (0–1) adds a 30% increase to the moment arm at that instant.

        Uses settings.EMG_muscle_mapping to map each EMG channel to its muscles, and
        settings.DOFs to determine which MomentArm .sto files to modify.
        EMG is interpolated onto the moment-arm time grid so mismatched sample rates are handled.
        """
        import numpy as np

        muscles_to_skip = ['vaslat_l', 'vasmed_l', 'vaslat_r', 'vasmed_r', 'recfem_l', 'sart_l', 'tfl_l', 'recfem_r', 'sart_r', 'tfl_r']

        

        os.chdir(analysis.path)
        emg_data = utils.load_any_data_file(analysis.emg)
        emg_time = emg_data['time'].values

        for dof_name in settings.DOFs:
                ma_path = os.path.join(analysis.ma, f"_MuscleAnalysis_MomentArm_{dof_name}.sto")
                if not os.path.exists(ma_path):
                        print(f"[skip] MomentArm file not found: {ma_path}")
                        continue

                ma_data = utils.load_any_data_file(ma_path).copy()
                ma_time = ma_data['time'].values
                modified = False

                for emg_channel, muscles in settings.EMG_muscle_mapping.items():
                        if emg_channel not in emg_data.columns:
                                continue

                        # Interpolate EMG onto the moment-arm time grid
                        emg_signal = emg_data[emg_channel].values
                        emg_interp = np.interp(ma_time, emg_time, emg_signal)
                        factor = 1.0 + 3 * emg_interp  # 10% EMG → ×1.3 on moment arm

                        for muscle in muscles:
                                if muscle not in ma_data.columns:
                                        continue
                                if muscle in muscles_to_skip:
                                        continue
                                ma_data[muscle] = ma_data[muscle] * factor
                                modified = True

                if modified:
                        utils.write_sto_file(dataFrame=ma_data, file_path=ma_path)
                        print(f"[EMG-scaled MA] {dof_name}")

def test():
   pass


if __name__ == "__main__":

        MODE = 'sequential' # parallel sequential

        subject = settings.subject_list[0]
        sesssion = settings.session_list[0]
        trialList = settings.trial_list[0:]

        print(f"Subject: {subject}")
        print(f"Session: {sesssion}")
        print(f"Processing trials: {trialList}")

        # check to contiue with user input
        proceed = input("Do you want to proceed with processing these trials? (y/n): ")
        if proceed.lower() != 'y':
                print("Aborting processing.")
                exit()

        if MODE == 'sequential':
                for trial in trialList:
                        trialPath = os.path.join(utils.SIMULATIONS_DIR, subject, sesssion, trial)
                        try:

                                start_time = time.time()
                                analysis = utils.Analyse(trialPath=trialPath)


                                time_taken = time.time() - start_time
                                print(f'[{trial}] Analysis initialized in {time_taken:.2f} seconds.')

                                run_all_step(analysis)

                        except Exception as e:
                                print(f'[{trial}] Failed: {e}')


        elif MODE == 'parallel':
                with ProcessPoolExecutor() as executor:
                        futures = {executor.submit(_parallell_worker, trial, subject, sesssion): trial for trial in trialList}
                        for future in as_completed(futures):
                                trial, error = future.result()
                                if error:
                                        print(f'[{trial}] Failed: {error}')


# END
