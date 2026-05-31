# PyInstaller spec for meshprov — builds a single-file CLI binary.
#
# meshtastic pulls in submodules dynamically (protobufs) and reads its version
# via importlib.metadata, and it depends on pypubsub + pyserial. We collect all
# of that explicitly so the frozen binary has everything at runtime.
#
# Build:  uv run pyinstaller packaging/meshprov.spec --noconfirm
# Output: dist/meshprov  (single executable)

from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    copy_metadata,
)

hiddenimports = []
datas = []

for pkg in ("meshtastic", "pubsub", "serial", "google.protobuf"):
    hiddenimports += collect_submodules(pkg)
    datas += collect_data_files(pkg)

# meshtastic queries its own distribution metadata at import time.
datas += copy_metadata("meshtastic")

a = Analysis(
    ["entrypoint.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "wx"],  # GUI toolkits meshtastic CLI path doesn't need
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="meshprov",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
