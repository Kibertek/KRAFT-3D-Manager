import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"

# Missing columns are added in place. Existing columns and rows are preserved.
REQUIRED_COLUMNS = {
    "movement_date": "TEXT NOT NULL DEFAULT ''",
    "item_type": "TEXT NOT NULL DEFAULT 'component'",
    "item_id": "INTEGER NOT NULL DEFAULT 0",
    "item_name": "TEXT NOT NULL DEFAULT ''",
    "movement_type": "TEXT NOT NULL DEFAULT ''",
    "quantity": "REAL NOT NULL DEFAULT 0",
    "unit": "TEXT DEFAULT ''",
    "balance_after": "REAL NOT NULL DEFAULT 0",
    "source": "TEXT DEFAULT ''",
    "source_id": "INTEGER",
    "comment": "TEXT DEFAULT ''",
    "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
}


def main():
    if not DB_PATH.exists():
        raise SystemExit(
            f"База данных не найдена: {DB_PATH}\n"
            "Запусти программу из корневой папки проекта."
        )

    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("PRAGMA busy_timeout = 5000")
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stock_movements'"
        ).fetchone()

        if not table:
            connection.execute("""
                CREATE TABLE stock_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movement_date TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    movement_type TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT DEFAULT '',
                    balance_after REAL NOT NULL DEFAULT 0,
                    source TEXT DEFAULT '',
                    source_id INTEGER,
                    comment TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Создана таблица журнала складских движений.")
        else:
            existing = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(stock_movements)"
                ).fetchall()
            }
            added = []
            for column, definition in REQUIRED_COLUMNS.items():
                if column not in existing:
                    connection.execute(
                        f'ALTER TABLE stock_movements ADD COLUMN "{column}" {definition}'
                    )
                    added.append(column)

            if added:
                print("Добавлены недостающие столбцы: " + ", ".join(added))
            else:
                print("Структура stock_movements уже совместима.")

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_movements_date
            ON stock_movements(movement_date DESC, id DESC)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_movements_item
            ON stock_movements(item_type, item_id)
        """)
        connection.commit()
        print("Миграция завершена. Существующие строки не удалялись.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
