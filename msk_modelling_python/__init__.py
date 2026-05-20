try:
    # import for local development
    import bops
    from classes import *
    from src import *
    from utils import *
    import install_opensim
    
except:
    # import for package development
    import os
    from . import bops as bops
    from .classes import *
    from .utils import *
    from . import install_opensim


__version__ = "0.3.0"

if __name__ == "__main__":
    bops.greet()
    bops.about()
    try:
        import opensim as osim
        print("OpenSim is installed and imported successfully.")
    except ImportError:
        print("OpenSim is not installed. Attempting to install OpenSim...")
        install_opensim.run(osim_version="4.4")
    