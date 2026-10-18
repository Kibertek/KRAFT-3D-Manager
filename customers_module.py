import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"

CUSTOMER_SOURCES = [
    "VK",
    "Авито",
    "Сайт KRAFT 3D",
    "Telegram",
    "Ozon",
    "Wildberries",
    "Рекомендация",
    "Другое",
]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_customer_tables():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                customer_type TEXT NOT NULL DEFAULT 'Частное лицо',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                source TEXT DEFAULT 'Другое',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_name
            ON customers(name)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_phone
            ON customers(phone)
        """)


class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.customer = dict(customer) if customer is not None else None
        self.setWindowTitle("Редактирование заказчика" if customer else "Новый заказчик")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Имя и фамилия или название компании")

        self.type_input = QComboBox()
        self.type_input.addItems(["Частное лицо", "Компания"])

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+7 ...")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")

        self.source_input = QComboBox()
        self.source_input.setEditable(True)
        self.source_input.addItems(CUSTOMER_SOURCES)
        self.source_input.setCurrentText("Другое")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Предпочтения, детали общения и другие заметки")
        self.notes_input.setMaximumHeight(110)

        form.addRow("Имя / компания *:", self.name_input)
        form.addRow("Тип заказчика:", self.type_input)
        form.addRow("Телефон:", self.phone_input)
        form.addRow("Электронная почта:", self.email_input)
        form.addRow("Источник:", self.source_input)
        form.addRow("Комментарий:", self.notes_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.customer:
            self.name_input.setText(self.customer.get("name") or "")
            self.type_input.setCurrentText(
                self.customer.get("customer_type") or "Частное лицо"
            )
            self.phone_input.setText(self.customer.get("phone") or "")
            self.email_input.setText(self.customer.get("email") or "")
            self.source_input.setCurrentText(
                self.customer.get("source") or "Другое"
            )
            self.notes_input.setPlainText(self.customer.get("notes") or "")

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Не указано имя", "Укажи имя заказчика или название компании.")
            self.name_input.setFocus()
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "customer_type": self.type_input.currentText().strip() or "Частное лицо",
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "source": self.source_input.currentText().strip() or "Другое",
            "notes": self.notes_input.toPlainText().strip(),
        }


class CustomersPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_customer_tables()
        self.setup_ui()
        self.load_customers()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(14)

        title = QLabel("Заказчики")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Контакты заказчиков и источник обращения. В дальнейшем карточки "
            "будут связываться с заказами и финансовыми операциями."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по имени, телефону, почте или источнику...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_customers)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Добавить заказчика")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_customer)
        toolbar.addWidget(add_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Имя / компания", "Тип", "Телефон", "Электронная почта",
            "Источник", "Дата добавления"
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
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.edit_customer)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("Заказчиков: 0")
        self.count_label.setObjectName("subtitle")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_customer)
        bottom.addWidget(edit_button)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_customer)
        bottom.addWidget(delete_button)
        layout.addLayout(bottom)

    def selected_customer_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def load_customers(self, *args):
        search = self.search_input.text().strip()
        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM customers
                    WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                       OR source LIKE ? OR customer_type LIKE ? OR notes LIKE ?
                    ORDER BY id DESC
                """, (pattern, pattern, pattern, pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM customers ORDER BY id DESC"
                ).fetchall()

        self.table.setRowCount(len(rows))
        for row_index, customer in enumerate(rows):
            values = [
                customer["name"],
                customer["customer_type"] or "",
                customer["phone"] or "",
                customer["email"] or "",
                customer["source"] or "",
                customer["created_at"] or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, customer["id"])
                self.table.setItem(row_index, column, item)

        self.count_label.setText(f"Заказчиков: {len(rows)}")

    def add_customer(self):
        dialog = CustomerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        with get_connection() as connection:
            connection.execute("""
                INSERT INTO customers (
                    name, customer_type, phone, email, source, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data["name"], data["customer_type"], data["phone"],
                data["email"], data["source"], data["notes"]
            ))
        self.load_customers()

    def edit_customer(self, *args):
        customer_id = self.selected_customer_id()
        if customer_id is None:
            QMessageBox.information(self, "Заказчик не выбран", "Сначала выбери заказчика в таблице.")
            return

        with get_connection() as connection:
            customer = connection.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
        if customer is None:
            self.load_customers()
            return

        dialog = CustomerDialog(self, customer)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        with get_connection() as connection:
            connection.execute("""
                UPDATE customers
                SET name = ?, customer_type = ?, phone = ?, email = ?,
                    source = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data["name"], data["customer_type"], data["phone"],
                data["email"], data["source"], data["notes"], customer_id
            ))
        self.load_customers()

    def delete_customer(self):
        customer_id = self.selected_customer_id()
        if customer_id is None:
            QMessageBox.information(self, "Заказчик не выбран", "Сначала выбери заказчика в таблице.")
            return

        answer = QMessageBox.question(
            self,
            "Удаление заказчика",
            "Удалить карточку заказчика? Это действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        with get_connection() as connection:
            connection.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        self.load_customers()
