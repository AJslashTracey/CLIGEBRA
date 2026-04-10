from __future__ import annotations

from typing import Literal

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Key
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, Static, TextArea

from cligebra.renderer_bridge import RendererBridge
from cligebra.scene import ParseIssue, SCENE_SAMPLE, SceneObject, parse_scene


class HelpScreen(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                "\n".join(
                    [
                        "CLIGEBRA Interface",
                        "",
                        "Tab / Shift+Tab: move focus",
                        "Ctrl+E: focus editor pane",
                        "Ctrl+R: focus renderer info pane",
                        "Ctrl+O: focus objects pane",
                        "Ctrl+P: focus command palette",
                        "Ctrl+S: reparse scene buffer",
                        "Ctrl+G: load sample scene",
                        "?: toggle help",
                        "",
                        "Edit the scene buffer in the terminal.",
                        "The 3D scene opens in a separate Qt window.",
                        "Use that window for orbit/zoom controls.",
                    ]
                ),
                id="help-body",
            ),
            id="help-dialog",
        )

    def on_key(self) -> None:
        self.dismiss()


class RendererPane(Static):
    can_focus = True

    def set_renderer_status(self, *, connected: bool, objects: int, issues: int) -> None:
        state = "connected" if connected else "starting"
        self.update(
            "\n".join(
                [
                    "External Scene Window",
                    "",
                    f"renderer: {state}",
                    f"objects: {objects}",
                    f"issues: {issues}",
                    "",
                    "The 3D viewport is no longer drawn in the terminal.",
                    "A separate Python window shows the coordinate system",
                    "and scene objects in 3D.",
                    "",
                    "scene window controls",
                    "  arrows    rotate camera",
                    "  +/-       zoom",
                ]
            )
        )


class ObjectsPane(Static):
    can_focus = True

    def update_scene(self, objects: list[SceneObject], issues: list[ParseIssue]) -> None:
        lines = ["Objects", ""]
        if objects:
            for obj in objects:
                lines.append(f"{obj.name}")
                lines.append(f"  {obj.kind}  line {obj.line_no}")
                lines.append(f"  {obj.expression}")
                lines.append("")
        else:
            lines.append("No parsed objects.")
            lines.append("")

        if issues:
            lines.append("Issues")
            lines.append("")
            for issue in issues:
                lines.append(f"line {issue.line_no}: {issue.message}")

        self.update("\n".join(lines).rstrip())


class StatusBar(Static):
    def set_status(self, message: str) -> None:
        self.update(message)


class CommandPalette(Input):
    pass


class VimTextArea(TextArea):
    mode: reactive[Literal["NORMAL", "INSERT"]] = reactive("NORMAL")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pending_operator: str | None = None
        self._register = ""
        self._register_linewise = False

    def watch_mode(self, mode: str) -> None:
        try:
            app = self.app
        except Exception:
            return
        if app is not None and hasattr(app, "set_editor_mode"):
            app.set_editor_mode(mode)

    def enter_normal_mode(self) -> None:
        self.mode = "NORMAL"
        self._pending_operator = None

    def enter_insert_mode(self) -> None:
        self.mode = "INSERT"
        self._pending_operator = None

    def on_focus(self) -> None:
        self.watch_mode(self.mode)

    def on_key(self, event: Key) -> None:
        if self.mode == "INSERT":
            if event.key == "escape":
                self.enter_normal_mode()
                event.stop()
                event.prevent_default()
            return

        handled = self._handle_normal_mode_key(event)
        if handled:
            event.stop()
            event.prevent_default()

    def _handle_normal_mode_key(self, event: Key) -> bool:
        key = event.key
        character = event.character

        if key == "escape":
            self._pending_operator = None
            self._set_status("NORMAL")
            return True

        if self._pending_operator is not None:
            operator = self._pending_operator
            self._pending_operator = None
            if operator == key == "d":
                self._delete_current_line()
                return True
            if operator == key == "y":
                self._yank_current_line()
                return True
            self._set_status(f"NORMAL  cancelled {operator}")
            return True

        if key == "i":
            self.enter_insert_mode()
            return True
        if key == "a":
            self.action_cursor_right()
            self.enter_insert_mode()
            return True
        if key == "h":
            self.action_cursor_left()
            return True
        if key == "j":
            self.action_cursor_down()
            return True
        if key == "k":
            self.action_cursor_up()
            return True
        if key == "l":
            self.action_cursor_right()
            return True
        if key == "0":
            self.action_cursor_line_start()
            return True
        if key == "$":
            self.action_cursor_line_end()
            return True
        if key == "w":
            self.move_cursor(self.get_cursor_word_right_location())
            return True
        if key == "b":
            self.move_cursor(self.get_cursor_word_left_location())
            return True
        if key == "x":
            self._delete_under_cursor()
            return True
        if key in {"d", "y"}:
            self._pending_operator = key
            self._set_status(f"NORMAL  {key}")
            return True
        if key == "p":
            self._put_register()
            return True
        if key == ":" or character == ":":
            try:
                app = self.app
            except Exception:
                return True
            if app is not None and hasattr(app, "focus_command_with_prefix"):
                app.focus_command_with_prefix(":")
            return True

        return True

    def _current_lines(self) -> list[str]:
        return self.text.split("\n")

    def _delete_under_cursor(self) -> None:
        row, column = self.cursor_location
        lines = self._current_lines()
        line = lines[row]

        if column < len(line):
            deleted = line[column]
            self._register = deleted
            self._register_linewise = False
            self.delete((row, column), (row, column + 1))
            self.move_cursor((row, column))
            return

        if row < len(lines) - 1:
            self._register = "\n"
            self._register_linewise = False
            self.delete((row, column), (row + 1, 0))
            self.move_cursor((row, column))

    def _delete_current_line(self) -> None:
        row, _ = self.cursor_location
        lines = self._current_lines()
        line = lines[row]

        self._register = line + ("\n" if row < len(lines) - 1 else "")
        self._register_linewise = True

        if len(lines) == 1:
            self.load_text("")
            self.move_cursor((0, 0))
        else:
            end = (row + 1, 0) if row < len(lines) - 1 else (row, len(line))
            self.delete((row, 0), end)
            new_row = min(row, len(self._current_lines()) - 1)
            self.move_cursor((new_row, 0))

        self._set_status("NORMAL  deleted line")

    def _yank_current_line(self) -> None:
        row, _ = self.cursor_location
        lines = self._current_lines()
        line = lines[row]
        self._register = line + ("\n" if row < len(lines) - 1 else "")
        self._register_linewise = True
        self._set_status("NORMAL  yanked line")

    def _put_register(self) -> None:
        if not self._register:
            return

        row, column = self.cursor_location
        lines = self._current_lines()

        if self._register_linewise:
            insert_line = self._register.rstrip("\n")
            if row < len(lines) - 1:
                self.insert(insert_line + "\n", (row + 1, 0))
                self.move_cursor((row + 1, 0))
            else:
                suffix = ("\n" if self.text else "") + insert_line
                self.insert(suffix, (row, len(lines[row])))
                target_row = row + 1 if self.text else 0
                self.move_cursor((target_row, 0))
            self._set_status("NORMAL  put line")
            return

        insert_at = (row, min(column + 1, len(lines[row])))
        self.insert(self._register, insert_at)
        self.move_cursor(insert_at)
        self._set_status("NORMAL  put")

    def _set_status(self, message: str) -> None:
        try:
            app = self.app
        except Exception:
            return
        if app is not None and hasattr(app, "set_transient_status"):
            app.set_transient_status(message)


class CligebraApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #10151c;
        color: #d7e0ea;
    }

    Header {
        background: #18212b;
        color: #f5f7fa;
    }

    Footer {
        background: #18212b;
        color: #9fb2c7;
    }

    #workspace {
        height: 1fr;
    }

    #center-column {
        width: 1fr;
        height: 1fr;
    }

    #renderer-pane {
        height: 9;
        border: round #4b657f;
        padding: 1 2;
        background: #0d131a;
    }

    #editor-pane {
        height: 1fr;
        border: round #5c7c9d;
        background: #111922;
    }

    #sidebar {
        width: 34;
        min-width: 28;
        border-left: heavy #314154;
        background: #111922;
    }

    #objects-pane {
        height: 1fr;
        padding: 1;
    }

    #command-row {
        height: 3;
    }

    #command-label {
        width: 16;
        content-align: center middle;
        color: #8fb4d8;
    }

    #command-palette {
        width: 1fr;
    }

    #status-bar {
        height: 1;
        padding: 0 1;
        color: #9fb2c7;
        background: #18212b;
    }

    #help-dialog {
        width: 72;
        height: 18;
        border: double #88a8c8;
        background: #10151c;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("ctrl+e", "focus_editor", "Editor"),
        ("ctrl+r", "focus_renderer", "Renderer"),
        ("ctrl+o", "focus_objects", "Objects"),
        ("ctrl+p", "focus_command", "Command"),
        ("ctrl+s", "sync_scene", "Parse"),
        ("ctrl+g", "load_sample", "Sample"),
        ("question_mark", "toggle_help", "Help"),
    ]

    SUB_TITLE = "Geometry Workspace"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace"):
            with Vertical(id="center-column"):
                yield RendererPane(id="renderer-pane")
                yield VimTextArea.code_editor(SCENE_SAMPLE, language="python", id="editor-pane")
            with Container(id="sidebar"):
                yield ObjectsPane(id="objects-pane")
        with Horizontal(id="command-row"):
            yield Label("Command", id="command-label")
            yield CommandPalette(placeholder=":command palette", id="command-palette")
        yield StatusBar("Ctrl+E editor  Ctrl+R renderer  Ctrl+P command  ? help", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CLIGEBRA"
        self.renderer_bridge = RendererBridge()
        self.renderer_bridge.start()
        self.editor.language = None
        self.editor.enter_normal_mode()
        self.sync_scene()
        self.editor.focus()

    @property
    def editor(self) -> VimTextArea:
        return self.query_one("#editor-pane", VimTextArea)

    @property
    def renderer_pane(self) -> RendererPane:
        return self.query_one("#renderer-pane", RendererPane)

    @property
    def objects_pane(self) -> ObjectsPane:
        return self.query_one("#objects-pane", ObjectsPane)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one("#status-bar", StatusBar)

    @property
    def command_palette(self) -> CommandPalette:
        return self.query_one("#command-palette", CommandPalette)

    def sync_scene(self) -> None:
        objects, issues = parse_scene(self.editor.text)
        self.objects_pane.update_scene(objects, issues)
        self.renderer_pane.set_renderer_status(
            connected=True,
            objects=len(objects),
            issues=len(issues),
        )
        status = (
            f"{len(objects)} objects parsed cleanly"
            if not issues
            else f"{len(objects)} objects, {len(issues)} issues"
        )
        self.renderer_bridge.send_scene(objects, issues, status)
        if issues:
            self.status_bar.set_status(f"{self.editor.mode}  {len(objects)} objects, {len(issues)} issues")
        else:
            self.status_bar.set_status(f"{self.editor.mode}  {len(objects)} objects parsed cleanly")

    def set_editor_mode(self, mode: str) -> None:
        objects, issues = parse_scene(self.editor.text)
        if issues:
            self.status_bar.set_status(f"{mode}  {len(objects)} objects, {len(issues)} issues")
        else:
            self.status_bar.set_status(f"{mode}  {len(objects)} objects parsed cleanly")

    def set_transient_status(self, message: str) -> None:
        self.status_bar.set_status(message)

    def focus_command_with_prefix(self, prefix: str) -> None:
        self.command_palette.value = prefix
        self.command_palette.focus()
        self.status_bar.set_status(f"{self.editor.mode}  command palette")

    def action_sync_scene(self) -> None:
        self.sync_scene()

    def action_load_sample(self) -> None:
        self.editor.text = SCENE_SAMPLE
        self.sync_scene()
        self.status_bar.set_status(f"{self.editor.mode}  sample scene loaded")

    def action_focus_editor(self) -> None:
        self.editor.focus()
        self.status_bar.set_status(f"{self.editor.mode}  focus: editor")

    def action_focus_renderer(self) -> None:
        self.renderer_pane.focus()
        self.status_bar.set_status("Focus: renderer info  scene window is external")

    def action_focus_objects(self) -> None:
        self.objects_pane.focus()
        self.status_bar.set_status("Focus: objects")

    def action_focus_command(self) -> None:
        self.command_palette.focus()
        self.status_bar.set_status("Focus: command palette")

    def action_toggle_help(self) -> None:
        self.push_screen(HelpScreen())

    def on_text_area_changed(self, _: TextArea.Changed) -> None:
        self.sync_scene()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input is not self.command_palette:
            return

        value = event.value.strip()
        if not value:
            return

        if value in {":q", "quit", "exit"}:
            self.renderer_bridge.close()
            self.exit()
            return

        if value in {":w", "parse", "render"}:
            self.sync_scene()
            self.command_palette.value = ""
            return

        if value in {":help", "help"}:
            self.command_palette.value = ""
            self.action_toggle_help()
            return

        if value in {":sample", "sample"}:
            self.command_palette.value = ""
            self.action_load_sample()
            return

        self.status_bar.set_status(f"Unknown command: {value}")
        self.command_palette.value = ""

    def on_unmount(self) -> None:
        if hasattr(self, "renderer_bridge"):
            self.renderer_bridge.close()


def run() -> None:
    CligebraApp().run()


if __name__ == "__main__":
    run()
