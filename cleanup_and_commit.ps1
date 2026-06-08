# cleanup_and_commit.ps1
# Run this from C:\Git\msk_modelling_python in PowerShell to:
#   1. Remove the git index lock (if VS Code left it)
#   2. Delete old package files that no longer belong
#   3. Switch to the app branch and commit

Set-Location "C:\Git\msk_modelling_python"

# ---- 1. Remove stale index lock ----
$lock = ".git\index.lock"
if (Test-Path $lock) {
    Remove-Item $lock -Force
    Write-Host "Removed $lock"
}

# ---- 2. Delete old package files ----
$pkg = "msk_modelling_python"
$old_files = @(
    "$pkg\bops.py",
    "$pkg\ceinms.py",
    "$pkg\classes.py",
    "$pkg\dev.py",
    "$pkg\install_opensim.py",
    "$pkg\notebook.ipynb",
    "$pkg\openSim.py",        # moved to utils/
    "$pkg\emg_normalise.py",  # moved to utils/
    "$pkg\exportC3D.py",      # moved to utils/
    "$pkg\settings.json",
    "$pkg\error_log.txt",
    "$pkg\log.txt",
    "$pkg\requirements.txt"
)

foreach ($f in $old_files) {
    if (Test-Path $f) {
        Remove-Item $f -Force
        Write-Host "Deleted: $f"
    }
}

# Remove old app/ subfolder (now replaced by top-level structure)
if (Test-Path "$pkg\app") {
    Remove-Item "$pkg\app" -Recurse -Force
    Write-Host "Deleted: $pkg\app\"
}

# Remove old executables/ folder (binaries now in utils/ceinms/)
if (Test-Path "$pkg\executables") {
    Remove-Item "$pkg\executables" -Recurse -Force
    Write-Host "Deleted: $pkg\executables\"
}

# Remove old src/ folder
if (Test-Path "$pkg\src") {
    Remove-Item "$pkg\src" -Recurse -Force
    Write-Host "Deleted: $pkg\src\"
}

# ---- 3. Switch to app branch and commit ----
git checkout app
git add -A
git commit -m "[RESTRUCTURE] Replace package with working app (v2.1.0)

- Replace msk_modelling_python/ contents with C:\Git\app
- New structure: config/, core/, gui/, utils/, record/, tests/
- utils/ceinms/ contains CEINMS executables (moved from executables/)
- New entry points: msk-gui (GUI) and msk-batch (CLI)
- Updated setup.py to v2.1.0 with correct subpackages and data files
- Updated __init__.py to expose Analyse, normalise_emg_across_session, launch_gui"

Write-Host "Done. Use 'git push origin app' to push."
