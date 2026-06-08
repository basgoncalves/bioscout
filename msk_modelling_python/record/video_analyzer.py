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

        # Set output directory
        if args.output_dir:
            output_dir = Path(args.output_dir)
        else:
            output_dir = video_path.parent

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

            frame_count = frame_idx + 1

            if frame_count % max(1, int(fps)) == 0:  # Progress every second
                print(f"  Frame {frame_count}/{len(frames_to_process)}")

            # Detect pose
            if frame_count % args.detect_interval == 0:
                try:
                    import mediapipe as mp
                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    )
                    result = tracker._pose_landmarker.detect(mp_image)
                    if result.pose_landmarks:
                        pose_count += 1
                        h, w = frame.shape[:2]
                        landmarks = {
                            name: (lm.x * w, lm.y * h)
                            for name, lm in zip(_LANDMARK_NAMES,
                                               result.pose_landmarks[0])
                        }
                except:
                    landmarks = None
            else:
                landmarks = None

            # Detect ball
            ball = tracker._detect_ball(frame)
            if ball:
                ball_count += 1

            # Store record
            frame_time = frame_idx / fps
            tracker._records.append((frame.copy(), frame_time, landmarks, ball))
            tracker._duration_seconds = duration

        print(f"[OK] Extracted {frame_count} frames")
        print(f"  Pose detections: {pose_count}")
        print(f"  Ball detections: {ball_count}")

        if pose_count == 0:
            print("\nWARNING: No poses detected. Check video quality and lighting.")

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

        # Analyze release/catch (if ball detected)
        release_path = None
        if ball_count > 10:
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
