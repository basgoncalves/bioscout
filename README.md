# msk_modelling_python (pre-release)

A Python package for musculoskeletal modelling.

**Author:** Basilio Goncalves, PhD, University of Vienna, 2024
https://ufind.univie.ac.at/de/person.html?id=1004543
https://github.com/basgoncalves


---

## Pre-requisites for Installation

1. **Download a Code Interpreter**  
    I recommend [Visual Studio Code](https://code.visualstudio.com/download), but use your preferred one.

2. **Download and Install Python (>= 3.8)**  
    Make sure it is the correct bit version: [Python 3.8](https://www.python.org/downloads/release/python-380/)

3. **Download and Install OpenSim (suggest >=4.3)**  
    [OpenSim Downloads](https://simtk.org/frs/?group_id=91)

4. **Install Rapid Env Editor (optional)**  
    [Rapid Env Editor](https://www.rapidee.com/en/about)

5. **MOKKA (optional / only Windows users)**
    [Open-source and cross-platform software to easily analyze biomechanical data](https://biomechanical-toolkit.github.io/mokka/)

---


### Pip installation (works for python 3.8)
(for later versions try [OpenSim using Conda](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085346/Scripting+in+Python))

#### Create a Virtual Environment**
```sh
cd <your project folder>
python -m venv msk
```
Note: replace 'msk' if you want a different name

```
.\msk\Scripts\activate
```
#### Install uv package manager
```
pip install uv
```

#### Install msk-modelling-python
```
uv pip install msk-modelling-python
```

#### Test usage
``` python
import msk_modelling_python as msk
msk.bops.greet()
```

#### Install opensim 
```python
import msk_modelling_python as msk
msk.install_opensim.run()
```


---
## Work with the code 

1. **Activate your virtual enviroment (assume name 'msk')** 
   ```
   .\msk\Scripts\activate
   ```
---

2. **Clone this Module "msk_modelling_python" to your virtual environment**
   ```
   cd .\msk\Lib\site-packages
   ```
     ```
     git clone https://github.com/basgoncalves/msk_modelling_python.git
     ```
     *Note: Ensure the name of the package is exactly "msk_modelling_python"*
---

3. **Run OpenSim Setup from Installation Folder**  
    See [OpenSim Scripting in Python](https://simtk-confluence.stanford.edu:8443/display/OpenSim/Scripting+in+Python)

     ```sh
     cd 'C:\OpenSim 4.5\sdk\Python'
     ```
     ```sh
     python setup_win_python38.py
     ```
     ```sh
     python -m pip install .
     ```
     Note: run commands from shell or terminal    
---

4. **Add the Path to the OpenSim Libraries to Your Environment Variables**  
    Add the following paths to your `PATH` variable:
     ```
     C:\OpenSim 4.5\bin
     C:\OpenSim 4.5\lib
     ```
     Note: see for help https://answers.microsoft.com/en-us/windows/forum/all/change-system-variables-on-windows-11/f172c29e-fd9e-4f0b-949d-c4696bd656b8
---
5. **Verify the OpenSim Installation.**
     ```cmd
     python 
     ```
     ```cmd
     import opensim as osim
     model = osim.Model()
     ```
---
6. **Install requirements (in the terminal)**
     ```powershell
     cd .\msk\Lib\site-packages\msk_modelling_python
     pip install -r requirements.txt
     ```
---
7. **Testing msk_modelling_python (in python)**
     ```python
     import msk_modelling_python as msk
     msk.run_bops()
     ```
     Note: to change the performance of msk.run_bops() edit the settings file in .\msk_modelling_python\src\bops\settings.json
---
8. **Basic Usage**
     ```python
     import msk_modelling_python as msk

     # export c3d
     c3d_file_path = r'path\to\your\file.c3d'
     msk.bops.export_c3d(c3d_file_path)

     # run IK
     trial = msk.Project
     ```
---
9. **Use Example Scripts**
     Use example scripts in the "ExampleScripts" directory to get started with common tasks and workflows.

---

This package includes a combination of other packages and custom functions to manipulate and analyze biomechanical data. Inspired by the MATLAB version of BOPS (Batch OpenSim Processing Scripts) - [BOPS](https://simtk.org/projects/bops/)

## Tools to be Included:
- **BTK**  
  [BTK Documentation](https://biomechanical-toolkit.github.io/docs/Wrapping/Python/_getting_started.html)
- **c3dServer**  
  [c3dServer](https://www.c3dserver.com/)
- **OpenSim**  
  [OpenSim Scripting in Python](https://simtk-confluence.stanford.edu:8443/display/OpenSim/Scripting+in+Python)
- **3D Slicer**  
  [3D Slicer](https://www.slicer.org/)
- **FEbioStudio**  
  [FEbioStudio](https://febio.org/)
- **MeshLab 2023.12**  
  [MeshLab](https://www.meshlab.net/)
- **Genesis**  
  [Genesis](https://genesis-embodied-ai.github.io/)
  

---

## Code Structure

1. **msk_modelling_python**
     This is the main package including all the modules needed for msk modelling, stats, data_processing, etc. This package contains subpackages that can be used independently.

2. **bops**
     Batch Opensim Processing Software  
     Package with functions and classes to use Opensim, CEINMS, stats, and others for easier processing.

3. **__main__** 
    

---

## Examples

Find examples under ".\example_data\example_modules".

**Workflow Examples**: See `example_data/workflow_example.py` for complete pipeline examples including:
- OpenSim analysis pipelines (IK -> ID -> SO -> JRA)
- Batch processing workflows
- Data processing pipelines

---

## Contact

For any questions or inquiries, please contact:

- **Name:** Basilio Goncalves
- **Email:** basilio.goncalves@univie.ac.at
- **ResearchGate:** [Basilio Goncalves](https://www.researchgate.net/profile/Basilio-Goncalves)

## References

Thelen, D. G. -2003- J. Biomech. Eng. 125, 70–77

Lloyd, D. G. et al. -2003- J. Biomech. 36, 765–776

Delp, S. L. et al. -2007- IEEE Trans. Biomed. Eng. 54, 1940–1950

Pizzolato, C. et al. -2015- J. Biomech. 48, 3929–3936

Hicks, J. L. et al. -2015- J. Biomech. Eng. 137,

Rajagopal, A. et al. -2016- IEEE Trans. Biomed. Eng. 63, 2068–2079

Goncalves, B. A. M. et al. -2023- Gait Posture 106, S68

Goncalves, B. A. M. et al. -2024- Med. Sci. Sport. Exerc. 56, 402–410

## Version updates 0.2.1

- include openSim function with functions to improve opensim management

## Version updates 0.3.0

- include ceinms and other plotting utils

