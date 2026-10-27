import sqlite3

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QComboBox, QTextEdit, QMessageBox, QAbstractItemView, QDoubleSpinBox,
    QDateEdit, QTabWidget, QListWidget, QListWidgetItem
)

from database import get_connection
from PySide6.QtWidgets import QApplication


def initialize_equipment_tables():
    """Добавляет поля оборудования и журнал обслуживания без пересоздания данных."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                power REAL DEFAULT 0,
                purchase_price REAL DEFAULT 0,
                resource_hours REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(printers)").fetchall()
        }
        additions = {
            "manufacturer": "TEXT DEFAULT ''",
            "model": "TEXT DEFAULT ''",
            "serial_number": "TEXT DEFAULT ''",
            "purchase_date": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'Работает'",
            "hours_used": "REAL DEFAULT 0",
            "notes": "TEXT DEFAULT ''",
        }
        for name, column_type in additions.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE printers ADD COLUMN {name} {column_type}"
                )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS printer_maintenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                printer_id INTEGER NOT NULL,
                service_date TEXT NOT NULL,
                service_type TEXT NOT NULL DEFAULT 'Обслуживание',
                hours_at_service REAL DEFAULT 0,
                cost REAL DEFAULT 0,
                description TEXT DEFAULT '',
                parts_used TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(printer_id) REFERENCES printers(id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS component_printer_compatibility (
                component_id INTEGER NOT NULL,
                printer_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(component_id, printer_id),
                FOREIGN KEY(component_id) REFERENCES components(id) ON DELETE CASCADE,
                FOREIGN KEY(printer_id) REFERENCES printers(id) ON DELETE CASCADE
            )
        """)
        # Старый модуль комплектующих пока использует отдельное соединение SQLite,
        # где внешние ключи могут быть выключены. Триггер гарантирует очистку связей.
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_components_delete_printer_compatibility
            AFTER DELETE ON components
            BEGIN
                DELETE FROM component_printer_compatibility
                WHERE component_id = OLD.id;
            END
        """)


def money(value):
    return f"{float(value or 0):,.2f} ₽".replace(",", " ").replace(".", ",")


def number(value, decimals=1):
    return f"{float(value or 0):,.{decimals}f}".replace(",", " ").replace(".", ",")


class PrinterDialog(QDialog):
    def __init__(self, parent=None, printer=None):
        super().__init__(parent)
        self.printer = printer
        self.setWindowTitle("Редактирование принтера" if printer else "Новый принтер")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например, KRAFT Printer")
        self.manufacturer_input = QLineEdit()
        self.model_input = QLineEdit()
        self.serial_input = QLineEdit()
        self.purchase_date_input = QDateEdit()
        self.purchase_date_input.setCalendarPopup(True)
        self.purchase_date_input.setDisplayFormat("dd.MM.yyyy")
        self.purchase_date_input.setDate(QDate.currentDate())
        self.purchase_price_input = self.make_number()
        self.power_input = self.make_number()
        self.resource_input = self.make_number()
        self.hours_input = self.make_number()
        self.status_input = QComboBox()
        self.status_input.addItems(["Работает", "На обслуживании", "Не работает", "Продан"])
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(85)

        form.addRow("Название *", self.name_input)
        form.addRow("Производитель", self.manufacturer_input)
        form.addRow("Модель", self.model_input)
        form.addRow("Серийный номер", self.serial_input)
        form.addRow("Дата покупки", self.purchase_date_input)
        form.addRow("Стоимость покупки, ₽", self.purchase_price_input)
        form.addRow("Мощность, Вт", self.power_input)
        form.addRow("Ресурс до обслуживания, ч", self.resource_input)
        form.addRow("Наработка, ч", self.hours_input)
        form.addRow("Статус", self.status_input)
        form.addRow("Примечания", self.notes_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Отмена")
        save = QPushButton("Сохранить")
        save.setObjectName("accentButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        if printer:
            self.name_input.setText(printer["name"] or "")
            self.manufacturer_input.setText(printer["manufacturer"] or "")
            self.model_input.setText(printer["model"] or "")
            self.serial_input.setText(printer["serial_number"] or "")
            date_text = (printer["purchase_date"] or "")[:10]
            parsed = QDate.fromString(date_text, "yyyy-MM-dd")
            if parsed.isValid():
                self.purchase_date_input.setDate(parsed)
            self.purchase_price_input.setValue(printer["purchase_price"] or 0)
            self.power_input.setValue(printer["power"] or 0)
            self.resource_input.setValue(printer["resource_hours"] or 0)
            self.hours_input.setValue(printer["hours_used"] or 0)
            self.status_input.setCurrentText(printer["status"] or "Работает")
            self.notes_input.setPlainText(printer["notes"] or "")

    @staticmethod
    def make_number():
        field = QDoubleSpinBox()
        field.setRange(0, 999999999)
        field.setDecimals(2)
        field.setKeyboardTracking(False)
        return field

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Не указано название", "Укажи название принтера.")
            self.name_input.setFocus()
            return
        self.data = {
            "name": name,
            "manufacturer": self.manufacturer_input.text().strip(),
            "model": self.model_input.text().strip(),
            "serial_number": self.serial_input.text().strip(),
            "purchase_date": self.purchase_date_input.date().toString("yyyy-MM-dd"),
            "purchase_price": self.purchase_price_input.value(),
            "power": self.power_input.value(),
            "resource_hours": self.resource_input.value(),
            "hours_used": self.hours_input.value(),
            "status": self.status_input.currentText(),
            "notes": self.notes_input.toPlainText().strip(),
        }
        try:
            with get_connection() as connection:
                if self.printer:
                    connection.execute("""
                        UPDATE printers SET name=?, manufacturer=?, model=?, serial_number=?,
                            purchase_date=?, purchase_price=?, power=?, resource_hours=?,
                            hours_used=?, status=?, notes=? WHERE id=?
                    """, (*self.data.values(), self.printer["id"]))
                else:
                    connection.execute("""
                        INSERT INTO printers (
                            name, manufacturer, model, serial_number, purchase_date,
                            purchase_price, power, resource_hours, hours_used, status, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, tuple(self.data.values()))
            self.accept()
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка сохранения", str(error))


class MaintenanceDialog(QDialog):
    def __init__(self, parent, printers):
        super().__init__(parent)
        self.setWindowTitle("Добавить обслуживание")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.printer_input = QComboBox()
        for printer in printers:
            self.printer_input.addItem(
                f'{printer["name"]} ({printer["model"] or "модель не указана"})',
                int(printer["id"])
            )
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd.MM.yyyy")
        self.date_input.setDate(QDate.currentDate())
        self.type_input = QComboBox()
        self.type_input.addItems([
            "Регламентное обслуживание", "Замена сопла", "Замена хотенда",
            "Ремонт", "Калибровка", "Чистка", "Замена другой запчасти", "Другое"
        ])
        self.hours_input = QDoubleSpinBox()
        self.hours_input.setRange(0, 99999999)
        self.hours_input.setDecimals(1)
        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 999999999)
        self.cost_input.setDecimals(2)
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.parts_input = QLineEdit()
        self.parts_input.setPlaceholderText("Например, сопло 0,4 мм")
        form.addRow("Принтер", self.printer_input)
        form.addRow("Дата", self.date_input)
        form.addRow("Тип работ", self.type_input)
        form.addRow("Наработка на момент работ, ч", self.hours_input)
        form.addRow("Стоимость, ₽", self.cost_input)
        form.addRow("Запчасти", self.parts_input)
        form.addRow("Описание", self.description_input)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Отмена")
        save = QPushButton("Сохранить")
        save.setObjectName("accentButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def save(self):
        if self.printer_input.currentData() is None:
            QMessageBox.warning(self, "Нет принтера", "Сначала добавь принтер.")
            return
        self.data = (
            int(self.printer_input.currentData()),
            self.date_input.date().toString("yyyy-MM-dd"),
            self.type_input.currentText(),
            self.hours_input.value(),
            self.cost_input.value(),
            self.description_input.toPlainText().strip(),
            self.parts_input.text().strip(),
        )
        try:
            with get_connection() as connection:
                connection.execute("""
                    INSERT INTO printer_maintenance (
                        printer_id, service_date, service_type, hours_at_service,
                        cost, description, parts_used
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, self.data)
            self.accept()
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка сохранения", str(error))


class CompatibilityDialog(QDialog):
    def __init__(self, parent, components, printers, component_id=None):
        super().__init__(parent)
        self.setWindowTitle("Совместимость комплектующего")
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #202020;
                color: #eeeeee;
            }
            QLabel {
                color: #eeeeee;
                background-color: transparent;
            }
            QComboBox {
                background-color: #303030;
                color: #eeeeee;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 6px;
                min-height: 22px;
            }
            QComboBox QAbstractItemView {
                background-color: #303030;
                color: #eeeeee;
                selection-background-color: #75421e;
                selection-color: #ffffff;
                border: 1px solid #555555;
                outline: 0;
            }
            QListWidget {
                background-color: #252525;
                color: #eeeeee;
                border: 1px solid #454545;
                alternate-background-color: #2d2d2d;
                selection-background-color: #75421e;
                selection-color: #ffffff;
            }
            QListWidget::item {
                padding: 7px;
            }
            QPushButton {
                background-color: #303030;
                color: #eeeeee;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 7px 10px;
            }
            QPushButton:hover {
                background-color: #414141;
            }
            QPushButton#accentButton {
                background-color: #ff7a00;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
        """)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.component_input = QComboBox()
        for component in components:
            self.component_input.addItem(
                f'{component["name"]} (ID {component["id"]})',
                int(component["id"])
            )
        if component_id is not None:
            index = self.component_input.findData(int(component_id))
            if index >= 0:
                self.component_input.setCurrentIndex(index)
        form.addRow("Комплектующее", self.component_input)
        layout.addLayout(form)
        layout.addWidget(QLabel("Отметь модели принтеров, с которыми совместима запчасть:"))
        self.printer_list = QListWidget()
        self.printer_items = {}
        for printer in printers:
            label = f'{printer["name"]} | {printer["model"] or "модель не указана"}'
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(printer["id"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.printer_list.addItem(item)
            self.printer_items[int(printer["id"])] = item
        layout.addWidget(self.printer_list, 1)
        self.component_input.currentIndexChanged.connect(self.load_checked)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Отмена")
        save = QPushButton("Сохранить совместимость")
        save.setObjectName("accentButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.load_checked()

    def load_checked(self, *_):
        component_id = self.component_input.currentData()
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT printer_id FROM component_printer_compatibility WHERE component_id=?",
                (component_id,)
            ).fetchall() if component_id is not None else []
        selected = {int(row["printer_id"]) for row in rows}
        for printer_id, item in self.printer_items.items():
            item.setCheckState(
                Qt.CheckState.Checked if printer_id in selected else Qt.CheckState.Unchecked
            )

    def save(self):
        component_id = self.component_input.currentData()
        if component_id is None:
            QMessageBox.warning(self, "Нет комплектующего", "Добавь комплектующее в разделе «Комплектующие».")
            return
        selected = [
            printer_id for printer_id, item in self.printer_items.items()
            if item.checkState() == Qt.CheckState.Checked
        ]
        try:
            with get_connection() as connection:
                connection.execute(
                    "DELETE FROM component_printer_compatibility WHERE component_id=?",
                    (component_id,)
                )
                connection.executemany(
                    "INSERT INTO component_printer_compatibility (component_id, printer_id) VALUES (?, ?)",
                    [(int(component_id), printer_id) for printer_id in selected]
                )
            self.accept()
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка сохранения", str(error))


class EquipmentPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_equipment_tables()
        self.setup_ui()
        self.load_printers()
        self.load_maintenance()
        self.load_compatibility()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        title = QLabel("Оборудование")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Принтеры, наработка, обслуживание и совместимость запчастей.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        printers_tab = QWidget()
        p_layout = QVBoxLayout(printers_tab)
        toolbar = QHBoxLayout()
        self.printer_search = QLineEdit()
        self.printer_search.setPlaceholderText("Поиск по названию, модели, производителю или серийному номеру...")
        self.printer_search.textChanged.connect(self.load_printers)
        toolbar.addWidget(self.printer_search, 1)
        add = QPushButton("+ Добавить принтер")
        add.setObjectName("accentButton")
        add.clicked.connect(self.add_printer)
        toolbar.addWidget(add)
        edit = QPushButton("Редактировать")
        edit.clicked.connect(self.edit_printer)
        toolbar.addWidget(edit)
        delete = QPushButton("Удалить")
        delete.setObjectName("dangerButton")
        delete.clicked.connect(self.delete_printer)
        toolbar.addWidget(delete)
        p_layout.addLayout(toolbar)
        self.printer_table = QTableWidget(0, 8)
        self.printer_table.setHorizontalHeaderLabels([
            "ID", "Принтер", "Производитель", "Модель", "Наработка, ч",
            "Мощность, Вт", "Стоимость, ₽", "Статус"
        ])
        self.prepare_table(self.printer_table)
        self.printer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.printer_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.printer_table.doubleClicked.connect(self.edit_printer)
        p_layout.addWidget(self.printer_table, 1)
        self.printer_summary = QLabel()
        self.printer_summary.setObjectName("subtitle")
        p_layout.addWidget(self.printer_summary)
        self.tabs.addTab(printers_tab, "Принтеры")

        maintenance_tab = QWidget()
        m_layout = QVBoxLayout(maintenance_tab)
        m_toolbar = QHBoxLayout()
        add_service = QPushButton("+ Записать обслуживание")
        add_service.setObjectName("accentButton")
        add_service.clicked.connect(self.add_maintenance)
        m_toolbar.addWidget(add_service)
        m_toolbar.addStretch()
        m_layout.addLayout(m_toolbar)
        self.maintenance_table = QTableWidget(0, 7)
        self.maintenance_table.setHorizontalHeaderLabels([
            "Дата", "Принтер", "Тип работ", "Наработка, ч", "Стоимость, ₽", "Запчасти", "Описание"
        ])
        self.prepare_table(self.maintenance_table)
        self.maintenance_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.maintenance_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        m_layout.addWidget(self.maintenance_table, 1)
        self.maintenance_summary = QLabel()
        self.maintenance_summary.setObjectName("subtitle")
        m_layout.addWidget(self.maintenance_summary)
        self.tabs.addTab(maintenance_tab, "Обслуживание")

        compatibility_tab = QWidget()
        c_layout = QVBoxLayout(compatibility_tab)
        c_toolbar = QHBoxLayout()
        self.compatibility_search = QLineEdit()
        self.compatibility_search.setPlaceholderText("Поиск комплектующего...")
        self.compatibility_search.textChanged.connect(self.load_compatibility)
        c_toolbar.addWidget(self.compatibility_search, 1)
        set_compat = QPushButton("Настроить совместимость")
        set_compat.setObjectName("accentButton")
        set_compat.clicked.connect(self.edit_compatibility)
        c_toolbar.addWidget(set_compat)
        c_layout.addLayout(c_toolbar)
        self.compatibility_table = QTableWidget(0, 3)
        self.compatibility_table.setHorizontalHeaderLabels(["ID", "Комплектующее", "Совместимые принтеры"])
        self.prepare_table(self.compatibility_table)
        self.compatibility_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.compatibility_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.compatibility_table.doubleClicked.connect(self.edit_compatibility)
        c_layout.addWidget(self.compatibility_table, 1)
        self.tabs.addTab(compatibility_tab, "Запчасти и совместимость")

    @staticmethod
    def prepare_table(table):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def load_data(self):
        self.load_printers()
        self.load_maintenance()
        self.load_compatibility()

    def load_printers(self, *_):
        search = self.printer_search.text().strip()
        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM printers WHERE name LIKE ? OR manufacturer LIKE ?
                        OR model LIKE ? OR serial_number LIKE ?
                    ORDER BY name COLLATE NOCASE
                """, (pattern, pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM printers ORDER BY name COLLATE NOCASE").fetchall()
        self.printer_table.setRowCount(len(rows))
        total_hours = 0.0
        for index, printer in enumerate(rows):
            hours = float(printer["hours_used"] or 0)
            total_hours += hours
            values = [
                str(printer["id"]), printer["name"], printer["manufacturer"] or "",
                printer["model"] or "", number(hours), number(printer["power"], 0),
                money(printer["purchase_price"]), printer["status"] or "Работает"
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, int(printer["id"]))
                self.printer_table.setItem(index, column, item)
        self.printer_summary.setText(
            f"Принтеров: {len(rows)}  |  Суммарная наработка: {number(total_hours)} ч"
        )

    def selected_printer_id(self):
        row = self.printer_table.currentRow()
        item = self.printer_table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def add_printer(self):
        dialog = PrinterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def edit_printer(self, *_):
        printer_id = self.selected_printer_id()
        if printer_id is None:
            QMessageBox.information(self, "Принтер не выбран", "Выбери принтер в таблице.")
            return
        with get_connection() as connection:
            printer = connection.execute("SELECT * FROM printers WHERE id=?", (printer_id,)).fetchone()
        if printer is None:
            self.load_printers()
            return
        dialog = PrinterDialog(self, printer)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def delete_printer(self):
        printer_id = self.selected_printer_id()
        if printer_id is None:
            QMessageBox.information(self, "Принтер не выбран", "Выбери принтер в таблице.")
            return
        with get_connection() as connection:
            printer = connection.execute("SELECT * FROM printers WHERE id=?", (printer_id,)).fetchone()
            service_count = connection.execute(
                "SELECT COUNT(*) FROM printer_maintenance WHERE printer_id=?", (printer_id,)
            ).fetchone()[0]
        if service_count:
            QMessageBox.warning(
                self, "Нельзя удалить принтер",
                "У принтера есть записи обслуживания. Чтобы сохранить историю, измени статус на «Продан» или «Не работает»."
            )
            return
        answer = QMessageBox.question(
            self, "Удаление принтера", f'Удалить принтер «{printer["name"]}»?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        with get_connection() as connection:
            connection.execute("DELETE FROM component_printer_compatibility WHERE printer_id=?", (printer_id,))
            connection.execute("DELETE FROM printers WHERE id=?", (printer_id,))
        self.load_data()

    def load_maintenance(self):
        with get_connection() as connection:
            rows = connection.execute("""
                SELECT m.*, p.name AS printer_name
                FROM printer_maintenance m
                JOIN printers p ON p.id = m.printer_id
                ORDER BY m.service_date DESC, m.id DESC
            """).fetchall()
        self.maintenance_table.setRowCount(len(rows))
        total_cost = 0.0
        for index, record in enumerate(rows):
            total_cost += float(record["cost"] or 0)
            values = [
                record["service_date"], record["printer_name"], record["service_type"],
                number(record["hours_at_service"]), money(record["cost"]),
                record["parts_used"] or "", record["description"] or ""
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, int(record["id"]))
                self.maintenance_table.setItem(index, column, item)
        self.maintenance_summary.setText(
            f"Записей обслуживания: {len(rows)}  |  Учтённые расходы: {money(total_cost)}"
        )

    def add_maintenance(self):
        with get_connection() as connection:
            printers = connection.execute("SELECT * FROM printers ORDER BY name").fetchall()
        if not printers:
            QMessageBox.information(self, "Нет принтеров", "Сначала добавь принтер во вкладке «Принтеры».")
            return
        dialog = MaintenanceDialog(self, printers)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_maintenance()

    def load_compatibility(self, *_):
        search = self.compatibility_search.text().strip() if hasattr(self, "compatibility_search") else ""
        with get_connection() as connection:
            pattern = f"%{search}%"
            rows = connection.execute("""
                SELECT c.id, c.name,
                    GROUP_CONCAT(p.name || CASE WHEN COALESCE(p.model, '') = '' THEN '' ELSE ' (' || p.model || ')' END, ', ') AS printer_names
                FROM components c
                LEFT JOIN component_printer_compatibility cp ON cp.component_id = c.id
                LEFT JOIN printers p ON p.id = cp.printer_id
                WHERE c.name LIKE ?
                  AND TRIM(COALESCE(c.category, '')) NOT IN ('Упаковка', 'упаковка')
                  AND c.name NOT LIKE '%Цепоч%'
                  AND c.name NOT LIKE '%цепоч%'
                GROUP BY c.id, c.name
                ORDER BY c.name COLLATE NOCASE
            """, (pattern,)).fetchall()
        self.compatibility_table.setRowCount(len(rows))
        for index, component in enumerate(rows):
            values = [
                str(component["id"]), component["name"],
                component["printer_names"] or "Совместимость не указана"
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, int(component["id"]))
                self.compatibility_table.setItem(index, column, item)

    def edit_compatibility(self, *_):
        row = self.compatibility_table.currentRow()
        item = self.compatibility_table.item(row, 0) if row >= 0 else None
        component_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        with get_connection() as connection:
            components = connection.execute("""
                SELECT id, name FROM components
                WHERE TRIM(COALESCE(category, '')) NOT IN ('Упаковка', 'упаковка')
                  AND name NOT LIKE '%Цепоч%'
                  AND name NOT LIKE '%цепоч%'
                ORDER BY name COLLATE NOCASE
            """).fetchall()
            printers = connection.execute("SELECT id, name, model FROM printers ORDER BY name").fetchall()
        if not components:
            QMessageBox.information(self, "Нет комплектующих", "Сначала добавь запчасть/комплектующее в разделе «Склад → Комплектующие».")
            return
        if not printers:
            QMessageBox.information(self, "Нет принтеров", "Сначала добавь принтер.")
            return
        dialog = CompatibilityDialog(self, components, printers, component_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_compatibility()
