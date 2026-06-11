"""
Application version information - centralized versioning for all modules.
Update versions here when releasing new features.
"""

# Application Version
APP_VERSION = "0.4.0"
APP_NAME = "msk_modelling_python"

# Module Versions
MODULE_VERSIONS = {
    "config": "1.2.0",           # Configuration system (YAML + GUI)
    "core": "2.0.0",             # Analysis runner and core orchestration
    "gui": "2.1.0",              # GUI framework and widgets
    "utils": "2.0.0",            # Utility functions and data handling
    "openSim": "2.1.0",          # OpenSim wrapper with RRA/CMC/Energetics
    "ceinms": "1.1.0",           # CEINMS integration
    "emg_normalise": "1.0.0",    # EMG processing
    "exportC3D": "1.0.0",        # C3D export utilities
    "logger": "1.0.0",           # Logging system
}

# API/Component Versions
COMPONENT_VERSIONS = {
    "analysis_runner": "2.0.0",           # AnalysisRunner class
    "analysis_step_enum": "2.0.0",        # AnalysisStep enum (RRA, CMC added)
    "session_manager": "1.0.0",           # Session management system
    "trial_discovery": "1.0.0",           # Trial auto-discovery from C3D/TRC
    "ceinms_calibration": "1.1.0",        # CEINMS calibration with trial selection
    "emg_processing": "2.0.0",            # EMG Processing tab
}

# Dependency Versions (key packages)
DEPENDENCY_VERSIONS = {
    "customtkinter": "5.0+",              # GUI framework
    "opensim": "4.4+",                    # OpenSim Python API
    "pandas": "1.5+",                     # Data analysis
    "numpy": "1.20+",                     # Numerical computing
    "scipy": "1.7+",                      # Scientific computing
    "pyyaml": "6.0+",                     # YAML configuration
}

# Version History
VERSION_HISTORY = {
    "2.1.0": {
        "date": "2026-05-13",
        "changes": [
            "Added RRA (Residual Reduction Algorithm) analysis step",
            "Added CMC (Computed Muscle Control) analysis step",
            "Added Energetics (Metabolic Cost) analysis step",
            "Added Body Kinematics analysis step",
            "Removed EMG_NORMALISE and SCALE_EMG from trial-level analysis",
            "Fixed progress callback signature in AnalysisRunner",
            "Improved exportC3D module error handling",
            "Added version tracking system",
            "Session-level analysis architecture (refactored)",
            "Trial auto-discovery system",
            "CEINMS calibration trial selection with status indicators",
        ]
    },
    "2.0.0": {
        "date": "2026-05-12",
        "changes": [
            "Complete module import system fix with dual fallback",
            "AnalysisRunner restructured with proper callbacks",
            "GUI simplified with session-level CEINMS calibration",
            "EMG Processing tab enhancements",
        ]
    },
    "1.0.0": {
        "date": "2026-01-01",
        "changes": [
            "Initial release with basic OpenSim analysis pipeline",
        ]
    },
}


def get_version(module_name: str = None) -> str:
    """Get version for a specific module or application version."""
    if module_name is None:
        return APP_VERSION
    return MODULE_VERSIONS.get(module_name, "unknown")


def get_full_version_info() -> dict:
    """Get complete version information for the application."""
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "modules": MODULE_VERSIONS,
        "components": COMPONENT_VERSIONS,
        "dependencies": DEPENDENCY_VERSIONS,
    }


def print_version_info():
    """Print full version information to console."""
    info = get_full_version_info()
    print(f"\n{'='*60}")
    print(f"{info['app_name']} - v{info['app_version']}")
    print(f"{'='*60}")
    print("\nModule Versions:")
    for module, version in info['modules'].items():
        print(f"  {module:.<30} {version}")
    print("\nComponent Versions:")
    for component, version in info['components'].items():
        print(f"  {component:.<30} {version}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    print_version_info()
