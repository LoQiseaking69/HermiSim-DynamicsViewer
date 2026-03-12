import xml.etree.ElementTree as ET
import os
import logging
import pybullet as p

class FileLoader:
    def __init__(self, simulation):
        self.simulation = simulation
        self.logger = logging.getLogger(__name__)
        self.supported_extensions = (".urdf", ".xml")

    def load_file(self, file_path):
        """Load a file into the simulation with validation."""
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.lower().endswith(self.supported_extensions):
            self.logger.error(f"Unsupported file type: {file_path}. Supported types are {', '.join(self.supported_extensions)}")
            raise ValueError(f"Unsupported file type: {file_path}")

        try:
            if file_path.lower().endswith(".urdf"):
                self.simulation.load_robot(file_path)
            elif file_path.lower().endswith(".xml"):
                self._parse_xml(file_path)
            self.logger.info(f"Successfully loaded file: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to load file {file_path}: {e}")
            raise RuntimeError(f"Failed to load file {file_path}: {e}")

    def _parse_xml(self, file_path):
        """Parse an XML file and load any referenced URDF files."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            for element in root.findall("robot"):
                urdf_path = element.get("urdf")
                if urdf_path:
                    # Construct the full path for the URDF file
                    xml_dir = os.path.dirname(file_path)
                    full_urdf_path = os.path.join(xml_dir, urdf_path)
                    self.simulation.load_robot(full_urdf_path)
            self.logger.info(f"Successfully parsed XML file: {file_path}")
        except ET.ParseError as e:
            self.logger.error(f"Error parsing XML file {file_path}: {e}")
            raise ValueError(f"Error parsing XML file {file_path}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing XML file {file_path}: {e}")
            raise

    def load_initial_data(self):
        """Load initial data for the simulation. Placeholder method."""
        initial_data = {
            'robot_urdf': 'r2d2.urdf'
        }
        self.logger.info("Loaded initial data")
        return initial_data

    def load_multiple_files(self, file_paths):
        """Load multiple files into the simulation."""
        for file_path in file_paths:
            self.load_file(file_path)
