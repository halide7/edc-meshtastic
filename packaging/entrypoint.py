"""PyInstaller entry point — invokes the meshprov CLI.

PyInstaller freezes a concrete script, not a console-script entry point, so this
thin wrapper calls the same main() that `meshprov` does.
"""

import sys

from meshprov.cli import main

if __name__ == "__main__":
    sys.exit(main())
