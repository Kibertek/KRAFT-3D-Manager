from pathlib import Path

MAIN = Path(__file__).resolve().parent / "main.py"

text = MAIN.read_text(encoding="utf-8")

IMPORT_LINE = "from marketplace_module import MarketplacePage\n"
REPORT_IMPORT = "from reports_module import ReportsPage\n"

if IMPORT_LINE not in text:
    if REPORT_IMPORT not in text:
        raise SystemExit("Не найден импорт ReportsPage в main.py.")
    text = text.replace(REPORT_IMPORT, REPORT_IMPORT + IMPORT_LINE, 1)

DEFINITION = '            ("Маркетплейсы", MarketplacePage()),\n'
ANCHOR = '            ("Отчёты", ReportsPage()),\n'
if DEFINITION not in text:
    if ANCHOR not in text:
        raise SystemExit("Не найден раздел «Отчёты» в меню main.py.")
    text = text.replace(ANCHOR, ANCHOR + DEFINITION, 1)

OLD = '''        elif isinstance(page, ReportsPage):
            page.load_report()
'''
NEW = '''        elif isinstance(page, ReportsPage):
            page.load_report()
        elif isinstance(page, MarketplacePage):
            page.load_data()
'''
if NEW not in text:
    if OLD not in text:
        raise SystemExit("Не найден обработчик ReportsPage в change_page().")
    text = text.replace(OLD, NEW, 1)

text = text.replace('KRAFT 3D Manager\\nv0.4.0', 'KRAFT 3D Manager\\nv0.5.0')
text = text.replace('app.setApplicationVersion("0.4.0")', 'app.setApplicationVersion("0.5.0")')

MAIN.write_text(text, encoding="utf-8")
print("Готово. main.py подключён к разделу «Маркетплейсы».")
