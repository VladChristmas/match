from dataclasses import dataclass

from app.models import CommunicationProfile

LENGTH_BOUNDS: dict[str, tuple[int, int]] = {
    "very_short": (1, 80),
    "short": (1, 160),
    "medium": (1, 400),
    "long": (1, 900),
}
DEFAULT_BOUNDS = (1, 400)


@dataclass(frozen=True)
class StyleProfile:
    typical_message_length: str | None
    min_length: int
    max_length: int
    tone_preferences: dict
    style_preferences: dict
    humor_preferences: dict
    initiative_preferences: dict

    def describe(self) -> str:
        parts: list[str] = []
        if self.typical_message_length:
            parts.append(f"typical message length: {self.typical_message_length}")
        if self.tone_preferences:
            parts.append(f"tone: {self.tone_preferences}")
        if self.style_preferences:
            parts.append(f"style: {self.style_preferences}")
        if self.humor_preferences:
            parts.append(f"humor: {self.humor_preferences}")
        if self.initiative_preferences:
            parts.append(f"initiative: {self.initiative_preferences}")
        return "; ".join(parts) if parts else "neutral, natural, conversational"


def build_style(profile: CommunicationProfile | None) -> StyleProfile:
    if profile is None:
        return StyleProfile(None, *DEFAULT_BOUNDS, {}, {}, {}, {})
    bounds = LENGTH_BOUNDS.get(profile.typical_message_length or "", DEFAULT_BOUNDS)
    return StyleProfile(
        typical_message_length=profile.typical_message_length,
        min_length=bounds[0],
        max_length=bounds[1],
        tone_preferences=profile.tone_preferences or {},
        style_preferences=profile.style_preferences or {},
        humor_preferences=profile.humor_preferences or {},
        initiative_preferences=profile.initiative_preferences or {},
    )
