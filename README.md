# meshprov

Provision Meshtastic nodes over USB serial — EDC routers and "fam" client nodes.

This is the Python port of the original shell scripts (now under `sh/` —
`setup-router.sh`, `verify-router.sh`, `setup-fam-node.sh` — kept for reference). It talks
to the device through the official `meshtastic` Python library's structured
config API rather than scraping CLI text, so it is more reliable across firmware
versions and works the same on macOS and Windows.

---

## 1. Install uv (once per machine)

`meshprov` uses [uv](https://docs.astral.sh/uv/) to manage its Python virtual
environment and dependencies.

```bash
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

The installer puts `uv` in `~/.local/bin` (macOS/Linux). **Open a new terminal**
after installing, then confirm it is on your PATH:

```bash
uv --version        # e.g. "uv 0.11.17"
```

If `uv` is "command not found", add its directory to your shell profile:

```bash
# macOS/Linux (zsh): add to ~/.zshrc, then restart the terminal
export PATH="$HOME/.local/bin:$PATH"
```

## 2. Set up the project (once per checkout)

```bash
cd /path/to/mesh        # the directory containing pyproject.toml
uv sync                 # creates .venv and installs locked dependencies
```

`uv sync` reads `uv.lock` and installs the exact dependency versions (including
`meshtastic`). You do not need to manually create or activate a virtualenv —
`uv run` (below) uses the project's `.venv` automatically.

## 3. Set up the PSK key file (once)

Channel encryption keys are **never** stored in the code or committed to git.
`meshprov` reads them from a local file named **`fam-keys.env`**.

### Where the file must live

`fam-keys.env` must be in the **project root** — the same directory as
`pyproject.toml` and `README.md` (i.e. `/path/to/mesh/fam-keys.env`).
This is true even if you install `meshprov` as a global tool (see §5): the keys
are always read from the project root, not your current directory.

### How to create it

A template is provided. Copy it and fill in your keys:

```bash
cd /path/to/mesh
cp fam-keys.env.example fam-keys.env
```

Then edit `fam-keys.env` so it looks like this:

```sh
# Fam (channel 0) key — shared/reused across ALL fam nodes so they share the channel.
FAM_PSK_DEFAULT="<your-fam-key>"
# EDC-MeshOps (channel 1) key.
OPS_PSK_DEFAULT="<your-ops-key>"
```

Key format rules:

- Each value may be **base64** (e.g. `AQIDBAUGBwgJCgsMDQ4PEA==`) **or**
  **`0x`-hex** (e.g. `0x0102030405060708090a0b0c0d0e0f10`). `meshprov` normalizes
  either form.
- A key must decode to **16 or 32 bytes** (AES-128 or AES-256). Anything else is
  rejected with a clear error.
- `FAM_PSK_DEFAULT` should be the **same on every fam node** so they all share the
  "Fam" channel. Generate it once and reuse it; do not regenerate per node.

`fam-keys.env` is listed in `.gitignore` and will not be committed. Keep a secure
backup of it somewhere outside the repo.

### Overriding keys on the command line

You can override either key per run without touching the file (handy for testing
or one-off nodes). CLI flags take precedence over `fam-keys.env`:

```bash
uv run meshprov fam -n "Node One" --ops-key <your-ops-key>
```

If a key is neither provided on the command line nor present in `fam-keys.env`,
`meshprov fam` stops with an error telling you which key is missing.

---

## 4. Running meshprov

Run all commands **from the project directory** (where `pyproject.toml` is),
prefixing with `uv run`:

```bash
uv run meshprov --help            # list commands and options
uv run meshprov verify            # read-only spot check of the connected node
uv run meshprov router            # provision the EDC router profile
uv run meshprov fam --name "Node One"          # provision a fam client node
uv run meshprov fam -n "Backup Node" --mute    # second nearby node -> CLIENT_MUTE
uv run meshprov fam -n "Node One" -p /dev/cu.usbmodemXXXX   # target a specific port
```

### Commands

| Command  | What it does                                                        |
|----------|---------------------------------------------------------------------|
| `router` | Apply the EDC router profile, wait for reboot, then verify.         |
| `verify` | Read-only check of the router profile. No writes, no reboot.        |
| `fam`    | Provision a fam client node: radio, position-off, both channels.    |

### Options

- All commands: `-p` / `--port <dev>` — serial port (e.g. `/dev/cu.usbmodemXXXX`
  on macOS, `COM5` on Windows). Default: auto-detect the single connected node.
- `fam` only:
  - `-n` / `--name <str>` — **required**, owner long name (the per-node attribute).
  - `-s` / `--short <str>` — owner short name (≤4 chars). Default: first 4
    alphanumerics of `--name`, uppercased.
  - `--mute` — provision as `CLIENT_MUTE` (for a person's **second** node carried
    near their first: it participates but does not rebroadcast).
  - `--fam-key <key>` / `--ops-key <key>` — override the channel keys (base64 or
    `0x`-hex), instead of reading them from `fam-keys.env`.

Exit codes: `0` success / match, `1` device error or verification mismatch,
`2` bad arguments or missing key.

### Running from another directory

`uv run` looks for `pyproject.toml` in the current directory. To run from
elsewhere, point at the project:

```bash
uv run --project /path/to/mesh meshprov verify
```

## 5. Optional: run without typing `uv run`

**Activate the venv** for a session:

```bash
cd /path/to/mesh
source .venv/bin/activate     # Windows: .venv\Scripts\activate
meshprov verify               # no `uv run` prefix while activated
deactivate                    # when finished
```

**Or install as a global tool** (run `meshprov` from any directory):

```bash
uv tool install --from /path/to/mesh meshprov
meshprov verify
```

Remember: even when installed globally, keys are still read from
`/path/to/mesh/fam-keys.env`. Keep that file in place, or pass keys with
`--fam-key` / `--ops-key`.

---

## Profiles

- **Router**: role ROUTER, rebroadcast ALL, US / SHORT_TURBO / slot 30, hop limit 3.
- **Fam**: role CLIENT (or CLIENT_MUTE), US / SHORT_TURBO / slot 30, position OFF,
  channel 0 "Fam" (shared key) + channel 1 "EDC-MeshOps".

Every other node in the mesh must match region/preset/slot (US / SHORT_TURBO /
30) to interoperate.

## Distribution — standalone binary

For users who should not have to install Python or uv, build a single-file
executable with PyInstaller (already configured as a dev dependency):

```bash
cd packaging
uv run pyinstaller meshprov.spec --noconfirm --distpath ../dist --workpath ../build
```

This produces `dist/meshprov` (~13 MB on macOS arm64) — a self-contained binary
that runs with no Python, no venv, and from any directory:

```bash
./dist/meshprov --help
./dist/meshprov verify
./dist/meshprov fam --name "Node One"
```

### Keys for the binary

The frozen binary looks for `fam-keys.env` in this order:

1. The current working directory.
2. The directory containing the `meshprov` executable.

So when you distribute the binary, ship a `fam-keys.env` **next to it** (or have
users keep one in their working directory). As always, `--fam-key` / `--ops-key`
override the file. **Never bundle real keys into the binary or commit them.**

### Per-platform builds

PyInstaller is not a cross-compiler: build on each target OS. Run the same
command on a Mac to get the macOS binary and on Windows (PowerShell) to get
`dist\meshprov.exe`. The GitHub Actions workflows below produce both from one
push.

## Continuous integration & releases

Two workflows live in `.github/workflows/`:

- **`ci.yml`** — on every push/PR to `main`: runs the test suite on Linux,
  macOS, and Windows, then builds + smoke-tests the binary on macOS and Windows
  and uploads each as a downloadable workflow artifact.
- **`release.yml`** — on any `v*` tag: re-runs tests, verifies the tag matches
  the `pyproject.toml` version, builds the macOS and Windows binaries, and
  publishes them to a **GitHub Release** that anyone can download.

### Cutting a release (SemVer)

Versions follow [SemVer](https://semver.org/) (`vMAJOR.MINOR.PATCH`). To release:

1. Bump `version` in `pyproject.toml` (e.g. `0.1.0` → `0.2.0`) and commit.
2. Tag and push:

   ```bash
   git tag -a v0.1.0 -m "meshprov v0.1.0"
   git push origin v0.1.0
   ```

3. The release workflow builds the binaries and attaches them to the GitHub
   Release for that tag. (The tag's version must match `pyproject.toml`, or the
   workflow fails on purpose.)

Released binaries appear under **Releases** on GitHub; CI build artifacts (for
untagged commits) appear under each workflow run's **Artifacts**.
