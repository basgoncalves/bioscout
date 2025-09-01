import subprocess
import os
import sys

def run(osim_version='4.5'):
    try:
        # Change directory to the OpenSim Python SDK
        opensim_sdk_path = rf'C:\OpenSim {osim_version}\sdk\Python'
        if not os.path.exists(opensim_sdk_path):
            raise FileNotFoundError(f"Path does not exist: {opensim_sdk_path}")


        os.chdir(opensim_sdk_path)
        print(f"Changed directory to: {opensim_sdk_path}")

        # Print the current working directory
        print(f"Current working directory: {os.getcwd()}")

        # Run the setup script for Windows Python 3.8
        print("Running setup script for Windows Python 3.8...")
        setup_script = 'setup_win_python38.py'
        
        command_list = [sys.executable, setup_script]
        print(f"Executing:")
        print(f"{' '.join(command_list)}") # Print the command as it would look in the shell
        
        subprocess.run(command_list, check=True, cwd=opensim_sdk_path) # Use list and specify cwd explicitly
        print(f"Executed: python {setup_script}")

        # Install the Python bindings
        print("Installing OpenSim Python bindings...")
        install_command_list = [sys.executable, '-m', 'pip', 'install', '.']
        print(f"Executing:")
        print(f"{' '.join(install_command_list)}") # Print the command
        subprocess.run(install_command_list, check=True, cwd=opensim_sdk_path) # Use list and specify cwd explicitly
        print("Executed: python -m pip install .")

        print("OpenSim Python bindings installation process completed successfully.")
        
        # change the venv\lib\site-packages\opensim\__init__.py install_path to the correct path in C:
        opensim_lib_path = os.path.join(sys.prefix, 'Lib', 'site-packages', 'opensim')
        with open(os.path.join(opensim_lib_path, '__init__.py'), 'r') as file:
            lines = file.readlines()
        
            # Find the line containing 'install_path' and ensure it exists
            string_to_find = 'install_path'
            matching_lines = [line for line in lines if string_to_find in line]
            if not matching_lines:
                raise ValueError(f"Expected line containing '{string_to_find}' not found in __init__.py")
            
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
    run(osim_version='4.4')