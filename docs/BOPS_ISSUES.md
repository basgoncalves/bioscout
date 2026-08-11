

## opensim import

'''
import opensim

Traceback (most recent call last):
  File "c:/Users/Bas/Desktop/osim_load.py", line 2, in <module>
    import opensim
  File "C:\Users\Bas\AppData\Local\Programs\Python\Python38\lib\site-packages\opensim\__init__.py", line 7, in <module>
    from .common import *
  File "C:\Users\Bas\AppData\Local\Programs\Python\Python38\lib\site-packages\opensim\common.py", line 13, in <module>
    from . import _common
ImportError: DLL load failed while importing _common: The specified procedure could not be found.

Solution:
  https://stackoverflow.com/questions/20201868/importerror-dll-load-failed-the-specified-module-could-not-be-found
  
  Download msvcp71.dll and msvcr71.dll from the web or check msk_modelling_python.src.bops

  Save them to your C:\Windows\System32 folder.

  Save them to your C:\Windows\SysWOW64 folder as well (if you have a 64-bit operating system).

Solution 2:

  cd 'C:\OpenSim 4.4\sdk\Python' (or your version)

  pip install -m . 

  change DLL path in 'C:\Git\python-envs\msk_modelling\lib\site-packages\opensim\__init__.py' to 'C:\OpenSim 4.4\bin' (or your version)


## C3D export

### Problem 1 - pyc3dserver 
```
Traceback (most recent call last):
  File "c:/Git/Opencap_squat_validation/code/export_emg_c3d.py", line 5, in <module>
    msk.bops.c3d_emg_export(c3d_file_path,emg_labels='all')
  File "C:\Git\python-envs\msk_modelling\lib\site-packages\msk_modelling_python\src\bops\bops.py", line 720, in c3d_emg_export      
    itf = c3d.c3dserver(msg=False)   # Get the COM object of C3Dserver (https://pypi.org/project/pyc3dserver/)
  File "C:\Git\python-envs\msk_modelling\lib\site-packages\pyc3dserver\pyc3dserver.py", line 145, in c3dserver
    itf = win32.Dispatch('C3DServer.C3D')
  File "C:\Git\python-envs\msk_modelling\lib\site-packages\win32com\client\__init__.py", line 118, in Dispatch
    dispatch, userName = dynamic._GetGoodDispatchAndUserName(dispatch, userName, clsctx)
  File "C:\Git\python-envs\msk_modelling\lib\site-packages\win32com\client\dynamic.py", line 104, in _GetGoodDispatchAndUserName    
    return (_GetGoodDispatch(IDispatch, clsctx), userName)
  File "C:\Git\python-envs\msk_modelling\lib\site-packages\win32com\client\dynamic.py", line 86, in _GetGoodDispatch
    IDispatch = pythoncom.CoCreateInstance(
pywintypes.com_error: (-2147221005, 'Invalid class string', None, None)
```
#### solution1
  try regsvr32 C3DServer.dll in cmd (open as admin)
  ```
  regsvr32 C3DServer.dll
  ```




## CEINMS 


Error 1

C:\Git\isbs2024\Data\Simulations\Athlete_06\sq_90\ceinms_results\Torques.sto is empty
Traceback (most recent call last):
  File "c:/Git/msk_modelling_python/results_isbs2024.py", line 46, in <module>
    compare_two_df(id_mom_normalised,ceinms_mom_normalised,columns_to_compare=columns_to_plot,
  File "c:\Git\msk_modelling_python\plotting\plot_ceinms.py", line 142, in compare_two_df
    df2 = df2[columns_to_compare]
  File "C:\Users\Bas\AppData\Local\Programs\Python\Python38\lib\site-packages\pandas\core\frame.py", line 3767, in __getitem__
    indexer = self.columns._get_indexer_strict(key, "columns")[1]
  File "C:\Users\Bas\AppData\Local\Programs\Python\Python38\lib\site-packages\pandas\core\indexes\base.py", line 5877, in _get_indexer_strict
    self._raise_if_missing(keyarr, indexer, axis_name)
  File "C:\Users\Bas\AppData\Local\Programs\Python\Python38\lib\site-packages\pandas\core\indexes\base.py", line 5938, in _raise_if_missing
    raise KeyError(f"None of [{key}] are in the [{axis_name}]")
KeyError: "None of [Index(['hip_flexion_r', 'hip_flexion_l', 'hip_adduction_r', 'hip_adduction_l',\n       'hip_rotation_r', 'hip_rotation_l', 'knee_angle_r', 'knee_angle_l',\n       'ankle_angle_r', 'ankle_angle_l'],\n      dtype='object')] are in the [columns]"


Solution: 
==============================================================================================================================