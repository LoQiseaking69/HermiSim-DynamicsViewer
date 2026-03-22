import pytest
import os
from unittest.mock import Mock, patch
from gui.file_loader import FileLoader
from physics_engine.simulation import Simulation

@pytest.fixture
def mock_simulation():
    return Mock(spec=Simulation)

@pytest.fixture
def file_loader(mock_simulation):
    return FileLoader(mock_simulation)

def test_load_urdf_file_success(file_loader, mock_simulation, tmp_path):
    urdf_content = "<robot name=\"test_robot\"></robot>"
    urdf_file = tmp_path / "test.urdf"
    urdf_file.write_text(urdf_content)

    file_loader.load_file(str(urdf_file))
    mock_simulation.load_robot.assert_called_once_with(str(urdf_file))

def test_load_xml_file_success(file_loader, mock_simulation, tmp_path):
    xml_content = "<root><robot urdf=\"robot.urdf\"/></root>"
    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content)

    robot_urdf_file = tmp_path / "robot.urdf"
    robot_urdf_file.write_text("<robot name=\"sub_robot\"></robot>")

    file_loader.load_file(str(xml_file))
    # The file_loader constructs the full path, so we need to assert with that
    expected_urdf_path = str(tmp_path / "robot.urdf")
    mock_simulation.load_robot.assert_called_once_with(expected_urdf_path)

def test_load_non_existent_file(file_loader):
    with pytest.raises(FileNotFoundError):
        file_loader.load_file("non_existent_file.urdf")

def test_load_unsupported_file_type(file_loader, tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("plain text")
    with pytest.raises(ValueError, match="Unsupported file type"):
        file_loader.load_file(str(txt_file))

def test_parse_xml_invalid_format(file_loader, tmp_path):
    invalid_xml_content = "<root><robot></root>"
    invalid_xml_file = tmp_path / "invalid.xml"
    invalid_xml_file.write_text(invalid_xml_content)

    with pytest.raises(RuntimeError, match="Failed to load file"):
        file_loader.load_file(str(invalid_xml_file))

def test_load_multiple_files(file_loader, mock_simulation, tmp_path):
    urdf_content = "<robot name=\"test_robot\"></robot>"
    urdf_file1 = tmp_path / "test1.urdf"
    urdf_file1.write_text(urdf_content)

    urdf_file2 = tmp_path / "test2.urdf"
    urdf_file2.write_text(urdf_content)

    file_loader.load_multiple_files([str(urdf_file1), str(urdf_file2)])
    assert mock_simulation.load_robot.call_count == 2
    mock_simulation.load_robot.assert_any_call(str(urdf_file1))
    mock_simulation.load_robot.assert_any_call(str(urdf_file2))
