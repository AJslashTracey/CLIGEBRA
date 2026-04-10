from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np


LINE_LEGACY_RE = re.compile(
    r"point\s*(\([^)]*\))\s*dir\s*(\([^)]*\)|\[[^]]*\]|vec\[[^]]*\])",
    re.IGNORECASE,
)
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


def resolve_point(expression: str, named_points: dict[str, np.ndarray]) -> np.ndarray | None:
    stripped = expression.strip()
    if stripped.lower().startswith("point(") and stripped.endswith(")"):
        stripped = stripped[stripped.find("(") :]
    point = parse_point(stripped)
    if point is not None:
        return point
    return named_points.get(stripped)


def resolve_vector(expression: str, named_vectors: dict[str, np.ndarray]) -> np.ndarray | None:
    stripped = expression.strip()
    if stripped.lower().startswith("dir(") and stripped.endswith(")"):
        stripped = stripped[stripped.find("(") :]
    vector = parse_vector(stripped)
    if vector is not None:
        return vector
    return named_vectors.get(stripped)


def split_call_arguments(arguments: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    paren_depth = 0
    bracket_depth = 0

    for char in arguments:
        if char == "," and paren_depth == 0 and bracket_depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        current.append(char)

    if current:
        parts.append("".join(current).strip())

    if paren_depth != 0 or bracket_depth != 0:
        raise ValueError("unbalanced delimiters")

    return parts


def parse_constructor_call(expression: str, names: tuple[str, ...]) -> list[str]:
    stripped = expression.strip()
    name_pattern = "|".join(re.escape(name) for name in names)
    call_match = re.fullmatch(rf"(?:{name_pattern})\s*\((.*)\)", stripped, re.IGNORECASE)
    if call_match is None:
        raise ValueError("invalid constructor call")
    return split_call_arguments(call_match.group(1))


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


def configure_renderer_environment() -> None:
    temp_dir = Path(os.environ.get("TMPDIR", "/tmp"))
    matplotlib_config = temp_dir / "cligebra_matplotlib"
    font_cache = temp_dir / "cligebra_cache"
    matplotlib_config.mkdir(parents=True, exist_ok=True)
    font_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_config))
    os.environ.setdefault("XDG_CACHE_HOME", str(font_cache))


class PyVistaSceneWindow:
    def __init__(self, state_file: Path) -> None:
        configure_renderer_environment()

        import pyvista as pv

        self.state_file = state_file
        self._last_text = ""
        self.payload = {"objects": [], "issues": [], "status": "Waiting for scene..."}
        self.pv = pv
        self._finite_scene_points: list[np.ndarray] = []
        self._finite_scene_center = np.zeros(3, dtype=float)
        self._finite_scene_radius = 4.0
        self.plotter = pv.Plotter(window_size=(1100, 820), title="CLIGEBRA Scene")
        self.plotter.set_background("#0c1117")
        self.plotter.enable_anti_aliasing()
        self.plotter.add_axes(line_width=4, labels_off=False)
        self.plotter.show_grid(color="#273442")
        self.plotter.camera_position = "iso"

    def run(self) -> None:
        self.pull_updates(force=True)
        self.plotter.show(interactive_update=True, auto_close=False)
        while not self.plotter.iren.interactor.GetDone():
            self.pull_updates()
            self.plotter.update()
            time.sleep(0.04)

    def pull_updates(self, *, force: bool = False) -> None:
        if not self.state_file.exists():
            return

        text = self.state_file.read_text(encoding="utf-8")
        if not text or (text == self._last_text and not force):
            return

        self._last_text = text
        payload = json.loads(text)
        self.payload = compile_payload(payload)
        self.draw_scene()

    def draw_scene(self) -> None:
        camera_position = self.plotter.camera_position
        self.plotter.clear()
        self.plotter.set_background("#0c1117")
        self.plotter.add_axes(line_width=4, labels_off=False)
        self.plotter.show_grid(color="#273442")
        self._finite_scene_points = self.finite_scene_points()
        self._finite_scene_center, self._finite_scene_radius = self.finite_scene_bounds()
        for obj in self.payload.get("objects", []):
            kind = obj["kind"]
            if kind == "point":
                self.draw_point(np.array(obj["point"], dtype=float), obj["name"])
            elif kind == "vector":
                self.draw_vector(np.array(obj["vector"], dtype=float), obj["name"])
            elif kind == "line":
                self.draw_line(
                    np.array(obj["anchor"], dtype=float),
                    np.array(obj["direction"], dtype=float),
                    obj["name"],
                )
            elif kind == "plane":
                self.draw_plane(
                    np.array(obj["point"], dtype=float),
                    np.array(obj["normal"], dtype=float),
                    obj["name"],
                )
            elif kind == "cylinder":
                self.draw_cylinder(
                    np.array(obj["start"], dtype=float),
                    np.array(obj["end"], dtype=float),
                    float(obj["radius"]),
                    obj["name"],
                )
        self.draw_overlay()
        self.plotter.camera_position = camera_position
        self.plotter.render()

    def draw_point(self, point: np.ndarray, name: str) -> None:
        self.plotter.add_points(point.reshape(1, 3), color="#ffd43b", point_size=14, render_points_as_spheres=True)
        self.plotter.add_point_labels(
            [point],
            [name],
            font_size=14,
            text_color="#fff3bf",
            shape=None,
            point_size=0,
        )

    def draw_vector(self, vector: np.ndarray, name: str) -> None:
        if np.allclose(vector, 0.0):
            return
        length = np.linalg.norm(vector)
        unit = vector / length
        tip_length = min(0.35, length * 0.35)
        shaft_length = max(0.0, length - tip_length)
        shaft_radius = min(0.035, length * 0.04)
        tip_radius = min(0.12, length * 0.12)

        if shaft_length > 0.0:
            shaft = self.pv.Cylinder(
                center=unit * (shaft_length / 2),
                direction=unit,
                radius=shaft_radius,
                height=shaft_length,
                resolution=18,
            )
            self.plotter.add_mesh(shaft, color="#ff922b", smooth_shading=True)

        tip = self.pv.Cone(
            center=vector - unit * (tip_length / 2),
            direction=unit,
            height=tip_length,
            radius=tip_radius,
            resolution=24,
        )
        self.plotter.add_mesh(tip, color="#ff922b", smooth_shading=True)
        self.plotter.add_point_labels(
            [vector],
            [name],
            font_size=14,
            text_color="#ffe8cc",
            shape=None,
            point_size=0,
        )

    def draw_line(self, anchor: np.ndarray, direction: np.ndarray, name: str) -> None:
        unit = direction / np.linalg.norm(direction)
        line_center = self.line_render_center(anchor, unit)
        line_half_extent = self.line_render_half_extent()
        start = line_center - unit * line_half_extent
        end = line_center + unit * line_half_extent
        line = self.pv.Line(start, end)
        self.plotter.add_mesh(line, color="#dee2e6", line_width=4)
        self.plotter.add_point_labels(
            [line_center + unit * min(1.5, line_half_extent * 0.2)],
            [name],
            font_size=14,
            text_color="#f8f9fa",
            shape=None,
            point_size=0,
        )

    def draw_plane(self, point: np.ndarray, normal: np.ndarray, name: str) -> None:
        plane_center = self.plane_render_center(point, normal)
        plane_size = self.plane_render_size()
        plane = self.pv.Plane(
            center=plane_center,
            direction=normal,
            i_size=plane_size,
            j_size=plane_size,
            i_resolution=8,
            j_resolution=8,
        )
        self.plotter.add_mesh(plane, color="#868e96", opacity=0.22, show_edges=True, edge_color="#adb5bd")
        self.plotter.add_point_labels(
            [plane_center],
            [name],
            font_size=14,
            text_color="#ced4da",
            shape=None,
            point_size=0,
        )

    def draw_cylinder(self, start: np.ndarray, end: np.ndarray, radius: float, name: str) -> None:
        axis = end - start
        axis_norm = np.linalg.norm(axis)
        if axis_norm == 0.0:
            return

        cylinder = self.pv.Cylinder(
            center=(start + end) / 2,
            direction=axis,
            radius=radius,
            height=axis_norm,
            resolution=24,
            capping=False,
        )
        self.plotter.add_mesh(cylinder, color="#22d3c5", opacity=0.35, show_edges=True, edge_color="#99f6e4")
        self.plotter.add_point_labels(
            [(start + end) / 2],
            [name],
            font_size=14,
            text_color="#99f6e4",
            shape=None,
            point_size=0,
        )

    def draw_overlay(self) -> None:
        lines = [
           "" 
        ]
        issues = self.payload.get("issues", [])
        if issues:
            lines.append(" | ".join(issues[:2]))
        self.plotter.add_text("\n".join(lines), position="lower_left", font_size=10, color="#e9ecef")

    def finite_scene_points(self) -> list[np.ndarray]:
        points: list[np.ndarray] = []

        for obj in self.payload.get("objects", []):
            kind = obj["kind"]
            if kind == "point":
                points.append(np.array(obj["point"], dtype=float))
            elif kind == "vector":
                points.append(np.array(obj["vector"], dtype=float))
            elif kind == "cylinder":
                start = np.array(obj["start"], dtype=float)
                end = np.array(obj["end"], dtype=float)
                radius = float(obj["radius"])
                offsets = [
                    np.array([radius, 0.0, 0.0], dtype=float),
                    np.array([-radius, 0.0, 0.0], dtype=float),
                    np.array([0.0, radius, 0.0], dtype=float),
                    np.array([0.0, -radius, 0.0], dtype=float),
                    np.array([0.0, 0.0, radius], dtype=float),
                    np.array([0.0, 0.0, -radius], dtype=float),
                ]
                points.extend([start, end])
                for offset in offsets:
                    points.extend([start + offset, end + offset])

        return points or [np.zeros(3, dtype=float)]

    def finite_scene_bounds(self) -> tuple[np.ndarray, float]:
        if not self._finite_scene_points:
            return np.zeros(3, dtype=float), 4.0

        points = np.array(self._finite_scene_points, dtype=float)
        center = points.mean(axis=0)
        distances = np.linalg.norm(points - center, axis=1)
        radius = max(4.0, float(distances.max(initial=0.0)))
        return center, radius

    def plane_render_center(self, point: np.ndarray, normal: np.ndarray) -> np.ndarray:
        unit = normal / np.linalg.norm(normal)
        relative = self._finite_scene_center - point
        return self._finite_scene_center - unit * float(np.dot(relative, unit))

    def plane_render_size(self) -> float:
        return max(16.0, self._finite_scene_radius * 3.0)

    def line_render_center(self, anchor: np.ndarray, unit: np.ndarray) -> np.ndarray:
        relative = self._finite_scene_center - anchor
        return anchor + unit * float(np.dot(relative, unit))

    def line_render_half_extent(self) -> float:
        return max(8.0, self._finite_scene_radius * 1.8)


def compile_payload(scene_payload: dict) -> dict:
    compiled_objects: list[dict] = []
    issues: list[str] = list(scene_payload.get("parse_issues", []))
    named_points: dict[str, np.ndarray] = {}
    named_vectors: dict[str, np.ndarray] = {}

    for obj in scene_payload.get("objects", []):
        kind = obj["kind"]
        expression = obj["expression"]
        name = obj["name"]

        if kind == "point":
            point = parse_point(expression)
            if point is None:
                issues.append(f"{name}: invalid point syntax")
                continue
            named_points[name] = point
            compiled_objects.append({"kind": "point", "name": name, "point": point.tolist()})
            continue

        if kind == "vector":
            vector = parse_vector(expression)
            if vector is None:
                issues.append(f"{name}: invalid vector syntax")
                continue
            named_vectors[name] = vector
            compiled_objects.append({"kind": "vector", "name": name, "vector": vector.tolist()})
            continue

        if kind == "line":
            try:
                anchor, direction = compile_line_expression(expression, named_points, named_vectors)
            except ValueError as error:
                issues.append(f"{name}: {error}")
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
                point = resolve_point(point_expr, named_points)
                normal = resolve_vector(normal_expr, named_vectors)
            elif expression.strip().startswith("plane("):
                try:
                    point, normal = compile_plane_constructor(expression, named_points, named_vectors)
                except ValueError as error:
                    issues.append(f"{name}: {error}")
                    continue
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

            start = resolve_point(start_expr, named_points)
            end = resolve_point(end_expr, named_points)
            axis = None if start is None or end is None else end - start
            if start is None or end is None:
                issues.append(f"{name}: cylinder endpoints must be points or point names")
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
    legacy_match = LINE_LEGACY_RE.fullmatch(stripped)
    if legacy_match is not None:
        return legacy_match.group(1), legacy_match.group(2)

    raise ValueError("invalid line expression")


def compile_line_expression(
    expression: str,
    named_points: dict[str, np.ndarray],
    named_vectors: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    stripped = expression.strip()

    try:
        first_arg, second_arg = parse_constructor_call(stripped, ("line",))
    except ValueError:
        anchor_expr, direction_expr = parse_line_expression(expression)
        anchor = resolve_point(anchor_expr, named_points)
        direction = resolve_vector(direction_expr, named_vectors)
        if anchor is None or direction is None or np.allclose(direction, 0.0):
            raise ValueError("invalid line geometry")
        return anchor, direction

    if any(not part for part in (first_arg, second_arg)):
        raise ValueError("expected line(point, vector) or line(point, point)")

    anchor = resolve_point(first_arg, named_points)
    if anchor is None:
        raise ValueError("line anchor must be a point or point name")

    second_point = resolve_point(second_arg, named_points)
    if second_point is not None:
        direction = second_point - anchor
        if np.allclose(direction, 0.0):
            raise ValueError("line points must be different")
        return anchor, direction

    direction = resolve_vector(second_arg, named_vectors)
    if direction is not None and not np.allclose(direction, 0.0):
        return anchor, direction

    raise ValueError("line second argument must be a vector, point, or object name")


def compile_plane_constructor(
    expression: str,
    named_points: dict[str, np.ndarray],
    named_vectors: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    try:
        args = parse_constructor_call(expression, ("plane",))
    except ValueError as error:
        raise ValueError("invalid plane syntax") from error

    if len(args) == 2:
        point = resolve_point(args[0], named_points)
        normal = resolve_vector(args[1], named_vectors)
        if point is None:
            raise ValueError("plane first argument must be a point or point name")
        if normal is None or np.allclose(normal, 0.0):
            raise ValueError("plane second argument must be a non-zero vector or vector name")
        return point, normal

    if len(args) != 3:
        raise ValueError("expected plane(point, normal), plane(p1, p2, p3), or plane(point, v1, v2)")

    point = resolve_point(args[0], named_points)
    if point is None:
        raise ValueError("plane first argument must be a point or point name")

    second_point = resolve_point(args[1], named_points)
    third_point = resolve_point(args[2], named_points)
    if second_point is not None and third_point is not None:
        v1 = second_point - point
        v2 = third_point - point
        normal = np.cross(v1, v2)
        if np.allclose(normal, 0.0):
            raise ValueError("plane points must not be collinear")
        return point, normal

    v1 = resolve_vector(args[1], named_vectors)
    v2 = resolve_vector(args[2], named_vectors)
    if v1 is None or v2 is None:
        raise ValueError("plane arguments must be three points or one point plus two vectors")

    normal = np.cross(v1, v2)
    if np.allclose(normal, 0.0):
        raise ValueError("plane vectors must not be parallel")
    return point, normal


def parse_cylinder_expression(expression: str) -> tuple[str, str, float]:
    stripped = expression.strip()
    call_match = re.fullmatch(r"(?:zyl|cyl|cylinder)\s*\((.*)\)", stripped, re.IGNORECASE)
    if call_match is None:
        raise ValueError("expected cyl((x,y,z), (x,y,z), radius)")

    try:
        start_expr, end_expr, radius_expr = split_call_arguments(call_match.group(1))
    except ValueError as error:
        raise ValueError("expected cyl((x,y,z), (x,y,z), radius)") from error

    if any(not part for part in (start_expr, end_expr, radius_expr)):
        raise ValueError("expected cyl((x,y,z), (x,y,z), radius)")

    try:
        radius = float(radius_expr.strip())
    except ValueError as error:
        raise ValueError("cylinder radius must be numeric") from error

    return start_expr, end_expr, radius


def renderer_main(state_file: Path) -> None:
    window = PyVistaSceneWindow(state_file)
    window.run()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m cligebra.renderer_window <state-file>")
    renderer_main(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
