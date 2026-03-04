import subprocess
import os
import sys

def check_opensim_available_veersions():
    ''' function to check for available OpenSim versions in the default installation path on Windows or MacOS '''
    if sys.platform == "win32":
        base_path = "C:/OpenSim"
    elif sys.platform == "darwin":  # MacOS
        base_path = "/Applications/OpenSim"
    else:
        print("Unsupported operating system for this check.")
        return []
    available_versions = []
    # find any folders that start with base_path and have a version number after it
    for item in os.listdir(os.path.dirname(base_path)):
        if item.startswith(os.path.basename(base_path)) and os.path.isdir(os.path.join(os.path.dirname(base_path), item)):
            version = item[len(os.path.basename(base_path)):].strip()
            available_versions.append(version)
    return available_versions

def run(osim_version='4.5'):

    available_versions = check_opensim_available_veersions()
    if osim_version not in available_versions:
        print(f"Error: OpenSim version {osim_version} not found in the default installation path. Available versions: {available_versions}")
        return

    try:
        # Change directory to the OpenSim Python SDK
        opensim_sdk_path = rf'C:\OpenSim {osim_version}\sdk\Python'
        if not os.path.exists(opensim_sdk_path):
            raise FileNotFoundError(f"Path does not exist: {opensim_sdk_path}")


        os.chdir(opensim_sdk_path)
        print(f"Changed directory to: {opensim_sdk_path}")
        print(f"Current working directory: {os.getcwd()}")

        # Run the setup script for Windows Python 3.8
        print("Running setup script for Windows Python 3.8...")
        setup_script = 'setup_win_python38.py'
        
        command_list = [sys.executable, setup_script]
        print(f"Executing:")
        print(f"{' '.join(command_list)}")
        
        subprocess.run(command_list, check=True, cwd=opensim_sdk_path) 
        print(f"Executed: python {setup_script}")

        # Install the Python bindings as per the documentation
        print("Installing OpenSim Python...")
        install_command_list = [sys.executable, '-m', 'pip', 'install', '.']
        print(f"Executing:")
        print(f"{' '.join(install_command_list)}")
        subprocess.run(install_command_list, check=True, cwd=opensim_sdk_path) 
        print("Executed: python -m pip install .")

        print("OpenSim Python bindings installation process completed successfully.")
        
        # change the venv\lib\site-packages\opensim\__init__.py install_path to the correct path in C:
        opensim_lib_path = os.path.join(sys.prefix, 'Lib', 'site-packages', 'opensim')
        init_py_path = os.path.join(opensim_lib_path, '__init__.py')
        opensim_install_path = os.path.dirname(os.path.dirname(opensim_sdk_path))
        opensim_bin_path = os.path.join(opensim_install_path, 'bin').replace('\\', '/')
        
        with open(init_py_path, 'r') as file:
            lines = file.readlines()
        
            # Find the line containing 'install_path' and ensure it exists
            string_to_find = 'install_path'
            matching_lines = [line for line in lines if string_to_find in line]
            
            if not matching_lines:
                print(f"[WARNING] Expected line containing \"{string_to_find}\" not found in __init__.py \n Please check the file and update the install_path manually to: {init_py_path}")
                return
            
            idx = lines.index(matching_lines[0])  # Get the index of the first matching line
            line_text = lines[idx]
            
            # edit so install_path = opensim_install_path\bin
            opensim_install_path = os.path.dirname(os.path.dirname(opensim_sdk_path))
            lines[idx] = f'    install_path = r"{opensim_install_path}\\bin"\n'
            
            
        with open(os.path.join(opensim_lib_path, '__init__.py'), 'w') as file:
            file.writelines(lines)
        print("Updated install_path in __init__.py to the correct path.")
        
        

    except subprocess.CalledProcessError as e:
        print(f"Error during execution: {e}")
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}")
    except OSError as e:
        print(f"Error changing directory: {e}")

if __name__ == "__main__":

    print("Starting OpenSim Python bindings installation process...")
    print("Checking for available OpenSim versions...")
    print(f"Available OpenSim versions: {check_opensim_available_veersions()}")

    version = input("Enter the OpenSim version you want to install (e.g., 4.5): ")

    run(osim_version=version)