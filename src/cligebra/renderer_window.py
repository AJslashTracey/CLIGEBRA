from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


LINE_CALL_RE = re.compile(
    r"line\s*\(\s*point\s*(\([^)]*\))\s*,\s*dir\s*(\([^)]*\)|\[[^]]*\]|vec\[[^]]*\])\s*\)",
    re.IGNORECASE,
)
LINE_LEGACY_RE = re.compile(
    r"point\s*(\([^)]*\))\s*dir\s*(\([^)]*\)|\[[^]]*\]|vec\[[^]]*\])",
    re.IGNORECASE,
)
CYLINDER_RE = re.compile(
    r"(?:zyl|cyl|cylinder)\s*\(\s*(\([^)]*\))\s*,\s*(\([^)]*\))\s*,\s*([^,()]+)\s*\)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class CameraState:
    yaw: float = math.radians(35)
    pitch: float = math.radians(25)
    scale: float = 42.0


def parse_triplet(expression: str, open_char: str, close_char: str) -> np.ndarray | None:
    stripped = expression.strip()
    if not (stripped.startswith(open_char) and stripped.endswith(close_char)):
        return None
    parts = [part.strip() for part in stripped[1:-1].split(",")]
    if len(parts) != 3:
        return None
    try:
        return np.array([float(part) for part in parts], dtype=float)
    except ValueError:
        return None


def parse_point(expression: str) -> np.ndarray | None:
    return parse_triplet(expression, "(", ")")


def parse_vector(expression: str) -> np.ndarray | None:
    stripped = expression.strip()
    if stripped.startswith("vec[") and stripped.endswith("]"):
        stripped = stripped[3:]

    vector = parse_triplet(stripped, "[", "]")
    if vector is not None:
        return vector
    return parse_triplet(stripped, "(", ")")


def parse_plane_equation(expression: str) -> tuple[np.ndarray, float] | None:
    compact = expression.replace(" ", "")
    if "=" not in compact:
        return None

    left, right = compact.split("=", 1)
    try:
        right_value = float(right)
    except ValueError:
        return None

    coefficients = {"x": 0.0, "y": 0.0, "z": 0.0}
    buffer = ""
    for char in left:
        if char in "xyz":
            coeff_text = buffer
            sign = 1.0
            if coeff_text.startswith("+"):
                coeff_text = coeff_text[1:]
            elif coeff_text.startswith("-"):
                coeff_text = coeff_text[1:]
                sign = -1.0
            coeff = float(coeff_text) if coeff_text else 1.0
            coefficients[char] += sign * coeff
            buffer = ""
        else:
            buffer += char

    if any(char.isalpha() for char in buffer):
        return None

    constant = 0.0
    if buffer:
        try:
            constant = float(buffer)
        except ValueError:
            return None

    normal = np.array([coefficients["x"], coefficients["y"], coefficients["z"]], dtype=float)
    if np.allclose(normal, 0.0):
        return None

    d = constant - right_value
    return normal, d


def point_on_plane(normal: np.ndarray, d: float) -> np.ndarray:
    axis = int(np.argmax(np.abs(normal)))
    point = np.zeros(3, dtype=float)
    point[axis] = -d / normal[axis]
    return point


def plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    unit = normal / np.linalg.norm(normal)
    reference = np.array([0.0, 0.0, 1.0], dtype=float)
    if abs(np.dot(unit, reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0], dtype=float)
    u = np.cross(unit, reference)
    u = u / np.linalg.norm(u)
    v = np.cross(unit, u)
    return u, v


def cylinder_basis(axis_unit: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return plane_basis(axis_unit)


def world_to_view(point: np.ndarray, camera: CameraState) -> np.ndarray:
    cy = math.cos(camera.yaw)
    sy = math.sin(camera.yaw)
    cp = math.cos(camera.pitch)
    sp = math.sin(camera.pitch)

    yaw_matrix = np.array(
        [
            [cy, 0.0, sy],
            [0.0, 1.0, 0.0],
            [-sy, 0.0, cy],
        ]
    )
    pitch_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cp, -sp],
            [0.0, sp, cp],
        ]
    )
    return pitch_matrix @ (yaw_matrix @ point)


class SceneWindow(QWidget):
    def __init__(self, state_file: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.state_file = state_file
        self._last_text = ""
        self.camera = CameraState()
        self.payload = {"objects": [], "issues": [], "status": "Waiting for scene..."}
        self.setWindowTitle("CLIGEBRA Scene")
        self.resize(980, 760)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.pull_updates)
        self.timer.start(40)

    def pull_updates(self) -> None:
        if not self.state_file.exists():
            return

        text = self.state_file.read_text(encoding="utf-8")
        if not text or text == self._last_text:
            return

        self._last_text = text
        payload = json.loads(text)
        self.payload = compile_payload(payload)
        self.update()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        changed = False
        if key == Qt.Key.Key_Left:
            self.camera.yaw -= math.radians(8)
            changed = True
        elif key == Qt.Key.Key_Right:
            self.camera.yaw += math.radians(8)
            changed = True
        elif key == Qt.Key.Key_Up:
            self.camera.pitch = min(self.camera.pitch + math.radians(8), math.radians(85))
            changed = True
        elif key == Qt.Key.Key_Down:
            self.camera.pitch = max(self.camera.pitch - math.radians(8), math.radians(-85))
            changed = True
        elif key in {Qt.Key.Key_Plus, Qt.Key.Key_Equal}:
            self.camera.scale *= 1.15
            changed = True
        elif key == Qt.Key.Key_Minus:
            self.camera.scale = max(self.camera.scale / 1.15, 8.0)
            changed = True

        if changed:
            self.update()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0c1117"))

        viewport = self.rect().adjusted(20, 20, -20, -90)
        self.draw_grid(painter, viewport)
        self.draw_axes(painter, viewport)
        self.draw_objects(painter, viewport)
        self.draw_overlay(painter)
        painter.end()

    def project(self, point: np.ndarray, viewport) -> tuple[float, float]:
        view = world_to_view(point, self.camera)
        x = viewport.center().x() + view[0] * self.camera.scale
        y = viewport.center().y() - view[1] * self.camera.scale
        return x, y

    def draw_grid(self, painter: QPainter, viewport) -> None:
        painter.setPen(QPen(QColor("#18222d"), 1))
        for x in range(viewport.left(), viewport.right() + 1, 40):
            painter.drawLine(x, viewport.top(), x, viewport.bottom())
        for y in range(viewport.top(), viewport.bottom() + 1, 40):
            painter.drawLine(viewport.left(), y, viewport.right(), y)

    def draw_axes(self, painter: QPainter, viewport) -> None:
        origin = np.zeros(3, dtype=float)
        axes = [
            (np.array([4.0, 0.0, 0.0], dtype=float), QColor("#ff6b6b"), "x"),
            (np.array([0.0, 4.0, 0.0], dtype=float), QColor("#51cf66"), "y"),
            (np.array([0.0, 0.0, 4.0], dtype=float), QColor("#4dabf7"), "z"),
        ]
        origin_xy = self.project(origin, viewport)
        for axis_end, color, label in axes:
            painter.setPen(QPen(color, 2))
            end_xy = self.project(axis_end, viewport)
            painter.drawLine(*origin_xy, *end_xy)
            painter.drawText(int(end_xy[0] + 4), int(end_xy[1] - 4), label)

        painter.setBrush(QColor("#f8f9fa"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(origin_xy[0] - 3), int(origin_xy[1] - 3), 6, 6)

    def draw_objects(self, painter: QPainter, viewport) -> None:
        for obj in self.payload.get("objects", []):
            kind = obj["kind"]
            if kind == "point":
                self.draw_point(painter, viewport, np.array(obj["point"], dtype=float), obj["name"])
            elif kind == "vector":
                self.draw_vector(painter, viewport, np.array(obj["vector"], dtype=float), obj["name"])
            elif kind == "line":
                self.draw_line(
                    painter,
                    viewport,
                    np.array(obj["anchor"], dtype=float),
                    np.array(obj["direction"], dtype=float),
                    obj["name"],
                )
            elif kind == "plane":
                self.draw_plane(
                    painter,
                    viewport,
                    np.array(obj["point"], dtype=float),
                    np.array(obj["normal"], dtype=float),
                    obj["name"],
                )
            elif kind == "cylinder":
                self.draw_cylinder(
                    painter,
                    viewport,
                    np.array(obj["start"], dtype=float),
                    np.array(obj["end"], dtype=float),
                    float(obj["radius"]),
                    obj["name"],
                )

    def draw_point(self, painter: QPainter, viewport, point: np.ndarray, name: str) -> None:
        x, y = self.project(point, viewport)
        painter.setPen(QPen(QColor("#ffd43b"), 2))
        painter.setBrush(QColor("#ffd43b"))
        painter.drawEllipse(int(x - 4), int(y - 4), 8, 8)
        painter.setPen(QPen(QColor("#f8f9fa")))
        painter.drawText(int(x + 6), int(y - 6), name)

    def draw_vector(self, painter: QPainter, viewport, vector: np.ndarray, name: str) -> None:
        start = self.project(np.zeros(3, dtype=float), viewport)
        end = self.project(vector, viewport)
        vector_color = QColor("#ff922b")
        painter.setPen(QPen(vector_color, 3))
        painter.drawLine(*start, *end)
        self.draw_arrowhead(painter, start, end, vector_color)
        painter.setPen(QPen(QColor("#ffe8cc")))
        painter.drawText(int(end[0] + 6), int(end[1] - 6), name)

    def draw_arrowhead(
        self,
        painter: QPainter,
        start: tuple[float, float],
        end: tuple[float, float],
        color: QColor,
    ) -> None:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 1.0:
            return

        ux = dx / length
        uy = dy / length
        size = 13.0
        wing = 0.55
        left = (
            end[0] - size * (ux * math.cos(wing) - uy * math.sin(wing)),
            end[1] - size * (uy * math.cos(wing) + ux * math.sin(wing)),
        )
        right = (
            end[0] - size * (ux * math.cos(-wing) - uy * math.sin(-wing)),
            end[1] - size * (uy * math.cos(-wing) + ux * math.sin(-wing)),
        )

        painter.setPen(QPen(color, 2))
        painter.drawLine(*end, *left)
        painter.drawLine(*end, *right)

    def draw_line(self, painter: QPainter, viewport, anchor: np.ndarray, direction: np.ndarray, name: str) -> None:
        unit = direction / np.linalg.norm(direction)
        start = anchor - unit * 8.0
        end = anchor + unit * 8.0
        painter.setPen(QPen(QColor("#dee2e6"), 1))
        painter.drawLine(*self.project(start, viewport), *self.project(end, viewport))
        label_pos = self.project(anchor + unit * 1.5, viewport)
        painter.drawText(int(label_pos[0] + 4), int(label_pos[1] - 4), name)

    def draw_plane(self, painter: QPainter, viewport, point: np.ndarray, normal: np.ndarray, name: str) -> None:
        u, v = plane_basis(normal)
        painter.setPen(QPen(QColor("#495057"), 1))
        for a in np.linspace(-4.0, 4.0, 5):
            previous = None
            for b in np.linspace(-4.0, 4.0, 16):
                sample = point + u * a + v * b
                current = self.project(sample, viewport)
                if previous is not None:
                    painter.drawLine(*previous, *current)
                previous = current
        for b in np.linspace(-4.0, 4.0, 5):
            previous = None
            for a in np.linspace(-4.0, 4.0, 16):
                sample = point + u * a + v * b
                current = self.project(sample, viewport)
                if previous is not None:
                    painter.drawLine(*previous, *current)
                previous = current
        label = self.project(point, viewport)
        painter.setPen(QPen(QColor("#adb5bd")))
        painter.drawText(int(label[0] + 6), int(label[1] - 6), name)

    def draw_cylinder(
        self,
        painter: QPainter,
        viewport,
        start: np.ndarray,
        end: np.ndarray,
        radius: float,
        name: str,
    ) -> None:
        axis = end - start
        axis_norm = np.linalg.norm(axis)
        if axis_norm == 0.0:
            return

        axis_unit = axis / axis_norm
        u, v = cylinder_basis(axis_unit)
        segments = 24
        bottom_points: list[np.ndarray] = []
        top_points: list[np.ndarray] = []

        for index in range(segments):
            angle = math.tau * index / segments
            offset = radius * (math.cos(angle) * u + math.sin(angle) * v)
            bottom_points.append(start + offset)
            top_points.append(end + offset)

        cylinder_color = QColor("#22d3c5")
        painter.setPen(QPen(cylinder_color, 2))
        for index in range(segments):
            next_index = (index + 1) % segments
            painter.drawLine(
                *self.project(bottom_points[index], viewport),
                *self.project(bottom_points[next_index], viewport),
            )
            painter.drawLine(
                *self.project(top_points[index], viewport),
                *self.project(top_points[next_index], viewport),
            )
            if index % 4 == 0:
                painter.drawLine(
                    *self.project(bottom_points[index], viewport),
                    *self.project(top_points[index], viewport),
                )

        label = self.project((start + end) / 2 + u * radius * 1.2, viewport)
        painter.setPen(QPen(QColor("#99f6e4")))
        painter.drawText(int(label[0] + 6), int(label[1] - 6), name)

    def draw_overlay(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor("#e9ecef")))
        painter.setFont(QFont("Menlo", 10))
        footer_top = self.height() - 58
        painter.drawText(24, footer_top, "CLIGEBRA Scene Window")
        painter.drawText(
            24,
            footer_top + 20,
            f"objects {len(self.payload.get('objects', []))}  issues {len(self.payload.get('issues', []))}",
        )
        painter.drawText(24, footer_top + 40, "camera: arrows rotate   +/- zoom")
        issues = self.payload.get("issues", [])
        if issues:
            painter.setPen(QPen(QColor("#ff8787")))
            painter.drawText(360, footer_top + 20, " | ".join(issues[:2]))


def compile_payload(scene_payload: dict) -> dict:
    compiled_objects: list[dict] = []
    issues: list[str] = list(scene_payload.get("parse_issues", []))

    for obj in scene_payload.get("objects", []):
        kind = obj["kind"]
        expression = obj["expression"]
        name = obj["name"]

        if kind == "point":
            point = parse_point(expression)
            if point is None:
                issues.append(f"{name}: invalid point syntax")
                continue
            compiled_objects.append({"kind": "point", "name": name, "point": point.tolist()})
            continue

        if kind == "vector":
            vector = parse_vector(expression)
            if vector is None:
                issues.append(f"{name}: invalid vector syntax")
                continue
            compiled_objects.append({"kind": "vector", "name": name, "vector": vector.tolist()})
            continue

        if kind == "line":
            try:
                anchor_expr, direction_expr = parse_line_expression(expression)
            except ValueError:
                issues.append(f"{name}: expected line(point(...), dir(...))")
                continue
            anchor = parse_point(anchor_expr)
            direction = parse_vector(direction_expr)
            if anchor is None or direction is None or np.allclose(direction, 0.0):
                issues.append(f"{name}: invalid line geometry")
                continue
            compiled_objects.append(
                {
                    "kind": "line",
                    "name": name,
                    "anchor": anchor.tolist(),
                    "direction": direction.tolist(),
                }
            )
            continue

        if kind == "plane":
            if "normal" in expression and "point" in expression:
                try:
                    left, right = expression.split("normal", 1)
                    point_expr = left.replace("point", "", 1).strip()
                    normal_expr = right.strip()
                except ValueError:
                    issues.append(f"{name}: invalid plane syntax")
                    continue
                point = parse_point(point_expr)
                normal = parse_vector(normal_expr)
            else:
                equation = parse_plane_equation(expression)
                if equation is None:
                    issues.append(f"{name}: invalid plane syntax")
                    continue
                normal, d = equation
                point = point_on_plane(normal, d)

            if point is None or normal is None or np.allclose(normal, 0.0):
                issues.append(f"{name}: invalid plane geometry")
                continue

            compiled_objects.append(
                {
                    "kind": "plane",
                    "name": name,
                    "point": point.tolist(),
                    "normal": normal.tolist(),
                }
            )
            continue

        if kind == "cylinder":
            try:
                start_expr, end_expr, radius = parse_cylinder_expression(expression)
            except ValueError as error:
                issues.append(f"{name}: {error}")
                continue

            start = parse_point(start_expr)
            end = parse_point(end_expr)
            axis = None if start is None or end is None else end - start
            if start is None or end is None:
                issues.append(f"{name}: cylinder points must use (x,y,z)")
                continue
            if radius <= 0.0:
                issues.append(f"{name}: cylinder radius must be greater than 0")
                continue
            if axis is None or np.allclose(axis, 0.0):
                issues.append(f"{name}: cylinder start and end must be different points")
                continue

            compiled_objects.append(
                {
                    "kind": "cylinder",
                    "name": name,
                    "start": start.tolist(),
                    "end": end.tolist(),
                    "radius": radius,
                }
            )
            continue

        issues.append(f"{name}: unsupported {kind}")

    return {"objects": compiled_objects, "issues": issues, "status": scene_payload.get("status", "")}


def parse_line_expression(expression: str) -> tuple[str, str]:
    stripped = expression.strip()
    call_match = LINE_CALL_RE.fullmatch(stripped)
    if call_match is not None:
        return call_match.group(1), call_match.group(2)

    legacy_match = LINE_LEGACY_RE.fullmatch(stripped)
    if legacy_match is not None:
        return legacy_match.group(1), legacy_match.group(2)

    raise ValueError("invalid line expression")


def parse_cylinder_expression(expression: str) -> tuple[str, str, float]:
    stripped = expression.strip()
    match = CYLINDER_RE.fullmatch(stripped)
    if match is None:
        raise ValueError("expected zyl((x,y,z), (x,y,z), radius)")

    start_expr, end_expr, radius_expr = match.groups()
    try:
        radius = float(radius_expr.strip())
    except ValueError as error:
        raise ValueError("cylinder radius must be numeric") from error

    return start_expr, end_expr, radius


def renderer_main(state_file: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = SceneWindow(state_file)
    window.show()
    app.exec()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m cligebra.renderer_window <state-file>")
    renderer_main(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
