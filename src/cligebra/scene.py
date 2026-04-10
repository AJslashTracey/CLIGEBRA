from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SceneObject:
    kind: str
    name: str
    expression: str
    line_no: int


@dataclass(slots=True)
class ParseIssue:
    line_no: int
    message: str


SCENE_SAMPLE = """# Scene buffer
# Edit objects here. Parsed objects appear in the sidebar.
point P1 = (0, 0, 0)
vector V1 = [1, 2, 0]
line L1 = point(0,0,0) dir(1,1,0)
plane A = 2x + y + 2z - 8 = 0
"""


VALID_KINDS = {"point", "vector", "line", "plane", "cylinder"}


def parse_scene(source: str) -> tuple[list[SceneObject], list[ParseIssue]]:
    objects: list[SceneObject] = []
    issues: list[ParseIssue] = []

    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            issues.append(ParseIssue(line_no, "Expected '=' in object definition"))
            continue

        head, expression = [part.strip() for part in line.split("=", 1)]
        head_parts = head.split()
        if len(head_parts) != 2:
            issues.append(ParseIssue(line_no, "Expected '<kind> <name> = <expr>'"))
            continue

        kind, name = head_parts
        if kind not in VALID_KINDS:
            issues.append(ParseIssue(line_no, f"Unknown object type '{kind}'"))
            continue

        if not name.replace("_", "").isalnum():
            issues.append(ParseIssue(line_no, f"Invalid object name '{name}'"))
            continue

        if kind == "vector":
            stripped = expression.strip()
            if not (stripped.startswith("[") and stripped.endswith("]")):
                issues.append(ParseIssue(line_no, "Vectors must use square brackets: [x, y, z]"))
                continue

        objects.append(
            SceneObject(
                kind=kind,
                name=name,
                expression=expression,
                line_no=line_no,
            )
        )

    return objects, issues
