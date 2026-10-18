from pathlib import Path

MAIN = Path(__file__).resolve().parent / "main.py"

text = MAIN.read_text(encoding="utf-8")

REPORT_IMPORT = "from reports_module import ReportsPage\n"
MARKETPLACE_IMPORT = "from marketplace_module import MarketplacePage\n"
FINANCE_IMPORT = "from ozon_finance_module import OzonFinancePage\n"

if MARKETPLACE_IMPORT not in text:
    if REPORT_IMPORT not in text:
        raise SystemExit("Не найден импорт ReportsPage в main.py.")
    text = text.replace(REPORT_IMPORT, REPORT_IMPORT + MARKETPLACE_IMPORT, 1)

if FINANCE_IMPORT not in text:
    anchor_import = MARKETPLACE_IMPORT if MARKETPLACE_IMPORT in text else REPORT_IMPORT
    text = text.replace(anchor_import, anchor_import + FINANCE_IMPORT, 1)

MARKETPLACE_DEFINITION = '            ("Маркетплейсы", MarketplacePage()),\n'
FINANCE_DEFINITION = '            ("Финансы Ozon", OzonFinancePage()),\n'
ANCHOR = '            ("Отчёты", ReportsPage()),\n'

if MARKETPLACE_DEFINITION not in text:
    if ANCHOR not in text:
        raise SystemExit("Не найден раздел «Отчёты» в меню main.py.")
    text = text.replace(ANCHOR, ANCHOR + MARKETPLACE_DEFINITION, 1)

if FINANCE_DEFINITION not in text:
    if MARKETPLACE_DEFINITION in text:
        text = text.replace(MARKETPLACE_DEFINITION, MARKETPLACE_DEFINITION + FINANCE_DEFINITION, 1)
    elif ANCHOR in text:
        text = text.replace(ANCHOR, ANCHOR + FINANCE_DEFINITION, 1)
    else:
        raise SystemExit("Не найдено место для раздела «Финансы Ozon» в main.py.")

OLD_REPORT = '''        elif isinstance(page, ReportsPage):
            page.load_report()
'''
NEW_REPORT = '''        elif isinstance(page, ReportsPage):
            page.load_report()
        elif isinstance(page, MarketplacePage):
            page.load_data()
        elif isinstance(page, OzonFinancePage):
            page.load_data()
'''

if "elif isinstance(page, OzonFinancePage):" not in text:
    if OLD_REPORT not in text:
        raise SystemExit("Не найден обработчик ReportsPage в change_page().")
    text = text.replace(OLD_REPORT, NEW_REPORT, 1)

text = text.replace('KRAFT 3D Manager\\nv0.4.0', 'KRAFT 3D Manager\\nv0.6.0')
text = text.replace('KRAFT 3D Manager\\nv0.5.0', 'KRAFT 3D Manager\\nv0.6.0')
text = text.replace('app.setApplicationVersion("0.4.0")', 'app.setApplicationVersion("0.6.0")')
text = text.replace('app.setApplicationVersion("0.5.0")', 'app.setApplicationVersion("0.6.0")')

MAIN.write_text(text, encoding="utf-8")
print("Готово. main.py подключён к разделам «Маркетплейсы» и «Финансы Ozon».")
