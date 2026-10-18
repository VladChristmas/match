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

const SCHEMA_VERSION: i64 = 2;
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
}
