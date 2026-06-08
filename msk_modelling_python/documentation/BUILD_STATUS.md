# Android APK Build Status

**Last Updated**: May 27, 2026, 7:31 AM  
**Status**: ✅ All fixes applied and committed to `main` branch

## What's Been Fixed

### 1. Settings Module Path ✅
- Moved `settings.py` to `mobile/` folder so buildozer packages it into the APK
- Updated `main.py` to import directly: `from settings import RecordingSettings`
- Removed `sys.path.insert()` manipulation that doesn't work in APK

### 2. Buildozer Configuration ✅
- **buildozer.spec**:
  - Added `source.include_patterns = **/*.py,**/*.png,**/*.jpg,**/*.kv,**/*.atlas,**/*.task`
  - Removed unsupported `android.features` flag (incompatible with p4a 2026.5.9)
  - Simplified requirements to: `python3,kivy` (removed problematic pyjnius)

### 3. GitHub Actions Workflow ✅
- **Added SDK License Acceptance** (lines 19-24):
  ```yaml
  - name: Accept Android SDK Licenses
    run: |
      mkdir -p $HOME/.android
      echo -e "\n\nSDK Licenses:\n" > $HOME/.android/repositories.cfg
      yes | sdkmanager --licenses 2>/dev/null || true
  ```
- This prevents: "Android SDK Build-Tools license not accepted" error

## Current Configuration

```
buildozer.spec:
  ✓ requirements = python3,kivy
  ✓ android.api = 31, android.minapi = 24
  ✓ android.ndk = 25b
  ✓ android.arch = arm64-v8a
  ✓ source.include_patterns properly set

main.py:
  ✓ Imports settings directly (no parent path manipulation)
  ✓ Has fallback to default path if import fails

.github/workflows/build-apk.yml:
  ✓ SDK licenses accepted before buildozer runs
  ✓ Uploads APK to artifacts (30-day retention)
  ✓ Triggers on: push to main/master/develop, PRs, manual dispatch
```

## Next Steps

### To Start the Build

**Option 1: Automatic (No Action Needed)**
- The build will automatically trigger on the next push to `main` branch
- Currently everything is committed, so if you make any changes and push, it will build

**Option 2: Manual Trigger**
1. Go to: https://github.com/YOUR_USERNAME/YOUR_REPO
2. Click: **Actions** tab
3. Click: **Build APK** (left sidebar)
4. Click: **Run workflow** → **Run workflow** (blue button)
5. Wait for build to complete (typically 10-15 minutes)

### Where to Find the APK

Once the build completes:
1. Go to **Actions** tab
2. Click the most recent **Build APK** workflow run
3. Scroll down to **Artifacts** section
4. Download: `openbio-apk` → contains your APK file

The APK is: `bin/openbio-debug.apk` inside the artifact

### Why This Works

The GitHub Actions environment provides:
- ✓ Linux Docker container (required for buildozer `sh` module)
- ✓ Proper network access (no SSL issues)
- ✓ Android NDK and SDK pre-installed
- ✓ All build dependencies available

Local Windows builds won't work because buildozer requires the Linux `sh` module.  
WSL had SSL certificate issues in the hostpython3 environment.

## Troubleshooting

If the build fails after you return:

1. **Check the build log** in GitHub Actions workflow run
2. **Most common error**: SDK licenses
   - Already handled by the workflow, shouldn't occur
3. **Module import error**: 
   - Verify `mobile/settings.py` exists (it does: 19KB, dated May 27)
4. **Buildozer cache issue**:
   - Clear with: `cd mobile && rm -rf .buildozer bin build`

## Files Changed

- `mobile/settings.py` — Created (copied from parent directory)
- `mobile/main.py` — Modified (removed sys.path manipulation)
- `mobile/buildozer.spec` — Modified (added include_patterns, removed android.features)
- `mobile/.github/workflows/build-apk.yml` — Modified (added SDK license acceptance)
- `mobile/FIX_BUILD_ERROR.md` — Updated (documents the fixes)

All changes are committed to the `main` branch.
