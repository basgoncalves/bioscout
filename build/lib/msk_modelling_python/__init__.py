try:
    # import for local development
    import bops
    from classes import *
    from src import *
    from utils import *
    import install_opensim
    import workflow
    
except:
    # import for package development
    import os
    from . import bops as bops
    from .classes import *
    from .utils import *
    from . import install_opensim
    from . import workflow

__version__ = "0.0.20"

if __name__ == "__main__":
    bops.greet()
    bops.about()
    
    if False:
        data = bops.read.c3d()
        print(data)
    
    if False:
        data_json = bops.read.json()
        print(data_json)
    
    if False:
        data_mot = bops.read.mot()
        print(data_mot)