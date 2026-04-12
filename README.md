# CLIGEBRA

`CLIGEBRA` is a terminal-native geometry workspace for linear algebra and 3D analytic geometry.

The current milestone focuses on the interface:

- a full-screen TUI shell
- an editable scene-definition buffer
- a live object list derived from the buffer
- a separate PyVista scene window for 3D visualization

Current scene syntax examples:

- `point P1 = (0, 0, 0)`
- `p1 = (0, 0, 0)`
- `v1 = vec[1, 2, 0]`
- `l1 = line(point(0,0,0), dir(1,1,0))`
- `c1 = cyl((0,0,0), (0,0,5), 1)`
- `cyl((0,0,0), (0,0,5), 1)`
- `a = 2x + y + 2z - 8 = 0`
- `vec[0, 0, 2]`

Points use `(x, y, z)`, vectors use `vec[x, y, z]`, and cylinders use `cyl((x,y,z), (x,y,z), radius)`.

## Run

Fastest local run:

```bash
python3 main.py
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

`cligebra` and `cligebra tui` start the TUI. `cligebra watch <file>` starts the PyVista renderer for a scene file.

## Neovim

CLIGEBRA scene files are intended to work well as normal files edited in Neovim. Use `.clg` as the main extension:

```bash
nvim examples/cylinder.clg
```

### Add the renderer shortcut

Put the following Lua in your Neovim config. For a LazyVim-style config, a good place is:

```text
~/.config/nvim/lua/config/autocmds.lua
```

This does two things:

- detects `.clg` and `.cligebra` files as `cligebra`
- adds a buffer-local `<leader>cr` shortcut that starts `cligebra watch` for the current file

```lua
vim.filetype.add({
  extension = {
    clg = "cligebra",
    cligebra = "cligebra",
  },
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = "cligebra",
  callback = function(event)
    vim.keymap.set("n", "<leader>cr", function()
      local file = vim.api.nvim_buf_get_name(0)

      if file == "" then
        vim.notify("Save this CLIGEBRA buffer before starting the renderer", vim.log.levels.WARN)
        return
      end

      if vim.bo.modified then
        vim.cmd.write()
      end

      vim.fn.jobstart({ "cligebra", "watch", file }, {
        detach = true,
      })

      vim.notify("Started CLIGEBRA renderer for " .. vim.fn.fnamemodify(file, ":t"))
    end, { buffer = event.buf, desc = "Start CLIGEBRA renderer" })
  end,
})
```

With LazyVim's default leader key, `<leader>cr` means:

```text
Space c r
```

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

### Add autocomplete

CLIGEBRA autocomplete works nicely with LazyVim's default `blink.cmp` setup. The simplest version is:

- keep the `cligebra` filetype from the section above
- add a small `blink.cmp` filetype override
- add CLIGEBRA snippets under `~/.config/nvim/snippets`

Create this file:

```text
~/.config/nvim/lua/plugins/cligebra.lua
```

```lua
return {
  {
    "saghen/blink.cmp",
    opts = {
      sources = {
        per_filetype = {
          cligebra = { "snippets", "buffer", "path" },
        },
      },
    },
  },
}
```

Then create this folder:

```text
~/.config/nvim/snippets
```

with this package file:

```json
{
  "name": "cligebra-snippets",
  "contributes": {
    "snippets": [
      {
        "language": "cligebra",
        "path": "./cligebra.json"
      }
    ]
  }
}
```

and this snippet file:

```json
{
  "point": {
    "prefix": "point",
    "body": "${1:p1} = (${2:0}, ${3:0}, ${4:0})",
    "description": "Point definition"
  },
  "vector": {
    "prefix": "vec",
    "body": "${1:v1} = vec[${2:1}, ${3:0}, ${4:0}]",
    "description": "Vector definition"
  },
  "line through two points": {
    "prefix": "line",
    "body": "${1:l1} = line(${2:p1}, ${3:p2})",
    "description": "Line through two points"
  },
  "line through point and vector": {
    "prefix": "linepv",
    "body": "${1:l1} = line(${2:p1}, ${3:v1})",
    "description": "Line through point and vector"
  },
  "plane point normal": {
    "prefix": "plane",
    "body": "${1:E1} = plane(${2:p1}, ${3:vec[0, 0, 1]})",
    "description": "Plane through a point with a normal"
  },
  "plane through three points": {
    "prefix": "plane3",
    "body": "${1:E1} = plane(${2:p1}, ${3:p2}, ${4:p3})",
    "description": "Plane through three points"
  },
  "plane with two vectors": {
    "prefix": "planevv",
    "body": "${1:E1} = plane(${2:p1}, ${3:v1}, ${4:v2})",
    "description": "Plane through a point spanned by two vectors"
  },
  "cylinder": {
    "prefix": "cyl",
    "body": "${1:c1} = cyl(${2:p1}, ${3:p2}, ${4:1})",
    "description": "Cylinder from two points and a radius"
  }
}
```

After restarting Neovim, editing a `.clg` file will give you:

- snippet completion for CLIGEBRA constructors
- buffer completion for names already used in the file, like `p1`, `p2`, `v1`
- path completion if you want it

The repository also includes the same example files here:

- [editor/nvim/lua/plugins/cligebra.lua](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/lua/plugins/cligebra.lua)
- [editor/nvim/snippets/package.json](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/snippets/package.json)
- [editor/nvim/snippets/cligebra.json](/Users/aj/Desktop/GitHub/CLIGEBRA/editor/nvim/snippets/cligebra.json)
