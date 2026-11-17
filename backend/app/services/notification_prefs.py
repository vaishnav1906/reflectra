"""What reminders a user wants, and the "about you" facts that shape replies.

Notification preferences live in user_settings.notifications (JSON) so the web app
and the future Android and iOS apps read and write the same switches. Nothing is
sent unless `enabled` is on: the master switch defaults to off.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional

DEFAULT_PREFS: Dict[str, object] = {
    "enabled": False,  # master switch: nothing is ever sent while this is off
    "follow_ups": True,  # "how did the gym go?" once something you planned is due
    "weekly_digest": True,  # Sunday evening: your week in reflection
    "daily_check_in": False,  # one question a day, at check_in_time
    "check_in_time": "21:00",
    "birthdays": True,  # a heads-up the day before someone in your People has a birthday
    "quiet_start": "22:30",
    "quiet_end": "08:00",
}
BOOLEAN_KEYS = ("enabled", "follow_ups", "weekly_digest", "daily_check_in", "birthdays")
TIME_KEYS = ("check_in_time", "quiet_start", "quiet_end")
_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

MIN_AGE, MAX_AGE = 13, 120


class ProfileError(ValueError):
    """Bad input; the message is safe to show."""


def merged_prefs(stored: Optional[Dict[str, object]]) -> Dict[str, object]:
    prefs = dict(DEFAULT_PREFS)
    for key, value in (stored or {}).items():
        if key in BOOLEAN_KEYS and isinstance(value, bool):
            prefs[key] = value
        elif key in TIME_KEYS and isinstance(value, str) and _TIME.match(value):
            prefs[key] = value
    return prefs


def clean_prefs(changes: Dict[str, object], current: Optional[Dict[str, object]]) -> Dict[str, object]:
    prefs = merged_prefs(current)
    for key, value in changes.items():
        if key in BOOLEAN_KEYS:
            if not isinstance(value, bool):
                raise ProfileError(f"{key} must be on or off.")
            prefs[key] = value
        elif key in TIME_KEYS:
            if not (isinstance(value, str) and _TIME.match(value)):
                raise ProfileError("Times look like 21:00.")
            prefs[key] = value
        else:
            raise ProfileError(f"Unknown setting: {key}")
    return prefs


def clean_theme(value: Optional[Dict[str, object]]) -> Optional[Dict[str, int]]:
    """{"hue": 0-359, "saturation": 30-100}, or None for the default colours."""
    if value is None:
        return None
    try:
        hue = int(round(float(value.get("hue")))) % 360  # type: ignore[arg-type]
        saturation = int(round(float(value.get("saturation"))))  # type: ignore[arg-type]
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProfileError("A colour needs a hue and an intensity.") from exc
    if not 30 <= saturation <= 100:
        raise ProfileError("Intensity goes from 30 to 100.")
    return {"hue": hue, "saturation": saturation}


def age_on(birth: Optional[date], today: date) -> Optional[int]:
    if birth is None:
        return None
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def clean_birth_date(value: Optional[str], today: date) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        birth = date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ProfileError("Date of birth should look like 2004-03-14.") from exc
    age = age_on(birth, today)
    if birth > today or age is None or age < MIN_AGE or age > MAX_AGE:
        raise ProfileError(f"Reflectra is for people aged {MIN_AGE} and over; check the date.")
    return birth


def clean_display_name(value: str) -> str:
    name = " ".join((value or "").split())[:60]
    if not name or not re.search(r"[^\W\d_]", name):
        raise ProfileError("Your name needs at least one letter.")
    return name


def about_lines(birth: Optional[date], today: date) -> List[str]:
    """What a reply should know about the user's age (and birthday, on the day)."""
    if birth is None:
        return []
    lines = [f"They're {age_on(birth, today)}."]
    if (birth.month, birth.day) == (today.month, today.day):
        lines.append("It's their birthday today. Say happy birthday once, warmly, early in the chat.")
    return lines
