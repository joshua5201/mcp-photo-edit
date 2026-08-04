"""Pydantic models shared across the server and domain layers."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import (
    BaseModel,
    Field,
    JsonValue,
    computed_field,
    field_validator,
    model_validator,
)


class AdjustmentSpecData(TypedDict):
    """Typed source data for discoverable adjustment metadata."""

    minimum: float | int | None
    maximum: float | int | None
    default: float | int | None
    unit: str
    description: str
    example: JsonValue


ADJUSTMENT_SPECS: dict[str, AdjustmentSpecData] = {
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
    "rgb_mixer": {
        "minimum": None,
        "maximum": None,
        "default": None,
        "unit": "percent_triplets",
        "description": "Per-output RGB channel mixer rows with `red`, `green`, and `blue` triplets in percentage units.",
        "example": {
            "red": [100.0, 0.0, 0.0],
            "green": [0.0, 95.0, 5.0],
            "blue": [0.0, 0.0, 100.0],
        },
    },
    "denoise_luma": {
        "minimum": 0.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "strength",
        "description": "Luminance noise reduction strength.",
        "example": 20.0,
    },
    "denoise_detail": {
        "minimum": 0.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "strength",
        "description": "Luminance detail preservation during denoising.",
        "example": 15.0,
    },
    "denoise_chroma": {
        "minimum": 0.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "strength",
        "description": "Chrominance noise reduction strength.",
        "example": 25.0,
    },
    "color_temperature": {
        "minimum": 1500.0,
        "maximum": 60000.0,
        "default": None,
        "unit": "kelvin",
        "description": "Manual white balance color temperature.",
        "example": 5200.0,
    },
    "green_balance": {
        "minimum": 0.02,
        "maximum": 100.0,
        "default": None,
        "unit": "scale",
        "description": "Manual white balance green-magenta balance.",
        "example": 1.05,
    },
    "highlights": {
        "minimum": 0.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "strength",
        "description": "Highlight recovery strength.",
        "example": 18.0,
    },
    "shadows": {
        "minimum": 0.0,
        "maximum": 100.0,
        "default": 0.0,
        "unit": "strength",
        "description": "Shadow recovery strength.",
        "example": 22.0,
    },
    "sharpen_amount": {
        "minimum": 0,
        "maximum": 1000,
        "default": 0.0,
        "unit": "integer_strength",
        "description": "Sharpening amount using RawTherapee's main sharpening tool in usm mode.",
        "example": 180,
    },
    "sharpen_radius": {
        "minimum": 0.3,
        "maximum": 3.0,
        "default": 0.5,
        "unit": "pixels",
        "description": "Sharpening radius using RawTherapee's main sharpening tool in usm mode.",
        "example": 0.8,
    },
    "sharpen_contrast": {
        "minimum": 0.0,
        "maximum": 200.0,
        "default": 20.0,
        "unit": "strength",
        "description": "Sharpening contrast using RawTherapee's main sharpening tool in usm mode.",
        "example": 30.0,
    },
}

RESETTABLE_FIELDS = (*tuple(ADJUSTMENT_SPECS.keys()), "crop")


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
    def validate_bounds(self) -> CropAdjustment:
        """Require a positive crop area."""

        if self.left >= self.right:
            raise ValueError("crop.left must be less than crop.right")
        if self.top >= self.bottom:
            raise ValueError("crop.top must be less than crop.bottom")
        return self


class RGBMixer(BaseModel):
    """Per-output RGB channel mixing matrix in percentage units."""

    red: tuple[float, float, float] = (100.0, 0.0, 0.0)
    green: tuple[float, float, float] = (0.0, 100.0, 0.0)
    blue: tuple[float, float, float] = (0.0, 0.0, 100.0)

    @field_validator("red", "green", "blue")
    @classmethod
    def validate_row(
        cls,
        value: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Require exactly three bounded channel weights per row."""

        if len(value) != 3:
            raise ValueError("rgb_mixer rows must contain exactly three channel weights")
        if any(channel < -500.0 or channel > 500.0 for channel in value):
            raise ValueError("rgb_mixer values must be between -500 and 500")
        return value

    def is_identity(self) -> bool:
        """Whether the mixer matches the default channel routing."""

        return self == RGBMixer()


class AdjustmentState(BaseModel):
    """Full normalized edit state for a session."""

    exposure: float = Field(default=0.0, ge=-5.0, le=5.0)
    contrast: float = Field(default=0.0, ge=-100.0, le=100.0)
    saturation: float = Field(default=0.0, ge=-100.0, le=100.0)
    rgb_mixer: RGBMixer | None = None
    denoise_luma: float = Field(default=0.0, ge=0.0, le=100.0)
    denoise_detail: float = Field(default=0.0, ge=0.0, le=100.0)
    denoise_chroma: float = Field(default=0.0, ge=0.0, le=100.0)
    color_temperature: float | None = Field(default=None, ge=1500.0, le=60000.0)
    green_balance: float | None = Field(default=None, ge=0.02, le=100.0)
    highlights: float = Field(default=0.0, ge=0.0, le=100.0)
    shadows: float = Field(default=0.0, ge=0.0, le=100.0)
    sharpen_amount: int = Field(default=0, ge=0, le=1000)
    sharpen_radius: float = Field(default=0.5, ge=0.3, le=3.0)
    sharpen_contrast: float = Field(default=20.0, ge=0.0, le=200.0)
    orientation: int = 0
    crop: CropAdjustment | None = None

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: int) -> int:
        """Allow only quarter-turn rotations."""

        if value not in {-90, 0, 90, 180}:
            raise ValueError("orientation must be one of -90, 0, 90, 180")
        return value

    def apply_patch(self, patch: AdjustmentPatch) -> AdjustmentState:
        """Return a new state with only provided fields updated."""

        data = self.model_dump()
        patch_data = patch.model_dump(exclude_unset=True)
        if (
            "color_temperature" in patch_data
            and "green_balance" not in patch_data
            and data["green_balance"] is None
        ):
            data["green_balance"] = 1.0
        if (
            "green_balance" in patch_data
            and "color_temperature" not in patch_data
            and data["color_temperature"] is None
        ):
            data["color_temperature"] = 6504.0
        data.update(patch_data)
        return AdjustmentState.model_validate(data)

    def reset_fields(self, fields: list[str] | None = None) -> AdjustmentState:
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
    rgb_mixer: RGBMixer | None = None
    denoise_luma: float | None = Field(default=None, ge=0.0, le=100.0)
    denoise_detail: float | None = Field(default=None, ge=0.0, le=100.0)
    denoise_chroma: float | None = Field(default=None, ge=0.0, le=100.0)
    color_temperature: float | None = Field(default=None, ge=1500.0, le=60000.0)
    green_balance: float | None = Field(default=None, ge=0.02, le=100.0)
    highlights: float | None = Field(default=None, ge=0.0, le=100.0)
    shadows: float | None = Field(default=None, ge=0.0, le=100.0)
    sharpen_amount: int | None = Field(default=None, ge=0, le=1000)
    sharpen_radius: float | None = Field(default=None, ge=0.3, le=3.0)
    sharpen_contrast: float | None = Field(default=None, ge=0.0, le=200.0)
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
    example: JsonValue


class SourceImageInfo(BaseModel):
    """Resolved metadata about the source image."""

    input_path: str
    file_name: str
    suffix: str
    width: int | None = None
    height: int | None = None

    @classmethod
    def from_path(cls, input_path: Path) -> SourceImageInfo:
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


class DiagnosticDimensions(BaseModel):
    """Dimensions of the rendered image used for diagnostics."""

    width: int
    height: int


class DiagnosticLumaSummary(BaseModel):
    """Basic tonal distribution statistics."""

    p01: float
    p50: float
    p99: float
    clipped_black_pct: float
    clipped_white_pct: float


class DiagnosticRGBBalanceSummary(BaseModel):
    """Channel balance summary for the rendered image."""

    red_mean: float
    green_mean: float
    blue_mean: float
    temperature_hint: str
    tint_hint: str


class DiagnosticSaturationSummary(BaseModel):
    """Saturation distribution summary for the rendered image."""

    p50: float
    p95: float
    high_saturation_pct: float


class DiagnosticSummary(BaseModel):
    """Honest diagnostics for the current rendered state."""

    analysis_source: Literal["current_rendered_state"] = "current_rendered_state"
    dimensions: DiagnosticDimensions
    luma: DiagnosticLumaSummary
    rgb_balance: DiagnosticRGBBalanceSummary
    saturation: DiagnosticSaturationSummary


class HistoryStep(BaseModel):
    """A committed semantic edit state."""

    step_id: str
    kind: str
    created_at: datetime = Field(default_factory=utc_now)
    adjustments: AdjustmentState
    state_path: str | None = None
    preview_path: str | None = None
    preview_sequence: int | None = None
    diagnostic_dashboard_path: str | None = None
    diagnostic_summary: DiagnosticSummary | None = None
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
    preview_path: str
    diagnostic_dashboard_path: str | None = None
    diagnostic_summary: DiagnosticSummary | None = None
    preview_max_size: int = Field(default=1024, ge=64, le=4096)
    preview_history: list[PreviewArtifact] = Field(default_factory=list)
    adjustments: AdjustmentState = Field(default_factory=AdjustmentState)
    history: list[HistoryStep] = Field(default_factory=list)
    history_index: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_rendered_at: datetime | None = None
    backend: str = "mcp-photo-edit-rawtherapee"

    @field_validator("workspace_dir", "state_path", "preview_path")
    @classmethod
    def stringify_paths(cls, value: str | Path | None) -> str | None:
        """Persist paths as strings."""

        if value is None:
            return None
        return str(value)

    @model_validator(mode="after")
    def validate_history(self) -> SessionState:
        """Normalize state and ensure the history cursor is valid."""

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
    diagnostic_dashboard_path: str | None = None
    diagnostic_summary: DiagnosticSummary | None = None
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
