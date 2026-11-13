"""State-machine diagrams: runs `tulpa graph` and lays the Mermaid output out natively."""

from __future__ import annotations

import re
from collections import defaultdict

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QGraphicsScene, QGraphicsView, QLabel, QPlainTextEdit, QTabWidget,
                               QVBoxLayout, QWidget)

from gui.ide import theme

EDGE = re.compile(r"^\s*(\[\*\]|\w+)\s*-->\s*(\w+)\s*(?::\s*(.*))?$")


def parse_mermaid(text: str) -> list[dict]:
    """Split `tulpa graph` output into machines: {name, edges: [(a, b, label)]}."""
    machines, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^%%\s*machine\s+(\w+)", s) or re.match(r"^#+\s*(\w+)", s) or re.match(r"^---\s*(\w+)", s)
        if m and not s.startswith("stateDiagram"):
            cur = {"name": m.group(1), "edges": []}
            machines.append(cur)
            continue
        if s.startswith("stateDiagram"):
            if cur is None or cur["edges"]:
                cur = {"name": f"machine {len(machines) + 1}", "edges": []}
                machines.append(cur)
            continue
        e = EDGE.match(s)
        if e and cur is not None:
            cur["edges"].append((e.group(1), e.group(2), (e.group(3) or "").strip()))
    return [m for m in machines if m["edges"]]


class MachineGraph(QGraphicsView):
    def __init__(self, edges, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(theme.BG1))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        sc = QGraphicsScene(self)
        self.setScene(sc)
        # merge parallel transitions (same source and target) into one labelled edge
        merged: dict = {}
        for a, b, label in edges:
            merged.setdefault((a, b), []).append(label)
        edges = [(a, b, "  |  ".join(x for x in ls if x)) for (a, b), ls in merged.items()]
        # layered layout: BFS depth from the initial state
        start = next((b for a, b, _ in edges if a == "[*]"), edges[0][0])
        adj = defaultdict(list)
        nodes = []
        for a, b, _ in edges:
            for n in (a, b):
                if n != "[*]" and n not in nodes:
                    nodes.append(n)
            if a != "[*]":
                adj[a].append(b)
        depth = {start: 0}
        q = [start]
        while q:
            n = q.pop(0)
            for m in adj[n]:
                if m not in depth:
                    depth[m] = depth[n] + 1
                    q.append(m)
        for n in nodes:
            depth.setdefault(n, max(depth.values()) + 1)
        layers = defaultdict(list)
        for n in nodes:
            layers[depth[n]].append(n)
        pos = {}
        W, H, DX, DY = 150, 46, 330, 170
        for d, ns in layers.items():
            for i, n in enumerate(ns):
                pos[n] = QPointF(d * DX, (i - (len(ns) - 1) / 2) * DY)
        font = QFont(theme.mono_font(10))
        # edges
        drawn = defaultdict(int)
        for a, b, label in edges:
            if a == "[*]":
                p0 = pos[b] + QPointF(-W / 2 - 50, 0)
                sc.addEllipse(p0.x() - 7, p0.y() - 7, 14, 14, QPen(Qt.NoPen), QBrush(QColor(theme.CYAN)))
                self._arrow(sc, p0 + QPointF(7, 0), pos[b] + QPointF(-W / 2, 0), "", theme.CYAN, font, 0)
                continue
            k = drawn[(a, b)]
            drawn[(a, b)] += 1
            if a == b:
                c = pos[a]
                path = QPainterPath(c + QPointF(-20, -H / 2))
                path.cubicTo(c + QPointF(-40, -H / 2 - 60 - 16 * k), c + QPointF(40, -H / 2 - 60 - 16 * k), c + QPointF(20, -H / 2))
                sc.addPath(path, QPen(QColor(theme.MUTED), 1.4))
                t = sc.addSimpleText(label, font)
                t.setBrush(QColor(theme.SYN["function"]))
                t.setPos(c + QPointF(-t.boundingRect().width() / 2, -H / 2 - 62 - 16 * k))
                continue
            self._arrow(sc, pos[a], pos[b], label, theme.MUTED, font, k, W, H)
        # nodes on top
        for n, p in pos.items():
            r = QRectF(p.x() - W / 2, p.y() - H / 2, W, H)
            path = QPainterPath()
            path.addRoundedRect(r, 12, 12)
            sc.addPath(path, QPen(QColor(theme.VIOLET if n == start else theme.CYAN_DIM), 2), QBrush(QColor(theme.BG2)))
            t = sc.addSimpleText(n, QFont(theme.mono_font(11)))
            t.setBrush(QColor(theme.TEXT))
            br = t.boundingRect()
            t.setPos(p.x() - br.width() / 2, p.y() - br.height() / 2)
        self.setSceneRect(sc.itemsBoundingRect().adjusted(-60, -60, 60, 60))

    def _arrow(self, sc, a, b, label, color, font, k, W=0, H=0):
        d = b - a
        L = max(1.0, (d.x() ** 2 + d.y() ** 2) ** 0.5)
        ux, uy = d.x() / L, d.y() / L
        # clip to box borders
        def clip(c, sx):
            if W == 0:
                return c
            tx = (W / 2) / abs(ux) if abs(ux) > 1e-6 else 1e9
            ty = (H / 2) / abs(uy) if abs(uy) > 1e-6 else 1e9
            t = min(tx, ty)
            return QPointF(c.x() + sx * ux * t, c.y() + sx * uy * t)
        p0, p1 = clip(a, 1), clip(b, -1)
        bend = (30 + 30 * k) if W else 0
        mid = (p0 + p1) / 2 + QPointF(-uy * bend, ux * bend)
        path = QPainterPath(p0)
        path.quadTo(mid, p1)
        sc.addPath(path, QPen(QColor(color), 1.4))
        tang = p1 - mid
        tl = max(1.0, (tang.x() ** 2 + tang.y() ** 2) ** 0.5)
        tx, ty = tang.x() / tl, tang.y() / tl
        head = QPolygonF([p1, p1 - QPointF(tx * 10 - ty * 5, ty * 10 + tx * 5), p1 - QPointF(tx * 10 + ty * 5, ty * 10 - tx * 5)])
        sc.addPolygon(head, QPen(Qt.NoPen), QBrush(QColor(color)))
        if label:
            on_curve = p0 * 0.25 + mid * 0.5 + p1 * 0.25
            t = sc.addSimpleText(label, font)
            t.setBrush(QColor(theme.SYN["function"]))
            br = t.boundingRect()
            bg = sc.addRect(QRectF(on_curve.x() - br.width() / 2 - 4, on_curve.y() - br.height() / 2 - 1, br.width() + 8, br.height() + 2),
                            QPen(QColor(theme.LINE2)), QBrush(QColor(theme.BG0)))
            bg.setZValue(1)
            t.setZValue(2)
            t.setPos(on_curve.x() - br.width() / 2, on_curve.y() - br.height() / 2)

    def wheelEvent(self, e) -> None:  # noqa: N802
        k = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(k, k)


class MachinesView(QWidget):
    def __init__(self, source_name: str, mermaid: str, parent=None) -> None:
        super().__init__(parent)
        self.source_name = source_name
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        machines = parse_mermaid(mermaid)
        for m in machines:
            tabs.addTab(MachineGraph(m["edges"]), m["name"])
        src = QPlainTextEdit(mermaid, readOnly=True)
        src.setFont(theme.mono_font(10))
        tabs.addTab(src, "Mermaid source")
        if not machines:
            lay.addWidget(QLabel("No state machines in this file."))
        lay.addWidget(tabs)

    @property
    def title(self) -> str:
        return "◇ " + self.source_name
