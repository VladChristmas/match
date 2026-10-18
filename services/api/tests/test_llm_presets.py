from app.config import Settings
from app.llm.gateway import build_providers
from app.llm.presets import PRESETS, resolve_preset


def test_known_presets_have_openai_compatible_endpoints():
    for preset in PRESETS.values():
        assert preset.base_url.startswith("https://")
        assert preset.model


def test_resolve_preset_is_case_insensitive():
    assert resolve_preset(" Groq ") is PRESETS["groq"]
    assert resolve_preset("unknown") is None
    assert resolve_preset("") is None


def test_preset_fills_cloud_provider_endpoint():
    settings = Settings(
        llm_provider="openai",
        llm_fallback_providers="ollama,echo",
        openai_api_key="secret",
        llm_preset="groq",
    )
    providers = build_providers(settings)
    assert [provider.name for provider in providers] == ["openai", "ollama", "echo"]
    cloud = providers[0]
    assert cloud.base_url == PRESETS["groq"].base_url
    assert cloud.model == PRESETS["groq"].model


def test_explicit_fields_used_when_no_preset():
    settings = Settings(
        llm_provider="openai",
        llm_fallback_providers="",
        openai_api_key="secret",
        openai_base_url="https://example.test/v1",
        openai_model="custom-model",
    )
    cloud = build_providers(settings)[0]
    assert cloud.base_url == "https://example.test/v1"
    assert cloud.model == "custom-model"


def test_preset_without_key_is_skipped():
    settings = Settings(
        llm_provider="openai",
        llm_fallback_providers="",
        llm_preset="groq",
    )
    assert [provider.name for provider in build_providers(settings)] == ["echo"]
