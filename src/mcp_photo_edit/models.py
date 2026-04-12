"""Pydantic models shared across the server and domain layers."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


ADJUSTMENT_SPECS: dict[str, dict[str, Any]] = {
    "exposure": {
        "minimum": -5.0,
        "maximum": 5.0,
        "default": 0.0,
        "unit": "ev",
        "description": "Overall exposure compensation.",
        "example": 0.8,
    },
    "contrast": {
        "minimum": -100.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "percent",
        "description": "Global contrast strength.",
        "example": 20.0,
    },
    "saturation": {
        "minimum": -100.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "percent",
        "description": "Global saturation adjustment.",
        "example": 8.0,
    },
    "orientation": {
        "minimum": -90,
        "maximum": 180,
        "default": 0,
        "unit": "quarter_turn_degrees",
        "description": "Quarter-turn orientation. Allowed values are -90, 0, 90, 180.",
        "example": 90,
    },
}

RESETTABLE_FIELDS = tuple(ADJUSTMENT_SPECS.keys()) + ("crop",)


def utc_now() -> datetime:
    """Return a timezone-aware timestamp."""

    return datetime.now(UTC)


class ErrorInfo(BaseModel):
    """Structured tool error payload."""

    code: str
    message: str
    hint: str | None = None


class CropAdjustment(BaseModel):
    """Normalized crop box."""

    left: float = Field(ge=0.0, le=1.0)
    top: float = Field(ge=0.0, le=1.0)
    right: float = Field(ge=0.0, le=1.0)
    bottom: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "CropAdjustment":
        """Require a positive crop area."""

        if self.left >= self.right:
            raise ValueError("crop.left must be less than crop.right")
        if self.top >= self.bottom:
            raise ValueError("crop.top must be less than crop.bottom")
        return self


class AdjustmentState(BaseModel):
    """Full normalized edit state for a session."""

    exposure: float = Field(default=0.0, ge=-5.0, le=5.0)
    contrast: float = Field(default=0.0, ge=-100.0, le=100.0)
    saturation: float = Field(default=0.0, ge=-100.0, le=100.0)
    orientation: int = 0
    crop: CropAdjustment | None = None

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: int) -> int:
        """Allow only quarter-turn rotations."""

        if value not in {-90, 0, 90, 180}:
            raise ValueError("orientation must be one of -90, 0, 90, 180")
        return value

    def apply_patch(self, patch: "AdjustmentPatch") -> "AdjustmentState":
        """Return a new state with only provided fields updated."""

        data = self.model_dump()
        data.update(patch.model_dump(exclude_unset=True))
        return AdjustmentState.model_validate(data)

    def reset_fields(self, fields: list[str] | None = None) -> "AdjustmentState":
        """Return a new state with selected fields reset to defaults."""

        if not fields:
            return AdjustmentState()

        data = self.model_dump()
        defaults = AdjustmentState().model_dump()
        for field in fields:
            data[field] = defaults[field]
        return AdjustmentState.model_validate(data)


class AdjustmentPatch(BaseModel):
    """Partial update payload for tools."""

    exposure: float | None = Field(default=None, ge=-5.0, le=5.0)
    contrast: float | None = Field(default=None, ge=-100.0, le=100.0)
    saturation: float | None = Field(default=None, ge=-100.0, le=100.0)
    orientation: int | None = None
    crop: CropAdjustment | None = None

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: int | None) -> int | None:
        """Allow only quarter-turn rotations."""

        if value is not None and value not in {-90, 0, 90, 180}:
            raise ValueError("orientation must be one of -90, 0, 90, 180")
        return value


class AdjustmentSpec(BaseModel):
    """Runtime-discoverable adjustment documentation."""

    name: str
    minimum: float | int | None
    maximum: float | int | None
    default: float | int | None
    unit: str
    description: str
    example: float | int | dict[str, float]


class SourceImageInfo(BaseModel):
    """Resolved metadata about the source image."""

    input_path: str
    file_name: str
    suffix: str
    width: int | None = None
    height: int | None = None

    @classmethod
    def from_path(cls, input_path: Path) -> "SourceImageInfo":
        """Build image info from a resolved path."""

        width: int | None = None
        height: int | None = None
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - optional import at runtime
            Image = None

        if Image is not None:
            try:
                with Image.open(input_path) as image:
                    width, height = image.size
            except OSError:
                width = None
                height = None

        if width is None or height is None:
            width, height = _exiftool_dimensions(input_path)

        return cls(
            input_path=str(input_path),
            file_name=input_path.name,
            suffix=input_path.suffix.lower(),
            width=width,
            height=height,
        )


class PreviewArtifact(BaseModel):
    """A single preview render artifact."""

    sequence: int
    path: str
    rendered_at: datetime = Field(default_factory=utc_now)


class HistoryStep(BaseModel):
    """A committed semantic edit state."""

    step_id: str
    kind: str
    created_at: datetime = Field(default_factory=utc_now)
    adjustments: AdjustmentState
    state_path: str | None = None
    preview_path: str | None = None
    preview_sequence: int | None = None
    description: str | None = None


def _exiftool_dimensions(input_path: Path) -> tuple[int | None, int | None]:
    executable = shutil.which("exiftool")
    if executable is None:
        return None, None

    completed = subprocess.run(
        [
            executable,
            "-s3",
            "-ImageWidth",
            "-ImageHeight",
            str(input_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None, None

    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None, None

    try:
        return int(lines[0]), int(lines[1])
    except ValueError:
        return None, None


class SessionState(BaseModel):
    """Persisted session state."""

    session_id: str
    session_label: str | None = None
    source: SourceImageInfo
    workspace_dir: str
    state_path: str | None = None
    xmp_path: str | None = None
    preview_path: str
    preview_max_size: int = Field(default=1024, ge=64, le=4096)
    preview_history: list[PreviewArtifact] = Field(default_factory=list)
    adjustments: AdjustmentState = Field(default_factory=AdjustmentState)
    history: list[HistoryStep] = Field(default_factory=list)
    history_index: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_rendered_at: datetime | None = None
    backend: str = "rawtherapee-cli"

    @field_validator("workspace_dir", "state_path", "xmp_path", "preview_path")
    @classmethod
    def stringify_paths(cls, value: str | Path | None) -> str | None:
        """Persist paths as strings."""

        if value is None:
            return None
        return str(value)

    @model_validator(mode="after")
    def validate_history(self) -> "SessionState":
        """Normalize state and ensure the history cursor is valid."""

        if self.state_path is None and self.xmp_path is not None:
            self.state_path = self.xmp_path
        if not self.history:
            raise ValueError("history must contain at least one step")
        if self.history_index < 0 or self.history_index >= len(self.history):
            raise ValueError("history_index must point to a valid step")
        return self

    def touch(self) -> None:
        """Refresh the update timestamp."""

        self.updated_at = utc_now()

    @property
    def current_step(self) -> HistoryStep:
        """Return the history step referenced by the current cursor."""

        return self.history[self.history_index]

    @computed_field
    @property
    def can_undo(self) -> bool:
        """Whether the cursor can move backward."""

        return self.history_index > 0

    @computed_field
    @property
    def can_redo(self) -> bool:
        """Whether the cursor can move forward."""

        return self.history_index < len(self.history) - 1

    @computed_field
    @property
    def history_length(self) -> int:
        """Return the number of semantic history steps."""

        return len(self.history)


class SessionEnvelope(BaseModel):
    """Tool response for session-bearing endpoints."""

    ok: bool = True
    session: SessionState | None = None
    warnings: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = None


class PreviewResult(BaseModel):
    """Tool response for preview rendering."""

    ok: bool = True
    session_id: str | None = None
    preview_path: str | None = None
    preview_count: int | None = None
    preview_history: list[PreviewArtifact] = Field(default_factory=list)
    history_index: int | None = None
    history_length: int | None = None
    can_undo: bool | None = None
    can_redo: bool | None = None
    last_rendered_at: datetime | None = None
    error: ErrorInfo | None = None


class ExportResult(BaseModel):
    """Tool response for exports."""

    ok: bool = True
    session_id: str | None = None
    output_path: str | None = None
    format: str | None = None
    backend: str | None = None
    error: ErrorInfo | None = None


class SupportedAdjustmentsResult(BaseModel):
    """Tool response for supported adjustment discovery."""

    ok: bool = True
    adjustments: list[AdjustmentSpec] = Field(default_factory=list)
    error: ErrorInfo | None = None
