# Логическая модель данных

> Заготовка. Уточняется до реализации. Персональные данные не хранятся; доступ по токенам.

## Сущности

### users
`id (UUID)`, `token_ref`, `status`, `created_at`, `updated_at`.
Идентификатор — токен/псевдоним, без email/персональных данных.

### user_profiles
`id`, `user_id`, `relationship_goals`, `values`, `preferences`, `boundaries`, `profile_version`, `created_at`, `updated_at`.

### communication_profiles
`id`, `user_id`, `style_preferences`, `tone_preferences`, `typical_message_length`, `humor_preferences`, `initiative_preferences`, `version`, `updated_at`.

### matches
`id`, `user_id`, `display_name` (псевдоним), `platform_id`, `status`, `goals_context`, `created_at`, `updated_at`.

### platform_connections
`id`, `user_id`, `platform_id`, `integration_mode`, `permissions`, `status`, `last_checked_at`.
Пароли/cookie/токены сторонних сервисов не хранятся.

### conversations
`id`, `match_id`, `status`, `autonomy_mode`, `last_activity_at`, `context_version`, `created_at`, `updated_at`.
На Этапе 3 реализована с добавлением `user_id` (FK на `users`, для изоляции по пользователю); `match_id` — nullable UUID без FK (таблица `matches` появится позже).

### messages
`id`, `conversation_id`, `external_message_id?`, `direction`, `content`/ссылка, `source`, `created_at`, `processed_at`, `processing_status`.
Текст хранится минимально; возможно удаление после обработки. Реализована на Этапе 3.

### psychological_observations
`id`, `user_id`/`match_id`, `subject_type`, `category`, `observation`, `evidence_reference`, `confidence`, `status`, `observed_at`, `expires_at`, `created_at`.
Гипотезы не становятся фактами автоматически. **Видно только пользователю.**

### compatibility_assessments
`id`, `user_id`, `match_id`, `goals_alignment`, `values_alignment`, `lifestyle_alignment`, `reciprocity`, `uncertainty`, `explanation`, `assessed_at`, `model_version`.

### risk_assessments
`id`, `match_id`, `conversation_id`, `risk_category`, `signals`, `confidence`, `explanation`, `recommended_action`, `assessed_at`.

### agent_permissions
`id`, `user_id`, `scope`, `action_type`, `allowed`, `limits`, `valid_from`, `valid_until`, `updated_at`.

### agent_actions
`id`, `user_id`, `conversation_id`, `action_type`, `decision_reason`, `permission_check_result`, `status`, `idempotency_key`, `created_at`, `completed_at`.

### user_feedback
`id`, `user_id`, `conversation_id`, `action_id`, `feedback_type`, `rating`, `correction`, `created_at`.
На Этапе 2 таблица реализована; `conversation_id`/`action_id` — nullable UUID без FK (таблицы `conversations`/`agent_actions` появятся на этапах 3/8).

### model_runs
`id`, `task_type`, `provider`, `model`, `model_version`, `prompt_version`, `latency_ms`, `token_usage`, `status`, `created_at`.
Полный текст переписки в технические логи по умолчанию не пишется.

## Требования

- UUID для публичных сущностей; внешние ключи и целостность.
- Индексы под частые запросы; явное разделение данных пользователей.
- RLS при необходимости; политики удаления связанных данных.
- Версионированные миграции; документированные сроки хранения и бэкапы.
- Запрет хранения секретов в таблицах без обоснования.
