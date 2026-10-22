import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QDoubleSpinBox, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QDateEdit, QTextEdit, QFormLayout
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def money(value):
    return f"{float(value or 0):,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def number(value, decimals=3):
    return f"{float(value or 0):,.{decimals}f}".replace(",", " ").replace(".", ",")


def initialize_inventory_tables():
    """Создаёт только таблицы складского журнала, не изменяя существующие данные."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movement_date TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT DEFAULT '',
                balance_after REAL NOT NULL DEFAULT 0,
                source TEXT DEFAULT '',
                source_id INTEGER,
                comment TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_movements_date
            ON stock_movements(movement_date DESC, id DESC)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_movements_item
            ON stock_movements(item_type, item_id)
        """)


def get_item(item_type, item_id, connection=None):
    own_connection = connection is None
    connection = connection or get_connection()
    try:
        if item_type == "material":
            row = connection.execute(
                "SELECT id, name, spool_count AS quantity, 'катушка' AS unit FROM materials WHERE id = ?",
                (item_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT id, name, COALESCE(quantity, 0) AS quantity, COALESCE(unit, 'шт.') AS unit FROM components WHERE id = ?",
                (item_id,),
            ).fetchone()
        return row
    finally:
        if own_connection:
            connection.close()


def write_stock_movement(connection, item_type, item_id, movement_type,
                         quantity, source="", source_id=None, comment="",
                         movement_date=None):
    """Изменяет остаток и одновременно записывает движение."""
    quantity = float(quantity)
    item = get_item(item_type, item_id, connection)
    if item is None:
        raise ValueError("Позиция склада не найдена.")

    current = float(item["quantity"] or 0)
    new_balance = current + quantity
    if new_balance < -0.000001:
        raise ValueError(
            f"Недостаточно остатка позиции «{item['name']}». "
            f"Текущий остаток: {number(current)} {item['unit']}."
        )

    if item_type == "material":
        connection.execute(
            "UPDATE materials SET spool_count = ? WHERE id = ?",
            (max(0, new_balance), item_id),
        )
    else:
        connection.execute(
            "UPDATE components SET quantity = ? WHERE id = ?",
            (max(0, new_balance), item_id),
        )

    connection.execute("""
        INSERT INTO stock_movements (
            movement_date, item_type, item_id, item_name, movement_type,
            quantity, unit, balance_after, source, source_id, comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        movement_date or QDate.currentDate().toString("yyyy-MM-dd"),
        item_type,
        item_id,
        item["name"],
        movement_type,
        quantity,
        item["unit"] or "",
        max(0, new_balance),
        source,
        source_id,
        comment,
    ))


class StockAdjustmentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Корректировка склада")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd.MM.yyyy")
        self.date_input.setDate(QDate.currentDate())

        self.type_input = QComboBox()
        self.type_input.addItem("Материал", "material")
        self.type_input.addItem("Комплектующее / запчасть", "component")

        self.item_input = QComboBox()
        self.item_input.setMinimumWidth(280)
        self.item_input.currentIndexChanged.connect(self.update_current_stock)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(-100000000, 100000000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setSingleStep(1)
        self.quantity_input.setSuffix(" ед.")

        self.reason_input = QComboBox()
        self.reason_input.addItems([
            "Корректировка остатка",
            "Инвентаризация",
            "Списание",
            "Возврат на склад",
            "Прочее",
        ])

        self.comment_input = QTextEdit()
        self.comment_input.setMaximumHeight(90)
        self.comment_input.setPlaceholderText("Причина или примечание")

        self.stock_label = QLabel("Текущий остаток: 0")
        self.stock_label.setObjectName("subtitle")

        form.addRow("Дата:", self.date_input)
        form.addRow("Тип:", self.type_input)
        form.addRow("Позиция:", self.item_input)
        form.addRow("Изменение:", self.quantity_input)
        form.addRow("Причина:", self.reason_input)
        form.addRow("Комментарий:", self.comment_input)
        form.addRow("", self.stock_label)
        layout.addLayout(form)

        hint = QLabel(
            "Положительное число увеличивает остаток, отрицательное уменьшает."
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.type_input.currentIndexChanged.connect(self.load_items)
        self.load_items()

    def load_items(self):
        item_type = self.type_input.currentData()
        self.item_input.clear()
        with get_connection() as connection:
            if item_type == "material":
                rows = connection.execute(
                    "SELECT id, name, spool_count AS quantity, 'катушка' AS unit FROM materials ORDER BY name"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, name, COALESCE(quantity, 0) AS quantity, COALESCE(unit, 'шт.') AS unit FROM components ORDER BY name COLLATE NOCASE"
                ).fetchall()

        for row in rows:
            self.item_input.addItem(row["name"], dict(row))
        self.update_current_stock()

    def update_current_stock(self):
        row = self.item_input.currentData()
        if not row:
            self.stock_label.setText("Позиция не выбрана")
            return
        self.stock_label.setText(
            f"Текущий остаток: {number(row.get('quantity'))} {row.get('unit') or ''}"
        )

    def validate_and_accept(self):
        row = self.item_input.currentData()
        quantity = self.quantity_input.value()
        if not row:
            QMessageBox.warning(self, "Нет позиции", "Выбери складскую позицию.")
            return
        if abs(quantity) < 0.000001:
            QMessageBox.warning(self, "Нет изменения", "Укажи ненулевое изменение остатка.")
            return
        new_balance = float(row.get("quantity") or 0) + quantity
        if new_balance < -0.000001:
            QMessageBox.warning(
                self, "Недостаточно остатка",
                "Нельзя списать больше, чем есть на складе."
            )
            return
        self.accept()

    def get_data(self):
        row = self.item_input.currentData()
        return {
            "movement_date": self.date_input.date().toString("yyyy-MM-dd"),
            "item_type": self.type_input.currentData(),
            "item_id": int(row["id"]),
            "quantity": self.quantity_input.value(),
            "movement_type": self.reason_input.currentText(),
            "comment": self.comment_input.toPlainText().strip(),
        }


class InventoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_inventory_tables()
        self.setup_ui()
        self.load_stock()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(14)

        title = QLabel("Склад")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Текущие остатки материалов и комплектующих и журнал движения."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по названию позиции...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_stock)
        toolbar.addWidget(self.search_input, 1)

        adjust_button = QPushButton("± Корректировка")
        adjust_button.setObjectName("accentButton")
        adjust_button.clicked.connect(self.adjust_stock)
        toolbar.addWidget(adjust_button)

        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.load_stock)
        toolbar.addWidget(refresh_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Тип", "Позиция", "Остаток", "Ед.", "Статус"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        movement_title = QLabel("Последние движения")
        movement_title.setObjectName("pageTitle")
        movement_title.setStyleSheet("font-size: 19px;")
        layout.addWidget(movement_title)

        self.movements_table = QTableWidget(0, 7)
        self.movements_table.setHorizontalHeaderLabels([
            "Дата", "Позиция", "Операция", "Изменение", "Остаток", "Источник", "Комментарий"
        ])
        self.movements_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.movements_table.setAlternatingRowColors(True)
        self.movements_table.verticalHeader().setVisible(False)
        movement_header = self.movements_table.horizontalHeader()
        for column in range(6):
            movement_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        movement_header.setStretchLastSection(True)
        layout.addWidget(self.movements_table, 1)

    def load_stock(self, *args):
        search = self.search_input.text().strip()
        pattern = f"%{search}%"
        with get_connection() as connection:
            materials = connection.execute("""
                SELECT id, name, spool_count AS quantity, 'катушка' AS unit,
                       'material' AS item_type
                FROM materials
                WHERE name LIKE ?
                ORDER BY name
            """, (pattern,)).fetchall()
            components = connection.execute("""
                SELECT id, name, COALESCE(quantity, 0) AS quantity,
                       COALESCE(unit, 'шт.') AS unit, 'component' AS item_type
                FROM components
                WHERE name LIKE ?
                ORDER BY name COLLATE NOCASE
            """, (pattern,)).fetchall()
            movements = connection.execute("""
                SELECT movement_date, item_name, movement_type, quantity,
                       unit, balance_after, source, comment
                FROM stock_movements
                ORDER BY movement_date DESC, id DESC
                LIMIT 100
            """).fetchall()

        rows = list(materials) + list(components)
        rows.sort(key=lambda row: str(row["name"]).lower())
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            quantity = float(row["quantity"] or 0)
            status = "В норме"
            if quantity <= 0:
                status = "Нет остатка"
            elif quantity < 1:
                status = "Низкий остаток"
            type_label = "Материал" if row["item_type"] == "material" else "Комплектующее"
            values = [
                type_label,
                row["name"],
                number(quantity),
                row["unit"] or "",
                status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, item)

        self.movements_table.setRowCount(len(movements))
        for row_index, movement in enumerate(movements):
            qty = float(movement["quantity"] or 0)
            sign = "+" if qty > 0 else ""
            values = [
                movement["movement_date"],
                movement["item_name"],
                movement["movement_type"],
                f"{sign}{number(qty)} {movement['unit'] or ''}".strip(),
                f"{number(movement['balance_after'])} {movement['unit'] or ''}".strip(),
                movement["source"] or "",
                movement["comment"] or "",
            ]
            for column, value in enumerate(values):
                self.movements_table.setItem(row_index, column, QTableWidgetItem(str(value)))

    def adjust_stock(self):
        dialog = StockAdjustmentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            with get_connection() as connection:
                write_stock_movement(
                    connection,
                    data["item_type"],
                    data["item_id"],
                    data["movement_type"],
                    data["quantity"],
                    source="Ручная корректировка",
                    comment=data["comment"],
                    movement_date=data["movement_date"],
                )
            self.load_stock()
            QMessageBox.information(self, "Склад обновлён", "Движение записано в журнал.")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка изменения склада", str(error))
            self.load_stock()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    app.setStyleSheet("QWidget { background:#181818; color:#eeeeee; }")
    initialize_inventory_tables()
    window = InventoryPage()
    window.resize(1100, 800)
    window.setWindowTitle("Склад | KRAFT 3D Manager")
    window.show()
    sys.exit(app.exec())
