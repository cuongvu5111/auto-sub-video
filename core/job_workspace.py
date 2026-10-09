"""Create and safely clean isolated temporary directories for pipeline jobs."""

import shutil
import tempfile
from pathlib import Path

from config import Config


def create_job_workspace() -> Path:
    jobs_root = (Config.TEMP_DIR / "jobs").resolve()
    jobs_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="job_", dir=str(jobs_root))).resolve()


def cleanup_job_workspace(workspace: Path) -> None:
    """Remove only an existing direct child of the dedicated jobs directory."""
    jobs_root = (Config.TEMP_DIR / "jobs").resolve()
    target = Path(workspace).resolve()
    if target.parent != jobs_root or target == jobs_root:
        raise ValueError("Refusing to remove a path outside the pipeline jobs directory.")
    if target.exists():
        shutil.rmtree(target)
