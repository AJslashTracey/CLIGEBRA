# Contributing to CLIGEBRA

Bug fixes, scene examples, documentation improvements, and editor integrations
are welcome. For a larger change, open an issue describing the intended behavior
before starting implementation.

## Local setup

Use Python 3.11 or newer, as specified in [pyproject.toml](pyproject.toml).
Fork the repository first if you do not have write access, then clone your fork.
Contributors with write access can clone the main repository:

```bash
git clone https://github.com/AJslashTracey/CLIGEBRA.git
cd CLIGEBRA
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
git switch -c describe-your-change
```

On Windows, activate the virtual environment with `.venv\Scripts\Activate.ps1`
in PowerShell instead of `source .venv/bin/activate`.

The editable installation makes changes under `src/cligebra` available to the
`cligebra` command without reinstalling the project.

## Validate a change

From the repository root, check the bundled scenes without opening a renderer:

```bash
cligebra check examples/basic.clg
cligebra check examples/cylinder.clg
cligebra check examples/basic.clg --json
```

Successful checks exit with status `0`; scene or file errors exit with status
`1`. JSON output includes `ok`, object counts, and an `issues` list. Include a
small `.clg` scene that reproduces a bug when changing parsing or geometry.

For interface or renderer changes, also run:

```bash
cligebra examples/basic.clg
cligebra watch examples/basic.clg
```

These commands need a graphical desktop for the PyVista window. In watch mode,
edit and save the scene in another editor, confirm the renderer updates, and
press `Ctrl+C` to stop the watcher.

For documentation changes, check that relative links resolve to tracked files
and that commands match the current CLI. The scene syntax is documented in
[LANGUAGE.md](LANGUAGE.md), and the editor setup is in [README.md](README.md#neovim).

## Submit a pull request

Keep a pull request focused on one change and target the `main` branch. Describe
the problem, the resulting behavior, and the checks you ran. For visual changes,
include a screenshot that shows the result.

Stage only the files you intend to change. Keep local virtual environments,
Python bytecode, package metadata, and editor settings out of your commit.
The current `.gitignore` excludes `/examples`, so adding a new example may
require `git add -f examples/your-scene.clg`; check the file before forcing it
into the index.

For bug reports, include your operating system, Python version, the command you
ran, the smallest relevant scene, and the complete error message.
