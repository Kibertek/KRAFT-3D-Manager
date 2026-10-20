import sqlite3
from pathlib import Path

from finance_module import initialize_finance_tables

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
        purchase_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(purchases)").fetchall()
        }
        if "finance_transaction_id" not in purchase_columns:
            connection.execute(
                "ALTER TABLE purchases ADD COLUMN finance_transaction_id INTEGER"
            )
        if "printer_id" not in purchase_columns:
            connection.execute(
                "ALTER TABLE purchases ADD COLUMN printer_id INTEGER"
            )
    initialize_finance_tables()


class PurchaseDialog(QDialog):
    def __init__(self, parent=None, purchase=None):
        super().__init__(parent)
        self.purchase = dict(purchase) if purchase is not None else None
        self.setWindowTitle("Редактирование закупки" if self.purchase else "Добавить закупку")
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
        self.type_input.addItem("Запчасть для принтера", "part")

        self.item_input = QComboBox()
        self.printer_input = QComboBox()
        self.printer_input.setMinimumWidth(260)
        self.item_input.setMinimumWidth(260)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0.001, 100000000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setValue(1)
        self.quantity_input.setSuffix(" ед.")
        self.quantity_input.setMinimumHeight(38)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 100000000)
        self.price_input.setDecimals(2)
        self.price_input.setSingleStep(10)
        self.price_input.setSuffix(" ₽")
        self.price_input.setMinimumHeight(38)

        numeric_style = """
            QDoubleSpinBox {
                background-color: #252525;
                color: #f2f2f2;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 8px;
                selection-background-color: #75421e;
                selection-color: #ffffff;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #ff7a00;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #383838;
                border: none;
                width: 20px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #505050;
            }
        """
        self.quantity_input.setStyleSheet(numeric_style)
        self.price_input.setStyleSheet(numeric_style)

        # Дополнительное оформление всплывающих элементов: календаря,
        # списков выбора и внутренних полей ввода чисел.
        popup_style = """
            QCalendarWidget QWidget {
                background-color: #252525;
                color: #f2f2f2;
            }
            QCalendarWidget QToolButton {
                background-color: #383838;
                color: #f2f2f2;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
            }
            QCalendarWidget QMenu {
                background-color: #252525;
                color: #f2f2f2;
                border: 1px solid #555555;
            }
            QCalendarWidget QSpinBox {
                background-color: #252525;
                color: #f2f2f2;
                border: 1px solid #555555;
            }
            QCalendarWidget QAbstractItemView {
                background-color: #252525;
                color: #f2f2f2;
                selection-background-color: #ff7a00;
                selection-color: #ffffff;
                alternate-background-color: #303030;
            }
            QComboBox {
                background-color: #252525;
                color: #f2f2f2;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #252525;
                color: #f2f2f2;
                selection-background-color: #75421e;
                selection-color: #ffffff;
                border: 1px solid #555555;
                outline: 0;
            }
            QDateEdit {
                background-color: #252525;
                color: #f2f2f2;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 24px;
            }
            QDateEdit QCalendarWidget QToolButton {
                background-color: #383838;
                color: #f2f2f2;
            }
        """
        self.setStyleSheet(popup_style)

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
        form.addRow("Для принтера:", self.printer_input)
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
        self.type_input.currentIndexChanged.connect(self.update_printer_visibility)
        self.item_input.currentIndexChanged.connect(self.select_item)
        self.load_printers()
        self.update_printer_visibility()
        self.quantity_input.valueChanged.connect(self.update_total)
        self.price_input.valueChanged.connect(self.update_total)

        self.load_items()
        if self.purchase:
            self.load_purchase_values()
        self.update_total()

    def load_printers(self):
        current = self.printer_input.currentData()
        self.printer_input.clear()
        with get_connection() as connection:
            rows = connection.execute("SELECT id, name, model FROM printers ORDER BY name COLLATE NOCASE").fetchall()
        self.printer_input.addItem("Не выбран", None)
        for printer in rows:
            label = printer["name"] + (f' ({printer["model"]})' if printer["model"] else "")
            self.printer_input.addItem(label, int(printer["id"]))
        if current is not None:
            index = self.printer_input.findData(current)
            if index >= 0:
                self.printer_input.setCurrentIndex(index)

    def update_printer_visibility(self, *_):
        is_part = self.type_input.currentData() == "part"
        self.printer_input.setEnabled(is_part)

    def load_purchase_values(self):
        purchase = self.purchase
        target_type = purchase.get("item_type", "material")
        index = self.type_input.findData(target_type)
        if index >= 0:
            self.type_input.setCurrentIndex(index)
        self.load_items()

        target_id = purchase.get("item_id")
        for index in range(self.item_input.count()):
            row = self.item_input.itemData(index)
            if row and row.get("id") == target_id:
                self.item_input.setCurrentIndex(index)
                break

        date = QDate.fromString(purchase.get("purchase_date", ""), "yyyy-MM-dd")
        if date.isValid():
            self.date_input.setDate(date)
        self.quantity_input.setValue(float(purchase.get("quantity") or 1))
        self.price_input.setValue(float(purchase.get("unit_price") or 0))
        self.supplier_input.setText(purchase.get("supplier") or "")
        self.notes_input.setPlainText(purchase.get("notes") or "")
        printer_index = self.printer_input.findData(purchase.get("printer_id"))
        if printer_index >= 0:
            self.printer_input.setCurrentIndex(printer_index)
        self.stock_label.setText("Редактируется существующая закупка")
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
            elif item_type == "part":
                rows = connection.execute("""
                    SELECT id, name, COALESCE(unit, 'шт.') AS unit,
                           COALESCE(price, 0) AS price, COALESCE(quantity, 0) AS quantity
                    FROM components
                    WHERE TRIM(COALESCE(category, '')) NOT IN ('Упаковка', 'упаковка')
                    ORDER BY name COLLATE NOCASE
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
        if self.type_input.currentData() == "part" and self.printer_input.currentData() is None:
            QMessageBox.warning(self, "Не выбран принтер", "Для закупки запчасти выбери принтер, для которого она предназначена.")
            return
        self.accept()

    def get_data(self):
        row = self.item_input.currentData()
        return {
            "purchase_date": self.date_input.date().toString("yyyy-MM-dd"),
            "item_type": self.type_input.currentData(),
            "item_id": int(row["id"]),
            "printer_id": self.printer_input.currentData() if self.type_input.currentData() == "part" else None,
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

        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_selected_purchase)
        toolbar.addWidget(edit_button)

        delete_button = QPushButton("Удалить закупку")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_purchase)
        toolbar.addWidget(delete_button)

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
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(3, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        # Растягиваем последний столбец на свободную ширину таблицы.
        header.setStretchLastSection(True)
        self.table.doubleClicked.connect(self.edit_selected_purchase)
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
            type_label = {"material": "Материал", "component": "Комплектующее / упаковка", "part": "Запчасть для принтера"}.get(purchase["item_type"], "Комплектующее")
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

    def selected_purchase_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def edit_selected_purchase(self, *args):
        purchase_id = self.selected_purchase_id()
        if purchase_id is None:
            QMessageBox.information(
                self, "Закупка не выбрана",
                "Выбери запись в таблице, которую нужно отредактировать."
            )
            return

        with get_connection() as connection:
            purchase = connection.execute(
                "SELECT * FROM purchases WHERE id = ?", (purchase_id,)
            ).fetchone()

        if purchase is None:
            QMessageBox.warning(self, "Запись не найдена", "Обнови список закупок и попробуй снова.")
            self.load_purchases()
            return

        dialog = PurchaseDialog(self, purchase)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_data = dialog.get_data()
        old_data = dict(purchase)
        try:
            with get_connection() as connection:
                # Обновляем остатки только на разницу, а не прибавляем закупку повторно.
                self.apply_stock_change(connection, old_data, -1)
                self.apply_stock_change(connection, new_data, 1)

                connection.execute("""
                    UPDATE purchases
                    SET purchase_date = ?, item_type = ?, item_id = ?, item_name = ?,
                        quantity = ?, unit = ?, unit_price = ?, total = ?,
                        supplier = ?, notes = ?, printer_id = ?
                    WHERE id = ?
                """, (
                    new_data["purchase_date"], new_data["item_type"], new_data["item_id"],
                    new_data["item_name"], new_data["quantity"], new_data["unit"],
                    new_data["unit_price"], new_data["total"], new_data["supplier"],
                    new_data["notes"], new_data.get("printer_id"), purchase_id
                ))
                self.sync_finance_expense(
                    connection, purchase_id, new_data,
                    old_data.get("finance_transaction_id")
                )

            self.load_purchases()
            QMessageBox.information(
                self, "Закупка обновлена",
                "Изменения сохранены, остатки скорректированы."
            )
        except Exception as error:
            QMessageBox.critical(self, "Ошибка редактирования", str(error))
            self.load_purchases()

    def apply_stock_change(self, connection, data, direction):
        quantity = float(data.get("quantity") or 0) * direction
        item_id = data.get("item_id")
        if data.get("item_type") == "material":
            item = connection.execute(
                "SELECT spool_weight, spool_price, spool_count FROM materials WHERE id = ?",
                (item_id,)
            ).fetchone()
            if item is None:
                raise ValueError("Материал из закупки не найден в справочнике.")

            current_count = float(item["spool_count"] or 0)
            updated_count = current_count + quantity
            if updated_count < -0.000001:
                raise ValueError(
                    "Нельзя уменьшить остаток материала ниже нуля. "
                    "Возможно, часть материала уже была использована. "
                    "Проверь остаток перед изменением этой закупки."
                )

            # При обратном применении старой записи меняем только остаток.
            # Новая цена применяется только при добавлении новой/изменённой закупки.
            new_price = float(data.get("unit_price") or 0)
            weight = float(item["spool_weight"] or 1000)
            if weight <= 0:
                weight = 1000
            if direction > 0:
                old_price = float(item["spool_price"] or 0)
                connection.execute("""
                    UPDATE materials
                    SET spool_count = ?, spool_price = ?, price_per_gram = ?
                    WHERE id = ?
                """, (max(0, updated_count), new_price, new_price / weight, item_id))
                if abs(old_price - new_price) > 0.000001:
                    connection.execute("""
                        INSERT INTO material_price_history (
                            material_id, old_weight, new_weight, old_price, new_price
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (item_id, weight, weight, old_price, new_price))
            else:
                connection.execute(
                    "UPDATE materials SET spool_count = ? WHERE id = ?",
                    (max(0, updated_count), item_id)
                )
        else:
            item = connection.execute(
                "SELECT quantity FROM components WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None:
                raise ValueError("Комплектующее из закупки не найдено в справочнике.")
            updated_count = float(item["quantity"] or 0) + quantity
            if updated_count < -0.000001:
                raise ValueError(
                    "Нельзя уменьшить остаток комплектующего ниже нуля. "
                    "Возможно, часть уже была использована. Проверь складской остаток."
                )
            if direction > 0:
                connection.execute("""
                    UPDATE components SET quantity = ?, price = ? WHERE id = ?
                """, (max(0, updated_count), float(data.get("unit_price") or 0), item_id))
            else:
                connection.execute(
                    "UPDATE components SET quantity = ? WHERE id = ?",
                    (max(0, updated_count), item_id)
                )

    def sync_finance_expense(self, connection, purchase_id, data, finance_id=None):
        """Создаёт или обновляет ровно одну финансовую запись для закупки."""
        if data.get("item_type") == "material":
            category = "Материалы"
        else:
            component = connection.execute(
                "SELECT category FROM components WHERE id = ?",
                (data.get("item_id"),)
            ).fetchone()
            component_category = (component["category"] or "") if component else ""
            category = "Упаковка" if "упаков" in component_category.lower() else "Комплектующие"

        quantity_text = number(data.get("quantity") or 0)
        unit = data.get("unit") or "ед."
        comment_parts = [
            f'Закупка: {data.get("item_name", "позиция")} — {quantity_text} {unit}'
        ]
        if data.get("notes"):
            comment_parts.append(str(data["notes"]).strip())
        comment = ". ".join(part for part in comment_parts if part)

        values = (
            data.get("purchase_date") or QDate.currentDate().toString("yyyy-MM-dd"),
            category,
            float(data.get("total") or 0),
            (data.get("supplier") or "").strip() or "Поставщик",
            comment,
        )

        existing = None
        if finance_id:
            existing = connection.execute(
                "SELECT id FROM finance_transactions WHERE id = ?",
                (finance_id,)
            ).fetchone()

        if existing:
            connection.execute("""
                UPDATE finance_transactions
                SET operation_date = ?, operation_type = 'Расход', category = ?,
                    amount = ?, source = ?, marketplace = '', order_id = NULL,
                    order_number = '', comment = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (*values, finance_id))
        else:
            cursor = connection.execute("""
                INSERT INTO finance_transactions (
                    operation_date, operation_type, category, amount, source,
                    order_id, order_number, marketplace, comment
                ) VALUES (?, 'Расход', ?, ?, ?, NULL, '', '', ?)
            """, values)
            finance_id = cursor.lastrowid

        connection.execute(
            "UPDATE purchases SET finance_transaction_id = ? WHERE id = ?",
            (finance_id, purchase_id)
        )

    def delete_selected_purchase(self):
        purchase_id = self.selected_purchase_id()
        if purchase_id is None:
            QMessageBox.information(
                self, "Закупка не выбрана",
                "Выбери закупку, которую нужно удалить."
            )
            return

        with get_connection() as connection:
            purchase = connection.execute(
                "SELECT * FROM purchases WHERE id = ?", (purchase_id,)
            ).fetchone()

        if purchase is None:
            self.load_purchases()
            return

        answer = QMessageBox.question(
            self, "Удаление закупки",
            f'Удалить закупку «{purchase["item_name"]}» на сумму {money(purchase["total"])}? '
            "Складской остаток будет уменьшен, а связанный расход удалён из финансов.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_connection() as connection:
                self.apply_stock_change(connection, dict(purchase), -1)
                finance_id = purchase["finance_transaction_id"]
                if finance_id:
                    connection.execute(
                        "DELETE FROM finance_transactions WHERE id = ?",
                        (finance_id,)
                    )
                connection.execute(
                    "DELETE FROM purchases WHERE id = ?", (purchase_id,)
                )
            self.load_purchases()
            QMessageBox.information(
                self, "Закупка удалена",
                "Закупка удалена, склад и финансовая запись обновлены."
            )
        except Exception as error:
            QMessageBox.critical(
                self, "Не удалось удалить закупку",
                f"{error}\n\nЕсли часть материала уже использована, сначала проверь остаток."
            )
            self.load_purchases()

    def add_purchase(self):
        dialog = PurchaseDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        try:
            with get_connection() as connection:
                # Изменение склада и запись закупки выполняются одной транзакцией.
                self.apply_stock_change(connection, data, 1)
                cursor = connection.execute("""
                    INSERT INTO purchases (
                        purchase_date, item_type, item_id, item_name,
                        quantity, unit, unit_price, total, supplier, notes, printer_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["purchase_date"], data["item_type"], data["item_id"],
                    data["item_name"], data["quantity"], data["unit"],
                    data["unit_price"], data["total"], data["supplier"], data["notes"], data.get("printer_id")
                ))
                purchase_id = cursor.lastrowid
                self.sync_finance_expense(connection, purchase_id, data)
                if data.get("item_type") == "part" and data.get("printer_id"):
                    connection.execute(
                        "INSERT OR IGNORE INTO component_printer_compatibility (component_id, printer_id) VALUES (?, ?)",
                        (data["item_id"], data["printer_id"])
                    )

            self.load_purchases()
            QMessageBox.information(
                self, "Закупка сохранена",
                "Закупка записана, складской остаток обновлён."
            )
        except Exception as error:
            QMessageBox.critical(self, "Ошибка закупки", str(error))
            self.load_purchases()
