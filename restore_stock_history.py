
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB = Path("data/kraft3d.db")
DATA = DB.parent


def main():
    if not DB.exists():
        raise RuntimeError("База данных не найдена.")

    backups = list(DATA.glob("kraft3d_before_stock_history_*.db"))
    if not backups:
        raise RuntimeError("Не найдена исходная резервная копия.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DATA / f"kraft3d_stock_repair_{stamp}.db"
    shutil.copy2(DB, backup)

    check = sqlite3.connect(backup)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Резервная копия повреждена.")
        if not check.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='purchases'
        """).fetchone():
            raise RuntimeError("В резервной копии нет таблицы purchases.")
    finally:
        check.close()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Основная база не прошла проверку.")

        con.execute("BEGIN IMMEDIATE")
        purchases = con.execute("""
            SELECT id, purchase_date, item_type, item_id, item_name,
                   quantity, unit, supplier, notes
            FROM purchases ORDER BY purchase_date, id
        """).fetchall()

        added = 0
        skipped = 0

        for p in purchases:
            exists = con.execute("""
                SELECT 1 FROM stock_movements
                WHERE source = 'Закупки'
                  AND source_id = ?
                  AND movement_type = 'Закупка'
                  AND item_type = ?
                  AND item_id = ?
                LIMIT 1
            """, (str(p["id"]), p["item_type"], p["item_id"])).fetchone()

            if exists:
                skipped += 1
                continue

            if p["item_type"] == "material":
                row = con.execute(
                    "SELECT spool_count FROM materials WHERE id=?",
                    (p["item_id"],)
                ).fetchone()
                balance = row["spool_count"] if row else 0
            else:
                row = con.execute(
                    "SELECT quantity FROM components WHERE id=?",
                    (p["item_id"],)
                ).fetchone()
                balance = row["quantity"] if row else 0

            details = [
                "Историческая запись восстановлена.",
                "Остаток на дату закупки неизвестен."
            ]
            if p["supplier"]:
                details.append("Поставщик: " + str(p["supplier"]))
            if p["notes"]:
                details.append(str(p["notes"]))

            con.execute("""
                INSERT INTO stock_movements (
                    product_id, movement_type, quantity, movement_date,
                    source_type, source_id, notes, item_type, item_id,
                    item_name, unit, balance_after, source, comment
                ) VALUES (
                    NULL, 'Закупка', ?, ?, 'purchase', ?, ?,
                    ?, ?, ?, ?, ?, 'Закупки', ?
                )
            """, (
                p["quantity"], p["purchase_date"], str(p["id"]),
                "Историческая закупка", p["item_type"], p["item_id"],
                p["item_name"], p["unit"] or "", balance,
                " | ".join(details)
            ))
            added += 1

        con.commit()
        print("Восстановление завершено.")
        print("Резервная копия:", backup)
        print("Всего закупок:", len(purchases))
        print("Добавлено записей:", added)
        print("Пропущено:", skipped)
        print("Остатки склада не изменялись.")

    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
