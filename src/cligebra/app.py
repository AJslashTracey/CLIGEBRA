from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, Static, TextArea

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
                        "Ctrl+R: focus render pane",
                        "Ctrl+E: focus editor pane",
                        "Ctrl+O: focus objects pane",
                        "Ctrl+P: focus command palette",
                        "Ctrl+S: reparse scene buffer",
                        "Ctrl+G: load sample scene",
                        "?: toggle help",
                        "",
                        "Edit the scene buffer like source code.",
                        "The sidebar reflects parsed objects.",
                    ]
                ),
                id="help-body",
            ),
            id="help-dialog",
        )

    def on_key(self) -> None:
        self.dismiss()


class RenderPane(Static):
    can_focus = True
    objects: reactive[list[SceneObject]] = reactive(list)
    issues: reactive[list[ParseIssue]] = reactive(list)

    def update_scene(self, objects: list[SceneObject], issues: list[ParseIssue]) -> None:
        self.objects = objects
        self.issues = issues
        self.update(self._build_view())

    def _build_view(self) -> str:
        lines = [
            "Render Viewport",
            "",
            "The live renderer will project scene geometry here.",
            "For now, this pane reflects the parsed scene state.",
            "",
            f"objects: {len(self.objects)}",
            f"errors: {len(self.issues)}",
            "",
        ]

        if self.objects:
            lines.append("visible objects")
            for obj in self.objects[:8]:
                lines.append(f"  {obj.kind:<8} {obj.name:<10} line {obj.line_no}")
        else:
            lines.append("No objects parsed.")

        if self.issues:
            lines.extend(["", "issues"])
            for issue in self.issues[:5]:
                lines.append(f"  line {issue.line_no}: {issue.message}")

        lines.extend(
            [
                "",
                "planned controls",
                "  h j k l / arrows  move camera",
                "  +/-               zoom",
                "  :                 command palette",
            ]
        )
        return "\n".join(lines)


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

    #sidebar {
        width: 34;
        min-width: 28;
        border-left: heavy #314154;
        background: #111922;
    }

    #render-pane {
        height: 1fr;
        border: round #4b657f;
        padding: 1 2;
        background: #0d131a;
    }

    #editor-pane {
        height: 14;
        border: round #5c7c9d;
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
        ("ctrl+r", "focus_render", "Render"),
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
                yield RenderPane(id="render-pane")
                yield TextArea.code_editor(SCENE_SAMPLE, language="python", id="editor-pane")
            with Container(id="sidebar"):
                yield ObjectsPane(id="objects-pane", classes="panel")
        with Horizontal(id="command-row"):
            yield Label("Command", id="command-label")
            yield CommandPalette(placeholder=":command palette", id="command-palette")
        yield StatusBar("Ctrl+E editor  Ctrl+R render  Ctrl+P command  ? help", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CLIGEBRA"
        self.editor.language = None
        self.sync_scene()
        self.editor.focus()

    @property
    def editor(self) -> TextArea:
        return self.query_one("#editor-pane", TextArea)

    @property
    def render_pane(self) -> RenderPane:
        return self.query_one("#render-pane", RenderPane)

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
        self.render_pane.update_scene(objects, issues)
        self.objects_pane.update_scene(objects, issues)
        if issues:
            self.status_bar.set_status(f"{len(objects)} objects, {len(issues)} issues")
        else:
            self.status_bar.set_status(f"{len(objects)} objects parsed cleanly")

    def action_sync_scene(self) -> None:
        self.sync_scene()

    def action_load_sample(self) -> None:
        self.editor.text = SCENE_SAMPLE
        self.sync_scene()
        self.status_bar.set_status("Sample scene loaded")

    def action_focus_editor(self) -> None:
        self.editor.focus()
        self.status_bar.set_status("Focus: editor")

    def action_focus_render(self) -> None:
        self.render_pane.focus()
        self.status_bar.set_status("Focus: render")

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


def run() -> None:
    CligebraApp().run()


if __name__ == "__main__":
    run()
