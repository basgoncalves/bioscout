# bioscout.model.mri2msk (MRI2MSK, draft 0.1)


Python port of the MATLAB **MRI2MSK** pipeline (W. Koller, Univ. Vienna), part of bioscout since 2026-11-04 (was MRI2MSKpy). Includes the full warping workflow (steps 1–8) and a Post-Warp tab
(scale → IK → ID → SO → JRA → JCF contributions) that uses BioScout's OpenSim functions.

| Python | MATLAB | Notes |
|---|---|---|
| `step1_rescale_and_align` | executeStep01 | uses the Python STAPLE port in `mri2msk/staple` |
| `step2_align_skin` | executeStep02 | trimesh quadric decimation replaces `reducepatch` |
| `step2b_add_skin_to_base_model` | executeStep02b | |
| `step4_create_warp_setup` | executeStep03 | |
| `step5_warp_model` | (OpenSim Creator Model Warper) | Python TPS warper, matches OSC < 0.001 mm |
| `step6_replace_skin` | executeStep04b | |
| `step7a_correct_torsion` | executeStep05 | |
| `step7b_correct_mass_centers` | executeStep06 | |
| `step8_mechanical_knee_axis` | executeStep07 | matplotlib plot + confirm callback replace uifigure |

### STAPLE port (step 1)

`mri2msk/staple` re-implements the parts of STAPLE / GIBOC-core that step 1 uses:
`STAPLE_pelvis` (ground_pelvis), `GIBOC_femur` with ellipsoids (hip JCS) and
`Kai2014_tibia` (knee JCS). Checked against MATLAB on `exampleParticipant`:

| bone | origin diff | max axis diff | resize factor diff |
|---|---|---|---|
| pelvis | 0.000 mm | 0.00° | 0.06% |
| tibia l / r | ≤ 0.004 mm | ≤ 0.02° | 0.00% |
| femur l / r | 0.000 mm | 0.09° / 0.26° | ≤ 0.02% |

Rerun with `python bioscout/tests/mri2msk/validate_step1.py ../MRI2MSK/exampleParticipant/stls`.
Not ported: the MATLAB fallbacks (Kai2014 femur / pelvis), used only when the
main algorithm errors.

Step 1 writes `stls/preAligningToOpenSim.json`. Later steps also accept the MATLAB
`preAligningToOpenSim.mat`, so you can run step 1 in MATLAB and the rest in Python.

## GUI

```bash
bioscout model mri2msk gui     # opens the GUI (same layout as the MATLAB app)
```

Pick the participant folder (base model defaults to `../MRI2MSK/BaseModel_Lernagopal`),
then run the steps top to bottom. Steps 3 and 5 open OpenSim Creator; the GUI
detects the landmark CSVs and `warpedModel/warpedModel.osim` automatically.
Configs save as `warpingConfig.json`; MATLAB `warpingConfig.mat` files load too.
The post-scaling tab (IK, muscle paths, optimiser) is not ported yet.

## Command line

```bash
pip install -e "C:/Git/bioscout[mri2msk]"   # + conda install -c opensim-org opensim
bioscout model mri2msk status --participant ../MRI2MSK/exampleParticipant \
       --base-model ../MRI2MSK/BaseModel_Lernagopal/LernagopalLaiUhlrich2025_CGM2.osim
bioscout model mri2msk 7a --participant ... --base-model ...
```
