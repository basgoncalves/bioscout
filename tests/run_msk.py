import os
import sys
import subprocess
import msk_modelling_python as msk
msk.bops.greet()

CURRENT_DIR = msk.os.path.dirname(msk.os.path.abspath(__file__))
EXAMPLE_DATA_DIR = msk.os.path.join(msk.os.path.dirname(CURRENT_DIR), 'example_data')
SIMULATION_DIR = msk.os.path.join(EXAMPLE_DATA_DIR,'running')

SUBJECT = 'Athlete1'
SESSION = 'session1'
TASK = 'sprint_1'
TASK_FOLDER = msk.os.path.join(SIMULATION_DIR, SUBJECT, SESSION, TASK)

# Trial = msk.bops.Trial(TASK_FOLDER)
# Trial.run_ik()



