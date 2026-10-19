//! Локальное хранилище клиента (Этап 16, OQ-6) и оффлайн-очередь (Этап 20).
//!
//! Хранит настройки клиента (одна строка JSON без журнала), журнал событий (таблица с
//! индексом по времени) и оффлайн-очередь исходящих запросов (`outbox`). Настройки и
//! журнал не покидают устройство; серверу они не нужны (ADR-0007). Старый `settings.json`
//! переносится в БД один раз и переименовывается.
//!
//! Схема версионируется через `PRAGMA user_version`, поэтому будущие изменения добавляются
//! новой ветвью в `migrate` без внешних миграционных инструментов. `outbox` появилась в
//! версии 2 (ADR-0026).

use std::fs;
use std::path::PathBuf;

use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Manager};

const SCHEMA_VERSION: i64 = 3;
const JOURNAL_LIMIT: i64 = 500;

#[derive(Serialize, Deserialize, Clone)]
pub struct JournalEntry {
    pub id: String,
    pub at: String,
    pub kind: String,
    pub summary: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct OutboxEntry {
    pub id: String,
    pub at: String,
    pub method: String,
    pub path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub body: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub idempotency_key: Option<String>,
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub attempts: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_error: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Memory {
    pub id: String,
    pub user_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub conversation_id: Option<String>,
    pub kind: String,
    pub status: String,
    pub content: String,
    pub source: String,
    pub confidence: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub valid_until: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct MemoryEvent {
    pub id: String,
    pub memory_id: String,
    pub event_type: String,
    pub actor: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
    pub created_at: String,
}

#[derive(Serialize)]
pub struct StateSnapshot {
    pub settings: Value,
    pub journal: Vec<JournalEntry>,
}

#[derive(Serialize)]
pub struct StorageInfo {
    pub path: String,
    pub schema_version: i64,
    pub sqlite_version: String,
    pub journal_entries: i64,
    pub outbox_entries: i64,
    pub memory_entries: i64,
    pub size_bytes: u64,
    pub settings_present: bool,
}

fn db_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("match.db"))
}

fn open(app: &AppHandle) -> Result<Connection, String> {
    let path = db_path(app)?;
    let conn = Connection::open(&path).map_err(|e| e.to_string())?;
    conn.execute_batch("PRAGMA journal_mode = WAL;")
        .map_err(|e| e.to_string())?;
    migrate(&conn)?;
    import_legacy_settings(app, &conn)?;
    Ok(conn)
}

fn migrate(conn: &Connection) -> Result<(), String> {
    let version: i64 = conn
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    if version >= SCHEMA_VERSION {
        return Ok(());
    }
    if version < 1 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS settings (
                 key TEXT PRIMARY KEY,
                 value TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS journal (
                 id TEXT PRIMARY KEY,
                 at TEXT NOT NULL,
                 kind TEXT NOT NULL,
                 summary TEXT NOT NULL,
                 detail TEXT
             );
             CREATE INDEX IF NOT EXISTS idx_journal_at ON journal(at DESC);",
        )
        .map_err(|e| e.to_string())?;
    }
    if version < 2 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS outbox (
                 id TEXT PRIMARY KEY,
                 at TEXT NOT NULL,
                 method TEXT NOT NULL,
                 path TEXT NOT NULL,
                 body TEXT,
                 idempotency_key TEXT,
                 label TEXT NOT NULL DEFAULT '',
                 attempts INTEGER NOT NULL DEFAULT 0,
                 last_error TEXT
             );
              CREATE INDEX IF NOT EXISTS idx_outbox_at ON outbox(at);",
        )
        .map_err(|e| e.to_string())?;
    }
    if version < 3 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS memories (
                 id TEXT PRIMARY KEY,
                 user_id TEXT NOT NULL,
                 conversation_id TEXT,
                 kind TEXT NOT NULL,
                 status TEXT NOT NULL DEFAULT 'received',
                 content TEXT NOT NULL,
                 source TEXT NOT NULL DEFAULT 'message',
                 confidence REAL NOT NULL DEFAULT 0.5,
                 valid_until TEXT,
                 created_at TEXT NOT NULL,
                 updated_at TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS memory_events (
                 id TEXT PRIMARY KEY,
                 memory_id TEXT NOT NULL,
                 event_type TEXT NOT NULL,
                 actor TEXT NOT NULL DEFAULT 'system',
                 detail TEXT,
                 created_at TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
             CREATE INDEX IF NOT EXISTS idx_memories_conversation_id ON memories(conversation_id);
             CREATE INDEX IF NOT EXISTS idx_memory_events_memory_id ON memory_events(memory_id);",
        )
        .map_err(|e| e.to_string())?;
    }
    conn.pragma_update(None, "user_version", SCHEMA_VERSION)
        .map_err(|e| e.to_string())
}

fn store_settings(conn: &Connection, value: &Value) -> Result<(), String> {
    let mut payload = value.clone();
    if let Some(object) = payload.as_object_mut() {
        object.remove("journal");
    }
    let raw = serde_json::to_string(&payload).map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('app', ?1)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        params![raw],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

fn insert_journal(conn: &Connection, entry: &JournalEntry) -> Result<(), String> {
    conn.execute(
        "INSERT OR REPLACE INTO journal (id, at, kind, summary, detail)
         VALUES (?1, ?2, ?3, ?4, ?5)",
        params![entry.id, entry.at, entry.kind, entry.summary, entry.detail],
    )
    .map_err(|e| e.to_string())?;
    conn.execute(
        "DELETE FROM journal WHERE id NOT IN
         (SELECT id FROM journal ORDER BY at DESC LIMIT ?1)",
        params![JOURNAL_LIMIT],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

fn load_stored_settings(conn: &Connection) -> Result<Value, String> {
    let raw: Option<String> = conn
        .query_row("SELECT value FROM settings WHERE key = 'app'", [], |row| {
            row.get(0)
        })
        .ok();
    match raw {
        Some(text) => serde_json::from_str(&text).map_err(|e| e.to_string()),
        None => Ok(Value::Object(serde_json::Map::new())),
    }
}

fn load_journal(conn: &Connection) -> Result<Vec<JournalEntry>, String> {
    let mut statement = conn
        .prepare("SELECT id, at, kind, summary, detail FROM journal ORDER BY at DESC LIMIT ?1")
        .map_err(|e| e.to_string())?;
    let rows = statement
        .query_map(params![JOURNAL_LIMIT], |row| {
            Ok(JournalEntry {
                id: row.get(0)?,
                at: row.get(1)?,
                kind: row.get(2)?,
                summary: row.get(3)?,
                detail: row.get(4)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}

fn insert_outbox(conn: &Connection, entry: &OutboxEntry) -> Result<(), String> {
    conn.execute(
        "INSERT OR REPLACE INTO outbox
             (id, at, method, path, body, idempotency_key, label, attempts, last_error)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
        params![
            entry.id,
            entry.at,
            entry.method,
            entry.path,
            entry.body,
            entry.idempotency_key,
            entry.label,
            entry.attempts,
            entry.last_error
        ],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

fn list_outbox(conn: &Connection) -> Result<Vec<OutboxEntry>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, at, method, path, body, idempotency_key, label, attempts, last_error
             FROM outbox ORDER BY at ASC",
        )
        .map_err(|e| e.to_string())?;
    let rows = statement
        .query_map([], |row| {
            Ok(OutboxEntry {
                id: row.get(0)?,
                at: row.get(1)?,
                method: row.get(2)?,
                path: row.get(3)?,
                body: row.get(4)?,
                idempotency_key: row.get(5)?,
                label: row.get(6)?,
                attempts: row.get(7)?,
                last_error: row.get(8)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}

fn remove_outbox(conn: &Connection, id: &str) -> Result<(), String> {
    conn.execute("DELETE FROM outbox WHERE id = ?1", params![id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn fail_outbox(conn: &Connection, id: &str, error: &str) -> Result<(), String> {
    conn.execute(
        "UPDATE outbox SET attempts = attempts + 1, last_error = ?2 WHERE id = ?1",
        params![id, error],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

/// Переносит прежний `settings.json` в БД (однократно) и переименовывает файл.
fn import_legacy_settings(app: &AppHandle, conn: &Connection) -> Result<(), String> {
    let stored: i64 = conn
        .query_row("SELECT COUNT(*) FROM settings", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    if stored > 0 {
        return Ok(());
    }
    let Ok(dir) = app.path().app_config_dir() else {
        return Ok(());
    };
    let legacy = dir.join("settings.json");
    if !legacy.exists() {
        return Ok(());
    }
    let raw = fs::read_to_string(&legacy).map_err(|e| e.to_string())?;
    let value: Value = serde_json::from_str(&raw).unwrap_or(Value::Object(serde_json::Map::new()));
    store_settings(conn, &value)?;
    if let Some(entries) = value.get("journal").and_then(|journal| journal.as_array()) {
        for item in entries {
            if let Ok(entry) = serde_json::from_value::<JournalEntry>(item.clone()) {
                insert_journal(conn, &entry)?;
            }
        }
    }
    let _ = fs::rename(&legacy, dir.join("settings.json.migrated"));
    Ok(())
}

/// Возвращает настройки и журнал из локальной БД.
#[tauri::command]
pub fn load_state(app: AppHandle) -> Result<StateSnapshot, String> {
    let conn = open(&app)?;
    Ok(StateSnapshot {
        settings: load_stored_settings(&conn)?,
        journal: load_journal(&conn)?,
    })
}

/// Сохраняет настройки клиента (журнал хранится отдельно).
#[tauri::command]
pub fn save_state(app: AppHandle, settings: Value) -> Result<(), String> {
    let conn = open(&app)?;
    store_settings(&conn, &settings)
}

/// Добавляет запись журнала и подрезает историю до 500 последних записей.
#[tauri::command]
pub fn journal_append(app: AppHandle, entry: JournalEntry) -> Result<(), String> {
    let conn = open(&app)?;
    insert_journal(&conn, &entry)
}

/// Полностью очищает журнал на устройстве.
#[tauri::command]
pub fn journal_clear(app: AppHandle) -> Result<(), String> {
    let conn = open(&app)?;
    conn.execute("DELETE FROM journal", [])
        .map_err(|e| e.to_string())?;
    conn.execute("VACUUM", [])
        .map(|_| ())
        .map_err(|e| e.to_string())
}

/// Добавляет запрос в оффлайн-очередь (идемпотентно по `id`).
#[tauri::command]
pub fn outbox_add(app: AppHandle, entry: OutboxEntry) -> Result<(), String> {
    let conn = open(&app)?;
    insert_outbox(&conn, &entry)
}

/// Возвращает очередь исходящих запросов в порядке добавления.
#[tauri::command]
pub fn outbox_list(app: AppHandle) -> Result<Vec<OutboxEntry>, String> {
    let conn = open(&app)?;
    list_outbox(&conn)
}

/// Удаляет запрос из очереди (успешная отправка или необратимая ошибка).
#[tauri::command]
pub fn outbox_remove(app: AppHandle, id: String) -> Result<(), String> {
    let conn = open(&app)?;
    remove_outbox(&conn, &id)
}

/// Отмечает неудачную попытку отправки: увеличивает счётчик и пишет последнюю ошибку.
#[tauri::command]
pub fn outbox_fail(app: AppHandle, id: String, error: String) -> Result<(), String> {
    let conn = open(&app)?;
    fail_outbox(&conn, &id, &error)
}

/// Полностью очищает оффлайн-очередь.
#[tauri::command]
pub fn outbox_clear(app: AppHandle) -> Result<(), String> {
    let conn = open(&app)?;
    conn.execute("DELETE FROM outbox", [])
        .map_err(|e| e.to_string())?;
    Ok(())
}

const EVENT_RECEIVED: &str = "received";
const EVENT_CLASSIFIED: &str = "classified";
const EVENT_VERIFIED: &str = "verified";
const EVENT_REVISED: &str = "revised";

fn insert_memory_event(
    conn: &Connection,
    memory_id: &str,
    event_type: &str,
    actor: &str,
    detail: Option<&str>,
    created_at: &str,
) -> Result<(), String> {
    conn.execute(
        "INSERT INTO memory_events
             (id, memory_id, event_type, actor, detail, created_at)
          VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![
            format!("{}-{}", memory_id, event_type),
            memory_id,
            event_type,
            actor,
            detail,
            created_at,
        ],
    )
    .map(|_| ())
    .map_err(|e| e.to_string())
}

fn load_memories(conn: &Connection, user_id: &str) -> Result<Vec<Memory>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, user_id, conversation_id, kind, status, content, source, confidence,
                valid_until, created_at, updated_at
         FROM memories WHERE user_id = ?1 ORDER BY created_at DESC",
        )
        .map_err(|e| e.to_string())?;
    let rows = statement
        .query_map(params![user_id], |row| {
            Ok(Memory {
                id: row.get(0)?,
                user_id: row.get(1)?,
                conversation_id: row.get(2)?,
                kind: row.get(3)?,
                status: row.get(4)?,
                content: row.get(5)?,
                source: row.get(6)?,
                confidence: row.get(7)?,
                valid_until: row.get(8)?,
                created_at: row.get(9)?,
                updated_at: row.get(10)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}

fn list_memories_filtered(
    conn: &Connection,
    user_id: &str,
    conversation_id: Option<&str>,
    kind: Option<&str>,
    status: Option<&str>,
    limit: i64,
    offset: i64,
) -> Result<Vec<Memory>, String> {
    let all = load_memories(conn, user_id)?;
    let filtered: Vec<Memory> = all
        .into_iter()
        .filter(|m| {
            conversation_id
                .as_ref()
                .is_none_or(|c| m.conversation_id.as_deref() == Some(c))
                && kind.as_ref().is_none_or(|k| m.kind == *k)
                && status.as_ref().is_none_or(|s| m.status == *s)
        })
        .collect();
    let start = offset as usize;
    if start >= filtered.len() {
        return Ok(vec![]);
    }
    let end = (start + limit as usize).min(filtered.len());
    Ok(filtered[start..end].to_vec())
}

fn get_memory(conn: &Connection, id: &str, user_id: &str) -> Result<Option<Memory>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, user_id, conversation_id, kind, status, content, source, confidence,
                valid_until, created_at, updated_at
         FROM memories WHERE id = ?1 AND user_id = ?2",
        )
        .map_err(|e| e.to_string())?;
    let row = statement.query_row(params![id, user_id], |row| {
        Ok(Memory {
            id: row.get(0)?,
            user_id: row.get(1)?,
            conversation_id: row.get(2)?,
            kind: row.get(3)?,
            status: row.get(4)?,
            content: row.get(5)?,
            source: row.get(6)?,
            confidence: row.get(7)?,
            valid_until: row.get(8)?,
            created_at: row.get(9)?,
            updated_at: row.get(10)?,
        })
    });
    match row {
        Ok(memory) => Ok(Some(memory)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

fn load_memory_events(conn: &Connection, memory_id: &str) -> Result<Vec<MemoryEvent>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, memory_id, event_type, actor, detail, created_at
         FROM memory_events WHERE memory_id = ?1 ORDER BY created_at ASC",
        )
        .map_err(|e| e.to_string())?;
    let rows = statement
        .query_map(params![memory_id], |row| {
            Ok(MemoryEvent {
                id: row.get(0)?,
                memory_id: row.get(1)?,
                event_type: row.get(2)?,
                actor: row.get(3)?,
                detail: row.get(4)?,
                created_at: row.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}

fn insert_memory(conn: &Connection, entry: &Memory) -> Result<(), String> {
    conn.execute(
        "INSERT INTO memories
             (id, user_id, conversation_id, kind, status, content, source, confidence,
              valid_until, created_at, updated_at)
          VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
        params![
            entry.id,
            entry.user_id,
            entry.conversation_id,
            entry.kind,
            entry.status,
            entry.content,
            entry.source,
            entry.confidence,
            entry.valid_until,
            entry.created_at,
            entry.updated_at,
        ],
    )
    .map(|_| ())
    .map_err(|e| e.to_string())
}

/// Добавляет воспоминание в статусе `received` и фиксирует событие создания.
#[tauri::command]
pub fn memory_add(app: AppHandle, entry: Memory) -> Result<(), String> {
    let conn = open(&app)?;
    insert_memory(&conn, &entry)?;
    insert_memory_event(
        &conn,
        &entry.id,
        EVENT_RECEIVED,
        "system",
        None,
        &entry.created_at,
    )
}

/// Возвращает воспоминания пользователя с опциональными фильтрами и пагинацией.
#[tauri::command]
pub fn memory_list(
    app: AppHandle,
    user_id: String,
    conversation_id: Option<String>,
    kind: Option<String>,
    status: Option<String>,
    limit: i64,
    offset: i64,
) -> Result<Vec<Memory>, String> {
    let conn = open(&app)?;
    list_memories_filtered(
        &conn,
        &user_id,
        conversation_id.as_deref(),
        kind.as_deref(),
        status.as_deref(),
        limit,
        offset,
    )
}

/// Возвращает одно воспоминание пользователя.
#[tauri::command]
pub fn memory_get(app: AppHandle, id: String, user_id: String) -> Result<Option<Memory>, String> {
    let conn = open(&app)?;
    get_memory(&conn, &id, &user_id)
}

/// Классифицирует воспоминание (устанавливает тип и статус `classified`).
#[tauri::command]
pub fn memory_classify(
    app: AppHandle,
    id: String,
    user_id: String,
    kind: String,
    updated_at: String,
    event_created_at: String,
) -> Result<Option<Memory>, String> {
    let conn = open(&app)?;
    let _ = get_memory(&conn, &id, &user_id)?.ok_or_else(|| "memory not found".to_string())?;
    conn.execute(
        "UPDATE memories SET kind = ?1, status = ?2, updated_at = ?3 WHERE id = ?4 AND user_id = ?5",
        params![kind, "classified", updated_at, id, user_id],
    )
    .map_err(|e| e.to_string())?;
    insert_memory_event(
        &conn,
        &id,
        EVENT_CLASSIFIED,
        "user",
        Some(&format!("classified as {kind}")),
        &event_created_at,
    )?;
    get_memory(&conn, &id, &user_id)
}

/// Верифицирует воспоминание (статус `verified`).
#[tauri::command]
pub fn memory_verify(
    app: AppHandle,
    id: String,
    user_id: String,
    updated_at: String,
    event_created_at: String,
) -> Result<Option<Memory>, String> {
    let conn = open(&app)?;
    let _ = get_memory(&conn, &id, &user_id)?.ok_or_else(|| "memory not found".to_string())?;
    conn.execute(
        "UPDATE memories SET status = ?1, updated_at = ?2 WHERE id = ?3 AND user_id = ?4",
        params!["verified", updated_at, id, user_id],
    )
    .map_err(|e| e.to_string())?;
    insert_memory_event(&conn, &id, EVENT_VERIFIED, "user", None, &event_created_at)?;
    get_memory(&conn, &id, &user_id)
}

/// Исправляет воспоминание пользователем (статус `revised`).
#[tauri::command]
pub fn memory_correct(
    app: AppHandle,
    id: String,
    user_id: String,
    content: Option<String>,
    confidence: Option<f64>,
    updated_at: String,
    event_created_at: String,
) -> Result<Option<Memory>, String> {
    let conn = open(&app)?;
    let mut memory =
        get_memory(&conn, &id, &user_id)?.ok_or_else(|| "memory not found".to_string())?;
    if let Some(content) = content {
        memory.content = content;
    }
    if let Some(confidence) = confidence {
        memory.confidence = confidence;
    }
    conn.execute(
        "UPDATE memories SET content = ?1, confidence = ?2, status = 'revised', updated_at = ?3
         WHERE id = ?4 AND user_id = ?5",
        params![memory.content, memory.confidence, updated_at, id, user_id],
    )
    .map_err(|e| e.to_string())?;
    insert_memory_event(
        &conn,
        &id,
        EVENT_REVISED,
        "user",
        Some("corrected by user"),
        &event_created_at,
    )?;
    get_memory(&conn, &id, &user_id)
}

/// Удаляет воспоминание пользователя (события каскадно удаляются).
#[tauri::command]
pub fn memory_delete(app: AppHandle, id: String, user_id: String) -> Result<bool, String> {
    let conn = open(&app)?;
    let memory = get_memory(&conn, &id, &user_id)?;
    if memory.is_none() {
        return Ok(false);
    }
    conn.execute(
        "DELETE FROM memories WHERE id = ?1 AND user_id = ?2",
        params![id, user_id],
    )
    .map_err(|e| e.to_string())?;
    Ok(true)
}

/// Возвращает историю событий воспоминания.
#[tauri::command]
pub fn memory_events(app: AppHandle, memory_id: String) -> Result<Vec<MemoryEvent>, String> {
    let conn = open(&app)?;
    load_memory_events(&conn, &memory_id)
}

/// Сведения о локальном хранилище для экрана настроек.
#[tauri::command]
pub fn storage_info(app: AppHandle) -> Result<StorageInfo, String> {
    let path = db_path(&app)?;
    let conn = open(&app)?;
    let journal_entries: i64 = conn
        .query_row("SELECT COUNT(*) FROM journal", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    let outbox_entries: i64 = conn
        .query_row("SELECT COUNT(*) FROM outbox", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    let memory_entries: i64 = conn
        .query_row("SELECT COUNT(*) FROM memories", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    let settings_present: i64 = conn
        .query_row("SELECT COUNT(*) FROM settings", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    let schema_version: i64 = conn
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    let size_bytes = fs::metadata(&path).map(|meta| meta.len()).unwrap_or(0);
    Ok(StorageInfo {
        path: path.to_string_lossy().to_string(),
        schema_version,
        sqlite_version: rusqlite::version().to_string(),
        journal_entries,
        outbox_entries,
        memory_entries,
        size_bytes,
        settings_present: settings_present > 0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn memory() -> Connection {
        let conn = Connection::open_in_memory().expect("in-memory db");
        migrate(&conn).expect("migrate");
        conn
    }

    fn entry(index: usize) -> JournalEntry {
        JournalEntry {
            id: format!("entry-{index}"),
            at: format!("2026-10-18T10:{:02}:00Z", index % 60),
            kind: "test".to_string(),
            summary: format!("summary {index}"),
            detail: None,
        }
    }

    #[test]
    fn migrate_sets_schema_version_and_is_idempotent() {
        let conn = memory();
        migrate(&conn).expect("second migrate");
        let version: i64 = conn
            .query_row("PRAGMA user_version", [], |row| row.get(0))
            .expect("version");
        assert_eq!(version, SCHEMA_VERSION);
    }

    #[test]
    fn settings_roundtrip_drops_journal_blob() {
        let conn = memory();
        let payload = serde_json::json!({"apiBaseUrl": "http://x", "journal": [{"id": "a"}]});
        store_settings(&conn, &payload).expect("store");
        let stored = load_stored_settings(&conn).expect("load");
        assert_eq!(stored["apiBaseUrl"], "http://x");
        assert!(stored.get("journal").is_none());
    }

    #[test]
    fn journal_is_ordered_and_pruned_to_limit() {
        let conn = memory();
        for index in 0..(JOURNAL_LIMIT as usize + 5) {
            insert_journal(&conn, &entry(index)).expect("insert");
        }
        let stored = load_journal(&conn).expect("load");
        assert_eq!(stored.len(), JOURNAL_LIMIT as usize);
        assert!(stored.windows(2).all(|pair| pair[0].at >= pair[1].at));
    }

    #[test]
    fn journal_append_is_idempotent_by_id() {
        let conn = memory();
        let first = entry(1);
        insert_journal(&conn, &first).expect("insert");
        insert_journal(&conn, &first).expect("insert again");
        assert_eq!(load_journal(&conn).expect("load").len(), 1);
    }

    fn outbox_item(index: usize) -> OutboxEntry {
        OutboxEntry {
            id: format!("outbox-{index}"),
            at: format!("2026-10-18T11:{:02}:00Z", index % 60),
            method: "POST".to_string(),
            path: "/api/v1/conversations/x/messages/import".to_string(),
            body: Some("{\"content\":\"hi\"}".to_string()),
            idempotency_key: None,
            label: "import".to_string(),
            attempts: 0,
            last_error: None,
        }
    }

    #[test]
    fn outbox_roundtrip_is_ordered_and_removable() {
        let conn = memory();
        insert_outbox(&conn, &outbox_item(2)).expect("insert 2");
        insert_outbox(&conn, &outbox_item(1)).expect("insert 1");
        let stored = list_outbox(&conn).expect("list");
        assert_eq!(stored.len(), 2);
        assert!(stored[0].at <= stored[1].at);
        remove_outbox(&conn, "outbox-1").expect("remove");
        assert_eq!(list_outbox(&conn).expect("list").len(), 1);
    }

    #[test]
    fn outbox_fail_records_attempts_and_error() {
        let conn = memory();
        insert_outbox(&conn, &outbox_item(1)).expect("insert");
        fail_outbox(&conn, "outbox-1", "network down").expect("fail");
        fail_outbox(&conn, "outbox-1", "network down").expect("fail again");
        let stored = list_outbox(&conn).expect("list");
        assert_eq!(stored[0].attempts, 2);
        assert_eq!(stored[0].last_error.as_deref(), Some("network down"));
    }

    #[test]
    fn migrate_from_v1_adds_outbox() {
        let conn = Connection::open_in_memory().expect("in-memory db");
        conn.execute_batch(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
             CREATE TABLE journal (
                 id TEXT PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL,
                 summary TEXT NOT NULL, detail TEXT
             );",
        )
        .expect("v1 schema");
        conn.pragma_update(None, "user_version", 1).expect("set v1");
        migrate(&conn).expect("migrate to v2");
        let version: i64 = conn
            .query_row("PRAGMA user_version", [], |row| row.get(0))
            .expect("version");
        assert_eq!(version, SCHEMA_VERSION);
        insert_outbox(&conn, &outbox_item(1)).expect("outbox works after upgrade");
    }

    fn memory_item(index: usize) -> Memory {
        Memory {
            id: format!("mem-{index}"),
            user_id: "user-1".to_string(),
            conversation_id: Some(format!("conv-{index}")),
            kind: "fact".to_string(),
            status: "received".to_string(),
            content: format!("content {index}"),
            source: "message".to_string(),
            confidence: 0.5,
            valid_until: None,
            created_at: format!("2026-10-18T12:{:02}:00Z", index % 60),
            updated_at: format!("2026-10-18T12:{:02}:00Z", index % 60),
        }
    }

    fn db_classify_memory(
        conn: &Connection,
        id: &str,
        user_id: &str,
        kind: &str,
        updated_at: &str,
        event_created_at: &str,
    ) -> Result<Memory, String> {
        conn.execute(
            "UPDATE memories SET kind = ?1, status = 'classified', updated_at = ?2
             WHERE id = ?3 AND user_id = ?4",
            params![kind, updated_at, id, user_id],
        )
        .map_err(|e| e.to_string())?;
        insert_memory_event(
            conn,
            id,
            EVENT_CLASSIFIED,
            "user",
            Some(&format!("classified as {kind}")),
            event_created_at,
        )?;
        get_memory(conn, id, user_id)?.ok_or_else(|| "memory not found".to_string())
    }

    fn db_verify_memory(
        conn: &Connection,
        id: &str,
        user_id: &str,
        updated_at: &str,
        event_created_at: &str,
    ) -> Result<Memory, String> {
        conn.execute(
            "UPDATE memories SET status = 'verified', updated_at = ?1 WHERE id = ?2 AND user_id = ?3",
            params![updated_at, id, user_id],
        )
        .map_err(|e| e.to_string())?;
        insert_memory_event(conn, id, EVENT_VERIFIED, "user", None, event_created_at)?;
        get_memory(conn, id, user_id)?.ok_or_else(|| "memory not found".to_string())
    }

    fn db_correct_memory(
        conn: &Connection,
        id: &str,
        user_id: &str,
        content: Option<String>,
        confidence: Option<f64>,
        updated_at: &str,
        event_created_at: &str,
    ) -> Result<Memory, String> {
        let memory =
            get_memory(conn, id, user_id)?.ok_or_else(|| "memory not found".to_string())?;
        let content = content.unwrap_or(memory.content.clone());
        let confidence = confidence.unwrap_or(memory.confidence);
        conn.execute(
            "UPDATE memories SET content = ?1, confidence = ?2, status = 'revised', updated_at = ?3
             WHERE id = ?4 AND user_id = ?5",
            params![content, confidence, updated_at, id, user_id],
        )
        .map_err(|e| e.to_string())?;
        insert_memory_event(
            conn,
            id,
            EVENT_REVISED,
            "user",
            Some("corrected by user"),
            event_created_at,
        )?;
        let mut updated = memory;
        updated.content = content;
        updated.confidence = confidence;
        updated.status = "revised".to_string();
        Ok(updated)
    }

    fn db_delete_memory(conn: &Connection, id: &str, user_id: &str) -> Result<bool, String> {
        let rows = conn
            .execute(
                "DELETE FROM memories WHERE id = ?1 AND user_id = ?2",
                params![id, user_id],
            )
            .map_err(|e| e.to_string())?;
        Ok(rows > 0)
    }

    #[test]
    fn memory_add_and_list() {
        let conn = memory();
        let item = memory_item(1);
        insert_memory(&conn, &item).expect("insert");
        let stored =
            list_memories_filtered(&conn, "user-1", None, None, None, 50, 0).expect("list");
        assert_eq!(stored.len(), 1);
        assert_eq!(stored[0].kind, "fact");
        assert_eq!(stored[0].status, "received");
    }

    #[test]
    fn memory_get_and_foreign_missing() {
        let conn = memory();
        let item = memory_item(1);
        insert_memory(&conn, &item).expect("insert");
        assert!(get_memory(&conn, "mem-1", "user-1").expect("get").is_some());
        assert!(
            get_memory(&conn, "mem-1", "user-2")
                .expect("get foreign")
                .is_none()
        );
        assert!(
            get_memory(&conn, "mem-missing", "user-1")
                .expect("get missing")
                .is_none()
        );
    }

    #[test]
    fn memory_classify_verify_correct() {
        let conn = memory();
        let item = memory_item(1);
        insert_memory(&conn, &item).expect("insert");
        let updated_at = "2026-10-18T12:01:00Z";
        let event_at = "2026-10-18T12:01:00Z";
        let classified =
            db_classify_memory(&conn, "mem-1", "user-1", "preference", updated_at, event_at)
                .expect("classify");
        assert_eq!(classified.kind, "preference");
        assert_eq!(classified.status, "classified");
        let verified =
            db_verify_memory(&conn, "mem-1", "user-1", updated_at, event_at).expect("verify");
        assert_eq!(verified.status, "verified");
        let corrected = db_correct_memory(
            &conn,
            "mem-1",
            "user-1",
            Some("new content".to_string()),
            Some(0.9),
            updated_at,
            event_at,
        )
        .expect("correct");
        assert_eq!(corrected.content, "new content");
        assert_eq!(corrected.confidence, 0.9);
        assert_eq!(corrected.status, "revised");
        let events = load_memory_events(&conn, "mem-1").expect("events");
        assert!(events.iter().any(|e| e.event_type == "classified"));
        assert!(events.iter().any(|e| e.event_type == "verified"));
        assert!(events.iter().any(|e| e.event_type == "revised"));
    }

    #[test]
    fn memory_delete() {
        let conn = memory();
        let item = memory_item(1);
        insert_memory(&conn, &item).expect("insert");
        assert!(db_delete_memory(&conn, "mem-1", "user-1").expect("delete"));
        assert!(
            get_memory(&conn, "mem-1", "user-1")
                .expect("get after delete")
                .is_none()
        );
        assert!(!db_delete_memory(&conn, "mem-1", "user-1").expect("delete again"));
        assert!(!db_delete_memory(&conn, "mem-1", "user-2").expect("delete foreign"));
    }

    #[test]
    fn memory_filters_and_pagination() {
        let conn = memory();
        insert_memory(&conn, &memory_item(1)).expect("insert 1");
        let mut pref = memory_item(2);
        pref.kind = "preference".to_string();
        pref.status = "verified".to_string();
        insert_memory(&conn, &pref).expect("insert 2");
        let facts = list_memories_filtered(&conn, "user-1", None, Some("fact"), None, 50, 0)
            .expect("facts");
        assert_eq!(facts.len(), 1);
        let verified = list_memories_filtered(&conn, "user-1", None, None, Some("verified"), 50, 0)
            .expect("verified");
        assert_eq!(verified.len(), 1);
        let page = list_memories_filtered(&conn, "user-1", None, None, None, 1, 0).expect("page1");
        assert_eq!(page.len(), 1);
    }

    #[test]
    fn migrate_from_v2_adds_memories() {
        let conn = Connection::open_in_memory().expect("in-memory db");
        conn.execute_batch(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
             CREATE TABLE journal (
                 id TEXT PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL,
                 summary TEXT NOT NULL, detail TEXT
             );
             CREATE TABLE outbox (
                 id TEXT PRIMARY KEY, at TEXT NOT NULL, method TEXT NOT NULL,
                 path TEXT NOT NULL, body TEXT, idempotency_key TEXT,
                 label TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
                 last_error TEXT
             );",
        )
        .expect("v2 schema");
        conn.pragma_update(None, "user_version", 2).expect("set v2");
        migrate(&conn).expect("migrate to v3");
        let version: i64 = conn
            .query_row("PRAGMA user_version", [], |row| row.get(0))
            .expect("version");
        assert_eq!(version, SCHEMA_VERSION);
        insert_memory(&conn, &memory_item(1)).expect("memory works after upgrade");
    }
}
