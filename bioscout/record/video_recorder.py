#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Video recording script using webcam or IP camera with pose estimation."""

import argparse
import sys
from pathlib import Path
from datetime import datetime
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
    from record.video import MovementTracker, ARM26_BALL_CONFIG, FULL_BODY_CONFIG, AVAILABLE_MODELS
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}", file=sys.stderr)
    print("ERROR: cv2 (OpenCV) not installed. Install with: pip install opencv-python", file=sys.stderr)
    sys.exit(1)


def main():
    # Get available model names for argument parser
    available_model_names = list(AVAILABLE_MODELS.keys())

    parser = argparse.ArgumentParser(description="Record video with pose estimation")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--camera", type=str, choices=["webcam", "ip"], default="webcam")
    parser.add_argument("--ip-address", type=str, default="http://192.168.0.107:8080/video")
    parser.add_argument("--model", type=str, choices=available_model_names,
                        default="arm26_ball" if "arm26_ball" in available_model_names else available_model_names[0],
                        help=f"OpenSim model to use. Available: {', '.join(available_model_names)}")
    parser.add_argument("--duration", type=int, default=10, help="Recording duration in seconds")
    parser.add_argument("--fps", type=float, default=None, help="Target FPS")
    parser.add_argument("--detect-interval", type=int, default=1, help="Pose detection interval")

    args = parser.parse_args()

    try:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Recording from {args.camera}...")
        print(f"Output directory: {output_dir}")
        print(f"Duration: {args.duration} seconds")
        print(f"Model: {args.model}")

        # Patch IP address in video.py if needed
        if args.camera == "ip":
            print(f"IP Address: {args.ip_address}")

        # Initialize tracker
        print(f"Initializing MovementTracker...")
        try:
            tracker = MovementTracker()
            print(f"✓ MovementTracker initialized successfully")
        except Exception as e:
            print(f"ERROR: Failed to initialize MovementTracker: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

        # Record video
        print(f"Starting video recording...")
        try:
            video_path = tracker.record_video(
                duration_seconds=args.duration,
                camera_type=args.camera,
                output_dir=output_dir,
                target_fps=args.fps,
                detection_interval=args.detect_interval
            )
        except Exception as e:
            print(f"ERROR: Exception during record_video: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

        if video_path is None:
            print("ERROR: Failed to record video - record_video returned None")
            return 1

        print(f"\n[OK] Video recorded successfully")
        print(f"  Path: {video_path}")

        # Select model config from available models
        if args.model in AVAILABLE_MODELS:
            model_config = AVAILABLE_MODELS[args.model]
        else:
            print(f"WARNING: Model '{args.model}' not found in available models")
            print(f"Available models: {', '.join(sorted(AVAILABLE_MODELS.keys()))}")
            # Fallback to first available model
            model_config = list(AVAILABLE_MODELS.values())[0]
            print(f"Using fallback model: {model_config.name}")

        # Save analysis outputs
        print(f"\nGenerating analysis outputs...")

        # Save frames
        frames_dir = output_dir / "frames"
        tracker.save_frames(frames_dir)

        # Plot joint angles
        angles_path = output_dir / "joint_angles.png"
        tracker.plot_joint_angles(save_path=str(angles_path))

        # Analyze release/catch (if ball detected)
        release_path = output_dir / "release_catch.png"
        try:
            tracker.analyze_release(save_path=str(release_path))
        except Exception as e:
            print(f"Could not analyze release/catch: {e}")

        # Write MOT file
        mot_filename = f"{model_config.name}_motion.mot"
        mot_path = output_dir / mot_filename
        tracker.write_opensim_mot(save_path=str(mot_path), model_config=model_config)

        print(f"\n[OK] Analysis complete!")
        print(f"  MOT file: {mot_path}")
        print(f"  Frames: {frames_dir}")
        print(f"  Plots: {angles_path}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
