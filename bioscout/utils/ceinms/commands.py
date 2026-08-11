"""bioscout.utils.ceinms.commands — Running the CEINMS executables: the terminal wrapper, calibration,
execution, the weight loop and CEINMSoptimise.

Split out of the former flat `utils/ceinms.py`; see the package
__init__ for why. The shared header (imports, the live `settings`
proxy) comes from `.shared`.
"""
from .shared import *          # noqa: F401,F403 — the common header
from .shared import abg_base_name, abg_from_name, check_input_times
from .configs import replace_ceinms_cfg_parameter
from .plot import plot_experimental_vs_ceinms, plot_loop_results, plot_optimisation_results


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
    exit_code = None
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

            # Capture CEINMS stdout to out.txt ONLY (do not echo to the terminal).
            # CEINMS is very chatty (ASCII banner + per-iteration dumps); it's all
            # preserved in out.txt and the last 3000 chars are printed below with a
            # pointer to the file, so echoing it live just doubles the noise.
            if process.stdout:
                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()

            process.wait()
        exit_code = process.returncode
        print(f"CEINMS process finished with exit code: {exit_code}")

        # Print the actual calibration log this run produced (out.txt). This is the
        # streamed CEINMS output we captured above; do NOT read the exe-dir
        # out.log/err.log, which are stale artifacts from unrelated past runs.
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='replace') as _lf:
                    _content = _lf.read()
                print(f"--- CEINMS log: {log_file_path} (last 3000 chars) ---")
                print(_content[-3000:])
            except Exception as _e:
                print(f"  (could not read {log_file_path}: {_e})")

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
        # Success is determined by the process exit code, not by file mtimes:
        # out.txt is written/flushed after subjectCalibrated.xml, so an mtime
        # comparison gives a spurious "predates this run" failure on good runs.
        if exit_code not in (0, None):
            print(f"CEINMS exited with code {exit_code} — calibration may have failed.")
            return False
        return True
    except Exception as e:
        print(f"Error checking calibrated model: {e}")
        return False


def calibrate(setupXML_path=None):
    
    if not setupXML_path:
        setupXML_path = input("Enter path to setup XML file: ").strip('"')
    
    os.chdir(os.path.dirname(setupXML_path)) # change wd to parent dir of setupXML (needed for CEINMS)
    
    setupXML = ET.parse(setupXML_path).getroot()
    outputDirectory = setupXML.find("outputDirectory").text
    
    # Fixed calibrationOutput name — the whole ceinms_calibration/ folder is
    # archived by the caller on re-calibration, so no per-run timestamp is needed
    # (keeps paths stable). Clear any stale contents first.
    outputDirectory = outputDirectory.split('_run_')[0]
    if os.path.isdir(outputDirectory):
        shutil.rmtree(outputDirectory, ignore_errors=True)

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
    executionOutputDir = abg_base_name(setup.find('outputDirectory').text)
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

    # leave the setup XML on the clean base name so a re-run does not nest
    setup.find("outputDirectory").text = executionOutputDir
    utils.save_pretty_xml(ET.ElementTree(setup), setupXML_path)
        
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
            abg = abg_from_name(folder_name)
            if abg is None:
                print(f"skipping {folder_name}: no _a_b_g suffix")
                continue
            alpha, beta, gamma = abg
            
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


