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
            return
        if not columns["product_id"][3]:
            print("product_id уже допускает NULL. Изменения не требуются.")
            return

        backup_name = "stock_movements_before_nullable_product_id"
        backup_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (backup_name,)
        ).fetchone()

        # Keep the recovery copy in the same transaction as the table rebuild.
        # A previous failed attempt may have left an empty backup table behind.
        if not backup_exists:
            connection.execute(
                f'CREATE TABLE "{backup_name}" AS SELECT * FROM stock_movements WHERE 0'
            )
        backup_count = connection.execute(
            f'SELECT COUNT(*) FROM "{backup_name}"'
        ).fetchone()[0]
        source_count = connection.execute(
            "SELECT COUNT(*) FROM stock_movements"
        ).fetchone()[0]

        if backup_count == 0:
            names = [row[1] for row in info]
            quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
            connection.execute(
                f'INSERT INTO "{backup_name}" ({quoted}) SELECT {quoted} FROM stock_movements'
            )
            backup_count = connection.execute(
                f'SELECT COUNT(*) FROM "{backup_name}"'
            ).fetchone()[0]

        if backup_count != source_count:
            raise SystemExit(
                f"Остановлено для защиты данных: в основной таблице {source_count} строк, "
                f"в резервной {backup_count}. Таблицы не перестраивались."
            )

        # Remove only the purchase logging triggers that reference this table.
        for trigger in PURCHASE_TRIGGERS:
            connection.execute(f'DROP TRIGGER IF EXISTS "{trigger}"')

        definitions = []
        for row in info:
            name, declared_type, notnull, default_value, pk = row[1], row[2] or "", row[3], row[4], row[5]
            if name == "id":
                definitions.append('"id" INTEGER PRIMARY KEY AUTOINCREMENT')
                continue
            if name == "product_id":
                # Product links are optional for material/component inventory movements.
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

        rebuilt_count = connection.execute(
            "SELECT COUNT(*) FROM stock_movements_new"
        ).fetchone()[0]
        if rebuilt_count != source_count:
            raise RuntimeError(
                f"Проверка переноса не пройдена: было {source_count} строк, "
                f"перенесено {rebuilt_count}. Транзакция будет отменена."
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

    try:
        from inventory_purchase_bridge import initialize_purchase_stock_triggers
        initialize_purchase_stock_triggers()
    except Exception as exc:
        raise SystemExit(
            "Таблица исправлена и данные сохранены, но не удалось восстановить "
            f"триггеры закупок: {exc}. Не повторяй миграцию; сообщи эту ошибку."
        )

    check = sqlite3.connect(DB_PATH)
    try:
        product_id_info = next(
            row for row in check.execute("PRAGMA table_info(stock_movements)").fetchall()
            if row[1] == "product_id"
        )
        if product_id_info[3]:
            raise SystemExit("Проверка не пройдена: product_id всё ещё NOT NULL.")
        final_count = check.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]
        backup_count = check.execute(
            f'SELECT COUNT(*) FROM "{backup_name}"'
        ).fetchone()[0]
        if final_count != backup_count:
            raise SystemExit(
                f"Проверка не пройдена: основная таблица {final_count} строк, "
                f"резервная {backup_count}. Не повторяй миграцию."
            )
    finally:
        check.close()

    print("Готово: product_id теперь допускает NULL для движений материалов и комплектующих.")
    print(f"Резервная копия сохранена в таблице {backup_name}; строк: {backup_count}.")
    print("Количество строк проверено до и после переноса. Остатки не изменялись.")
    print("Триггеры журнала закупок восстановлены.")


if __name__ == "__main__":
    main()
