OpenSim / CEINMS setup file templates
======================================
These files are copied to <project>/setup_files/ when you run:

    python -m bioscout --init <project_path>

Replace the placeholder files here with your own project-specific versions.
Files typically include:
  IK_task_set.xml         — IK marker task weights
  markers_*.xml           — marker set definitions
  externalloads.xml       — GRF external loads
  setup_IK.xml            — IK tool setup
  setup_ID.xml            — ID tool setup
  setup_MA.xml            — muscle analysis setup
  setup_SO.xml            — static optimisation setup
  setup_scale.xml         — model scaling setup
  actuators_so.xml        — SO actuator set
  setup_JRA.xml           — joint reaction analysis
  excitationGenerator.xml — CEINMS excitation generator
  calibrationCfg.xml      — CEINMS calibration config
  subjectUncalibrated.xml — CEINMS uncalibrated model template
