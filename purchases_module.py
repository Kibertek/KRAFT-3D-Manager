import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QDateEdit, QDoubleSpinBox, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox
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


def initialize_purchase_tables():
    """Создаёт таблицу закупок и безопасно расширяет существующую таблицу материалов."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_date TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_id INTEGER,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT DEFAULT '',
                unit_price REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                supplier TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchases_date
            ON purchases(purchase_date)
        """)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(materials)").fetchall()
        }
        if "spool_count" not in columns:
            connection.execute(
                "ALTER TABLE materials ADD COLUMN spool_count REAL NOT NULL DEFAULT 0"
            )


class PurchaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить закупку")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd.MM.yyyy")
        self.date_input.setDate(QDate.currentDate())

        self.type_input = QComboBox()
        self.type_input.addItem("Материал", "material")
        self.type_input.addItem("Комплектующее / упаковка", "component")

        self.item_input = QComboBox()
        self.item_input.setMinimumWidth(260)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0.001, 100000000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setValue(1)
        self.quantity_input.setSuffix(" ед.")

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 100000000)
        self.price_input.setDecimals(2)
        self.price_input.setSingleStep(10)
        self.price_input.setSuffix(" ₽")

        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText("Магазин или поставщик")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Ссылка на заказ, номер чека и другие заметки")
        self.notes_input.setMaximumHeight(80)

        self.stock_label = QLabel("Текущий остаток: 0")
        self.stock_label.setObjectName("subtitle")

        form.addRow("Дата закупки:", self.date_input)
        form.addRow("Тип позиции:", self.type_input)
        form.addRow("Позиция:", self.item_input)
        form.addRow("Количество:", self.quantity_input)
        form.addRow("Цена за единицу:", self.price_input)
        form.addRow("Поставщик:", self.supplier_input)
        form.addRow("Комментарий:", self.notes_input)
        form.addRow("", self.stock_label)
        layout.addLayout(form)

        self.total_label = QLabel()
        self.total_label.setObjectName("pageTitle")
        self.total_label.setStyleSheet("font-size: 18px; color: #ff9a3d;")
        layout.addWidget(self.total_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.type_input.currentIndexChanged.connect(self.load_items)
        self.item_input.currentIndexChanged.connect(self.select_item)
        self.quantity_input.valueChanged.connect(self.update_total)
        self.price_input.valueChanged.connect(self.update_total)

        self.load_items()
        self.update_total()

    def load_items(self, *args):
        item_type = self.type_input.currentData()
        self.item_input.clear()

        with get_connection() as connection:
            if item_type == "material":
                rows = connection.execute("""
                    SELECT id, name, 'катушка' AS unit,
                           spool_price AS price, spool_count AS quantity
                    FROM materials ORDER BY name
                """).fetchall()
            else:
                rows = connection.execute("""
                    SELECT id, name, COALESCE(unit, 'шт.') AS unit,
                           COALESCE(price, 0) AS price,
                           COALESCE(quantity, 0) AS quantity
                    FROM components ORDER BY name
                """).fetchall()

        for row in rows:
            self.item_input.addItem(row["name"], dict(row))

        self.select_item()

    def select_item(self, *args):
        row = self.item_input.currentData()
        if not row:
            self.stock_label.setText("Нет доступных позиций. Сначала добавь позицию в справочник.")
            return

        self.price_input.setValue(float(row.get("price") or 0))
        self.stock_label.setText(
            f"Текущий остаток: {number(row.get('quantity') or 0)} {row.get('unit') or ''}"
        )
        self.update_total()

    def update_total(self, *args):
        total = self.quantity_input.value() * self.price_input.value()
        self.total_label.setText(f"Сумма закупки: {money(total)}")

    def validate_and_accept(self):
        if self.item_input.currentData() is None:
            QMessageBox.warning(
                self, "Нет позиции",
                "Сначала добавь материал или комплектующее в соответствующий справочник."
            )
            return
        if self.quantity_input.value() <= 0:
            QMessageBox.warning(self, "Проверь количество", "Количество должно быть больше нуля.")
            return
        self.accept()

    def get_data(self):
        row = self.item_input.currentData()
        return {
            "purchase_date": self.date_input.date().toString("yyyy-MM-dd"),
            "item_type": self.type_input.currentData(),
            "item_id": int(row["id"]),
            "item_name": row["name"],
            "quantity": self.quantity_input.value(),
            "unit": row.get("unit") or "",
            "unit_price": self.price_input.value(),
            "total": self.quantity_input.value() * self.price_input.value(),
            "supplier": self.supplier_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip(),
        }


class PurchasesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_purchase_tables()
        self.setup_ui()
        self.load_purchases()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(14)

        title = QLabel("Закупки")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "История закупок материалов и комплектующих. "
            "Сохранённая закупка автоматически увеличивает складской остаток."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по позиции, поставщику или комментарию...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_purchases)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Добавить закупку")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_purchase)
        toolbar.addWidget(add_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Дата", "Тип", "Позиция", "Количество", "Цена за ед.", "Сумма", "Поставщик"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in range(3, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("Закупок: 0")
        self.count_label.setObjectName("subtitle")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.total_label = QLabel("Всего: 0,00 ₽")
        self.total_label.setObjectName("subtitle")
        bottom.addWidget(self.total_label)
        layout.addLayout(bottom)

    def load_purchases(self, *args):
        search = self.search_input.text().strip()
        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM purchases
                    WHERE item_name LIKE ? OR supplier LIKE ? OR notes LIKE ?
                    ORDER BY purchase_date DESC, id DESC
                """, (pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute("""
                    SELECT * FROM purchases
                    ORDER BY purchase_date DESC, id DESC
                """).fetchall()

        self.table.setRowCount(len(rows))
        total_sum = 0.0
        for row_index, purchase in enumerate(rows):
            total_sum += float(purchase["total"] or 0)
            type_label = "Материал" if purchase["item_type"] == "material" else "Комплектующее"
            values = [
                purchase["purchase_date"],
                type_label,
                purchase["item_name"],
                f"{number(purchase['quantity'])} {purchase['unit'] or ''}".strip(),
                money(purchase["unit_price"]),
                money(purchase["total"]),
                purchase["supplier"] or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in (3, 4, 5):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                item.setData(Qt.ItemDataRole.UserRole, purchase["id"])
                self.table.setItem(row_index, column, item)

        self.count_label.setText(f"Закупок: {len(rows)}")
        self.total_label.setText(f"Всего: {money(total_sum)}")

    def add_purchase(self):
        dialog = PurchaseDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        try:
            with get_connection() as connection:
                connection.execute("""
                    INSERT INTO purchases (
                        purchase_date, item_type, item_id, item_name,
                        quantity, unit, unit_price, total, supplier, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["purchase_date"], data["item_type"], data["item_id"],
                    data["item_name"], data["quantity"], data["unit"],
                    data["unit_price"], data["total"], data["supplier"], data["notes"]
                ))

                if data["item_type"] == "material":
                    material = connection.execute(
                        "SELECT spool_weight, spool_price, spool_count FROM materials WHERE id = ?",
                        (data["item_id"],)
                    ).fetchone()
                    if material is None:
                        raise ValueError("Материал больше не существует в справочнике.")
                    old_price = float(material["spool_price"] or 0)
                    old_weight = float(material["spool_weight"] or 1000)
                    new_price = data["unit_price"]
                    new_weight = old_weight if old_weight > 0 else 1000
                    connection.execute("""
                        UPDATE materials
                        SET spool_count = COALESCE(spool_count, 0) + ?,
                            spool_price = ?,
                            price_per_gram = ?
                        WHERE id = ?
                    """, (
                        data["quantity"], new_price, new_price / new_weight,
                        data["item_id"]
                    ))
                    if old_price != new_price:
                        connection.execute("""
                            INSERT INTO material_price_history (
                                material_id, old_weight, new_weight, old_price, new_price
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (
                            data["item_id"], old_weight, new_weight, old_price, new_price
                        ))
                else:
                    component = connection.execute(
                        "SELECT quantity FROM components WHERE id = ?",
                        (data["item_id"],)
                    ).fetchone()
                    if component is None:
                        raise ValueError("Комплектующее больше не существует в справочнике.")
                    connection.execute("""
                        UPDATE components
                        SET quantity = COALESCE(quantity, 0) + ?, price = ?
                        WHERE id = ?
                    """, (data["quantity"], data["unit_price"], data["item_id"]))

            self.load_purchases()
            QMessageBox.information(
                self, "Закупка сохранена",
                "Закупка записана, складской остаток обновлён."
            )
        except Exception as error:
            QMessageBox.critical(self, "Ошибка закупки", str(error))
            self.load_purchases()
