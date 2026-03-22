"""Step-by-step MJCF model builder with live XML preview."""

from __future__ import annotations

import copy
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)


# ── Minimal XML syntax highlighter ────────────────────────────────────

class _XmlHighlighter(QSyntaxHighlighter):
    """Very lightweight XML highlighter for the preview pane."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tag_fmt = QTextCharFormat()
        self._tag_fmt.setForeground(QColor("#7c3aed"))
        self._tag_fmt.setFontWeight(QFont.Bold)

        self._attr_fmt = QTextCharFormat()
        self._attr_fmt.setForeground(QColor("#3fb950"))

        self._val_fmt = QTextCharFormat()
        self._val_fmt.setForeground(QColor("#d29922"))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#8b949e"))
        self._comment_fmt.setFontItalic(True)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        import re
        for m in re.finditer(r"</?[\w:-]+", text):
            self.setFormat(m.start(), m.end() - m.start(), self._tag_fmt)
        for m in re.finditer(r'\b(\w+)=', text):
            self.setFormat(m.start(1), m.end(1) - m.start(1), self._attr_fmt)
        for m in re.finditer(r'"[^"]*"', text):
            self.setFormat(m.start(), m.end() - m.start(), self._val_fmt)
        for m in re.finditer(r"<!--.*?-->", text):
            self.setFormat(m.start(), m.end() - m.start(), self._comment_fmt)


# ── Data model for a MuJoCo model ────────────────────────────────────

class _ModelSpec:
    """In-memory representation of the model being built."""

    def __init__(self) -> None:
        self.model_name: str = "my_model"
        self.timestep: float = 0.002
        self.gravity: List[float] = [0.0, 0.0, -9.81]
        self.integrator: str = "Euler"
        self.ground_plane: bool = True
        self.ground_rgba: List[float] = [0.3, 0.3, 0.3, 1.0]
        self.bodies: List[Dict[str, Any]] = []
        self.joints: List[Dict[str, Any]] = []
        self.actuators: List[Dict[str, Any]] = []
        self.sensors: List[Dict[str, Any]] = []
        self.cameras: List[Dict[str, Any]] = []

    # ── XML generation ────────────────────────────────────────────

    def to_xml(self) -> str:
        """Generate a valid MJCF XML string."""
        root = ET.Element("mujoco", model=self.model_name)

        # option
        opt = ET.SubElement(root, "option")
        opt.set("timestep", str(self.timestep))
        opt.set("gravity", " ".join(f"{v}" for v in self.gravity))
        opt.set("integrator", self.integrator)

        # visual
        visual = ET.SubElement(root, "visual")
        headlight = ET.SubElement(visual, "headlight")
        headlight.set("ambient", "0.4 0.4 0.4")

        # asset
        asset = ET.SubElement(root, "asset")
        ET.SubElement(
            asset, "texture",
            type="skybox", builtin="gradient",
            rgb1="0.1 0.12 0.18", rgb2="0.02 0.02 0.04",
            width="512", height="512",
        )
        ET.SubElement(
            asset, "texture",
            name="grid", type="2d", builtin="checker",
            rgb1="0.25 0.25 0.28", rgb2="0.20 0.20 0.22",
            width="256", height="256",
        )
        ET.SubElement(
            asset, "material",
            name="grid_mat", texture="grid",
            texrepeat="8 8", reflectance="0.1",
        )

        # worldbody
        worldbody = ET.SubElement(root, "worldbody")
        ET.SubElement(worldbody, "light", diffuse="0.8 0.8 0.8",
                      pos="0 0 4", dir="0 0 -1")

        if self.ground_plane:
            rgba_str = " ".join(f"{v}" for v in self.ground_rgba)
            ET.SubElement(
                worldbody, "geom",
                name="ground", type="plane",
                size="5 5 0.1", rgba=rgba_str,
                material="grid_mat",
            )

        # cameras
        for cam in self.cameras:
            attrs = {"name": cam["name"], "pos": cam["pos"]}
            if cam.get("target"):
                attrs["target"] = cam["target"]
            ET.SubElement(worldbody, "camera", **attrs)

        # bodies
        body_map: Dict[str, ET.Element] = {}
        for body in self.bodies:
            parent_elem = body_map.get(body.get("parent", ""), worldbody)
            belem = ET.SubElement(parent_elem, "body",
                                  name=body["name"],
                                  pos=body["pos"])
            if body.get("euler"):
                belem.set("euler", body["euler"])

            # inertial (auto-compute if mass provided)
            if body.get("mass"):
                inertial = ET.SubElement(belem, "inertial",
                                         mass=str(body["mass"]),
                                         pos="0 0 0")
                inertial.set("diaginertia", body.get(
                    "diaginertia", "0.001 0.001 0.001"))

            # geom
            geom_attrs: Dict[str, str] = {
                "name": f"{body['name']}_geom",
                "type": body.get("geom_type", "box"),
                "size": body.get("geom_size", "0.05 0.05 0.05"),
            }
            if body.get("geom_rgba"):
                geom_attrs["rgba"] = body["geom_rgba"]
            ET.SubElement(belem, "geom", **geom_attrs)
            body_map[body["name"]] = belem

        # joints (attach to their parent body element)
        for joint in self.joints:
            parent_elem = body_map.get(joint.get("body", ""))
            if parent_elem is None:
                continue
            jattrs: Dict[str, str] = {
                "name": joint["name"],
                "type": joint.get("type", "hinge"),
            }
            if joint.get("axis"):
                jattrs["axis"] = joint["axis"]
            if joint.get("range"):
                jattrs["range"] = joint["range"]
            if joint.get("damping"):
                jattrs["damping"] = str(joint["damping"])
            ET.SubElement(parent_elem, "joint", **jattrs)

        # actuator
        if self.actuators:
            actuator_elem = ET.SubElement(root, "actuator")
            for act in self.actuators:
                act_type = act.get("type", "motor")
                aattrs: Dict[str, str] = {
                    "name": act["name"],
                    "joint": act.get("joint", ""),
                }
                if act.get("ctrlrange"):
                    aattrs["ctrlrange"] = act["ctrlrange"]
                if act.get("gear"):
                    aattrs["gear"] = str(act["gear"])
                ET.SubElement(actuator_elem, act_type, **aattrs)

        # sensor
        if self.sensors:
            sensor_elem = ET.SubElement(root, "sensor")
            for sens in self.sensors:
                sattrs: Dict[str, str] = {"name": sens["name"]}
                stype = sens.get("type", "jointpos")
                if stype in ("jointpos", "jointvel", "actuatorfrc"):
                    sattrs["joint"] = sens.get("joint", "")
                elif stype in ("framepos", "framequat", "framelinvel"):
                    sattrs["objtype"] = "body"
                    sattrs["objname"] = sens.get("body", "")
                elif stype == "accelerometer":
                    sattrs["site"] = sens.get("site", "")
                ET.SubElement(sensor_elem, stype, **sattrs)

        return _pretty_xml(root)


def _pretty_xml(element: ET.Element, indent: str = "  ") -> str:
    """Produce indented XML string from an ElementTree element."""
    ET.indent(element, space=indent)
    return ET.tostring(element, encoding="unicode", xml_declaration=True)


# ── Step pages ────────────────────────────────────────────────────────

class _WorldPage(QWidget):
    """Step 1 — world / option configuration."""

    def __init__(self, spec: _ModelSpec) -> None:
        super().__init__()
        self._spec = spec
        layout = QVBoxLayout(self)

        grp = QGroupBox("World Properties")
        form = QFormLayout()

        self._name_edit = QLineEdit(spec.model_name)
        form.addRow("Model name:", self._name_edit)

        self._ts_spin = QDoubleSpinBox()
        self._ts_spin.setRange(0.0001, 0.1)
        self._ts_spin.setDecimals(4)
        self._ts_spin.setSingleStep(0.001)
        self._ts_spin.setValue(spec.timestep)
        form.addRow("Timestep (s):", self._ts_spin)

        self._grav = QLineEdit(" ".join(str(v) for v in spec.gravity))
        self._grav.setPlaceholderText("x y z")
        form.addRow("Gravity:", self._grav)

        self._integrator = QComboBox()
        self._integrator.addItems(["Euler", "RK4", "implicit", "implicitfast"])
        form.addRow("Integrator:", self._integrator)

        self._ground = QCheckBox("Include ground plane")
        self._ground.setChecked(spec.ground_plane)
        form.addRow(self._ground)

        grp.setLayout(form)
        layout.addWidget(grp)
        layout.addStretch()

    def apply(self) -> None:
        self._spec.model_name = self._name_edit.text().strip() or "my_model"
        self._spec.timestep = self._ts_spin.value()
        parts = self._grav.text().split()
        if len(parts) == 3:
            self._spec.gravity = [float(p) for p in parts]
        self._spec.integrator = self._integrator.currentText()
        self._spec.ground_plane = self._ground.isChecked()


class _BodiesPage(QWidget):
    """Step 2 — add / remove rigid bodies."""

    def __init__(self, spec: _ModelSpec) -> None:
        super().__init__()
        self._spec = spec
        layout = QVBoxLayout(self)

        top = QHBoxLayout()

        # body list
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._select)
        top.addWidget(self._list, 1)

        # form
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name_edit = QLineEdit()
        form.addRow("Name:", self._name_edit)

        self._pos_edit = QLineEdit("0 0 0.5")
        self._pos_edit.setPlaceholderText("x y z")
        form.addRow("Position:", self._pos_edit)

        self._euler_edit = QLineEdit()
        self._euler_edit.setPlaceholderText("rx ry rz (degrees)")
        form.addRow("Euler angles:", self._euler_edit)

        self._mass_spin = QDoubleSpinBox()
        self._mass_spin.setRange(0.0, 10000.0)
        self._mass_spin.setDecimals(3)
        self._mass_spin.setValue(1.0)
        form.addRow("Mass (kg):", self._mass_spin)

        self._parent_combo = QComboBox()
        self._parent_combo.addItem("(world)")
        form.addRow("Parent body:", self._parent_combo)

        self._geom_type = QComboBox()
        self._geom_type.addItems([
            "box", "sphere", "capsule", "cylinder", "ellipsoid", "mesh",
        ])
        form.addRow("Geom type:", self._geom_type)

        self._geom_size = QLineEdit("0.05 0.05 0.05")
        self._geom_size.setPlaceholderText("size params")
        form.addRow("Geom size:", self._geom_size)

        self._geom_rgba = QLineEdit("0.4 0.6 0.9 1")
        self._geom_rgba.setPlaceholderText("r g b a")
        form.addRow("Geom RGBA:", self._geom_rgba)

        top.addWidget(form_widget, 2)
        layout.addLayout(top)

        # buttons
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Body")
        self._add_btn.clicked.connect(self._add_body)
        self._rm_btn = QPushButton("Remove Selected")
        self._rm_btn.clicked.connect(self._remove_body)
        self._update_btn = QPushButton("Update Selected")
        self._update_btn.clicked.connect(self._update_body)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._update_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh_list(self) -> None:
        self._list.clear()
        self._parent_combo.clear()
        self._parent_combo.addItem("(world)")
        for b in self._spec.bodies:
            self._list.addItem(b["name"])
            self._parent_combo.addItem(b["name"])

    def _select(self, row: int) -> None:
        if row < 0 or row >= len(self._spec.bodies):
            return
        b = self._spec.bodies[row]
        self._name_edit.setText(b["name"])
        self._pos_edit.setText(b["pos"])
        self._euler_edit.setText(b.get("euler", ""))
        self._mass_spin.setValue(b.get("mass", 1.0))
        idx = self._geom_type.findText(b.get("geom_type", "box"))
        if idx >= 0:
            self._geom_type.setCurrentIndex(idx)
        self._geom_size.setText(b.get("geom_size", "0.05 0.05 0.05"))
        self._geom_rgba.setText(b.get("geom_rgba", "0.4 0.6 0.9 1"))
        pidx = self._parent_combo.findText(b.get("parent", "(world)"))
        if pidx >= 0:
            self._parent_combo.setCurrentIndex(pidx)

    def _collect(self) -> Dict[str, Any]:
        name = self._name_edit.text().strip()
        if not name:
            raise ValueError("Body name is required")
        parent = self._parent_combo.currentText()
        d: Dict[str, Any] = {
            "name": name,
            "pos": self._pos_edit.text().strip() or "0 0 0",
            "mass": self._mass_spin.value(),
            "geom_type": self._geom_type.currentText(),
            "geom_size": self._geom_size.text().strip() or "0.05 0.05 0.05",
            "geom_rgba": self._geom_rgba.text().strip(),
        }
        if parent and parent != "(world)":
            d["parent"] = parent
        euler = self._euler_edit.text().strip()
        if euler:
            d["euler"] = euler
        return d

    def _add_body(self) -> None:
        try:
            body = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        # unique check
        if any(b["name"] == body["name"] for b in self._spec.bodies):
            QMessageBox.warning(self, "Duplicate", f"Body '{body['name']}' already exists.")
            return
        self._spec.bodies.append(body)
        self._refresh_list()

    def _update_body(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        try:
            body = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        self._spec.bodies[row] = body
        self._refresh_list()

    def _remove_body(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        del self._spec.bodies[row]
        self._refresh_list()

    def apply(self) -> None:
        pass  # bodies are persisted immediately

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh_list()


class _JointsPage(QWidget):
    """Step 3 — configure joints."""

    def __init__(self, spec: _ModelSpec) -> None:
        super().__init__()
        self._spec = spec
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._select)
        top.addWidget(self._list, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name_edit = QLineEdit()
        form.addRow("Name:", self._name_edit)

        self._body_combo = QComboBox()
        form.addRow("Body:", self._body_combo)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["hinge", "slide", "ball", "free"])
        form.addRow("Type:", self._type_combo)

        self._axis_edit = QLineEdit("0 0 1")
        self._axis_edit.setPlaceholderText("x y z")
        form.addRow("Axis:", self._axis_edit)

        self._range_edit = QLineEdit()
        self._range_edit.setPlaceholderText("-90 90 (optional)")
        form.addRow("Range (deg):", self._range_edit)

        self._damping_spin = QDoubleSpinBox()
        self._damping_spin.setRange(0.0, 1000.0)
        self._damping_spin.setDecimals(3)
        self._damping_spin.setValue(0.1)
        form.addRow("Damping:", self._damping_spin)

        top.addWidget(form_widget, 2)
        layout.addLayout(top)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Joint")
        add_btn.clicked.connect(self._add)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(self._remove)
        update_btn = QPushButton("Update Selected")
        update_btn.clicked.connect(self._update)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(update_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        self._list.clear()
        self._body_combo.clear()
        for b in self._spec.bodies:
            self._body_combo.addItem(b["name"])
        for j in self._spec.joints:
            self._list.addItem(f"{j['name']}  [{j.get('type','hinge')}]  → {j.get('body','')}")

    def _select(self, row: int) -> None:
        if row < 0 or row >= len(self._spec.joints):
            return
        j = self._spec.joints[row]
        self._name_edit.setText(j["name"])
        idx = self._body_combo.findText(j.get("body", ""))
        if idx >= 0:
            self._body_combo.setCurrentIndex(idx)
        tidx = self._type_combo.findText(j.get("type", "hinge"))
        if tidx >= 0:
            self._type_combo.setCurrentIndex(tidx)
        self._axis_edit.setText(j.get("axis", "0 0 1"))
        self._range_edit.setText(j.get("range", ""))
        self._damping_spin.setValue(j.get("damping", 0.1))

    def _collect(self) -> Dict[str, Any]:
        name = self._name_edit.text().strip()
        if not name:
            raise ValueError("Joint name is required")
        d: Dict[str, Any] = {
            "name": name,
            "body": self._body_combo.currentText(),
            "type": self._type_combo.currentText(),
            "axis": self._axis_edit.text().strip() or "0 0 1",
            "damping": self._damping_spin.value(),
        }
        rng = self._range_edit.text().strip()
        if rng:
            d["range"] = rng
        return d

    def _add(self) -> None:
        try:
            j = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        if any(x["name"] == j["name"] for x in self._spec.joints):
            QMessageBox.warning(self, "Duplicate", f"Joint '{j['name']}' already exists.")
            return
        self._spec.joints.append(j)
        self._refresh()

    def _update(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        try:
            j = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        self._spec.joints[row] = j
        self._refresh()

    def _remove(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        del self._spec.joints[row]
        self._refresh()

    def apply(self) -> None:
        pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()


class _ActuatorsPage(QWidget):
    """Step 4 — add actuators."""

    def __init__(self, spec: _ModelSpec) -> None:
        super().__init__()
        self._spec = spec
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._select)
        top.addWidget(self._list, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name_edit = QLineEdit()
        form.addRow("Name:", self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["motor", "position", "velocity", "general"])
        form.addRow("Type:", self._type_combo)

        self._joint_combo = QComboBox()
        form.addRow("Joint:", self._joint_combo)

        self._ctrlrange = QLineEdit("-1 1")
        self._ctrlrange.setPlaceholderText("min max")
        form.addRow("Control range:", self._ctrlrange)

        self._gear_spin = QDoubleSpinBox()
        self._gear_spin.setRange(0.0, 10000.0)
        self._gear_spin.setDecimals(2)
        self._gear_spin.setValue(1.0)
        form.addRow("Gear:", self._gear_spin)

        top.addWidget(form_widget, 2)
        layout.addLayout(top)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Actuator")
        add_btn.clicked.connect(self._add)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(self._remove)
        update_btn = QPushButton("Update Selected")
        update_btn.clicked.connect(self._update)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(update_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        self._list.clear()
        self._joint_combo.clear()
        for j in self._spec.joints:
            self._joint_combo.addItem(j["name"])
        for a in self._spec.actuators:
            self._list.addItem(f"{a['name']}  [{a.get('type','motor')}]  → {a.get('joint','')}")

    def _select(self, row: int) -> None:
        if row < 0 or row >= len(self._spec.actuators):
            return
        a = self._spec.actuators[row]
        self._name_edit.setText(a["name"])
        tidx = self._type_combo.findText(a.get("type", "motor"))
        if tidx >= 0:
            self._type_combo.setCurrentIndex(tidx)
        jidx = self._joint_combo.findText(a.get("joint", ""))
        if jidx >= 0:
            self._joint_combo.setCurrentIndex(jidx)
        self._ctrlrange.setText(a.get("ctrlrange", "-1 1"))
        self._gear_spin.setValue(a.get("gear", 1.0))

    def _collect(self) -> Dict[str, Any]:
        name = self._name_edit.text().strip()
        if not name:
            raise ValueError("Actuator name is required")
        return {
            "name": name,
            "type": self._type_combo.currentText(),
            "joint": self._joint_combo.currentText(),
            "ctrlrange": self._ctrlrange.text().strip() or "-1 1",
            "gear": self._gear_spin.value(),
        }

    def _add(self) -> None:
        try:
            a = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        if any(x["name"] == a["name"] for x in self._spec.actuators):
            QMessageBox.warning(self, "Duplicate", f"Actuator '{a['name']}' already exists.")
            return
        self._spec.actuators.append(a)
        self._refresh()

    def _update(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        try:
            a = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        self._spec.actuators[row] = a
        self._refresh()

    def _remove(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        del self._spec.actuators[row]
        self._refresh()

    def apply(self) -> None:
        pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()


class _SensorsPage(QWidget):
    """Step 5 — add sensors."""

    def __init__(self, spec: _ModelSpec) -> None:
        super().__init__()
        self._spec = spec
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._select)
        top.addWidget(self._list, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name_edit = QLineEdit()
        form.addRow("Name:", self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems([
            "jointpos", "jointvel", "actuatorfrc",
            "framepos", "framequat", "framelinvel",
            "accelerometer", "gyro", "touch",
        ])
        form.addRow("Type:", self._type_combo)

        self._target_combo = QComboBox()
        form.addRow("Target (joint/body):", self._target_combo)

        top.addWidget(form_widget, 2)
        layout.addLayout(top)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Sensor")
        add_btn.clicked.connect(self._add)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(self._remove)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        self._list.clear()
        self._target_combo.clear()
        for j in self._spec.joints:
            self._target_combo.addItem(f"joint:{j['name']}")
        for b in self._spec.bodies:
            self._target_combo.addItem(f"body:{b['name']}")
        for s in self._spec.sensors:
            self._list.addItem(f"{s['name']}  [{s.get('type','jointpos')}]")

    def _select(self, row: int) -> None:
        if row < 0 or row >= len(self._spec.sensors):
            return
        s = self._spec.sensors[row]
        self._name_edit.setText(s["name"])
        tidx = self._type_combo.findText(s.get("type", "jointpos"))
        if tidx >= 0:
            self._type_combo.setCurrentIndex(tidx)

    def _collect(self) -> Dict[str, Any]:
        name = self._name_edit.text().strip()
        if not name:
            raise ValueError("Sensor name is required")
        target = self._target_combo.currentText()
        d: Dict[str, Any] = {
            "name": name,
            "type": self._type_combo.currentText(),
        }
        if ":" in target:
            kind, tname = target.split(":", 1)
            if kind == "joint":
                d["joint"] = tname
            elif kind == "body":
                d["body"] = tname
        return d

    def _add(self) -> None:
        try:
            s = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
            return
        if any(x["name"] == s["name"] for x in self._spec.sensors):
            QMessageBox.warning(self, "Duplicate", f"Sensor '{s['name']}' already exists.")
            return
        self._spec.sensors.append(s)
        self._refresh()

    def _remove(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        del self._spec.sensors[row]
        self._refresh()

    def apply(self) -> None:
        pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()


class _PreviewPage(QWidget):
    """Step 6 — XML preview + load into simulation."""

    def __init__(self, spec: _ModelSpec, simulation: Simulation) -> None:
        super().__init__()
        self._spec = spec
        self._simulation = simulation

        layout = QVBoxLayout(self)

        lbl = QLabel("Generated MJCF XML")
        lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl)

        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setReadOnly(False)
        self._highlighter = _XmlHighlighter(self._editor.document())
        layout.addWidget(self._editor)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Regenerate XML")
        refresh_btn.clicked.connect(self.refresh)
        load_btn = QPushButton("Load into Simulation")
        load_btn.setStyleSheet(
            "QPushButton { background-color: #7c3aed; border-color: #7c3aed; }"
            "QPushButton:hover { background-color: #8b5cf6; }"
        )
        load_btn.clicked.connect(self._load)
        save_btn = QPushButton("Save as File\u2026")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self) -> None:
        try:
            xml = self._spec.to_xml()
            self._editor.setPlainText(xml)
        except Exception as exc:
            self._editor.setPlainText(f"<!-- Error generating XML: {exc} -->")

    def _load(self) -> None:
        xml = self._editor.toPlainText()
        if not xml.strip():
            QMessageBox.warning(self, "Empty", "No XML to load.")
            return
        try:
            self._simulation.engine.load_model_from_xml(xml)
            self._simulation.model_loaded.emit()
            QMessageBox.information(self, "Success", "Model loaded into simulation.")
            logger.info("Model builder: loaded custom model into simulation")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _save(self) -> None:
        xml = self._editor.toPlainText()
        if not xml.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MJCF Model", "model.xml",
            "MJCF Files (*.xml *.mjcf);;All Files (*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            QMessageBox.information(self, "Saved", f"Model saved to {path}")
        except OSError as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def apply(self) -> None:
        pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()


# ── Main tab widget ───────────────────────────────────────────────────

_STEPS = [
    ("World",      "Define simulation world properties"),
    ("Bodies",     "Add rigid bodies and geometry"),
    ("Joints",     "Attach joints to bodies"),
    ("Actuators",  "Add motors and actuators"),
    ("Sensors",    "Configure sensor readings"),
    ("Preview",    "Review and load the model"),
]


class ModelBuilderTab(QWidget):
    """Wizard-style model creation with step sidebar and live preview."""

    def __init__(self, simulation: Simulation, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._spec = _ModelSpec()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Sidebar ───────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QWidget { background-color: #0d1117; }
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(8, 12, 8, 12)

        title = QLabel("Model Builder")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #a78bfa; margin-bottom: 6px;")
        sb_layout.addWidget(title)

        self._step_list = QListWidget()
        self._step_list.setSpacing(2)
        for i, (name, desc) in enumerate(_STEPS):
            item = QListWidgetItem(f"  {i + 1}.  {name}")
            item.setToolTip(desc)
            self._step_list.addItem(item)
        self._step_list.setCurrentRow(0)
        self._step_list.currentRowChanged.connect(self._go_to_step)
        sb_layout.addWidget(self._step_list)

        # nav buttons
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("\u25c0  Back")
        self._prev_btn.clicked.connect(self._prev_step)
        self._next_btn = QPushButton("Next  \u25b6")
        self._next_btn.clicked.connect(self._next_step)
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._next_btn)
        sb_layout.addLayout(nav)

        # reset
        reset_btn = QPushButton("Reset All")
        reset_btn.setStyleSheet(
            "QPushButton { color: #f85149; border-color: #f85149; }"
            "QPushButton:hover { background-color: #f8514922; }"
        )
        reset_btn.clicked.connect(self._reset)
        sb_layout.addWidget(reset_btn)

        layout.addWidget(sidebar)

        # ── Stacked pages ─────────────────────────────────────────
        self._stack = QStackedWidget()
        self._pages = [
            _WorldPage(self._spec),
            _BodiesPage(self._spec),
            _JointsPage(self._spec),
            _ActuatorsPage(self._spec),
            _SensorsPage(self._spec),
            _PreviewPage(self._spec, self._simulation),
        ]
        for page in self._pages:
            self._stack.addWidget(page)

        layout.addWidget(self._stack, 1)
        self._update_nav()

    # ── Navigation ────────────────────────────────────────────────

    def _go_to_step(self, index: int) -> None:
        # apply current page before leaving
        current = self._stack.currentWidget()
        if hasattr(current, "apply"):
            current.apply()
        self._stack.setCurrentIndex(index)
        self._step_list.setCurrentRow(index)
        self._update_nav()

    def _next_step(self) -> None:
        idx = self._stack.currentIndex()
        if idx < len(self._pages) - 1:
            self._go_to_step(idx + 1)

    def _prev_step(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._go_to_step(idx - 1)

    def _update_nav(self) -> None:
        idx = self._stack.currentIndex()
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < len(self._pages) - 1)

    def _reset(self) -> None:
        reply = QMessageBox.question(
            self, "Reset Model",
            "Clear all model data and start over?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._spec.__init__()  # type: ignore[misc]
            self._go_to_step(0)
