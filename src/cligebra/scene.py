from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SceneObject:
    kind: str
    name: str
    expression: str
    line_no: int
    anonymous: bool = False


@dataclass(slots=True)
class ParseIssue:
    line_no: int
    message: str


SCENE_SAMPLE = """# Scene buffer
# Edit objects here. Parsed objects appear in the sidebar.
p1 = (0, 0, 0)
v1 = vec[1, 2, 0]
l1 = line(point(0,0,0), dir(1,1,0))
a = 2x + y + 2z - 8 = 0
vec[0, 0, 2]
"""


VALID_KINDS = {"point", "vector", "line", "plane", "cylinder"}
KIND_ALIASES = {
    "point": "point",
    "pt": "point",
    "vector": "vector",
    "vec": "vector",
    "line": "line",
    "ln": "line",
    "plane": "plane",
    "pl": "plane",
    "cylinder": "cylinder",
    "cyl": "cylinder",
}


def parse_scene(source: str) -> tuple[list[SceneObject], list[ParseIssue]]:
    objects: list[SceneObject] = []
    issues: list[ParseIssue] = []

    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        anonymous = "=" not in line
        if anonymous:
            expression = line
            name = f"_{line_no}"
            kind = infer_kind(expression)
        else:
            head, expression = [part.strip() for part in line.split("=", 1)]
            head_parts = head.split()
            if len(head_parts) == 1:
                name = head_parts[0]
                kind = infer_kind(expression)
            elif len(head_parts) == 2:
                declared_kind, name = head_parts
                kind = KIND_ALIASES.get(declared_kind)
                if kind is None:
                    issues.append(ParseIssue(line_no, f"Unknown object type '{declared_kind}'"))
                    continue
            else:
                issues.append(ParseIssue(line_no, "Expected '<name> = <expr>' or '<kind> <name> = <expr>'"))
                continue

        if kind is None:
            issues.append(ParseIssue(line_no, "Could not infer object type from expression"))
            continue

        if not name.replace("_", "").isalnum():
            issues.append(ParseIssue(line_no, f"Invalid object name '{name}'"))
            continue

        if kind == "vector":
            stripped = expression.strip()
            if not (
                stripped.startswith("vec[")
                and stripped.endswith("]")
                or stripped.startswith("[")
                and stripped.endswith("]")
            ):
                issues.append(ParseIssue(line_no, "Vectors must use vec[x, y, z]"))
                continue

        objects.append(
            SceneObject(
                kind=kind,
                name=name,
                expression=expression,
                line_no=line_no,
                anonymous=anonymous,
            )
        )

    return objects, issues


def infer_kind(expression: str) -> str | None:
    stripped = expression.strip()
    compact = stripped.replace(" ", "")

    if stripped.startswith("vec[") and stripped.endswith("]"):
        return "vector"
    if stripped.startswith("[") and stripped.endswith("]"):
        return "vector"
    if stripped.startswith("(") and stripped.endswith("]"):
        return None
    if stripped.startswith("(") and stripped.endswith(")"):
        return "point"
    if stripped.startswith("line(") and stripped.endswith(")"):
        return "line"
    if stripped.lower().startswith("point") and "dir" in stripped.lower():
        return "line"
    if "normal" in stripped.lower() and "point" in stripped.lower():
        return "plane"
    if "=" in compact and any(axis in compact for axis in "xyz"):
        return "plane"
    if stripped.startswith("plane(") and stripped.endswith(")"):
        return "plane"
    return None
