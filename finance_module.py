import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDoubleSpinBox, QDateEdit
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"

INCOME_CATEGORIES = [
    "Оплата заказа", "Продажа на маркетплейсе", "Услуга", "Прочий доход"
]
EXPENSE_CATEGORIES = [
    "Материалы", "Комплектующие", "Упаковка", "Маркетплейс и комиссия",
    "Доставка", "Оборудование", "Электричество", "Реклама", "Подписки",
    "Налоги", "Возврат клиенту", "Прочий расход"
]
SOURCES = [
    "Заказчик", "Ozon", "Wildberries", "VK", "Авито",
    "Сайт KRAFT 3D", "Telegram", "Поставщик", "Другое"
]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_finance_tables():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS finance_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_date TEXT NOT NULL,
                operation_type TEXT NOT NULL DEFAULT 'Расход',
                category TEXT NOT NULL DEFAULT 'Прочее',
                amount REAL NOT NULL DEFAULT 0,
                source TEXT DEFAULT '',
                order_id INTEGER,
                order_number TEXT DEFAULT '',
                marketplace TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_finance_date
            ON finance_transactions(operation_date)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_finance_type
            ON finance_transactions(operation_type)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_finance_order
            ON finance_transactions(order_id)
        """)


def money(value):
    return f"{float(value or 0):,.2f} ₽".replace(",", " ").replace(".", ",")


class FinanceDialog(QDialog):
    def __init__(self, parent=None, transaction=None):
        super().__init__(parent)
        self.transaction = dict(transaction) if transaction is not None else None
        self.orders = []

        self.setWindowTitle("Редактирование операции" if transaction else "Новая финансовая операция")
        self.setMinimumWidth(540)

        with get_connection() as connection:
            self.orders = connection.execute("""
                SELECT id, order_number, customer_name, product_name, total_price
                FROM orders
                ORDER BY id DESC
            """).fetchall()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd.MM.yyyy")
        self.date_input.setDate(QDate.currentDate())

        self.type_input = QComboBox()
        self.type_input.addItems(["Расход", "Доход"])

        self.category_input = QComboBox()
        self.category_input.setEditable(True)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 999999999)
        self.amount_input.setDecimals(2)
        self.amount_input.setSuffix(" ₽")
        self.amount_input.setKeyboardTracking(False)

        self.source_input = QComboBox()
        self.source_input.setEditable(True)
        self.source_input.addItems(SOURCES)

        self.marketplace_input = QComboBox()
        self.marketplace_input.setEditable(True)
        self.marketplace_input.addItems(["Не применяется", "Ozon", "Wildberries", "Другая площадка"])
        self.marketplace_input.setCurrentText("Не применяется")

        self.order_input = QComboBox()
        self.order_input.addItem("Без привязки к заказу", None)
        for order in self.orders:
            label = f'{order["order_number"]} | {order["customer_name"]} | {order["product_name"]}'
            self.order_input.addItem(label, order["id"])

        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("Назначение платежа, номер чека, комиссия и другие примечания")
        self.comment_input.setMaximumHeight(100)

        form.addRow("Дата операции:", self.date_input)
        form.addRow("Тип операции:", self.type_input)
        form.addRow("Категория:", self.category_input)
        form.addRow("Сумма:", self.amount_input)
        form.addRow("Источник:", self.source_input)
        form.addRow("Маркетплейс:", self.marketplace_input)
        form.addRow("Связанный заказ:", self.order_input)
        form.addRow("Комментарий:", self.comment_input)
        layout.addLayout(form)

        self.type_input.currentTextChanged.connect(self.load_categories)
        self.order_input.currentIndexChanged.connect(self.order_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_categories()

        if self.transaction:
            item = self.transaction
            parsed = QDate.fromString(item.get("operation_date", ""), "yyyy-MM-dd")
            if parsed.isValid():
                self.date_input.setDate(parsed)
            self.type_input.setCurrentText(item.get("operation_type") or "Расход")
            self.load_categories()
            self.category_input.setCurrentText(item.get("category") or "")
            self.amount_input.setValue(float(item.get("amount") or 0.01))
            self.source_input.setCurrentText(item.get("source") or "")
            self.marketplace_input.setCurrentText(item.get("marketplace") or "Не применяется")
            if item.get("order_id") is not None:
                index = self.order_input.findData(item["order_id"])
                if index >= 0:
                    self.order_input.setCurrentIndex(index)
            self.comment_input.setPlainText(item.get("comment") or "")

    def load_categories(self, *_):
        previous = self.category_input.currentText() if hasattr(self, "category_input") else ""
        self.category_input.clear()
        categories = INCOME_CATEGORIES if self.type_input.currentText() == "Доход" else EXPENSE_CATEGORIES
        self.category_input.addItems(categories)
        if previous:
            self.category_input.setCurrentText(previous)
        elif categories:
            self.category_input.setCurrentIndex(0)

    def order_changed(self, *_):
        order_id = self.order_input.currentData()
        order = next((row for row in self.orders if row["id"] == order_id), None)
        if order and not self.comment_input.toPlainText().strip():
            self.comment_input.setPlainText(
                f'Оплата по заказу {order["order_number"]}'
            )

    def validate_and_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Проверь сумму", "Сумма операции должна быть больше нуля.")
            return
        if not self.category_input.currentText().strip():
            QMessageBox.warning(self, "Не указана категория", "Укажи категорию финансовой операции.")
            self.category_input.setFocus()
            return
        self.accept()

    def get_data(self):
        order_id = self.order_input.currentData()
        order = next((row for row in self.orders if row["id"] == order_id), None)
        marketplace = self.marketplace_input.currentText().strip()
        if marketplace == "Не применяется":
            marketplace = ""
        return {
            "operation_date": self.date_input.date().toString("yyyy-MM-dd"),
            "operation_type": self.type_input.currentText(),
            "category": self.category_input.currentText().strip(),
            "amount": self.amount_input.value(),
            "source": self.source_input.currentText().strip(),
            "order_id": order_id,
            "order_number": order["order_number"] if order else "",
            "marketplace": marketplace,
            "comment": self.comment_input.toPlainText().strip(),
        }


class FinancePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_finance_tables()
        self.setup_ui()
        self.load_transactions()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(14)

        title = QLabel("Финансы")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Ручной учёт фактических доходов и расходов. Создание заказа само по себе "
            "не записывает доход: внеси операцию, когда платёж действительно состоялся."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по категории, источнику, заказу, маркетплейсу или комментарию...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_transactions)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Добавить операцию")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_transaction)
        toolbar.addWidget(add_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Дата", "Тип", "Категория", "Сумма", "Источник", "Заказ / площадка", "Комментарий"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.edit_transaction)
        layout.addWidget(self.table, 1)

        totals = QHBoxLayout()
        self.count_label = QLabel("Операций: 0")
        self.count_label.setObjectName("subtitle")
        totals.addWidget(self.count_label)
        totals.addStretch()

        self.income_label = QLabel("Доходы: 0,00 ₽")
        self.income_label.setObjectName("subtitle")
        totals.addWidget(self.income_label)

        self.expense_label = QLabel("Расходы: 0,00 ₽")
        self.expense_label.setObjectName("subtitle")
        totals.addWidget(self.expense_label)

        self.balance_label = QLabel("Разница: 0,00 ₽")
        self.balance_label.setObjectName("pageTitle")
        totals.addWidget(self.balance_label)
        layout.addLayout(totals)

        buttons = QHBoxLayout()
        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_transaction)
        buttons.addWidget(edit_button)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_transaction)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        layout.addLayout(buttons)

    @staticmethod
    def display_date(value):
        parsed = QDate.fromString(str(value or ""), "yyyy-MM-dd")
        return parsed.toString("dd.MM.yyyy") if parsed.isValid() else str(value or "")

    def load_transactions(self, *_):
        search = self.search_input.text().strip()
        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM finance_transactions
                    WHERE category LIKE ? OR source LIKE ? OR order_number LIKE ?
                       OR marketplace LIKE ? OR comment LIKE ? OR operation_type LIKE ?
                    ORDER BY operation_date DESC, id DESC
                """, (pattern, pattern, pattern, pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute("""
                    SELECT * FROM finance_transactions
                    ORDER BY operation_date DESC, id DESC
                """).fetchall()

        self.table.setRowCount(len(rows))
        income = 0.0
        expense = 0.0

        for row_index, transaction in enumerate(rows):
            amount = float(transaction["amount"] or 0)
            if transaction["operation_type"] == "Доход":
                income += amount
            else:
                expense += amount

            order_and_market = " / ".join(
                value for value in [
                    transaction["order_number"] or "",
                    transaction["marketplace"] or ""
                ] if value
            ) or "—"

            values = [
                self.display_date(transaction["operation_date"]),
                transaction["operation_type"],
                transaction["category"],
                money(amount),
                transaction["source"] or "—",
                order_and_market,
                transaction["comment"] or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, transaction["id"])
                if column == 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row_index, column, item)

        self.count_label.setText(f"Операций: {len(rows)}")
        self.income_label.setText(f"Доходы: {money(income)}")
        self.expense_label.setText(f"Расходы: {money(expense)}")
        self.balance_label.setText(f"Разница: {money(income - expense)}")

    def selected_transaction_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def get_transaction(self, transaction_id):
        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM finance_transactions WHERE id = ?", (transaction_id,)
            ).fetchone()

    def add_transaction(self):
        dialog = FinanceDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            with get_connection() as connection:
                connection.execute("""
                    INSERT INTO finance_transactions (
                        operation_date, operation_type, category, amount, source,
                        order_id, order_number, marketplace, comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["operation_date"], data["operation_type"], data["category"],
                    data["amount"], data["source"], data["order_id"], data["order_number"],
                    data["marketplace"], data["comment"]
                ))
            self.load_transactions()
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось сохранить операцию:\n{error}")

    def edit_transaction(self, *_):
        transaction_id = self.selected_transaction_id()
        if transaction_id is None:
            QMessageBox.information(self, "Операция не выбрана", "Выбери запись в таблице.")
            return
        transaction = self.get_transaction(transaction_id)
        if transaction is None:
            self.load_transactions()
            return

        dialog = FinanceDialog(self, transaction)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            with get_connection() as connection:
                connection.execute("""
                    UPDATE finance_transactions SET
                        operation_date = ?, operation_type = ?, category = ?, amount = ?,
                        source = ?, order_id = ?, order_number = ?, marketplace = ?,
                        comment = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    data["operation_date"], data["operation_type"], data["category"],
                    data["amount"], data["source"], data["order_id"], data["order_number"],
                    data["marketplace"], data["comment"], transaction_id
                ))
            self.load_transactions()
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось обновить операцию:\n{error}")

    def delete_transaction(self):
        transaction_id = self.selected_transaction_id()
        if transaction_id is None:
            QMessageBox.information(self, "Операция не выбрана", "Выбери запись в таблице.")
            return
        transaction = self.get_transaction(transaction_id)
        if transaction is None:
            self.load_transactions()
            return

        answer = QMessageBox.question(
            self, "Удаление операции",
            f'Удалить финансовую операцию на сумму {money(transaction["amount"])}?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        with get_connection() as connection:
            connection.execute(
                "DELETE FROM finance_transactions WHERE id = ?", (transaction_id,)
            )
        self.load_transactions()
