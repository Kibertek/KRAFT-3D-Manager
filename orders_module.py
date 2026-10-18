import sqlite3
from pathlib import Path
from html import escape
from datetime import date, datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QTextDocument, QTextOption, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDoubleSpinBox, QSpinBox, QDateEdit, QFileDialog
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"

ORDER_STATUSES = [
    "Новый", "Согласован", "В производстве", "Готов", "Передан клиенту",
    "Отменён",
]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_order_tables():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL DEFAULT '',
                customer_id INTEGER,
                product_id INTEGER,
                customer_name TEXT NOT NULL DEFAULT '',
                customer_contact TEXT DEFAULT '',
                product_name TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL DEFAULT 0,
                total_price REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Новый',
                order_date TEXT NOT NULL DEFAULT '',
                due_date TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_number
            ON orders(order_number)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status
            ON orders(status)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_customer
            ON orders(customer_id)
        """)


def money(value):
    return f"{float(value or 0):,.2f} ₽".replace(",", " ").replace(".", ",")


class OrderDialog(QDialog):
    def __init__(self, parent=None, order=None):
        super().__init__(parent)
        self.order = dict(order) if order is not None else None
        self.customers = []
        self.products = []
        self.setWindowTitle("Редактирование заказа" if order else "Новый заказ")
        self.setMinimumWidth(540)

        with get_connection() as connection:
            self.customers = connection.execute(
                "SELECT id, name, phone, email FROM customers ORDER BY name COLLATE NOCASE"
            ).fetchall()
            self.products = connection.execute("""
                SELECT id, article, name, sale_price FROM products
                ORDER BY name COLLATE NOCASE
            """).fetchall()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.customer_combo = QComboBox()
        self.customer_combo.addItem("Без привязки к заказчику", None)
        for customer in self.customers:
            contact = customer["phone"] or customer["email"] or ""
            label = f'{customer["name"]} ({contact})' if contact else customer["name"]
            self.customer_combo.addItem(label, customer["id"])

        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Телефон или электронная почта")

        self.product_combo = QComboBox()
        self.product_combo.addItem("Произвольное изделие / услуга", None)
        for product in self.products:
            self.product_combo.addItem(
                f'{product["article"]} | {product["name"]}', product["id"]
            )
        self.product_combo.currentIndexChanged.connect(self.product_changed)

        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("Что нужно изготовить или выполнить")

        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 100000)
        self.quantity_input.setValue(1)
        self.quantity_input.valueChanged.connect(self.update_total)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999999)
        self.price_input.setDecimals(2)
        self.price_input.setSuffix(" ₽")
        self.price_input.setKeyboardTracking(False)
        self.price_input.valueChanged.connect(self.update_total)

        self.total_label = QLabel(money(0))
        self.total_label.setObjectName("pageTitle")

        self.status_combo = QComboBox()
        self.status_combo.addItems(ORDER_STATUSES)

        self.order_date_input = QDateEdit()
        self.order_date_input.setCalendarPopup(True)
        self.order_date_input.setDisplayFormat("dd.MM.yyyy")
        self.order_date_input.setDate(QDate.currentDate())

        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDisplayFormat("dd.MM.yyyy")
        self.due_date_input.setSpecialValueText("Не установлен")
        self.due_date_input.setMinimumDate(QDate(2000, 1, 1))
        self.due_date_input.setDate(QDate.currentDate())
        self.no_due_date = QComboBox()
        self.no_due_date.addItems(["Срок не установлен", "Указать срок"])
        self.no_due_date.currentIndexChanged.connect(
            lambda index: self.due_date_input.setEnabled(index == 1)
        )
        self.due_date_input.setEnabled(False)

        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("Требования, цвет, размеры, примечания...")
        self.comment_input.setMaximumHeight(100)

        form.addRow("Заказчик:", self.customer_combo)
        form.addRow("Контакт:", self.contact_input)
        form.addRow("Изделие из каталога:", self.product_combo)
        form.addRow("Наименование заказа *:", self.product_name_input)
        form.addRow("Количество:", self.quantity_input)
        form.addRow("Цена за единицу:", self.price_input)
        form.addRow("Сумма заказа:", self.total_label)
        form.addRow("Статус:", self.status_combo)
        form.addRow("Дата заказа:", self.order_date_input)
        form.addRow("Срок выполнения:", self.no_due_date)
        form.addRow("Дата выполнения:", self.due_date_input)
        form.addRow("Комментарий:", self.comment_input)
        layout.addLayout(form)

        self.customer_combo.currentIndexChanged.connect(self.customer_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.order:
            self.product_name_input.setText(self.order.get("product_name") or "")
            self.contact_input.setText(self.order.get("customer_contact") or "")
            self.quantity_input.setValue(int(self.order.get("quantity") or 1))
            self.price_input.setValue(float(self.order.get("unit_price") or 0))
            self.status_combo.setCurrentText(self.order.get("status") or "Новый")
            self.set_date(self.order_date_input, self.order.get("order_date"))
            if self.order.get("due_date"):
                self.no_due_date.setCurrentIndex(1)
                self.due_date_input.setEnabled(True)
                self.set_date(self.due_date_input, self.order.get("due_date"))
            self.comment_input.setPlainText(self.order.get("comment") or "")
            if self.order.get("customer_id") is not None:
                index = self.customer_combo.findData(self.order["customer_id"])
                if index >= 0:
                    self.customer_combo.setCurrentIndex(index)
            if self.order.get("product_id") is not None:
                index = self.product_combo.findData(self.order["product_id"])
                if index >= 0:
                    self.product_combo.setCurrentIndex(index)
        self.update_total()

    @staticmethod
    def set_date(widget, value):
        if not value:
            return
        parsed = QDate.fromString(str(value), "yyyy-MM-dd")
        if parsed.isValid():
            widget.setDate(parsed)

    def customer_changed(self, *_):
        customer_id = self.customer_combo.currentData()
        customer = next((c for c in self.customers if c["id"] == customer_id), None)
        if customer and not self.contact_input.text().strip():
            self.contact_input.setText(customer["phone"] or customer["email"] or "")

    def product_changed(self, *_):
        product_id = self.product_combo.currentData()
        product = next((p for p in self.products if p["id"] == product_id), None)
        if product:
            self.product_name_input.setText(product["name"])
            self.price_input.setValue(float(product["sale_price"] or 0))
        self.update_total()

    def update_total(self, *_):
        self.total_label.setText(money(self.quantity_input.value() * self.price_input.value()))

    def validate_and_accept(self):
        if not self.product_name_input.text().strip():
            QMessageBox.warning(self, "Не указано изделие", "Укажи название изделия или услуги.")
            self.product_name_input.setFocus()
            return
        self.accept()

    def get_data(self):
        customer_id = self.customer_combo.currentData()
        customer = next((c for c in self.customers if c["id"] == customer_id), None)
        return {
            "customer_id": customer_id,
            "product_id": self.product_combo.currentData(),
            "customer_name": customer["name"] if customer else "Не указан",
            "customer_contact": self.contact_input.text().strip(),
            "product_name": self.product_name_input.text().strip(),
            "quantity": self.quantity_input.value(),
            "unit_price": self.price_input.value(),
            "total_price": self.quantity_input.value() * self.price_input.value(),
            "status": self.status_combo.currentText(),
            "order_date": self.order_date_input.date().toString("yyyy-MM-dd"),
            "due_date": (
                self.due_date_input.date().toString("yyyy-MM-dd")
                if self.no_due_date.currentIndex() == 1 else ""
            ),
            "comment": self.comment_input.toPlainText().strip(),
        }


class OrdersPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_order_tables()
        self.setup_ui()
        self.load_orders()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(14)

        title = QLabel("Заказы")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Заказы связаны с карточками заказчиков и изделиями каталога. "
            "Название, цена и контакты сохраняются в заказе как снимок, "
            "поэтому последующие изменения карточек не перепишут старые заказы."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по номеру, заказчику, изделию или статусу...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_orders)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Новый заказ")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_order)
        toolbar.addWidget(add_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Номер", "Дата", "Заказчик", "Изделие", "Кол-во",
            "Сумма", "Статус", "Срок выполнения"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.edit_order)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("Заказов: 0")
        self.count_label.setObjectName("subtitle")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        for label, handler, object_name in [
            ("Печать A5", self.print_order, ""),
            ("Редактировать", self.edit_order, ""),
            ("Удалить", self.delete_order, "dangerButton"),
        ]:
            button = QPushButton(label)
            if object_name:
                button.setObjectName(object_name)
            button.clicked.connect(handler)
            bottom.addWidget(button)
        layout.addLayout(bottom)

    def selected_order_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def load_orders(self, *_):
        search = self.search_input.text().strip()
        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM orders
                    WHERE order_number LIKE ? OR customer_name LIKE ?
                       OR product_name LIKE ? OR status LIKE ? OR customer_contact LIKE ?
                    ORDER BY id DESC
                """, (pattern, pattern, pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()

        self.table.setRowCount(len(rows))
        for row_index, order in enumerate(rows):
            due_date = order["due_date"] or "Не указан"
            values = [
                order["order_number"],
                self.display_date(order["order_date"]),
                order["customer_name"] or "Не указан",
                order["product_name"],
                str(order["quantity"]),
                money(order["total_price"]),
                order["status"],
                self.display_date(due_date) if due_date != "Не указан" else due_date,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, order["id"])
                self.table.setItem(row_index, column, item)
        self.count_label.setText(f"Заказов: {len(rows)}")

    @staticmethod
    def display_date(value):
        if not value:
            return ""
        parsed = QDate.fromString(str(value), "yyyy-MM-dd")
        return parsed.toString("dd.MM.yyyy") if parsed.isValid() else str(value)

    def get_order(self, order_id):
        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()

    def add_order(self):
        dialog = OrderDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            with get_connection() as connection:
                temporary_number = f'TEMP-{datetime.now().strftime("%Y%m%d%H%M%S%f")}'
                cursor = connection.execute("""
                    INSERT INTO orders (
                        order_number, customer_id, product_id, customer_name,
                        customer_contact, product_name, quantity, unit_price,
                        total_price, status, order_date, due_date, comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    temporary_number, data["customer_id"], data["product_id"], data["customer_name"],
                    data["customer_contact"], data["product_name"], data["quantity"],
                    data["unit_price"], data["total_price"], data["status"],
                    data["order_date"], data["due_date"], data["comment"]
                ))
                order_id = cursor.lastrowid
                order_number = f"K3D-{date.today().year}-{order_id:05d}"
                connection.execute(
                    "UPDATE orders SET order_number = ? WHERE id = ?",
                    (order_number, order_id)
                )
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось сохранить заказ:\n{error}")
            return
        self.load_orders()

    def edit_order(self, *_):
        order_id = self.selected_order_id()
        if order_id is None:
            QMessageBox.information(self, "Заказ не выбран", "Сначала выбери заказ в таблице.")
            return
        order = self.get_order(order_id)
        if order is None:
            self.load_orders()
            return
        dialog = OrderDialog(self, order)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            with get_connection() as connection:
                connection.execute("""
                    UPDATE orders SET customer_id = ?, product_id = ?,
                        customer_name = ?, customer_contact = ?, product_name = ?,
                        quantity = ?, unit_price = ?, total_price = ?, status = ?,
                        order_date = ?, due_date = ?, comment = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    data["customer_id"], data["product_id"], data["customer_name"],
                    data["customer_contact"], data["product_name"], data["quantity"],
                    data["unit_price"], data["total_price"], data["status"],
                    data["order_date"], data["due_date"], data["comment"], order_id
                ))
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось обновить заказ:\n{error}")
            return
        self.load_orders()

    def delete_order(self):
        order_id = self.selected_order_id()
        if order_id is None:
            QMessageBox.information(self, "Заказ не выбран", "Сначала выбери заказ в таблице.")
            return
        order = self.get_order(order_id)
        if order is None:
            self.load_orders()
            return
        answer = QMessageBox.question(
            self, "Удаление заказа",
            f'Удалить заказ {order["order_number"]}? Это действие нельзя отменить.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        with get_connection() as connection:
            connection.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        self.load_orders()

    def print_order(self):
        order_id = self.selected_order_id()
        if order_id is None:
            QMessageBox.information(self, "Заказ не выбран", "Сначала выбери заказ для печати.")
            return
        order = self.get_order(order_id)
        if order is None:
            self.load_orders()
            return

        safe = lambda value: escape(str(value or "")).replace("\n", "<br>")
        due = self.display_date(order["due_date"]) if order["due_date"] else "Не установлен"
        html = f"""
        <html><head><meta charset="utf-8">
        <style>
        body {{ font-family: Arial, sans-serif; color: #111; font-size: 10pt; }}
        h1 {{ font-size: 18pt; text-align: center; margin-bottom: 4px; }}
        .sub {{ text-align: center; color: #555; margin-bottom: 18px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
        td, th {{ border: 1px solid #777; padding: 7px; vertical-align: top; word-break: normal; overflow-wrap: normal; hyphens: none; }}
        th {{ background: #eee; text-align: left; }}
        .total {{ font-size: 13pt; font-weight: bold; text-align: right; margin-top: 15px; }}
        .sign {{ margin-top: 35px; }}
        </style></head><body>
        <h1>ЗАКАЗ KRAFT 3D</h1>
        <div class="sub">Управление производством и изготовлением изделий</div>
        <table>
          <tr><th>Номер заказа</th><td>{safe(order["order_number"])}</td><th>Статус</th><td>{safe(order["status"])}</td></tr>
          <tr><th>Дата заказа</th><td>{safe(self.display_date(order["order_date"]))}</td><th>Срок выполнения</th><td>{safe(due)}</td></tr>
          <tr><th>Заказчик</th><td colspan="3">{safe(order["customer_name"])}</td></tr>
          <tr><th>Контакт</th><td colspan="3">{safe(order["customer_contact"]) or "Не указан"}</td></tr>
        </table>
        <table>
          <tr><th>Изделие / услуга</th><th>Количество</th><th>Цена за единицу</th><th>Сумма</th></tr>
          <tr><td>{safe(order["product_name"])}</td><td>{order["quantity"]}</td><td>{money(order["unit_price"])}</td><td>{money(order["total_price"])}</td></tr>
        </table>
        <div class="total">Итого: {money(order["total_price"])}</div>
        <p><b>Комментарий / требования:</b><br>{safe(order["comment"]) or "Не указаны"}</p>
        <div class="sign">Заказчик: ____________________ &nbsp;&nbsp; Исполнитель: ____________________</div>
        </body></html>
        """

        choice_dialog = QMessageBox(self)
        choice_dialog.setWindowTitle("Заказ " + str(order["order_number"]))
        choice_dialog.setText("Что сделать с заказом?")
        choice_dialog.setInformativeText("Формат документа: A5, книжная ориентация.")
        print_button = choice_dialog.addButton(
            "Отправить на печать", QMessageBox.ButtonRole.AcceptRole
        )
        pdf_button = choice_dialog.addButton(
            "Сохранить в PDF", QMessageBox.ButtonRole.ActionRole
        )
        choice_dialog.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        choice_dialog.exec()
        selected_button = choice_dialog.clickedButton()

        if selected_button not in (print_button, pdf_button):
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
        printer.setDocName(f'Заказ {order["order_number"]}')

        if selected_button == print_button:
            print_dialog = QPrintDialog(printer, self)
            print_dialog.setWindowTitle("Печать заказа A5")
            if print_dialog.exec() != QDialog.DialogCode.Accepted:
                return
        else:
            default_filename = f'Заказ_{order["order_number"]}.pdf'
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить заказ в PDF",
                str(BASE_DIR / default_filename),
                "PDF-файлы (*.pdf)"
            )
            if not file_path:
                return
            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)

        document = QTextDocument(self)
        document.setDefaultTextOption(QTextOption(QTextOption.WrapMode.WordWrap))
        document.setHtml(html)
        document.print_(printer)
