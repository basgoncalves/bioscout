import logging
import sys
import os
import datetime
from time import time
import warnings
import numpy as np
from scipy import linalg, optimize
import opensim as osim
import pandas as pd


def mean_squared_error(y_true, y_pred, squared=True):
    """Local RMSE/MSE helper (avoids sklearn version differences over the
    removed `squared=` kwarg). Returns RMSE when squared=False."""
    err = float(np.mean((np.asarray(y_true, float) - np.asarray(y_pred, float)) ** 2))
    return err if squared else np.sqrt(err)


def _assembly_accuracy(default=1e-8):
    """Model assembly/constraint tolerance to use when loading models.

    Constraint-coupled knees (Lerner/JAM, GPK, patella couplers) frequently miss
    OpenSim's ultra-tight default constraint tolerance during assemble(), spamming
    'Unable to achieve required assembly error tolerance' before it relaxes and
    recovers. Loosening to ~1e-8 (physically negligible for joint moments / JCF)
    silences it. Override via BatchSettings.assembly_accuracy in a project."""
    try:
        from bioscout import utils as _u
        v = getattr(getattr(_u, "settings", None), "BatchSettings", None)
        v = getattr(v, "assembly_accuracy", None)
        return float(v) if v else default
    except Exception:
        return default


def _quiet_model(arg):
    """``osim.Model(arg)`` with its printBasicInfo() dump suppressed.

    Constructing a Model writes a fixed block to std::cout from C++::

                   MODEL: 021
             coordinates: 39
                  forces: 97
             ...
        misc modelcomponents: 0

    It bypasses OpenSim's logger, so BatchSettings.opensim_log_level cannot
    touch it, and it bypasses sys.stdout, so the _Tee log filter never sees it
    either. Only a file-descriptor level redirect stops it.

    The redirect here is UNCONDITIONAL — deliberately not gated on
    opensim_log_level like _osim_quiet_ctx(). That gate reads `settings`, which
    openSim.py resolves via a sys.path insert of its own directory, so which
    module it lands on depends on how the process was started; the block kept
    leaking through as a result. printBasicInfo carries no diagnostic value, and
    fd 2 (stderr) stays open throughout, so genuine OpenSim errors still surface.
    """
    import sys as _sys
    try:
        _sys.stdout.flush()
    except Exception:
        pass
    try:
        _saved = os.dup(1)
    except Exception:                     # no real fd 1 (embedded/captured stdout)
        return osim.Model(arg)
    _devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(_devnull, 1)
        return osim.Model(arg)
    finally:
        try:
            os.dup2(_saved, 1)
        finally:
            os.close(_devnull)
            os.close(_saved)


def load_model(path, accuracy=None):
    """opensim.Model(path) with a relaxed assembly accuracy applied (see
    _assembly_accuracy). Use everywhere a model is loaded for a tool run."""
    model = _quiet_model(path)
    acc = accuracy if accuracy is not None else _assembly_accuracy()
    try:
        model.set_assembly_accuracy(acc)
    except Exception:
        pass
    return model
import matplotlib.pyplot as plt
from xml.etree import ElementTree as ET
from pathlib import Path
# Ensure utils dir and app dir are on sys.path for standalone execution.

_utils_dir = str(Path(__file__).parent)
_app_dir = str(Path(__file__).parent.parent)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
if _utils_dir in sys.path:
    sys.path.remove(_utils_dir)
sys.path.insert(0, _utils_dir)

try:
    import settings
except ImportError as e:
    print(f"Warning: Could not import settings in openSim.py: {e}")
    settings = None

import utils
import exportC3D  # Lazy import below to avoid circular dependency

def _quiet_osim():
    """Apply the configured OpenSim log level (settings.BatchSettings.
    opensim_log_level, e.g. "off"/"error"). Uses the Level_* ENUM — proven to work
    on the installed build — and reads the flag from the LOADED project settings
    (bioscout.utils.settings) first, falling back to this module's ``settings``.
    OpenSim's tools reset the logger to 'info' when they run, so this is re-applied
    before each tool via the ``_quiet_console`` decorator."""
    try:
        _lvl = None
        try:
            from bioscout import utils as _u
            _bs = getattr(getattr(_u, "settings", None), "BatchSettings", None)
            _lvl = getattr(_bs, "opensim_log_level", None)
        except Exception:
            _lvl = None
        if not _lvl:
            _lvl = getattr(getattr(settings, "BatchSettings", None), "opensim_log_level", None)
        if not _lvl:
            return
        _enum = {"off": osim.Logger.Level_Off, "critical": osim.Logger.Level_Critical,
                 "error": osim.Logger.Level_Error, "warn": osim.Logger.Level_Warn,
                 "warning": osim.Logger.Level_Warn, "info": osim.Logger.Level_Info,
                 "debug": osim.Logger.Level_Debug, "trace": osim.Logger.Level_Trace
                 }.get(str(_lvl).strip().lower())
        if _enum is not None:
            osim.Logger.setLevel(_enum)
        else:
            osim.Logger.setLevelString(str(_lvl).strip().lower())
    except Exception:
        pass


import contextlib as _contextlib
import functools as _functools


@_contextlib.contextmanager
def _osim_quiet_ctx():
    """Apply the configured OpenSim log level around an OpenSim tool. Tools RESET
    the logger to 'info' as they run, so we re-apply it BEFORE and AFTER. When the
    level is 'off', ALSO redirect C-level stdout (fd 1) to devnull for the duration
    — that swallows OpenSim's Model::printBasicInfo() block ("MODEL: ... coordinates
    ...") which is written to std::cout and bypasses the logger. stderr stays open
    (errors still surface); the Python log-file tee is unaffected."""
    _quiet_osim()
    # Quiet unless the project explicitly asks for OpenSim's chatter.
    #
    # This used to be opt-IN: redirect fd 1 only when
    # BatchSettings.opensim_log_level == "off". The gate resolves `settings`
    # through a sys.path insert that finds the project's settings.py only when
    # the process was started a particular way — so `python -c "from bioscout
    # import Session; ..."` from the project folder read no setting at all,
    # fell back to False, and OpenSim's printBasicInfo block came back four
    # times per trial. The same fragility already forced _quiet_model() to be
    # made unconditional; this is the other half of it.
    #
    # Now: quiet unless a level was explicitly set to something verbose. The
    # redirect covers fd 1 only, so errors on stderr still surface.
    _off = True
    try:
        _bs = getattr(getattr(settings, "BatchSettings", None), "opensim_log_level", None)
        if _bs is not None:
            _off = str(_bs).strip().lower() in ("off", "", "none")
    except Exception:
        _off = True
    if not _off:
        try:
            yield
        finally:
            _quiet_osim()
        return
    import sys as _sys
    try:
        _sys.stdout.flush()
    except Exception:
        pass
    # Swapping fd 1 for devnull silences OpenSim's C++ chatter, but it is only
    # safe when fd 1 is a real file or console. Under MINGW / Git Bash it is a
    # pty, and after the dup2 the NEXT ordinary print() raises
    # "OSError: [WinError 1] Incorrect function" -- from inside the wrapped
    # function, which makes it look like the OpenSim call failed when nothing
    # of the sort happened. If the swap cannot be done safely, skip it: noisy
    # output is a far smaller problem than a tool that appears to crash.
    # On Windows `sys.stdout` wraps a _WindowsConsoleIO bound to the CONSOLE
    # HANDLE, not to fd 1. Swapping fd 1 therefore leaves it writing to a
    # handle that is no longer a console, and the next ordinary print() dies
    # with "OSError: [WinError 1] Incorrect function" -- raised from inside the
    # wrapped function, so it reads as an OpenSim failure when nothing of the
    # sort happened. Only swap when stdout is NOT a console: a redirected file
    # or pipe survives it, and that is the case where the C++ chatter is worth
    # suppressing anyway.
    _console = False
    try:
        _raw = getattr(getattr(_sys.stdout, "buffer", None), "raw", None)
        _console = (os.name == "nt"
                    and (type(_raw).__name__ == "_WindowsConsoleIO"
                         or _sys.stdout.isatty()))
    except Exception:                                        # noqa: BLE001
        _console = os.name == "nt"
    if _console:
        try:
            yield
        finally:
            _quiet_osim()
        return
    try:
        _saved = os.dup(1)
        _devnull = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        try:
            yield
        finally:
            _quiet_osim()
        return
    _swapped = False
    try:
        try:
            os.dup2(_devnull, 1)
            _swapped = True
        except OSError:
            pass                      # keep the real stdout; just do not silence
        yield
    finally:
        try:
            _sys.stdout.flush()
        except Exception:
            pass
        if _swapped:
            try:
                os.dup2(_saved, 1)
            except OSError:
                pass
        for _fd in (_devnull, _saved):
            try:
                os.close(_fd)
            except OSError:
                pass
        _quiet_osim()


def _quiet_console(fn):
    """Decorator: run an OpenSim tool wrapper inside :func:`_osim_quiet_ctx`."""
    @_functools.wraps(fn)
    def _w(*a, **k):
        with _osim_quiet_ctx():
            return fn(*a, **k)
    return _w


def terminal_warnings(mode='off'):
    """Set OpenSim terminal warnings on or off."""
    if mode == 'off':
        osim.Logger.setLevelString('warning')
        print("OpenSim terminal warnings turned OFF.")
    elif mode == 'on':
        osim.Logger.setLevelString('info')
        print("OpenSim terminal warnings turned ON.")
    else:
        print("Invalid mode. Use 'on' or 'off'.")

# Model editing functions
def scale_body_masses(osim_modelPath):
    """ 
    Scale the body masses of model_target to match the percentages of model_reference.
    """

    model_ref = _quiet_model(osim_modelPath)

    model_targ_path = osim_modelPath.replace('.osim', '_scaledMasses.osim')
    model_targ = _quiet_model(model_targ_path)

    state1 = model_ref.initSystem()
    state2 = model_targ.initSystem()

    # prnt model weight
    print(f"Model: {model_ref.getName()}, Weight: {model_ref.getTotalMass(state1)} kg")
    print(f"Model: {model_targ.getName()}, Weight: {model_targ.getTotalMass(state2)} kg")

    # Compare each body's mass between model1 and model2
    bodyset_ref = {body.getName(): body for body in model_ref.getBodySet()}
    bodyset_targ = {body.getName(): body for body in model_targ.getBodySet()}

    print("\nComparison of body masses between model1 and model2:")

    for body_name in bodyset_ref:
        if body_name in bodyset_targ:
            mass_ref = bodyset_ref[body_name].getMass()
            mass_targ = bodyset_targ[body_name].getMass()
            percent_mass_ref = (mass_ref / model_ref.getTotalMass(state1)) * 100
            percent_mass_targ = (mass_targ / model_targ.getTotalMass(state2)) * 100
            print(f"Body: {body_name}, Model1 Mass: {mass_ref} kg ({percent_mass_ref:.2f}%), Model2 Mass: {mass_targ} kg ({percent_mass_targ:.2f}%)")
            
            # change mass of body in model2 to match model1 percentage
            if percent_mass_ref != percent_mass_targ:
                new_body_mass_targ = (percent_mass_ref / 100) * model_targ.getTotalMass(state2)
                bodyset_targ[body_name].setMass(new_body_mass_targ)
                print(f"Updated Model2 {body_name} mass to: {new_body_mass_targ} kg, {percent_mass_ref:.2f}%")
            
        else:
            mass_ref = bodyset_ref[body_name].getMass()
            print(f"Body: {body_name}, Model1 Mass: {mass_ref} kg, Model2 Mass: Not Found")
            
    # save model2 with updated masses
    model_targ.setName(model_targ.getName() + "_updated_masses")
    model_targ.printToXML(model_targ_path)
    print(f"\nUpdated model saved to: {model_targ_path}")

        
    return model_targ

def add_mass_to_body(osim_modelPath, body_name, mass_to_add):
    """
    Add a specific mass to a body in the OpenSim model.
    """
    model = _quiet_model(osim_modelPath)
    state = model.initSystem()

    save_path = osim_modelPath.replace('.osim', '_updatedMasses.osim')

    body = model.getBodySet().get(body_name)
    
    if body:
        current_mass = body.getMass()
        new_mass = current_mass + mass_to_add
        body.setMass(new_mass)
        model.printToXML(save_path)
        print(f"Updated {body_name} mass from {current_mass} kg to {new_mass} kg.")
    else:
        print(f"Body '{body_name}' not found in the model.")

def print_body_mass_per_segment(osim_modelPath=None):
    """ 
    Print the mass of each body segment in the OpenSim model.
    """
    if not osim_modelPath:
        osim_modelPath = input("Enter path to OpenSim model (.osim): ").strip('"')
    
    model = _quiet_model(osim_modelPath)
    state = model.initSystem()

    print("Body Segment Masses:")
    for body in model.getBodySet():
        print(f"{body.getName()}: {body.getMass()} kg ({body.getMass() / model.getTotalMass(state) * 100:.2f}%)")

def increase_isometric_force(osim_modelPath=None, muscleList='all', factor: float = None):
    """
    Increase the isometric force of a specified muscle by a given factor.
    """
    if not osim_modelPath:
        osim_modelPath = input("Enter path to OpenSim model (.osim): ").strip('"')
    
    if not factor:
        factor = float(input("Enter factor to increase max isometric force (e.g., 1.2 for 20% increase): "))

    model = _quiet_model(osim_modelPath)
    
    if muscleList == 'all':
        muscleList = []
        for muscle in model.getMuscles():
            muscleList.append(muscle.getName())
    
    _n = 0
    for muscle_name in muscleList:
        muscle = model.getMuscles().get(muscle_name)
        if muscle:
            muscle.setMaxIsometricForce(muscle.getMaxIsometricForce() * factor)
            _n += 1
        else:
            print(f"Muscle '{muscle_name}' not found in the model.")

    _out = osim_modelPath.replace('.osim', f'_increased_{factor:.2f}.osim')
    model.printToXML(_out)
    print(f"[scale] increased isometric force x{factor:.2f} on {_n} muscles -> {os.path.basename(_out)}")

def lock_model_coordinates(osim_modelPath=None, coordinates_to_lock: list = None, save_path=None, unlock=False):
    """
    Lock specified coordinates in the OpenSim model.
    """
    if not osim_modelPath:
        osim_modelPath = input("Enter path to OpenSim model (.osim): ").strip('"')
    
    if not coordinates_to_lock:
        coordinates_to_lock = input("Enter coordinates to lock (comma-separated): ").split(',')

    model = _quiet_model(osim_modelPath)
    state = model.initSystem()
    
    for coord_name in coordinates_to_lock:
        coord = model.getCoordinateSet().get(coord_name)
        if coord:
            if unlock:
                coord.setDefaultLocked(False)
                print(f"Unlocked coordinate: {coord_name}")
            else:
                coord.setDefaultLocked(True)
                print(f"Locked coordinate: {coord_name}")
        else:
            print(f"Coordinate '{coord_name}' not found in the model.")

    if not save_path:
        save_path = osim_modelPath.replace('.osim', '_lockedCoords.osim')
    model.printToXML(save_path)
    print(f"Updated model with locked coordinates saved to: {save_path}")

def coord_moment_arms(osim_model, muscle_list):
    '''Check which coordinates the muscles in the list have moment arms about (non-zero across the range of the model)'''

    model = _quiet_model(osim_model)
    state = model.initSystem()
    coord_moment_arms = {}

    for muscle_name in muscle_list:
        try:
            muscle = model.getMuscles().get(muscle_name)
            moment_arms = {}
            for i in range(model.getNumCoordinates()):
                coord = model.getCoordinateSet().get(i)
                model.realizePosition(state)
                moment_arm_value = muscle.computeMomentArm(state, coord)
                if not np.isclose(moment_arm_value, 0):
                    moment_arms[coord.getName()] = moment_arm_value
            coord_moment_arms[muscle_name] = moment_arms
        except Exception as e:
            print(f"Error processing muscle {muscle_name}: {e}")
    
    coord_names = set()
    for muscle, mom_arms in coord_moment_arms.items():
        for coord in mom_arms.keys():
            if not np.isnan(mom_arms[coord]):
                coord_names.add(coord)

    return coord_names

def add_wrapping_surfaces(reference_model_path=None, target_model_path=None, output_model_path=None):
    """
    Add wrapping surfaces from reference OpenSim model to target model.
    
    Args:
        reference_model_path (str): Path to reference .osim file
        target_model_path (str): Path to target .osim file
        output_model_path (str): Path for output .osim file with wrapping surfaces
    """

    # prompt user for paths if not provided
    if not reference_model_path:
        reference_model_path = input("Enter path to reference OpenSim model (.osim): ").strip('"')
    if not target_model_path:
        target_model_path = input("Enter path to target OpenSim model (.osim): ").strip('"')
    if not output_model_path:
        output_model_path = input("Enter path to save output OpenSim model with wrapping surfaces (.osim): ").strip('"')

    # turn off OpenSim terminal warnings for cleaner output
    terminal_warnings('off')
    try:
        # Load both models
        reference_model = _quiet_model(reference_model_path)
        target_model = _quiet_model(target_model_path)
        
        # Get wrapping surfaces from reference model
        reference_bodies = reference_model.getBodySet()
        target_bodies = target_model.getBodySet()
        
        # Add wrapping surfaces to target model
        for i in range(reference_bodies.getSize()):
            ref_body = reference_bodies.get(i)
            wrapping_surfaces = ref_body.getWrapObjectSet()
            
            if wrapping_surfaces.getSize() > 0:
                try:
                    # find matching body in target model
                    target_body = target_bodies.get(ref_body.getName())
                    target_wrap_set = target_body.getWrapObjectSet()
                    
                    for j in range(wrapping_surfaces.getSize()):
                        wrap_obj = wrapping_surfaces.get(j)
                        wrap_name = wrap_obj.getName()
                        
                        # Check if surface already exists
                        if target_wrap_set.getIndex(wrap_name) >= 0:
                            print(f"Skipped wrapping surface '{wrap_name}' on body '{target_body.getName()}' (already exists)")
                        else:
                            target_body.addWrapObject(wrap_obj)
                            print(f"Added wrapping surface '{wrap_name}' to body '{target_body.getName()}'")
                except RuntimeError:
                    print(f"Body '{ref_body.getName()}' not found in target model")
        
        # change model name to avoid confusion
        target_model.setName(target_model.getName() + "_with_wrapping")

        # Save output model
        target_model.printToXML(output_model_path)
        print(f"\nModel saved to: {output_model_path}")
        
    except ImportError:
        print("Error: OpenSim Python API not installed. Please install opensim package.")
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
    except Exception as e:
        print(f"Error: {e}")

def edit_model_range_coordinates(osim_modelPath, coordinate_name, new_range: list, save_path):
    """
    Edit the range of motion for a specific coordinate in the OpenSim model.

    Args:
        osim_modelPath (str): Path to the .osim model file
        coordinate_name (str): Name of the coordinate to edit
        new_range (list): New range of motion as [min, max] in radians
        save_path (str): Path to save the modified model

    """
    model = _quiet_model(osim_modelPath)
    state = model.initSystem()

    coordinate = model.getCoordinateSet().get(coordinate_name)

    if coordinate:
        current_range = (coordinate.getRangeMin(), coordinate.getRangeMax())
        coordinate.setRangeMin(new_range[0])
        coordinate.setRangeMax(new_range[1])
        model.printToXML(save_path)
        print(f"Updated {coordinate_name} range from {current_range} to {new_range}.")
    else:
        print(f"Coordinate '{coordinate_name}' not found in the model.")

def add_wrapping_surface_to_model(model_path, surface_name, wrap_name, save_path=None):
    """
    Add a wrapping surface to an OpenSim model.
    
    Args:
        model_path (str): Path to the .osim model file
        surface_name (str): Name of the wrapping surface to add
        wrap_name (str): Name of the wrap object to create
        save_path (str, optional): Path to save the modified model. If None, saves to model_path with '_wrap_added' suffix
    
    Returns:
        str: Path to the saved model file
    """
    
    # Load model
    model = _quiet_model(model_path)
    
    # Initialize system
    state = model.initSystem()
    
    try:
        # Create wrapping surface (example: a cylinder)
        wrap_surface = osim.WrapCylinder(surface_name, 0.05, 0.1)  # name, radius, length
        
        # Add wrapping surface to model
        model.addWrapObject(wrap_surface)
        
        print(f"Added wrapping surface: {surface_name}")
        
    except Exception as e:
        print(f"Error adding wrapping surface '{surface_name}': {e}")
    
    # Finalize connections and initialize system
    model.finalizeConnections()
    
    # Determine save path
    if save_path is None:
        base_name = os.path.splitext(model_path)[0]
        save_path = f"{base_name}_wrap_added.osim"
    
    # change model name to indicate wrap added
    model.setName(model.getName() + "_wrap_added")

    # Save the modified model
    model.printToXML(save_path)
    
    print(f"Modified model saved to: {save_path}")
    
    return save_path

def add_muscles_to_model(source_model_path, target_model_path, muscle_names, save_path=None):
    """
    Add muscles from a source OpenSim model to a target OpenSim model.
    
    Args:
        source_model_path (str): Path to the source .osim model file
        target_model_path (str): Path to the target .osim model file
        muscle_names (list): List of muscle names to copy from source to target
        save_path (str, optional): Path to save the modified model. If None, saves to target_model_path with '_muscles_added' suffix
    
    Returns:
        str: Path to the saved model file
    """
    
    # Load models
    source_model = _quiet_model(source_model_path)
    target_model = _quiet_model(target_model_path)
    
    # Initialize systems
    source_state = source_model.initSystem()
    target_state = target_model.initSystem()
    
    muscles_added = []
    muscles_skipped = []
    
    for muscle_name in muscle_names:
        try:
            # Check if muscle already exists in target
            if target_model.getMuscles().contains(muscle_name):
                print(f"Muscle '{muscle_name}' already exists in target model. Skipping.")
                muscles_skipped.append(muscle_name)
                continue
            
            # Get muscle from source model
            source_muscle = source_model.getMuscles().get(muscle_name)
            
            # Clone the muscle
            cloned_muscle = source_muscle.clone()
            
            # Add to target model
            target_model.addForce(cloned_muscle)
            
            # Find wrap objects referenced by this muscle's geometry path
            source_path_wraps = source_muscle.getGeometryPath().getWrapSet()

            for i in range(source_path_wraps.getSize()):
                path_wrap = source_path_wraps.get(i)
                wrap_object_name = path_wrap.getWrapObjectName()

                # Search all bodies in source model for the wrap object
                source_wrap_obj = None
                source_body = None
                body_set = source_model.getBodySet()
                for b in range(body_set.getSize()):
                    body = body_set.get(b)
                    wrap_set = body.getWrapObjectSet()
                    for w in range(wrap_set.getSize()):
                        if wrap_set.get(w).getName() == wrap_object_name:
                            source_wrap_obj = wrap_set.get(w)
                            source_body = body
                            break
                    if source_wrap_obj is not None:
                        break

                if source_wrap_obj is None:
                    print(f"Wrap object '{wrap_object_name}' not found in source model. Skipping.")
                    continue

                target_body_name = source_body.getName()
                if not target_model.getBodySet().contains(target_body_name):
                    print(f"Body '{target_body_name}' not found in target model. Cannot add wrap object '{wrap_object_name}'.")
                    continue

                target_body = target_model.getBodySet().get(target_body_name)
                target_wrap_set = target_body.getWrapObjectSet()

                # Check if wrap object already exists on that body
                wrap_exists = any(target_wrap_set.get(w).getName() == wrap_object_name
                                  for w in range(target_wrap_set.getSize()))
                if not wrap_exists:
                    cloned_wrap = source_wrap_obj.clone()
                    target_body.addWrapObject(cloned_wrap)
                    print(f"Added wrap object: {wrap_object_name} to body: {target_body_name} for muscle: {muscle_name}")
                else:
                    print(f"Wrap object '{wrap_object_name}' already exists on body '{target_body_name}'. Skipping.")
            muscles_added.append(muscle_name)
            print(f"Added muscle: {muscle_name}")
     
        except Exception as e:
            print(f"Error adding muscle '{muscle_name}': {e}")
            muscles_skipped.append(muscle_name)
    
    # Finalize connections and initialize system
    target_model.finalizeConnections()
    
    # Determine save path
    if save_path is None:
        base_name = os.path.splitext(target_model_path)[0]
        save_path = f"{base_name}_muscles_added.osim"
    
    # change model name to indicate muscles added
    target_model.setName(target_model.getName() + "_muscles_added")

    # Save the modified model
    target_model.printToXML(save_path)
    
    print(f"\n=== Summary ===")
    print(f"Muscles added: {len(muscles_added)}")
    print(f"Muscles skipped: {len(muscles_skipped)}")
    print(f"Modified model saved to: {save_path}")
    
    return save_path

def copy_model_coordinate(src_model=None, target_model=None, coordinate_name=None, target_joint_name=None):
    """Copy one or more coordinates from a source model to a target model via XML manipulation.

    coordinate_name: str or list of str
    target_joint_name: str, list of str (matched by index to coordinate_name), or None
        If None, the source joint name is used for each coordinate.

    Adds each coordinate to the target joint's <coordinates> list and mirrors
    any SpatialTransform/TransformAxis references from the source joint.
    """
    import copy

    if not src_model:
        src_model = input("Enter the path to the source model (.osim): ")
    if not target_model:
        target_model = input("Enter the path to the target model (.osim): ")
    if not coordinate_name:
        coordinate_name = input("Enter coordinate name(s) (comma-separated): ").split(',')

    # Normalise to lists
    if isinstance(coordinate_name, str):
        coordinate_name = [coordinate_name]
    if target_joint_name is None:
        target_joint_name = [None] * len(coordinate_name)
    elif isinstance(target_joint_name, str):
        target_joint_name = [target_joint_name] * len(coordinate_name)

    src_tree = ET.parse(src_model)
    tar_tree = ET.parse(target_model)
    src_root = src_tree.getroot()
    tar_root = tar_tree.getroot()

    src_parent_map = {c: p for p in src_root.iter() for c in p}
    _skip_tags = {'CoordinateSet', 'coordinates', 'objects', 'groups', 'components'}

    for coord_name, joint_override in zip(coordinate_name, target_joint_name):

        # --- Find coordinate element and parent joint in source ---
        src_coord_elem = None
        for coord in src_root.iter('Coordinate'):
            if coord.get('name') == coord_name:
                src_coord_elem = coord
                break
        if src_coord_elem is None:
            print(f"Warning: Coordinate '{coord_name}' not found in source model. Skipping.")
            continue

        src_joint_name = None
        src_joint_elem = None
        elem = src_coord_elem
        while elem in src_parent_map:
            parent = src_parent_map[elem]
            if parent.get('name') and parent.tag not in _skip_tags:
                src_joint_name = parent.get('name')
                src_joint_elem = parent
                break
            elem = parent
        print(f"Found coordinate '{coord_name}' in joint '{src_joint_name}'.")

        # Find which TransformAxis names in source reference this coordinate
        src_axes_referencing = []
        if src_joint_elem is not None:
            for axis in src_joint_elem.iter('TransformAxis'):
                coords_elem = axis.find('coordinates')
                if coords_elem is not None and coords_elem.text and coord_name in coords_elem.text.split():
                    src_axes_referencing.append(axis.get('name'))
        print(f"Source TransformAxes referencing '{coord_name}': {src_axes_referencing}")

        # --- Locate target joint ---
        joint_to_find = joint_override if joint_override else src_joint_name
        tar_joint_elem = None
        for jelem in tar_root.iter():
            if jelem.get('name') == joint_to_find:
                tar_joint_elem = jelem
                break
        if tar_joint_elem is None:
            print(f"Warning: Joint '{joint_to_find}' not found in target model. Skipping '{coord_name}'.")
            continue

        # --- Add coordinate to target joint's <coordinates> list ---
        coords_container = tar_joint_elem.find('coordinates')
        if coords_container is None:
            coords_container = ET.SubElement(tar_joint_elem, 'coordinates')

        existing = None
        for coord in coords_container.findall('Coordinate'):
            if coord.get('name') == coord_name:
                existing = coord
                break

        if existing is not None:
            for child in list(existing):
                existing.remove(child)
            for child in src_coord_elem:
                existing.append(copy.deepcopy(child))
            print(f"Updated existing coordinate '{coord_name}'.")
        else:
            coords_container.append(copy.deepcopy(src_coord_elem))
            print(f"Appended coordinate '{coord_name}' to joint '{joint_to_find}'.")

        # --- Update SpatialTransform in target to reference coordinate ---
        for axis in tar_joint_elem.iter('TransformAxis'):
            if axis.get('name') in src_axes_referencing:
                coords_elem = axis.find('coordinates')
                if coords_elem is None:
                    coords_elem = ET.SubElement(axis, 'coordinates')
                coords_elem.text = coord_name
                print(f"Updated TransformAxis '{axis.get('name')}' to reference '{coord_name}'.")

    # --- Fix empty <translation> tags ---
    for elem in tar_root.iter('translation'):
        if not elem.text or not elem.text.strip():
            elem.text = '0 0 0'

    save_path = target_model.replace('.osim', '_modified.osim')
    tar_tree.write(save_path, encoding='unicode', xml_declaration=True)
    print(f"Saved modified model to: {save_path}")

    # Verify all coordinates exist in saved XML
    verify_root = ET.parse(save_path).getroot()
    saved_coords = {c.get('name') for c in verify_root.iter('Coordinate')}
    for coord_name in coordinate_name:
        if coord_name in saved_coords:
            print(f"Verified: '{coord_name}' exists in the modified model.")
        else:
            print(f"Error: '{coord_name}' not found in the modified model.")

    # Validate by loading with OpenSim API; save to separate file
    validated_path = save_path.replace('.osim', '_validated.osim')
    model = _quiet_model(save_path)
    model.initSystem()
    model.setName('tps_transformed_with_added_coordinates')
    model.printToXML(validated_path)
    print(f"OpenSim-validated model saved to: {validated_path}")

def checkMuscleMomentArms(model_file_path=None, ik_file_path=None, leg = 'l', threshold = 0.005):
    '''
    Adapted from Willi Koller: https://github.com/WilliKoller/OpenSimMatlabBasic/blob/main/checkMuscleMomentArms.m
    Models Verified for:
        - Rajagopal 2015
        - Cateli 
    '''
    def get_model_coord(model, coord_name):
        try:
            index = model.getCoordinateSet().getIndex(coord_name)
            coord = model.updCoordinateSet().get(index)
        except:
            index = None
            coord = None
            print(f'Coordinate {coord_name} not found in model')
        
        return index, coord

    if not model_file_path or not os.path.isfile(model_file_path):
        model_file_path = input("Enter path to OpenSim model (.osim): ").strip('"')

    if not ik_file_path or not os.path.isfile(ik_file_path):
        ik_file_path = input("Enter path to OpenSim motion file (.mot or .sto): ").strip('"')

    # raise Exception('This function is not yet working. Please use the Matlab version for now or fix line containing " time_discontinuity.append(time_vector[discontinuity_indices]) "')

    # Load motions and model
    motion = osim.Storage(ik_file_path)
    model = _quiet_model(model_file_path)

    # Initialize system and state
    model.initSystem()
    state = model.initSystem()

    # coordinate names
    flexIndexLHip, flexCoordLHip = get_model_coord(model, 'hip_flexion_' + leg)
    rotIndexLHip, rotCoordLHip = get_model_coord(model, 'hip_rotation_' + leg)
    addIndexLHip, addCoordLHip = get_model_coord(model, 'hip_adduction_' + leg)
    addIndexLKnee, addCoordLKnee = get_model_coord(model, 'knee_adduction_' + leg)
    flexIndexLKnee, flexCoordLKnee = get_model_coord(model, 'knee_angle_' + leg)
    flexIndexLAnk, flexCoordLAnk = get_model_coord(model, 'ankle_angle_' + leg)

    # get names of the hip muscles
    numMuscles = model.getMuscles().getSize()
    muscleIndices_hip = []
    muscleNames_hip = []
    for i in range(numMuscles):
        tmp_muscleName = str(model.getMuscles().get(i).getName())
        if ('add' in tmp_muscleName or 'gl' in tmp_muscleName or 'semi' in tmp_muscleName or 'bf' in tmp_muscleName or
                'grac' in tmp_muscleName or 'piri' in tmp_muscleName or 'sart' in tmp_muscleName or 'tfl' in tmp_muscleName or
                'iliacus' in tmp_muscleName or 'psoas' in tmp_muscleName or 'rect' in tmp_muscleName) and ('_' + leg in tmp_muscleName):
            muscleIndices_hip.append(i)
            muscleNames_hip.append(tmp_muscleName)

    flexMomentArms = np.zeros((motion.getSize(), len(muscleIndices_hip)))
    addMomentArms = np.zeros((motion.getSize(), len(muscleIndices_hip)))
    rotMomentArms = np.zeros((motion.getSize(), len(muscleIndices_hip)))

    # get names of the knee muscles
    numMuscles = model.getMuscles().getSize()
    muscleIndices_knee = []
    muscleNames_knee = []
    for i in range(numMuscles):
        tmp_muscleName = str(model.getMuscles().get(i).getName())
        if ('bf' in tmp_muscleName or 'gas' in tmp_muscleName or 'grac' in tmp_muscleName or 'sart' in tmp_muscleName or
                'semim' in tmp_muscleName or 'semit' in tmp_muscleName or 'rec' in tmp_muscleName or 'vas' in tmp_muscleName) and ('_' + leg in tmp_muscleName):
            muscleIndices_knee.append(i)
            muscleNames_knee.append(tmp_muscleName)

    kneeFlexMomentArms = np.zeros((motion.getSize(), len(muscleIndices_knee)))

    # get names of the ankle muscles
    numMuscles = model.getMuscles().getSize()
    muscleIndices_ankle = []
    muscleNames_ankle = []
    for i in range(numMuscles):
        tmp_muscleName = str(model.getMuscles().get(i).getName())
        print(tmp_muscleName)
        if ('edl' in tmp_muscleName or 'ehl' in tmp_muscleName or 'tibant' in tmp_muscleName or 'gas' in tmp_muscleName or
                'fdl' in tmp_muscleName or 'fhl' in tmp_muscleName or 'perb' in tmp_muscleName or 'perl' in tmp_muscleName or
                'sole' in tmp_muscleName or 'tibpos' in tmp_muscleName) and ('_' + leg in tmp_muscleName):
            muscleIndices_ankle.append(i)
            muscleNames_ankle.append(tmp_muscleName)

    ankleFlexMomentArms = np.zeros((motion.getSize(), len(muscleIndices_ankle)))

    # compute moment arms for each muscle and create time vector
    time_vector = []
    for i in range(1, motion.getSize()):
        flexAngleL = motion.getStateVector(i-1).getData().get(flexIndexLHip) / 180 * np.pi
        rotAngleL = motion.getStateVector(i-1).getData().get(rotIndexLHip) / 180 * np.pi
        addAngleL = motion.getStateVector(i-1).getData().get(addIndexLHip) / 180 * np.pi
        addAngleLKnee = motion.getStateVector(i-1).getData().get(addIndexLKnee) / 180 * np.pi
        flexAngleLknee = motion.getStateVector(i-1).getData().get(flexIndexLKnee) / 180 * np.pi
        flexAngleLank = motion.getStateVector(i-1).getData().get(flexIndexLAnk) / 180 * np.pi

        time_vector.append(motion.getStateVector(i-1).getTime())
        # Update the state with the joint angle
        coordSet = model.updCoordinateSet()
        coordSet.get(flexIndexLHip).setValue(state, flexAngleL)
        coordSet.get(rotIndexLHip).setValue(state, rotAngleL)
        coordSet.get(addIndexLHip).setValue(state, addAngleL)
        coordSet.get(flexIndexLKnee).setValue(state, flexAngleLknee)
        coordSet.get(addIndexLKnee).setValue(state, addAngleLKnee)
        coordSet.get(flexIndexLAnk).setValue(state, flexAngleLank)

        # Realize the state to compute dependent quantities
        model.computeStateVariableDerivatives(state)
        model.realizeVelocity(state)

        # Compute the moment arm hip
        for j in range(len(muscleIndices_hip)):
            muscleIndex = muscleIndices_hip[j]
            if muscleNames_hip[j][-1] == leg:
                flexMomentArm = model.getMuscles().get(muscleIndex).computeMomentArm(state, flexCoordLHip)
                flexMomentArms[i, j] = flexMomentArm

                rotMomentArm = model.getMuscles().get(muscleIndex).computeMomentArm(state, rotCoordLHip)
                rotMomentArms[i, j] = rotMomentArm

                addMomentArm = model.getMuscles().get(muscleIndex).computeMomentArm(state, addCoordLHip)
                addMomentArms[i, j] = addMomentArm

        # Compute the moment arm knee
        for j in range(len(muscleNames_knee)):
            muscleIndex = muscleIndices_knee[j]
            if muscleNames_knee[j][-1] == leg:
                kneeFlexMomentArm = model.getMuscles().get(muscleIndex).computeMomentArm(state, flexCoordLKnee)
                kneeFlexMomentArms[i, j] = kneeFlexMomentArm

                kneeAddMomentArm = model.getMuscles().get(muscleIndex).computeMomentArm(state, addCoordLKnee)
                addMomentArms[i, j] = kneeAddMomentArm

        # Compute the moment arm ankle
        for j in range(len(muscleNames_ankle)):
            muscleIndex = muscleIndices_ankle[j]
            if muscleNames_ankle[j][-1] == leg:
                ankleFlexMomentArm = model.getMuscles().get(muscleIndex).computeMomentArm(state, flexCoordLAnk)
                ankleFlexMomentArms[i, j] = ankleFlexMomentArm

    # check discontinuities
    discontinuity = []
    muscle_action = []
    time_discontinuity = []
    discontinuity_frames = []

    fDistC = plt.figure('Discontinuity', figsize=(8, 8))
    plt.title(ik_file_path)

    save_folder = os.path.join(os.path.dirname(ik_file_path),'momentArmsCheck')

    def find_discontinuities(momArms, threshold, muscleNames, action, discontinuity, muscle_action, time_discontinuity, discontinuity_frames):
        for i in range(momArms.shape[1]):
            dy = np.diff(momArms[:, i])
            discontinuity_indices = np.where(np.abs(dy) > threshold)[0]
            if discontinuity_indices.size > 0:
                print('Discontinuity detected at', muscleNames[i], 'at ', action, ' moment arm')
                plt.plot(momArms[:, i])
                plt.plot(discontinuity_indices, momArms[discontinuity_indices, i], 'rx')
                discontinuity.append(i)
                muscle_action.append(str(muscleNames[i] + ' ' + action + ' at frames: ' + str(discontinuity_indices)))
                time_discontinuity.append([time_vector[index] for index in discontinuity_indices])
                discontinuity_frames.append(discontinuity_indices)


        return discontinuity, muscle_action, time_discontinuity, discontinuity_frames

    # hip flexion
    discontinuity, muscle_action, time_discontinuity, discontinuity_frames = find_discontinuities(
        flexMomentArms, threshold, muscleNames_hip, 'flexion', discontinuity, muscle_action, time_discontinuity, discontinuity_frames)

    # hip adduction
    discontinuity, muscle_action, time_discontinuity, discontinuity_frames = find_discontinuities(
        addMomentArms, threshold, muscleNames_hip, 'adduction', discontinuity, muscle_action, time_discontinuity, discontinuity_frames)
    
    # hip rotation
    discontinuity, muscle_action, time_discontinuity, discontinuity_frames = find_discontinuities(
        rotMomentArms, threshold, muscleNames_hip, 'rotation', discontinuity, muscle_action, time_discontinuity, discontinuity_frames)
    
    # knee flexion
    discontinuity, muscle_action, time_discontinuity, discontinuity_frames = find_discontinuities(
        kneeFlexMomentArms, threshold, muscleNames_knee, 'flexion', discontinuity, muscle_action, time_discontinuity, discontinuity_frames)
    
    # knee adduction
    try:
        discontinuity, muscle_action, time_discontinuity, discontinuity_frames = find_discontinuities(
            addMomentArms, threshold, muscleNames_knee, 'adduction', discontinuity, muscle_action, time_discontinuity, discontinuity_frames)
    except Exception as e:
        print(f'Error in knee adduction discontinuity check: {e}')
    
    # ankle flexion
    discontinuity, muscle_action, time_discontinuity, discontinuity_frames = find_discontinuities(
        ankleFlexMomentArms, threshold, muscleNames_ankle, 'dorsiflexion', discontinuity, muscle_action, time_discontinuity, discontinuity_frames)
    
    # plot discontinuities
    if len(discontinuity) > 0:
        plt.legend(muscle_action)
        plt.ylabel('Muscle Moment Arms with discontinuities (m)')
        plt.xlabel('Frame (after start time)')
        utils.save_fig(plt.gcf(), save_path=os.path.join(save_folder, 'discontinuities_' + leg + '.png'))
        print('\n\nYou should alter the model - most probably you have to reduce the radius of corresponding wrap objects for the identified muscles\n\n\n')

        # save txt file with discontinuities
        with open(os.path.join(save_folder, 'discontinuities_' + leg + '.txt'), 'w') as f:
            f.write(f"model file = {model_file_path}\n")
            f.write(f"motion file = {ik_file_path}\n")
            f.write(f"leg checked = {leg}\n")
            
            f.write("\n muscles with discontinuities \n", ) 
            
            for i in range(len(muscle_action)):
                try:
                    f.write("%s : time %s \n" % (muscle_action[i], time_discontinuity[i]))
                except:
                    print('no discontinuities detected')

        momentArmsAreWrong = 1
    else:
        plt.close(fDistC)
        print('No discontinuities detected')
        momentArmsAreWrong = 0

    # plot hip flexion
    plt.figure('flexMomentArms_' + leg, figsize=(8, 8))
    plt.plot(flexMomentArms)
    plt.title('All muscle moment arms in motion ' + ik_file_path)
    plt.legend(muscleNames_hip, loc='best')
    plt.ylabel('Hip Flexion Moment Arm (m)')
    plt.xlabel('Frame (after start time)')
    utils.save_fig(plt.gcf(), save_path=os.path.join(save_folder, 'hip_flex_MomentArms_' + leg + '.png'))

    # hip adduction
    plt.figure('addMomentArms_' + leg, figsize=(8, 8))
    plt.plot(addMomentArms)
    plt.title('All muscle moment arms in motion ' + ik_file_path)
    plt.legend(muscleNames_hip, loc='best')
    plt.ylabel('Hip Adduction Moment Arm (m)')
    plt.xlabel('Frame (after start time)')
    utils.save_fig(plt.gcf(), save_path=os.path.join(save_folder, 'hip_add_MomentArms_' + leg + '.png'))

    # hip rotation
    plt.figure('rotMomentArms_' + leg, figsize=(8, 8))
    plt.plot(rotMomentArms)
    plt.title('All muscle moment arms in motion ' + ik_file_path)
    plt.legend(muscleNames_hip, loc='best')
    plt.ylabel('Hip Rotation Moment Arm (m)')
    plt.xlabel('Frame (after start time)')
    utils.save_fig(plt.gcf(), save_path=os.path.join(save_folder, 'hip_rot_MomentArms_' + leg + '.png'))

    # knee flexion
    plt.figure('kneeFlexMomentArms_' + leg, figsize=(8, 8))
    plt.plot(kneeFlexMomentArms)
    plt.title('All muscle moment arms in motion ' + ik_file_path)
    plt.legend(muscleNames_knee, loc='best')
    plt.ylabel('Knee Flexion Moment Arm (m)')
    plt.xlabel('Frame (after start time)')
    utils.save_fig(plt.gcf(), save_path=os.path.join(save_folder, 'knee_MomentArms_' + leg + '.png'))

    # ankle flexion
    plt.figure('ankleFlexMomentArms_' + leg, figsize=(8, 8))
    plt.plot(ankleFlexMomentArms)
    plt.title('All muscle moment arms in motion ' + ik_file_path)
    plt.legend(muscleNames_ankle, loc='best')
    plt.ylabel('Ankle Dorsiflexion Moment Arm (m)')
    plt.xlabel('Frame (after start time)')
    utils.save_fig(plt.gcf(), save_path=os.path.join(save_folder, 'ankle_MomentArms_' + leg + '.png'))

    print('Moment arms checked for ' + ik_file_path)
    print('Results saved in ' + save_folder + ' \n\n' )

    return momentArmsAreWrong, discontinuity, muscle_action, discontinuity_frames

def muscles_per_coordinate(osimModel=None):

    if osimModel is None:
        osimModel = input("Enter path to OpenSim model (.osim): ").strip('"')
        osimModel = _quiet_model(osimModel)


    muscles = {}
    indexes = {}
    coordSet = osimModel.getCoordinateSet()

    for i in range(coordSet.getSize()):
        coord = coordSet.get(i)    
        coord_name = coord.getName()
        muscles[coord_name] = []
        indexes[coord_name] = []
        coord = osimModel.getCoordinateSet().get(coord_name)
        state = osimModel.initSystem()
        osimModel.realizePosition(state)

        for i in range(osimModel.getMuscles().getSize()):
            muscle = osimModel.getMuscles().get(i)
            if abs(muscle.computeMomentArm(state, coord)) > 1e-4:
                muscles[coord_name].append(muscle.getName())
                indexes[coord_name].append(i)

    if __name__ == "__main__":
        
        for coord_name in muscles.keys():
            print(f'coordinate: {coord_name} : \n')
            print(muscles[coord_name])
            print('\n')

    return muscles, indexes

#: Cap on evaluation points per muscle in sampleMuscleQuantities -- guards
#: against combinatorial explosion for muscles spanning many DOFs. Above it the
#: per-coordinate N is reduced until the grid fits, so a nominal N is NOT always
#: the N a muscle actually gets: at 1500, a 3-DOF muscle collapses from N=12 to
#: an effective 11, and a 4-DOF muscle sits at 6 from N=7 upwards. Module-level
#: so a convergence study can raise it (tests/ModeneseN --max-eval-points)
#: without editing this file. Changing it changes results for any muscle it
#: binds on, so leave the default alone for production runs.
MAX_EVAL_POINTS = 1500

#: Coordinates the muscle optimiser must NOT treat as spanned, by exact name or
#: by substring. The grid is N**nDOF, so every extra coordinate multiplies the
#: cost by N — and a secondary DOF earns its place only if the muscle really
#: does change length over it.
#:
#: Measured on GPK_v3 (Athlete_06, N=4): `knee_adduction` and `subtalar_angle`
#: are unlocked with ranges of +-20 deg and +-30 deg, and they push the
#: hamstrings/quadriceps group to 5 spanned coordinates (4**5 = 1024 poses,
#: 177 s each) and the gastrocnemii to 6 (capped down to 3**6 = 729, 113 s
#: each). Those 13 muscles cost 34 of the run's 39 minutes. Excluding the two
#: secondary DOFs drops them to 4 coordinates.
#:
#: Empty by default — this changes results, so a project opts in through
#: BatchSettings.muscle_opt_skip_coords rather than inheriting it silently.
MUSCLE_OPT_SKIP_COORDS = ()

#: A coordinate counts as spanned only if the muscle's moment arm exceeds this
#: anywhere in its range. 1e-4 m = 0.1 mm, which is below the resolution of
#: any musculoskeletal geometry and lets numerical noise add a whole axis to
#: the grid. Raise it to exclude coordinates the muscle barely acts on.
MUSCLE_OPT_MA_TOL = 1e-4


def sampleMuscleQuantities(osimModel, osimMuscle, muscleQuant, N_eval):
    """Sample muscle-tendon quantities across the range of motion of the
    coordinates spanned by the muscle (Modenese 2015 muscle optimiser helper).

    For each combination of N_eval values per spanned coordinate the model is
    posed, muscles are equilibrated (elastic tendon, activation = 1) and the
    following are recorded per evaluation point:

        [muscleTendonLength, normalizedFiberLength, tendonLength,
         normalizedFiberLength*cos(pennation), pennationAngle]

    muscleQuant='MTL' returns only muscleTendonLength per point; 'all' returns
    the full row above (the indices used by optimMuscleParams are 0,1,2,4).
    """
    import itertools

    state = osimModel.initSystem()
    gp = osimMuscle.getGeometryPath()
    coords = osimModel.getCoordinateSet()

    # getMuscles().get(...) hands back a base-class Muscle handle, and
    # computeInitialFiberEquilibrium is declared on the CONCRETE type
    # (Millard2012EquilibriumMuscle, Thelen2003Muscle, ...). Without this
    # downcast BOTH getattr lookups in _equilibrate_single miss, every
    # evaluation point falls through to equilibrateMuscles(), and the whole
    # model is equilibrated to sample one muscle. Measured on this project's
    # 80-muscle Catelli model: 0.39 ms/call for the model against 0.010 ms for
    # the single muscle. The comment below always claimed it equilibrated only
    # the current muscle; until now it never did.
    _mus = osimMuscle
    try:
        _cc = getattr(osim, osimMuscle.getConcreteClassName(), None)
        if _cc is not None and hasattr(_cc, "safeDownCast"):
            _mus = _cc.safeDownCast(osimMuscle) or osimMuscle
    except Exception:                                        # noqa: BLE001
        pass

    def _equilibrate_single():
        """Equilibrate ONLY the current muscle (not all ~100 muscles)."""
        for meth in ("computeInitialFiberEquilibrium", "computeFiberEquilibrium"):
            fn = getattr(_mus, meth, None)
            if fn is not None:
                try:
                    fn(state)
                    return
                except Exception:
                    pass
        try:
            osimModel.equilibrateMuscles(state)   # fallback (slow)
        except Exception:
            pass

    # --- coordinates spanned by the muscle (non-zero moment arm in ROM) -------
    # Detection only needs the muscle path length/moment arm, so realizePosition
    # (cheap) is enough here -- no need for the full constraint assembler.
    _skip = tuple(MUSCLE_OPT_SKIP_COORDS or ())
    _ma_tol = float(MUSCLE_OPT_MA_TOL)
    spanned = []
    _excluded = []
    for i in range(coords.getSize()):
        c = coords.get(i)
        try:
            if c.getLocked(state) or c.isConstrained(state):
                continue
        except Exception:
            pass
        _nm = c.getName()
        if any(_s == _nm or _s in _nm for _s in _skip):
            _excluded.append(_nm)
            continue
        rmin, rmax = c.getRangeMin(), c.getRangeMax()
        hit = False
        for frac in (0.0, 0.5, 1.0):
            c.setValue(state, rmin + frac * (rmax - rmin), False)
            osimModel.realizePosition(state)
            try:
                if abs(gp.computeMomentArm(state, c)) > _ma_tol:
                    hit = True
                    break
            except Exception:
                pass
        c.setValue(state, 0.5 * (rmin + rmax), False)
        if hit:
            spanned.append(i)

    # --- full-factorial grid over the spanned coordinates --------------------
    # Bound the grid BEFORE building it: cap the number of DOFs and reduce the
    # points-per-axis so N_per**nDOF stays under MAX_EVAL_POINTS (a full product
    # of N_eval**nDOF would blow up memory for multi-joint muscles).
    MAX_DOF = 6
    if len(spanned) > MAX_DOF:
        spanned = spanned[:MAX_DOF]
    nDOF = len(spanned)
    if _excluded:
        print(f"      [opt] {osimMuscle.getName()}: {nDOF} DOF "
              f"(excluded {', '.join(_excluded)})")
    n_per = N_eval
    if nDOF and n_per ** nDOF > MAX_EVAL_POINTS:
        n_per = max(2, int(MAX_EVAL_POINTS ** (1.0 / nDOF)))
    axes = [np.linspace(coords.get(i).getRangeMin(),
                        coords.get(i).getRangeMax(), n_per) for i in spanned]
    combos = list(itertools.product(*axes)) if axes else [()]

    need_equil = (muscleQuant != 'MTL')                   # MTL needs geometry only
    if need_equil:
        try:
            osimMuscle.setActivation(state, 1.0)
        except Exception:
            pass

    musOutput = []
    for combo in combos:
        # set independent coords; enforce constraints once (updates coupled DOFs)
        for k, i in enumerate(spanned):
            coords.get(i).setValue(state, float(combo[k]),
                                   k == len(spanned) - 1)
        if not spanned:
            osimModel.assemble(state)

        if not need_equil:
            osimModel.realizePosition(state)
            musOutput.append(osimMuscle.getLength(state))
            continue

        osimModel.realizeVelocity(state)
        _equilibrate_single()
        MTL = osimMuscle.getLength(state)
        try:
            LfibNorm = osimMuscle.getNormalizedFiberLength(state)
            Lten = osimMuscle.getTendonLength(state)
            penAngle = osimMuscle.getPennationAngle(state)
        except Exception:
            LfibNorm, Lten, penAngle = np.nan, np.nan, 0.0
        musOutput.append([MTL, LfibNorm, Lten,
                          LfibNorm * np.cos(penAngle), penAngle])
    return musOutput


def muscle_optimimizer_Modenese2015(osim_model_path=None, save_path=None,
                                    ref_model_path=None, N_eval=10,
                                    log_folder=None):
    """
    Optimize muscle parameters in an OpenSim model using the Modenese 2015 method.

    Args:
        osim_model_path (str): Path to the TARGET (e.g. scaled) .osim model whose
            muscle optimal-fiber-length / tendon-slack-length will be optimised.
        save_path (str, optional): Where to write the optimised model. Defaults to
            '<target>_opt_N<N_eval>.osim'.
        ref_model_path (str, optional): Reference (template/generic) model whose
            muscle operating range is preserved. Defaults to the target model.
        N_eval (int): Sampling points per spanned coordinate (default 10 -> _N10).
        log_folder (str, optional): Folder for the per-muscle optimisation log.
    """
    if osim_model_path is None:
        osim_model_path = input("Path to target model (.osim): ").strip('"')
    if ref_model_path is None:
        ref_model_path = osim_model_path
    if log_folder is None:
        log_folder = os.path.dirname(osim_model_path)

    # The Modenese sampling equilibrates muscles at extreme joint poses, which
    # makes OpenSim emit a flood of "at its minimum fiber length" warnings --
    # this both spams the console and slows the run dramatically (log I/O).
    # Silence the OpenSim logger during optimisation, then restore it.
    try:
        _prev_log_level = osim.Logger.getLevelString()
    except Exception:
        _prev_log_level = "Info"
    try:
        osim.Logger.setLevelString("off")
    except Exception:
        pass
    try:
        osim_model_opt, sims_info = optimMuscleParams(ref_model_path, osim_model_path,
                                                      N_eval, log_folder)
    finally:
        try:
            osim.Logger.setLevelString(_prev_log_level)
        except Exception:
            pass

    if save_path is None:
        save_path = osim_model_path.replace('.osim', f'_opt_N{N_eval}.osim')
    osim_model_opt.printToXML(save_path)
    print(f"Optimized model saved to: {save_path}")
    return save_path


def _apply_muscle_opt_settings():
    """Pull the optimiser's DOF knobs from the project's BatchSettings, once.

    Kept as module globals rather than threaded through four signatures
    because sampleMuscleQuantities is called from two places and is itself
    called per muscle per quantity; a project sets the policy once and every
    call site sees it.
    """
    global MUSCLE_OPT_SKIP_COORDS, MUSCLE_OPT_MA_TOL
    try:
        from . import settings as _st
        _bs = getattr(_st, "BatchSettings", None)
    except Exception:
        _bs = None
    if _bs is None:
        return
    _sk = getattr(_bs, "muscle_opt_skip_coords", None)
    if _sk:
        MUSCLE_OPT_SKIP_COORDS = tuple(_sk)
        print(f"[opt] excluding coordinates from the muscle-optimiser grid: "
              f"{', '.join(MUSCLE_OPT_SKIP_COORDS)}")
    _tol = getattr(_bs, "muscle_opt_ma_tol", None)
    if _tol:
        MUSCLE_OPT_MA_TOL = float(_tol)
        print(f"[opt] moment-arm threshold for 'spanned': {MUSCLE_OPT_MA_TOL*1000:.2f} mm")


def optimMuscleParams(osimModel_ref_filepath, osimModel_targ_filepath, N_eval, log_folder):

    # Read the project's DOF policy before any muscle is sampled.
    _apply_muscle_opt_settings()

    # results file identifier
    res_file_id_exp = '_N' + str(N_eval)
    
    # import models
    osimModel_ref = _quiet_model(osimModel_ref_filepath)
    osimModel_targ = _quiet_model(osimModel_targ_filepath)
    
    # models details
    name = Path(osimModel_targ_filepath).stem
    ext = Path(osimModel_targ_filepath).suffix
    
    # assigning new name to the model
    osimModel_opt_name = name + '_opt' + res_file_id_exp + ext
    osimModel_targ.setName(osimModel_opt_name)
    
    # initializing log file
    log_folder = Path(log_folder)
    log_folder.mkdir(parents=True, exist_ok=True)
    log_file_path = log_folder / (name + '_opt' + res_file_id_exp + '.log')
    
    # Check if log file exists and find last processed muscle
    # ROTATE the log before reading it. `processed_muscles` below is a resume
    # feature: any muscle named in this file is SKIPPED. The file is opened in
    # append mode and never cleared, so a log left by an earlier run makes a
    # later run skip almost everything and write a model whose parameters are
    # mostly the UNOPTIMISED scaled ones -- under an `_opt_N10` filename, with
    # no error and in a fraction of the expected time.
    #
    # Observed 2026-08-06: a production run resumed from a 168-entry log,
    # optimised 8 muscles of 80, and produced a scaled_opt_N10.osim that
    # differed from scaled.osim on 8 muscles. CEINMS then ran against it.
    #
    # Resume is worth far less than it was: the sampler is ~10x faster since
    # the muscle downcast fix, so a full pass is minutes. Rotating always means
    # an interrupted run restarts cleanly instead of silently half-finishing.
    if log_file_path.exists() and log_file_path.stat().st_size > 0:
        import time as _t
        _prev = log_file_path.with_suffix('.log.prev_%s' % _t.strftime('%y%m%d_%H%M%S'))
        try:
            log_file_path.rename(_prev)
            print('[muscle-opt] rotated previous log -> %s' % _prev.name)
        except OSError:
            pass

    processed_muscles = set()
    if log_file_path.exists():
        with open(log_file_path, 'r') as f:
            for line in f:
                if 'Calculated optimized muscle parameters for' in line:
                    muscle_name = line.split('Calculated optimized muscle parameters for')[1].split('in')[0].strip()
                    processed_muscles.add(muscle_name)
        print(f'Found {len(processed_muscles)} already processed muscles in log file')
    
    logging.basicConfig(filename=str(log_file_path), filemode='a', format='%(levelname)s:%(message)s', level=logging.INFO)
        
    # get muscles
    muscles = osimModel_ref.getMuscles()
    muscles_scaled = osimModel_targ.getMuscles()
    
    # initialize with recognizable values
    LmOptLts_opt = -1000*np.ones((muscles.getSize(),2))
    SimInfo = {}
    
    for n_mus in range(0, muscles.getSize()):
        
        # current muscle name (here so that it is possible to choose a single muscle when developing).
        curr_mus_name = muscles.get(n_mus).getName()
        
        # Skip if already processed
        if curr_mus_name in processed_muscles:
            print(f'Skipping muscle {n_mus+1}: {curr_mus_name} (already processed)')
            continue
        
        tic = time()
        print('processing mus ' + str(n_mus+1) + ': ' + curr_mus_name)
        
        # import muscles
        curr_mus = muscles.get(curr_mus_name)
        curr_mus_scaled = muscles_scaled.get(curr_mus_name)
        
        # extracting the muscle parameters from reference model
        LmOptLts = [curr_mus.getOptimalFiberLength(), curr_mus.getTendonSlackLength()]
        PenAngleOpt = curr_mus.getPennationAngleAtOptimalFiberLength()
        Mus_ref = sampleMuscleQuantities(osimModel_ref,curr_mus,'all',N_eval)
        
        # calculating minimum fiber length before having pennation 90 deg
        # acos(0.1) = 1.47 red = 84 degrees, chosen as in OpenSim
        limitPenAngle = np.arccos(0.1)
        # this is the minimum length the fiber can be for geometrical reasons.
        LfibNorm_min = np.sin(PenAngleOpt) / np.sin(limitPenAngle)
        # LfibNorm as calculated above can be shorter than the minimum length
        # at which the fiber can generate force (taken to be 0.5 Zajac 1989)
        if LfibNorm_min < 0.5:
            LfibNorm_min = 0.5
        
        # muscle-tendon paramenters value
        MTL_ref = [musc_param_iter[0] for musc_param_iter in Mus_ref]
        LfibNorm_ref = [musc_param_iter[1] for musc_param_iter in Mus_ref]
        LtenNorm_ref = [musc_param_iter[2]/LmOptLts[1] for musc_param_iter in Mus_ref]
        penAngle_ref = [musc_param_iter[4] for musc_param_iter in Mus_ref]
        # LfibNomrOnTen_ref = LfibNorm_ref.*cos(penAngle_ref)
        LfibNomrOnTen_ref = [(musc_param_iter[1]*np.cos(musc_param_iter[4])) for musc_param_iter in Mus_ref]         
        
        # checking the muscle configuration that do not respect the condition.
        okList = [pos for pos, value in enumerate(LfibNorm_ref) if value > LfibNorm_min]

        # Guard: if too few valid evaluation points remain (< 2 needed to fit the
        # two parameters), the linear system is unsolvable. Keep this muscle's
        # existing (scaled) optimal-fiber / tendon-slack lengths unchanged and
        # move on instead of crashing on empty arrays.
        if len(okList) < 2:
            LmOptLts_opt[n_mus] = [curr_mus_scaled.getOptimalFiberLength(),
                                   curr_mus_scaled.getTendonSlackLength()]
            logging.warning('Only %d valid sample(s) for %s; kept scaled '
                            'parameters (not optimised).'
                            % (len(okList), curr_mus_name))
            continue

        # keeping only acceptable values
        MTL_ref = np.array([MTL_ref[index] for index in okList])
        LfibNorm_ref = np.array([LfibNorm_ref[index] for index in okList])
        LtenNorm_ref = np.array([LtenNorm_ref[index] for index in okList])
        penAngle_ref = np.array([penAngle_ref[index] for index in okList])
        LfibNomrOnTen_ref = np.array([LfibNomrOnTen_ref[index] for index in okList])
        
        # in the target only MTL is needed for all muscles
        MTL_targ = sampleMuscleQuantities(osimModel_targ,curr_mus_scaled,'MTL',N_eval)
        evalTotPoints = len(MTL_targ)
        MTL_targ = np.array([MTL_targ[index] for index in okList])
        evalOkPoints  = len(MTL_targ)
        
        # The problem to be solved is: 
        # [LmNorm*cos(penAngle) LtNorm]*[Lmopt Lts]' = MTL;
        # written as Ax = b or their equivalent (A^T A) x = (A^T b)  
        A = np.array([LfibNomrOnTen_ref , LtenNorm_ref]).T
        b = MTL_targ
        
        # ===== LINSOL =======
        # solving the problem to calculate the muscle param
        try:
            x = linalg.solve(np.dot(A.T , A) , np.dot(A.T , b))
        except (np.linalg.LinAlgError, linalg.LinAlgError, ValueError):
            # normal-equations matrix is (near-)singular for this muscle
            # (e.g. tendon length ~constant over the sampled range). Fall back
            # to a rank-revealing least-squares solve, then to NNLS.
            x, *_ = np.linalg.lstsq(A, b, rcond=None)
            if np.min(x) <= 0:
                x = optimize.nnls(np.dot(A.T , A), np.dot(A.T , b))[0]
            logging.warning('Singular system for %s; used least-squares fallback.'
                            % curr_mus_name)
        LmOptLts_opt[n_mus] = x
        
        # checking the results
        if np.min(x) <= 0:
            # informing the user
            line0 = ' '
            line1 = 'Negative value estimated for muscle parameter of muscle ' + curr_mus_name + '\n'
            line2 = '                         Lm Opt        Lts' + '\n'
            line3 = 'Template model       : ' + str(LmOptLts) + '\n'
            line4 ='Optimized param      : ' + str(LmOptLts_opt[n_mus]) + '\n'
            
            # ===== IMPLEMENTING CORRECTIONS IF ESTIMATION IS NOT CORRECT =======
            x = optimize.nnls(np.dot(A.T , A) , np.dot(A.T , b))
            x = x[0]
            LmOptLts_opt[n_mus] = x
            line5 = 'Opt params (optimize.nnls): ' + str(LmOptLts_opt[n_mus])
            
            logging.info(line0 + line1 + line2 + line3 + line4 + line5 + '\n')
            # In our tests, if something goes wrong is generally tendon slack 
            # length becoming negative or zero because tendon length doesn't change
            # throughout the range of motion, so lowering the rank of A.
            if np.min(x) <= 0:
                # analyzes of Lten behaviour
                Lten_ref = [musc_param_iter[2] for musc_param_iter in Mus_ref]
                Lten_ref = np.array([Lten_ref[index] for index in okList])
                if (np.max(Lten_ref) - np.min(Lten_ref)) < 0.0001:
                    logging.warning(' Tendon length not changing throughout range of motion')
                
                # calculating proportion of tendon and fiber
                Lten_fraction = Lten_ref/MTL_ref
                Lten_targ = Lten_fraction*MTL_targ
                
                # first round: optimizing Lopt maintaing the proportion of
                # tendon as in the reference model
                A1 = np.array([LfibNomrOnTen_ref , LtenNorm_ref*0]).T
                b1 = MTL_targ - Lten_targ
                x1 = optimize.nnls(np.dot(A1.T , A1) , np.dot(A1.T , b1))
                x[0] = x1[0][0]
                
                # second round: using the optimized Lopt to recalculate Lts
                A2 = np.array([LfibNomrOnTen_ref*0 , LtenNorm_ref]).T
                b2 = MTL_targ - np.dot(A1,x1[0])
                x2 = optimize.nnls(np.dot(A2.T , A2) , np.dot(A2.T , b2))
                x[1] = x2[0][1]
                
                LmOptLts_opt[n_mus] = x
            
        
        # Here tests about/against optimizers were implemented
        
        # calculating the error (mean squared errors)
        fval = mean_squared_error(b, np.dot(A,x), squared=False)
        
        # update muscles from scaled model
        curr_mus_scaled.setOptimalFiberLength(LmOptLts_opt[n_mus][0])
        curr_mus_scaled.setTendonSlackLength(LmOptLts_opt[n_mus][1])
        
        # PRINT LOGS
        toc = time() - tic
        line0 = ' '
        line1 = 'Calculated optimized muscle parameters for ' + curr_mus.getName() + ' in ' +  str(toc) + ' seconds.' + '\n'
        line2 = '                         Lm Opt        Lts' + '\n'
        line3 = 'Template model       : ' + str(LmOptLts) + '\n'
        line4 = 'Optimized param      : ' + str(LmOptLts_opt[n_mus]) + '\n'
        line5 = 'Nr of eval points    : ' + str(evalOkPoints) + '/' + str(evalTotPoints) + ' used' + '\n'
        line6 = 'fval                 : ' + str(fval) + '\n'
        line7 = 'var from template [%]: ' + str(100*(np.abs(LmOptLts - LmOptLts_opt[n_mus])) / LmOptLts) + '%' + '\n'
        
        logging.info(line0 + line1 + line2 + line3 + line4 + line5 + line6 + line7 + '\n')
              
        # SIMULATION INFO AND RESULTS
        
        SimInfo[n_mus] = {}
        SimInfo[n_mus]['colheader'] = curr_mus.getName()
        SimInfo[n_mus]['LmOptLts_ref'] = LmOptLts
        SimInfo[n_mus]['LmOptLts_opt'] = LmOptLts_opt[n_mus]
        SimInfo[n_mus]['varPercLmOptLts'] = 100*(np.abs(LmOptLts - LmOptLts_opt[n_mus])) / LmOptLts
        SimInfo[n_mus]['sampledEvalPoints'] = evalOkPoints
        SimInfo[n_mus]['sampledEvalPoints'] = evalTotPoints
        SimInfo[n_mus]['fval'] = fval
    
    # assigning optimized model as output
    osimModel_opt = osimModel_targ
            
    return osimModel_opt, SimInfo

def plot_optimization_results(intial_model_path, optimised_model_path):

    base_model = _quiet_model(intial_model_path)
    optimized_model = _quiet_model(optimised_model_path)
    
    muscles = base_model.getMuscles()
    n_muscles = muscles.getSize()
    
    params = ['optimal_fiber_length', 'tendon_slack_length', 'pennation_angle_at_optimal']
    fig, axes = plt.subplots(len(params), 1, figsize=(8, 12))
    
    for ax, param in zip(axes, params):
        ax.set_title(param.replace('_', ' ').title())
        ax.set_xlabel('Muscle Index')
        ax.set_ylabel(param.replace('_', ' ').title())
        for i in range(n_muscles):
            muscle = muscles.get(i)
            muscle_name = muscle.getName()
            base_muscle = base_model.getMuscles().get(muscle_name)
            optim_muscle = optimized_model.getMuscles().get(muscle_name)
            if param == 'optimal_fiber_length':
                base_value = base_muscle.getOptimalFiberLength()
                optim_value = optim_muscle.getOptimalFiberLength()
            elif param == 'tendon_slack_length':
                base_value = base_muscle.getTendonSlackLength()
                optim_value = optim_muscle.getTendonSlackLength()
            elif param == 'pennation_angle_at_optimal':
                base_value = base_muscle.getPennationAngleAtOptimalFiberLength()
                optim_value = optim_muscle.getPennationAngleAtOptimalFiberLength()
            
            # bar plot
            ax.bar(i - 0.2, base_value, width=0.4, label='Base' if i == 0 else "", color='b')
            ax.bar(i + 0.2, optim_value, width=0.4, label='Optimized' if i == 0 else "", color='r')

            # setting x-ticks
            ax.set_xticks(range(n_muscles))
            ax.set_xticklabels([muscles.get(i).getName() for i in range(n_muscles)], rotation=90, size=6)

        ax.legend()    
    plt.tight_layout()
    
    save_path = optimised_model_path.replace('.osim', '_muscle_params.png')
    plt.savefig(save_path)
    print(f'Optimization results plot saved to {save_path}')


    def main(osim_model_ref_filepath=None, osim_model_targ_filepath=None):
        # ========= USER SETTINGS =======
        # model files with paths
        if osim_model_ref_filepath is None:
            osim_model_ref_filepath = input("Please provide the path to the reference model: ").strip('"')
        if osim_model_targ_filepath is None:
            osim_model_targ_filepath = input("Please provide the path to the target model: ").strip('"')
        optimized_model_folder = os.path.dirname(osim_model_targ_filepath)
        
        # evaluations
        n_eval = 10
        # ===============================

        # initializing folders and log file
        log_folder = optimized_model_folder
        
        # checking if results folder exists. If not, create it.
        if not os.path.isdir(optimized_model_folder):
            warnings.warn(f'Folder {optimized_model_folder} does not exist. It will be created.')
            os.makedirs(optimized_model_folder)

        # optimizing target model based on reference model for n_eval points per
        # degree of freedom
        osim_model_opt, sims_info = optimMuscleParams(osim_model_ref_filepath,
                                                        osim_model_targ_filepath,
                                                        n_eval,
                                                        log_folder)

        # printing the optimized model
        output_path = osim_model_targ_filepath.replace('.osim', f'_opt_N{n_eval}.osim')
        osim_model_opt.printToXML(output_path)
        print(f'Optimized model saved to: {output_path}')
        
        # plotting optimization results
        plot_optimization_results(osim_model_targ_filepath, output_path)

    
    model = _quiet_model(intial_model_path)
    state = model.initSystem()

    # Call the Modenese 2015 optimization method
    try:
        main(osim_model_ref_filepath=intial_model_path, osim_model_targ_filepath=optimised_model_path)
        print("Muscle optimization completed successfully.")
    except Exception as e:
        print(f"Error during muscle optimization: {e}")
        return

    # Determine save path
    if save_path is None:
        save_path = intial_model_path.replace('.osim', '_optimized.osim')

    # Save the optimized model
    model.printToXML(save_path)
    print(f"Optimized model saved to: {save_path}")

def compare_osim_models(model_list=None):

    if not model_list:
        model_list = []
        while True:
            model_path = input("Enter the path to an OpenSim model (.osim) (or 'done' to finish): ").strip('"')
            if model_path.lower() == 'done':
                break
            if model_path.strip():
                model_list.append(model_path)


    # Load all models and extract muscles
    models = []
    model_names = []
    all_muscles_set = set()
    
    for idx, model_path in enumerate(model_list):
        model = _quiet_model(model_path)
        models.append(model)
        model_name = f"Model {idx + 1}"
        model_names.append(model_name)
        
        muscles = model.getMuscles()
        print(f"{model_name}: {model_path} has {muscles.getSize()} muscles")
        
        for i in range(muscles.getSize()):
            all_muscles_set.add(muscles.get(i).getName())
    
    # Compare muscle properties 
    muscle_properties_list = []
    for muscle_name in all_muscles_set:
        for model, model_name in zip(models, model_names):
            muscles = model.getMuscles()
            muscle = None
            for i in range(muscles.getSize()):
                if muscles.get(i).getName() == muscle_name:
                    muscle = muscles.get(i)
                    break
            
            if muscle:
                optimal_fiber_length = muscle.getOptimalFiberLength()
                tendon_slack_length = muscle.getTendonSlackLength()
                pennation_angle = muscle.getPennationAngleAtOptimalFiberLength()
                max_isometric_force = muscle.getMaxIsometricForce()
                muscle_properties_list.append({
                    'Muscle': muscle_name,
                    'Model': model_name,
                    'Optimal Fiber Length': optimal_fiber_length,
                    'Tendon Slack Length': tendon_slack_length,
                    'Pennation Angle at Optimal Fiber Length': pennation_angle,
                    'Maximum Isometric Force': max_isometric_force
                })
    
    muscle_properties = pd.DataFrame(muscle_properties_list)
    
    # Create spider plots for each property
    properties = ['Optimal Fiber Length', 'Tendon Slack Length', 'Pennation Angle at Optimal Fiber Length', 'Maximum Isometric Force']

    # Use the full sorted union of muscles so all models share the same axis
    all_muscle_names = sorted(all_muscles_set)
    num_vars = len(all_muscle_names)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    # Pivot to wide format: index=Muscle, columns=Model — missing entries become 0
    n_props = len(properties)
    fig, axes = plt.subplots(1, n_props, figsize=(6 * n_props, 6), subplot_kw=dict(projection='polar'))

    for idx, prop in enumerate(properties):
        ax = axes[idx]
        wide = (
            muscle_properties[['Muscle', 'Model', prop]]
            .pivot(index='Muscle', columns='Model', values=prop)
            .reindex(all_muscle_names)
            .fillna(0)
        )
        for model_name in model_names:
            if model_name not in wide.columns:
                continue
            values = wide[model_name].tolist()
            values += values[:1]
            ax.plot(angles, values, 'o-', linewidth=2, label=model_name)
            ax.fill(angles, values, alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(all_muscle_names, size=8)
        ax.set_title(f'Spider Plot: {prop}', size=14, weight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.grid(True)

    plt.tight_layout()

    # count coordinates
    coordinate_presence = {}  # coord_name -> list of model names that have it
    for model, model_name in zip(models, model_names):
        coordSet = model.getCoordinateSet()
        for i in range(coordSet.getSize()):
            coord_name = coordSet.get(i).getName()
            coordinate_presence.setdefault(coord_name, []).append(model_name)
    print("\nCoordinate counts across models:")
    for coord_name, present_in in sorted(coordinate_presence.items()):
        missing = [m for m in model_names if m not in present_in]
        missing_str = f"  [MISSING in: {', '.join(missing)}]" if missing else ""
        print(f"{coord_name}: {len(present_in)}/{len(models)} ({', '.join(present_in)}){missing_str}")

    plt.show()

def optimize_moment_arms(ref_model_path=None, target_model_path=None):
    '''Optimize muscle parameters in the target model to match the moment arms of the reference model.
    
    NOT FINNISED!!!
    
    '''

    if ref_model_path is None:
        ref_model_path = input("Enter the path to the reference .osim model file: ").strip('"')
    if target_model_path is None:
        target_model_path = input("Enter the path to the target .osim model file: ").strip('"')

    ref_model = _quiet_model(ref_model_path)
    target_model = _quiet_model(target_model_path)
    optimized_model = _quiet_model(target_model_path)

    def compute_moment_arms(model):
        state = model.initSystem()
        model.realizePosition(state)
        moment_arms = {}
        for i in range(model.getMuscles().getSize()):
            muscle = model.getMuscles().get(i)
            muscle_name = muscle.getName()
            moment_arms[muscle_name] = {}
            for j in range(model.getCoordinateSet().getSize()):
                coord = model.getCoordinateSet().get(j)
                coord_name = coord.getName()
                moment_arms[muscle_name][coord_name] = muscle.computeMomentArm(state, coord)
        return moment_arms
    
    def optimize_moment_arm(muscle_name, coord_name, ref_arm, target_arm):
        # Placeholder for optimization logic
        # In a real implementation, this would adjust muscle parameters in the target model to minimize the difference in moment arms
        optimized_arm = target_arm
        return optimized_arm
    
    ref_moment_arms = compute_moment_arms(ref_model)
    target_moment_arms = compute_moment_arms(target_model)

    for muscle_name in ref_moment_arms.keys():
        if muscle_name in target_moment_arms:
            for coord_name in ref_moment_arms[muscle_name].keys():
                if coord_name in target_moment_arms[muscle_name]:
                    ref_arm = ref_moment_arms[muscle_name][coord_name]
                    target_arm = target_moment_arms[muscle_name][coord_name]
                    if abs(ref_arm - target_arm) > 0.01:  # Threshold for optimization
                        print(f"Optimizing {muscle_name} for {coord_name}: Ref={ref_arm:.4f}, Target={target_arm:.4f}")
                        optimized_arm = optimize_moment_arm(muscle_name, coord_name, ref_arm, target_arm)



    # save the optimized model
    optimized_model_path = target_model_path.replace('.osim', '_optimized.osim')
    optimized_model.printToXML(optimized_model_path)
    print(f"Optimized model saved to: {optimized_model_path}")


    # Compare moment arms and plot results
    model1 = _quiet_model(ref_model_path)
    model2 = _quiet_model(target_model_path)
    model3 = _quiet_model(optimized_model_path)

    optimized_arms = compute_moment_arms(model3)


    n_muscles = len(ref_moment_arms)
    n_cols = 5
    n_rows = (n_muscles + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 6, n_rows * 3))
    axes = axes.flatten() if n_muscles > 1 else [axes]
    for idx, muscle_name in enumerate(ref_moment_arms.keys()):
        ax = axes[idx]
        ref_arms = list(ref_moment_arms[muscle_name].values())
        target_arms = list(target_moment_arms[muscle_name].values())
        optimized_arms_values = list(optimized_arms[muscle_name].values())
        
        coords = list(ref_moment_arms[muscle_name].keys())
        
        ax.plot(coords, ref_arms, 'o-', label='Reference')
        ax.plot(coords, target_arms, 'x-', label='Target')
        ax.plot(coords, optimized_arms_values, 's-', label='Optimized')
        
        ax.set_title(muscle_name)
        ax.set_ylabel('Moment Arm (m)')
        ax.tick_params(axis='x', rotation=45)
    
    utils.mmfn(fig, n_cols=n_cols, n_rows=n_rows)
    plt.tight_layout()

    save_path = target_model_path.replace('.osim', '_moment_arms_comparison.png')
    plt.savefig(save_path)
    print(f"Moment arms comparison plot saved to: {save_path}")

    # make a spider plot for each coordinate with the moment arms of all muscles and save the figure
    n_coords = ref_model.getCoordinateSet().getSize()
    n_cols = 3
    n_rows = (n_coords + n_cols - 1) // n_cols
    fig, ax = plt.subplots(n_rows, n_cols, figsize=(n_cols * 6, n_rows * 6), subplot_kw=dict(projection='polar'))
    ax = ax.flatten() if n_coords > 1 else [ax]
    for i in range(n_coords):
        coord = ref_model.getCoordinateSet().get(i)
        coord_name = coord.getName()
        ax_coord = ax[i]
        ref_arms = [ref_moment_arms[muscle_name][coord_name] for muscle_name in ref_moment_arms.keys()]
        target_arms = [target_moment_arms[muscle_name][coord_name] for muscle_name in target_moment_arms.keys()]
        optimized_arms_values = [optimized_arms[muscle_name][coord_name] for muscle_name in optimized_arms.keys()]
        
        muscles = list(ref_moment_arms.keys())
        angles = np.linspace(0, 2 * np.pi, len(muscles), endpoint=False).tolist()
        angles += angles[:1]
        
        ax_coord.plot(angles, ref_arms + [ref_arms[0]], 'o-', label='Reference')
        ax_coord.plot(angles, target_arms + [target_arms[0]], 'x-', label='Target')
        ax_coord.plot(angles, optimized_arms_values + [optimized_arms_values[0]], 's-', label='Optimized')
        
        ax_coord.set_title(coord_name)
        ax_coord.set_xticks(angles[:-1])
        ax_coord.set_xticklabels(muscles, rotation=90, size=8)

    save_path = target_model_path.replace('.osim', '_moment_arms_comparison_spider.png')
    plt.savefig(save_path)
    print(f"Moment arms comparison spider plot saved to: {save_path}")

# c3d export functions
def export_c3d(c3d_file_path, emg_string_list=['emg'], create_folder=True):
    """
    Export a C3D file using the exportC3D module.

    Args:
        c3d_file_path (str): Path to the C3D file to export.
        emg_string_list (list): List of EMG channel prefixes to filter.
        create_folder (bool): Whether to create output folder if it doesn't exist.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Call the export function
        exportC3D.main(
            c3d_file_path,
            emg_string_list=emg_string_list,
            create_folder=create_folder
        )

        return True, f"C3D file exported successfully: {c3d_file_path}"

    except Exception as e:
        import traceback
        return False, f"Error exporting C3D file: {str(e)}\n{traceback.format_exc()}"


def convert_trc_os3_to_os4(trc_file_path: str = '', output_trc_file_path: str = ''):
    """
    Convert a .trc file from OpenSim 3 format to OpenSim 4 format.

    Parameters:
    trc_file_path (str): Path to the input .trc file in OpenSim 3 format.
    output_trc_file_path (str): Path to save the converted .trc file in OpenSim 4 format.
    """

    if not os.path.isfile(trc_file_path):
        trc_file_path = input("Enter the path to the .trc file to convert: ").strip('"')

    if not output_trc_file_path:
        output_trc_file_path = trc_file_path.replace('.trc', '_os4.trc')

    trc_df = utils.load_any_data_file(trc_file_path)  # This will raise an error if the file is not found or not a valid .trc file

    def load_trc_metadata_os3(trc_file_path):
        with open(trc_file_path, 'r') as file:
            lines = file.readlines()
        
        metadata = {}
        for i, line in enumerate(lines):
            parts = line.strip().split('\t')
            if parts[0] == "DataRate" and i + 1 < len(lines):
                values = lines[i + 1].strip().split('\t')
                keys = parts
                type_map = {'DataRate': float, 'CameraRate': float, 'NumFrames': int,
                            'NumMarkers': int, 'Units': str, 'OrigDataRate': float,
                            'DataStartFrame': int, 'OrigNumFrames': int}
                for key, val in zip(keys, values):
                    if key in type_map:
                        metadata[key] = type_map[key](val)
                break
        
        return metadata
    
    trc_metadata = load_trc_metadata_os3(trc_file_path)

    # remove columnn 'Frame#' if it exists
    if 'Frame#' in trc_df.columns:
        trc_df = trc_df.drop(columns=['Frame#'])

    utils.write_trc(trc_df,
                    trc_file=output_trc_file_path,
                    units=trc_metadata.get('Units'),
                    frame_rate=trc_metadata.get('DataRate'),
                    first_frame=trc_metadata.get('DataStartFrame'))

    print(f"Converted .trc file saved to: {output_trc_file_path}")

# Marker data and inverse kinematics functions
def add_joint_centers_to_trc(input_trc_path=None, output_trc_path=None, marker_map=None):
    """
    Add hip, knee, and ankle joint centre markers to a TRC file.

    New markers added (if computable):
      - RHJC, LHJC (hip joint centres)
      - RKJC, LKJC (knee joint centres)
      - RAJC, LAJC (ankle joint centres)

    Inputs:
        - input_trc_path: path to input TRC file 
        - output_trc_path: path to output TRC file (if None, will save in same directory with suffix '_with_JointCenters')
        - marker_map: dictionary specifying marker names for pelvis, knee pairs, ankle pairs, and existing hip markers.

    """
    if input_trc_path is None:
        input_trc_path = input("Enter path to input TRC file: ").strip('"')

    if output_trc_path is None:
        output_trc_path = input_trc_path.replace(".trc", "_with_JointCenters.trc")

    # -----------------------------
    # TRC read
    # -----------------------------
    with open(input_trc_path, "r") as f:
        lines = f.readlines()

    if len(lines) < 6:
        raise ValueError(f"Invalid TRC file: {input_trc_path}")

    header_1 = lines[0].rstrip("\n")
    header_keys = [x for x in lines[1].strip().split("\t") if x != ""]
    header_vals = [x for x in lines[2].strip().split("\t") if x != ""]

    marker_header = lines[3].rstrip("\n")
    coord_header = lines[4].rstrip("\n")

    df = pd.read_csv(input_trc_path, sep="\t", skiprows=5, header=None)

    marker_names = [m for m in marker_header.split("\t")[2:] if m.strip()]
    cols = ["Frame#", "Time"]
    for m in marker_names:
        cols.extend([f"{m}_X", f"{m}_Y", f"{m}_Z"])

    df = df.iloc[:, :len(cols)]
    df.columns = cols

    # -----------------------------
    # helpers
    # -----------------------------
    def has_marker(m):
        return all(c in df.columns for c in [f"{m}_X", f"{m}_Y", f"{m}_Z"])

    def get_marker_xyz(m):
        return df[[f"{m}_X", f"{m}_Y", f"{m}_Z"]].to_numpy(dtype=float)

    def set_marker_xyz(m, xyz):
        df[f"{m}_X"] = xyz[:, 0]
        df[f"{m}_Y"] = xyz[:, 1]
        df[f"{m}_Z"] = xyz[:, 2]

    def midpoint(m1, m2):
        return 0.5 * (get_marker_xyz(m1) + get_marker_xyz(m2))

    def first_valid_pair(pairs):
        for a, b in pairs:
            if has_marker(a) and has_marker(b):
                return a, b
        return None

    # -----------------------------
    # default marker map
    # -----------------------------
    default_map =  {
        "pelvis": {"LASI": "LASI", "RASI": "RASI", "LPSI": "LPSI", "RPSI": "RPSI"},
        "knee_r_pairs": [("RLFC", "RMFC"), ("RKNE", "RKNM"), ("RKNE", "RKNI"), ("RLK", "RMK")],
        "knee_l_pairs": [("LLFC", "LMFC"), ("LKNE", "LKNM"), ("LKNE", "LKNI"), ("LLK", "LMK")],
        "ankle_r_pairs": [("RANK", "RMED"), ("RANK", "RANM"), ("RANK", "RANKM"), ("RLA", "RMA")],
        "ankle_l_pairs": [("LANK", "LMED"), ("LANK", "LANM"), ("LANK", "LANKM"), ("LLA", "LMA")],
        "existing_hip_r": ["RHJC", "RHIP"],
        "existing_hip_l": ["LHJC", "LHIP"],
        }
    if marker_map is None:
        marker_map = default_map

    # -----------------------------
    # hip centres (Harrington-style pelvis-frame estimate)
    # -----------------------------
    rhjc_added = False
    lhjc_added = False

    # Use existing hip markers if present
    for m in marker_map["existing_hip_r"]:
        if has_marker(m):
            set_marker_xyz("RHJC", get_marker_xyz(m))
            rhjc_added = True
            break

    for m in marker_map["existing_hip_l"]:
        if has_marker(m):
            set_marker_xyz("LHJC", get_marker_xyz(m))
            lhjc_added = True
            break

    # If not available, estimate from pelvis landmarks
    pelvis = marker_map["pelvis"]
    if (not rhjc_added or not lhjc_added) and all(has_marker(pelvis[k]) for k in ["LASI", "RASI", "LPSI", "RPSI"]):
        LASI = get_marker_xyz(pelvis["LASI"])
        RASI = get_marker_xyz(pelvis["RASI"])
        LPSI = get_marker_xyz(pelvis["LPSI"])
        RPSI = get_marker_xyz(pelvis["RPSI"])

        mid_asis = 0.5 * (LASI + RASI)
        mid_psi = 0.5 * (LPSI + RPSI)

        # pelvis axes
        z_axis = RASI - LASI  # left -> right
        z_axis /= np.linalg.norm(z_axis, axis=1, keepdims=True)

        x_axis = mid_asis - mid_psi  # posterior -> anterior
        x_axis /= np.linalg.norm(x_axis, axis=1, keepdims=True)

        y_axis = np.cross(z_axis, x_axis)  # superior
        y_axis /= np.linalg.norm(y_axis, axis=1, keepdims=True)

        # re-orthogonalize x
        x_axis = np.cross(y_axis, z_axis)
        x_axis /= np.linalg.norm(x_axis, axis=1, keepdims=True)

        pelvis_width = np.linalg.norm(RASI - LASI, axis=1)   # mm
        pelvis_depth = np.linalg.norm(mid_asis - mid_psi, axis=1)  # mm

        # Harrington-like offsets (mm)
        x_post = -0.24 * pelvis_depth - 9.9
        y_inf = -0.30 * pelvis_width - 10.9
        z_lat = 0.33 * pelvis_width + 7.3

        # right(+z), left(-z)
        RHJC = mid_asis + x_axis * x_post[:, None] + y_axis * y_inf[:, None] + z_axis * z_lat[:, None]
        LHJC = mid_asis + x_axis * x_post[:, None] + y_axis * y_inf[:, None] - z_axis * z_lat[:, None]

        if not rhjc_added:
            set_marker_xyz("RHJC", RHJC)
        if not lhjc_added:
            set_marker_xyz("LHJC", LHJC)

    # -----------------------------
    # knee centres
    # -----------------------------
#     breakpoint()
    pair = first_valid_pair(marker_map["knee_r_pairs"])
    if pair is not None:
        set_marker_xyz("RKJC", midpoint(*pair))

    pair = first_valid_pair(marker_map["knee_l_pairs"])
    if pair is not None:
        set_marker_xyz("LKJC", midpoint(*pair))

    # -----------------------------
    # ankle centres
    # -----------------------------
    pair = first_valid_pair(marker_map["ankle_r_pairs"])
    if pair is not None:
        set_marker_xyz("RAJC", midpoint(*pair))

    pair = first_valid_pair(marker_map["ankle_l_pairs"])
    if pair is not None:
        set_marker_xyz("LAJC", midpoint(*pair))

    # -----------------------------
    # TRC write
    # -----------------------------
    out_marker_names = [c[:-2] for c in df.columns if c.endswith("_X")]
    num_markers = len(out_marker_names)

    # update header values
    header_map = dict(zip(header_keys, header_vals))
    if "NumFrames" in header_map:
        header_map["NumFrames"] = str(len(df))
    if "NumMarkers" in header_map:
        header_map["NumMarkers"] = str(num_markers)

    updated_vals = [header_map.get(k, "") for k in header_keys]
    line2 = "\t".join(header_keys) + "\n"
    line3 = "\t".join(updated_vals) + "\n"

    # marker + coord header
    line4_parts = ["Frame#", "Time"]
    for m in out_marker_names:
        line4_parts.extend([m, "", ""])
    line4 = "\t".join(line4_parts).rstrip() + "\n"

    line5_parts = ["", ""]
    for i in range(1, num_markers + 1):
        line5_parts.extend([f"X{i}", f"Y{i}", f"Z{i}"])
    line5 = "\t".join(line5_parts).rstrip() + "\n"

    with open(output_trc_path, "w") as f:
        f.write(header_1 + "\n")
        f.write(line2)
        f.write(line3)
        f.write(line4)
        f.write(line5)
        df.to_csv(f, sep="\t", index=False, header=False, float_format="%.6f", lineterminator="\n")

    print(f"Saved TRC with joint centres: {output_trc_path}")

def validate_markers_used(osim_modelPath, ikTool, markers_path):

    def get_all_marker_parent_frames(model_path):
        model = _quiet_model(model_path)
        model.initSystem()

        marker_set = model.getMarkerSet()
        result = {}
        for i in range(marker_set.getSize()):
            marker = marker_set.get(i)
            result[marker.getName()] = marker.getParentFrameName()
        return result

    model =  _quiet_model(osim_modelPath)
    markerSet = model.get_MarkerSet() 
    markers_model = [marker.getName() for marker in markerSet]

    task_set_template = ikTool.upd_IKTaskSet()
    markers_df = utils.load_trc(markers_path)
    markers_trc = markers_df.columns.get_level_values(0).unique().tolist()
    
    for marker_name in markers_model:
        if marker_name not in markers_trc:
            print(f"Warning: Marker '{marker_name}' not found in TRC file.")

    markers_in_task = [task.getName() for task in task_set_template if isinstance(task, osim.IKMarkerTask)]
    markers_parent_frames = get_all_marker_parent_frames(osim_modelPath)

    # Marker IK weights are keyed by the parent BODY (e.g. 'pelvis', 'femur_r',
    # 'calcn_l') in BatchSettings.marker_weights. NOTE: the value lives on the
    # BatchSettings *class*, not the settings module — `settings.marker_weights`
    # raised AttributeError and silently forced every weight to 1.0. Markers
    # whose body isn't listed default to 1.0.
    try:
        _marker_weights = dict(getattr(settings.BatchSettings, 'marker_weights', {}) or {})
    except Exception:
        _marker_weights = {}

    # Markers to exclude from IK entirely (e.g. belt/noise markers BL, BR). Their
    # IK task is disabled so they don't pull the fit. Listed in
    # BatchSettings.markers_to_skip; matched case-insensitively.
    try:
        _skip = {str(s).upper() for s in getattr(settings.BatchSettings, 'markers_to_skip', []) or []}
    except Exception:
        _skip = set()

    def _weight_for(_mname):
        _pf = (markers_parent_frames.get(_mname) or "").replace("/bodyset/", "")
        return float(_marker_weights.get(_pf, 1.0)), _pf

    for marker_name in markers_model:
        _w, _pf = _weight_for(marker_name)
        _skipped = marker_name.upper() in _skip
        _in_trc = (marker_name in markers_trc) and not _skipped
        if marker_name in markers_in_task:
            task = task_set_template.get(marker_name)
            task.setWeight(_w)                 # apply weight to template markers too
            task.setApply(_in_trc)
            if _skipped:
                print(f"Marker '{marker_name}' SKIPPED (markers_to_skip). Disabling task.")
            elif not _in_trc:
                print(f"Marker '{marker_name}' not found in TRC file. Disabling task.")
            else:
                print(f"Marker '{marker_name}' weight={_w} (body '{_pf}').")
        else:
            newTask = osim.IKMarkerTask()
            newTask.setName(marker_name)
            newTask.setWeight(_w)
            newTask.setApply(_in_trc)
            if _skipped:
                print(f"Marker '{marker_name}' SKIPPED (markers_to_skip). Disabling task.")
            elif _in_trc:
                print(f"Marker '{marker_name}' added with weight={_w} (body '{_pf}').")
            else:
                print(f"Marker '{marker_name}' in Model not found in TRC file. Disabling task.")
            task_set_template.adoptAndAppend(newTask)


    
    return ikTool

def compare_marker_locations(marker_experimental_path=None, marker_virtual_path=None):
    """
    Calculates the root mean square error between experimental and virtual markers.

    Args:
        marker_experimental_path (str, optional): Path to the experimental .trc file.
        marker_virtual_path (str, optional): Path to the virtual .sto markers file.
    """

    # Select the trials if needed
    if not marker_experimental_path:
        marker_experimental_path = input("Enter path to experimental .trc markers file: ").strip('"')
        if not marker_experimental_path: return # User cancelled

    if not marker_virtual_path:
        marker_virtual_path = input("Enter path to virtual .sto markers file: ").strip('"')
        if not marker_virtual_path: return # User cancelled

    # Load marker data
    virtual_markers_df = utils.load_sto(marker_virtual_path)
    experimental_markers_df = utils.load_trc(marker_experimental_path,
                                combine_headers=True)

    exp_marker_names = experimental_markers_df.columns.get_level_values(0).unique().tolist()
    
    # Find frames to plot in the experimental data
    time = virtual_markers_df['time']
    
    # Find the closest indices in experimental time to the start and end of virtual time
    exp_time = experimental_markers_df['time']
    initial_index = (exp_time - time.iloc[0]).abs().idxmin()
    final_index = (exp_time - time.iloc[-1]).abs().idxmin()

    distances = pd.DataFrame({'time': time.values})
    
    # Marker errors describe IK quality -> write them next to the IK outputs,
    # i.e. the same folder as the virtual/model marker locations file
    # (<sim_trial>/external_biomechanics/). Deriving the folder from the
    # experimental TRC (marker_experimental_path) is wrong: that file lives in
    # the experimental data tree, so the errors ended up there.
    output_dir = os.path.dirname(os.path.abspath(marker_virtual_path))
    _extbio = os.path.join(os.path.dirname(output_dir), "external_biomechanics")
    if os.path.basename(output_dir) != "external_biomechanics" and os.path.isdir(_extbio):
        output_dir = _extbio
    mean_errors_filename = os.path.join(output_dir, '_ik_marker_errors_mean.txt')

    print('Calculating marker errors for all markers...')
    with open(mean_errors_filename, 'w') as f_mean_errors:
        f_mean_errors.write('mean errors for each marker (m)\n\n')

        for marker_name in exp_marker_names:

            if 'time' in marker_name.lower() or 'frame' in marker_name.lower():
                continue

            try:
                marker_name = marker_name.split('_')[0]
                exp_cols = [col for col in exp_marker_names if col.split('_')[0] == marker_name]
                virtual_cols = [col for col in virtual_markers_df.columns if col.split('_')[0] == marker_name]

                if not exp_cols or not virtual_cols:
                    continue

                # Get experimental data for the current time range and convert mm to m
                exp_slice = experimental_markers_df.iloc[initial_index:final_index + 1]
                x1 = pd.to_numeric(exp_slice[exp_cols[0]], errors='coerce').values / 1000.0
                y1 = pd.to_numeric(exp_slice[exp_cols[1]], errors='coerce').values / 1000.0
                z1 = pd.to_numeric(exp_slice[exp_cols[2]], errors='coerce').values / 1000.0

                # Get virtual data
                x2 = virtual_markers_df[virtual_cols[0]].values
                y2 = virtual_markers_df[virtual_cols[1]].values
                z2 = virtual_markers_df[virtual_cols[2]].values
                
                # Ensure arrays are the same length by trimming the longer one
                min_len = min(len(x1), len(x2))
                x1, y1, z1 = x1[:min_len], y1[:min_len], z1[:min_len]
                x2, y2, z2 = x2[:min_len], y2[:min_len], z2[:min_len]
                
                # Calculate the 3D distance
                dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
                distances[marker_name] = pd.Series(dist)

                # Write mean error to file
                mean_error_text = f'{marker_name} = {np.mean(dist):.4f} m\n'
                f_mean_errors.write(mean_error_text)

            except (KeyError, IndexError) as e:
                print(f"Could not process marker '{marker_name}'. It might be missing in one of the files. Error: {e}")

    # Write all distance data to a .sto file
    all_errors_filename = os.path.join(output_dir, '_ik_marker_errors_all.sto')
    utils.write_sto_file(distances.dropna(axis=1, how='all'), all_errors_filename)
    print(f"Mean errors saved to: {mean_errors_filename}")
    print(f"All error data saved to: {all_errors_filename}")
    
    # plot marker errors over time    
    plt.figure(figsize=(12, 6))
    for marker_name in distances.columns:
        if marker_name != 'time':
            plt.plot(distances['time'], distances[marker_name], label=marker_name)
    
    # plot mean error as a dashed line
    mean_errors = distances.drop(columns='time').mean(axis=1)
    plt.plot(distances['time'], mean_errors, label='Mean Error', linestyle='--', color='black')
    
    plt.xlabel('Time (s)')
    plt.ylabel('Marker Error (m)')
    plt.title('Marker Errors Over Time')
    plt.legend()
    plt.grid()
    
    # save fig
    plt.savefig(os.path.join(output_dir, '_ik_marker_errors_plot.png'))
    plt.close()
    print(f"Marker errors plot saved to: {os.path.join(output_dir, '_ik_marker_errors_plot.png')}")

def assign_grfs_to_feet(grf_mot_path=None, marker_trc_path=None,
                        right_foot_markers=None, left_foot_markers=None,
                        right_foot_body='calcn_r', left_foot_body='calcn_l',
                        vert_force_threshold=10.0, max_cop_foot_dist_mm=None):
    """
    Detect force plates from a GRF .mot file and assign each to left/right foot.

    Loads the .mot file, auto-detects force-plate columns, then assigns each
    active plate to a foot by comparing median CoP Y with mean foot-marker Y
    from the TRC file.

    Parameters
    ----------
    grf_mot_path : str
        Path to the GRF .mot file.
    marker_trc_path : str, optional
        Path to the marker TRC file for anatomical assignment.
        If not provided, plates are sorted by CoP Y and alternated R/L.
    right_foot_markers : list of str, optional
        Marker names for right foot. Defaults to common heel/toe names.
    left_foot_markers : list of str, optional
        Marker names for left foot. Defaults to common heel/toe names.
    right_foot_body : str
        OpenSim body name for right foot (default 'calcn_r').
    left_foot_body : str
        OpenSim body name for left foot (default 'calcn_l').
    vert_force_threshold : float
        Minimum |Fy| in N to consider a plate active (default 10 N).

    Returns
    -------
    dict
        {plate_num_str: body_name}  e.g. {'4': 'calcn_r', '5': 'calcn_l'}
    """
    import re

    if not grf_mot_path:
        grf_mot_path = input('Paste the grf mot file path: ').strip('"')

    if not marker_trc_path:
        marker_trc_path = input('Paste the markers trc file path: ').strip('"')

    DEFAULT_RIGHT = ['RHEE', 'RTOE', 'RANK', 'RANM', 'RMED', 'RMT2', 'RCAL', 'RKNE']
    DEFAULT_LEFT  = ['LHEE', 'LTOE', 'LANK', 'LANM', 'LMED', 'LMT2', 'LCAL', 'LKNE']
    right_markers = list(right_foot_markers or DEFAULT_RIGHT)
    left_markers  = list(left_foot_markers  or DEFAULT_LEFT)

    # ------------------------------------------------------------------ #
    # 1. Load GRF file and detect plates from column names
    # ------------------------------------------------------------------ #
    grf_df = utils.load_sto(grf_mot_path)
    cols = grf_df.columns.tolist()

    plates = {}
    for col in cols:
        col_str = str(col)
        if col_str.lower() == 'time':
            continue
        nums = re.findall(r'\d+', col_str)
        if not nums:
            continue
        pnum = nums[0]
        plates.setdefault(pnum, {})
        if re.search(r'vx$', col_str, re.IGNORECASE) and 'force' in col_str.lower():
            plates[pnum]['force_id'] = col_str[:-1]        # strip trailing 'x'
        elif re.search(r'px$', col_str, re.IGNORECASE) and 'force' in col_str.lower():
            plates[pnum]['point_id'] = col_str[:-1]        # strip trailing 'x'
        elif re.search(r'x$', col_str, re.IGNORECASE) and 'torque' in col_str.lower():
            plates[pnum]['torque_id'] = col_str[:-1]

    valid = {k: v for k, v in plates.items()
             if 'force_id' in v and 'point_id' in v}
    if not valid:
        raise ValueError(f"No force-plate columns detected in {grf_mot_path}")

    print(f"Detected {len(valid)} force plate(s): {sorted(valid.keys(), key=int)}")

    # ------------------------------------------------------------------ #
    # 2. Median CoP Y for each active plate
    # ------------------------------------------------------------------ #
    def find_col(name):
        nl = name.lower()
        for c in grf_df.columns:
            if str(c).lower() == nl:
                return c
        return None

    # The plate->foot assignment must compare the CoP and the foot markers on the
    # SAME (medio-lateral) axis. In the OpenSim GRF frame Y is VERTICAL, so CoP-Y
    # is ~0 at the ground and cannot separate left from right — every plate then
    # collapses to the nearest foot. Use the lateral axis (BatchSettings.
    # trc_lateral_axis, default Z), matching how the foot markers are read below.
    _lateral = getattr(getattr(settings, 'BatchSettings', None),
                       'trc_lateral_axis', 'Z').upper()
    cop_y_per_plate = {}
    for pnum, ids in valid.items():
        fy_col = find_col(ids['force_id'] + 'y')                 # vertical force (active-plate test)
        py_col = find_col(ids['point_id'] + _lateral.lower())    # lateral CoP (L/R assignment)
        if fy_col is None or py_col is None:
            print(f"  Plate {pnum}: Fy or CoP-Y column missing — skipping")
            continue
        fy = pd.to_numeric(grf_df[fy_col], errors='coerce')
        py = pd.to_numeric(grf_df[py_col], errors='coerce')
        active = fy.abs() > vert_force_threshold
        if not active.any():
            print(f"  Plate {pnum}: no active frames (|Fy| > {vert_force_threshold} N) — skipping")
            continue
        cop_y_per_plate[pnum] = float(py[active].median())

    if not cop_y_per_plate:
        print("  Warning: no active plates — returning empty assignment")
        return {}

    # ------------------------------------------------------------------ #
    # 3. Auto-detect CoP units  (metres → mm)
    # ------------------------------------------------------------------ #
    max_cop = max(abs(v) for v in cop_y_per_plate.values())
    if max_cop < 10.0:
        cop_y_per_plate = {k: v * 1000.0 for k, v in cop_y_per_plate.items()}
        print(f"  CoP units: metres detected → converted to mm")
    else:
        print(f"  CoP units: mm (max |CoP Y| = {max_cop:.1f} mm)")

    for pnum, cy in sorted(cop_y_per_plate.items(), key=lambda x: int(x[0])):
        print(f"  Plate {pnum}: median CoP Y = {cy:.1f} mm")

    # ------------------------------------------------------------------ #
    # 4. Mean foot-marker lateral position from TRC  (mm)
    # ------------------------------------------------------------------ #
    # Which TRC axis separates left from right foot comes from settings.
    # After exportC3D (OpenSim frame) this is Z; in raw lab frame it is X.
    _lateral = getattr(
        getattr(settings, 'BatchSettings', None), 'trc_lateral_axis', 'Z'
    ).upper()

    r_foot_y = None
    l_foot_y = None

    if marker_trc_path and os.path.exists(str(marker_trc_path)):
        try:
            trc_df = utils.load_trc(marker_trc_path)

            # Flatten MultiIndex → "MARKER_COORD" lookup.
            # TRC sub-headers are "X1","Y1","Z1" (numbered) so use
            # startswith — e.g. "RHEE_Z" matches "RHEE_Z1", "RHEE_Z2", etc.
            if isinstance(trc_df.columns, pd.MultiIndex):
                _pairs = [(f"{str(m).upper()}_{str(c).upper()}", (m, c))
                          for m, c in trc_df.columns]
                def get_y(name):
                    prefix = f"{name.upper()}_{_lateral}"
                    for _k, _col in _pairs:
                        if _k == prefix or _k.startswith(prefix):
                            return pd.to_numeric(trc_df[_col], errors='coerce').dropna()
                    return pd.Series(dtype=float)
            else:
                _flat_cols = [(str(c).upper(), c) for c in trc_df.columns]
                def get_y(name):
                    prefix = f"{name.upper()}_{_lateral}"
                    for _k, _col in _flat_cols:
                        if _k == prefix or _k.startswith(prefix):
                            return pd.to_numeric(trc_df[_col], errors='coerce').dropna()
                    return pd.Series(dtype=float)

            def mean_foot_y(names, label):
                vals, found = [], []
                for n in names:
                    s = get_y(n)
                    if not s.empty:
                        vals.append(float(s.mean()))
                        found.append(n)
                if vals:
                    print(f"  {label} markers found: {found}  →  mean Y = {np.mean(vals):.1f} mm")
                    return float(np.mean(vals))
                print(f"  {label} markers not found in TRC")
                return None

            r_foot_y = mean_foot_y(right_markers, 'Right foot')
            l_foot_y = mean_foot_y(left_markers,  'Left  foot')

        except Exception as exc:
            print(f"  Warning: could not load TRC — {exc}")

    # ------------------------------------------------------------------ #
    # 5. Assign each plate to a foot
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # 5. TEMPORAL, horizontal-plane assignment.
    #    For each plate, over ONLY the frames it is loaded, pick the foot whose
    #    markers are closest to the CoP in the (X,Z) horizontal plane (Y is
    #    vertical in the OpenSim GRF frame). Robust to walkway orientation and
    #    straight-line walking — does NOT use session-mean foot positions.
    # ------------------------------------------------------------------ #
    _tcol = find_col('time')
    _gt = pd.to_numeric(grf_df[_tcol], errors='coerce').values if _tcol is not None else None

    _trc = None
    if marker_trc_path and os.path.exists(str(marker_trc_path)):
        try:
            _trc = utils.load_trc(marker_trc_path)
        except Exception as _e:
            print(f"  Warning: could not load TRC for assignment — {_e}")

    def _series(pref):
        """First TRC column whose flattened NAME_AXIS starts with pref (upper)."""
        if _trc is None:
            return None
        if isinstance(_trc.columns, pd.MultiIndex):
            for m, c in _trc.columns:
                if f"{str(m).upper()}_{str(c).upper()}".startswith(pref):
                    return pd.to_numeric(_trc[(m, c)], errors='coerce').values
        else:
            for c in _trc.columns:
                if str(c).upper().startswith(pref):
                    return pd.to_numeric(_trc[c], errors='coerce').values
        return None

    _tt = _series("TIME")

    def _foot_xz(markers, t0, t1):
        xs, zs = [], []
        for m in markers:
            for axis, acc in (('X', xs), ('Z', zs)):
                v = _series(f"{m.upper()}_{axis}")
                if v is None:
                    continue
                if _tt is not None and np.isfinite(_tt).any():
                    sel = (_tt >= t0) & (_tt <= t1) & np.isfinite(v)
                    if sel.any():
                        acc.append(float(np.nanmedian(v[sel])))
                        continue
                acc.append(float(np.nanmedian(v)))
        return (float(np.mean(xs)) if xs else None,
                float(np.mean(zs)) if zs else None)

    # A plate whose CoP sits farther than this (mm) from BOTH foot-marker centroids
    # is not acting on a foot (e.g. a loaded barbell resting on a plate during a
    # deadlift) and is dropped so it never enters GRF.xml. None/0 disables the check.
    if max_cop_foot_dist_mm is None:
        max_cop_foot_dist_mm = getattr(getattr(settings, 'BatchSettings', None),
                                       'grf_max_cop_foot_dist_mm', 300.0)

    plate_to_body = {}
    print("  Assignment (temporal CoP<->foot distance, horizontal plane):")
    for pnum in sorted(valid.keys(), key=int):
        ids = valid[pnum]
        fy = pd.to_numeric(grf_df[find_col(ids['force_id'] + 'y')], errors='coerce').values
        pxc = find_col(ids['point_id'] + 'x')
        pzc = find_col(ids['point_id'] + 'z')
        active = np.abs(fy) > vert_force_threshold
        if not active.any():
            # Empty/unused plate (never loaded above threshold) — EXCLUDE entirely.
            # Do NOT parity-assign it to a foot: an ExternalForce with ~0 N and an
            # undefined CoP (M/Fz -> 0/0) pollutes ID/JRA with a phantom load.
            print(f"    Plate {pnum}: no active frames (|Fy| <= {vert_force_threshold:.0f} N) "
                  f"— EXCLUDED (empty plate)")
            continue
        if pxc is None or pzc is None:
            body = right_foot_body if int(pnum) % 2 == 1 else left_foot_body
            plate_to_body[pnum] = body
            print(f"    Plate {pnum}: active but no CoP columns -> parity fallback {body}")
            continue
        px = pd.to_numeric(grf_df[pxc], errors='coerce').values
        pz = pd.to_numeric(grf_df[pzc], errors='coerce').values
        cx = float(np.nanmedian(px[active]))
        cz = float(np.nanmedian(pz[active]))
        if max(abs(cx), abs(cz)) < 10.0:          # metres -> mm (match TRC)
            cx *= 1000.0; cz *= 1000.0
        if _gt is not None:
            ta = _gt[active]
            t0, t1 = float(np.nanmin(ta)), float(np.nanmax(ta))
        else:
            t0, t1 = -np.inf, np.inf
        rx, rz = _foot_xz(right_markers, t0, t1)
        lx, lz = _foot_xz(left_markers, t0, t1)
        # FAIS patch 2026-08-12: decide LEFT/RIGHT on the LATERAL axis ALONE.
        # The CoP sits mid-foot, ~150 mm forward of the heel marker, so the
        # progression-axis error is systematically LARGER than the real left/right
        # separation (~50-100 mm). Scoring on the horizontal plane let that offset
        # dominate and collapsed every plate onto one foot: Run_baselineA1 put all
        # three plates on calcn_l, so the right leg had kinematics but no GRF and
        # therefore no ankle moment. The horizontal distance is still used, but
        # only for the "is this a foot at all" gate below.
        _lat = getattr(getattr(settings, 'BatchSettings', None),
                       'trc_lateral_axis', 'Z').upper()
        _c_lat, _r_lat, _l_lat = ((cx, rx, lx) if _lat == 'X' else (cz, rz, lz))
        dR = abs(_c_lat - _r_lat) if _r_lat is not None else np.inf
        dL = abs(_c_lat - _l_lat) if _l_lat is not None else np.inf
        _hR = np.hypot(cx - rx, cz - rz) if rx is not None else np.inf
        _hL = np.hypot(cx - lx, cz - lz) if lx is not None else np.inf
        print(f"    Plate {pnum}: lateral({_lat}) CoP={_c_lat:.0f} "
              f"R={_r_lat if _r_lat is None else round(_r_lat)} "
              f"L={_l_lat if _l_lat is None else round(_l_lat)} "
              f"-> dR={dR:.0f} dL={dL:.0f} mm")
        if not np.isfinite(dR) and not np.isfinite(dL):
            body = right_foot_body if int(pnum) % 2 == 1 else left_foot_body
        else:
            body = right_foot_body if dR <= dL else left_foot_body
        # Reject plates whose CoP is too far from BOTH foot centroids — not on a
        # foot (e.g. a loaded barbell on the plate). Excluded from GRF.xml.
        _dmin = min([d for d in (dR, dL) if np.isfinite(d)], default=np.inf)
        if max_cop_foot_dist_mm and np.isfinite(_dmin) and _dmin > float(max_cop_foot_dist_mm):
            print(f"    Plate {pnum}: CoP=({cx:.0f},{cz:.0f})  dR={dR:.0f}  dL={dL:.0f}  "
                  f"-> nearest foot {_dmin:.0f} mm > {float(max_cop_foot_dist_mm):.0f} mm "
                  f"threshold — NOT on a foot; EXCLUDED")
            continue
        side = 'R' if body == right_foot_body else 'L'
        plate_to_body[pnum] = body
        print(f"    Plate {pnum}: CoP=({cx:.0f},{cz:.0f})  dR={dR:.0f}  dL={dL:.0f}  ->  {side} ({body})")

    return plate_to_body


def create_grf_xml(grf_mot_path=None, output_xml_path=None,
                   marker_trc_path=None,
                   right_foot_markers=None, left_foot_markers=None,
                   right_foot_body='calcn_r', left_foot_body='calcn_l',
                   vert_force_threshold=10.0,
                   max_cop_foot_dist_mm=None,
                   filter_cutoff=6,
                   datafile=None):
    """
    Create a working OpenSim ExternalLoads XML (GRF.xml) from a GRF .mot file.

    Automatically detects force-plate column names, assigns each plate to the
    left or right foot using marker TRC data or COP Z-position heuristic, and
    writes a correctly-formatted GRF.xml.

    Parameters
    ----------
    grf_mot_path : str
        Path to the GRF .mot file containing force plate data.
    output_xml_path : str, optional
        Output XML path. Defaults to GRF.xml next to the .mot file.
    marker_trc_path : str, optional
        Marker TRC file used to assign plates to feet by comparing COP
        positions to foot marker Z-positions.
    right_foot_markers : list of str, optional
        Marker names for the right foot (e.g. ['RHEE', 'RTOE']).
        If None, common names are tried automatically.
    left_foot_markers : list of str, optional
        Marker names for the left foot (e.g. ['LHEE', 'LTOE']).
        If None, common names are tried automatically.
    right_foot_body : str
        OpenSim body for the right foot (default 'calcn_r').
    left_foot_body : str
        OpenSim body for the left foot (default 'calcn_l').
    vert_force_threshold : float
        Minimum vertical force (N) to consider a plate active (default 10.0).
    filter_cutoff : float
        Low-pass filter cut-off for load kinematics in the XML (default 6 Hz).
    datafile : str, optional
        Value for the <datafile> tag. Defaults to the basename of grf_mot_path.
    """
    import re
    import xml.etree.ElementTree as ET

    if not os.path.exists(grf_mot_path):
        raise FileNotFoundError(f"GRF .mot file not found: {grf_mot_path}")

    if output_xml_path is None:
        output_xml_path = os.path.join(os.path.dirname(grf_mot_path), 'GRF.xml')

    if datafile is None:
        datafile = os.path.basename(grf_mot_path)

    # ------------------------------------------------------------------ #
    # 1. Load .mot and detect column name patterns per force plate
    # ------------------------------------------------------------------ #
    grf_df = utils.load_sto(grf_mot_path)
    cols = grf_df.columns.tolist()

    # plates[plate_number] = {'force_id': ..., 'point_id': ..., 'torque_id': ...}
    plates = {}

    for col in cols:
        if col.lower() == 'time':
            continue

        # Force columns: end in vx/vy/vz (e.g. ground_force3_vx)
        if re.search(r'vx$', col, re.IGNORECASE) and 'force' in col.lower():
            identifier = col[:-1]   # strip trailing 'x' → e.g. 'ground_force3_v'
            nums = re.findall(r'\d+', col)
            if nums:
                plates.setdefault(nums[0], {})['force_id'] = identifier
            continue

        # Point columns: end in px/py/pz (e.g. ground_force3_px)
        if re.search(r'px$', col, re.IGNORECASE) and 'force' in col.lower():
            identifier = col[:-1]   # → e.g. 'ground_force3_p'
            nums = re.findall(r'\d+', col)
            if nums:
                plates.setdefault(nums[0], {})['point_id'] = identifier
            continue

        # Torque columns: contain 'torque' and end in x (e.g. ground_torque3_x or ground_torque3_mx)
        if re.search(r'x$', col, re.IGNORECASE) and 'torque' in col.lower():
            identifier = col[:-1]   # → e.g. 'ground_torque3_' or 'ground_torque3_m'
            nums = re.findall(r'\d+', col)
            if nums:
                plates.setdefault(nums[0], {})['torque_id'] = identifier

    if not plates:
        raise ValueError("No force plate columns detected in the .mot file. "
                         "Expected columns like 'ground_force1_vx', 'ground_force1_px', etc.")

    print(f"Detected force plates: {sorted(plates.keys(), key=lambda x: int(x))}")
    for n, ids in sorted(plates.items(), key=lambda x: int(x[0])):
        print(f"  Plate {n}: force_id='{ids.get('force_id','')}', "
              f"point_id='{ids.get('point_id','')}', torque_id='{ids.get('torque_id','')}'")

    # ------------------------------------------------------------------ #
    # 2. Assign each plate to a foot
    # ------------------------------------------------------------------ #
    print("\nAssigning force plates to feet...")
    plate_to_body = assign_grfs_to_feet(
        grf_mot_path=grf_mot_path,
        marker_trc_path=marker_trc_path,
        right_foot_markers=right_foot_markers,
        left_foot_markers=left_foot_markers,
        right_foot_body=right_foot_body,
        left_foot_body=left_foot_body,
        vert_force_threshold=vert_force_threshold,
        max_cop_foot_dist_mm=max_cop_foot_dist_mm,
    )

    # ------------------------------------------------------------------ #
    # 3. Build XML tree
    # ------------------------------------------------------------------ #
    root = ET.Element('OpenSimDocument')
    root.set('Version', '40000')

    ext_loads = ET.SubElement(root, 'ExternalLoads')
    ext_loads.set('name', 'externalloads')
    objects_el = ET.SubElement(ext_loads, 'objects')

    for plate_num in sorted(plates.keys(), key=lambda x: int(x)):
        ids = plates[plate_num]
        if 'force_id' not in ids or 'point_id' not in ids:
            continue

        # Only include plates that are actually in plate_to_body (have significant force data)
        if plate_num not in plate_to_body:
            continue

        body = plate_to_body[plate_num]
        side = 'r' if body == right_foot_body else 'l'
        force_name = f'grf_{side}_{plate_num}'

        ef = ET.SubElement(objects_el, 'ExternalForce')
        ef.set('name', force_name)
        ET.SubElement(ef, 'applied_to_body').text          = body
        ET.SubElement(ef, 'force_expressed_in_body').text  = 'ground'
        ET.SubElement(ef, 'point_expressed_in_body').text  = 'ground'
        ET.SubElement(ef, 'force_identifier').text         = ids['force_id']
        ET.SubElement(ef, 'point_identifier').text         = ids['point_id']
        ET.SubElement(ef, 'torque_identifier').text        = ids.get('torque_id', '')
        ET.SubElement(ef, 'data_source_name').text         = ''

    ET.SubElement(ext_loads, 'groups')
    ET.SubElement(ext_loads, 'datafile').text = datafile
    ET.SubElement(ext_loads, 'external_loads_model_kinematics_file').text = ''
    ET.SubElement(ext_loads, 'lowpass_cutoff_frequency_for_load_kinematics').text = str(filter_cutoff)

    # ------------------------------------------------------------------ #
    # 4. Save using utils pretty-printer
    # ------------------------------------------------------------------ #
    tree = ET.ElementTree(root)
    utils.save_pretty_xml(tree, output_xml_path)

    print(f"\nGRF XML saved to: {os.path.abspath(output_xml_path)}")
    print(f"Plates: {sorted(plates.keys(), key=lambda x: int(x))}  |  Data file: {datafile}")
    return os.path.abspath(output_xml_path)

def convert_mot_to_sto(mot_file_path = None):
    """
    Convert a .mot file to a .sto file.
    """
    if not mot_file_path:
        mot_file_path = input("Enter path to .mot file: ").strip('"')
    
    sto_file_path = mot_file_path.replace('.mot', '.sto')
    
    if not os.path.exists(mot_file_path):
        print(f".mot file not found: {mot_file_path}")
        return

    if os.path.exists(sto_file_path):
        print(f".sto file already exists: {sto_file_path}")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        sto_file_path = mot_file_path.replace('.mot', f'_{timestamp}.sto')
    
    mot_data = utils.load_any_data_file(mot_file_path)
    utils.write_sto_file(mot_data, sto_file_path)
    
    print(f"Converted {mot_file_path} to {sto_file_path}")

    return sto_file_path

def scale_model_from_xml(setup_xml_path, generic_model_path, static_trc_path, scaled_model_path, mass=None):
    """
    Scale an OpenSim model using a pre-existing ScaleTool setup XML (preserving its
    MeasurementSet, MarkerPlacer IK tasks, etc.) while overriding the key file paths
    and optionally the subject mass.

    Args:
        setup_xml_path (str): Path to the ScaleTool setup XML file.
        generic_model_path (str): Path to the unscaled generic .osim model.
        static_trc_path (str): Path to the static trial TRC file.
        scaled_model_path (str): Absolute path for the output scaled .osim model.
        mass (float, optional): Subject mass in kg. Defaults to model total mass.
    """
    scale_tool = osim.ScaleTool(setup_xml_path)

    base_folder = os.path.dirname(setup_xml_path)

    if mass is not None:
        scale_tool.setSubjectMass(mass)

    # GenericModelMaker
    scale_tool.getGenericModelMaker().setModelFileName(generic_model_path)

    # ModelScaler
    model_scaler = scale_tool.getModelScaler()
    model_scaler.setApply(True)
    model_scaler.setMarkerFileName(os.path.basename(static_trc_path))
    model_scaler.setOutputModelFileName(os.path.relpath(scaled_model_path, base_folder))
    model_scaler.setOutputScaleFileName('scale_set.xml')

    # MarkerPlacer
    marker_placer = scale_tool.getMarkerPlacer()
    marker_placer.setApply(True)
    marker_placer.setMarkerFileName(os.path.basename(static_trc_path))
    marker_placer.setOutputModelFileName(os.path.relpath(scaled_model_path, base_folder))
    marker_placer.setOutputMarkerFileName('static_output.trc')

    # print scale tool setup xml
    os.chdir(base_folder)
    scale_tool.printToXML(os.path.join(base_folder, 'setup_scale.xml'))
    print(f"Modified ScaleTool setup saved to: {os.path.join(os.path.dirname(scaled_model_path), 'setup_scale.xml')}")

    output = scale_tool.run()
    
    if not output:
        print(f"Scaled model saved to: {scaled_model_path}")
    else:
        print("Error: Scaling failed. Check the ScaleTool setup and input files.")

    return scale_tool

def _sanitize_markerset_xml(src_path, skip_names, out_dir):
    """Write a copy of an OpenSim marker-set XML with markers removed that would
    crash ScaleTool's MarkerPlacer: those named in ``skip_names`` and any marker
    parented to ground (``<socket_parent_frame>`` referencing ground). Returns the
    sanitized file path, or None if nothing was removed."""
    import re
    txt = open(src_path, errors="replace").read()
    skipU = {str(s).upper() for s in (skip_names or set())}
    removed = []
    def _filt(m):
        name, body = m.group(1), m.group(2)
        pf = re.search(r'<socket_parent_frame>([^<]+)', body)
        frame = (pf.group(1) if pf else "").strip().lower()
        if name.upper() in skipU or frame.endswith("ground"):
            removed.append(name)
            return ""
        return m.group(0)
    new = re.sub(r'<Marker name="([^"]+)">(.*?)</Marker>\s*', _filt, txt, flags=re.S)
    if not removed:
        return None
    out = os.path.join(out_dir,
                       os.path.splitext(os.path.basename(src_path))[0] + "_scaleready.xml")
    with open(out, "w") as f:
        f.write(new)
    print(f"[scale] dropped unplaceable markers from marker set: {removed} -> {os.path.basename(out)}")
    return out


def scale_model(generic_opensim_model_path, static_trc_path, scaled_model_path, scale_setup_output_dir=None, mass=None, time_range=None, marker_set_file=None, linear_scaling=True, marker_placer=False, ik_weights=None, setup_xml_path=None, run=True):
    """
    Scale an OpenSim model using the ScaleTool based on static marker data from a TRC file.

    The ScaleTool has two independent stages, exposed here as booleans that map
    1:1 onto OpenSim's own ``ModelScaler`` and ``MarkerPlacer``:

      * ``linear_scaling`` (ModelScaler) — dimensional scaling from marker
        distances. Turn OFF for an already-personalised model (e.g. MRI/TPS
        geometry) so its segment sizes are NOT changed.
      * ``marker_placer`` (MarkerPlacer) — move the model's markers onto the
        subject's static-trial markers (with an IK pass). Useful even when
        ``linear_scaling`` is off, so markers line up for IK. Off by default
        because it is memory-heavy with 100+ marker sets.

    Combinations: both True = classic scale+placement; linear only = size but
    keep template markers; placer only = keep geometry, re-place markers
    (MRI case); both False = copy the model through unchanged.

    Args:
        scale_setup_output_dir: Directory where to save scale_setup.xml (defaults to scaled_model directory)
        ik_weights: ``{marker: weight}`` for the standalone marker-registration
            IK. A weight of 0 drops the marker from the pass entirely. Only
            used when ``marker_placer`` is on; ignored otherwise. Default None
            = every marker weighted 1.0, which is what this always did.
        setup_xml_path: Where to write the ScaleTool setup. Defaults to
            ``<scale_setup_output_dir>/scale_setup.xml``. This file is the
            record of what was actually applied — the MeasurementSet, the
            joint-centre-augmented TRC, the time range — and is the first thing
            to read when a scaled model looks wrong.
        run: False writes the setup and returns its path WITHOUT scaling. The
            setup references files under ``_temp_scaling/`` (the augmented TRC,
            the sanitised model), so that folder is kept in this mode — the
            setup is loadable in the OpenSim GUI as written.

    Returns:
        The setup XML path when ``run=False``; otherwise None.
    """
    import shutil as _shutil
    from bioscout.utils import scale_measurements as _sm
    # Apply the configured OpenSim log level right here (lowercase — OpenSim
    # ignores "Error") so ScaleTool's geometry [warning] spam is quiet.
    try:
        _lvl = getattr(getattr(settings, "BatchSettings", None), "opensim_log_level", None)
        if _lvl:
            osim.Logger.setLevelString(str(_lvl).lower())
    except Exception:
        pass
    # Self-heal a corrupt generic: some TPS/warping tools pad the .osim with
    # trailing NUL bytes after </OpenSimDocument>. OpenSim loads it but ScaleTool's
    # MarkerPlacer then segfaults / throws "string too long". Strip the padding
    # (in place, with a .nulbak backup) so scaling works.
    generic_opensim_model_path = _strip_trailing_nulls(generic_opensim_model_path)
    # Neither stage requested → nothing for the ScaleTool to do; pass the model
    # through unchanged so downstream steps still find scaled_model_path.
    if not linear_scaling and not marker_placer:
        os.makedirs(os.path.dirname(scaled_model_path) or ".", exist_ok=True)
        if os.path.abspath(generic_opensim_model_path) != os.path.abspath(scaled_model_path):
            _shutil.copyfile(generic_opensim_model_path, scaled_model_path)
        print(f"[scale] linear_scaling=False, marker_placer=False → copied model "
              f"unchanged to: {scaled_model_path}")
        # "Unchanged" used to include the mass, so a model routed through this
        # branch kept whatever total mass its source had while every downstream
        # result was normalised by the subject's. Geometry still stays untouched.
        if mass is not None:
            try:
                _sm.set_total_mass(scaled_model_path, mass)
            except Exception as e:
                print(f"[scale] [WARNING] mass-only rescale failed: {e}")
        return
    model = _quiet_model(generic_opensim_model_path)
    state = model.initSystem()
    subject_mass = mass if mass is not None else model.getTotalMass(state)

    # MarkerPlacer runs an internal IK that SEGFAULTS on markers with no valid
    # placement — markers in BatchSettings.markers_to_skip and any marker rigidly
    # attached to ground (belt markers BL/BR). Strip them from a sanitized copy of
    # BOTH the model and the marker-set file, and scale from those, leaving the
    # user's originals untouched.
    try:
        from bioscout.utils import settings as _settings
        _skip = {str(s).upper() for s in
                 getattr(getattr(_settings, "BatchSettings", None), "markers_to_skip", []) or []}
    except Exception:
        _skip = set()
    _outdir = scale_setup_output_dir or os.path.dirname(scaled_model_path) or "."
    os.makedirs(_outdir, exist_ok=True)
    # Throwaway scaling intermediates (sanitized model/markerset, ScaleTool's
    # scale_setup.xml, the static-IK marker-registration .mot) live in a private
    # _temp_scaling/ subfolder that is removed on success — so they never clutter the
    # iteration folder. (Kept only if scaling raises, for debugging.)
    _tmp = os.path.join(_outdir, "_temp_scaling")
    os.makedirs(_tmp, exist_ok=True)
    generic_for_scaling = generic_opensim_model_path
    marker_set_for_scaling = marker_set_file
    _msd = model.updMarkerSet()
    _drop = []
    for _i in range(_msd.getSize()):
        _mk = _msd.get(_i)
        try:
            _fr = _mk.getParentFrame().getName().lower()
        except Exception:
            _fr = ""
        if _mk.getName().upper() in _skip or _fr == "ground":
            _drop.append((_i, _mk.getName()))
    if _drop:
        for _i, _ in sorted(_drop, reverse=True):
            _msd.remove(_i)
        model.finalizeConnections()
        generic_for_scaling = os.path.join(
            _tmp, os.path.splitext(os.path.basename(generic_opensim_model_path))[0] + "_scaleready.osim")
        model.printToXML(generic_for_scaling)
        print(f"[scale] dropped unplaceable markers from model: {[n for _, n in _drop]}")
    if marker_set_file and os.path.exists(marker_set_file):
        _san = _sanitize_markerset_xml(marker_set_file, _skip, _tmp)
        if _san:
            marker_set_for_scaling = _san

    # --- joint centres -----------------------------------------------------
    # ScaleTool measures DISTANCES BETWEEN MARKER PAIRS. The femur and tibia can
    # only be measured hip-to-knee-to-ankle, and a motion capture system cannot
    # see a joint centre — so the *WK virtual markers that markers_powerlifter.xml
    # puts on the body origins exist in every model but in NO TRC. Compute them
    # (Harrington hips, midpoint knees/ankles) into a scaling-only copy of the
    # static TRC. The ORIGINAL TRC is left untouched and is what marker
    # registration and every dynamic trial keep using.
    trc_for_scaling = static_trc_path
    if linear_scaling:
        try:
            trc_for_scaling = _sm.augment_static_trc(
                static_trc_path,
                os.path.join(_tmp, os.path.basename(static_trc_path).replace(".trc", "_jc.trc")))
        except Exception as e:
            print(f"[scale] [WARNING] could not add joint centres to the static TRC: {e}")
            trc_for_scaling = static_trc_path

    # Resolve time range from TRC if not provided
    storage = osim.Storage(trc_for_scaling)
    t0, t1 = (time_range[0], time_range[1]) if time_range else (storage.getFirstTime(), storage.getLastTime())
    osim_time_range = osim.ArrayDouble()
    osim_time_range.append(t0)
    osim_time_range.append(t1)

    scaleTool = osim.ScaleTool()
    scaleTool.setName("ModelScaling")
    scaleTool.setSubjectMass(subject_mass)

    # GenericModelMaker — sets the unscaled model (and optionally a marker set)
    gmm = scaleTool.getGenericModelMaker()
    gmm.setModelFileName(generic_for_scaling)
    if marker_set_for_scaling:
        gmm.setMarkerSetFileName(marker_set_for_scaling)

    # Determine where to save scale setup XML
    if scale_setup_output_dir is None:
        scale_setup_output_dir = os.path.dirname(scaled_model_path)
    os.makedirs(scale_setup_output_dir, exist_ok=True)

    # ModelScaler (dimensional scaling) — toggled by ``linear_scaling``.
    #
    # A default-constructed osim.ScaleTool() has an EMPTY MeasurementSet. OpenSim
    # accepts that without complaint: setApply(True) then scales every body by
    # 1.0 and only setSubjectMass() has any effect, so the output is generic
    # geometry wearing the subject's mass — a "scaled" model that is not scaled.
    # That silent failure is why this MeasurementSet is built and attached here,
    # and why verify_scaled() checks the result afterwards.
    modelScaler = scaleTool.getModelScaler()
    modelScaler.setApply(bool(linear_scaling))
    if linear_scaling:
        try:
            _mset, _rep, _skip_m = _sm.build_measurement_set(
                model, trc_for_scaling,
                model_markers=_sm.markerset_file_names(marker_set_for_scaling))
            if _mset.getSize() == 0:
                print("[scale] [ERROR] MeasurementSet is EMPTY — ScaleTool would apply a "
                      "scale factor of 1.0 to every body and return the generic model with "
                      "the subject's mass. Check the marker names above.")
            try:
                modelScaler.setMeasurementSet(_mset)
            except Exception:
                pass
            # getModelScaler()/getMeasurementSet() hand back C++ references through
            # SWIG, but that is an assumption worth checking rather than trusting:
            # if the set did not land, append into the tool's own set instead, and
            # if THAT does not stick, say so instead of scaling by 1.0 in silence.
            if modelScaler.getMeasurementSet().getSize() != _mset.getSize():
                _tgt = modelScaler.getMeasurementSet()
                for _i in range(_mset.getSize()):
                    _tgt.cloneAndAppend(_mset.get(_i))
            _n = modelScaler.getMeasurementSet().getSize()
            if _n != _mset.getSize():
                print(f"[scale] [ERROR] the ScaleTool kept {_n} of {_mset.getSize()} "
                      f"measurements — scaling would be wrong or absent. Aborting is safer "
                      f"than shipping a generic model named 'scaled'.")
                raise RuntimeError("MeasurementSet did not attach to the ScaleTool")
            try:
                modelScaler.setScalingOrder(osim.ArrayStr("measurements", 1))
            except Exception:
                pass
            print(f"[scale] ScaleTool holds {_n} measurements")
        except Exception as e:
            print(f"[scale] [ERROR] could not build the MeasurementSet: {e}")
            raise
    modelScaler.setMarkerFileName(trc_for_scaling)
    modelScaler.setTimeRange(osim_time_range)
    modelScaler.setOutputModelFileName(scaled_model_path)
    # Keep the computed scale factors OUT of the throwaway _temp_scaling folder:
    # this file is the record of exactly what was applied to each body, and it is
    # the first thing to read when a result looks wrong.
    modelScaler.setOutputScaleFileName(os.path.join(_outdir, 'scale_factors.xml'))

    # MarkerPlacer (place model markers onto static-trial markers) — toggled by
    # ``marker_placer``. Off by default (memory-heavy with 100+ markers). When
    # linear_scaling is off but this is on, it operates on the (unscaled) model —
    # the MRI case — and writes the final model to scaled_model_path.
    # MarkerPlacer: NEVER use ScaleTool's own C++ MarkerPlacer stage — its internal
    # IK throws a HARD SIGSEGV (uncatchable in Python, so a try/except cannot recover)
    # on some complex models (Catelli high-hip-flexion, MRI Lerner-knee). Instead
    # ScaleTool does DIMENSIONAL SCALING ONLY, then markers are registered by a
    # standalone IK pass (place_markers_via_ik) — the same MarkerPlacer algorithm,
    # done by hand, which is numerically equivalent, validates markers first, and is
    # crash-safe.
    markerPlacer = scaleTool.getMarkerPlacer()
    markerPlacer.setApply(False)

    # Write the setup BEFORE running. Written after, a crash leaves nothing to
    # read — which is exactly when you want it. This is a real ScaleTool setup:
    # OpenSim serialises it, so the OpenSim GUI opens it.
    _setup_out = setup_xml_path or os.path.join(_outdir, "scale_setup.xml")
    try:
        os.makedirs(os.path.dirname(_setup_out) or ".", exist_ok=True)
        scaleTool.printToXML(_setup_out)
        print(f"[scale] ScaleTool setup written: {_setup_out}")
    except Exception as e:
        print(f"[scale] [WARNING] could not write the ScaleTool setup: {e}")
        _setup_out = None

    if not run:
        # Deliberately NOT removing _temp_scaling: the setup points into it.
        print(f"[scale] run=False — setup written, nothing scaled. Its inputs "
              f"live in {_tmp}")
        return _setup_out

    print(f"[scale] linear_scaling={bool(linear_scaling)}, marker_placer={bool(marker_placer)} "
          f"(marker placement via standalone IK, not ScaleTool MarkerPlacer)")
    if linear_scaling:
        scaleTool.run()                           # dimensional scaling only -> scaled_model_path
    else:
        # MRI/TPS case: geometry is already personalised and must not be touched.
        # But with ModelScaler off, NOTHING ever applies the subject's mass, so the
        # model silently keeps the generic's — which is why the MRI variants were
        # carrying 75.34 kg while every result was normalised by the real body mass.
        # Copy the geometry through, then rescale mass and inertia alone.
        if os.path.abspath(generic_for_scaling) != os.path.abspath(scaled_model_path):
            _shutil.copyfile(generic_for_scaling, scaled_model_path)
        if mass is not None:
            try:
                _sm.set_total_mass(scaled_model_path, mass)
            except Exception as e:
                print(f"[scale] [WARNING] mass-only rescale failed: {e}")
    if marker_placer:
        # Register markers against the ORIGINAL TRC with the joint centres stripped
        # from the marker set: they are regression estimates, not measurements, and
        # must never pull the model's real markers around during the IK pass.
        _ms_place = _sm.marker_placement_markerset(marker_set_for_scaling, _tmp)
        place_markers_via_ik(scaled_model_path, static_trc_path, scaled_model_path,
                             marker_set_file=_ms_place, time_range=(t0, t1),
                             work_dir=_tmp, ik_weights=ik_weights)
    # Prove the model actually changed size. Without this the empty-MeasurementSet
    # failure is invisible: the file exists, is named scaled.osim, and every
    # downstream stage runs happily on generic geometry.
    if linear_scaling:
        try:
            _sm.verify_scaled(generic_for_scaling, scaled_model_path)
        except Exception as e:
            print(f"[scale] [WARNING] post-scaling verification failed: {e}")
    # scaling succeeded — drop the throwaway intermediates. The setup XML above
    # names two of them (the joint-centre-augmented TRC and, if markers were
    # dropped, the sanitised model), so those paths no longer resolve: the setup
    # is a RECORD of what ran, not a re-runnable file. Call with run=False to
    # get one that is.
    _shutil.rmtree(_tmp, ignore_errors=True)
    print(f"Scaled model saved to: {scaled_model_path}")
    
# --- Inverse Kinematics ---
def create_setup_IK(osim_modelPath=None, marker_trc=None,
                    ik_output=None, taskSetPath=None, time_range=None,
                    saveXMLPath=None):
    """
    Create an Inverse Kinematics (IK) setup XML file for OpenSim.
    """
    if not osim_modelPath:
        raise ValueError("create_setup_IK: osim_modelPath is required")

    if not marker_trc:
        raise ValueError("create_setup_IK: marker_trc is required")
        
    if not os.path.exists(osim_modelPath):
        print(f"OpenSim model file not found: {osim_modelPath}")
        return
    
    # Load the model
    model = _quiet_model(osim_modelPath)
    
    # Load markers
    markers = osim.Storage(marker_trc)

    # Create the Inverse Kinematics tool
    ikTool = osim.InverseKinematicsTool()
    
    if taskSetPath:
        ikTaskSet_template = osim.IKTaskSet(taskSetPath) 
        ikTool.set_IKTaskSet(ikTaskSet_template)    
    
    # simple function to validate the markers used in the IK setup
    ikTool = validate_markers_used(osim_modelPath, ikTool, marker_trc)

    # Set the model and parameters
    ikTool.setModel(model)

    # Use relative path for model file for portability
    if saveXMLPath:
        setup_dir = os.path.dirname(saveXMLPath)
        relative_model_path = os.path.relpath(osim_modelPath, setup_dir)
        ikTool.set_model_file(relative_model_path)
    else:
        ikTool.set_model_file(osim_modelPath)

    # Set the marker data file and time range
    ikTool.setMarkerDataFileName(marker_trc)
    ikTool.set_report_marker_locations(True)
    ikTool.set_report_errors(True)

    # # check time range is valid and set it
    print(f"Input time_range: {time_range}")
    print(f"Marker data time range: [{markers.getFirstTime()}, {markers.getLastTime()}]")

    if time_range is not None:
        try:
            # Handle different time_range formats
            if isinstance(time_range, str):
                # Parse string format like "[0.0, 1.5]" or "np.float64(0.0), np.float64(1.5)"
                cleaned = time_range.strip('[]').replace('np.float64(', '').replace(')', '')
                parts = cleaned.split(',')
                time_range = [float(p.strip()) for p in parts]
            elif isinstance(time_range, (list, tuple)):
                time_range = [float(t) for t in time_range]
            else:
                time_range = None

            if time_range and len(time_range) >= 2:
                print(f"Parsed time_range: [{time_range[0]}, {time_range[1]}]")
                if time_range[0] < markers.getFirstTime() or time_range[1] > markers.getLastTime():
                    print("Warning: Specified time range is outside the bounds of the marker data. Using full range instead.")
                    time_range = [markers.getFirstTime(), markers.getLastTime()]

                ikTool.setStartTime(float(time_range[0]))  # Set start time
                ikTool.setEndTime(float(time_range[1]))    # Set end time
                print(f"IK time range set to: [{time_range[0]}, {time_range[1]}]")
            else:
                time_range = None
        except (ValueError, TypeError, AttributeError) as e:
            print(f"Error parsing time_range: {e}. Using full range instead.")
            time_range = None

    if time_range is None:
        print(f"Using full marker data time range for IK")
        ikTool.setStartTime(markers.getFirstTime())  # Default start time
        ikTool.setEndTime(markers.getLastTime())    # Default end time
    
    # Set the output motion file name relative to the results directory.
    #
    # setResultsDir('./') meant the PROCESS CWD, not the trial folder, and
    # set_report_errors(True) above makes OpenSim write `_ik_marker_errors.sto`
    # and `_ik_model_marker_locations.sto` into that results dir. Run from a
    # project root (as settings.py is) and those land in the repo root, are
    # rewritten by every trial, and `Analyse.calculate_mean_marker_error`
    # then reads whichever one happened to be last -- for the wrong trial.
    # Point it at the trial's own folder.
    resultsDir = os.path.dirname(os.path.abspath(ik_output))
    os.makedirs(resultsDir, exist_ok=True)
    ikTool.setResultsDir(resultsDir)
    ikTool.setOutputMotionFileName(os.path.relpath(ik_output, resultsDir))
    if saveXMLPath is None:
        saveXMLPath = ik_output.replace('.mot', '_ik_setup.xml')
    ikTool.printToXML(saveXMLPath)
    print(f"Inverse Kinematics setup saved to {os.path.abspath(saveXMLPath)}")

@_quiet_console
def run_ik(osim_modelPath=None, setup_xml=None, resultsDir=None):
    print(f"DEBUG: run_ik() called with osim_modelPath={osim_modelPath}, setup_xml={setup_xml}, resultsDir={resultsDir}")
    utils.print_to_log(f"DEBUG: run_ik() called with osim_modelPath={osim_modelPath}, setup_xml={setup_xml}, resultsDir={resultsDir}")

    if osim_modelPath is None:
        osim_modelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')
    if setup_xml is None:
        setup_xml = input("Enter the path to save the IK setup XML file (.xml): ").strip('"')

    # Determine results directory
    if resultsDir is None:
        resultsDir = os.path.dirname(os.path.abspath(setup_xml))

    resultsDir = os.path.abspath(resultsDir)
    original_cwd = os.getcwd()
    print(f"DEBUG: resultsDir={resultsDir}, original_cwd={original_cwd}")
    utils.print_to_log(f"DEBUG: resultsDir={resultsDir}, original_cwd={original_cwd}")

    try:
        # Pre-flight checks
        print(f"[IK] Performing pre-flight checks...")
        _check_ik_prerequisites(osim_modelPath, setup_xml, resultsDir)

        # Change to the results directory to ensure output files are created in the correct location
        os.chdir(resultsDir)
        print(f"Changed working directory to: {resultsDir}")
        utils.print_to_log(f"Changed working directory to: {resultsDir}")

        # Load the model
        print(f"Loading model from {osim_modelPath}")
        model = _quiet_model(osim_modelPath)

        # Initialize the system before disabling analyses
        model.initSystem()
        print(f"Model initialized")

        # Disable all analyses to avoid "null upcall object" errors
        analysisSet = model.getAnalysisSet()
        print(f"Number of analyses in model: {analysisSet.getSize()}")
        for i in range(analysisSet.getSize()):
            try:
                analysis = analysisSet.get(i)
                analysis.setEnabled(False)
                print(f"Disabled analysis {i}: {analysis.getName()}")
            except Exception as e:
                print(f"Error disabling analysis {i}: {e}")

        # Finalize the model after modifying analyses
        try:
            model.finalizeConnections()
            print("Model connections finalized")
        except Exception as e:
            print(f"Warning: Error finalizing connections: {e}")

        # Reload tool from xml
        print(f"Loading IK tool from {setup_xml}")
        ikTool = osim.InverseKinematicsTool(setup_xml)
        ikTool.setModel(model)

        # --- NaN interpolation: fill missing marker data before IK ---
        # Gaps in the TRC can make AssemblySolver return -nan and crash. We fill
        # them by linear interpolation, but the TRC format MUST be preserved
        # exactly: a .trc has a fixed 5-line header where line 3 is the numeric
        # DataRate row and line 4 ("Frame#  Time  ...") + line 5 (X1 Y1 Z1 ...)
        # are the column headers. Data begins on line 6. We anchor on the
        # 'Frame#' row, interpolate only the numeric data block, keep the header
        # verbatim, and restore the original file on any error.
        try:
            import xml.etree.ElementTree as _ET
            import numpy as _np
            _tree = _ET.parse(setup_xml)
            _mf = _tree.getroot().findtext('.//marker_file') or ''
            if _mf and not os.path.isabs(_mf):
                _mf = os.path.join(resultsDir, _mf)
            if _mf and os.path.isfile(_mf):
                _orig = open(_mf, 'r').read()
                try:
                    _lines = _orig.splitlines(keepends=True)
                    # Locate the 'Frame#' column-header row; data starts 2 lines
                    # below it (after the X1/Y1/Z1 axis-label row).
                    _fr = next((i for i, l in enumerate(_lines)
                                if l.lstrip().lower().startswith('frame#')), None)
                    if _fr is not None and _fr + 2 < len(_lines):
                        _hdr = _lines[:_fr + 2]
                        _data = [l for l in _lines[_fr + 2:] if l.strip()]
                        _rows = []
                        for _l in _data:
                            _cells = _l.rstrip('\r\n').split('\t')
                            _rows.append([
                                float(_c) if _c.strip() not in ('', 'nan', 'NaN')
                                else _np.nan for _c in _cells])
                        _w = max(len(r) for r in _rows)
                        _A = _np.full((len(_rows), _w), _np.nan)
                        for _i, _r in enumerate(_rows):
                            _A[_i, :len(_r)] = _r
                        # Columns 0,1 are Frame# and Time; only fill SHORT
                        # interior gaps in the marker columns (2..end). Long gaps,
                        # leading/trailing gaps, and fully-missing markers are left
                        # EMPTY so OpenSim treats them as 'marker absent' and skips
                        # them — filling those (e.g. with 0,0,0 or a long straight
                        # line) plants markers far from the body and makes IK
                        # diverge / fail.
                        # Fill what can be filled, honestly.
                        #
                        # This used to be a straight-line interpolation over
                        # gaps of up to 20 frames and nothing else. It reported
                        # "Filled 0 of 178168" on 022's running trials and moved
                        # on, and IK then solved a pelvis that was unobserved
                        # for a third of the window — which OpenSim does not
                        # complain about, because a marker it cannot see costs
                        # it nothing. bioscout.utils.gapfill does the two things
                        # that actually work: spline through short gaps, and
                        # reconstruct longer ones from the other markers on the
                        # same segment, refusing when it cannot do so to a
                        # measured tolerance. What it refuses stays empty.
                        _nan_count = int(_np.isnan(_A[:, 2:]).sum())
                        if _nan_count > 0:
                            from bioscout.utils import gapfill as _gf
                            _nmk = (_w - 2) // 3
                            _cube = _A[:, 2:2 + 3 * _nmk].reshape(len(_rows), _nmk, 3)
                            try:
                                _names = [c.strip() for c in
                                          _lines[_fr].rstrip('\r\n').split('\t')[2:]
                                          if c.strip()][:_nmk]
                            except Exception:
                                _names = None
                            _filledA, _rep = _gf.fill_array(_cube, _names)
                            _rep.path = _mf
                            for _ln in _gf.format_report(_rep).splitlines():
                                print(f"[IK] {_ln}")
                            _A[:, 2:2 + 3 * _nmk] = _filledA.reshape(len(_rows), -1)
                            # Say what is still solvable. A window that keeps
                            # frames nothing constrains is a window that will
                            # produce kinematics nobody should trust, and this
                            # is the last moment anyone is looking.
                            try:
                                _s0, _e0, _L0, _why0 = _gf.usable_window(_filledA, _names)
                                _tcol = _A[:, 1]
                                if _L0 and _L0 < 0.95 * len(_rows):
                                    print(f"[IK] {_why0}")
                                    print(f"[IK] markers support at most "
                                          f"time_range: [{_tcol[_s0]:.3f}, "
                                          f"{_tcol[_e0 - 1]:.3f}] "
                                          f"({_tcol[_e0 - 1] - _tcol[_s0]:.3f} s) — "
                                          f"solving wider than this fits a pose "
                                          f"nothing observed.")
                            except Exception:
                                pass
                            _out = list(_hdr)
                            for _i in range(_A.shape[0]):
                                _v = _A[_i]
                                _frame = int(round(_v[0])) if not _np.isnan(_v[0]) else _i + 1
                                _cells = [str(_frame)] + [
                                    ("" if _np.isnan(_x) else f"{_x:.5f}") for _x in _v[1:]]
                                _out.append('\t'.join(_cells) + '\n')
                            with open(_mf, 'w', newline='') as _f:
                                _f.writelines(_out)
                            print(f"[IK] TRC gap-fill complete → {_mf}")
                except Exception as _ie:
                    # Any problem → put the original TRC back so IK still runs.
                    with open(_mf, 'w', newline='') as _f:
                        _f.write(_orig)
                    print(f"[IK] NaN interpolation skipped, original TRC restored ({_ie})")
        except Exception as _nan_e:
            print(f"[IK] Warning: NaN interpolation step failed (continuing): {_nan_e}")

        # Setup XML now lives in a subfolder (external_biomechanics/). OpenSim
        # resolves relative <marker_file>/<output_motion_file> in a deserialized
        # tool against the SETUP FILE's directory, not the cwd — so trial-root-
        # relative paths (e.g. inputs\marker_experimental.trc) break. Force them
        # absolute on the tool so the subfoldered layout works.
        try:
            import xml.etree.ElementTree as _ET2
            _setup_dir = os.path.dirname(os.path.abspath(setup_xml))
            _r2 = _ET2.parse(setup_xml).getroot()
            _mk = _r2.findtext('.//marker_file') or ''
            _om = _r2.findtext('.//output_motion_file') or ''
            # marker_file is written trial-root-relative; resolve to wherever the
            # file actually exists (trial root, else next to the setup).
            if _mk and not os.path.isabs(_mk):
                _cands = [os.path.abspath(os.path.join(resultsDir, _mk)),
                          os.path.abspath(os.path.join(_setup_dir, _mk))]
                _mk_abs = next((c for c in _cands if os.path.isfile(c)), _cands[0])
            else:
                _mk_abs = _mk
            # output_motion_file is written relative to the setup file's own dir
            # (OpenSim convention), i.e. it belongs NEXT TO setup_IK.xml.
            _om_abs = _om if (not _om or os.path.isabs(_om)) else \
                os.path.abspath(os.path.join(_setup_dir, _om))
            if _mk:
                try:    ikTool.set_marker_file(_mk_abs)
                except Exception: ikTool.setMarkerDataFileName(_mk_abs)
            if _om:
                os.makedirs(os.path.dirname(_om_abs), exist_ok=True)
                try:    ikTool.set_output_motion_file(_om_abs)
                except Exception: ikTool.setOutputMotionFileName(_om_abs)
            print(f"[IK] marker_file={_mk_abs}\n[IK] output_motion_file={_om_abs}")
        except Exception as _abs_e:
            print(f"[IK] Warning: could not set absolute tool paths ({_abs_e})")

        # Run the inverse kinematics calculation. The TOOL loads its own
        # model from the setup XML, so _quiet_model() upstream cannot reach
        # that copy's printBasicInfo — only the fd-level context can.
        with _osim_quiet_ctx():
            ikTool.run()
        utils.print_to_log(f"Inverse Kinematics calculation completed. Results saved to {resultsDir}")
        print(f"Inverse Kinematics calculation completed successfully")
        # Cold-start repair: the FIRST solved frame starts from the model's
        # default pose and can converge to a folded mirror solution (pelvis
        # ~90 deg off) that the warm-started frames never revisit. ID then
        # differentiates that single frame into multi-kNm pelvis moments.
        # Replace leading frames that sit far from the trial median with the
        # first good frame.
        try:
            _sanitize_ik_leading_frames(_om_abs)
        except Exception as _se:
            print(f"[IK] leading-frame check skipped: {_se}")

    except Exception as e:
        utils.print_to_log(f"Error running IK: {e}")
        print(f"Error running IK: {e}")
        # OpenSim writes the real failure detail to opensim.log (in cwd); surface
        # the tail so the actual cause is visible instead of the generic message.
        try:
            for _logp in ('opensim.log', os.path.join(resultsDir, 'opensim.log')):
                if os.path.isfile(_logp):
                    _tail = open(_logp, 'r', errors='replace').read().splitlines()[-25:]
                    print("----- opensim.log (last 25 lines) -----")
                    print("\n".join(_tail))
                    print("---------------------------------------")
                    break
        except Exception:
            pass
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Always restore original working directory
        try:
            os.chdir(original_cwd)
            print(f"Restored working directory to: {original_cwd}")
        except Exception as e:
            print(f"Warning: Could not restore original working directory: {e}")

def _sanitize_ik_leading_frames(mot_path, max_lead=5, tol_deg=30.0):
    """Replace up to `max_lead` leading frames whose pelvis orientation is more
    than `tol_deg` from the trial median (IK cold-start fold) with the first
    good frame's values. In-place; no-op when the file starts clean."""
    import numpy as _np
    lines = open(mot_path, errors="replace").read().splitlines()
    h = max(i for i, l in enumerate(lines) if l.strip().lower() == "endheader")
    cols = lines[h + 1].split()
    body = [l for l in lines[h + 2:] if l.strip()]
    d = _np.array([[float(x) for x in l.split()] for l in body])
    idx = [cols.index(c) for c in ("pelvis_tilt", "pelvis_list", "pelvis_rotation")
           if c in cols]
    if not idx or len(d) < max_lead + 2:
        return
    med = _np.median(d[:, idx], axis=0)
    bad = _np.abs(d[:, idx] - med).max(axis=1) > tol_deg
    n = 0
    while n < min(max_lead, len(d) - 1) and bad[n]:
        n += 1
    if n == 0:
        return
    good = d[n].copy()
    for k in range(n):
        t = d[k, 0]
        d[k] = good
        d[k, 0] = t
    fmt = "\t".join(["%12.8f"] * d.shape[1])
    out = lines[:h + 2] + [fmt % tuple(r) for r in d]
    open(mot_path, "w").write("\n".join(out) + "\n")
    print(f"[IK] cold-start repair: replaced {n} leading frame(s) with the "
          f"first good frame (pelvis was >{tol_deg:.0f} deg off the trial median)")


def _check_ik_prerequisites(osim_modelPath, setup_xml, resultsDir):
    """
    Pre-flight checks for IK: verify all required files exist.
    Raises detailed error messages if issues are found.
    """
    errors = []

    # Check model file
    if not os.path.isfile(osim_modelPath):
        errors.append(f"Model file not found: {osim_modelPath}")

    # Check setup XML file
    if not os.path.isfile(setup_xml):
        errors.append(f"IK setup XML not found: {setup_xml}")
    else:
        # Parse setup XML to find required input files
        try:
            tree = ET.parse(setup_xml)
            root = tree.getroot()

            # Find the IK tool element (usually the root or a child)
            ik_tool = root.find('.//InverseKinematicsTool') or root

            # Get the marker data file
            marker_file_elem = ik_tool.find('.//marker_file') or ik_tool.find('.//MarkerFile')
            if marker_file_elem is not None and marker_file_elem.text:
                marker_file = marker_file_elem.text.strip()
                # Resolve relative paths
                if not os.path.isabs(marker_file):
                    marker_file = os.path.join(resultsDir, marker_file)

                if not os.path.isfile(marker_file):
                    errors.append(f"Marker file (TRC) not found: {marker_file}")
                else:
                    print(f"[IK] ✓ Marker file found: {marker_file}")

            # Get the coordinate file (IK output)
            coord_file_elem = ik_tool.find('.//output_motion_file') or ik_tool.find('.//OutputMotionFile')
            if coord_file_elem is not None and coord_file_elem.text:
                coord_file = coord_file_elem.text.strip()
                print(f"[IK] ✓ Output will be saved to: {os.path.join(resultsDir, coord_file)}")

        except Exception as e:
            errors.append(f"Error parsing IK setup XML: {e}")

    # Check results directory
    if not os.path.isdir(resultsDir):
        errors.append(f"Results directory not found: {resultsDir}")

    if errors:
        error_msg = "IK Pre-flight Check Failed:\n" + "\n".join(f"  - {err}" for err in errors)
        raise RuntimeError(error_msg)

# --- Muscle Analysis ---
def find_non_zero_mom_arm_muscles(ma_data: pd.DataFrame, muscles: list) -> list:
    '''
    Find the muscles that have non-zero moment arms in the given data.
    '''
    
    non_zero_muscles = []
    for muscle in muscles:
        if ma_data is None:
            continue
        if muscle not in ma_data.columns:
            continue
        if ma_data[muscle].abs().sum() > 0:
            non_zero_muscles.append(muscle)
    return non_zero_muscles

# --- Static optimisation --
def edit_pelvis_com_actuators(osim_modelPath, actuatorsFilePath):
    """
    Edit the pelvis center of mass actuator in the OpenSim model.
    """ 
    model = _quiet_model(osim_modelPath)
    model.initSystem()

    # Find the pelvis center of mass actuator
    pelvis = model.getBodySet().get('pelvis')
    com = pelvis.get_mass_center().to_numpy()

    actuators = utils.read_xml(actuatorsFilePath)
    point_actuators = actuators.find('ForceSet').find('objects').findall('PointActuator')
    
    for actuator in point_actuators:
        if actuator.get('name') in ['FX', 'FY', 'FZ']:
            # Update the point in the actuator to match the pelvis center of mass
            point = actuator.find('point')
            point.text = f"{com[0]} {com[1]} {com[2]}"
    
    # Save the modified actuators file
    utils.save_pretty_xml(actuators, actuatorsFilePath)
    
    print(f"Updated pelvis center of mass actuator in {actuatorsFilePath} to {com}")

def normalise_muscle(muscle_forces_path, osim_modelPath):
    
    muscle_forces = utils.load_any_data_file(muscle_forces_path)
    model = _quiet_model(osim_modelPath)
    model_muscles = model.getMuscles()
    for muscle in muscle_forces.columns:
        try:
            muscle_obj = model_muscles.get(muscle)
        except Exception as e:
            print(f"Error retrieving muscle '{muscle}': {e}")
            continue
                
        # Normalize the muscle forces
        normalized_forces = muscle_forces[muscle] / muscle_obj.getMaxIsometricForce()
        
        # Save the normalized forces back to the DataFrame
        muscle_forces[muscle] = normalized_forces
    
    # Save the normalized muscle forces to a new file
    header = utils.load_sto_header(muscle_forces_path)
    utils.write_sto_file(muscle_forces, muscle_forces_path.replace('.sto', '_normalised.sto'), header=header)
    
    print(f"Normalized muscle forces saved to {muscle_forces_path.replace('.sto','_normalised.sto')}")

# --- Joint Reaction Analysis ---
def _strip_trailing_nulls(osim_path):
    """If an .osim (or any XML) file is padded with NUL bytes after its closing
    tag (a corruption some TPS/warping tools produce that segfaults ScaleTool),
    truncate the padding in place — backing up the original as ``<file>.nulbak``.
    Returns the (now clean) path. No-op if the file has no NULs."""
    import shutil as _shutil
    try:
        with open(osim_path, "rb") as f:
            b = f.read()
        if b.count(0) == 0:
            return osim_path
        end = b.rfind(b"</OpenSimDocument>")
        if end < 0:
            end = b.rfind(b">")                    # generic XML fallback
        if end < 0:
            return osim_path
        cut = end + (len(b"</OpenSimDocument>") if b[end:end + 18] == b"</OpenSimDocument>" else 1)
        if b[cut:cut + 2] == b"\r\n":
            cut += 2
        elif b[cut:cut + 1] == b"\n":
            cut += 1
        clean = b[:cut]
        if clean.count(0):                          # still dirty -> leave it alone
            return osim_path
        if not os.path.exists(osim_path + ".nulbak"):
            _shutil.copy2(osim_path, osim_path + ".nulbak")
        with open(osim_path, "wb") as f:
            f.write(clean)
        print(f"[scale] stripped {b.count(0)} trailing NUL bytes from "
              f"{os.path.basename(osim_path)} (backup: {os.path.basename(osim_path)}.nulbak)")
    except Exception:
        pass
    return osim_path


def place_markers_via_ik(model_path, static_trc, out_model_path,
                         marker_set_file=None, time_range=None, work_dir=None,
                         ik_weights=None):
    """Register a model's markers to the subject's STATIC pose WITHOUT ScaleTool's
    MarkerPlacer (which segfaults / throws bad_alloc on some complex models, e.g.
    the MRI/Lerner-knee model). Standard MarkerPlacer algorithm, done by hand:

      1. run a normal IK on the static trial (this path works where MarkerPlacer
         fails),
      2. move the model to the MEAN static pose,
      3. relocate each model marker to the averaged experimental marker position,
         expressed in that marker's parent frame.

    Writes the registered model to ``out_model_path``. Best-effort; on failure the
    base model is left as-is (markers un-registered)."""
    import numpy as _np
    _quiet_osim()
    model = _quiet_model(model_path)
    if marker_set_file and os.path.exists(marker_set_file):
        try:
            model.updateMarkerSet(osim.MarkerSet(model, marker_set_file))
        except Exception:
            pass
    state = model.initSystem()

    md = osim.MarkerData(static_trc)
    try:
        md.convertToUnits(osim.Units(osim.Units.Meters))     # -> metres to match the model
    except Exception:
        pass
    t0 = md.getStartFrameTime() if time_range is None else float(time_range[0])
    t1 = md.getLastFrameTime() if time_range is None else float(time_range[1])

    # 1) IK on the static trial
    _mot = (os.path.join(work_dir, os.path.splitext(os.path.basename(out_model_path))[0] + "_static_ik.mot")
            if work_dir else os.path.splitext(out_model_path)[0] + "_static_ik.mot")
    ik = osim.InverseKinematicsTool()
    # Marker weights for the registration pass. Without a task set every marker
    # is weighted 1.0, so a marker you know is badly placed pulls the static
    # pose exactly as hard as a reliable one — and the model's markers are then
    # registered to that pose.
    if ik_weights:
        try:
            _model_names = {model.getMarkerSet().get(_i).getName()
                            for _i in range(model.getMarkerSet().getSize())}
            _ts = osim.IKTaskSet()
            _used = _zero = 0
            for _n, _w in sorted(ik_weights.items()):
                if _n not in _model_names:
                    continue                      # in the TRC, not on the model
                _t = osim.IKMarkerTask()
                _t.setName(_n)
                _t.setWeight(float(_w))
                _t.setApply(float(_w) > 0)
                _ts.cloneAndAppend(_t)
                if float(_w) > 0:
                    _used += 1
                else:
                    _zero += 1
            if _ts.getSize():
                ik.set_IKTaskSet(_ts)
                print(f"[scale] marker registration IK: {_used} marker(s) weighted, "
                      f"{_zero} switched off")
        except Exception as e:
            print(f"[scale] [WARNING] could not apply marker weights to the "
                  f"registration IK ({e}); every marker weighted 1.0")
    ik.setModel(model)
    ik.setMarkerDataFileName(static_trc)
    ik.setStartTime(t0)
    ik.setEndTime(t1)
    ik.setOutputMotionFileName(_mot)
    # OpenSim defaults results_directory to './' (the PROCESS CWD) and
    # report_errors to True, so this registration pass used to drop
    # `_ik_marker_errors.sto` in whatever directory the run started from --
    # the project root -- overwritten by every model and session. Keep it
    # next to the model it belongs to.
    _ik_res = os.path.dirname(os.path.abspath(_mot))
    os.makedirs(_ik_res, exist_ok=True)
    try:
        ik.setResultsDir(_ik_res)
    except Exception:
        pass
    with _osim_quiet_ctx():
        ik.run()

    # 2) mean static pose
    sto = osim.Storage(_mot)
    try:
        if sto.isInDegrees():
            model.getSimbodyEngine().convertDegreesToRadians(sto)
    except Exception:
        pass
    cs = model.getCoordinateSet()
    for i in range(cs.getSize()):
        c = cs.get(i)
        arr = osim.ArrayDouble()
        try:
            sto.getDataColumn(c.getName(), arr)
            vals = [arr.getitem(k) for k in range(arr.getSize())]
        except Exception:
            vals = []
        if vals:
            try:
                c.setValue(state, float(_np.mean(vals)), False)
            except Exception:
                pass
    model.assemble(state)
    model.realizePosition(state)

    # 3) relocate markers to the averaged experimental positions
    ground = model.getGround()
    ms = model.updMarkerSet()
    nfr = md.getNumFrames()
    moved = 0
    for i in range(ms.getSize()):
        mk = ms.get(i)
        try:
            idx = md.getMarkerIndex(mk.getName())
        except Exception:
            idx = -1
        if idx < 0:
            continue
        acc = _np.zeros(3); n = 0
        for f in range(nfr):
            v = md.getFrame(f).getMarker(idx)
            x, y, z = v.get(0), v.get(1), v.get(2)
            if x == x:                                       # skip NaN
                acc += (x, y, z); n += 1
        if n == 0:
            continue
        p = acc / n
        try:
            pF = ground.findStationLocationInAnotherFrame(
                state, osim.Vec3(float(p[0]), float(p[1]), float(p[2])), mk.getParentFrame())
            mk.set_location(pF)
            moved += 1
        except Exception:
            pass
    model.finalizeConnections()
    model.printToXML(out_model_path)
    print(f"[scale] IK-based marker registration placed {moved}/{ms.getSize()} markers "
          f"-> {os.path.basename(out_model_path)}")
    return out_model_path


def relativise_setup_xml(xml_path):
    """Rewrite absolute filesystem paths in an OpenSim/CEINMS setup XML to paths
    RELATIVE to the setup file's own directory, so the setup is portable (OpenSim
    resolves relative paths against the setup dir). Only rewrites values that look
    like absolute paths (drive-letter, UNC, or POSIX-absolute); everything else is
    left untouched. Best-effort — no-op on parse failure."""
    import xml.etree.ElementTree as _ET
    try:
        xml_path = os.path.abspath(xml_path)
        base = os.path.dirname(xml_path)
        tree = _ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return
    def _is_abs(t):
        return len(t) > 2 and (t[1:3] in (":\\", ":/") or t.startswith(("/", "\\\\")))
    changed = False
    for el in root.iter():
        t = (el.text or "").strip()
        if not t or " " in t and not _is_abs(t):
            continue
        # a value may be a space-separated LIST of paths (e.g. force set files)
        parts = t.split()
        if parts and all(_is_abs(p) for p in parts):
            try:
                el.text = " ".join(os.path.relpath(p, base).replace("/", "\\") for p in parts)
                changed = True
            except Exception:
                pass
    if changed:
        try:
            tree.write(xml_path)
        except Exception:
            pass


def create_analysis_tool(marker_trc, externalloadsfile, osim_modelPath,
                         results_directory, actuators=None):
    """Creates and configures an OpenSim AnalyzeTool object.

    Args:
    coordinates_file: Path to the motion data file (e.g., .trc or .mot).
    model_path: Path to the OpenSim model file (.osim).
    results_directory: Path to the directory for storing results.
    force_set_files (optional): List of paths to actuator force set files.

    Returns:
    OpenSim AnalyzeTool object.

    # Example usage:
        coordinates_file = "your_motion_data.trc"
        model_path = "your_model.osim"
        results_directory = "analysis_results"
        force_set_files = ["actuator1_forces.xml", "actuator2_forces.xml"]  # Optional

        analysis_tool = create_analysis_tool(coordinates_file, model_path, results_directory, force_set_files)

        # Run the analysis
        analysis_tool.run()
    """

    # Load the motion data
    mot_data = osim.Storage(marker_trc)

    # Get initial and final time
    initial_time = mot_data.getFirstTime()
    final_time = mot_data.getLastTime()

    # Create and set model
    model = _quiet_model(osim_modelPath)
    analyze_tool = osim.AnalyzeTool()
    analyze_tool.setModel(model)

    # Set other parameters. Use ABSOLUTE paths: the setup XML may be saved in a
    # different subfolder than the coordinates/model, and OpenSim resolves
    # relative paths against the setup file's own dir — absolute sidesteps that.
    analyze_tool.setModelFilename(os.path.abspath(osim_modelPath))
    analyze_tool.setReplaceForceSet(False)

    # set results directory
    analyze_tool.setResultsDir(os.path.abspath(results_directory))
    analyze_tool.setOutputPrecision(8)

    # Set actuator force files (if provided)
    if actuators:
        force_set = osim.ArrayStr()
        for file in actuators:
            force_set.append(file)
        analyze_tool.setForceSetFiles(force_set)

    # Set initial and final time
    analyze_tool.setInitialTime(initial_time)
    analyze_tool.setFinalTime(final_time)

    # Set analysis parameters
    analyze_tool.setSolveForEquilibrium(False)
    analyze_tool.setMaximumNumberOfSteps(20000)
    analyze_tool.setMaxDT(1)
    analyze_tool.setMinDT(1e-8)
    analyze_tool.setErrorTolerance(1e-5)

    # Set external loads and coordinates files (absolute — see note above).
    analyze_tool.setExternalLoadsFileName(os.path.abspath(externalloadsfile))
    analyze_tool.setCoordinatesFileName(os.path.abspath(marker_trc))

    # Set filter cutoff frequency
    analyze_tool.setLowpassCutoffFrequency(6)


    # Return the analysis tool
    return analyze_tool

# --- Induced Acceleration Analysis ---
def create_iaa_tool(osim_modelPath=None, ik_output=None, grf_xml=None, setup_file_path=None, so_controls_file=None, actuators=None):
    """
    Create and configure an OpenSim Induced Acceleration Tool object.

    Args:
        osim_modelPath (str): Path to the OpenSim model file (.osim).
        ik_output (str): Path to the Inverse Kinematics output file (.mot).
        grf_xml (str): Path to the Ground Reaction Forces XML file (.xml).
        setup_file_path (str): Path to the Induced Acceleration setup XML file (.xml).
        so_controls_file (str, optional): Path to the Static Optimization controls file (.sto).

    Returns:
        OpenSim InducedAccelerationTool object.
    """

    if not osim_modelPath:
        osim_modelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')

    if not ik_output:
        ik_output = input("Enter the path to the Inverse Kinematics output file (.mot): ").strip('"')

    if not grf_xml:
        grf_xml = input("Enter the path to the Ground Reaction Forces XML file (.xml): ").strip('"')

    if not setup_file_path:
        setup_file_path = os.path.join(os.path.dirname(os.path.abspath(ik_output)), 'setup_IAA.xml')

    if not so_controls_file:
        so_controls_file = input("Enter the path to the Static Optimization controls file (.sto): ").strip('"')

        activation_file = input("Enter the path to the Static Optimization activations file (.sto) (or press Enter to skip): ").strip('"')

    # Create and set model
    model = _quiet_model(osim_modelPath)
    tool = osim.AnalyzeTool(model)
    tool.setName("InducedAccelerations_Tool")
    tool.setModelFilename(osim_modelPath)

    # Load motion to get start/end times
    motion = osim.Storage(ik_output)
    initial_time = motion.getFirstTime()
    final_time = motion.getLastTime()

    # Set Tool Parameters
    tool.setInitialTime(initial_time)
    tool.setFinalTime(final_time)
    tool.setCoordinatesFileName(ik_output)
    tool.setExternalLoadsFileName(grf_xml)
    tool.setControlsFileName(so_controls_file)
    tool.setSolveForEquilibrium(True)
    tool.setLowpassCutoffFrequency(6.0) # Filter coordinates

    tool.setStatesFileName(activation_file)
    tool.setSolveForEquilibrium(False)
    
    # Set results directory relative to where the setup file will be, or absolute
    results_dir = os.path.join(os.path.dirname(setup_file_path), "IAA_Results")
    tool.setResultsDir(results_dir)

    # Set actuator force files (if provided)
    if actuators:
        force_set = osim.ArrayStr()
        for file in actuators:
            force_set.append(os.path.abspath(file))
        tool.setForceSetFiles(force_set)
        tool.setReplaceForceSet(False)

    # 3. Configure the InducedAccelerations Analysis
    iaa_analysis = osim.InducedAccelerations()
    iaa_analysis.setName("InducedAccelerations")
    iaa_analysis.setStartTime(initial_time)
    iaa_analysis.setEndTime(final_time)
    
    # Add the Analysis to the Tool
    tool.getAnalysisSet().adoptAndAppend(iaa_analysis)

    # Save the setup file for reference
    tool.printToXML(setup_file_path)
    print(f"IAA Tool configured. Setup file saved to: {setup_file_path}")
    tool.run()
    return tool

# --- Main OSIM Analysis ---
def create_setup_ID(osim_modelPath=None, ik_output=None, grf_xml=None,
                   id_output=None, taskSetPath=None, saveXMLPath=None):
    """
    Create an Inverse Dynamics (ID) setup XML file for OpenSim.

    This function creates the setup XML that will be used by run_id().
    """
    if not osim_modelPath:
        osim_modelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')
    if not ik_output:
        ik_output = input("Enter the path to the IK output file (.mot): ").strip('"')
    if not grf_xml:
        grf_xml = input("Enter the path to the GRF XML file (.xml): ").strip('"')
    if not id_output:
        id_output = input("Enter the desired output path for the ID results (.sto): ").strip('"')

    if not os.path.exists(osim_modelPath):
        raise FileNotFoundError(f"OpenSim model file not found: {osim_modelPath}")
    if not os.path.exists(ik_output):
        raise FileNotFoundError(f"IK output file not found: {ik_output}")
    if not os.path.exists(grf_xml):
        raise FileNotFoundError(f"GRF XML file not found: {grf_xml}")

    # Load the model
    model = _quiet_model(osim_modelPath)
    model.initSystem()

    # Load the motion data
    motion = osim.Storage(ik_output)

    # Create the Inverse Dynamics tool
    idTool = osim.InverseDynamicsTool()
    idTool.setModel(model)
    idTool.setOutputGenForceFileName(os.path.basename(id_output))

    # Use relative paths for portability
    if saveXMLPath:
        setup_dir = os.path.dirname(saveXMLPath)
        relative_model = os.path.relpath(osim_modelPath, setup_dir)
        relative_ik = os.path.relpath(ik_output, setup_dir)
        relative_grf = os.path.relpath(grf_xml, setup_dir)
        relative_results = "./"
    else:
        relative_model = osim_modelPath
        relative_ik = ik_output
        relative_grf = grf_xml
        relative_results = os.path.dirname(os.path.abspath(id_output))

    idTool.setModelFileName(relative_model)
    idTool.setCoordinatesFileName(relative_ik)
    idTool.setStartTime(motion.getFirstTime())
    idTool.setEndTime(motion.getLastTime())
    idTool.setExternalLoadsFileName(relative_grf)
    idTool.setResultsDir(relative_results)
    idTool.setLowpassCutoffFrequency(6)

    # Save setup XML
    if saveXMLPath is None:
        saveXMLPath = id_output.replace('.sto', '_id_setup.xml')

    idTool.printToXML(saveXMLPath)

    # Load xml and edit forces to exclude
    xml = utils.read_xml(saveXMLPath)
    xml.find('.//forces_to_exclude').text = 'Muscles'
    utils.save_pretty_xml(xml, saveXMLPath)

    print(f"Inverse Dynamics setup saved to {os.path.abspath(saveXMLPath)}")

@_quiet_console
def run_id(osimModelPath=None, ikOutputPath=None, grfXmlPath=None,
         setupXmlPath=None):
    """
    Example usage:
    main(osim_modelPath='path/to/model.osim',
         ik_output='path/to/ik_output.mot',
         grf_xml='path/to/grf.xml',
         setup_xml='path/to/setup.xml',
         resultsDir='path/to/results')

    """
    # If setupXmlPath is provided, load parameters from it
    if setupXmlPath and os.path.exists(setupXmlPath):
        setup_dir = os.path.dirname(os.path.abspath(setupXmlPath))
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(setupXmlPath)
            root = tree.getroot()

            # Extract paths from setup XML
            if not osimModelPath:
                model_elem = root.find('.//model_file')
                if model_elem is not None and model_elem.text:
                    model_file = model_elem.text
                    # Convert relative to absolute if needed
                    if not os.path.isabs(model_file):
                        osimModelPath = os.path.normpath(os.path.join(setup_dir, model_file))
                    else:
                        osimModelPath = model_file

            if not ikOutputPath:
                coord_elem = root.find('.//coordinates_file')
                if coord_elem is not None and coord_elem.text:
                    coord_file = coord_elem.text
                    if not os.path.isabs(coord_file):
                        ikOutputPath = os.path.normpath(os.path.join(setup_dir, coord_file))
                    else:
                        ikOutputPath = coord_file

            if not grfXmlPath:
                grf_elem = root.find('.//external_loads_file')
                if grf_elem is not None and grf_elem.text:
                    grf_file = grf_elem.text
                    if not os.path.isabs(grf_file):
                        grfXmlPath = os.path.normpath(os.path.join(setup_dir, grf_file))
                    else:
                        grfXmlPath = grf_file
        except Exception as e:
            print(f"Warning: Could not read parameters from setup XML: {e}")

    # Fall back to prompting if parameters are still missing
    if not osimModelPath:
        osimModelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')
    if not ikOutputPath:
        ikOutputPath = input("Enter the path to the Inverse Kinematics output file (.mot): ").strip('"')
    if not grfXmlPath:
        grfXmlPath = input("Enter the path to the Ground Reaction Forces XML file (.xml): ").strip('"')
    if not setupXmlPath:
        setupXmlPath = input("Enter the path to save the Inverse Dynamics setup XML file (.xml): ").strip('"')

    resultsDir = os.path.dirname(os.path.abspath(setupXmlPath))
    
    if not os.path.exists(osimModelPath):
        raise FileNotFoundError(f"OpenSim model file not found: {osimModelPath}")
    
    if not os.path.exists(ikOutputPath):
        raise FileNotFoundError(f"Inverse Kinematics motion file not found: {ikOutputPath}")

    if not os.path.exists(grfXmlPath):
        raise FileNotFoundError(f"Ground Reaction Forces XML file not found: {grfXmlPath}")
    
    if not os.path.exists(resultsDir):
        os.makedirs(resultsDir)
    
    # Load the model
    print(f"Loading OpenSim model from {osimModelPath}")
    model = load_model(osimModelPath)
    model.initSystem()

    # Load the motion data
    motion = osim.Storage(ikOutputPath)

    # Create the Inverse Dynamics tool
    idTool = osim.InverseDynamicsTool()
    idTool.setModel(model)
    idTool.setOutputGenForceFileName("inverse_dynamics.sto") # Output file name for the forces
    idTool.setModelFileName(os.path.relpath(osimModelPath, start=os.path.dirname(setupXmlPath)))
    idTool.setCoordinatesFileName(os.path.relpath(ikOutputPath, start=os.path.dirname(setupXmlPath)))
    idTool.setStartTime(motion.getFirstTime()) # Start time
    idTool.setEndTime(motion.getLastTime()) # end time
    idTool.setExternalLoadsFileName(os.path.relpath(grfXmlPath, start=os.path.dirname(setupXmlPath)))
    idTool.setResultsDir(os.path.relpath(resultsDir, start=os.path.dirname(setupXmlPath)))
    
    # Set lowpass filter frequency
    idTool.setLowpassCutoffFrequency(6)
    
    # Print the setup to XML
    idTool.printToXML(setupXmlPath)
    print(f"Inverse Dynamics setup saved to {setupXmlPath}")
    
    # Load xml and edit forces to exclude
    xml = utils.read_xml(setupXmlPath)
    xml.find('.//forces_to_exclude').text = 'Muscles'
    utils.save_pretty_xml(xml, setupXmlPath)

    # Reload tool from xml
    idTool = osim.InverseDynamicsTool(setupXmlPath)
    idTool.printToXML(setupXmlPath)  # Print to XML again to ensure changes are saved

    # Run the inverse dynamics calculation
    original_cwd = os.getcwd()
    try:
        os.chdir(resultsDir)
        with _osim_quiet_ctx():
            idTool.run()
        idTool.setModel(model)  # Set the model again after running
        print(f"Inverse Dynamics calculation completed. Results saved to {resultsDir}\\inverse_dynamics.sto")
    finally:
        # Restore original working directory
        try:
            os.chdir(original_cwd)
        except Exception as e:
            print(f"Warning: Could not restore original working directory: {e}")

@_quiet_console
def run_ma(osim_modelPath=None, ik_output=None,
         grf_xml=None, results_dir=None, coordinates=None,
         solve_equilibrium=False):
    if osim_modelPath is None:
        osim_modelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')
    if ik_output is None:
        ik_output = input("Enter the desired output path for the IK results (.mot): ").strip('"')
    if grf_xml is None:
        grf_xml = input("Enter the path to the GRF XML file (.xml): ").strip('"')
    
    ikParentDir = os.path.dirname(os.path.abspath(ik_output))
    # Write MA outputs to the caller-specified folder (muscle_analysis/ in the
    # subfoldered layout); fall back to the legacy MuscleAnalysis/ next to IK.
    resultsDir = os.path.abspath(results_dir) if results_dir else os.path.join(ikParentDir, 'MuscleAnalysis')
    setup_xml = os.path.join(resultsDir, 'setup_MA.xml')
    

    if not os.path.exists(osim_modelPath):
        raise FileNotFoundError(f"OpenSim model file not found: {osim_modelPath}")
    
    if not os.path.exists(ik_output):
        raise FileNotFoundError(f"Inverse Kinematics motion file not found: {ik_output}")
    
    if not os.path.exists(grf_xml):
        raise FileNotFoundError(f"Ground Reaction Forces XML file not found: {grf_xml}")
        
    if not os.path.exists(resultsDir):
        os.makedirs(resultsDir, exist_ok=True)
    
    # Load the model
    print(f"Loading OpenSim model from {osim_modelPath}")
    model = load_model(osim_modelPath)
    model.initSystem()

    # Load the motion data
    motion = osim.Storage(ik_output)

    # Create a MuscleAnalysis object
    muscleAnalysis = osim.MuscleAnalysis()
    muscleAnalysis.setModel(model)
    muscleAnalysis.setStartTime(motion.getFirstTime())
    muscleAnalysis.setEndTime(motion.getLastTime())

    # Restrict MA to the coordinates we actually use. By default MuscleAnalysis
    # computes moment arms + moments for EVERY coordinate (arms, lumbar, wrist,
    # mtp, ...), which is the bulk of MA compute and disk I/O (~80 .sto files).
    # Limiting to the lower-limb DOFs is a large speed-up with no loss for our
    # analyses/validation. The list can be overridden via the `coordinates`
    # argument or settings.MuscleAnalysisSettings.coordinates.
    if coordinates is None:
        try:
            coordinates = list(getattr(settings, 'MuscleAnalysisSettings', None)
                               and settings.MuscleAnalysisSettings.coordinates or [])
        except Exception:
            coordinates = []
        if not coordinates:
            coordinates = ['hip_flexion', 'hip_adduction', 'hip_rotation',
                           'knee_angle', 'knee_adduction', 'ankle_angle',
                           'subtalar_angle']
    try:
        cs = model.getCoordinateSet()
        model_names = {cs.get(i).getName() for i in range(cs.getSize())}
        want = []
        for base in coordinates:
            cands = [base] if base in model_names else [f'{base}_r', f'{base}_l']
            for nm in cands:
                if nm in model_names and nm not in want:
                    want.append(nm)
        if want:
            arr = osim.ArrayStr()
            for nm in want:
                arr.append(nm)
            muscleAnalysis.setCoordinates(arr)
            print(f"MuscleAnalysis restricted to {len(want)} coordinates: {want}")
    except Exception as _e:
        print(f"Warning: could not restrict MuscleAnalysis coordinates ({_e}); "
              "computing all.")

    # Create the muscle analysis tool
    maTool = osim.AnalyzeTool()
    maTool.setModel(model)
    maTool.setModelFilename(os.path.relpath(osim_modelPath,  start=os.path.dirname(setup_xml)))
    maTool.setLowpassCutoffFrequency(6)
    maTool.setCoordinatesFileName(os.path.relpath(ik_output, start=os.path.dirname(setup_xml)))
    maTool.setName('')
    maTool.setMaximumNumberOfSteps(20000)
    maTool.setStartTime(motion.getFirstTime())
    maTool.setFinalTime(motion.getLastTime())
    maTool.getAnalysisSet().cloneAndAppend(muscleAnalysis)
    maTool.setResultsDir(os.path.relpath(resultsDir, start=os.path.dirname(setup_xml)))
    maTool.setInitialTime(motion.getFirstTime())
    maTool.setFinalTime(motion.getLastTime())
    maTool.setExternalLoadsFileName(os.path.relpath(grf_xml, start=os.path.dirname(setup_xml)))
    # With equilibrium OFF the tool never solves the fibre/tendon force
    # balance, so _MuscleAnalysis_FiberLength.sto comes back at the muscle's
    # INITIAL fibre length for every frame -- 0.1000 m for every muscle in
    # every model -- and FiberVelocity is then the derivative of a flat line,
    # reaching 631 m/s. Moment arms, MTU length and the kinematic outputs are
    # unaffected, which is why this went unnoticed: only the fibre columns are
    # wrong. Turn it on when a fibre-level quantity is actually wanted; it is
    # slower, and with a coordinates file and no states OpenSim solves at a
    # default activation, so the result is a kinematically consistent fibre
    # length rather than an activation-specific one.
    maTool.setSolveForEquilibrium(bool(solve_equilibrium))
    maTool.setReplaceForceSet(False)
    maTool.setMaximumNumberOfSteps(20000)
    maTool.setOutputPrecision(8)
    maTool.setMaxDT(1)
    maTool.setMinDT(1e-008)
    maTool.setErrorTolerance(1e-005)
    maTool.removeControllerSetFromModel()
    maTool.setLowpassCutoffFrequency(6)
    maTool.printToXML(setup_xml)

    # Reload analysis from xml
    maTool = osim.AnalyzeTool(setup_xml)
    try:
        maTool.getModel().set_assembly_accuracy(_assembly_accuracy())
    except Exception:
        pass
    maTool.getModel().initSystem()
    # Run the muscle analysis calculation
    original_cwd = os.getcwd()
    try:
        os.chdir(resultsDir)
        maTool.run()
    finally:
        # Restore original working directory
        try:
            os.chdir(original_cwd)
        except Exception as e:
            print(f"Warning: Could not restore original working directory: {e}")

_RESIDUAL_NAMES = ("FX", "FY", "FZ", "MX", "MY", "MZ")


def reserve_actuator_plan(model, actuators_path, model_path=""):
    """Decide whether SO's reserve actuators come from the MODEL or from a file.

    They must come from exactly ONE of the two. StaticOptimization runs with
    useModelForceSet(True) and ALSO appends whatever force-set files it is
    given, so an actuator present in both is created TWICE: two independent
    actuators on the same coordinate. That halves the effective cost of using a
    reserve and doubles the reserve torque available, and nothing warns.

    Present in NEITHER is worse, and quieter. SO then has nothing to absorb the
    difference between the muscle moments and the inverse-dynamics moments, so
    it drives the muscles to whatever it takes. Measured case: a walking hip
    contact force of 26 BW against a true 5.4, gastrocnemius off by 5.9 kN, and
    no error, warning or missing file anywhere -- the only visible symptom was
    the force file carrying 128 columns instead of 144.

    -> ("model", note)  skip the append
       ("file",  note)  append, as before
    Raises RuntimeError when neither source has them, or when they are split
    across both.
    """
    import re as _re
    have = set()
    fs = model.getForceSet()
    for i in range(fs.getSize()):
        n = fs.get(i).getName()
        if n.endswith("_reserve") or n in _RESIDUAL_NAMES:
            have.add(n)

    want, file_state = set(), "missing"
    if actuators_path and os.path.exists(actuators_path):
        file_state = "present but empty"
        try:
            with open(actuators_path, encoding="utf-8", errors="replace") as _fh:
                _txt = _fh.read()
            want = set(_re.findall(
                r'<(?:Coordinate|Point|Torque)Actuator name="([^"]+)"', _txt))
            if want:
                file_state = "%d actuator(s)" % len(want)
        except OSError:
            file_state = "unreadable"

    if have and want:
        both = have & want
        if both == want:
            return "model", ("%d already in the model; NOT appending %s "
                             "(appending would create each one twice)"
                             % (len(have), os.path.basename(actuators_path)))
        raise RuntimeError(
            "[SO ERROR] reserve actuators are SPLIT across the model and the "
            "force-set file; the overlap would be duplicated.\n"
            "  model only : %s\n"
            "  file only  : %s\n"
            "  in both    : %s\n"
            "Put the whole set in one place -- all in the model, or all in %s."
            % (sorted(have - want), sorted(want - have), sorted(both),
               actuators_path))

    if have:
        return "model", ("%d in the model (force-set file: %s); nothing appended"
                         % (len(have), file_state))
    if want:
        return "file", ("%d appended from %s"
                        % (len(want), os.path.basename(actuators_path)))

    raise RuntimeError(
        "[SO ERROR] no reserve or residual actuators anywhere -- static "
        "optimisation cannot run honestly.\n"
        "  model : %s\n"
        "          contains no *_reserve and none of FX/FY/FZ/MX/MY/MZ\n"
        "  file  : %s\n"
        "          %s\n"
        "Without them SO has nothing to absorb the muscle-moment vs ID-moment "
        "difference and will drive the muscle forces to compensate, silently. "
        "Add the actuators to the model, or restore the force-set file."
        % (model_path or "(unnamed)", actuators_path or "(none given)",
           file_state))


@_quiet_console
def run_so(osim_modelPath=None, ik_output=None, grf_xml=None,
           setup_xml=None, actuators=None, resultsDir=None):
    if not osim_modelPath:
        osim_modelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')

    if not ik_output:
        ik_output = input("Enter the desired output path for the IK results (.mot): ").strip('"')

    if not grf_xml:
        grf_xml = input("Enter the path to the GRF XML file (.xml): ").strip('"')

    if not setup_xml:
        setup_xml = input("Enter the path to the setup XML file (.xml): ").strip('"')

    if not actuators:
        actuators = input("Enter the path to the actuators file (.xml): ").strip('"')

    if not resultsDir:
        resultsDir = os.path.dirname(ik_output)

    # Pre-flight file existence checks
    errors = []
    if not os.path.exists(osim_modelPath):
        errors.append(f"Model file not found: {osim_modelPath}")
    if not os.path.exists(ik_output):
        errors.append(f"IK output file not found: {ik_output}")
    if not os.path.exists(grf_xml):
        errors.append(f"GRF XML file not found: {grf_xml}")
    # A missing actuator file is NOT fatal on its own any more: the reserve
    # actuators may live in the model instead. reserve_actuator_plan() below
    # raises if they are in neither place, which is the condition that matters.

    if errors:
        error_msg = "SO Pre-flight Check Failed:\n" + "\n".join(f"  - {err}" for err in errors)
        raise RuntimeError(error_msg)

    if not os.path.exists(resultsDir):
        os.makedirs(resultsDir)

    # Load the model
    print(f"Loading OpenSim model from {osim_modelPath}")

    model = load_model(osim_modelPath)
    # model.initSystem()

    # load the motion data
    motion = osim.Storage(ik_output)

    # Create a StaticOptimization object
    so = osim.StaticOptimization()
    so.setStartTime(motion.getFirstTime())
    so.setEndTime(motion.getLastTime())
    so.setInDegrees(True)
    so.setUseMusclePhysiology(True)
    so.setUseModelForceSet(True)
    
    
    # Create analyze tool for static optimization
    so_analyze_tool = osim.AnalyzeTool()
    so_analyze_tool.setName("SO")

    # Set model file, motion files and external load file names
    so_analyze_tool.setModelFilename(os.path.relpath(osim_modelPath, start=os.path.dirname(setup_xml)))
    so_analyze_tool.setCoordinatesFileName(os.path.relpath(ik_output, start=os.path.dirname(setup_xml)))
    so_analyze_tool.setExternalLoadsFileName(os.path.relpath(grf_xml, start=os.path.dirname(setup_xml)))
    so_analyze_tool.setReplaceForceSet(False)
    _res_src, _res_note = reserve_actuator_plan(model, actuators, osim_modelPath)
    print(f"[SO] reserve actuators: {_res_note}")
    if _res_src == "file":
        so_analyze_tool.getForceSetFiles().append(
            os.path.relpath(actuators, start=os.path.dirname(setup_xml)))

    so_analyze_tool.setLowpassCutoffFrequency(6)
    
    # Add StaticOptimization analysis to the tool
    so_analyze_tool.updAnalysisSet().cloneAndAppend(so)

    # Configure analyze tool
    so_analyze_tool.setReplaceForceSet(False)
    so_analyze_tool.setStartTime(motion.getFirstTime())
    so_analyze_tool.setFinalTime(motion.getLastTime())

    # Set results directory
    so_analyze_tool.setResultsDir(os.path.relpath(resultsDir, start=os.path.dirname(setup_xml)))

    # Print configuration to XML file
    so_analyze_tool.printToXML(setup_xml)
    print("\n \n Static Optimization setup saved to:", setup_xml)
    
    # change optimizer_max_iterations in the xml file
    xml = utils.read_xml(setup_xml)
    static_opt = xml.getroot().find('.//StaticOptimization/optimizer_max_iterations')
    static_opt.text = '100'  # Set to 10 iterations
    utils.save_pretty_xml(xml, setup_xml)
    
    # run the Static Optimization
    so_analyze_tool = osim.AnalyzeTool(setup_xml)
    original_cwd = os.getcwd()
    try:
        os.chdir(resultsDir)
        so_analyze_tool.run()
        print(f"Static Optimization calculation completed. Results saved to {resultsDir}")
    except Exception as e:
        print(f"Error during Static Optimization: {e}")
    finally:
        # Restore original working directory
        try:
            os.chdir(original_cwd)
        except Exception as e:
            print(f"Warning: Could not restore original working directory: {e}")

@_quiet_console
def run_jra(osim_modelPath=None, ik_output=None,
         grf_xml=None, setup_xml=None, actuators=None,
         muscle_force_path=None, saveFileName=None):
    if not osim_modelPath:
        osim_modelPath = input("Enter the path to the OpenSim model file (.osim): ").strip('"')
    if not ik_output:
        ik_output = input("Enter the path to the coordinates motion file (.mot or .trc): ").strip('"')
    if not grf_xml:
        grf_xml = input("Enter the path to the external loads file (.xml): ").strip('"')
    if not setup_xml:
        setup_xml = input("Enter the path to save the JRA setup XML file (.xml): ").strip('"')
    if not muscle_force_path:
        muscle_force_path = input("Enter the path to the muscle forces file (.sto): ").strip('"')
    
    # Results + intermediate output belong next to the JRA SETUP file
    # (joint_contact_forces/), not next to the coordinates file
    # (external_biomechanics/). Derive from setup_xml, falling back to ik_output.
    setup_xml_parent = os.path.dirname(os.path.abspath(setup_xml)) if setup_xml \
        else os.path.dirname(os.path.abspath(ik_output))

    # start model
    osimModel = _quiet_model(osim_modelPath)
    
    # Get mot data to determine time range
    motData = osim.Storage(ik_output)

    # Get initial and intial time
    initial_time = motData.getFirstTime()
    final_time = motData.getLastTime()
    
    # start joint reaction analysis
    jr = osim.JointReaction(setup_xml)
    
    # add muscle forces file name to joint reaction analysis
    jr.setName('JRA')
    
    # define JRA 
    inFrame = osim.ArrayStr()
    onBody = osim.ArrayStr()
    jointNames = osim.ArrayStr()
    inFrame.set(0, 'child')
    onBody.set(0, 'child')
    jointNames.set(0, 'all')

    jr.setInFrame(inFrame)
    jr.setOnBody(onBody)
    jr.setJointNames(jointNames)

    # Set other parameters as needed
    jr.setStartTime(initial_time)
    jr.setEndTime(final_time)
    jr.setForcesFileName(os.path.abspath(muscle_force_path))

    # add to analysis tool
    analyzeTool_JR = create_analysis_tool(marker_trc = ik_output,
                                          externalloadsfile = grf_xml,
                                          osim_modelPath = osim_modelPath, 
                                          results_directory = setup_xml_parent, 
                                          actuators=actuators)
    
    analyzeTool_JR.setName('Analyse')
    analyzeTool_JR.getAnalysisSet().cloneAndAppend(jr)
    osimModel.addAnalysis(jr)

    # save setup file, rewrite its file paths RELATIVE to the setup's own dir
    # (portable), then reload so OpenSim resolves them against that dir.
    analyzeTool_JR.printToXML(setup_xml)
    relativise_setup_xml(setup_xml)
    analyzeTool_JR = osim.AnalyzeTool(setup_xml)
    # JRA's AnalyzeTool reloads the model from the setup XML, so the looser
    # assembly accuracy set elsewhere is lost -> the coupled (walker/Lerner) knee
    # trips SimTK's 1e-10 assembler tolerance and spams recoverable [error] lines.
    # Re-apply the project assembly accuracy on JRA's own model copy.
    try:
        analyzeTool_JR.getModel().set_assembly_accuracy(_assembly_accuracy())
    except Exception:
        pass
    print('jra for', setup_xml)
    analyzeTool_JR.run()
    
    # rename output file
    output_jra_file = os.path.join(setup_xml_parent, 'Analyse_JRA_ReactionLoads.sto')
    if saveFileName:
        new_jra_file = os.path.abspath(saveFileName)
        if os.path.exists(output_jra_file) and new_jra_file != output_jra_file:
            if os.path.exists(new_jra_file):
                os.remove(new_jra_file)
            os.rename(output_jra_file, new_jra_file)
            print(f"Joint Reaction Analysis results saved to: {new_jra_file}")
    else:
        if os.path.exists(output_jra_file):
            print(f"Joint Reaction Analysis results saved to: {output_jra_file}")

def run_emg_normalise(target_emg_path=None, normalise_emg_list=None):
    """
    Normalises EMG data based on a target EMG file.
    The target EMG file is used to scale the other EMG files in the list.
    """
    
    if not target_emg_path:
        target_emg_path = input("Enter the path to the target EMG .mot file to normalise: ").strip('"')
        
    if not normalise_emg_list:
        normalise_emg_list = []
        print("Enter paths to EMG .mot files to use for normalisation (one per line). Enter an empty line to finish:")
        while True:
            emg_file = input().strip('"')
            if emg_file == "":
                break
            if os.path.exists(emg_file):
                normalise_emg_list.append(emg_file)
            else:
                print(f"File not found: {emg_file}. Please try again.")
    
    target_emg = utils.load_any_data_file(target_emg_path)
    max_values = pd.DataFrame(columns=target_emg.columns)

    # Calculate the max of each EMG channel in normalise_emg_list
    for emg_file in normalise_emg_list:
        if not os.path.exists(emg_file):
            utils.print_to_log(f"EMG file not found: {emg_file}")
            continue
        emg_data = utils.load_any_data_file(emg_file)
        if emg_data is not None:
            max_values = pd.concat([max_values, pd.DataFrame([emg_data.max()])], ignore_index=True)
        else:
            print(f"Warning: Could not load EMG data from {emg_file}")
            
    if max_values.empty:
        utils.print_to_log("No valid EMG data found in the provided list.")
    
    
    if target_emg is None:
        utils.print_to_log(f"Target EMG file not found or could not be loaded: {target_emg_path}")

    
    # Normalise the target EMG to its own max values
    max_per_column = max_values.max(axis=0)
    target_emg_norm = target_emg.divide(max_per_column, axis=1)
    target_emg_norm['time'] = target_emg['time']  # Ensure time column is preserved
    
    # Save the normalised target EMG
    ext = os.path.splitext(target_emg_path)[1]
    savePath = os.path.abspath(target_emg_path.replace(ext, f'_normalised{ext}'))   
    utils.write_sto_file(dataFrame=target_emg_norm, 
                         file_path=savePath)

    utils.print_to_log(f"Normalised EMG data saved to: {savePath}")

def run_iaa(osim_modelPath=None, ik_output=None, grf_xml=None, setup_file_path=None, so_controls_file=None, actuators=None, setup_xml=None):
    """
    Run an Induced Acceleration Analysis (IAA) using OpenSim.
    """

    if os.path.exists(setup_xml):
        try:
            tool = osim.AnalyzeTool(setup_xml)
            tool.run()
            utils.print_to_log(f"IAA run successfully with existing setup XML: {setup_xml}")
            return
        except Exception as e:
            print(f"Error running IAA with existing setup XML: {e}")
            print("Falling back to creating a new IAA tool.")
            utils.print_to_log(f"Error running IAA with existing setup XML: {e}. Falling back to creating a new IAA tool.")
    
    try:
        tool = create_iaa_tool(osim_modelPath, ik_output, grf_xml, setup_file_path, so_controls_file, actuators)
        tool.run()
        utils.print_to_log("IAA run successfully.")
    except Exception as e:
        print(f"Error running IAA: {e}")
        utils.print_to_log(f"Error running IAA: {e}")

# --- Residual Reduction Algorithm (RRA) ---
def run_rra(osim_modelPath=None, ik_output=None, grf_xml=None, actuators=None, setup_xml=None, results_dir=None):
    """
    Run Residual Reduction Algorithm (RRA) using OpenSim.

    RRA is used to reduce the residual forces and moments at the pelvis by adjusting
    body mass and inertia properties or applying model-wide kinematic adjustments.

    Args:
        osim_modelPath: Path to the OpenSim model file
        ik_output: Path to inverse kinematics output file (.mot)
        grf_xml: Path to ground reaction force XML file
        actuators: Path to actuators setup file
        setup_xml: Path to RRA setup XML file (if already created)
        results_dir: Directory for results output
    """
    try:
        print("Starting Residual Reduction Algorithm (RRA)...")

        if setup_xml and os.path.exists(setup_xml):
            # Use existing RRA setup file
            try:
                tool = osim.RRATool(setup_xml)
                model = _quiet_model(osim_modelPath)
                tool.setModel(model)
                tool.run()
                utils.print_to_log("RRA completed successfully using existing setup file.")
                print("RRA calculation completed.")
                return
            except Exception as e:
                print(f"Error running RRA with existing setup: {e}")
                utils.print_to_log(f"Error running RRA with existing setup: {e}")

        # Create a new RRA tool if setup_xml not provided
        if not osim_modelPath or not ik_output:
            raise ValueError("osim_modelPath and ik_output are required for RRA")

        model = _quiet_model(osim_modelPath)
        state = model.initSystem()

        # Create RRA tool
        rra_tool = osim.RRATool()
        rra_tool.setModel(model)
        rra_tool.setInitialTime(0.0)
        rra_tool.setFinalTime(0.0)

        # Set kinematics from IK output
        rra_tool.setKinematicsFileName(ik_output)

        # Set external loads if provided
        if grf_xml and os.path.exists(grf_xml):
            rra_tool.setExternalLoadsFileName(grf_xml)

        # Set output directory
        if results_dir:
            rra_tool.setOutputModelFileName(os.path.join(results_dir, "rra_adjusted_model.osim"))
            rra_tool.setResultsDir(results_dir)

        # Run RRA
        rra_tool.run()
        utils.print_to_log("RRA completed successfully.")
        print("RRA calculation completed. Results saved.")

    except Exception as e:
        error_msg = f"Error running RRA: {str(e)}"
        print(error_msg)
        utils.print_to_log(error_msg)
        raise

# --- Computed Muscle Control (CMC) ---
def run_cmc(osim_modelPath=None, ik_output=None, grf_xml=None, emg_file=None, actuators=None, setup_xml=None, results_dir=None):
    """
    Run Computed Muscle Control (CMC) using OpenSim.

    CMC uses an optimization approach to compute muscle excitations that produce the desired kinematics
    while minimizing a cost function, typically the sum of squared muscle activations.

    Args:
        osim_modelPath: Path to the OpenSim model file
        ik_output: Path to inverse kinematics output file (.mot)
        grf_xml: Path to ground reaction force XML file
        emg_file: Path to EMG data file for tracking constraints (optional)
        actuators: Path to actuators setup file
        setup_xml: Path to CMC setup XML file (if already created)
        results_dir: Directory for results output
    """
    try:
        print("Starting Computed Muscle Control (CMC)...")

        if setup_xml and os.path.exists(setup_xml):
            # Use existing CMC setup file
            try:
                tool = osim.CMCTool(setup_xml)
                # Do NOT setModel() here: CMCTool(setup) already built its model
                # WITH force_set_files applied; replacing it would silently drop
                # the residual/reserve actuators. The setup's <model_file> rules.
                tool.run()
                utils.print_to_log("CMC completed successfully using existing setup file.")
                print("CMC calculation completed.")
                return
            except Exception as e:
                print(f"Error running CMC with existing setup: {e}")
                utils.print_to_log(f"Error running CMC with existing setup: {e}")

        # Create a new CMC tool if setup_xml not provided
        if not osim_modelPath or not ik_output:
            raise ValueError("osim_modelPath and ik_output are required for CMC")

        model = _quiet_model(osim_modelPath)
        state = model.initSystem()

        # Create CMC tool
        cmc_tool = osim.CMCTool()
        cmc_tool.setModel(model)
        cmc_tool.setInitialTime(0.0)
        cmc_tool.setFinalTime(0.0)

        # Set kinematics from IK output
        cmc_tool.setDesiredKinematicsFileName(ik_output)

        # Set external loads if provided
        if grf_xml and os.path.exists(grf_xml):
            cmc_tool.setExternalLoadsFileName(grf_xml)

        # Set output directory
        if results_dir:
            cmc_tool.setResultsDir(results_dir)

        # Run CMC
        cmc_tool.run()
        utils.print_to_log("CMC completed successfully.")
        print("CMC calculation completed. Muscle excitations computed.")

    except Exception as e:
        error_msg = f"Error running CMC: {str(e)}"
        print(error_msg)
        utils.print_to_log(error_msg)
        raise

# --- Metabolic Cost Analysis (Energetics) ---
def run_energetics(osim_modelPath=None, ik_output=None, muscle_activations=None, setup_xml=None, results_dir=None):
    """
    Run Metabolic Cost Analysis (Energetics) using OpenSim.

    Computes the metabolic cost of a movement using muscle activations and kinematics.
    This uses the Metabolic Cost Analysis tool to estimate energy expenditure.

    Args:
        osim_modelPath: Path to the OpenSim model file
        ik_output: Path to inverse kinematics output file (.mot)
        muscle_activations: Path to muscle activation file (from CMC or SO)
        setup_xml: Path to Metabolic Cost Analysis setup XML file
        results_dir: Directory for results output
    """
    try:
        print("Starting Metabolic Cost Analysis (Energetics)...")

        # ------------------------------------------------------------------ #
        # Pre-flight checks
        # ------------------------------------------------------------------ #
        if not osim_modelPath or not os.path.exists(osim_modelPath):
            raise FileNotFoundError(f"Model file not found: {osim_modelPath}")
        if not ik_output or not os.path.exists(ik_output):
            raise FileNotFoundError(f"IK coordinates file not found: {ik_output}")

        if results_dir is None:
            results_dir = os.path.dirname(os.path.abspath(ik_output))
        os.makedirs(results_dir, exist_ok=True)

        # Absolute paths — the tool is run with cwd=results_dir below, so we keep
        # everything absolute to avoid relative-path surprises.
        osim_modelPath = os.path.abspath(osim_modelPath)
        ik_output = os.path.abspath(ik_output)
        if muscle_activations:
            muscle_activations = os.path.abspath(muscle_activations)

        # ------------------------------------------------------------------ #
        # Path A — an existing Metabolic Cost setup XML was supplied: use it.
        # ------------------------------------------------------------------ #
        if setup_xml and os.path.exists(setup_xml):
            try:
                tool = osim.AnalyzeTool(setup_xml)
                tool.setResultsDir(results_dir)
                original_cwd = os.getcwd()
                try:
                    os.chdir(results_dir)
                    tool.run()
                finally:
                    os.chdir(original_cwd)
                utils.print_to_log(
                    "Metabolic Cost Analysis completed using existing setup file.")
                print("Energetics calculation completed.")
                return
            except Exception as e:
                print(f"Existing energetics setup failed ({e}); rebuilding it.")
                utils.print_to_log(
                    f"Existing energetics setup failed ({e}); rebuilding it.")

        # ------------------------------------------------------------------ #
        # Path B — build a metabolic probe set + ProbeReporter from scratch.
        # ------------------------------------------------------------------ #
        model = _quiet_model(osim_modelPath)
        model.initSystem()

        # Attach an Umberger (2010) metabolic-energy probe covering every muscle.
        # All four rate components are reported (activation/maintenance,
        # shortening, mechanical work and basal), plus per-muscle breakdown.
        probe = osim.Umberger2010MuscleMetabolicsProbe()
        probe.setName("metabolics")
        for _setter, _val in (
            ("set_activation_maintenance_rate_on", True),
            ("set_shortening_rate_on",            True),
            ("set_basal_rate_on",                 True),
            ("set_mechanical_work_rate_on",       True),
            ("set_report_total_metabolics_only",  False),
            ("setOperation",                      "value"),
        ):
            try:
                getattr(probe, _setter)(_val)
            except Exception:
                pass  # property name varies slightly across OpenSim versions

        muscles = model.getMuscles()
        n_added = 0
        for i in range(muscles.getSize()):
            try:
                probe.addMuscle(muscles.get(i).getName(), 0.5)
                n_added += 1
            except Exception as e:
                print(f"  [warn] could not add muscle to metabolics probe: {e}")
        if n_added == 0:
            raise RuntimeError("No muscles could be added to the metabolics probe.")
        print(f"  Metabolics probe covers {n_added} muscles.")

        model.addProbe(probe)
        model.finalizeConnections()

        # Persist the probe-augmented model next to the results so the setup XML
        # is self-contained and reproducible.
        model_with_probes = os.path.join(results_dir, "model_metabolics.osim")
        model.printToXML(model_with_probes)

        # Time window from the IK motion.
        motion = osim.Storage(ik_output)
        initial_time = motion.getFirstTime()
        final_time = motion.getLastTime()

        # Build the AnalyzeTool around the in-memory (probe-augmented) model.
        tool = osim.AnalyzeTool(model)
        tool.setName("energetics")
        tool.setModelFilename(model_with_probes)
        tool.setCoordinatesFileName(ik_output)
        tool.setInitialTime(initial_time)
        tool.setFinalTime(final_time)
        tool.setLowpassCutoffFrequency(6.0)

        # Feed muscle activations (from Static Optimization) as the model states
        # so the probe evaluates real per-frame activations; solve fibre
        # equilibrium from the posed kinematics.
        if muscle_activations and os.path.exists(muscle_activations):
            tool.setStatesFileName(muscle_activations)
            try:
                tool.setSolveForEquilibrium(True)
            except Exception:
                pass
        else:
            print("  [warn] No SO activation file supplied — metabolic rates "
                  "will be based on default activation.")

        # Attach the ProbeReporter so probe outputs are written to .sto.
        probe_reporter = osim.ProbeReporter(model)
        probe_reporter.setName("ProbeReporter")
        probe_reporter.setStartTime(initial_time)
        probe_reporter.setEndTime(final_time)
        tool.updAnalysisSet().cloneAndAppend(probe_reporter)

        tool.setResultsDir(results_dir)

        # Save the setup for the record/debugging.
        if not setup_xml:
            setup_xml = os.path.join(results_dir, "setup_Energetics.xml")
        tool.printToXML(setup_xml)
        print(f"  Energetics setup saved to: {setup_xml}")

        # Run with cwd inside results_dir so all relative outputs land there.
        original_cwd = os.getcwd()
        try:
            os.chdir(results_dir)
            tool.run()
        finally:
            try:
                os.chdir(original_cwd)
            except Exception:
                pass

        out_file = os.path.join(results_dir, "energetics_ProbeReporter_probes.sto")
        utils.print_to_log(
            f"Metabolic Cost Analysis completed. Output: {out_file}")
        print(f"Energetics calculation completed. Metabolic cost written to "
              f"{results_dir}")

    except Exception as e:
        error_msg = f"Error running Metabolic Cost Analysis: {str(e)}"
        print(error_msg)
        utils.print_to_log(error_msg)
        raise

# --- Body Kinematics Analysis ---
def run_body_kinematics(osim_modelPath=None, ik_output=None, bodies=None, setup_xml=None, results_dir=None):
    """
    Run Body Kinematics Analysis using OpenSim.

    Computes body kinematics (position, velocity, acceleration) for specified bodies
    during a movement based on the inverse kinematics solution.

    Args:
        osim_modelPath: Path to the OpenSim model file
        ik_output: Path to inverse kinematics output file (.mot)
        bodies: List of body names to analyze (default: all bodies)
        setup_xml: Path to Body Kinematics setup XML file
        results_dir: Directory for results output
    """
    try:
        print("Starting Body Kinematics Analysis...")

        if setup_xml and os.path.exists(setup_xml):
            # Use existing Body Kinematics setup file
            try:
                tool = osim.AnalyzeTool(setup_xml)
                model = _quiet_model(osim_modelPath)
                tool.setModel(model)
                tool.run()
                utils.print_to_log("Body Kinematics Analysis completed successfully using existing setup file.")
                print("Body Kinematics calculation completed.")
                return
            except Exception as e:
                print(f"Error running Body Kinematics with existing setup: {e}")
                utils.print_to_log(f"Error running Body Kinematics with existing setup: {e}")

        # Create a new Body Kinematics Analysis if setup_xml not provided
        if not osim_modelPath or not ik_output:
            raise ValueError("osim_modelPath and ik_output are required for Body Kinematics Analysis")

        model = _quiet_model(osim_modelPath)
        state = model.initSystem()

        # Create AnalyzeTool for body kinematics
        analyze_tool = osim.AnalyzeTool()
        analyze_tool.setModel(model)

        # Set kinematics from IK output
        analyze_tool.setCoordinatesFileName(ik_output)

        # Get body set from model
        body_set = model.getBodySet()
        if bodies is None:
            # Analyze all bodies by default
            bodies = [body_set.get(i).getName() for i in range(body_set.getSize())]

        # Set output directory
        if results_dir:
            analyze_tool.setResultsDir(results_dir)

        # Run analysis
        analyze_tool.run()
        utils.print_to_log("Body Kinematics Analysis completed successfully.")
        print(f"Body Kinematics calculation completed for {len(bodies)} bodies.")

    except Exception as e:
        print(f"Error in Body Kinematics Analysis: {e}")
        utils.print_to_log(f"Error in Body Kinematics Analysis: {e}")
        raise


if __name__ == "__main__":

    class _Tee:
        """Write to both the original stdout and a log file simultaneously."""
        def __init__(self, log_file):
            self._stdout = sys.stdout
            self._log = log_file

        def write(self, data):
            self._stdout.write(data)
            self._stdout.flush()
            self._log.write(data)
            self._log.flush()

        def flush(self):
            self._stdout.flush()
            self._log.flush()

        def __getattr__(self, name):
            return getattr(self._stdout, name)

    LocalFuncs = [f for f in dir() if callable(globals()[f])]

    while True:
        print("Available commands:", LocalFuncs)
        command = input("Enter command: ")

        if command not in LocalFuncs:
            print("Invalid command. Please try again.")
            continue

        log_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs'))
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = os.path.join(log_dir, f'openSim_log_{timestamp}.log')

        with open(log_filename, 'w', encoding='utf-8') as _lf:
            _orig_stdout = sys.stdout
            sys.stdout = _Tee(_lf)
            _osim_sink = False
            try:
                osim.Logger.addFileSink(log_filename)
                _osim_sink = True
            except Exception:
                pass
            try:
                print(f"--- openSim command: {command} | {timestamp} ---")
                globals()[command]()
                print("Command executed successfully.")
            except Exception as e:
                print(f"Error executing {command}: {e}")
            finally:
                if _osim_sink:
                    try:
                        osim.Logger.removeFileSink(log_filename)
                    except Exception:
                        pass
                sys.stdout = _orig_stdout

        print(f"Log saved to: {log_filename}")
