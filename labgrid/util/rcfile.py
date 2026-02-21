"""Read ~/.lgrc to set default environment variables for labgrid."""

import os
from pathlib import Path


def apply_rcfile(path=None):
    """Read key=value pairs from *path* (default ``~/.lgrc``) and set them as
    environment variables, without overriding values already present in the
    environment.

    Blank lines and lines starting with ``#`` are ignored.
    """
    if path is None:
        path = Path.home() / '.lgrc'
    else:
        path = Path(path)

    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        os.environ.setdefault(key, value)
