# Advanced Video Recording & OpenSim Analysis

## Overview

The Recording tab now includes advanced features for recording from webcam or IP camera, with automatic pose estimation and generation of OpenSim MOT files for biomechanical analysis.

## Features

### 1. Multiple Video Sources

#### Webcam Recording
- Record from standard USB webcam (device 0)
- Simple plug-and-play setup
- No additional configuration needed

#### IP Camera Recording
- Record from any IP Webcam stream
- Perfect for wireless cameras or phone-based solutions
- Default template: `http://192.168.0.107:8080/video`
- Requires IP Webcam app on Android device

### 2. Pose Estimation

Records human movement using MediaPipe pose estimation:
- 33 pose landmarks (full body tracking)
- Ball detection (green ball tracking)
- Background thread processing (non-blocking)
- Configurable detection interval to balance quality vs. speed

### 3. OpenSim Integration

Generate OpenSim MOT files with joint angle data:

#### Arm26 Ball Model
- Right shoulder elevation
- Right elbow flexion
- Ball position (3D translation)
- Suitable for throwing analysis

#### Full Body with Ball Model
- Both arms (6 DOF each)
- Both legs (4 DOF each)
- Pelvis (6 DOF)
- Spine degrees of freedom
- Ball tracking

### 4. Automatic Analysis

Each recording generates:
- **video.mp4** - Raw annotated video with skeleton overlay
- **joint_angles.png** - Time-series plot of all joint angles
- **release_catch.png** - Release & catch phase analysis
- **[model]_motion.mot** - OpenSim-compatible MOT file
- **frames/** - Numbered PNG frames with annotations

## Usage

### Step 1: Select Video Source

**Webcam:**
- Select "Webcam (USB Camera)" radio button
- Ensure webcam is connected and working

**IP Camera:**
- Select "IP Camera" radio button
- Enter IP address (or use default)
- Install IP Webcam app on Android device
- Set phone IP in the address field

### Step 2: Set Output Directory

```
C:\Users\[YourName]\Videos\Recordings\  (default)
```

Can customize by clicking "Browse" button.

### Step 3: Select OpenSim Model

Choose which model to generate:
- **Arm26 Ball** - Throwing/catching analysis
- **Full Body** - Complete body movement analysis

### Step 4: Start Recording

Click "🔴 Start Recording"
- Records for configurable duration (default: 10 seconds)
- Shows real-time skeleton overlay
- Detects ball trajectory
- Runs pose estimation every frame (adjustable)

### Step 5: Analyze Results

Results automatically appear in the "Recent Recordings" section:
```
Video Files:
  video_20260522_143015.mp4 (25.3 MB)

MOT Files (Joint Angles):
  arm26_ball_motion.mot (12.4 KB)

Analysis Files:
  joint_angles.png
  release_catch.png
```

Can also manually select video for analysis using "📊 Analyze Recording" button.

## IP Webcam Setup

### Requirements
- Android phone with camera
- WiFi network connection
- IP Webcam app installed

### Steps

1. **Install IP Webcam App**
   - Google Play: Search "IP Webcam"
   - Use free version by Pavel Khlebovich

2. **Configure App**
   - Open app
   - Tap "START SERVER"
   - Note the IP address (e.g., 192.168.0.107:8080)

3. **Use in Recording Tab**
   - Select "IP Camera"
   - Enter: `http://[phone-ip]:8080/video`
   - Click "Start Recording"

### Example
```
Phone on WiFi: 192.168.0.107
Recording Tab: http://192.168.0.107:8080/video
```

### Troubleshooting

**Camera not connecting:**
- Check phone and computer are on same WiFi
- Ping phone IP to verify connectivity
- Ensure app is still running (screen on)

**Distorted/rotated video:**
- IP camera streams in portrait orientation
- App auto-rotates to landscape
- Check phone position

**Slow performance:**
- Reduce detection interval (process every 2nd or 3rd frame)
- Lower resolution on phone if available
- Ensure WiFi signal is strong

## Output Files

### video.mp4
- Raw video from camera
- 24-60 FPS depending on settings
- H.264 codec (plays on any media player)

### joint_angles.png
Multi-panel plot showing:
```
Left Arm:
  - Shoulder flexion angle over time
  - Elbow flexion angle over time
  - Wrist extension angle over time

Right Arm:
  - (same as left)

Left Leg:
  - Hip flexion angle over time
  - Knee flexion angle over time

Right Leg:
  - (same as left)
```

### release_catch.png
Two-panel analysis:

**Top Panel (Release):**
- Frame at release moment
- Ball trajectory (cyan path)
- Release velocity vector
- Release angle
- Impact vectors

**Bottom Panel (Catch):**
- Frame at catch moment
- Flight trajectory
- Flight time and distance

### [model]_motion.mot
OpenSim-format file with:
```
nRows=150
nColumns=9  (or more for full body)
inDegrees=yes

Columns:
  time (seconds)
  joint_1_angle
  joint_2_angle
  ...
  ball_x (meters)
  ball_y (meters)
  ball_z (meters)
```

Can be directly used in OpenSim for IK/ID analysis.

### frames/
Directory with annotated PNG images:
```
frame_00001.png - Frame 1 with skeleton overlay
frame_00002.png - Frame 2 with skeleton overlay
...
frame_00150.png - Frame 150
```

Each frame shows:
- Live video background
- Pose skeleton (joints + lines)
- Ball detection (green circle)
- Ball trajectory path (cyan line)
- Joint angle labels

## Configuration

### Detection Interval
- **1** - Every frame (highest accuracy, slowest)
- **2** - Every 2nd frame (balanced)
- **3+** - Every Nth frame (faster, lower accuracy)

### Recording Duration
- Default: 10 seconds
- Can adjust before recording

### Target FPS
- Default: Auto-detect from camera
- Can override for consistent framerate

## Performance Tips

💡 **For Smooth Recording:**
- Ensure good lighting for pose detection
- Keep motion in frame center
- Use detection_interval=2 for faster processing
- Run only recording tab (close other apps)

💡 **For Better Ball Detection:**
- Use bright/contrasting ball color (green default)
- Ensure ball is clearly visible
- Record at higher FPS if available
- Check ball detection in output video

💡 **For Faster Analysis:**
- Use Arm26 model instead of Full Body
- Skip release/catch analysis if not needed
- Reduce frame export quality if needed

## Example Workflow

```bash
# 1. Record throwing motion with arm26 model
→ "Start Recording"
→ Throw ball at camera
→ App auto-generates MOT file

# 2. Analyze results
→ View joint_angles.png
→ Check shoulder/elbow angles
→ Inspect release_catch.png for dynamics

# 3. Use in OpenSim
→ Open arm26_ball_motion.mot in OpenSim
→ Run inverse kinematics with recorded markers
→ Compare with model predictions
→ Calculate muscle forces
```

## Advanced: Manual Analysis

Can manually analyze existing videos:

1. Click "📊 Analyze Recording"
2. Select existing video file
3. Choose OpenSim model
4. Click OK
5. App processes and generates MOT file

Useful for re-analyzing with different models or settings.

## Troubleshooting

### No Poses Detected
**Problem:** "No poses detected in any frame"
**Solutions:**
- Improve lighting (better illumination needed)
- Move closer to camera
- Ensure full body visible
- Try slower motion (faster motion may be blurry)

### Ball Not Detected
**Problem:** "No ball detections"
**Solutions:**
- Check ball color is green (or adjust HSV range)
- Ensure ball is clearly visible
- Increase illumination
- Use ball larger than ~40 pixels

### Video Won't Play
**Problem:** video.mp4 cannot open
**Solutions:**
- Install VLC Media Player
- Try different media player
- Check file wasn't corrupted
- Check disk space during recording

### Slow Recording
**Problem:** Dropped frames / choppy video
**Solutions:**
- Increase detection_interval to 2 or 3
- Close other applications
- Check camera framerate
- Reduce screen resolution
- Use Arm26 instead of Full Body model

### IP Camera Connection Failed
**Problem:** Cannot connect to IP address
**Solutions:**
- Verify phone and computer on same WiFi
- Test: `ping 192.168.0.107`
- Ensure IP Webcam app is running
- Check phone screen is not off
- Try restarting app on phone

## Integration with OpenSim

### Importing MOT Files

In OpenSim:

1. **File → Import → Motion**
2. **Select:** `[model]_motion.mot`
3. **Choose model:** `arm26_ball.osim` or `Full_Body_with_ball.osim`
4. **Run IK/ID** with recorded motion

### Using with Generic Model

For other OpenSim models:
1. Edit MOT file to match model coordinates
2. Rename joints to match your model
3. Scale positions if needed
4. Import into OpenSim

## Next Steps

1. **Record first session** - Get comfortable with UI
2. **Analyze output files** - Check video and angles
3. **Import to OpenSim** - Test MOT compatibility
4. **Refine parameters** - Optimize for your use case

## Support

For issues or questions:
- Check logs: `C:\Git\app\logs\app_*.log`
- Review console output during recording
- See `RECORDING_QUICKSTART.md` for basic recording
- Check `RECORDING_FIXES.md` for known issues

---

**Status:** ✅ Advanced Recording Ready  
**Last Updated:** May 22, 2026
