
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView
)


BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "data" / "kraft3d.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_material_tables():
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                material_type TEXT,
                color TEXT,
                brand TEXT,
                spool_weight REAL DEFAULT 1000,
                spool_price REAL DEFAULT 0,
                price_per_gram REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS material_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                old_weight REAL,
                new_weight REAL,
                old_price REAL,
                new_price REAL,
                changed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def parse_number(value):
    """Принимает числа, введённые как с точкой, так и с запятой."""
    return float(value.strip().replace(",", "."))


def money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


# ============================================================
# ОКНО ДОБАВЛЕНИЯ И РЕДАКТИРОВАНИЯ МАТЕРИАЛА
# ============================================================

class MaterialDialog(QDialog):

    def __init__(self, parent=None, material=None):
        super().__init__(parent)

        self.material = material
        self.setWindowTitle(
            "Редактирование материала" if material
            else "Добавление материала"
        )
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например, PETG чёрный")

        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems([
            "PETG", "PLA", "TPU", "ABS", "ASA", "PA", "Другой"
        ])

        self.brand_input = QLineEdit()
        self.brand_input.setPlaceholderText("Производитель пластика")

        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("Например, чёрный")

        self.weight_input = QLineEdit("1000")
        self.weight_input.setPlaceholderText("Вес в граммах")

        self.price_input = QLineEdit("1200")
        self.price_input.setPlaceholderText("Цена всей катушки")

        form.addRow("Название *", self.name_input)
        form.addRow("Тип материала", self.type_input)
        form.addRow("Бренд", self.brand_input)
        form.addRow("Цвет", self.color_input)
        form.addRow("Вес катушки, г *", self.weight_input)
        form.addRow("Цена катушки, ₽ *", self.price_input)

        layout.addLayout(form)

        self.calculation_label = QLabel()
        self.calculation_label.setObjectName("subtitle")
        layout.addWidget(self.calculation_label)

        self.weight_input.textChanged.connect(self.update_calculation)
        self.price_input.textChanged.connect(self.update_calculation)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if material:
            self.name_input.setText(material["name"])
            self.type_input.setCurrentText(
                material["material_type"] or "Другой"
            )
            self.brand_input.setText(material["brand"] or "")
            self.color_input.setText(material["color"] or "")
            self.weight_input.setText(str(material["spool_weight"] or 1000))
            self.price_input.setText(str(material["spool_price"] or 0))

        self.update_calculation()

    def update_calculation(self, *args):
        try:
            weight = parse_number(self.weight_input.text())
            price = parse_number(self.price_input.text())

            if weight <= 0 or price < 0:
                raise ValueError

            per_gram = price / weight

            self.calculation_label.setText(
                f"Стоимость 1 г: {money(per_gram)}\n"
                f"Стоимость 10 г: {money(per_gram * 10)}\n"
                f"Стоимость 100 г: {money(per_gram * 100)}"
            )
        except (ValueError, ZeroDivisionError):
            self.calculation_label.setText(
                "Укажи корректные вес и цену."
            )

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(
                self, "Ошибка", "Укажи название материала."
            )
            self.name_input.setFocus()
            return

        try:
            weight = parse_number(self.weight_input.text())
            price = parse_number(self.price_input.text())

            if weight <= 0:
                raise ValueError("Вес должен быть больше нуля.")

            if price < 0:
                raise ValueError("Цена не может быть отрицательной.")

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Проверь данные",
                str(error) if str(error) else
                "Введи корректные числовые значения."
            )
            return

        self.accept()

    def get_data(self):
        weight = parse_number(self.weight_input.text())
        price = parse_number(self.price_input.text())

        return {
            "name": self.name_input.text().strip(),
            "material_type": self.type_input.currentText().strip(),
            "brand": self.brand_input.text().strip(),
            "color": self.color_input.text().strip(),
            "spool_weight": weight,
            "spool_price": price,
            "price_per_gram": price / weight,
        }


# ============================================================
# СТРАНИЦА МАТЕРИАЛОВ
# ============================================================

class MaterialsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__()

        initialize_material_tables()
        self.setup_ui()
        self.load_materials()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(16)

        title = QLabel("Материалы")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Пластик, стоимость катушек и автоматический расчёт цены грамма"
        )
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Поиск по названию, типу, бренду или цвету..."
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_materials)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Добавить материал")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_material)
        toolbar.addWidget(add_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Название",
            "Тип",
            "Бренд",
            "Цвет",
            "Вес, г",
            "Цена катушки",
            "Цена за 1 г",
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
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        for column in range(1, 7):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        self.table.doubleClicked.connect(self.edit_material)
        layout.addWidget(self.table, 1)

        self.count_label = QLabel("Материалов: 0")
        self.count_label.setObjectName("subtitle")
        layout.addWidget(self.count_label)

        buttons = QHBoxLayout()
        buttons.addStretch()

        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_material)
        buttons.addWidget(edit_button)

        history_button = QPushButton("История цен")
        history_button.clicked.connect(self.show_history)
        buttons.addWidget(history_button)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_material)
        buttons.addWidget(delete_button)

        layout.addLayout(buttons)

    def load_materials(self, *args):
        search = self.search_input.text().strip()

        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM materials
                    WHERE name LIKE ?
                       OR material_type LIKE ?
                       OR brand LIKE ?
                       OR color LIKE ?
                    ORDER BY id DESC
                """, (pattern, pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute("""
                    SELECT * FROM materials
                    ORDER BY id DESC
                """).fetchall()

        self.table.setRowCount(len(rows))

        for row_index, material in enumerate(rows):
            weight = float(material["spool_weight"] or 0)
            price = float(material["spool_price"] or 0)

            # Пересчитываем значение по весу и цене катушки.
            per_gram = price / weight if weight > 0 else 0

            values = [
                material["name"],
                material["material_type"] or "",
                material["brand"] or "",
                material["color"] or "",
                f"{weight:g}",
                money(price),
                money(per_gram),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    material["id"]
                )
                self.table.setItem(row_index, column, item)

        self.count_label.setText(f"Материалов: {len(rows)}")

    def selected_material_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if item is None:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def add_material(self):
        dialog = MaterialDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        with get_connection() as connection:
            cursor = connection.execute("""
                INSERT INTO materials (
                    name, material_type, brand, color,
                    spool_weight, spool_price, price_per_gram
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data["name"],
                data["material_type"],
                data["brand"],
                data["color"],
                data["spool_weight"],
                data["spool_price"],
                data["price_per_gram"],
            ))

            material_id = cursor.lastrowid

            connection.execute("""
                INSERT INTO material_price_history (
                    material_id, old_weight, new_weight,
                    old_price, new_price
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                material_id,
                None,
                data["spool_weight"],
                None,
                data["spool_price"],
            ))

        self.load_materials()

    def edit_material(self, *args):
        material_id = self.selected_material_id()

        if material_id is None:
            QMessageBox.information(
                self, "Материал не выбран",
                "Сначала выбери материал в таблице."
            )
            return

        with get_connection() as connection:
            material = connection.execute(
                "SELECT * FROM materials WHERE id = ?",
                (material_id,)
            ).fetchone()

        if material is None:
            self.load_materials()
            return

        dialog = MaterialDialog(self, material)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        old_weight = float(material["spool_weight"] or 0)
        old_price = float(material["spool_price"] or 0)

        with get_connection() as connection:
            connection.execute("""
                UPDATE materials
                SET name = ?,
                    material_type = ?,
                    brand = ?,
                    color = ?,
                    spool_weight = ?,
                    spool_price = ?,
                    price_per_gram = ?
                WHERE id = ?
            """, (
                data["name"],
                data["material_type"],
                data["brand"],
                data["color"],
                data["spool_weight"],
                data["spool_price"],
                data["price_per_gram"],
                material_id,
            ))

            if (
                old_weight != data["spool_weight"]
                or old_price != data["spool_price"]
            ):
                connection.execute("""
                    INSERT INTO material_price_history (
                        material_id, old_weight, new_weight,
                        old_price, new_price
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    material_id,
                    old_weight,
                    data["spool_weight"],
                    old_price,
                    data["spool_price"],
                ))

        self.load_materials()

    def show_history(self):
        material_id = self.selected_material_id()

        if material_id is None:
            QMessageBox.information(
                self, "Материал не выбран",
                "Сначала выбери материал в таблице."
            )
            return

        with get_connection() as connection:
            material = connection.execute(
                "SELECT name FROM materials WHERE id = ?",
                (material_id,)
            ).fetchone()

            history = connection.execute("""
                SELECT * FROM material_price_history
                WHERE material_id = ?
                ORDER BY id DESC
            """, (material_id,)).fetchall()

        if not history:
            QMessageBox.information(
                self, "История цен", "История изменений пока пуста."
            )
            return

        lines = [f"История цен: {material['name']}", ""]

        for entry in history:
            if entry["old_price"] is None:
                lines.append(
                    f"{entry['changed_at']}: создана запись, "
                    f"{entry['new_weight']:g} г, "
                    f"{money(entry['new_price'])}"
                )
            else:
                lines.append(
                    f"{entry['changed_at']}: "
                    f"{money(entry['old_price'])} → "
                    f"{money(entry['new_price'])}; "
                    f"вес: {entry['old_weight']:g} → "
                    f"{entry['new_weight']:g} г"
                )

        QMessageBox.information(
            self, "История цен", "\n".join(lines)
        )

    def delete_material(self):
        material_id = self.selected_material_id()

        if material_id is None:
            QMessageBox.information(
                self, "Материал не выбран",
                "Сначала выбери материал в таблице."
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление материала",
            "Удалить выбранный материал и его историю цен?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        with get_connection() as connection:
            connection.execute(
                "DELETE FROM material_price_history WHERE material_id = ?",
                (material_id,)
            )
            connection.execute(
                "DELETE FROM materials WHERE id = ?",
                (material_id,)
            )

        self.load_materials()
