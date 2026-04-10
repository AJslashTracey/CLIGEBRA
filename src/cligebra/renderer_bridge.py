from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from cligebra.scene import ParseIssue, SceneObject


class RendererBridge:
    def __init__(self) -> None:
        self._state_file = Path(tempfile.gettempdir()) / "cligebra_scene_state.json"
        self._process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return

        self._process = subprocess.Popen(
            [sys.executable, "-m", "cligebra.renderer_window", str(self._state_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def send_scene(self, objects: list[SceneObject], issues: list[ParseIssue], status: str) -> None:
        payload = {
            "objects": [asdict(obj) for obj in objects],
            "parse_issues": [f"line {issue.line_no}: {issue.message}" for issue in issues],
            "status": status,
        }
        self._state_file.write_text(json.dumps(payload), encoding="utf-8")

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
