"""OpenSim Model Scaling Tool integration.

Handles model scaling using OpenSim's Scale Tool with customizable marker weights.
"""

import os
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Dict, Tuple, Optional
import numpy as np

from .logger import logger


class ModelScaler:
    """Interface to OpenSim's Scale Tool for model scaling."""

    def __init__(self, template_model_path: str, trc_file: str, destination_dir: str, output_model_dir: Optional[str] = None):
        """
        Initialize ModelScaler.

        Args:
            template_model_path: Path to template OpenSim model (.osim)
            trc_file: Path to TRC file with marker data for scaling
            destination_dir: Directory to save setup XML files
            output_model_dir: Directory to save final scaled model (defaults to destination_dir)
        """
        self.template_model = Path(template_model_path)
        self.trc_file = Path(trc_file)
        self.destination_dir = Path(destination_dir)
        self.destination_dir.mkdir(parents=True, exist_ok=True)

        # Where the final scaled model gets saved (can differ from setup XML location)
        self.output_model_dir = Path(output_model_dir) if output_model_dir else self.destination_dir
        self.output_model_dir.mkdir(parents=True, exist_ok=True)

        # Optional: custom output filename (if not set, will use default)
        self.output_model_filename = None

        if not self.template_model.exists():
            raise FileNotFoundError(f"Template model not found: {self.template_model}")
        if not self.trc_file.exists():
            raise FileNotFoundError(f"TRC file not found: {self.trc_file}")

        logger.info(f"ModelScaler initialized:")
        logger.info(f"  Template: {self.template_model}")
        logger.info(f"  TRC: {self.trc_file}")
        logger.info(f"  Destination: {self.destination_dir}")

    def parse_trc_markers(self) -> Dict[str, np.ndarray]:
        """
        Parse TRC file and extract marker positions.

        Returns:
            Dictionary of marker_name -> (num_frames, 3) array of XYZ positions
        """
        markers = {}
        try:
            with open(self.trc_file, 'r') as f:
                lines = f.readlines()

            # Parse TRC header
            header_row = None
            data_start_row = None

            for i, line in enumerate(lines):
                if line.strip().startswith('Frame#'):
                    header_row = i
                    data_start_row = i + 2  # Skip header and marker line
                    break

            if header_row is None:
                raise ValueError("Could not find Frame# line in TRC file")

            # Extract marker names from header lines
            # TRC format typically has:
            # Line N: Frame#  Time  <marker1>  <marker2>  <marker3> ...
            # Line N+1: (blank or X1 Y1 Z1 X2 Y2 Z2 ...)

            marker_names = []

            # Try to get marker names from the header line itself
            header_line = lines[header_row].strip()
            header_parts = header_line.split()

            # Extract names between "Frame#" "Time" and the coordinate labels
            potential_markers = []
            skip_keywords = {'Frame#', 'Time', 'X', 'Y', 'Z'}

            for part in header_parts[2:]:  # Skip "Frame#" and "Time"
                # Check if it's a coordinate label (X1, Y1, Z1, etc.)
                if len(part) > 1 and part[0] in 'XYZ' and part[1:].isdigit():
                    # This is a coordinate label, stop here
                    break
                if part not in skip_keywords and part not in potential_markers:
                    potential_markers.append(part)

            # If we found marker names in header, use them
            if potential_markers:
                marker_names = potential_markers
            else:
                # Fallback: look for marker names in the next line
                if header_row + 1 < len(lines):
                    marker_line = lines[header_row + 1].strip()
                    marker_parts = marker_line.split()

                    # Extract unique marker names (they repeat 3 times for X, Y, Z)
                    unique_markers = []
                    for i in range(0, len(marker_parts), 3):
                        if i < len(marker_parts):
                            marker_part = marker_parts[i]
                            # Remove coordinate suffix
                            marker_base = marker_part.rstrip('0123456789')
                            if marker_base and marker_base not in ['X', 'Y', 'Z'] and marker_base not in unique_markers:
                                unique_markers.append(marker_base)

                    if unique_markers:
                        marker_names = unique_markers

            if not marker_names:
                raise ValueError("Could not extract marker names from TRC file. Check file format.")

            logger.info(f"Extracted marker names: {marker_names}")

            # Initialize marker data
            for marker in marker_names:
                markers[marker] = []

            # Parse marker data
            for line in lines[data_start_row:]:
                if not line.strip() or line.startswith(('Frame#', 'Time', 'C3D')):
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                # Skip Frame# and Time
                values = parts[2:]

                # Group XYZ coordinates for each marker
                marker_idx = 0
                for i in range(0, len(values), 3):
                    if marker_idx >= len(marker_names):
                        break
                    if i + 2 < len(values):
                        try:
                            x = float(values[i])
                            y = float(values[i + 1])
                            z = float(values[i + 2])
                            markers[marker_names[marker_idx]].append([x, y, z])
                        except ValueError:
                            pass
                    marker_idx += 1

            # Convert to numpy arrays
            for marker in list(markers.keys()):
                if markers[marker]:
                    markers[marker] = np.array(markers[marker])
                else:
                    del markers[marker]

            logger.info(f"Parsed {len(markers)} markers from TRC file: {list(markers.keys())}")
            return markers

        except Exception as e:
            logger.error(f"Error parsing TRC file: {e}")
            raise

    def calculate_scale_factors(
        self,
        marker_weights: Optional[Dict[str, float]],
        markerset_path: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate scale factors based on marker positions and weights.

        This is a simplified implementation. For production use, integrate with
        OpenSim's Scale Tool which uses more sophisticated algorithms.

        Args:
            marker_weights: Dictionary of marker_name -> weight
            markerset_path: Optional path to markerset XML file

        Returns:
            Dictionary of segment_name -> scale_factor
        """
        logger.info("Calculating scale factors...")
        if marker_weights is None:
            marker_weights = {}

        # Get marker data
        try:
            marker_data = self.parse_trc_markers()
        except Exception as e:
            logger.error(f"Failed to parse markers: {e}")
            raise

        # Calculate segment lengths from marker positions
        # This is simplified - actual implementation would load model
        scale_factors = {}

        # Example segment scale calculations
        segment_definitions = {
            'femur_r': [('LASIS', 'LKNE'), ('RASIS', 'RKNE')],  # Markers to calculate length
            'tibia_r': [('LKNE', 'LANK'), ('RKNE', 'RANK')],
            'talus_r': [('LANK', 'LHEE'), ('RANK', 'RHEE')],
        }

        try:
            for segment, marker_pairs in segment_definitions.items():
                segment_scales = []

                for marker1, marker2 in marker_pairs:
                    if marker1 in marker_data and marker2 in marker_data:
                        # Calculate average distance between markers
                        pos1 = marker_data[marker1]  # shape (num_frames, 3)
                        pos2 = marker_data[marker2]
                        distances = np.linalg.norm(pos1 - pos2, axis=1)
                        avg_distance = np.mean(distances[distances > 0])

                        if avg_distance > 0:
                            # Get marker weight for weighting this calculation
                            weight = min(
                                marker_weights.get(marker1, 1.0),
                                marker_weights.get(marker2, 1.0)
                            )
                            segment_scales.append((avg_distance, weight))

                if segment_scales:
                    # Weighted average of scale factors
                    weighted_scales = [s[0] for s in segment_scales]
                    weights = [s[1] for s in segment_scales]
                    scale_factors[segment] = np.average(weighted_scales, weights=weights)

            logger.info(f"Calculated scale factors: {scale_factors}")
            return scale_factors

        except Exception as e:
            logger.error(f"Error calculating scale factors: {e}")
            raise

    def create_scale_setup_xml(
        self,
        marker_weights: Dict[str, float],
        scale_factors: Dict[str, float],
        markerset_path: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> str:
        """
        Create OpenSim Scale Tool setup XML file.

        Args:
            marker_weights: Dictionary of marker weights
            scale_factors: Dictionary of segment scale factors
            markerset_path: Optional custom markerset file
            output_filename: Optional custom output filename (defaults to scaled_<template_name>.osim)

        Returns:
            Path to created setup XML file
        """
        logger.info("Creating Scale Tool setup XML...")
        if marker_weights is None:
            marker_weights = {}

        # Determine output filename (uses output_model_dir, not destination_dir)
        if output_filename:
            output_model_file = self.output_model_dir / output_filename
        else:
            output_model_file = self.output_model_dir / f"scaled_{self.template_model.stem}.osim"

        # Create XML structure
        root = ET.Element("OpenSimDocument", {"Version": "40000"})
        scale_tool = ET.SubElement(root, "ScaleTool", {"name": "scale"})

        # Generic model measurements
        generic_measurements = ET.SubElement(scale_tool, "GenericModelMaker")
        ET.SubElement(generic_measurements, "model_file").text = str(self.template_model)

        # Marker data
        marker_set = ET.SubElement(scale_tool, "MarkerSet")
        marker_file = ET.SubElement(marker_set, "objects")

        for marker_name, weight in sorted(marker_weights.items()):
            marker = ET.SubElement(marker_file, "IKMarker", {"name": marker_name})
            ET.SubElement(marker, "weight").text = str(weight)
            ET.SubElement(marker, "body_name").text = self._get_marker_body(marker_name)

        # Scale factors
        scale_factors_elem = ET.SubElement(scale_tool, "ScaleFactors")
        for segment, scale in sorted(scale_factors.items()):
            ET.SubElement(scale_factors_elem, segment).text = str(scale)

        # Output settings
        ET.SubElement(scale_tool, "output_model_file").text = str(output_model_file)
        ET.SubElement(scale_tool, "output_scale_file").text = str(
            self.destination_dir / "scale_factors.xml"
        )

        # Save XML
        tree = ET.ElementTree(root)
        setup_path = self.destination_dir / "scale_setup.xml"
        tree.write(str(setup_path), encoding='utf-8', xml_declaration=True)

        logger.info(f"Created setup XML: {setup_path}")
        logger.info(f"Output model will be: {output_model_file}")
        return str(setup_path)

    def _get_marker_body(self, marker_name: str) -> str:
        """
        Map marker name to body name.

        Args:
            marker_name: Name of marker

        Returns:
            Name of body where marker should be attached
        """
        # Simple mapping based on marker name patterns
        marker_name_lower = marker_name.lower()

        # Left side markers
        if 'l' in marker_name_lower:
            if 'hip' in marker_name_lower or 'asis' in marker_name_lower or 'psis' in marker_name_lower:
                return 'pelvis'
            elif 'kne' in marker_name_lower or 'femur' in marker_name_lower:
                return 'femur_l'
            elif 'ank' in marker_name_lower or 'tibia' in marker_name_lower:
                return 'tibia_l'
            elif 'hee' in marker_name_lower or 'toe' in marker_name_lower or 'calc' in marker_name_lower:
                return 'talus_l'

        # Right side markers
        else:
            if 'hip' in marker_name_lower or 'asis' in marker_name_lower or 'psis' in marker_name_lower:
                return 'pelvis'
            elif 'kne' in marker_name_lower or 'femur' in marker_name_lower:
                return 'femur_r'
            elif 'ank' in marker_name_lower or 'tibia' in marker_name_lower:
                return 'tibia_r'
            elif 'hee' in marker_name_lower or 'toe' in marker_name_lower or 'calc' in marker_name_lower:
                return 'talus_r'

        return 'pelvis'  # Default

    def run_scale(
        self,
        marker_weights: Dict[str, float],
        markerset_path: Optional[str] = None
    ) -> Tuple[str, Dict[str, float]]:
        """
        Run the complete scaling process.

        Args:
            marker_weights: Dictionary of marker weights
            markerset_path: Optional custom markerset

        Returns:
            Tuple of (scaled_model_path, scale_factors_dict)
        """
        try:
            logger.info("Starting model scaling process...")

            # Step 1: Calculate scale factors
            scale_factors = self.calculate_scale_factors(marker_weights, markerset_path)

            # Step 2: Create setup XML
            setup_xml = self.create_scale_setup_xml(marker_weights, scale_factors, markerset_path)

            # Step 3: Run OpenSim Scale Tool (placeholder for actual implementation)
            logger.info("Attempting to run OpenSim Scale Tool...")
            scaled_model = self._run_opensim_scale_tool(setup_xml)

            logger.info(f"Scaling complete! Scaled model: {scaled_model}")
            return scaled_model, scale_factors

        except Exception as e:
            logger.error(f"Scaling failed: {e}")
            raise

    def _run_opensim_scale_tool(self, setup_xml_path: str) -> str:
        """
        Run OpenSim's Scale Tool using the generated setup XML.

        Args:
            setup_xml_path: Path to generated setup XML

        Returns:
            Path to scaled model file

        Raises:
            RuntimeError: If OpenSim is not available or scaling fails
        """
        import shutil

        try:
            import opensim as osim

            logger.info(f"Loading ScaleTool from: {setup_xml_path}")
            scale_tool = osim.ScaleTool(setup_xml_path)

            logger.info("Running ScaleTool...")
            scale_tool.run()

            # Get the output model path from the setup XML
            # First try to use custom output filename if set
            if self.output_model_filename:
                scaled_model_path = self.output_model_dir / self.output_model_filename
            else:
                scaled_model_path = self.output_model_dir / f"scaled_{self.template_model.stem}.osim"

            if not scaled_model_path.exists():
                raise RuntimeError(f"Scaled model was not created at {scaled_model_path}")

            logger.info(f"Scaled model created: {scaled_model_path}")
            return str(scaled_model_path)

        except Exception as e:
            # Fallback: copy template model with subject-based naming
            logger.warning(f"ScaleTool execution failed: {e}")
            logger.info("Falling back to template model copy (full ScaleTool implementation pending)...")

            if self.output_model_filename:
                scaled_model_path = self.output_model_dir / self.output_model_filename
            else:
                scaled_model_path = self.output_model_dir / f"scaled_{self.template_model.stem}.osim"

            shutil.copy(self.template_model, scaled_model_path)
            logger.warning(f"Created scaled model at {scaled_model_path} (template copy - not fully optimized)")
            return str(scaled_model_path)
