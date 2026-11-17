# Data source

Instrumented-implant subject **H1L** from **OrthoLoad**, Julius Wolff
Institute, Charite - Universitaetsmedizin Berlin. In this one gait-analysis trial the
markers, the two AMTI force plates and the **measured hip contact force** were
recorded together, on this one person -- which is the whole reason this session exists.

- Database entry: <https://orthoload.com/database/?implantId=2355&activityId=2820&activityIndentationLevel=2&parameterId=1&parameterIndentationLevel=-1&patientId=h1l&fileId=h1l_060511_1_47_mov&fileType=a>
- Motion + plates + in-vivo force (the file this session was built from): <https://orthoload.com/wp-content/files/add_file/h1l_060511_1_47_mov.csv>
- Raw capture: <https://orthoload.com/wp-content/files/add_file/raw/h1l_060511_1_47_level_walking_mov.zip>
- Implant load file of the same trial (.akf): <https://orthoload.com/wp-content/files/file/result/h1l_060511_1_47.akf>
- Screen video: <https://orthoload.com/wp-content/files/add_video/mp4/h1l_060511_1_47_mov.mp4>
- Database home: <https://orthoload.com/database/>

Trial `Walking_01` = `h1l_060511_1_47_mov.csv` | hip implant, side `l` | body weight 760 N.

The raw OrthoLoad files are kept in `2_experimental/Walking_01/` beside the converted
ones: `h1l_060511_1_47_mov.csv` (markers + plates + in-vivo force, 960 Hz, the file everything here was
derived from) and `h1l_060511_1_47.akf` (the implant load trace as the database serves it).

Downloaded by `code/orthoload/orthoload_gait_download.py`, converted by
`code/orthoload/orthoload_to_bioscout.py`. What the conversion had to fix -- axes, the vertical
plate channel written in kN, the fitted plate origin, the absence of a static trial --
is written up in `results/orthoload/gait/RUN.md`.

**Citing it**: these are Bergmann et al. / OrthoLoad data; each file's database entry
names the publication it belongs to, so take the citation from the page linked above.
