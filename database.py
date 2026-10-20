"""
Единый слой доступа к SQLite для KRAFT 3D Manager.

Принципы:
- не удалять и не пересоздавать существующую базу;
- включать WAL, внешние ключи и ожидание блокировки;
- создавать согласованную резервную копию перед миграциями;
- миграции только добавочные и с явной версией.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "kraft3d.db"
BACKUP_DIR = DATA_DIR / "backups"
BUSY_TIMEOUT_MS = 30_000


def get_connection():
    """Создаёт соединение с едиными настройками безопасности."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def _has_user_tables(connection):
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def create_backup(connection=None, reason="manual"):
    """
    Создаёт согласованную SQLite-копию через backup API.
    Не копирует файл базы обычным копированием, потому что WAL может содержать
    ещё не перенесённые в основной файл изменения.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_reason = "".join(
        character if character.isalnum() or character in "_-" else "_"
        for character in str(reason)
    )
    backup_path = BACKUP_DIR / f"kraft3d_{timestamp}_{safe_reason}.db"

    own_connection = connection is None
    source = connection or get_connection()
    target = None
    try:
        target = sqlite3.connect(backup_path)
        source.backup(target)
        target.commit()
    except Exception:
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass
        raise
    finally:
        if target is not None:
            target.close()
        if own_connection:
            source.close()

    return backup_path


def initialize_database():
    """
    Включает WAL и создаёт журнал версий.
    При подключении к уже существующей базе делает её резервную копию
    до добавления служебной таблицы журнала.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    database_existed = DB_PATH.exists() and DB_PATH.stat().st_size > 0

    connection = sqlite3.connect(DB_PATH, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        has_migration_table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
            """
        ).fetchone() is not None

        if database_existed and not has_migration_table and _has_user_tables(connection):
            backup_path = create_backup(connection, "before_database_foundation")
            print(f"Резервная копия базы создана: {backup_path}")

        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            INSERT OR IGNORE INTO schema_migrations (version, description)
            VALUES (?, ?)
        """, ("0001_database_foundation", "Журнал миграций и единые настройки SQLite"))
        connection.commit()
    finally:
        connection.close()


def applied_migrations():
    """Возвращает версии миграций, записанные в журнале."""
    with get_connection() as connection:
        try:
            rows = connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        except sqlite3.OperationalError:
            return set()
    return {row["version"] for row in rows}


def apply_migrations(migrations: Iterable[tuple[str, str, Callable]]):
    """
    Применяет миграции по порядку.
    migrations: последовательность (version, description, callback).
    callback получает активное соединение.
    Перед каждой новой миграцией создаётся резервная копия.
    """
    initialize_database()

    for version, description, migration in migrations:
        with get_connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()
        if exists:
            continue

        backup_path = create_backup(reason=f"before_migration_{version}")
        try:
            with get_connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                migration(connection)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, description)
                    VALUES (?, ?)
                    """,
                    (version, description),
                )
                connection.commit()
        except Exception:
            # Контекст соединения откатит незавершённую транзакцию при ошибке.
            raise RuntimeError(
                f"Миграция {version} не выполнена. "
                f"Резервная копия сохранена: {backup_path}"
            )
