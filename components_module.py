
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QFormLayout,
    QComboBox,
    QTextEdit,
    QMessageBox,
    QAbstractItemView,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"


# --------------------------------------------------
# БАЗА ДАННЫХ
# --------------------------------------------------

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_component_tables():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                unit TEXT DEFAULT 'шт.',
                price REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(components)"
            ).fetchall()
        }

        new_columns = {
            "supplier": "TEXT DEFAULT ''",
            "quantity": "REAL DEFAULT 0",
            "min_quantity": "REAL DEFAULT 0",
            "notes": "TEXT DEFAULT ''",
        }

        for name, column_type in new_columns.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE components "
                    f"ADD COLUMN {name} {column_type}"
                )


# --------------------------------------------------
# ФОРМАТИРОВАНИЕ ЧИСЕЛ
# --------------------------------------------------

def parse_number(text):
    """Преобразует число с запятой или точкой в float."""
    text = str(text).strip().replace(" ", "").replace(",", ".")

    if not text:
        return 0.0

    try:
        value = float(text)
        if value < 0:
            return 0.0
        return value
    except ValueError:
        return 0.0


def format_number(value, decimals=2):
    value = float(value or 0)
    return f"{value:,.{decimals}f}".replace(
        ",", " "
    ).replace(".", ",")


def format_money(value):
    return f"{format_number(value, 2)} ₽"


# --------------------------------------------------
# ПОЛЕ ВВОДА ЧИСЛА
# --------------------------------------------------

class NumberInput(QLineEdit):
    def __init__(self, decimals=3, parent=None):
        super().__init__(parent)

        self.decimals = decimals

        validator = QDoubleValidator(
            0.0, 100000000.0, decimals, self
        )
        validator.setLocale(
            QLocale(QLocale.Language.Russian)
        )
        validator.setNotation(
            QDoubleValidator.Notation.StandardNotation
        )

        self.setValidator(validator)
        self.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.setMinimumHeight(32)

    def value(self):
        return parse_number(self.text())

    def setValue(self, value):
        self.setText(
            f"{float(value or 0):.{self.decimals}f}".replace(
                ".", ","
            )
        )


# --------------------------------------------------
# ОКНО ДОБАВЛЕНИЯ И РЕДАКТИРОВАНИЯ
# --------------------------------------------------

class ComponentDialog(QDialog):
    def __init__(self, parent=None, component=None):
        super().__init__(parent)

        self.component = component
        self.result_data = None

        self.setWindowTitle(
            "Редактирование комплектующего"
            if component else "Новое комплектующее"
        )
        self.setMinimumWidth(480)

        self.setStyleSheet("""
            QDialog {
                background-color: #252525;
                color: #f2f2f2;
            }

            QLabel {
                color: #f2f2f2;
                background-color: transparent;
            }

            QLineEdit, QComboBox, QTextEdit {
                background-color: #353535;
                color: #ffffff;
                border: 1px solid #606060;
                border-radius: 5px;
                padding: 6px;
                selection-background-color: #e88732;
                selection-color: #ffffff;
            }

            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #e88732;
            }

            QComboBox QAbstractItemView {
                background-color: #353535;
                color: #ffffff;
                selection-background-color: #e88732;
            }

            QPushButton {
                background-color: #414141;
                color: #ffffff;
                border: 1px solid #606060;
                border-radius: 5px;
                padding: 8px 14px;
            }

            QPushButton:hover {
                background-color: #e88732;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "Например, металлическое кольцо"
        )

        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems([
            "Фурнитура",
            "Крепёж",
            "Магниты",
            "Упаковка",
            "Электроника",
            "Расходники",
            "Прочее",
        ])

        self.unit_input = QComboBox()
        self.unit_input.setEditable(True)
        self.unit_input.addItems([
            "шт.",
            "комплект",
            "м",
            "см",
            "г",
            "кг",
            "упаковка",
        ])

        self.price_input = NumberInput(decimals=2)
        self.price_input.setPlaceholderText("Например, 12,50")

        self.quantity_input = NumberInput(decimals=3)
        self.quantity_input.setPlaceholderText("Например, 100")

        self.min_quantity_input = NumberInput(decimals=3)
        self.min_quantity_input.setPlaceholderText("Например, 10")

        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText(
            "Название магазина или поставщика"
        )

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText(
            "Дополнительная информация"
        )
        self.notes_input.setMaximumHeight(85)

        form.addRow("Название *:", self.name_input)
        form.addRow("Категория:", self.category_input)
        form.addRow("Единица измерения:", self.unit_input)
        form.addRow("Цена за единицу (₽):", self.price_input)
        form.addRow("Количество на складе:", self.quantity_input)
        form.addRow("Минимальный остаток:", self.min_quantity_input)
        form.addRow("Поставщик:", self.supplier_input)
        form.addRow("Примечания:", self.notes_input)

        layout.addLayout(form)

        self.total_label = QLabel()
        self.total_label.setStyleSheet("""
            QLabel {
                color: #ff9d3d;
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        layout.addWidget(self.total_label)

        self.price_input.textChanged.connect(self.update_total)
        self.quantity_input.textChanged.connect(self.update_total)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_button = QPushButton("Отмена")
        save_button = QPushButton("Сохранить")

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.save)

        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

        if component is not None:
            self.name_input.setText(component["name"] or "")
            self.category_input.setCurrentText(
                component["category"] or ""
            )
            self.unit_input.setCurrentText(
                component["unit"] or "шт."
            )
            self.price_input.setValue(
                component["price"] or 0
            )
            self.quantity_input.setValue(
                component["quantity"] or 0
            )
            self.min_quantity_input.setValue(
                component["min_quantity"] or 0
            )
            self.supplier_input.setText(
                component["supplier"] or ""
            )
            self.notes_input.setPlainText(
                component["notes"] or ""
            )
        else:
            self.price_input.setValue(0)
            self.quantity_input.setValue(0)
            self.min_quantity_input.setValue(0)

        self.update_total()

    def update_total(self, *_):
        price = self.price_input.value()
        quantity = self.quantity_input.value()
        total = price * quantity

        self.total_label.setText(
            f"Стоимость остатка: {format_money(total)}"
        )

    def save(self):
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Не указано название",
                "Введите название комплектующего."
            )
            self.name_input.setFocus()
            return

        self.result_data = {
            "name": name,
            "category": self.category_input.currentText().strip(),
            "unit": self.unit_input.currentText().strip() or "шт.",
            "price": self.price_input.value(),
            "quantity": self.quantity_input.value(),
            "min_quantity": self.min_quantity_input.value(),
            "supplier": self.supplier_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip(),
        }

        with get_connection() as connection:
            if self.component is not None:
                connection.execute("""
                    UPDATE components
                    SET name = ?,
                        category = ?,
                        unit = ?,
                        price = ?,
                        supplier = ?,
                        quantity = ?,
                        min_quantity = ?,
                        notes = ?
                    WHERE id = ?
                """, (
                    self.result_data["name"],
                    self.result_data["category"],
                    self.result_data["unit"],
                    self.result_data["price"],
                    self.result_data["supplier"],
                    self.result_data["quantity"],
                    self.result_data["min_quantity"],
                    self.result_data["notes"],
                    self.component["id"],
                ))
            else:
                connection.execute("""
                    INSERT INTO components (
                        name, category, unit, price, supplier,
                        quantity, min_quantity, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.result_data["name"],
                    self.result_data["category"],
                    self.result_data["unit"],
                    self.result_data["price"],
                    self.result_data["supplier"],
                    self.result_data["quantity"],
                    self.result_data["min_quantity"],
                    self.result_data["notes"],
                ))

        self.accept()


# --------------------------------------------------
# СТРАНИЦА КОМПЛЕКТУЮЩИХ
# --------------------------------------------------

class ComponentsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        initialize_component_tables()
        self.setup_ui()
        self.load_components()

    def setup_ui(self):
        self.setObjectName("componentsPage")
        self.setStyleSheet("""
            QWidget#componentsPage {
                background-color: #202020;
                color: #eeeeee;
            }

            QWidget#componentsPage QLabel {
                color: #eeeeee;
                background-color: transparent;
            }

            QWidget#componentsPage QLineEdit {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #75421e;
                selection-color: #ffffff;
            }

            QWidget#componentsPage QLineEdit:focus {
                border: 1px solid #ff7a00;
            }

            QTableWidget#componentsTable {
                background-color: #202020;
                alternate-background-color: #292929;
                color: #eeeeee;
                gridline-color: #383838;
                border: 1px solid #383838;
                border-radius: 4px;
                selection-background-color: #75421e;
                selection-color: #ffffff;
                outline: 0;
            }

            QTableWidget#componentsTable::item {
                color: #eeeeee;
                padding: 5px;
                border: none;
            }

            QTableWidget#componentsTable::item:selected {
                background-color: #75421e;
                color: #ffffff;
            }

            QTableWidget#componentsTable QHeaderView::section {
                background-color: #303030;
                color: #ffffff;
                padding: 9px 6px;
                border: none;
                border-bottom: 1px solid #484848;
                font-weight: 600;
            }

            QWidget#componentsPage QPushButton {
                background-color: #303030;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 6px;
                padding: 9px 12px;
            }

            QWidget#componentsPage QPushButton:hover {
                background-color: #414141;
                border-color: #ff7a00;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Комплектующие")
        title.setStyleSheet(
            "font-size: 24px; font-weight: bold;"
        )
        layout.addWidget(title)

        description = QLabel(
            "Фурнитура, крепёж, упаковка и другие складские расходники."
        )
        description.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(description)

        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Поиск по названию, категории или поставщику..."
        )
        self.search_input.textChanged.connect(self.load_components)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Добавить")
        add_button.clicked.connect(self.add_component)
        toolbar.addWidget(add_button)

        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_component)
        toolbar.addWidget(edit_button)

        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self.delete_component)
        toolbar.addWidget(delete_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setObjectName("componentsTable")
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Название",
            "Категория",
            "Остаток",
            "Цена за единицу",
            "Стоимость остатка",
            "Поставщик",
            "Статус",
        ])

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.edit_component)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            7, QHeaderView.ResizeMode.ResizeToContents
        )

        layout.addWidget(self.table, 1)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 6px;"
        )
        layout.addWidget(self.summary_label)

    def load_components(self, *_):
        search = self.search_input.text().strip()

        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM components
                    WHERE name LIKE ?
                       OR category LIKE ?
                       OR supplier LIKE ?
                    ORDER BY name COLLATE NOCASE
                """, (pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute("""
                    SELECT * FROM components
                    ORDER BY name COLLATE NOCASE
                """).fetchall()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        total_value = 0.0
        low_stock_count = 0

        for component in rows:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)

            quantity = float(component["quantity"] or 0)
            minimum = float(component["min_quantity"] or 0)
            price = float(component["price"] or 0)
            stock_value = quantity * price
            total_value += stock_value

            is_low = minimum > 0 and quantity <= minimum

            if is_low:
                low_stock_count += 1

            status = "Мало на складе" if is_low else "В норме"

            values = [
                str(component["id"]),
                component["name"] or "",
                component["category"] or "",
                f"{format_number(quantity, 3)} "
                f"{component['unit'] or 'шт.'}",
                format_money(price),
                format_money(stock_value),
                component["supplier"] or "",
                status,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column in (0, 3, 4, 5):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        int(component["id"])
                    )

                if is_low:
                    item.setBackground(QColor("#633b2d"))
                    item.setForeground(QColor("#ffffff"))

                self.table.setItem(row_index, column, item)

        self.table.setSortingEnabled(True)

        self.summary_label.setText(
            f"Позиций: {len(rows)}  |  "
            f"Стоимость запасов: {format_money(total_value)}  |  "
            f"Низкий остаток: {low_stock_count}"
        )

    def selected_component_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if item is None:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def get_component(self, component_id):
        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM components WHERE id = ?",
                (component_id,)
            ).fetchone()

    def add_component(self):
        dialog = ComponentDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_components()

    def edit_component(self, *_):
        component_id = self.selected_component_id()

        if component_id is None:
            QMessageBox.information(
                self,
                "Выберите позицию",
                "Сначала выберите комплектующее в таблице."
            )
            return

        component = self.get_component(component_id)

        if component is None:
            self.load_components()
            return

        dialog = ComponentDialog(self, component)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_components()

    def delete_component(self):
        component_id = self.selected_component_id()

        if component_id is None:
            QMessageBox.information(
                self,
                "Выберите позицию",
                "Сначала выберите комплектующее в таблице."
            )
            return

        component = self.get_component(component_id)

        if component is None:
            self.load_components()
            return

        answer = QMessageBox.question(
            self,
            "Удаление комплектующего",
            f"Удалить позицию «{component['name']}»?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        with get_connection() as connection:
            connection.execute(
                "DELETE FROM components WHERE id = ?",
                (component_id,)
            )

        self.load_components()
