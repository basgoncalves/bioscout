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

# 2. Delete files that should not be in the repo (disk cleanup)
$toDelete = @(
    "yolov8n.pt",
    "pose_landmarker_lite.task",
    "pose_landmarker_full.task",
    "bioscout\pose_landmarker_lite.task",
    "bioscout\record\pose_landmarker_full.task",
    "bioscout\core\test_reset_settings.py",
    "bioscout\utils\log.txt",
    "cd",
    "rmdir"
)

foreach ($f in $toDelete) {
    if (Test-Path $f) {
        Remove-Item $f -Force
        Write-Host "Deleted: $f" -ForegroundColor Green
    } else {
        Write-Host "Already gone: $f" -ForegroundColor DarkGray
    }
}

# 3. Stop tracking files covered by .gitignore that were previously committed
#    (safe to re-run — no-ops if already untracked)
Write-Host "`nUntracking gitignored files..." -ForegroundColor Cyan

$toUntrack = @(
    "bioscout/logs",                          # logs dir (already gitignored)
    "bioscout/record/pose_landmarker_full.task"  # 9 MB model file
)

foreach ($path in $toUntrack) {
    git rm -r --cached $path 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Untracked: $path" -ForegroundColor Green
    } else {
        Write-Host "Already untracked: $path" -ForegroundColor DarkGray
    }
}

# 4. Stage everything
git add -A
Write-Host "`nStaged changes:" -ForegroundColor Cyan
git status --short

# 5. Commit
$msg = "Clean up: untrack logs dir + pose_landmarker model, remove stale files, project-level analysis architecture"
git commit -m $msg
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nCommitted." -ForegroundColor Green
} else {
    Write-Host "`nNothing new to commit, or commit failed." -ForegroundColor Yellow
}

# 6. Push
git push
if ($LASTEXITCODE -eq 0) {
    Write-Host "Pushed successfully." -ForegroundColor Green
} else {
    Write-Host "Push failed — check remote/auth." -ForegroundColor Red
}
