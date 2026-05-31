# meshprov

Provision Meshtastic nodes over USB serial — EDC routers and "fam" client nodes.

It talks to the device through the official `meshtastic` Python library's
structured config API (not screen-scraping the CLI), so it's reliable across
firmware versions and works the same on Linux, macOS, and Windows.

---

## Quick start (recommended: pre-compiled binary)

Most people don't need Python or anything else installed — just grab the binary.

### 1. Download

Get the latest binary for your platform from the
[**Releases**](https://github.com/halide7/edc-meshtastic/releases) page:

| Platform        | File                         |
|-----------------|------------------------------|
| Linux (x64)     | `meshprov-linux-x64`         |
| macOS (Apple Si)| `meshprov-macos-arm64`       |
| Windows (x64)   | `meshprov-windows-x64.exe`   |

Make it runnable (Linux/macOS):

```bash
chmod +x meshprov-linux-x64        # or meshprov-macos-arm64
# optional: rename to plain `meshprov` and move onto your PATH
mv meshprov-linux-x64 meshprov
```

> **macOS Gatekeeper:** the binary is unsigned, so the first run may be blocked.
> Right-click → Open once, or run `xattr -d com.apple.quarantine ./meshprov`.

### 2. Set up channel keys (only needed for `fam`)

Channel encryption keys are never baked into the binary. Create a file named
**`fam-keys.env`** next to the binary (or in the directory you run it from):

```sh
# fam-keys.env
FAM_PSK_DEFAULT="<your-fam-key>"     # channel 0 "Fam" — same key on every fam node
OPS_PSK_DEFAULT="<your-ops-key>"     # channel 1 "EDC-MeshOps"
```

Keys may be **base64** (`AQIDBAUGBwgJCgsMDQ4PEA==`) or **`0x`-hex**
(`0x0102030405060708090a0b0c0d0e0f10`), and must decode to 16 or 32 bytes
(AES-128/256). The `router` and `verify` commands don't need this file.

> Keep `fam-keys.env` private — never commit it or bundle it into a binary.

### 3. Run

```bash
./meshprov --help                       # list commands and options
./meshprov verify                       # read-only spot check of the connected node
./meshprov router                       # provision the EDC router profile
./meshprov fam --name "Node One"         # provision a fam client node
```

(Windows: use `meshprov-windows-x64.exe` in place of `./meshprov`.)

---

## Usage

### Commands

| Command  | What it does                                                        |
|----------|---------------------------------------------------------------------|
| `router` | Apply the EDC router profile, wait for reboot, then verify.         |
| `verify` | Read-only check of the router profile. No writes, no reboot.        |
| `fam`    | Provision a fam client node: radio, position-off, both channels.    |

### Examples

```bash
./meshprov verify                               # check the connected node
./meshprov router                               # set up a router
./meshprov fam --name "Node One"                # fam node (auto short name "NODE")
./meshprov fam -n "Backup Node" --mute          # second nearby node -> CLIENT_MUTE
./meshprov fam -n "Node One" -p /dev/cu.usbmodemXXXX   # target a specific port
./meshprov fam -n "Node One" --ops-key <key>    # override a key for one run
```

### Options

- **All commands:** `-p` / `--port <dev>` — serial port (e.g.
  `/dev/cu.usbmodemXXXX` on macOS, `/dev/ttyACM0` on Linux, `COM5` on Windows).
  Default: auto-detect the single connected node.
- **`fam` only:**
  - `-n` / `--name <str>` — **required**, owner long name (the per-node attribute).
  - `-s` / `--short <str>` — owner short name (≤4 chars). Default: first 4
    alphanumerics of `--name`, uppercased.
  - `--mute` — provision as `CLIENT_MUTE` (for a person's **second** node carried
    near their first: participates but does not rebroadcast).
  - `--fam-key <key>` / `--ops-key <key>` — override the channel keys (base64 or
    `0x`-hex) instead of reading `fam-keys.env`.

Where the binary looks for `fam-keys.env`: (1) the current working directory,
then (2) the directory containing the executable. CLI `--fam-key`/`--ops-key`
always win. If a needed key is missing, `fam` stops with a clear error.

**Exit codes:** `0` success / match, `1` device error or verification mismatch,
`2` bad arguments or missing key.

### Profiles

- **Router**: role ROUTER, rebroadcast ALL, US / SHORT_TURBO / slot 30, hop limit 3.
- **Fam**: role CLIENT (or CLIENT_MUTE), US / SHORT_TURBO / slot 30, position OFF,
  channel 0 "Fam" (shared key) + channel 1 "EDC-MeshOps".

Every other node in the mesh must match region/preset/slot (US / SHORT_TURBO /
30) to interoperate.

---

## Developer workflow

You only need this section to run from source, modify the code, or cut releases.
It uses [uv](https://docs.astral.sh/uv/) for the virtual environment and deps.

### Install uv

```bash
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal, then confirm: `uv --version`. If it's "command not found",
add its install dir to your PATH (`export PATH="$HOME/.local/bin:$PATH"`).

### Set up the project

```bash
cd /path/to/mesh        # the directory containing pyproject.toml
uv sync                 # creates .venv and installs locked deps (incl. meshtastic)
```

For the `fam` command from source, put `fam-keys.env` in the project root
(copy the template): `cp fam-keys.env.example fam-keys.env`, then edit it.

### Run from source

```bash
uv run meshprov verify
uv run meshprov fam --name "Node One"
```

`uv run` uses the project's `.venv` automatically. To run from another directory,
add `--project /path/to/mesh`. To skip the `uv run` prefix, either
`source .venv/bin/activate` (Windows: `.venv\Scripts\activate`) or install it as
a tool: `uv tool install --from /path/to/mesh meshprov`.

### Run the tests

```bash
uv run pytest
```

21 hardware-independent unit tests (key parsing/resolution, name derivation,
profiles, arg parsing).

### Build a standalone binary

PyInstaller is configured as a dev dependency:

```bash
cd packaging
uv run pyinstaller meshprov.spec --noconfirm --distpath ../dist --workpath ../build
```

This produces `dist/meshprov` (or `dist\meshprov.exe`) — self-contained, runs
with no Python/venv. PyInstaller is **not** a cross-compiler: build on each
target OS (the CI workflows do this for all three platforms).

### Continuous integration & releases

Two workflows in `.github/workflows/`:

- **`ci.yml`** — on push/PR to `main`: runs tests on Linux/macOS/Windows, then
  builds + smoke-tests the binary on all three and uploads each as a workflow
  artifact.
- **`release.yml`** — on any `v*` tag: re-runs tests, verifies the tag matches
  the `pyproject.toml` version, builds the Linux/macOS/Windows binaries, and
  publishes them to a **GitHub Release**.

#### Cutting a release (SemVer)

Versions follow [SemVer](https://semver.org/) (`vMAJOR.MINOR.PATCH`):

1. Bump `version` in `pyproject.toml`, run `uv sync`, commit.
2. Tag and push:

   ```bash
   git tag -a v0.1.1 -m "meshprov v0.1.1"
   git push origin v0.1.1
   ```

3. The release workflow builds the binaries and attaches them to the Release for
   that tag. (The tag version must match `pyproject.toml` or the workflow fails.)

### Legacy shell scripts

The original Bash implementation lives under `sh/` (`setup-router.sh`,
`verify-router.sh`, `setup-fam-node.sh`), kept for reference. The Python
`meshprov` tool is the supported path.
