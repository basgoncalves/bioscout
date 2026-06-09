"""
Dependency installer for Powerlifting Model Analysis App.

Automatically detects, downloads, and installs missing dependencies like OpenSim.
"""

import subprocess
import sys
import json
from typing import List, Dict, Optional
from urllib.request import urlopen
import importlib.util

# Handle packaging import gracefully
try:
    from packaging import version as pkg_version
except ImportError:
    # Fallback: simple version comparison
    pkg_version = None


class DependencyInstaller:
    """Manages installation of Python and system dependencies."""

    # Define key dependencies with their package names and PyPI URLs
    DEPENDENCIES = {
        'opensim': {
            'package_name': 'opensim-core',
            'import_name': 'opensim',
            'pypi_url': 'https://pypi.org/pypi/opensim-core/json',
            'critical': True,  # App won't work without this
            'description': 'OpenSim biomechanics modeling library'
        },
        'customtkinter': {
            'package_name': 'customtkinter',
            'import_name': 'customtkinter',
            'pypi_url': 'https://pypi.org/pypi/customtkinter/json',
            'critical': True,
            'description': 'Modern GUI framework'
        },
        'pyyaml': {
            'package_name': 'pyyaml',
            'import_name': 'yaml',
            'pypi_url': 'https://pypi.org/pypi/pyyaml/json',
            'critical': True,
            'description': 'YAML configuration file support'
        },
        'matplotlib': {
            'package_name': 'matplotlib',
            'import_name': 'matplotlib',
            'pypi_url': 'https://pypi.org/pypi/matplotlib/json',
            'critical': False,
            'description': 'Data visualization library'
        },
        'pandas': {
            'package_name': 'pandas',
            'import_name': 'pandas',
            'pypi_url': 'https://pypi.org/pypi/pandas/json',
            'critical': True,
            'description': 'Data analysis library (required for analysis)'
        },
        'numpy': {
            'package_name': 'numpy',
            'import_name': 'numpy',
            'pypi_url': 'https://pypi.org/pypi/numpy/json',
            'critical': True,
            'description': 'Numerical computing library'
        },
        'scipy': {
            'package_name': 'scipy',
            'import_name': 'scipy',
            'pypi_url': 'https://pypi.org/pypi/scipy/json',
            'critical': False,
            'description': 'Scientific computing library'
        },
        'cv2': {
            'package_name': 'opencv-python',
            'import_name': 'cv2',
            'pypi_url': 'https://pypi.org/pypi/opencv-python/json',
            'critical': True,
            'description': 'OpenCV computer vision library (required for video recording)'
        },
        'mediapipe': {
            'package_name': 'mediapipe',
            'import_name': 'mediapipe',
            'pypi_url': 'https://pypi.org/pypi/mediapipe/json',
            'critical': True,
            'description': 'Pose estimation library (required for video analysis)'
        }
    }

    def __init__(self, verbose: bool = True):
        """
        Initialize dependency installer.

        Args:
            verbose: Print detailed information
        """
        self.verbose = verbose

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[{level}] {message}")

    def is_installed(self, package: str) -> bool:
        """
        Check if a package is installed.

        Args:
            package: Package import name

        Returns:
            True if installed and importable
        """
        try:
            importlib.util.find_spec(package)
            return True
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    def get_available_versions(self, package_name: str) -> List[str]:
        """
        Fetch available versions from PyPI.

        Args:
            package_name: PyPI package name

        Returns:
            List of available versions, newest first
        """
        try:
            pypi_url = f'https://pypi.org/pypi/{package_name}/json'
            with urlopen(pypi_url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                versions = list(data['releases'].keys())
                # Filter out pre-releases
                stable_versions = [
                    v for v in versions
                    if not any(pre in v for pre in ['a', 'b', 'rc', 'dev'])
                ]
                # Sort by version number (newest first)
                if pkg_version:
                    stable_versions.sort(key=lambda x: pkg_version.parse(x), reverse=True)
                else:
                    # Fallback: simple string sort
                    stable_versions.sort(reverse=True)
                return stable_versions[:10]  # Return top 10 versions
        except Exception as e:
            self._log(f"Could not fetch versions for {package_name}: {e}", "WARNING")
            return []

    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """
        Install a package using pip.

        Args:
            package_name: Package name on PyPI
            version: Specific version to install (if None, installs latest)

        Returns:
            True if installation successful
        """
        try:
            self._log(f"Installing {package_name}" + (f" version {version}" if version else ""))

            install_spec = f"{package_name}=={version}" if version else package_name

            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", install_spec],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                self._log(f"✓ Successfully installed {package_name}", "SUCCESS")
                return True
            else:
                self._log(f"✗ Failed to install {package_name}", "ERROR")
                self._log(f"Error: {result.stderr}", "ERROR")
                return False

        except subprocess.TimeoutExpired:
            self._log(f"Installation timeout for {package_name}", "ERROR")
            return False
        except Exception as e:
            self._log(f"Installation error for {package_name}: {e}", "ERROR")
            return False

    def check_and_install_opensim(self, interactive: bool = True) -> bool:
        """
        Check if OpenSim is installed, and install if needed.

        Args:
            interactive: If True, ask user which version to install

        Returns:
            True if OpenSim is available (either was installed or already present)
        """
        if self.is_installed('opensim'):
            self._log("OpenSim is already installed ✓")
            return True

        self._log("OpenSim is not installed")

        if not interactive:
            self._log("Installing latest OpenSim version...")
            return self.install_package('opensim-core')

        # Interactive mode - show available versions
        print("\n" + "="*70)
        print("OpenSim Installation Helper")
        print("="*70)
        print("\nFetching available OpenSim versions from PyPI...")

        available_versions = self.get_available_versions('opensim-core')

        if not available_versions:
            print("\nCould not fetch available versions from PyPI.")
            print("Installing latest version from PyPI...")
            return self.install_package('opensim-core')

        print(f"\nAvailable OpenSim versions ({len(available_versions)} shown):\n")
        for i, ver in enumerate(available_versions, 1):
            print(f"  {i}. {ver}")

        print(f"  {len(available_versions) + 1}. Latest (auto-select)")
        print(f"  {len(available_versions) + 2}. Cancel installation")

        while True:
            try:
                choice = input(f"\nSelect version to install (1-{len(available_versions) + 2}): ").strip()
                choice_num = int(choice)

                if choice_num == len(available_versions) + 2:
                    print("\nInstallation cancelled.")
                    return False

                if choice_num == len(available_versions) + 1:
                    selected_version = None
                    print(f"\nInstalling latest version...")
                    break

                if 1 <= choice_num <= len(available_versions):
                    selected_version = available_versions[choice_num - 1]
                    print(f"\nInstalling version {selected_version}...")
                    break

                print(f"Invalid choice. Please enter a number between 1 and {len(available_versions) + 2}")

            except ValueError:
                print("Invalid input. Please enter a number.")
                continue

        # Perform installation
        success = self.install_package('opensim-core', selected_version)

        if success:
            # Verify installation
            if self.is_installed('opensim'):
                print("\n✓ OpenSim installed successfully!")
                return True
            else:
                print("\n✗ OpenSim installation completed but import failed.")
                print("  This may be a compatibility issue with your Python version.")
                return False
        else:
            print("\n✗ Failed to install OpenSim")
            print("\nFor manual installation, see: https://opensim.stanford.edu/")
            return False

    def check_all_dependencies(self) -> Dict[str, bool]:
        """
        Check all dependencies.

        Returns:
            Dictionary of package_name: is_installed
        """
        results = {}
        for key, info in self.DEPENDENCIES.items():
            results[key] = self.is_installed(info['import_name'])
        return results

    def install_missing_dependencies(self, interactive: bool = True) -> bool:
        """
        Install all missing dependencies.

        Args:
            interactive: Show interactive prompts

        Returns:
            True if all critical dependencies are satisfied
        """
        status = self.check_all_dependencies()

        missing_critical = {
            k: v for k, v in status.items()
            if not v and self.DEPENDENCIES[k]['critical']
        }

        missing_optional = {
            k: v for k, v in status.items()
            if not v and not self.DEPENDENCIES[k]['critical']
        }

        if not missing_critical and not missing_optional:
            self._log("All dependencies are satisfied ✓")
            return True

        print("\n" + "="*70)
        print("Dependency Check")
        print("="*70)

        if missing_critical:
            print(f"\n✗ Missing {len(missing_critical)} critical dependencies:")
            for key in missing_critical:
                info = self.DEPENDENCIES[key]
                print(f"  - {key}: {info['description']}")

        if missing_optional:
            print(f"\n⚠ Missing {len(missing_optional)} optional dependencies:")
            for key in missing_optional:
                info = self.DEPENDENCIES[key]
                print(f"  - {key}: {info['description']}")

        if missing_critical:
            if interactive:
                response = input("\nInstall missing critical dependencies? (yes/no): ").strip().lower()
                if response not in ['yes', 'y']:
                    print("Cannot proceed without critical dependencies.")
                    return False

            print("\nInstalling critical dependencies...")
            for key in missing_critical:
                info = self.DEPENDENCIES[key]
                if key == 'opensim':
                    # Special handling for OpenSim
                    if not self.check_and_install_opensim(interactive=False):
                        self._log(f"Failed to install {key}", "ERROR")
                        return False
                else:
                    if not self.install_package(info['package_name']):
                        self._log(f"Failed to install {key}", "ERROR")
                        return False

        if missing_optional and interactive:
            response = input("\nInstall optional dependencies? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print("\nInstalling optional dependencies...")
                for key in missing_optional:
                    info = self.DEPENDENCIES[key]
                    self.install_package(info['package_name'])

        # Final check
        final_status = self.check_all_dependencies()
        critical_satisfied = all(
            final_status[k] for k in missing_critical
        )

        if critical_satisfied:
            print("\n✓ All critical dependencies installed successfully!")
            return True
        else:
            print("\n✗ Some critical dependencies still missing.")
            return False


def check_dependencies_and_install_if_needed():
    """
    Main function to check and install dependencies.
    Call this at application startup.
    """
    installer = DependencyInstaller(verbose=True)

    # Check all dependencies
    status = installer.check_all_dependencies()

    # If OpenSim is missing, offer interactive installation
    if not status['opensim']:
        print("\n" + "="*70)
        print("OpenSim Missing - Installation Required")
        print("="*70)
        print("\nThe Powerlifting Model Analysis App requires OpenSim.")
        print("OpenSim is a free, open-source musculoskeletal modeling software.")
        print("Homepage: https://opensim.stanford.edu/")

        if not installer.check_and_install_opensim(interactive=True):
            print("\n✗ Cannot proceed without OpenSim installed.")
            print("Please install OpenSim manually or try again.")
            sys.exit(1)

    # Check other critical dependencies
    installer.install_missing_dependencies(interactive=True)

    # Final verification
    if not installer.is_installed('opensim'):
        print("\n✗ Critical dependency check failed: OpenSim")
        sys.exit(1)

    print("\n✓ All dependencies ready. Launching application...\n")


if __name__ == "__main__":
    # Test the installer
    installer = DependencyInstaller(verbose=True)
    check_dependencies_and_install_if_needed()
