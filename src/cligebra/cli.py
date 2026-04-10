from __future__ import annotations

import argparse
import sys
import time
from dataclasses import asdict
from pathlib import Path

from cligebra.app import run as run_tui
from cligebra.renderer_bridge import RendererBridge
from cligebra.renderer_window import compile_payload
from cligebra.scene import ParseIssue, SceneObject, parse_scene


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
    objects, parse_issues, parse_status = load_scene_file(path)
    payload = compile_payload(
        {
            "objects": [asdict(obj) for obj in objects],
            "parse_issues": parse_issue_messages(parse_issues),
            "status": parse_status,
        }
    )
    status = compiled_scene_status(len(payload["objects"]), len(payload["issues"]))
    return objects, parse_issues, payload["issues"], status


def parse_issue_messages(issues: list[ParseIssue]) -> list[str]:
    return [f"line {issue.line_no}: {issue.message}" for issue in issues]


def print_check_result(path: Path) -> int:
    try:
        objects, parse_issues, compiled_issues, _ = read_scene(path)
    except OSError as error:
        print(f"{path}: {error}", file=sys.stderr)
        return 1

    if not parse_issues and not compiled_issues:
        print(f"{path}: ok ({len(objects)} objects)")
        return 0

    for issue in parse_issues:
        print(f"{path}:{issue.line_no}: {issue.message}", file=sys.stderr)

    parse_issue_text = set(parse_issue_messages(parse_issues))
    for issue in compiled_issues:
        if issue not in parse_issue_text:
            print(f"{path}: {issue}", file=sys.stderr)

    return 1


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
                    objects, issues, _, status = read_scene(path)
                except OSError as error:
                    print(f"{path}: {error}", file=sys.stderr)
                    time.sleep(interval)
                    continue

                bridge.send_scene(objects, issues, status)
                print(f"{path}: {status}")

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
        return print_check_result(args.file)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
