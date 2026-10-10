"""Write files safely."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, mode: int = 0o600, keep_backup: bool = False) -> None:
    """Write text to path in one step, with the given file mode.

    The text goes to a temporary file in the same directory first. Then the file is renamed over path,
    so a reader never sees half a file. With keep_backup, the old file is copied to <name>.bak (mode 0600)
    before the rename. The parent directory is created when it is missing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if keep_backup and path.exists():
        backup: Path = path.with_name(name=path.name + ".bak")
        backup.write_bytes(data=path.read_bytes())
        os.chmod(path=backup, mode=0o600)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    try:
        with os.fdopen(fd=fd, mode="w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(path=tmp, mode=mode)
        os.replace(src=tmp, dst=path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
