#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Video analysis script for generating joint angles and MOT files from recorded video."""

import argparse
import sys
from pathlib import Path
import io

# Fix stdout encoding on Windows to support Unicode characters
if sys.platform == 'win32':
    # Reconfigure stdout to use UTF-8 encoding with error handling
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for required dependencies
try:
    import cv2
    import mediapipe
    from record.video import MovementTracker, ARM26_BALL_CONFIG, FULL_BODY_CONFIG, AVAILABLE_MODELS, _LANDMARK_NAMES
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}", file=sys.stderr)
    print("ERROR: cv2 (OpenCV) not installed. Install with: pip install opencv-python", file=sys.stderr)
    sys.exit(1)


def main():
    # Get available model names for argument parser
    available_model_names = list(AVAILABLE_MODELS.keys())

    parser = argparse.ArgumentParser(description="Analyze video and generate MOT files")
    parser.add_argument("--video", type=str, required=True, help="Input video file")
    parser.add_argument("--model", type=str, choices=available_model_names,
                        default="arm26_ball" if "arm26_ball" in available_model_names else available_model_names[0],
                        help=f"OpenSim model to use. Available: {', '.join(available_model_names)}")
    parser.add_argument("--detect-interval", type=int, default=1, help="Pose detection interval")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: video directory)")
    parser.add_argument("--start-time", type=float, default=None,
                        help="Start time in seconds (trim video before this)")
    parser.add_argument("--end-time", type=float, default=None,
                        help="End time in seconds (trim video after this)")
    parser.add_argument("--player-rect", type=str, default=None,
                        help="Bounding box for player: x1,y1,x2,y2 (video pixels)")
    parser.add_argument("--frame-anchors", type=str, default=None,
                        help="Path to JSON file mapping frame_idx -> [x1,y1,x2,y2] "
                             "hard-reset anchors for adaptive tracking")
    parser.add_argument("--pose-data", type=str, default=None,
                        help="Path to JSON file mapping frame_idx -> {landmark: [x,y]} "
                             "pre-computed landmarks from the GUI (skips re-detection)")

    args = parser.parse_args()

    try:
        import time

        video_path = Path(args.video)
        if not video_path.exists():
            print(f"ERROR: Video file not found: {video_path}")
            return 1

        # Check file size and wait if needed (ensure video is fully written)
        file_size = video_path.stat().st_size
        print(f"Video file size: {file_size / (1024*1024):.1f} MB")

        if file_size < 1000000:  # Less than 1 MB
            print("WARNING: Video file is very small. Waiting for file to finalize...")
            time.sleep(2)

        # Set output directory — always inside a timestamped subfolder
        from datetime import datetime
        timestamp = datetime.now().strftime("video_analysis_%Y_%m_%d_%H_%M")
        base_dir = Path(args.output_dir) if args.output_dir else video_path.parent
        output_dir = base_dir / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Analyzing video: {video_path}")
        print(f"Output directory: {output_dir}")
        print(f"Model: {args.model}")

        # Get video info with better error handling
        print(f"\nOpening video file: {video_path}")
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"ERROR: Cannot open video file: {video_path}")
            print(f"ERROR: File exists: {video_path.exists()}")
            print(f"ERROR: File size: {video_path.stat().st_size} bytes")
            print(f"ERROR: File readable: {video_path.is_file() and video_path.stat().st_size > 0}")

            # Try with absolute path
            abs_path = video_path.resolve()
            print(f"ERROR: Trying with absolute path: {abs_path}")
            cap = cv2.VideoCapture(str(abs_path))
            if not cap.isOpened():
                print(f"ERROR: Also failed with absolute path")
                print(f"ERROR: This may be a codec issue or corrupted video file")
                return 1

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        cap.release()

        print(f"Video info: {total_frames} frames @ {fps:.1f} fps (~{duration:.1f}s)")

        # Parse time trim / player-point args
        start_frame = int(args.start_time * fps) if args.start_time is not None else 0
        end_frame   = int(args.end_time   * fps) if args.end_time   is not None else total_frames
        if args.start_time is not None or args.end_time is not None:
            print(f"Time trim: {args.start_time or 0:.2f}s → {args.end_time or duration:.2f}s  "
                  f"(frames {start_frame}–{end_frame})")

        # Load per-frame anchor rects
        frame_anchors = {}   # {frame_idx: (x1,y1,x2,y2)}
        if args.frame_anchors:
            try:
                import json as _json
                with open(args.frame_anchors) as _f:
                    raw = _json.load(_f)
                frame_anchors = {int(k): tuple(v) for k, v in raw.items()}
                print(f"Frame anchors: {len(frame_anchors)} loaded from {args.frame_anchors}")
            except Exception as e:
                print(f"WARNING: Could not load frame anchors: {e}")

        # Load pre-computed GUI poses (skips MediaPipe re-detection when provided)
        pose_data = {}  # {frame_idx: {landmark_name: (x, y)}}
        if args.pose_data:
            try:
                import json as _json
                with open(args.pose_data) as _f:
                    raw = _json.load(_f)
                pose_data = {int(k): {name: tuple(v) for name, v in lms.items()}
                             for k, lms in raw.items()}
                print(f"Pre-computed poses: {len(pose_data)} frames loaded from {args.pose_data}")
            except Exception as e:
                print(f"WARNING: Could not load pose data: {e}")

        player_rect = None
        if args.player_rect:
            try:
                x1, y1, x2, y2 = map(int, args.player_rect.split(','))
                player_rect = (min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
                print(f"Player region: {player_rect}")
            except ValueError:
                print(f"WARNING: Invalid --player-rect value '{args.player_rect}', ignoring.")

        # Export trimmed video clip (only if a time trim was requested)
        trimmed_video_path = None
        if start_frame > 0 or end_frame < total_frames - 1:
            trimmed_video_path = output_dir / f"{video_path.stem}_trimmed.mp4"
            print(f"\nExporting trimmed clip → {trimmed_video_path.name}")
            cap_trim = cv2.VideoCapture(str(video_path))
            vw = int(cap_trim.get(cv2.CAP_PROP_FRAME_WIDTH))
            vh = int(cap_trim.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_vid = cv2.VideoWriter(str(trimmed_video_path), fourcc, fps, (vw, vh))
            cap_trim.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            n_trim = min(end_frame, total_frames - 1) - start_frame + 1
            written = 0
            for _ in range(n_trim):
                ret, frm = cap_trim.read()
                if not ret:
                    break
                out_vid.write(frm)
                written += 1
            cap_trim.release()
            out_vid.release()
            print(f"  Wrote {written} frames ({written / fps:.2f}s)")

        # Initialize tracker and analyze
        tracker = MovementTracker()

        # Check if we should use PNG frames fallback (if video file is too small or has very few frames)
        use_png_fallback = False
        png_frames_dir = output_dir / "frames_raw"

        if total_frames < 10 and png_frames_dir.exists():
            png_files = sorted(list(png_frames_dir.glob("frame_*.png")))
            if len(png_files) > total_frames:
                print(f"WARNING: Video file has only {total_frames} frames but PNG fallback has {len(png_files)}")
                print(f"Using PNG frames instead of video file...")
                use_png_fallback = True

        # Extract frames and detect poses
        print("\nExtracting frames and detecting poses...")
        frame_count = 0
        pose_count = 0
        ball_count = 0

        # Adaptive ROI tracking: starts from player_rect (or a sensible default),
        # then follows the player by updating the search window each frame.
        _PAD_FRAC  = 0.6   # padding around detected bbox (fraction of bbox size)
        _PAD_MIN   = 60    # minimum padding in pixels
        _EXPAND_ON_MISS = 0.25  # grow search window by this fraction if no pose found
        _MAX_MISSES = 5    # after this many consecutive misses, reset to default crop
        consecutive_misses = 0
        last_cx: float | None = None   # last detected player centroid (full-frame px)
        last_cy: float | None = None

        # When no player rect is drawn, default to the top 80 % of the frame.
        # In broadcast basketball footage the court occupies the upper portion;
        # the bottom strip is typically close-camera crowd that would otherwise
        # score higher confidence than the distant player on the court.
        if player_rect:
            search_rect = player_rect
            _default_rect = player_rect
            print(f"Player rect provided — adaptive tracking from {player_rect}")
        else:
            # Will be filled from actual frame dimensions on first frame
            search_rect = None
            _default_rect = None   # set once on first frame
            print("No player rect drawn — defaulting to top 80% of frame. "
                  "For best results, draw a rect around the player before running.")

        if use_png_fallback:
            # Read from PNG frames instead of video
            png_files = sorted(list(png_frames_dir.glob("frame_*.png")))
            frames_to_process = [(cv2.imread(str(f)), Path(f).name) for f in png_files]
            print(f"Reading {len(frames_to_process)} PNG frames from {png_frames_dir}")
        else:
            # Read from video file
            cap = cv2.VideoCapture(str(video_path))
            frames_to_process = []

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames_to_process.append((frame, f"frame_{frame_count:06d}"))
                frame_count = len(frames_to_process)

            cap.release()
            print(f"Read {len(frames_to_process)} frames from video file")

        # Now process all frames (whether from video or PNG)
        for frame_idx, (frame, frame_label) in enumerate(frames_to_process):
            if frame is None:
                continue

            # Time trim: skip frames outside requested range
            if frame_idx < start_frame:
                continue
            if frame_idx > end_frame:
                break

            frame_count = frame_idx + 1

            if frame_count % max(1, int(fps)) == 0:  # Progress every second
                print(f"  Frame {frame_count}/{len(frames_to_process)}")

            # Detect pose (adaptive ROI tracking)
            landmarks = None
            if pose_data:
                # Use pre-computed GUI poses — no re-detection needed
                landmarks = pose_data.get(frame_idx)
            elif frame_count % args.detect_interval == 0:
                try:
                    import mediapipe as mp
                    h_full, w_full = frame.shape[:2]

                    # Hard-reset search_rect from a user-placed anchor if one exists
                    if frame_idx in frame_anchors:
                        ax1, ay1, ax2, ay2 = frame_anchors[frame_idx]
                        search_rect = (min(ax1,ax2), min(ay1,ay2),
                                       max(ax1,ax2), max(ay1,ay2))
                        consecutive_misses = 0
                        # Reset temporal centroid so first detection after anchor
                        # uses crop centre (not stale centroid from wrong player)
                        last_cx = (ax1 + ax2) / 2.0
                        last_cy = (ay1 + ay2) / 2.0
                        print(f"  [anchor] Frame {frame_idx}: ROI reset to {search_rect}")

                    # On the very first detection frame, build the default crop
                    # (top 80 % of frame) if no player_rect was supplied.
                    if not player_rect and search_rect is None:
                        _default_rect = (0, 0, w_full, int(h_full * 0.80))
                        search_rect = _default_rect

                    # Build crop from current search_rect
                    if search_rect:
                        rx1, ry1, rx2, ry2 = search_rect
                        rx1c = max(0, rx1);       ry1c = max(0, ry1)
                        rx2c = min(w_full, rx2);  ry2c = min(h_full, ry2)
                        detect_frame = frame[ry1c:ry2c, rx1c:rx2c]
                        off_x, off_y = rx1c, ry1c
                    else:
                        detect_frame = frame
                        off_x, off_y = 0, 0

                    if detect_frame.size == 0:
                        consecutive_misses += 1
                    else:
                        h_d, w_d = detect_frame.shape[:2]
                        mp_image = mp.Image(
                            image_format=mp.ImageFormat.SRGB,
                            data=cv2.cvtColor(detect_frame, cv2.COLOR_BGR2RGB)
                        )
                        result = tracker._pose_landmarker.detect(mp_image)
                        if result.pose_landmarks:
                            pose_count += 1
                            consecutive_misses = 0

                            # Pick person closest to last detected centroid
                            # (temporal consistency beats crop-centre distance).
                            # Falls back to crop centre when no prior centroid.
                            if last_cx is not None:
                                ref_x, ref_y = last_cx - off_x, last_cy - off_y
                            else:
                                ref_x, ref_y = w_d / 2.0, h_d / 2.0
                            best_idx = 0
                            best_dist = float('inf')
                            for pi, person in enumerate(result.pose_landmarks):
                                xs = [lm.x for lm in person]
                                ys = [lm.y for lm in person]
                                px = (sum(xs) / len(xs)) * w_d
                                py = (sum(ys) / len(ys)) * h_d
                                d = (px - ref_x)**2 + (py - ref_y)**2
                                if d < best_dist:
                                    best_dist = d
                                    best_idx = pi
                            chosen = result.pose_landmarks[best_idx]
                            _VIS_THRESH = 0.3
                            landmarks = {
                                name: (lm.x * w_d + off_x, lm.y * h_d + off_y)
                                for name, lm in zip(_LANDMARK_NAMES, chosen)
                                if (lm.visibility or 0.0) >= _VIS_THRESH
                            }

                            # Update search_rect + temporal centroid
                            if landmarks:
                                lxs = [x for x, y in landmarks.values()]
                                lys = [y for x, y in landmarks.values()]
                                lx1, lx2 = min(lxs), max(lxs)
                                ly1, ly2 = min(lys), max(lys)
                                # Store centroid in full-frame coords
                                last_cx = (lx1 + lx2) / 2.0
                                last_cy = (ly1 + ly2) / 2.0
                                bw = lx2 - lx1
                                bh = ly2 - ly1
                                pad_x = max(_PAD_MIN, int(bw * _PAD_FRAC))
                                pad_y = max(_PAD_MIN, int(bh * _PAD_FRAC))
                                search_rect = (
                                    int(lx1 - pad_x),
                                    int(ly1 - pad_y),
                                    int(lx2 + pad_x),
                                    int(ly2 + pad_y),
                                )
                        else:
                            # No pose in current crop — expand the search window
                            consecutive_misses += 1
                            if consecutive_misses >= _MAX_MISSES:
                                # Reset to default crop after too many misses
                                search_rect = player_rect if player_rect else _default_rect
                                print(f"  [track] Lost player at frame {frame_idx}, "
                                      f"resetting search window")
                            elif search_rect:
                                rx1, ry1, rx2, ry2 = search_rect
                                rw = rx2 - rx1;  rh = ry2 - ry1
                                ex = int(rw * _EXPAND_ON_MISS)
                                ey = int(rh * _EXPAND_ON_MISS)
                                search_rect = (rx1 - ex, ry1 - ey,
                                               rx2 + ex, ry2 + ey)
                except Exception:
                    landmarks = None

            # Detect ball
            ball = tracker._detect_ball(frame)
            if ball:
                ball_count += 1

            # Store record
            frame_time = frame_idx / fps
            tracker._records.append((frame.copy(), frame_time, landmarks, ball))
            tracker._duration_seconds = duration

        n_processed = len(tracker._records)
        print(f"[OK] Extracted {n_processed} frames "
              f"(frames {start_frame}–{min(end_frame, total_frames - 1)})")
        print(f"  Pose detections: {pose_count}")
        print(f"  Ball detections: {ball_count}")

        if pose_count == 0:
            print("\nWARNING: No poses detected. Check video quality and lighting.")

        # Check landmark coverage — warn if body is heavily cropped
        KEY_LANDMARKS = ('left_hip', 'right_hip', 'left_knee', 'right_knee',
                         'left_ankle', 'right_ankle', 'left_shoulder', 'right_shoulder')
        visible_counts = []
        for _, _, lm, _ in tracker._records:
            if lm:
                visible_counts.append(sum(1 for k in KEY_LANDMARKS if lm.get(k)))
        if visible_counts:
            avg_visible = sum(visible_counts) / len(visible_counts)
            if avg_visible < len(KEY_LANDMARKS) * 0.6:
                print(f"\nWARNING: Only {avg_visible:.1f}/{len(KEY_LANDMARKS)} key landmarks "
                      f"visible on average. The body may be cropped or too close to the camera. "
                      f"MOT accuracy will be low — try a wider shot from the side.")

        # Normalize timestamps so the trimmed clip starts at t=0
        if tracker._records:
            t0 = tracker._records[0][1]
            tracker._records = [
                (f, t - t0, lm, b) for f, t, lm, b in tracker._records
            ]
            tracker._duration_seconds = tracker._records[-1][1]
            trimmed_dur = tracker._duration_seconds
            print(f"  Clip duration after trim: {trimmed_dur:.2f}s")

        # Generate analysis outputs
        print(f"\nGenerating analysis outputs...")

        # Select model config from available models
        print(f"\n[Model Selection]")
        print(f"  Requested model: '{args.model}'")
        print(f"  Available models: {sorted(AVAILABLE_MODELS.keys())}")

        if args.model in AVAILABLE_MODELS:
            model_config = AVAILABLE_MODELS[args.model]
            print(f"  ✓ Model found: {model_config.name}")
        else:
            print(f"  ✗ ERROR: Model '{args.model}' not found!")
            print(f"  WARNING: Using fallback model (this may produce incorrect MOT)")
            # Fallback to first available model
            model_config = list(AVAILABLE_MODELS.values())[0]
            print(f"  Fallback: Using '{model_config.name}'")
            print(f"  To fix: Run recorder with --model {sorted(AVAILABLE_MODELS.keys())[0]}")

        # Create subdirectories for organized output
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(exist_ok=True)

        # Save frames
        print(f"  Saving annotated frames to {frames_dir}...")
        tracker.save_frames(frames_dir)

        # Plot joint angles in root of session folder
        angles_path = output_dir / "joint_angles.png"
        print(f"  Generating joint angle plot...")
        tracker.plot_joint_angles(save_path=str(angles_path))

        # Analyze release/catch only for ball-tracking models
        release_path = None
        if 'ball' in args.model.lower() and ball_count > 10:
            release_path = output_dir / "release_catch.png"
            print(f"  Analyzing release/catch...")
            try:
                tracker.analyze_release(save_path=str(release_path))
            except Exception as e:
                print(f"    Could not analyze release/catch: {e}")

        # Write MOT file to root of session folder
        mot_filename = f"{model_config.name}.mot"
        mot_path = output_dir / mot_filename
        print(f"  Generating MOT file for OpenSim...")
        tracker.write_opensim_mot(save_path=str(mot_path), model_config=model_config)

        # Clean up raw frames (only kept as fallback during recording)
        frames_raw_dir = output_dir / "frames_raw"
        if frames_raw_dir.exists():
            import shutil
            shutil.rmtree(frames_raw_dir)
            print(f"  Cleaned up temporary frames_raw directory")

        # Print summary
        print(f"\n[OK] Analysis complete!")
        if trimmed_video_path and trimmed_video_path.exists():
            print(f"  Trimmed clip: {trimmed_video_path}")
        print(f"  MOT file: {mot_path}")
        print(f"  Frames: {frames_dir}")
        print(f"  Joint angle plot: {angles_path}")
        if release_path and release_path.exists():
            print(f"  Release/catch analysis: {release_path}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
