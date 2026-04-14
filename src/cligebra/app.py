from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
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
                        "Ctrl+S: sync scene",
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
                yield TextArea.code_editor(SCENE_SAMPLE, language="python", id="editor-pane")
            with Container(id="sidebar"):
                yield ObjectsPane(id="objects-pane")
        with Horizontal(id="command-row"):
            yield Label("Command", id="command-label")
            yield CommandPalette(placeholder="command palette", id="command-palette")
        yield StatusBar("Ctrl+E editor  Ctrl+R renderer  Ctrl+P command  ? help", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CLIGEBRA"
        self.renderer_bridge = RendererBridge()
        self.renderer_bridge.start()
        self.editor.language = None
        self.sync_scene()
        self.editor.focus()

    @property
    def editor(self) -> TextArea:
        return self.query_one("#editor-pane", TextArea)

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
            self.status_bar.set_status(f"Editor  {len(objects)} objects, {len(issues)} issues")
        else:
            self.status_bar.set_status(f"Editor  {len(objects)} objects parsed cleanly")

    def set_transient_status(self, message: str) -> None:
        self.status_bar.set_status(message)

    def focus_command_with_prefix(self, prefix: str) -> None:
        self.command_palette.value = prefix
        self.command_palette.focus()
        self.status_bar.set_status("Command palette")

    def action_sync_scene(self) -> None:
        self.sync_scene()

    def action_load_sample(self) -> None:
        self.editor.text = SCENE_SAMPLE
        self.sync_scene()
        self.status_bar.set_status("Sample scene loaded")

    def action_focus_editor(self) -> None:
        self.editor.focus()
        self.status_bar.set_status("Focus: editor")

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

        if value in {"quit", "exit"}:
            self.renderer_bridge.close()
            self.exit()
            return

        if value in {"parse", "render"}:
            self.sync_scene()
            self.command_palette.value = ""
            return

        if value == "help":
            self.command_palette.value = ""
            self.action_toggle_help()
            return

        if value == "sample":
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
