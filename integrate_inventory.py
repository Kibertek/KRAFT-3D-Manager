from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAIN_FILE = ROOT / "main.py"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count == 0:
        raise RuntimeError(f"Не найден участок main.py для изменения: {label}")
    if count > 1:
        raise RuntimeError(f"Участок main.py найден несколько раз: {label}")
    return text.replace(old, new, 1)


def patch_main():
    text = MAIN_FILE.read_text(encoding="utf-8")

    if "from inventory_module import InventoryPage, initialize_inventory_tables" not in text:
        text = replace_once(
            text,
            "from production_module import ProductionPage\n",
            "from production_module import ProductionPage\n"
            "from inventory_module import InventoryPage, initialize_inventory_tables\n"
            "from inventory_purchase_bridge import initialize_purchase_stock_triggers\n",
            "импорты склада",
        )

    if '("Склад", InventoryPage()),' not in text:
        text = replace_once(
            text,
            '            ("Закупки", PurchasesPage()),\n',
            '            ("Закупки", PurchasesPage()),\n'
            '            ("Склад", InventoryPage()),\n',
            "страница склада",
        )

    if '            "Склад": InventoryPage,\n' not in text:
        text = replace_once(
            text,
            '            "Закупки": PurchasesPage,\n',
            '            "Закупки": PurchasesPage,\n'
            '            "Склад": InventoryPage,\n',
            "фабрика склада",
        )

    text = replace_once(
        text,
        '("Склад", ["Изделия", "Производство", "Материалы", "Комплектующие", "Упаковка", "Закупки"]),',
        '("Склад", ["Склад", "Изделия", "Производство", "Материалы", "Комплектующие", "Упаковка", "Закупки"]),',
        "пункт склада в меню",
    ) if '("Склад", ["Склад", "Изделия", "Производство", "Материалы", "Комплектующие", "Упаковка", "Закупки"]),' not in text else text

    if "elif isinstance(page, InventoryPage):" not in text:
        text = replace_once(
            text,
            '        elif isinstance(page, PackagingPage):\n',
            '        elif isinstance(page, InventoryPage):\n'
            '            page.load_stock()\n'
            '        elif isinstance(page, PackagingPage):\n',
            "обновление страницы склада",
        )

    if "initialize_purchase_stock_triggers()" not in text:
        text = replace_once(
            text,
            "    initialize_database()\n",
            "    initialize_database()\n"
            "    initialize_inventory_tables()\n"
            "    initialize_purchase_stock_triggers()\n",
            "инициализация складского журнала",
        )

    MAIN_FILE.write_text(text, encoding="utf-8")


def main():
    if not MAIN_FILE.exists():
        raise SystemExit(f"Не найден файл: {MAIN_FILE}")

    patch_main()
    print("Готово: main.py подключён к разделу «Склад» и журналу движений закупок.")
    print("База данных не пересоздаётся. Добавляются только новые таблицы/триггеры.")


if __name__ == "__main__":
    main()
