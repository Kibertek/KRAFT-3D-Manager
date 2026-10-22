"""
Безопасная миграция для производственного учёта KRAFT 3D Manager.

Запускать из корня проекта:
    py migrate_production_stock.py

Скрипт:
- создаёт резервную копию базы;
- добавляет таблицы рецептур, остатков открытых катушек и списаний по партиям;
- НЕ меняет существующие остатки и записи истории;
- повторный запуск безопасен.
"""
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"База не найдена: {DB_PATH}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_name(f"kraft3d_before_production_stock_{stamp}.db")
    shutil.copy2(DB_PATH, backup)
    print(f"Резервная копия: {backup}")

    con = sqlite3.connect(DB_PATH, timeout=30)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        required = {"products", "materials", "components", "production_batches", "stock_movements"}
        existing = {
            row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = required - existing
        if missing:
            raise RuntimeError("Не найдены обязательные таблицы: " + ", ".join(sorted(missing)))

        con.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS product_material_recipe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            grams_per_unit REAL NOT NULL CHECK (grams_per_unit > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, material_id),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY(material_id) REFERENCES materials(id)
        );

        CREATE TABLE IF NOT EXISTS product_component_recipe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            quantity_per_unit REAL NOT NULL CHECK (quantity_per_unit > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, component_id),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY(component_id) REFERENCES components(id)
        );

        CREATE TABLE IF NOT EXISTS material_spool_openings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            remaining_grams REAL NOT NULL CHECK (remaining_grams >= 0),
            note TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materials(id)
        );

        CREATE TABLE IF NOT EXISTS production_batch_consumption (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            item_type TEXT NOT NULL CHECK (item_type IN ('material','component')),
            item_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL CHECK (quantity > 0),
            unit TEXT NOT NULL,
            movement_id INTEGER,
            reversed INTEGER NOT NULL DEFAULT 0 CHECK (reversed IN (0,1)),
            reversal_movement_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(batch_id, item_type, item_id),
            FOREIGN KEY(batch_id) REFERENCES production_batches(id),
            FOREIGN KEY(movement_id) REFERENCES stock_movements(id),
            FOREIGN KEY(reversal_movement_id) REFERENCES stock_movements(id)
        );

        CREATE TABLE IF NOT EXISTS production_batch_waste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            waste_grams REAL NOT NULL CHECK (waste_grams > 0),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES production_batches(id),
            FOREIGN KEY(material_id) REFERENCES materials(id)
        );

        CREATE INDEX IF NOT EXISTS idx_product_material_recipe_product
            ON product_material_recipe(product_id);
        CREATE INDEX IF NOT EXISTS idx_product_component_recipe_product
            ON product_component_recipe(product_id);
        CREATE INDEX IF NOT EXISTS idx_open_spools_material
            ON material_spool_openings(material_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_batch_consumption_batch
            ON production_batch_consumption(batch_id);
        CREATE INDEX IF NOT EXISTS idx_batch_waste_batch
            ON production_batch_waste(batch_id);
        """)

        con.commit()
        print("Миграция выполнена.")
        print("Существующие остатки и движения не изменены.")
        print("Новые таблицы:")
        for row in con.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'product_material_recipe',
                'product_component_recipe',
                'material_spool_openings',
                'production_batch_consumption',
                'production_batch_waste'
            )
            ORDER BY name
        """):
            print(" -", row[0])
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
