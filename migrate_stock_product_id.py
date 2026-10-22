import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"

PURCHASE_TRIGGERS = (
    "trg_purchase_stock_movement_insert",
    "trg_purchase_stock_movement_delete",
    "trg_purchase_stock_movement_update_same_item",
    "trg_purchase_stock_movement_update_different_item",
)


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"База данных не найдена: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = OFF")
        info = connection.execute("PRAGMA table_info(stock_movements)").fetchall()
        if not info:
            raise SystemExit("Таблица stock_movements не найдена. Сначала запусти migrate_inventory_schema.py.")

        columns = {row[1]: row for row in info}
        if "product_id" not in columns:
            print("Столбец product_id отсутствует. Перестройка таблицы не требуется.")
            connection.close()
            return
        if not columns["product_id"][3]:
            print("product_id уже допускает NULL. Изменения не требуются.")
            connection.close()
            return

        backup_name = "stock_movements_before_nullable_product_id"
        existing_backup = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (backup_name,)
        ).fetchone()
        if existing_backup:
            raise SystemExit(
                f"Таблица {backup_name} уже существует. Остановлено для защиты данных. "
                "Не удаляй её вручную; сначала проверь её содержимое."
            )

        # Backup the existing rows before changing the table.
        connection.execute(f'CREATE TABLE "{backup_name}" AS SELECT * FROM stock_movements')

        # SQLite triggers reference the table by name. Drop only the known purchase
        # logging triggers during the rebuild; they are restored after the commit.
        for trigger in PURCHASE_TRIGGERS:
            connection.execute(f'DROP TRIGGER IF EXISTS "{trigger}"')

        definitions = []
        for row in info:
            name, declared_type, notnull, default_value, pk = row[1], row[2] or "", row[3], row[4], row[5]
            if name == "id":
                definitions.append('"id" INTEGER PRIMARY KEY AUTOINCREMENT')
                continue
            if name == "product_id":
                definitions.append('"product_id" INTEGER REFERENCES products(id)')
                continue
            definition = '"' + name.replace('"', '""') + '" ' + declared_type
            if notnull:
                definition += " NOT NULL"
            if default_value is not None:
                definition += " DEFAULT " + str(default_value)
            definitions.append(definition)

        connection.execute("DROP TABLE IF EXISTS stock_movements_new")
        connection.execute("CREATE TABLE stock_movements_new (" + ", ".join(definitions) + ")")
        names = [row[1] for row in info]
        quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
        connection.execute(
            f"INSERT INTO stock_movements_new ({quoted}) SELECT {quoted} FROM stock_movements"
        )
        connection.execute("DROP TABLE stock_movements")
        connection.execute("ALTER TABLE stock_movements_new RENAME TO stock_movements")

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_movements_date
            ON stock_movements(movement_date DESC, id DESC)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_movements_item
            ON stock_movements(item_type, item_id)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    # Reinstall purchase logging triggers only after the table replacement commits.
    # Existing trigger definitions are managed by the bridge module.
    try:
        from inventory_purchase_bridge import initialize_purchase_stock_triggers
        initialize_purchase_stock_triggers()
    except Exception as exc:
        raise SystemExit(
            "Таблица исправлена и данные сохранены, но не удалось восстановить "
            f"триггеры закупок: {exc}. Не повторяй миграцию; сообщи эту ошибку."
        )

    print("Готово: product_id теперь допускает NULL для движений материалов и комплектующих.")
    print(f"Резервная копия старых строк создана в таблице {backup_name}.")
    print("Все исходные строки перенесены; остатки не изменялись.")
    print("Триггеры журнала закупок восстановлены.")


if __name__ == "__main__":
    main()
