"""Running the spm package (ml/spm) from the backend, as a separate process.

spm keeps its own environment (rasterio, geopandas, matplotlib). The backend never imports it:
it runs `python -m spm.cli ...` in that environment and reads the files spm writes. If spm
crashes, hangs or is not installed, the rest of the backend keeps working.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Where ml/spm is. Unset: the copy in this repository.
SPM_DIR_SETTING = "SPM_DIR"
DEFAULT_SPM_DIR = Path(__file__).resolve().parents[2] / "ml" / "spm"

# A prediction is a few seconds of work. One that runs this long is stuck, and is stopped.
TIMEOUT_S = 300


def spm_dir() -> Path:
    return Path(os.environ.get(SPM_DIR_SETTING) or DEFAULT_SPM_DIR).resolve()


def spm_python(root: Path) -> Path:
    """The Python of spm's own environment. Windows lays the folder out differently."""
    folder, name = ("Scripts", "python.exe") if sys.platform == "win32" else ("bin", "python")
    return root / ".venv" / folder / name


def models(root: Path) -> dict[str, list[str]]:
    """Each fitted model under root/models, by file name, with the subject categories it can
    draw. A model can draw a category only if it holds a distance ring for it; `spm predict`
    refuses the others. A file that cannot be read is left out."""
    found = {}
    for path in sorted((root / "models").glob("*.json")):
        try:
            ring = json.loads(path.read_text())["ring"]
            pooled_only = ring.get("pooled_only", False)
            categories = sorted(c for c in ring["params"] if c != "__all__")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        found[path.stem] = [] if pooled_only else categories
    return found


def unavailable_reason(root: Path) -> str | None:
    """Why spm cannot run from root, or None if it can."""
    if not spm_python(root).is_file():
        return f"no Python at {spm_python(root)} (install ml/spm with its geo and viz extras)"
    if not models(root):
        return f"no fitted model under {root / 'models'} (run `spm fit`)"
    return None


def run(root: Path, args: list[str], timeout: float | None = TIMEOUT_S, capture: bool = True):
    """Run `spm <args>` in spm's environment and wait for it. Tests replace this.

    -I keeps the backend's own environment variables and folders out of spm's imports.
    capture=False lets spm print straight to the terminal, for long downloads.
    """
    return subprocess.run(
        [str(spm_python(root)), "-I", "-W", "ignore", "-m", "spm.cli", *args],
        cwd=root,
        capture_output=capture,
        text=True,
        timeout=timeout,
        check=False,
    )


def refusal(stderr: str) -> str | None:
    """The message of a deliberate spm refusal (incomplete terrain, no ring for the category),
    or None for a crash. A refusal is one line of text; a crash prints a traceback."""
    if "Traceback (most recent call last)" in stderr:
        return None
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1][:500] if lines else None
