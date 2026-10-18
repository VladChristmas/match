import uuid

from app.dialogue.context import build_context
from app.dialogue.style import build_style
from app.dialogue.validator import validate_draft
from app.models import CommunicationProfile, Message


def test_style_bounds_from_communication_profile():
    profile = CommunicationProfile(user_id=uuid.uuid4(), typical_message_length="short")
    style = build_style(profile)
    assert style.max_length == 160


def test_style_defaults_without_profile():
    style = build_style(None)
    assert (style.min_length, style.max_length) == (1, 400)
    assert "conversational" in style.describe()


def test_validate_rejects_empty():
    result = validate_draft("   ", build_style(None))
    assert result.ok is False
    assert "empty" in result.issues


def test_validate_rejects_too_long():
    style = build_style(CommunicationProfile(user_id=uuid.uuid4(), typical_message_length="short"))
    result = validate_draft("a" * 200, style)
    assert "too_long" in result.issues


def test_validate_detects_system_leak():
    result = validate_draft("As an AI language model I cannot", build_style(None))
    assert result.ok is False
    assert "system_leak" in result.issues


def test_validate_accepts_natural_reply():
    result = validate_draft("Привет! Рад познакомиться.", build_style(None))
    assert result.ok is True
    assert result.issues == []


def test_context_maps_history_roles_and_style():
    history = [
        Message(conversation_id=uuid.uuid4(), direction="inbound", content="привет"),
        Message(conversation_id=uuid.uuid4(), direction="outbound", content="привет!"),
    ]
    context = build_context(None, None, history)
    assert [m.role for m in context.messages] == ["user", "assistant"]
    assert "communication style" in context.system_prompt
