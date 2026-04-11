"""Helpers for resolving digital twin policy from user settings."""

from typing import Any, Dict, Optional


DEFAULT_TWIN_AUTONOMY_MODE = "draft_only"
VALID_TWIN_AUTONOMY_MODES = {"draft_only", "suggest", "auto_execute"}

DEFAULT_TWIN_SETTINGS: Dict[str, Any] = {
    "persona_mirroring": True,
    "pattern_tracking": True,
    "daily_reflections": True,
    "digital_twin_enabled": True,
    "twin_autonomy_mode": DEFAULT_TWIN_AUTONOMY_MODE,
    "twin_mirror_intensity": 0.8,
    "twin_require_approval": True,
}


def validate_twin_autonomy_mode(mode: Optional[str]) -> str:
    """Normalize and validate autonomy mode with safe fallback."""
    if not mode:
        return DEFAULT_TWIN_AUTONOMY_MODE

    normalized = mode.strip().lower()
    if normalized not in VALID_TWIN_AUTONOMY_MODES:
        allowed = ", ".join(sorted(VALID_TWIN_AUTONOMY_MODES))
        raise ValueError(f"Invalid twin_autonomy_mode. Allowed values: {allowed}")
    return normalized


def clamp_mirror_intensity(value: Optional[float]) -> float:
    """Clamp mirror intensity to [0, 1] with sane default."""
    if value is None:
        return float(DEFAULT_TWIN_SETTINGS["twin_mirror_intensity"])

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(DEFAULT_TWIN_SETTINGS["twin_mirror_intensity"])

    return max(0.0, min(1.0, numeric))


def resolve_twin_settings(settings_record: Any) -> Dict[str, Any]:
    """Build effective twin settings from DB model with backwards-compatible defaults."""
    resolved = dict(DEFAULT_TWIN_SETTINGS)
    if settings_record is None:
        return resolved

    def _read(name: str, default: Any) -> Any:
        if isinstance(settings_record, dict):
            return settings_record.get(name, default)
        return getattr(settings_record, name, default)

    resolved["persona_mirroring"] = bool(
        _read("persona_mirroring", resolved["persona_mirroring"])
    )
    resolved["pattern_tracking"] = bool(
        _read("pattern_tracking", resolved["pattern_tracking"])
    )
    resolved["daily_reflections"] = bool(
        _read("daily_reflections", resolved["daily_reflections"])
    )
    resolved["digital_twin_enabled"] = bool(
        _read("digital_twin_enabled", resolved["digital_twin_enabled"])
    )
    resolved["twin_autonomy_mode"] = validate_twin_autonomy_mode(
        _read("twin_autonomy_mode", None)
    )
    resolved["twin_mirror_intensity"] = clamp_mirror_intensity(
        _read("twin_mirror_intensity", None)
    )
    resolved["twin_require_approval"] = bool(
        _read("twin_require_approval", resolved["twin_require_approval"])
    )

    return resolved
