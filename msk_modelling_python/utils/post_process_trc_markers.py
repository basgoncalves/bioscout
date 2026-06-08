#!/usr/bin/env python3
r"""
Post-process TRC files to ensure all trials have the same marker set.

This script scans all exported TRC files, detects all unique markers across
all trials, then rebuilds each TRC file to include all markers (with zeros
for markers that don't exist in that trial).

Usage:
    python post_process_trc_markers.py <output_folder>

Example:
    python post_process_trc_markers.py "C:\Git\research_documents\Uvienna\Teaching\BD2II - Biomechanical Motion Analysis in Practice\2026S\MoCap\P01"
"""

import os
import sys
from pathlib import Path
import re


def find_trc_files(root_dir):
    """Find all marker_experimental.trc files in directory tree."""
    trc_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == 'marker_experimental.trc':
                trc_files.append(Path(dirpath) / filename)
    return sorted(trc_files)


def parse_trc_file(trc_path):
    """
    Parse a TRC file and return structured data.

    Returns: {
        'header_0': str,        # PathFileType line
        'header_1': str,        # DataRate line
        'header_2': str,        # Marker names line
        'header_3': str,        # Coordinate labels line
        'markers': [str],       # List of marker names in order
        'data': [[str]],        # List of data rows (each row is list of strings)
        'num_frames': str,      # Number of frames
        'camera_rate': str,     # Camera frame rate
    }
    """
    with open(str(trc_path), 'r') as f:
        lines = f.readlines()

    if len(lines) < 5:
        print(f"  ⚠ Invalid TRC format: {trc_path}")
        return None

    header_0 = lines[0].rstrip('\n')
    header_1 = lines[1].rstrip('\n')
    header_2 = lines[2].rstrip('\n')
    header_3 = lines[3].rstrip('\n')

    # Parse header 1 to get metadata
    header_1_parts = header_1.split('\t')
    camera_rate = header_1_parts[1] if len(header_1_parts) > 1 else "120"
    num_frames = header_1_parts[2] if len(header_1_parts) > 2 else "0"

    # Parse header 2 to get marker names
    header_2_parts = header_2.split('\t')
    markers = []
    i = 2
    while i < len(header_2_parts):
        marker_name = header_2_parts[i].strip()
        if marker_name and marker_name not in ['X', 'Y', 'Z']:
            markers.append(marker_name)
            i += 3  # Skip X, Y, Z
        else:
            i += 1

    # Parse data rows
    data = []
    for row_idx in range(4, len(lines)):
        row_str = lines[row_idx].rstrip('\n')
        if row_str.strip():
            data.append(row_str.split('\t'))

    return {
        'header_0': header_0,
        'header_1': header_1,
        'header_2': header_2,
        'header_3': header_3,
        'markers': markers,
        'data': data,
        'num_frames': num_frames,
        'camera_rate': camera_rate,
    }


def extract_all_markers(trc_files):
    """
    Scan all TRC files and extract all unique marker names.

    Returns: sorted list of all unique markers
    """
    all_markers = set()

    for trc_file in trc_files:
        trc_data = parse_trc_file(trc_file)
        if trc_data:
            all_markers.update(trc_data['markers'])

    return sorted(all_markers)


def rebuild_trc_file(trc_path, all_markers_sorted):
    """
    Rebuild a TRC file to include all markers.

    Adds missing markers with zero coordinates.
    """
    trc_data = parse_trc_file(trc_path)
    if not trc_data:
        return False

    existing_markers = set(trc_data['markers'])
    missing_markers = set(all_markers_sorted) - existing_markers

    if not missing_markers:
        print(f"  ✓ All markers present: {trc_path.name}")
        return True

    print(f"  + Adding {len(missing_markers)} missing markers to {trc_path.name}")

    # Add missing marker columns to data rows
    for _ in missing_markers:
        for row in trc_data['data']:
            row.extend(['0.000000', '0.000000', '0.000000'])

    # Rebuild header 2 (marker names)
    header_2_parts = ['Frame#', 'Time']
    for marker in all_markers_sorted:
        header_2_parts.extend([marker, 'X', 'Y', 'Z'])
    header_2_new = '\t'.join(header_2_parts)

    # Rebuild header 3 (coordinate labels)
    header_3_parts = [' (Frames)', ' ']
    for _ in all_markers_sorted:
        header_3_parts.extend(['X', 'Y', 'Z'])
    header_3_new = '\t'.join(header_3_parts)

    # Rebuild header 1 (metadata with updated NumMarkers)
    num_markers_total = len(all_markers_sorted)
    header_1_new = f"DataRate\t{trc_data['camera_rate']}\t{trc_data['num_frames']}\t{num_markers_total}\tUnitless"

    # Write rebuilt TRC file
    try:
        with open(str(trc_path), 'w') as f:
            f.write(trc_data['header_0'] + '\n')
            f.write(header_1_new + '\n')
            f.write(header_2_new + '\n')
            f.write(header_3_new + '\n')
            for row in trc_data['data']:
                f.write('\t'.join(row) + '\n')

        return True
    except Exception as e:
        print(f"  ✗ Error writing {trc_path.name}: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python post_process_trc_markers.py <output_folder>")
        print("\nExample:")
        print('  python post_process_trc_markers.py "C:\\path\\to\\exported\\trials"')
        sys.exit(1)

    output_folder = Path(sys.argv[1])

    if not output_folder.exists():
        print(f"✗ Folder not found: {output_folder}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"TRC Marker Post-Processing")
    print(f"{'='*80}")
    print(f"Scanning: {output_folder}\n")

    # Find all TRC files
    trc_files = find_trc_files(output_folder)

    if not trc_files:
        print("✗ No marker_experimental.trc files found!")
        sys.exit(1)

    print(f"Found {len(trc_files)} TRC files\n")

    # Extract all unique markers
    print("Scanning for all unique markers across trials...")
    all_markers = extract_all_markers(trc_files)
    print(f"✓ Found {len(all_markers)} unique markers:")
    print(f"  {', '.join(all_markers)}\n")

    # Rebuild each TRC file
    print(f"Rebuilding TRC files with complete marker set...\n")
    success_count = 0

    for trc_file in trc_files:
        if rebuild_trc_file(trc_file, all_markers):
            success_count += 1

    print(f"\n{'='*80}")
    print(f"✓ Completed: {success_count}/{len(trc_files)} files processed successfully")
    print(f"{'='*80}\n")

    if success_count == len(trc_files):
        print("✓ All TRC files now have consistent marker columns!")
        return 0
    else:
        print(f"⚠ {len(trc_files) - success_count} file(s) had errors")
        return 1


if __name__ == '__main__':
    sys.exit(main())
