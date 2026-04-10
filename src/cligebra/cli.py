from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from cligebra.app import run as run_tui
from cligebra.renderer_bridge import RendererBridge
from cligebra.renderer_window import compile_payload
from cligebra.scene import ParseIssue, SceneObject, parse_scene


@dataclass(frozen=True)
class CliIssue:
    line_no: int | None
    message: str
    source: str

    def format(self, path: Path) -> str:
        if self.line_no is None:
            return f"{path}: {self.message}"
        return f"{path}:{self.line_no}: {self.message}"


@dataclass(frozen=True)
class SceneRead:
    objects: list[SceneObject]
    rendered_object_count: int
    parse_issues: list[ParseIssue]
    compiled_issues: list[str]
    cli_issues: list[CliIssue]
    status: str


def scene_status(objects: list[SceneObject], issues: list[ParseIssue]) -> str:
    if issues:
        return f"{len(objects)} objects, {len(issues)} issues"
    return f"{len(objects)} objects parsed cleanly"


def compiled_scene_status(object_count: int, issue_count: int) -> str:
    if issue_count:
        return f"{object_count} objects, {issue_count} issues"
    return f"{object_count} objects rendered cleanly"


def load_scene_file(path: Path) -> tuple[list[SceneObject], list[ParseIssue], str]:
    source = path.read_text(encoding="utf-8")
    objects, parse_issues = parse_scene(source)
    return objects, parse_issues, scene_status(objects, parse_issues)


def read_scene(path: Path) -> tuple[list[SceneObject], list[ParseIssue], list[str], str]:
    scene = read_scene_details(path)
    return scene.objects, scene.parse_issues, scene.compiled_issues, scene.status


def read_scene_details(path: Path) -> SceneRead:
    objects, parse_issues, parse_status = load_scene_file(path)
    payload = compile_payload(
        {
            "objects": [asdict(obj) for obj in objects],
            "parse_issues": parse_issue_messages(parse_issues),
            "status": parse_status,
        }
    )
    status = compiled_scene_status(len(payload["objects"]), len(payload["issues"]))
    return SceneRead(
        objects=objects,
        rendered_object_count=len(payload["objects"]),
        parse_issues=parse_issues,
        compiled_issues=payload["issues"],
        cli_issues=build_cli_issues(objects, parse_issues, payload["issues"]),
        status=status,
    )


def parse_issue_messages(issues: list[ParseIssue]) -> list[str]:
    return [f"line {issue.line_no}: {issue.message}" for issue in issues]


def build_cli_issues(
    objects: list[SceneObject],
    parse_issues: list[ParseIssue],
    compiled_issues: list[str],
) -> list[CliIssue]:
    issues = [CliIssue(issue.line_no, issue.message, "parse") for issue in parse_issues]
    parse_issue_text = set(parse_issue_messages(parse_issues))
    line_by_name = {obj.name: obj.line_no for obj in objects}

    for issue in compiled_issues:
        if issue in parse_issue_text:
            continue

        object_name, separator, _ = issue.partition(":")
        line_no = line_by_name.get(object_name) if separator else None
        issues.append(CliIssue(line_no, issue, "geometry"))

    return issues


def print_plain_check_result(path: Path, scene: SceneRead) -> int:
    if not scene.cli_issues:
        print(f"{path}: ok ({len(scene.objects)} objects)")
        return 0

    for issue in scene.cli_issues:
        print(issue.format(path), file=sys.stderr)

    return 1


def print_json_check_result(path: Path, scene: SceneRead) -> int:
    result = {
        "path": str(path),
        "ok": not scene.cli_issues,
        "object_count": len(scene.objects),
        "rendered_object_count": scene.rendered_object_count,
        "status": scene.status,
        "issues": [
            {
                "line": issue.line_no,
                "message": issue.message,
                "source": issue.source,
            }
            for issue in scene.cli_issues
        ],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def print_check_result(path: Path, *, json_output: bool = False) -> int:
    try:
        scene = read_scene_details(path)
    except OSError as error:
        if json_output:
            print(
                json.dumps(
                    {
                        "path": str(path),
                        "ok": False,
                        "object_count": 0,
                        "rendered_object_count": 0,
                        "status": "file error",
                        "issues": [{"line": None, "message": str(error), "source": "io"}],
                    },
                    indent=2,
                )
            )
        else:
            print(f"{path}: {error}", file=sys.stderr)
        return 1

    if json_output:
        return print_json_check_result(path, scene)
    return print_plain_check_result(path, scene)


def print_watch_issues(path: Path, issues: list[CliIssue]) -> None:
    for issue in issues:
        print(issue.format(path), file=sys.stderr)


def watch_file(path: Path, *, interval: float) -> int:
    if not path.exists():
        print(f"{path}: file does not exist", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"{path}: not a file", file=sys.stderr)
        return 1

    bridge = RendererBridge()
    bridge.start()
    last_mtime: int | None = None
    print(f"Watching {path}. Save the file to update the renderer. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                mtime = path.stat().st_mtime_ns
            except OSError as error:
                print(f"{path}: {error}", file=sys.stderr)
                time.sleep(interval)
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    scene = read_scene_details(path)
                except OSError as error:
                    print(f"{path}: {error}", file=sys.stderr)
                    time.sleep(interval)
                    continue

                bridge.send_scene(scene.objects, scene.parse_issues, scene.status)
                print(f"{path}: {scene.status}")
                if scene.cli_issues:
                    print_watch_issues(path, scene.cli_issues)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped CLIGEBRA watcher.")
        return 0
    finally:
        bridge.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cligebra", description="CLIGEBRA geometry workspace")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("tui", help="open the interactive TUI")

    watch = subparsers.add_parser("watch", help="watch a .clg scene file and update the renderer")
    watch.add_argument("file", type=Path, help="scene file to watch")
    watch.add_argument("--interval", type=float, default=0.25, help="watch polling interval in seconds")

    check = subparsers.add_parser("check", help="check a .clg scene file")
    check.add_argument("file", type=Path, help="scene file to check")
    check.add_argument("--json", action="store_true", help="print check results as JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {None, "tui"}:
        run_tui()
        return 0

    if args.command == "watch":
        return watch_file(args.file, interval=args.interval)

    if args.command == "check":
        return print_check_result(args.file, json_output=args.json)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
