# BioScout cleanup & merge runbook

Run these in a **normal terminal** on your machine (PowerShell or git-bash), `cd C:\Git\bioscout`.
Do them stage by stage and read the notes — a few steps need a judgement call.

> Why a runbook instead of me doing it: the Cowork sandbox's file mount was serving
> corrupted/truncated views of recently-edited files (and even `.git/config`). Your real
> files are fine, but running `git add/commit/merge` from inside that sandbox risked writing
> the corrupted views back to disk. On your own machine there's no such layer.

---

## 0. Pre-flight + safety snapshots

```
git fetch --all --prune
git status
git branch backup/tracking_training-20260629 tracking_training
git branch backup/pull_ups-20260629 pull_ups
```

## 1. Confirm files are actually intact (they should be)

```
python -c "import ast,glob;[ast.parse(open(f,encoding='utf-8').read()) for f in glob.glob('bioscout/**/*.py',recursive=True)];print('all .py parse OK')"
python -c "import bioscout; print('version', bioscout.__version__)"
```

If both pass, the "corruption" was purely a sandbox artifact and you can proceed.
(Note: I already restored `bioscout/__init__.py` to the correct 50-line lazy-loader on disk.)

## 2. Triage uncommitted work on `tracking_training` (current branch)

Junk to delete:

```
del _ptest.txt
del bioscout\models\Full_Body_with_ball.osim.bak_pre_fix
```

The `.osim` model shows ~87k lines of churn between branches — that's reformatting noise, not
real edits. If you didn't intend to change it, discard it:

```
git checkout -- bioscout/models/Full_Body_with_ball.osim
```

Commit the genuine work (EMG consolidation + the new split modules + self-test):

```
git add bioscout/__init__.py bioscout/utils/__init__.py bioscout/settings.py bioscout/utils/settings.py
git add bioscout/utils/analyse.py bioscout/utils/plot.py bioscout/utils/shared.py
git commit -m "WIP: EMG consolidation, analyse/plot split, shared helpers"
```

## 3. Resolve the `tests.py` vs `tests/` collision  (real bug)

Both `bioscout/tests.py` and `bioscout/tests/__init__.py` exist and **both define `run()`**.
Python imports the *package directory*, so your untracked `bioscout/tests.py` is dead — and
`bioscout.test()` runs the directory's runner, not the file's. Pick one:

- Keep the tracked package (recommended): diff first, then drop the duplicate file.
  ```
  git diff --no-index bioscout/tests/__init__.py bioscout/tests.py
  del bioscout\tests.py
  ```
- Or, if `tests.py` is the newer/better runner, replace the package entry point with it:
  ```
  copy /Y bioscout\tests.py bioscout\tests\__init__.py
  del bioscout\tests.py
  git add bioscout/tests/__init__.py
  ```

Then verify:
```
python -c "import bioscout; bioscout.test()"
```

## 4. Merge the two active branches onto an integration branch

```
git switch main
git switch -c integration
git merge --no-ff tracking_training -m "merge tracking_training (EMG consolidation)"
git merge --no-ff pull_ups          -m "merge pull_ups (subject rename + pull-up detector)"
```

Git predicts **no automatic conflicts**, but review these overlap points by hand:

- **player -> subject rename** (from `pull_ups`): let it win everywhere —
  `subject_profile.py`, `subject_registry.py`, `subjects.json`, and call sites.
  Make sure no stray `player_profile` / `player_registry` / `players.json` references survive:
  ```
  git grep -n "player_profile\|player_registry\|players.json\|PlayerProfile\|PlayerRegistry"
  ```
- **`utils/emg.py`**: keep `tracking_training`'s consolidated version (pull_ups deletes it).
- **`utils/__init__.py` and `settings.py`**: both branches edited these — confirm both sets of
  changes are present after merge.

Validate:
```
python -c "import bioscout; bioscout.test()"
python -m bioscout            # smoke-test the CLI/GUI entry if applicable
```

## 5. Collapse the duplicate modules (do after the merge is green)

Pick one canonical module per pair and update imports; these are the duplicates I found:

- `utils/analyse.py`  vs  `utils/analysis.py`   (only `analysis.py` is imported by the package)
- `utils/plot.py`     vs  `utils/plotting.py`
- `settings.py` (root) vs `utils/settings.py` vs `config/config_manager.py`  (three settings sources)
- `utils/emg.py`      vs  `utils/emg_normalise.py`

For each: `git grep -n "<module name>"` to see who imports it, fold into the keeper, delete the
other, run `bioscout.test()`.

## 6. De-bloat version control

These are tracked but shouldn't be (≈80 MB total):

```
git rm --cached bioscout/utils/ceinms/torch_cpu.zip
git rm --cached bioscout/utils/ceinms/*.exe bioscout/utils/ceinms/*.dll
git rm --cached bioscout/utils/platypus.jpg bioscout/utils/platypus_sad.jpg
git rm --cached bioscout/utils/app_window.png bioscout/utils/shot_analysis_card.png bioscout/utils/logo.png
```

Append to `.gitignore`:
```
bioscout/utils/ceinms/*.zip
bioscout/utils/ceinms/*.exe
bioscout/utils/ceinms/*.dll
bioscout/utils/*.png
bioscout/utils/*.jpg
*.bak_pre_fix
```
```
git commit -m "stop tracking CEINMS binaries and image assets"
```

> `git rm --cached` stops tracking but the blobs stay in history (clone size unchanged).
> To actually shrink the repo, run `git filter-repo --strip-blobs-bigger-than 5M` on a fresh
> clone — destructive, force-pushes history, coordinate before doing it.

## 7. Prune branches

```
# local
git branch -d video_analyser        # fully merged (10 behind main, 0 ahead)
git branch -D jump_analysis         # stale/superseded -- confirm you don't need it

# worktree for pull_ups (after it's merged)
git worktree remove C:/Git/bioscout/.wt/pull_ups
git worktree prune

# remote -- abandoned 2025 branches
git push origin --delete copilot/create-pipeline-in-python coverage_automation make-simpler osim_commands

# REVIEW BEFORE DELETING: 15 unique commits, may hold real CEINMS work
git log origin/main..origin/update-ceinms --oneline
```

## 8. Land it

```
git switch main
git merge --ff-only integration     # or push `integration` and open a PR
git push origin main
git push origin --delete tracking_training pull_ups   # once merged
```

---

### Branch state reference (at time of audit, 2026-06-29)

| branch | vs main | last commit | verdict |
|---|---|---|---|
| main | — | 2026-06-12 | frozen base |
| tracking_training | +12 / 0 behind | 2026-06-26 | merge (EMG consolidation) |
| pull_ups | +12 / 0 behind | 2026-06-26 | merge (subject rename + pull-ups) |
| jump_analysis | +4 / 0 behind | 2026-06-15 | likely superseded → delete |
| video_analyser | 0 / 10 behind | 2026-06-11 | merged → delete |
| origin/update-ceinms | +15 / 34 behind | 2025-09-01 | review then decide |
| origin/make-simpler | 0 / 70 behind | 2025-04-14 | abandoned → delete |
| origin/copilot/create-pipeline | 0 / 28 behind | 2025-10-09 | abandoned → delete |
| origin/coverage_automation | 0 / 141 behind | 2025-02-12 | abandoned → delete |
| origin/osim_commands | 0 / 171 behind | 2025-01-27 | abandoned → delete |
