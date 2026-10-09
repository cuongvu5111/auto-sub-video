"""Typed status returned by the GUI-facing pipeline job boundary."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class JobStatus(str, Enum):
    """Stable terminal states for one video job."""

    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobResult:
    """Outcome details shared by pipeline orchestration and the GUI worker."""

    status: JobStatus
    output_path: Optional[Path] = None
    warnings: Tuple[str, ...] = ()
    error: Optional[str] = None
