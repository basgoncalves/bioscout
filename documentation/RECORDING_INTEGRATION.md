# Screen Recording Integration

## Overview

Screen recording functionality has been integrated into the Powerlifting Model Analysis App, providing users with the ability to record selected areas of their screen with optional trimming and preview capabilities.

## Changes Made

### 1. New Recording Module (`C:\Git\app\record\`)

Created a new `record` module containing the screen recording implementation:

- **`__init__.py`** - Module initialization with ScreenRecorder export
- **`screen_record.py`** - Complete ScreenRecorder implementation (546 lines)
  - Interactive area selection with dashed red border overlay
  - Multi-monitor support using Windows API
  - OpenCV-based video recording (5-60 fps configurable)
  - Video trimming with frame-by-frame scrubbing
  - PIL integration for video preview
  - Background threading for non-blocking recording
  - Output files stored in `C:\Git\app\outputs\`

### 2. New Recording Tab Widget (`C:\Git\app\gui\widgets\recording.py`)

Created a CustomTkinter widget for the GUI:

- `RecordingTab` class extending `ctk.CTkFrame`
- Features:
  - Launch button to open ScreenRecorder in separate window
  - Live list of recent recordings with file info
  - Refresh button to update output file list
  - Size and timestamp display for recordings
  - Status updates and error handling
  - Integrated logging with app's status system

### 3. Main Window Integration (`C:\Git\app\gui\main_window.py`)

Updated the main application window:

- Added `RecordingTab` import (line 53)
- Added "Recording" to sidebar navigation tabs (row 9)
- Added Recording to tab_definitions (lazy-loaded)
- Updated sidebar row configuration (row 10)
- Updated status frame row position (row 11)
- Updated button frame row position (row 12)
- Updated version label row position (row 13)

## Directory Structure

```
C:\Git\app\
├── record/
│   ├── __init__.py                    # Module initialization
│   └── screen_record.py               # ScreenRecorder class (546 lines)
├── gui/
│   ├── widgets/
│   │   └── recording.py               # RecordingTab widget (200+ lines)
│   └── main_window.py                 # Updated with Recording tab
├── outputs/                           # Recording output directory
│   └── screen_record_YYYYMMDD_HHMMSS.mp4  # Recording files
└── documentation/
    └── RECORDING_INTEGRATION.md       # This file
```

## Usage

### Launching Screen Recorder

1. Open the Analysis App
2. Click "Recording" in the left sidebar
3. Click "Launch Screen Recorder" button
4. A separate ScreenRecorder window opens with control panel

### Recording Video

1. Click "Select Area" to choose what to record
2. Click and drag on screen to select recording area
3. Choose FPS setting (5, 10, 15, 20, 24, 30, or 60)
4. Click "▶ Start" to begin recording
5. Click "■ Stop" to end recording
6. File saves automatically to `C:\Git\app\outputs\`

### Trimming Video

1. In the recorder, click "✂ Trim Video"
2. Browse to select a video file
3. Use frame-by-frame scrubber to preview
4. Set trim start and end points
5. Click "✂ Trim" to create trimmed video

### Viewing Recordings

1. The Recording tab displays recent recordings
2. Shows filename, size, and modification time
3. Click "Refresh File List" to update
4. Files are stored in `C:\Git\app\outputs\`

## Features

✅ **Interactive Area Selection**
- Full-screen overlay across all monitors
- Click-drag to select recording area
- Real-time dimension display
- Dashed red border preview

✅ **Flexible Recording**
- Configurable FPS (5-60 fps)
- Background thread recording (non-blocking UI)
- Support for multiple monitors
- Automatic file naming with timestamp

✅ **Video Trimming**
- Frame-by-frame scrubbing
- Preview thumbnail display
- Time-based trim points
- Cursor-following timeline

✅ **Integration**
- Seamless integration with main app
- Status updates in app status bar
- Output file list in tab
- Proper thread management

## Technical Details

### Output Path Resolution

The screen recorder outputs files to:
```
Path(__file__).parent.parent / "outputs"
```

This resolves to `C:\Git\app\outputs\` when run from the record module.

### Process Management

- ScreenRecorder launches as subprocess via Python
- Non-blocking implementation using threading
- Process monitoring in background thread
- Output list auto-refreshes when recorder closes

### Dependencies

The recording module requires:
- `cv2` (OpenCV) - for video encoding/decoding
- `numpy` - for frame processing
- `pyautogui` - for screenshot capture
- `Pillow` (PIL) - for preview thumbnails (optional, degrades gracefully)

### Thread Safety

- ScreenRecorder runs in separate process (complete isolation)
- Tab uses background thread for process monitoring
- UI updates marshaled back to main thread with `.after()`
- File list refresh only after process completion

## Future Enhancements

Potential improvements:
- Video quality/codec selection
- Real-time FPS/bitrate monitoring
- Recording history/database
- Audio recording support
- Custom output format templates
- Pause/resume recording
- Multiple concurrent recordings

## Troubleshooting

### Recorder won't launch
- Check if python is properly installed
- Verify `cv2`, `numpy`, `pyautogui` are installed
- Check logs for detailed error messages

### No video output
- Verify `outputs/` directory exists and is writable
- Check disk space
- Review FPS setting (lower FPS if recording fails)

### Trimming not working
- Install Pillow: `pip install Pillow`
- Video file must be readable MP4
- Trim start must be before trim end

### Preview not showing
- Pillow required: `pip install Pillow`
- Video must be valid MP4 with readable frames
- Check video codec compatibility

## Integration Verification

To verify the recording module is properly integrated:

1. Start the app: `python __main__.py`
2. Click "Recording" tab (should appear in sidebar)
3. Click "Launch Screen Recorder"
4. Separate window should open
5. Test area selection
6. Test recording a short clip
7. Check `outputs/` directory for file
8. Refresh file list to see recording

All should work without errors!
