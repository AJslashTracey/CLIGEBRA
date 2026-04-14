# CLIGEBRA

`CLIGEBRA` is a terminal-native geometry workspace for linear algebra and 3D analytic geometry.

The current milestone focuses on the interface:

- a full-screen TUI shell
- an editable scene-definition buffer
- a live object list derived from the buffer
- a separate PyVista scene window for 3D visualization

The language reference lives in [LANGUAGE.md](https://github.com/AJslashTracey/CLIGEBRA/blob/main/LANGUAGE.md).
Check out [example.md](https://github.com/AJslashTracey/CLIGEBRA/blob/main/example.md) to see how I use it in my Math Classes
## Two Ways To Use It

There are two normal ways to work with CLIGEBRA:

1. Built-in editor  
   Start `cligebra`, `cligebra tui`, or open a file directly with `cligebra <file.clg>`. The object list and renderer update from that editor.

2. Neovim or another external editor  
   Edit a `.clg` file as a normal file and run `cligebra watch <file>` to update the renderer when the file is saved.

If you want everything in one place, use the built-in editor. If you want your usual editor workflow, use a `.clg` file with `watch`.

## Run

Open the built-in editor:

```bash
cligebra
```

Open a file directly in the built-in editor:

```bash
cligebra examples/basic.clg
```

Watch a scene file and update the renderer when it is saved:

```bash
cligebra watch examples/basic.clg
```

Check a scene file without opening the renderer:

```bash
cligebra check examples/basic.clg
```

For editor integrations, checks can also be emitted as JSON:

```bash
cligebra check examples/basic.clg --json
```

Installed entrypoint:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cligebra
```

Without installing, you can also run:

```bash
python3 main.py
python3 main.py examples/basic.clg
```

`cligebra`, `cligebra tui`, and `cligebra <file>` start the built-in editor. `cligebra watch <file>` starts the PyVista renderer for a scene file.

## Built-in Editor

Start the built-in editor with:

```bash
cligebra
```

or:

```bash
cligebra tui
```

or open a file directly:

```bash
cligebra examples/basic.clg
```

Edit the scene directly inside the app. The parsed object list updates in the sidebar and the renderer updates from the editor content.

Inside the command palette you can use:

- `save`
- `save <file>`
- `open <file>`
- `sample`
- `help`
- `quit`

## Neovim

CLIGEBRA scene files are intended to work well as normal files edited in Neovim. Use `.clg` as the main extension:

```bash
nvim examples/cylinder.clg
```

### Renderer Shortcut

The repository includes Neovim examples here:

- [editor/nvim/lua/config/autocmds.lua](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/lua/config/autocmds.lua)
- [editor/nvim/lua/plugins/cligebra.lua](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/lua/plugins/cligebra.lua)
- [editor/nvim/snippets/package.json](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/snippets/package.json)
- [editor/nvim/snippets/cligebra.json](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/snippets/cligebra.json)

With LazyVim's default leader key, `<leader>cr` means `Space c r`.

### Use it

Open a scene file:

```bash
nvim examples/cylinder.clg
```

Then press:

```text
Space c r
```

That starts this command in the background:

```bash
cligebra watch /absolute/path/to/current-file.clg
```

The PyVista renderer window opens. After that, edit the scene normally and save with:

```vim
:w
```

Every save updates the renderer.

To confirm the buffer is using the right filetype:

```vim
:set filetype?
```

Expected:

```text
filetype=cligebra
```

If `Space c r` does nothing, restart Neovim after adding the config, reopen the `.clg` file, and check `:set filetype?`.

### Autocomplete

After restarting Neovim, editing a `.clg` file will give you:

- snippet completion for CLIGEBRA constructors
- buffer completion for names already used in the file, like `p1`, `p2`, `v1`
- path completion if you want it
