"""GRF Phase Detector - Automatic movement phase detection from force data."""

import numpy as np
from scipy import signal
from pathlib import Path
import sys
from typing import List, Tuple, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import logger


class GRFPhaseDetector:
    """Detect movement phases from Ground Reaction Force data."""

    def __init__(self):
        """Initialize phase detector."""
        self.min_phase_duration = 10  # Minimum samples in a phase
        self.force_threshold_percentile = 0.05  # 5% threshold by default

    def detect_running_phases(self, grf_data: np.ndarray, threshold: float = 0.5) -> List[Tuple[int, int]]:
        """
        Detect running phases (contact cycles) from vertical GRF.

        Phases: Heel strike → Ground contact → Toe-off → Flight

        Args:
            grf_data: Vertical ground reaction force data
            threshold: Force threshold as fraction of body weight (0.0-1.0)

        Returns:
            List of (start_idx, end_idx) tuples for each contact phase
        """
        try:
            # Normalize by max force
            max_force = np.max(grf_data)
            if max_force <= 0:
                return []

            normalized = grf_data / max_force

            # Find above-threshold regions
            above_threshold = normalized > threshold

            # Find transitions
            diff = np.diff(above_threshold.astype(int))

            # Starts: 0→1 transition (off_to_on)
            starts = np.where(diff == 1)[0] + 1
            # Ends: 1→0 transition (on_to_off)
            ends = np.where(diff == -1)[0]

            # Ensure matching pairs
            if len(starts) == 0 or len(ends) == 0:
                return []

            if starts[0] > ends[0]:
                starts = starts[:-1]

            if len(starts) > len(ends):
                ends = np.append(ends, len(grf_data) - 1)

            # Filter short phases
            phases = [(s, e) for s, e in zip(starts, ends)
                     if e - s >= self.min_phase_duration]

            logger.info(f"Running detection: Found {len(phases)} contact phases")
            return phases

        except Exception as e:
            logger.error(f"Error detecting running phases: {str(e)}")
            return []

    def detect_squatting_phases(self, grf_data: np.ndarray) -> Dict[str, List[Tuple[int, int]]]:
        """
        Detect squatting phases (descent, bottom, ascent) from vertical GRF.

        Phases:
        - Descent: Force increasing (first derivative positive)
        - Bottom: Local minimum (peak force)
        - Ascent: Force decreasing (first derivative negative)

        Args:
            grf_data: Vertical ground reaction force data

        Returns:
            Dict with 'descent', 'bottom', 'ascent' phase lists
        """
        try:
            # Find the deepest point (minimum force)
            # For a squat, the subject pushes down then returns
            min_idx = np.argmin(grf_data)

            # Find descent phase: rising force towards the bottom
            # Look backwards from minimum for the start of descent
            descent_start = 0
            for i in range(min_idx, 0, -1):
                if grf_data[i] < grf_data[i-1]:
                    descent_start = i
                else:
                    break

            # Find ascent phase: rising force from the bottom
            # Look forwards from minimum for the end of ascent
            ascent_end = len(grf_data) - 1
            for i in range(min_idx, len(grf_data) - 1):
                if grf_data[i] < grf_data[i+1]:
                    continue
                else:
                    ascent_end = i
                    break

            # Define phases
            phases = {
                'descent': [(descent_start, min_idx)],
                'bottom': [(max(min_idx - 5, 0), min(min_idx + 5, len(grf_data)-1))],
                'ascent': [(min_idx, ascent_end)]
            }

            logger.info(f"Squatting detection: Descent {descent_start}-{min_idx}, "
                       f"Bottom {min_idx}, Ascent {min_idx}-{ascent_end}")
            return phases

        except Exception as e:
            logger.error(f"Error detecting squatting phases: {str(e)}")
            return {'descent': [], 'bottom': [], 'ascent': []}

    def detect_jumping_phases(self, grf_data: np.ndarray, threshold: float = 0.5) -> Dict[str, List[Tuple[int, int]]]:
        """
        Detect jumping phases (flight, landing, takeoff) from vertical GRF.

        Phases:
        - Landing: Force spike above threshold
        - Propulsion: Force building during push-off
        - Takeoff: Force drops below threshold
        - Flight: No contact (force near zero)

        Args:
            grf_data: Vertical ground reaction force data
            threshold: Force threshold as fraction of max

        Returns:
            Dict with phase lists
        """
        try:
            max_force = np.max(grf_data)
            if max_force <= 0:
                return {'landing': [], 'propulsion': [], 'takeoff': [], 'flight': []}

            normalized = grf_data / max_force

            # Find contact phases (above threshold)
            contact = normalized > threshold
            diff = np.diff(contact.astype(int))

            landings = np.where(diff == 1)[0] + 1
            takeoffs = np.where(diff == -1)[0]

            # Match landings with takeoffs
            contact_phases = []
            for landing in landings:
                takeoff = np.min(np.where(takeoffs > landing)[0])
                if takeoff:
                    contact_phases.append((landing, takeoffs[takeoff]))

            # Identify peaks (propulsion) within each contact phase
            propulsion_phases = []
            for start, end in contact_phases:
                peak_idx = start + np.argmax(grf_data[start:end])
                propulsion_phases.append((start, peak_idx))

            phases = {
                'landing': contact_phases,
                'propulsion': propulsion_phases,
                'takeoff': contact_phases,  # Same as contact
                'flight': [(end, next_start) for end, next_start in
                          zip(takeoffs[:-1], landings[1:]) if next_start > end]
            }

            logger.info(f"Jumping detection: {len(contact_phases)} jump cycles detected")
            return phases

        except Exception as e:
            logger.error(f"Error detecting jumping phases: {str(e)}")
            return {'landing': [], 'propulsion': [], 'takeoff': [], 'flight': []}

    def detect_walking_phases(self, grf_data_left: np.ndarray, grf_data_right: np.ndarray,
                             threshold: float = 0.1) -> Dict[str, List[Tuple[int, int]]]:
        """
        Detect walking phases from two feet (double support, single support).

        Phases:
        - Double support: Both feet in contact
        - Single support: One foot in contact
        - Swing: One foot in air

        Args:
            grf_data_left: Vertical force from left foot
            grf_data_right: Vertical force from right foot
            threshold: Force threshold as fraction of max

        Returns:
            Dict with 'double_support', 'single_support_l', 'single_support_r', 'swing' phases
        """
        try:
            max_left = np.max(grf_data_left)
            max_right = np.max(grf_data_right)

            if max_left <= 0 or max_right <= 0:
                return {'double_support': [], 'single_support_l': [],
                       'single_support_r': [], 'swing': []}

            # Normalize
            left_contact = (grf_data_left / max_left) > threshold
            right_contact = (grf_data_right / max_right) > threshold

            # Define phases
            double_support = left_contact & right_contact
            single_left = left_contact & ~right_contact
            single_right = ~left_contact & right_contact

            # Convert to phase intervals
            def find_phases(contact_signal: np.ndarray) -> List[Tuple[int, int]]:
                diff = np.diff(contact_signal.astype(int))
                starts = np.where(diff == 1)[0] + 1
                ends = np.where(diff == -1)[0]

                phases = [(s, e) for s, e in zip(starts, ends)]
                return phases

            phases = {
                'double_support': find_phases(double_support),
                'single_support_l': find_phases(single_left),
                'single_support_r': find_phases(single_right),
                'swing': find_phases(~(left_contact | right_contact))
            }

            logger.info(f"Walking detection: Double={len(phases['double_support'])} cycles")
            return phases

        except Exception as e:
            logger.error(f"Error detecting walking phases: {str(e)}")
            return {'double_support': [], 'single_support_l': [],
                   'single_support_r': [], 'swing': []}

    def detect_phases(self, movement_type: str, grf_data: np.ndarray,
                     grf_data_right: Optional[np.ndarray] = None,
                     threshold: float = 0.5) -> Dict[str, List[Tuple[int, int]]]:
        """
        Detect phases based on movement type.

        Args:
            movement_type: One of 'running', 'squatting', 'jumping', 'walking'
            grf_data: Left foot GRF (or vertical for single-foot movements)
            grf_data_right: Right foot GRF (for walking)
            threshold: Force threshold (0.0-1.0)

        Returns:
            Dict of detected phases
        """
        if movement_type.lower() == 'running':
            return {'contact': self.detect_running_phases(grf_data, threshold)}

        elif movement_type.lower() == 'squatting':
            return self.detect_squatting_phases(grf_data)

        elif movement_type.lower() == 'jumping':
            return self.detect_jumping_phases(grf_data, threshold)

        elif movement_type.lower() == 'walking':
            if grf_data_right is None:
                logger.warning("Walking detection requires both left and right GRF data")
                return {}
            return self.detect_walking_phases(grf_data, grf_data_right, threshold)

        else:
            logger.warning(f"Unknown movement type: {movement_type}")
            return {}
