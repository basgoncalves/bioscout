"""bioscout.utils.ceinms.configs — Builders for every CEINMS XML: the subject model, the excitation
generator, calibration cfg/setup, input data, and the execution and
optimise configurations.

Split out of the former flat `utils/ceinms.py`; see the package
__init__ for why. The shared header (imports, the live `settings`
proxy) comes from `.shared`.
"""
from .shared import *          # noqa: F401,F403 — the common header


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


def create_excitation_generator(osim_model_path=None, emg_path=None, save_path=None,
                                mapping=None):
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
    # Canonical (sorted) channel order so the generator's inputSignals align
    # positionally with the equally-sorted excitations .mot columns (CEINMS
    # pairs them by position, not by name).
    emg_labels = sorted(emg_labels)

    # Create root element
    tree = ET.ElementTree()
    root = ET.Element('excitationGenerator')

    # Add inputSignals element
    input_signals = ET.SubElement(root, 'inputSignals', {'type': 'EMG'})
    input_signals.text = ' '.join(emg_labels)

    # Add mapping element
    mapping_el = ET.SubElement(root, 'mapping')
    mapping_dict = dict(mapping) if mapping else dict(settings.BatchSettings.emg_muscle_mapping)
    # A channel named in the map but ABSENT from the excitations file has no
    # inputSignal, and CEINMS aborts on the name/order mismatch. Drop those here
    # rather than writing an unsatisfiable generator.
    _present = set(emg_labels)
    _missing = [ch for ch in mapping_dict if ch not in _present]
    if _missing:
        print("create_excitation_generator: dropping "
              f"{len(_missing)} mapped channel(s) not present in "
              f"{os.path.basename(str(emg_path))}: {', '.join(sorted(_missing))}")
        mapping_dict = {k: v for k, v in mapping_dict.items() if k in _present}
    if not mapping_dict:
        raise ValueError(
            "no EMG channel in the muscle map matches a column in "
            f"{emg_path}. Columns are {emg_labels[:6]}... -- fix session.yaml's "
            "emg_map (or settings.BatchSettings.emg_muscle_mapping) to use the "
            "exported column names.")
    mapping = mapping_el

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


#: What each calibration parameter is called in calibrationCfg.xml, keyed by
#: every spelling seen in the wild. settings.py has always declared snake_case
#: (`optimal_fiber_length`) while this file read camelCase, so four of the six
#: ranges silently fell back to the literal below and editing settings.py did
#: nothing. Both spellings now reach the XML.
_PARAM_ALIASES = {
    "c1": ("c1",),
    "c2": ("c2",),
    "shapefactor": ("shapefactor", "shape_factor"),
    "optimalFiberLength": ("optimalFiberLength", "optimal_fiber_length",
                           "optimalFibreLength", "optimal_fibre_length"),
    "tendonSlackLength": ("tendonSlackLength", "tendon_slack_length"),
    "strengthCoefficient": ("strengthCoefficient", "strength_coefficient"),
}
_PARAM_DEFAULTS = {
    "c1": "-0.99 -0.05", "c2": "-0.95 -0.05",
    "shapefactor": "-2.999 -0.001",
    "optimalFiberLength": "0.5 3", "tendonSlackLength": "0.5 3",
    "strengthCoefficient": "0.75 3.5",
}

#: The `<optimiser>` block — how the calibration SEARCHES, as opposed to the
#: bounds it searches INSIDE. Keyed by the element name CEINMS reads, valued by
#: every spelling accepted in settings.py or in session.yaml's `calibration:`
#: block. Added 2026-08-10 for t25: the learning rate was a settings.py global,
#: so comparing 0.02 with 0.005 meant a runtime monkeypatch that left no trace
#: in the session it produced — the same defect the `calibration:` block was
#: introduced to end for the bounds.
#:
#: An optimiser key reaching `parametersToCalibrate` would be a silent
#: disaster: CEINMS would see a bound named "learningRate", the learning rate
#: itself would stay at 0.02, and bioscout would report the arm as configured.
#: :func:`calibration_param_ranges` filters these out by name, and this is the
#: only place that list is written down.
_OPTIMISER_ALIASES = {
    "hybridCalibration": ("hybridCalibration", "hybrid_calibration"),
    "learningRate": ("learningRate", "learning_rate"),
    "maxIterations": ("maxIterations", "max_iterations"),
    "minImprovement": ("minImprovement", "early_stopping_min_improvement"),
    "patience": ("patience", "early_stopping_patience"),
    "numberOfSynergies": ("numberOfSynergies", "num_synergies",
                          "number_of_synergies"),
    # <learningRateDecay> is a PARENT element holding these two. It ships
    # COMMENTED OUT in calibrationCfg_ceinms-nn_hybrid.xml, so whether this
    # CEINMS build parses it at all is unproven — emitted only when something
    # explicitly asks for it, never by default.
    "decay": ("decay", "learningRateDecay", "learning_rate_decay",
              "decayFactor", "decay_factor"),
    "minLearningRate": ("minLearningRate", "min_learning_rate"),
}
_OPTIMISER_DEFAULTS = {
    "hybridCalibration": "true",
    "learningRate": "0.02",
    "maxIterations": "1000",
    "minImprovement": "0.1",
    "patience": "20",
    "numberOfSynergies": 8,
    # "decay" and "minLearningRate" have NO default, on purpose — see above.
}
#: Which canonical keys sit inside `<earlyStopping>` / `<learningRateDecay>`.
_EARLY_STOPPING_KEYS = ("minImprovement", "patience")
_DECAY_KEYS = ("decay", "minLearningRate")


def _canonical_optimiser_key(key):
    """Canonical `<optimiser>` element name for an authored key, else None."""
    k = str(key).strip()
    low = k.lower()
    for name, aliases in _OPTIMISER_ALIASES.items():
        if k in aliases or low in {a.lower() for a in aliases}:
            return name
    return None


def is_optimiser_key(key) -> bool:
    """True when `key` configures the SEARCH rather than a parameter's bounds."""
    return _canonical_optimiser_key(key) is not None


def calibration_optimiser_settings(params=None, params_override=None):
    """-> ``{element: value}`` for calibrationCfg.xml's ``<optimiser>`` block.

    Precedence is :func:`calibration_param_ranges`'s exactly: `params_override`
    (this ITERATION's `calibration:` block in session.yaml) beats settings.py,
    which beats the built-in default. A partial override changes only what it
    names, so ``{"learningRate": 0.005}`` leaves maxIterations and the early
    stopping rule as settings.py has them.

    `decay` / `minLearningRate` are absent from the result unless something
    asked for them, so the emitted XML keeps its shipped shape by default.
    """
    params = params if params is not None else settings.CEINMSSettings
    out = {}
    for name, aliases in _OPTIMISER_ALIASES.items():
        if name in _OPTIMISER_DEFAULTS:
            out[name] = _OPTIMISER_DEFAULTS[name]
        for alias in aliases:                       # settings.py, any spelling
            if getattr(params, alias, None) is not None:
                out[name] = getattr(params, alias)
                break
    for k, v in (params_override or {}).items():    # the iteration wins
        name = _canonical_optimiser_key(k)
        if name is not None:
            out[name] = v
    return out


def calibration_param_ranges(params=None, params_override=None):
    """-> {parameter: "min max"} for calibrationCfg.xml.

    Precedence: `params_override` (this ITERATION's `calibration:` block in
    session.yaml) beats settings.py, which beats the built-in default. A
    partial override changes only the bounds it names.

    Optimiser keys (`learningRate`, `maxIterations`, the early-stopping pair)
    may share the override dict with the bounds — they are dropped here and
    picked up by :func:`calibration_optimiser_settings` instead, so they never
    turn into a `<parameter name="learningRate">` nobody reads.
    """
    params = params if params is not None else settings.CEINMSSettings
    out = {}
    for name, aliases in _PARAM_ALIASES.items():
        value = _PARAM_DEFAULTS[name]
        for alias in aliases:                       # settings.py, either spelling
            if getattr(params, alias, None) is not None:
                value = getattr(params, alias)
                break
        out[name] = value
    for k, v in (params_override or {}).items():    # the iteration wins
        if is_optimiser_key(k):                     # belongs in <optimiser>
            continue
        for name, aliases in _PARAM_ALIASES.items():
            if k in aliases:
                out[name] = v
                break
        else:
            out[str(k)] = v
    return {k: (" ".join(str(x) for x in v) if isinstance(v, (list, tuple))
                else str(v)) for k, v in out.items()}


def create_calibrationCfg(osimModelPath=None, inputPaths: list = [], outputPath: str = None,
                          params_override: dict = None):
    """
    Create a CEINMS calibration XML configuration from input parameters.

    Args:
    - osimModelPath (str): Path to the OpenSim model (.osim). Multiple trials allowed, path must be either full or relative to the calibrationCfgPath.
    - inputPaths (list): List of trial paths for "inputData.xml".
    - outputPath (str): Path to save the generated calibration configuration XML file.
    - params_override (dict): parameter ranges for THIS iteration, from
      session.yaml's `calibration:` block. Overrides settings.py per parameter.

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
    # Element ORDER matches the shipped calibrationCfg files. `opt` already
    # carries settings.py and this iteration's overrides, resolved.
    opt = calibration_optimiser_settings(params, params_override)
    optimiser = ET.SubElement(root, "optimiser")
    ET.SubElement(optimiser, "debug").text = "true"
    ET.SubElement(optimiser, "hybridCalibration").text = str(opt["hybridCalibration"])
    ET.SubElement(optimiser, "learningRate").text = str(opt["learningRate"])
    ET.SubElement(optimiser, "maxIterations").text = str(opt["maxIterations"])

    earlyStopping = ET.SubElement(optimiser, "earlyStopping")
    ET.SubElement(earlyStopping, "minImprovement").text = str(opt["minImprovement"])
    ET.SubElement(earlyStopping, "patience").text = str(opt["patience"])

    # Only when asked for -- the shipped reference has this block commented out.
    if any(k in opt for k in _DECAY_KEYS):
        decay = ET.SubElement(optimiser, "learningRateDecay")
        for _k, _tag in (("decay", "decay"), ("minLearningRate", "minLearningRate")):
            if _k in opt:
                ET.SubElement(decay, _tag).text = str(opt[_k])

    ET.SubElement(optimiser, "numberOfSynergies").text = str(opt["numberOfSynergies"])

    if params_override:
        _o = {k: v for k, v in params_override.items() if is_optimiser_key(k)}
        if _o:
            print("[ceinms] calibration optimiser from session.yaml: "
                  + ", ".join(f"{_canonical_optimiser_key(k)}={v}"
                              for k, v in _o.items()))

    # --- Tendon ---
    tendon = ET.SubElement(root, "tendon")
    tendon.text = getattr(params, "tendonType", "elastic")

    # --- calibrationTargets ---
    calibrationTargets = ET.SubElement(root, "calibrationTargets")

    # parametersToCalibrate - only range parameters
    parametersToCalibrate = ET.SubElement(calibrationTargets, "parametersToCalibrate")
    
    # Calibration parameter ranges (name -> "min max" string)
    param_ranges = calibration_param_ranges(params, params_override)
    _bounds_said = [k for k in (params_override or {}) if k in param_ranges]
    if _bounds_said:
        print(f"[ceinms] calibration bounds from session.yaml: "
              + ", ".join(f"{k}={param_ranges[k]}" for k in _bounds_said))
    for name, value in param_ranges.items():
        param_elem = ET.SubElement(parametersToCalibrate, "parameter", name=name)
        param_elem.text = str(value)

    # ------- muscleGroups (BASED ON SETTINGS PLEASE EDIT THIS FOR DIFFERENT MUSCLE GROUPS) ------
    muscleGroups = ET.SubElement(parametersToCalibrate, "muscleGroups")

    # BatchSettings.MUSCLE_GROUPS is right-side only (used for the right-focused
    # analysis figures). For CALIBRATION we mirror each group to the LEFT leg too,
    # otherwise only right-side muscles ever get their strength coefficient (and
    # other params) calibrated. Emit the right group + its _l counterpart.
    # DEDUPLICATED 2026-08-04. MUSCLE_GROUPS contains both "R Quadriceps" and
    # "L Quadriceps". The R group emitted its right muscles and then MIRRORED
    # them to the left; the L group then emitted that same left set again. So
    # every left-side group appeared TWICE and every right-side group once, and
    # the two sides were not constrained alike — while every muscle that
    # diverged in calibration was a left one. Emit each distinct set exactly
    # once, in first-seen order.
    _seen = set()
    for group, muscles in settings.BatchSettings.MUSCLE_GROUPS.items():
        left = [m[:-2] + "_l" if m.endswith("_r") else m for m in muscles]
        for variant in (list(muscles), left):
            key = tuple(sorted(variant))
            if not variant or key in _seen:
                continue
            _seen.add(key)
            ET.SubElement(muscleGroups, "muscles").text = " ".join(variant)

    # objectiveFunctions
    objectiveFunctions = ET.SubElement(calibrationTargets, "objectiveFunctions")
    for func in params.objective_functions:
        objFunc = ET.SubElement(objectiveFunctions, "objectiveFunction")
        for key, value in func.items():
            ET.SubElement(objFunc, key).text = str(value)

    # target muscles
    targetMuscles = ET.SubElement(calibrationTargets, "muscles")
    # FIXED 2026-08-04. target_muscles is "all" — a STRING — and iterating a
    # string yields characters, so this wrote
    # <muscles><muscle>a</muscle><muscle>l</muscle><muscle>l</muscle></muscles>.
    # Three muscle names that match nothing in any model.
    _targets = params.target_muscles
    if isinstance(_targets, str):
        _targets = [t for t in _targets.replace(",", " ").split() if t]
    _targets = list(_targets or [])
    if len(_targets) == 1 and _targets[0].lower() == "all":
        # "all" is a settings sentinel, not a CEINMS token. Expand it to every
        # muscle the calibration groups cover, both sides, first-seen order.
        _targets, _seen_t = [], set()
        for _g, _ms in settings.BatchSettings.MUSCLE_GROUPS.items():
            for _m in list(_ms) + [x[:-2] + "_l" if x.endswith("_r") else x
                                   for x in _ms]:
                if _m not in _seen_t:
                    _seen_t.add(_m)
                    _targets.append(_m)
        print(f"[ceinms] target_muscles='all' expanded to {len(_targets)} "
              f"muscles from MUSCLE_GROUPS")
    for muscle in _targets:
        ET.SubElement(targetMuscles, "muscle").text = str(muscle)

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
        outputDirectory = os.path.join(os.path.dirname(calibrationCfgPath), 'output')
    
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
                      startStopTime=None, output_path=None):

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
    
    # CEINMS resolves every path in inputData.xml relative to the LOCATION of
    # inputData.xml itself. So base all relative paths on the output file's
    # directory (which may be a ceinms/ subfolder while the muscle analysis /
    # kinematics live in sibling subfolders — e.g. "../muscle_analysis/...").
    savePath = (os.path.abspath(output_path) if output_path
                else os.path.join(os.path.dirname(os.path.abspath(MAFolder)), 'inputData.xml'))
    base = os.path.dirname(savePath)

    def _rel(p):
        return os.path.relpath(os.path.abspath(p), start=base)

    root = ET.Element("inputData")
    length_path = os.path.join(MAFolder, '_MuscleAnalysis_Length.sto')
    muscle_length_elem = ET.SubElement(root, "muscleTendonLengthFile")
    muscle_length_elem.text = _rel(length_path)

    excitations_elem = ET.SubElement(root, "excitationsFile")
    excitations_elem.text = _rel(excitationsFile)

    # Add moment arms files. A DOF the model doesn't have (e.g. knee_adduction on
    # a 1-DOF-knee model) produces no moment-arm file — skip it so inputData only
    # references files CEINMS can actually read.
    moment_arms = ET.SubElement(root, "momentArmsFiles")
    for dof in settings.BatchSettings.dof_list:
        dof_path = os.path.join(MAFolder, f'_MuscleAnalysis_MomentArm_{dof}.sto')
        if not os.path.exists(dof_path):
            continue
        dof_elem = ET.SubElement(moment_arms, "momentArmsFile")
        dof_elem.set("dofName", dof)
        dof_elem.text = _rel(dof_path)

    external_torques_elem = ET.SubElement(root, "externalTorquesFile")
    external_torques_elem.text = _rel(externalTorquesFile)

    motion_elem = ET.SubElement(root, "motionFile")
    motion_elem.text = _rel(motionFile)

    external_loads_elem = ET.SubElement(root, "externalLoadsFile")
    external_loads_elem.text = _rel(externalLoadsFile)

    startStop_elem = ET.SubElement(root, "startStopTime")
    startStop_elem.text = f"{startStopTime[0]} {startStopTime[1]}"

    os.makedirs(base, exist_ok=True)
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, savePath)


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


