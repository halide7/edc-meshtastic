# meshprov

Provision Meshtastic nodes over USB serial — EDC routers and "fam" client nodes.

This is the Python port of the original shell scripts (`setup-router.sh`,
`verify-router.sh`, `setup-fam-node.sh`, still present for reference). It talks
to the device through the official `meshtastic` Python library's structured
config API rather than scraping CLI text, so it is more reliable across firmware
versions and works the same on macOS and Windows.

## Setup

Uses [uv](https://docs.astral.sh/uv/) for the virtual environment and deps.

```bash
# Install uv (once):
#   macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
#   Windows:     powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

uv sync          # creates .venv and installs locked dependencies
```

## Secrets

Channel keys are **not** stored in the code. Copy the template and fill in keys:

```bash
cp fam-keys.env.example fam-keys.env   # then edit fam-keys.env
```

`fam-keys.env` is gitignored. Keys may be base64 or `0x`-hex. Command-line
`--fam-key` / `--ops-key` override the file.

## Usage

```bash
uv run meshprov router                       # provision EDC router (writes, reboots, verifies)
uv run meshprov verify                        # read-only spot check of the router profile
uv run meshprov fam --name "Node One"         # provision a fam client node
uv run meshprov fam -n "Backup Node" --mute   # second nearby node -> CLIENT_MUTE
uv run meshprov fam -n "Node One" -p /dev/cu.usbmodemXXXX   # target a specific port
```

All subcommands accept `-p/--port` (default: auto-detect the single connected
node). `fam` accepts `-n/--name` (required), `-s/--short`, `--mute`,
`--fam-key`, `--ops-key`.

## Profiles

- **Router**: role ROUTER, rebroadcast ALL, US / SHORT_TURBO / slot 30, hop limit 3.
- **Fam**: role CLIENT (or CLIENT_MUTE), US / SHORT_TURBO / slot 30, position OFF,
  channel 0 "Fam" (shared key) + channel 1 "EDC-MeshOps".

Every other node in the mesh must match region/preset/slot (US / SHORT_TURBO /
30) to interoperate.

## Distribution

`uv run` works anywhere uv + Python are installed. For a single-file binary that
non-technical users can run without installing Python, freeze with PyInstaller
(future work): `uvx pyinstaller --onefile ...`.
```
