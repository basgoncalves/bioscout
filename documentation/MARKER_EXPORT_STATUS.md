# Marker Export Status - Current Issues

## Problem Identified
The `_ensure_all_markers_in_trc()` function was corrupting the TRC file format when trying to rebuild it with missing markers.

**Root Cause:** TRC files have a strict binary-compatible format used by OpenSim. The header structure must be perfectly preserved and the metadata must match the data.

## Current Status
**Temporarily Disabled** the broken marker completion function to prevent file corruption.

## What's Happening Now
1. ✅ Markers are detected correctly across all trials (42 markers found in your session)
2. ✅ UI shows all detected markers properly
3. ❌ Exported TRC files still have inconsistent marker sets per trial
4. ❌ Missing markers are NOT being added

## Why the Previous Approach Failed
The `_ensure_all_markers_in_trc()` function was trying to:
1. Read the TRC file
2. Parse the headers
3. Rebuild the entire file with new markers

But TRC files created by OpenSim have specific formatting requirements:
- Header line 1 contains metadata that must be tab-separated in a specific order
- The NumMarkers count in line 1 must match the actual number of marker columns
- Data rows must have exactly matching tab positions
- Any mismatch breaks OpenSim compatibility

## Solution Needed
To properly export all markers, we need to either:

**Option A (Recommended):** Create TRC files from scratch
- Read C3D file data directly  
- Include all detected markers from the start
- Use proper OpenSim TRC format
- No post-processing needed

**Option B:** Patch OpenSim export
- Modify exportC3D.py to export all markers
- Tell it which markers to include (even if missing from trial)
- Use OpenSim's native TRC writer (guarantees correct format)

**Option C:** Robust post-processing
- Use pandas + proper TRC format understanding
- Update header metadata correctly
- Validate output format before saving

## Files Affected
- `gui/widgets/batch_c3d_export.py` - Marker completion disabled (line ~994)

## Next Steps
Choose one approach and implement properly. Currently recommending Option B (modify exportC3D.py) as it's simplest and most reliable.
