import os
from pathlib import Path

from src.errors import InvalidProcessSourceError


class ScriptFileResolver:
    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, relative_path: str) -> Path:
        try:
            script_path = (self._root / relative_path).resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise InvalidProcessSourceError(
                f"script file does not exist: {relative_path}"
            ) from error

        if not script_path.is_relative_to(self._root):
            raise InvalidProcessSourceError(
                "script file must remain inside the configured script root"
            )
        if not script_path.is_file():
            raise InvalidProcessSourceError(
                f"script path is not a file: {relative_path}"
            )
        has_read_bit = bool(script_path.stat().st_mode & 0o444)
        if not has_read_bit or not os.access(script_path, os.R_OK):
            raise InvalidProcessSourceError(
                f"script file is not readable: {relative_path}"
            )
        return script_path
