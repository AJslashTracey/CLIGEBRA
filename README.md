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
- `c1 = zyl((0,0,0), (0,0,5), 1)`
- `zyl((0,0,0), (0,0,5), 1)`
- `a = 2x + y + 2z - 8 = 0`
- `vec[0, 0, 2]`

Points use `(x, y, z)`, vectors use `vec[x, y, z]`, and cylinders use `zyl((x,y,z), (x,y,z), radius)`.

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
