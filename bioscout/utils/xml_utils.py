"""
XML Utilities - Pretty printing and formatting XML files.
Version: 1.0.0
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from utils.logger import logger


def indent(elem, level=0):
    """
    Add indentation to XML element tree for pretty printing.

    Args:
        elem: ElementTree element
        level: Current indentation level
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def save_pretty_xml(xml_tree, file_path, encoding='utf-8', xml_declaration=True):
    """
    Save XML ElementTree to file with proper formatting (indentation and newlines).

    Args:
        xml_tree: ElementTree.ElementTree object or Element
        file_path: Path to save XML file (str or Path)
        encoding: Encoding for XML file (default: utf-8)
        xml_declaration: Whether to include XML declaration (default: True)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        file_path = Path(file_path)

        # Handle both ElementTree and Element inputs
        if isinstance(xml_tree, ET.ElementTree):
            root = xml_tree.getroot()
        else:
            root = xml_tree

        # Apply indentation
        indent(root)

        # Create new ElementTree with root
        tree = ET.ElementTree(root)

        # Write to file
        tree.write(str(file_path), encoding=encoding, xml_declaration=xml_declaration)

        logger.info(f"Saved formatted XML to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Error saving pretty XML to {file_path}: {e}")
        return False
