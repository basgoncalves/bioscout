# Screen Recording - Quick Start Guide

## Getting Started (30 seconds)

1. **Launch the App**
   ```bash
   cd C:\Git\app
   python __main__.py
   ```

2. **Click "Recording"** in the left sidebar

3. **Click "Launch Screen Recorder"** button

A separate window opens with the recorder controls.

## Recording a Video

### Step 1: Select Area
- Click "Select Area"
- Click and drag to choose what to record
- A dashed red border shows your selection

### Step 2: Configure
- Choose FPS from dropdown (default: 20 fps)
  - Lower FPS = smaller file size
  - Higher FPS = smoother motion
  - Recommended: 20-30 fps

### Step 3: Record
- Click "▶ Start" to begin recording
- Status shows: "Recording 1280×720..."
- Do whatever you want to record

### Step 4: Stop
- Click "■ Stop" to end recording
- Status shows: "Saved → screen_record_YYYYMMDD_HHMMSS.mp4"
- File automatically saved to `C:\Git\app\outputs\`

## Trimming a Video

### Step 1: Open Trim Dialog
- In the recorder, click "✂ Trim Video"

### Step 2: Load Video
- Click "Browse…"
- Select your video file
- Preview appears with frame count

### Step 3: Set Trim Points
- **Method 1: Click and drag**
  - Use "▶ Start" slider to set beginning
  - Use "⏹ End" slider to set ending
  
- **Method 2: Use frame scrubber**
  - Drag timeline to position
  - Click "Set ◄" for start point
  - Click "Set ►" for end point

### Step 4: Trim
- Click "✂ Trim" button
- Wait for "Saved → filename_trim_YYYYMMDD_HHMMSS.mp4"
- Trimmed video saved to same folder

## Viewing Your Recordings

1. In the **Recording** tab, check "Recent Recordings" section
2. Lists up to 10 most recent videos
3. Shows:
   - Filename
   - File size
   - Date/time modified
   - Full path

Click "Refresh File List" to update after new recordings.

## Common FPS Settings

| FPS | File Size | Use Case |
|-----|-----------|----------|
| 5 | Very small | Slow screen grabs, text-heavy |
| 10 | Small | Slide presentations, slideshows |
| 15 | Small | Software demos, UIs |
| 20 | Medium | **Default - Best for most uses** |
| 24 | Medium | Video-like (cinema standard) |
| 30 | Large | Smooth motion, gaming |
| 60 | Very large | Fast motion, sports |

## Pro Tips

💡 **Select Efficiently**
- Use keyboard Escape key to cancel area selection
- Selected area stays when you cancel and select again

💡 **Get Better Videos**
- Close unused windows first (fewer things moving = smaller file)
- Use 24-30 fps for smooth motion
- Position recorder window out of recording area

💡 **Optimize Output**
- Lower FPS reduces file size significantly
- 20 fps is ideal for most screen recordings
- Trim unnecessary footage to reduce file size

💡 **Manage Files**
- Check outputs folder periodically
- Delete old recordings to save disk space
- Sort by "Modified" to find recent videos

💡 **Preview Quality**
- Frame preview updates as you scrub
- Timeline shows full duration of video
- Times shown in bold are trim boundaries

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Cancel area selection | Esc |
| Previous frame | ◄ Button |
| Next frame | ► Button |
| Close trim dialog | Close button or X |
| Quit recorder | Quit button or X |

## Troubleshooting

### Recorder Won't Launch
```bash
# Install required packages
pip install opencv-python numpy pyautogui Pillow
```

### Recording is Choppy
- Lower the FPS setting (try 15 or 10)
- Close other applications
- Check disk space

### Trim Dialog Won't Open
```bash
# Install Pillow for preview
pip install Pillow
```

### File Won't Play
- Try using VLC Media Player (supports more codecs)
- File might still be encoding - wait a few seconds
- Check file size > 1 MB

### Missing Recent Recordings
- Click "Refresh File List" button
- Check `C:\Git\app\outputs\` directory
- Verify write permissions on disk

## File Information

**Output Location:** `C:\Git\app\outputs\`

**File Format:** MP4 (H.264 video codec)

**File Naming:** `screen_record_YYYYMMDD_HHMMSS.mp4`
- Example: `screen_record_20260522_143015.mp4`

**Typical File Sizes** (1-minute recording):
- 5 fps: ~2-3 MB
- 10 fps: ~5-7 MB
- 20 fps: ~10-15 MB
- 30 fps: ~15-25 MB

## Next Steps

1. **First Recording**
   - Select a small area
   - Record for 10 seconds
   - Check that file appears in outputs

2. **Test Playback**
   - Open video with Windows Media Player or VLC
   - Verify video quality looks good

3. **Trim Practice**
   - Open one of your videos
   - Practice trimming first/last few frames
   - Save trimmed version

4. **Organize**
   - Create subfolder in outputs (e.g., `demos/`, `presentations/`)
   - Move videos by category
   - Delete test videos

## Getting Help

**Error Messages?**
- Check logs: `C:\Git\app\logs\app_*.log`
- Look for `Recording` or `ScreenRecorder` entries

**Feature Requests?**
- Check documentation: `C:\Git\app\documentation\`
- See `RECORDING_INTEGRATION.md` for technical details

## Summary

Recording is easy:
1. ✅ Select area
2. ✅ Click Start
3. ✅ Do your thing
4. ✅ Click Stop
5. ✅ Video saved!

Happy recording! 🎥
