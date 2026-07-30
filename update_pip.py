# update_pip_prepare.py
import os
import shutil
import subprocess
import sys
import re
import pyperclip

# --- Configuration ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # Directory of this script
SETUP_PY_FILE = os.path.join(CURRENT_DIR, "setup.py") # Path to setup.py file
DIST_FOLDER = os.path.join(CURRENT_DIR, "dist") # Path to dist folder
PYTHON_EXECUTABLE = sys.executable # Use the python executing this script

# --- Helper Functions ---
def run_command(command, cwd=None):
    """Runs a command in the shell and prints output."""
    print(f"\n▶️ Running command: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            check=True,        # Raise exception on non-zero exit code
            capture_output=True, # Capture stdout/stderr
            text=True,         # Decode output as text
            cwd=cwd            # Set working directory if needed
        )
        print("✅ Command successful.")
        if process.stdout:
            print("--- Output ---")
            print(process.stdout.strip())
            print("--------------")
        if process.stderr:
            print("--- Error Output (stderr) ---")
            print(process.stderr.strip())
            print("---------------------------")
        return True
    except FileNotFoundError:
        print(f"❌ Error: Command not found: {command[0]}. Is it in your PATH?")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing command: {' '.join(command)}")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print("--- Output ---")
            print(e.stdout.strip())
            print("--------------")
        if e.stderr:
            print("--- Error Output (stderr) ---")
            print(e.stderr.strip())
            print("---------------------------")
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        return False

def clean_build_folder():
    """Deletes the build folder if it exists."""
    build_folder = os.path.join(CURRENT_DIR, "build")
    if os.path.isdir(build_folder):
        print(f"\n🧹 Cleaning '{build_folder}' directory...")
        try:
            shutil.rmtree(build_folder)
            print(f"✅ Successfully cleaned '{build_folder}'.")
        except Exception as e:
            print(f"❌ Error cleaning '{build_folder}': {e}")
            return False
    else:
        print(f"'{build_folder}' directory does not exist. No cleaning needed.")
    return True

def clean_dist_folder():
    """Deletes all files within the dist folder."""
    print(f"\n🧹 Cleaning '{DIST_FOLDER}' directory...")
    if os.path.isdir(DIST_FOLDER):
        try:
            # Check if directory is empty first
            if not os.listdir(DIST_FOLDER):
                 print(f"'{DIST_FOLDER}' is already empty.")
                 return True
                 
            # If not empty, remove contents
            for filename in os.listdir(DIST_FOLDER):
                file_path = os.path.join(DIST_FOLDER, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        print(f"   Deleted file: {file_path}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"   Deleted directory: {file_path}")
                except Exception as e:
                    print(f"❌ Failed to delete {file_path}. Reason: {e}")
                    return False
            print(f"✅ Successfully cleaned '{DIST_FOLDER}'.")
            return True
        except Exception as e:
            print(f"❌ Error cleaning '{DIST_FOLDER}': {e}")
            return False
    else:
        print(f"'{DIST_FOLDER}' directory does not exist. No cleaning needed.")
        # Optionally create the directory if it doesn't exist?
        # os.makedirs(DIST_FOLDER)
        # print(f"'{DIST_FOLDER}' directory created.")
        return True # Not an error if it doesn't exist

def clean_egg_info():
    """Delete any *.egg-info folders.

    setuptools merges an existing egg-info/SOURCES.txt into each build, so a
    stale entry (e.g. a bare directory) gets carried forward and can break the
    wheel build with 'can't copy ...: not a regular file'. Removing egg-info
    forces a clean regeneration every time.
    """
    print("\n🧹 Cleaning '*.egg-info' directories...")
    removed = False
    for name in os.listdir(CURRENT_DIR):
        if name.endswith(".egg-info"):
            path = os.path.join(CURRENT_DIR, name)
            if os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                    print(f"   Deleted: {path}")
                    removed = True
                except Exception as e:
                    print(f"❌ Failed to delete {path}. Reason: {e}")
                    return False
    if not removed:
        print("   No .egg-info directories found. No cleaning needed.")
    return True

def update_version_in_setup_py():
    """Prompts for new version and updates it in setup.py."""
    print(f"\n🔢 Updating version in '{SETUP_PY_FILE}'...")
    if not os.path.isfile(SETUP_PY_FILE):
        print(f"❌ Error: '{SETUP_PY_FILE}' not found in the current directory.")
        return False, None # Indicate failure and no version

    try:
        with open(SETUP_PY_FILE, 'r') as f:
            content = f.read()

        # Regex to find version = '...' or version = "..."
        version_pattern = r"__version__\s*=\s*['\"]([^'\"]*)['\"]"
        match = re.search(version_pattern, content)

        if not match:
            print(f"❌ Error: Could not find version pattern (e.g., version='x.y.z') in '{SETUP_PY_FILE}'.")
            return False, None

        current_version = match.group(1)
        print(f"Current version detected: {current_version}")

        while True:
            new_version = input(f"Enter the new version number (current is {current_version}): ").strip()
            if new_version:
                confirm = input(f"Set version to '{new_version}'? (y/n): ").lower()
                if confirm == 'y':
                    break
            else:
                print("Version cannot be empty.")

        # Replace the version in the content
        new_content = re.sub(version_pattern, f"__version__ = '{new_version}'", content, count=1)

        # Write the updated content back to the file
        with open(SETUP_PY_FILE, 'w') as f:
            f.write(new_content)

        print(f"✅ Successfully updated version in '{SETUP_PY_FILE}' to '{new_version}'.")
        return True, new_version # Indicate success and return new version

    except Exception as e:
        print(f"❌ Error updating version in '{SETUP_PY_FILE}': {e}")
        print("Please check the file manually in the path:" + SETUP_PY_FILE)
        print("New version == " + new_version)
        
        return True, new_version

# --- Main Script ---
print("🚀 Starting PyPI Package Preparation Script...")

# Step 5: Update twine (Automated)
success = run_command([PYTHON_EXECUTABLE, "-m", "pip", "install", "--upgrade", "twine"])
if not success:
    print("\n🛑 Script stopped due to error updating twine.")
    sys.exit(1)

# Step 6a: Clean the build folder (Automated)
success = clean_build_folder()
if not success:
    print("\n🛑 Script stopped due to error cleaning build folder.")
    sys.exit(1)

# Step 6b: Delete all files in the dist folder (Automated)
success = clean_dist_folder()
if not success:
    print("\n🛑 Script stopped due to error cleaning dist folder.")
    sys.exit(1)

# Step 6c: Delete stale *.egg-info so SOURCES.txt regenerates cleanly (Automated)
success = clean_egg_info()
if not success:
    print("\n🛑 Script stopped due to error cleaning egg-info.")
    sys.exit(1)

# Step 7: Update the version number in the setup.py file (Automated with prompt)
version_updated, new_version = update_version_in_setup_py()
if not version_updated:
    print("\n🛑 Script stopped due to error updating version in setup.py.")
    sys.exit(1)

# Step 8: Build the package (Automated)
# Uses PEP 517 build frontend — does not invoke setup.py directly
success = run_command([PYTHON_EXECUTABLE, "-m", "build"])
if not success:
    print("\n🛑 Script stopped due to error building the package.")
    sys.exit(1)

print("\n✅ Automated preparation steps completed successfully!")

# --- Manual Steps Reminder ---
print("\n📋 Manual Steps Required:")
print("-" * 25)
print(f"1.  **Configure/Verify Metadata in `pyproject.toml`:**")
print(f"    - Ensure project name, author, description, classifiers, URLs etc. are correct and up-to-date.")
print(f"    - Check dependencies listed here if you use `pyproject.toml` for them.")
print(f"\n2.  **Update `README.md`:**")
print(f"    - Add the new version number ({new_version}).")
print(f"    - Document any new features added.")
print(f"    - List any bug fixes.")
print(f"    - Update usage instructions if they have changed.")
print(f"\n3.  **Verify Dependencies in `requirements.txt` (or `pyproject.toml`):**")
print(f"    - Check if your dependencies are up-to-date.")
print(f"    - Consider using tools like `pip list --outdated` or `pip-review`.")
print(f"    - Test your package thoroughly after updating dependencies.")
print(f"\n4.  **Review Build Artifacts:**")
print(f"    - Check the contents of the '{DIST_FOLDER}' directory (e.g., the .tar.gz and .whl files).")
print(f"    - Ensure they contain the expected files and look correct.")
print(f"    - You can use `twine check dist/*` to perform some basic checks.")
print(f"\n5.  **Upload to PyPI (PyPI first recommended):**")
print(f"    - To upload to PyPI:")
print(f"      {PYTHON_EXECUTABLE} -m twine upload --repository pypi {DIST_FOLDER}/*")
print("-" * 25)
print("\n👍 Preparation complete. Please perform the manual steps above before uploading.")

# Bash-friendly upload command (forward slashes, no drive letter issues)
bash_cmd = "python -m twine upload --repository pypi dist/*"
print(f"\n💻 Bash-compatible upload command:\n   {bash_cmd}")

try:
    pyperclip.copy(bash_cmd)
    print("📋 Copied to clipboard.")
except Exception:
    pass
