from __future__ import annotations

from dataclasses import dataclass
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
                        "The 3D scene opens in a separate PyVista window.",
                        "Use that window for mouse orbit, pan, and zoom.",
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
                    ""
                   
                ]
            )
        )


class ObjectsPane(Static):
    can_focus = True

    def update_scene(self, objects: list[SceneObject], issues: list[ParseIssue]) -> None:
        lines = ["Objects", ""]
        if objects:
            for obj in objects:
                title = obj.name if not obj.anonymous else f"{obj.name} anonymous"
                lines.append(title)
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


@dataclass(frozen=True)
class VimMotion:
    start: tuple[int, int]
    end: tuple[int, int]
    linewise: bool = False
    inclusive: bool = False


class VimTextArea(TextArea):
    mode: reactive[Literal["NORMAL", "INSERT"]] = reactive("NORMAL")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pending_operator: str | None = None
        self._pending_count = 1
        self._count_prefix = ""
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
        self._clear_pending()
        row, column = self.cursor_location
        if column > 0:
            self.move_cursor((row, column - 1))

    def enter_insert_mode(self) -> None:
        self.mode = "INSERT"
        self._clear_pending()

    def on_focus(self) -> None:
        self.watch_mode(self.mode)

    def on_key(self, event: Key) -> None:
        if self.mode == "INSERT":
            if event.key == "escape":
                self.enter_normal_mode()
                event.stop()
                event.prevent_default()
                return
            if self._handle_insert_mode_key(event):
                event.stop()
                event.prevent_default()
            return

        handled = self._handle_normal_mode_key(event)
        if handled:
            event.stop()
            event.prevent_default()

    def _handle_insert_mode_key(self, event: Key) -> bool:
        pairs = {
            "(": ")",
            "[": "]",
            "{": "}",
            '"': '"',
            "'": "'",
        }
        closers = {")", "]", "}", '"', "'"}
        character = event.character

        if character in pairs:
            row, column = self.cursor_location
            self.insert(character + pairs[character], (row, column))
            self.move_cursor((row, column + 1))
            return True

        if character in closers:
            row, column = self.cursor_location
            lines = self._current_lines()
            if row < len(lines) and column < len(lines[row]) and lines[row][column] == character:
                self.move_cursor((row, column + 1))
                return True

        return False

    def _handle_normal_mode_key(self, event: Key) -> bool:
        key = event.key
        character = event.character
        token = character or key

        if key == "escape":
            self._reset_command("NORMAL")
            return True

        if token.isdigit() and (token != "0" or self._count_prefix or self._pending_operator is not None):
            self._count_prefix += token
            self._set_status(self._command_status())
            return True

        if self._pending_operator is not None:
            operator = self._pending_operator
            operator_count = self._pending_count
            motion_count = self._consume_count()
            count = operator_count * motion_count

            if operator == token:
                self._apply_line_operator(operator, count)
                self._clear_pending()
                return True

            motion = self._motion_for_key(token, count=count, operator_pending=True)
            if motion is not None:
                self._apply_operator(operator, motion)
                self._clear_pending()
                return True

            self._reset_command(f"NORMAL  cancelled {operator}")
            return True

        if token == "u":
            self.action_undo()
            self._reset_command("NORMAL  undo")
            return True
        if key == "ctrl+r":
            self.action_redo()
            self._reset_command("NORMAL  redo")
            return True

        if token in {"d", "y", "c"}:
            self._pending_operator = token
            self._pending_count = self._consume_count()
            self._set_status(self._command_status())
            return True

        count = self._consume_count()

        if token == "i":
            self.enter_insert_mode()
            return True
        if token == "a":
            row, column = self.cursor_location
            line = self._current_lines()[row]
            if column < len(line):
                self.move_cursor((row, column + 1))
            self.enter_insert_mode()
            return True
        if token == "I":
            self.move_cursor(self._first_non_blank(self.cursor_location[0]))
            self.enter_insert_mode()
            return True
        if token == "A":
            self.move_cursor(self._line_end(self.cursor_location[0]))
            self.enter_insert_mode()
            return True
        if token == "o":
            row, _ = self.cursor_location
            self.insert("\n", self._line_end(row))
            self.move_cursor((row + 1, 0))
            self.enter_insert_mode()
            return True
        if token == "O":
            row, _ = self.cursor_location
            self.insert("\n", (row, 0))
            self.move_cursor((row, 0))
            self.enter_insert_mode()
            return True

        if token == "x":
            self._delete_under_cursor(count)
            return True
        if token == "p":
            self._put_register(after=True, count=count)
            return True
        if token == "P":
            self._put_register(after=False, count=count)
            return True

        motion = self._motion_for_key(token, count=count, operator_pending=False)
        if motion is not None:
            self.move_cursor(motion.end)
            return True

        if key == ":" or character == ":":
            self._clear_pending()
            try:
                app = self.app
            except Exception:
                return True
            if app is not None and hasattr(app, "focus_command_with_prefix"):
                app.focus_command_with_prefix(":")
            return True

        return True

    def _consume_count(self) -> int:
        if not self._count_prefix:
            return 1
        count = max(1, int(self._count_prefix))
        self._count_prefix = ""
        return count

    def _clear_pending(self) -> None:
        self._pending_operator = None
        self._pending_count = 1
        self._count_prefix = ""

    def _reset_command(self, status: str | None = None) -> None:
        self._clear_pending()
        if status is not None:
            self._set_status(status)

    def _command_status(self) -> str:
        if self._pending_operator is None:
            return f"NORMAL  {self._count_prefix}" if self._count_prefix else "NORMAL"
        prefix = "" if self._pending_count == 1 else str(self._pending_count)
        return f"NORMAL  {prefix}{self._pending_operator}{self._count_prefix}"

    def _motion_for_key(self, key: str, *, count: int, operator_pending: bool) -> VimMotion | None:
        start = self.cursor_location
        if key == "h":
            return VimMotion(start, self._left(start, count))
        if key == "l":
            return VimMotion(start, self._right(start, count))
        if key == "j":
            return VimMotion(start, self._vertical(start, count), linewise=operator_pending)
        if key == "k":
            return VimMotion(start, self._vertical(start, -count), linewise=operator_pending)
        if key == "0":
            return VimMotion(start, (start[0], 0))
        if key == "^":
            return VimMotion(start, self._first_non_blank(start[0]))
        if key == "$":
            return VimMotion(start, self._line_end(start[0]))
        if key == "w":
            return VimMotion(start, self._word_right(start, count))
        if key == "b":
            return VimMotion(start, self._word_left(start, count))
        if key == "e":
            return VimMotion(start, self._word_end(start, count), inclusive=operator_pending)
        return None

    def _current_lines(self) -> list[str]:
        return self.text.split("\n")

    def _apply_line_operator(self, operator: str, count: int) -> None:
        row, _ = self.cursor_location
        end_row = min(row + count - 1, len(self._current_lines()) - 1)
        motion = VimMotion((row, 0), (end_row, 0), linewise=True)
        self._apply_operator(operator, motion)

    def _apply_operator(self, operator: str, motion: VimMotion) -> None:
        if motion.linewise:
            start, end = self._linewise_span(motion.start[0], motion.end[0])
            linewise = True
        else:
            start, end = self._ordered_span(motion.start, motion.end)
            if start == end:
                return
            if motion.inclusive:
                end = self._right(end, 1)
            linewise = False

        text = self._slice_text(start, end)
        if operator == "y":
            self._register = text
            self._register_linewise = linewise
            self.move_cursor(start)
            self._set_status("NORMAL  yanked")
            return

        self._register = text
        self._register_linewise = linewise
        self.delete(start, end)
        self.move_cursor(self._clamp_location(start))
        if operator == "c":
            self.enter_insert_mode()
            self._set_status("INSERT  changed")
        else:
            self._set_status("NORMAL  deleted")

    def _clamp_location(self, location: tuple[int, int]) -> tuple[int, int]:
        lines = self._current_lines()
        row = min(max(0, location[0]), len(lines) - 1)
        column = min(max(0, location[1]), len(lines[row]))
        return row, column

    def _left(self, location: tuple[int, int], count: int) -> tuple[int, int]:
        row, column = location
        for _ in range(count):
            if column > 0:
                column -= 1
            elif row > 0:
                row -= 1
                column = len(self._current_lines()[row])
        return row, column

    def _right(self, location: tuple[int, int], count: int) -> tuple[int, int]:
        row, column = location
        lines = self._current_lines()
        for _ in range(count):
            if column < len(lines[row]):
                column += 1
            elif row < len(lines) - 1:
                row += 1
                column = 0
        return row, column

    def _vertical(self, location: tuple[int, int], delta: int) -> tuple[int, int]:
        lines = self._current_lines()
        row, column = location
        row = min(max(0, row + delta), len(lines) - 1)
        return row, min(column, len(lines[row]))

    def _line_end(self, row: int) -> tuple[int, int]:
        return row, len(self._current_lines()[row])

    def _first_non_blank(self, row: int) -> tuple[int, int]:
        line = self._current_lines()[row]
        return row, len(line) - len(line.lstrip())

    def _word_right(self, location: tuple[int, int], count: int) -> tuple[int, int]:
        index = self._index_from_location(location)
        for _ in range(count):
            index = self._next_word_start(index)
        return self._location_from_index(index)

    def _word_left(self, location: tuple[int, int], count: int) -> tuple[int, int]:
        index = self._index_from_location(location)
        for _ in range(count):
            index = self._previous_word_start(index)
        return self._location_from_index(index)

    def _word_end(self, location: tuple[int, int], count: int) -> tuple[int, int]:
        index = self._index_from_location(location)
        for _ in range(count):
            index = self._next_word_end(index)
        return self._location_from_index(index)

    def _index_from_location(self, location: tuple[int, int]) -> int:
        lines = self._current_lines()
        row, column = self._clamp_location(location)
        return sum(len(line) + 1 for line in lines[:row]) + column

    def _location_from_index(self, index: int) -> tuple[int, int]:
        lines = self._current_lines()
        index = min(max(0, index), len(self.text))
        offset = 0
        for row, line in enumerate(lines):
            line_end = offset + len(line)
            if index <= line_end:
                return row, index - offset
            offset = line_end + 1
        return len(lines) - 1, len(lines[-1])

    def _word_kind(self, character: str) -> str:
        if character.isspace():
            return "space"
        if character.isalnum() or character == "_":
            return "word"
        return "punct"

    def _next_word_start(self, index: int) -> int:
        text = self.text
        if index >= len(text):
            return len(text)

        if not text[index].isspace():
            kind = self._word_kind(text[index])
            while index < len(text) and self._word_kind(text[index]) == kind:
                index += 1

        while index < len(text) and text[index].isspace():
            index += 1
        return index

    def _previous_word_start(self, index: int) -> int:
        text = self.text
        if index <= 0:
            return 0

        index -= 1
        while index > 0 and text[index].isspace():
            index -= 1

        kind = self._word_kind(text[index])
        while index > 0 and self._word_kind(text[index - 1]) == kind:
            index -= 1
        return index

    def _next_word_end(self, index: int) -> int:
        text = self.text
        if index >= len(text):
            return len(text)

        if not text[index].isspace():
            kind = self._word_kind(text[index])
            if index + 1 < len(text) and self._word_kind(text[index + 1]) == kind:
                index += 1

        while index < len(text) and text[index].isspace():
            index += 1

        if index >= len(text):
            return len(text)

        kind = self._word_kind(text[index])
        while index + 1 < len(text) and self._word_kind(text[index + 1]) == kind:
            index += 1
        return index

    def _ordered_span(self, start: tuple[int, int], end: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
        return (start, end) if start <= end else (end, start)

    def _linewise_span(self, first_row: int, second_row: int) -> tuple[tuple[int, int], tuple[int, int]]:
        lines = self._current_lines()
        start_row, end_row = sorted((first_row, second_row))
        if end_row < len(lines) - 1:
            return (start_row, 0), (end_row + 1, 0)
        return (start_row, 0), (end_row, len(lines[end_row]))

    def _slice_text(self, start: tuple[int, int], end: tuple[int, int]) -> str:
        lines = self._current_lines()
        start_row, start_column = start
        end_row, end_column = end

        if start_row == end_row:
            return lines[start_row][start_column:end_column]

        chunks = [lines[start_row][start_column:]]
        chunks.extend(lines[start_row + 1 : end_row])
        chunks.append(lines[end_row][:end_column])
        return "\n".join(chunks)

    def _delete_under_cursor(self, count: int = 1) -> None:
        row, column = self.cursor_location
        end = self._right((row, column), count)
        if end == (row, column):
            return
        self._apply_operator("d", VimMotion((row, column), end))

    def _put_register(self, *, after: bool, count: int = 1) -> None:
        if not self._register:
            return

        row, column = self.cursor_location
        lines = self._current_lines()
        line = lines[row]
        text = self._register * count

        if self._register_linewise:
            if after:
                if row < len(lines) - 1:
                    insert_at = (row + 1, 0)
                    insert_text = text if text.endswith("\n") else text + "\n"
                else:
                    insert_at = (row, len(line))
                    insert_text = ("\n" if self.text else "") + text.rstrip("\n")
            else:
                insert_at = (row, 0)
                insert_text = text if text.endswith("\n") else text + "\n"
            self.insert(insert_text, insert_at)
            self.move_cursor((min(insert_at[0], len(self._current_lines()) - 1), 0))
            self._set_status("NORMAL  put line")
            return

        insert_at = (row, min(column + (1 if after else 0), len(line)))
        self.insert(text, insert_at)
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
        color: #d7e0ea;
    }

    Header {
        color: #f5f7fa;
    }

    Footer {
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
    }

    #editor-pane {
        height: 1fr;
        border: round #5c7c9d;
    }

    #sidebar {
        width: 34;
        min-width: 28;
        border-left: heavy #314154;
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
    }

    #help-dialog {
        width: 72;
        height: 18;
        border: double #88a8c8;
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
