#!/usr/bin/env pwsh
# cleanup_and_commit.ps1
# Run from PowerShell in C:\Git\msk_modelling_python
# > .\cleanup_and_commit.ps1

Set-Location $PSScriptRoot

# 1. Remove stale git lock left by sandbox
$lock = ".git\index.lock"
if (Test-Path $lock) {
    Remove-Item $lock -Force
    Write-Host "Removed stale $lock" -ForegroundColor Yellow
}

# 2. Delete files that should not be in the repo
$toDelete = @(
    "yolov8n.pt",
    "pose_landmarker_lite.task",
    "pose_landmarker_full.task",
    "msk_modelling_python\pose_landmarker_lite.task",
    "msk_modelling_python\core\test_reset_settings.py",
    "msk_modelling_python\utils\log.txt"
)

foreach ($f in $toDelete) {
    if (Test-Path $f) {
        Remove-Item $f -Force
        Write-Host "Deleted: $f" -ForegroundColor Green
    } else {
        Write-Host "Already gone: $f" -ForegroundColor DarkGray
    }
}

# 3. Stage everything
git add -A
Write-Host "`nStaged changes:" -ForegroundColor Cyan
git status --short

# 4. Commit
$msg = "Clean up: remove stale model files, fix timeline scrub, add resizable panel, AR crop buttons"
git commit -m $msg
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nCommitted." -ForegroundColor Green
} else {
    Write-Host "`nNothing new to commit, or commit failed." -ForegroundColor Yellow
}

# 5. Push
git push
if ($LASTEXITCODE -eq 0) {
    Write-Host "Pushed successfully." -ForegroundColor Green
} else {
    Write-Host "Push failed — check remote/auth." -ForegroundColor Red
}
