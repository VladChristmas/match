"""Статус LLM-шлюза для UI и эксплуатации (аудит 2026-10-25, P1).

Показывает фактический состав провайдеров (не только заявленные настройки):
кто будет получать промпты, какие провайдеры отброшены за неналичием ключа,
и какой лимит расходов на пользователя включён (`0` = выключен).
Доступен по токену, как и остальные `/api/v1`-маршруты.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, GatewayDep
from app.config import Settings, get_settings
from app.schemas import LLMStatusRead

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/status", response_model=LLMStatusRead)
async def llm_status(
    user: CurrentUser,
    gateway: GatewayDep,
    settings: SettingsDep,
) -> LLMStatusRead:
    declared = [
        name.strip()
        for name in [settings.llm_provider, *settings.llm_fallback_providers.split(",")]
        if name.strip()
    ]
    # Билдер отбрасывает неконфигурируемые (openai без ключа) и подставляет
    # echo — показываем и заявленный, и фактический состав, чтобы расхождение
    # между настройками и поведением было видно (аудит P1).
    resolved = list(gateway.provider_names)
    skipped = [name for name in declared if name not in resolved]
    limit = settings.llm_user_request_limit
    return LLMStatusRead(
        provider=gateway.provider_name,
        fallback_providers=resolved[1:],
        declared_providers=declared,
        skipped_providers=skipped,
        user_request_limit=limit,
        user_request_limit_enabled=limit > 0,
        timeout_seconds=settings.llm_timeout_seconds,
    )
