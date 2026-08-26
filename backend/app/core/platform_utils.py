from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def find_executable(name: str) -> str | None:
    """Find tools even when a GUI-launched app has a minimal PATH."""
    detected = shutil.which(name)
    if detected:
        return detected

    project_root = Path(__file__).resolve().parents[3]
    executable = f"{name}.exe" if platform.system() == "Windows" and not name.lower().endswith(".exe") else name
    candidates: list[Path] = [project_root / "tools" / "bin" / executable]
    if platform.system() == "Darwin":
        candidates.extend([
            Path.home() / ".homebrew" / "bin" / name,
            Path("/opt/homebrew/bin") / name,
            Path("/usr/local/bin") / name,
        ])
    elif platform.system() == "Windows":
        for key in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.getenv(key)
            if base:
                candidates.append(Path(base) / "ffmpeg" / "bin" / executable)
    else:
        candidates.extend([Path("/usr/local/bin") / name, Path("/usr/bin") / name])

    return next((str(path) for path in candidates if path.is_file()), None)


def open_path(path: Path) -> None:
    target = path.resolve()
    if platform.system() == "Darwin":
        subprocess.Popen(["open", str(target)])
    elif platform.system() == "Windows":
        os.startfile(str(target))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(target)])
