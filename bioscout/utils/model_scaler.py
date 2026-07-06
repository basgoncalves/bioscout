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

        # Optional: subject name / mass to stamp on the ScaleTool (otherwise the
        # template setup XML's baked-in subject name & mass are inherited).
        self.subject_name = None
        self.subject_mass = None

        # Optional: path to a real ScaleTool setup XML (with a MeasurementSet).
        # If None, one is auto-discovered next to the markerset, else the bundled
        # example template is used.
        self.scale_setup_xml = None

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
        logger.info("Starting model scaling process...")

        # Real measurement-based scaling needs a ScaleTool setup XML (which
        # carries the MeasurementSet + marker-pairs). Locate one, then run
        # OpenSim's ScaleTool with this subject's paths substituted in.
        setup_xml = self._locate_scale_setup(markerset_path)
        if setup_xml is not None:
            try:
                scaled_model = self._scale_with_setup_xml(setup_xml, markerset_path)
                if scaled_model:
                    logger.info(f"Scaling complete! Scaled model: {scaled_model}")
                    return scaled_model, {}
            except Exception as e:
                logger.warning(f"ScaleTool execution failed: {e}")

        # Could not scale properly — fall back to an UNSCALED template copy so
        # the pipeline can continue, but make it loud (results use generic model).
        return self._fallback_template_copy(), {}

    def _output_model_path(self) -> Path:
        if self.output_model_filename:
            return self.output_model_dir / self.output_model_filename
        return self.output_model_dir / f"scaled_{self.template_model.stem}.osim"

    def _locate_scale_setup(self, markerset_path) -> Optional[Path]:
        """Find a real ScaleTool setup XML (one containing a MeasurementSet)."""
        candidates = []
        if self.scale_setup_xml:
            candidates.append(Path(self.scale_setup_xml))
        if markerset_path:
            # The user's setup_files folder usually holds the markerset + setup.
            candidates.append(Path(markerset_path).parent / "setup_scale.xml")
        # Bundled example as a last resort (matches the LASI/RASI marker protocol).
        candidates.append(Path(__file__).parent.parent / "example_data" /
                          "running" / "setupFiles" / "setup_scale.xml")
        for c in candidates:
            try:
                if c and Path(c).is_file():
                    logger.info(f"Using ScaleTool setup: {c}")
                    return Path(c)
            except Exception:
                continue
        logger.warning(
            "No ScaleTool setup XML found (need one with a MeasurementSet). "
            "Place a 'setup_scale.xml' in your setup_files folder for real scaling.")
        return None

    def _scale_with_setup_xml(self, setup_xml: Path, markerset_path) -> Optional[str]:
        """Run OpenSim's ScaleTool from an existing setup, overriding paths.

        Preserves the setup's MeasurementSet / marker-pairs (the part that makes
        scaling correct) and only swaps in this subject's model, markerset, TRC,
        time range and output path — all as absolute paths.
        """
        import opensim as osim

        out_model = self._output_model_path()
        out_model.parent.mkdir(parents=True, exist_ok=True)

        scale_tool = osim.ScaleTool(str(setup_xml))

        # ScaleTool prepends getPathToSubject() (defaults to the setup XML's own
        # directory) to every file name it's given -- which turns our absolute
        # marker/model paths into 'setupFiles\C:\Users\...' and makes them
        # unopenable. Clear it so the absolute paths below are used verbatim.
        try:
            scale_tool.setPathToSubject("")
        except Exception:
            pass

        # The setup XML was authored for another subject (name/mass baked in).
        # Set this subject's name and, if provided, mass -- otherwise the model
        # inherits the template subject's mass (ScaleTool scales mass to it).
        try:
            scale_tool.setName(self.subject_name or self.template_model.stem)
        except Exception:
            pass
        if getattr(self, "subject_mass", None):
            try:
                scale_tool.setSubjectMass(float(self.subject_mass))
            except Exception:
                pass

        # Generic (unscaled) model + the model marker set used for scaling.
        gmm = scale_tool.getGenericModelMaker()
        gmm.setModelFileName(str(self.template_model.resolve()))
        if markerset_path and Path(markerset_path).is_file():
            gmm.setMarkerSetFileName(str(Path(markerset_path).resolve()))

        # Time range from the static TRC (markers are averaged over this range).
        try:
            md = osim.MarkerData(str(self.trc_file.resolve()))
            t0, t1 = md.getStartFrameTime(), md.getLastFrameTime()
        except Exception:
            t0, t1 = 0.0, 1.0
        tr = osim.ArrayDouble()
        tr.append(t0)
        tr.append(t1)

        trc_abs = str(self.trc_file.resolve())

        ms = scale_tool.getModelScaler()
        ms.setApply(True)
        ms.setMarkerFileName(trc_abs)
        ms.setTimeRange(tr)
        ms.setOutputModelFileName(str(out_model.resolve()))
        ms.setOutputScaleFileName(str((self.destination_dir / "scale_set.xml").resolve()))

        mp = scale_tool.getMarkerPlacer()
        mp.setApply(True)
        mp.setMarkerFileName(trc_abs)
        mp.setTimeRange(tr)
        mp.setOutputModelFileName(str(out_model.resolve()))
        try:
            mp.setOutputMotionFileName(
                str((self.destination_dir / "static_output.mot").resolve()))
        except Exception:
            pass

        # Save the resolved setup next to the trial for inspection/repro.
        try:
            scale_tool.printToXML(str((self.destination_dir / "scale_setup.xml").resolve()))
        except Exception:
            pass

        logger.info("Running OpenSim ScaleTool (measurement-based)...")
        # ScaleTool.run() return value is inconsistent across OpenSim builds, so
        # the file's existence is the source of truth.
        ret = scale_tool.run()
        if out_model.exists():
            logger.info(f"Scaled model created: {out_model}")
            return str(out_model)
        logger.warning(f"ScaleTool ran (returned {ret}) but no model at {out_model}")
        return None

    def _fallback_template_copy(self) -> str:
        """Copy the unscaled template so the pipeline can proceed (loud warning)."""
        import shutil
        out_model = self._output_model_path()
        out_model.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.template_model, out_model)
        logger.warning(
            f"[SCALING FALLBACK] Wrote an UNSCALED copy of the generic model to "
            f"{out_model}. Downstream results use the generic (non-subject-scaled) "
            f"model. Add a 'setup_scale.xml' (with a MeasurementSet) to your "
            f"setup_files folder for real scaling.")
        return str(out_model)
