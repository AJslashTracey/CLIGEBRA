# CLIGEBRA

`CLIGEBRA` is a terminal-native geometry workspace for linear algebra and 3D analytic geometry.

The current milestone focuses on the interface:

- a full-screen TUI shell
- an editable scene-definition buffer
- a live object list derived from the buffer
- a separate Python scene window for 3D visualization

Current scene syntax examples:

- `point P1 = (0, 0, 0)`
- `vector V1 = [1, 2, 0]`
- `line L1 = point(0,0,0) dir(1,1,0)`
- `plane A = 2x + y + 2z - 8 = 0`

## Run

Fastest local run:

```bash
python3 main.py
```

Installed entrypoint:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cligebra
```

When the TUI starts it also launches a separate Qt window that renders the scene.
