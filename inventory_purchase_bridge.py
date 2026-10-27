import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_purchase_stock_triggers():
    """Logs purchase stock changes without changing stock itself.

    purchases_module.py remains responsible for changing the actual stock.
    These triggers only append records to stock_movements, so a purchase
    cannot increase the stock twice.
    """
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
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

        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_purchase_stock_movement_insert
            AFTER INSERT ON purchases
            BEGIN
                INSERT INTO stock_movements (
                    movement_date, item_type, item_id, item_name,
                    movement_type, quantity, unit, balance_after,
                    source, source_id, comment
                )
                SELECT
                    NEW.purchase_date,
                    NEW.item_type,
                    NEW.item_id,
                    NEW.item_name,
                    'Закупка',
                    NEW.quantity,
                    NEW.unit,
                    CASE
                        WHEN NEW.item_type = 'material'
                            THEN COALESCE((SELECT spool_count FROM materials WHERE id = NEW.item_id), 0)
                        ELSE COALESCE((SELECT quantity FROM components WHERE id = NEW.item_id), 0)
                    END,
                    'Закупки',
                    NEW.id,
                    TRIM(
                        COALESCE(NEW.supplier, '') ||
                        CASE
                            WHEN COALESCE(NEW.notes, '') <> ''
                                THEN CASE WHEN COALESCE(NEW.supplier, '') <> '' THEN ' | ' ELSE '' END || NEW.notes
                            ELSE ''
                        END
                    );
            END
        """)

        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_purchase_stock_movement_delete
            AFTER DELETE ON purchases
            BEGIN
                INSERT INTO stock_movements (
                    movement_date, item_type, item_id, item_name,
                    movement_type, quantity, unit, balance_after,
                    source, source_id, comment
                )
                SELECT
                    DATE('now'),
                    OLD.item_type,
                    OLD.item_id,
                    OLD.item_name,
                    'Удаление закупки',
                    -OLD.quantity,
                    OLD.unit,
                    CASE
                        WHEN OLD.item_type = 'material'
                            THEN COALESCE((SELECT spool_count FROM materials WHERE id = OLD.item_id), 0)
                        ELSE COALESCE((SELECT quantity FROM components WHERE id = OLD.item_id), 0)
                    END,
                    'Закупки',
                    OLD.id,
                    'Остаток уменьшен после удаления закупки'
                ;
            END
        """)

        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_purchase_stock_movement_update_same_item
            AFTER UPDATE OF item_type, item_id, item_name, quantity, unit, purchase_date, supplier, notes ON purchases
            WHEN OLD.item_type = NEW.item_type AND OLD.item_id = NEW.item_id
            BEGIN
                INSERT INTO stock_movements (
                    movement_date, item_type, item_id, item_name,
                    movement_type, quantity, unit, balance_after,
                    source, source_id, comment
                )
                SELECT
                    NEW.purchase_date,
                    NEW.item_type,
                    NEW.item_id,
                    NEW.item_name,
                    'Изменение закупки',
                    NEW.quantity - OLD.quantity,
                    NEW.unit,
                    CASE
                        WHEN NEW.item_type = 'material'
                            THEN COALESCE((SELECT spool_count FROM materials WHERE id = NEW.item_id), 0)
                        ELSE COALESCE((SELECT quantity FROM components WHERE id = NEW.item_id), 0)
                    END,
                    'Закупки',
                    NEW.id,
                    'Закупка отредактирована'
                WHERE ABS(NEW.quantity - OLD.quantity) > 0.000001;
            END
        """)

        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_purchase_stock_movement_update_different_item
            AFTER UPDATE OF item_type, item_id, item_name, quantity, unit, purchase_date, supplier, notes ON purchases
            WHEN OLD.item_type <> NEW.item_type OR OLD.item_id <> NEW.item_id
            BEGIN
                INSERT INTO stock_movements (
                    movement_date, item_type, item_id, item_name,
                    movement_type, quantity, unit, balance_after,
                    source, source_id, comment
                )
                SELECT
                    NEW.purchase_date,
                    OLD.item_type,
                    OLD.item_id,
                    OLD.item_name,
                    'Изменение закупки',
                    -OLD.quantity,
                    OLD.unit,
                    CASE
                        WHEN OLD.item_type = 'material'
                            THEN COALESCE((SELECT spool_count FROM materials WHERE id = OLD.item_id), 0)
                        ELSE COALESCE((SELECT quantity FROM components WHERE id = OLD.item_id), 0)
                    END,
                    'Закупки',
                    NEW.id,
                    'Старая позиция закупки отменена'
                ;

                INSERT INTO stock_movements (
                    movement_date, item_type, item_id, item_name,
                    movement_type, quantity, unit, balance_after,
                    source, source_id, comment
                )
                SELECT
                    NEW.purchase_date,
                    NEW.item_type,
                    NEW.item_id,
                    NEW.item_name,
                    'Изменение закупки',
                    NEW.quantity,
                    NEW.unit,
                    CASE
                        WHEN NEW.item_type = 'material'
                            THEN COALESCE((SELECT spool_count FROM materials WHERE id = NEW.item_id), 0)
                        ELSE COALESCE((SELECT quantity FROM components WHERE id = NEW.item_id), 0)
                    END,
                    'Закупки',
                    NEW.id,
                    'Новая позиция закупки добавлена'
                ;
            END
        """)

        connection.commit()


if __name__ == "__main__":
    initialize_purchase_stock_triggers()
    print("Триггеры журнала закупок установлены.")
