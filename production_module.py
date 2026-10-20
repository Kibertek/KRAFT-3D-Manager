"""Учёт производственных партий и остатков готовой продукции KRAFT 3D."""
import sqlite3
from pathlib import Path
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QComboBox, QDateEdit, QDoubleSpinBox, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox, QDialog, QDialogButtonBox, QTextEdit)

DB_PATH = Path(__file__).resolve().parent / "data" / "kraft3d.db"

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def initialize_production_tables():
    with get_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS production_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            production_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_production_batches_product ON production_batches(product_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_production_batches_date ON production_batches(production_date)")
        connection.execute("""CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL CHECK(movement_type IN ('sale','return','writeoff','reserve','release')),
            quantity REAL NOT NULL CHECK(quantity > 0), movement_date TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'manual', source_id TEXT NOT NULL DEFAULT '',
            notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id))""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_date ON stock_movements(movement_date)")
        connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_movements_source
            ON stock_movements(source_type, source_id, movement_type) WHERE source_id != ''""")

class ProductionBatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Записать готовую партию")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.product = QComboBox()
        self.product.setMinimumWidth(280)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.001, 1000000)
        self.quantity.setDecimals(3)
        self.quantity.setValue(1)
        self.quantity.setSuffix(" шт.")
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        self.date.setDate(QDate.currentDate())
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(85)
        self.notes.setPlaceholderText("Например: партия из 10 брелоков, чёрный PETG")
        with get_connection() as connection:
            products = connection.execute("SELECT id, article, name FROM products WHERE status != 'Снято с производства' ORDER BY name COLLATE NOCASE").fetchall()
        for product in products:
            self.product.addItem(f"{product['article']} | {product['name']}", int(product["id"]))
        form.addRow("Изделие:", self.product)
        form.addRow("Количество готовых изделий:", self.quantity)
        form.addRow("Дата производства:", self.date)
        form.addRow("Комментарий:", self.notes)
        layout.addLayout(form)
        self.stock_label = QLabel("Сохранённая партия увеличит остаток готовой продукции.")
        self.stock_label.setWordWrap(True)
        layout.addWidget(self.stock_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if not products:
            self.product.setEnabled(False)
            self.stock_label.setText("Сначала добавь изделие в каталоге.")

    def validate_and_accept(self):
        if self.product.currentData() is None:
            QMessageBox.warning(self, "Нет изделий", "Сначала добавь изделие в каталоге.")
            return
        if self.quantity.value() <= 0:
            QMessageBox.warning(self, "Количество", "Количество должно быть больше нуля.")
            return
        self.accept()

    def data(self):
        return {"product_id": int(self.product.currentData()), "quantity": self.quantity.value(), "production_date": self.date.date().toString("yyyy-MM-dd"), "notes": self.notes.toPlainText().strip()}

class StockMovementDialog(QDialog):
    TYPES = [("Продажа / передача клиенту", "sale"), ("Возврат на склад", "return"),
             ("Списание брака / потери", "writeoff"), ("Резерв под заказ", "reserve"),
             ("Снять резерв", "release")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Движение готовой продукции")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.product = QComboBox()
        self.kind = QComboBox()
        for label, value in self.TYPES:
            self.kind.addItem(label, value)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.001, 1000000)
        self.quantity.setDecimals(3)
        self.quantity.setValue(1)
        self.quantity.setSuffix(" шт.")
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        self.date.setDate(QDate.currentDate())
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Номер заказа или причина операции")
        with get_connection() as connection:
            products = connection.execute("SELECT id, article, name FROM products ORDER BY name COLLATE NOCASE").fetchall()
        for product in products:
            self.product.addItem(f"{product['article']} | {product['name']}", int(product["id"]))
        form.addRow("Изделие:", self.product)
        form.addRow("Операция:", self.kind)
        form.addRow("Количество:", self.quantity)
        form.addRow("Дата:", self.date)
        form.addRow("Комментарий:", self.notes)
        layout.addLayout(form)
        hint = QLabel("Продажа и списание уменьшают остаток, возврат увеличивает. Резерв уменьшает доступное количество, но не физический остаток.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if not products:
            self.product.setEnabled(False)

    def data(self):
        return {"product_id": self.product.currentData(), "movement_type": self.kind.currentData(),
                "quantity": self.quantity.value(), "movement_date": self.date.date().toString("yyyy-MM-dd"),
                "notes": self.notes.text().strip()}


class ProductionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_production_tables()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)
        title = QLabel("Производство и склад готовой продукции")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Учитывай производство, продажи, возвраты, списания и резервы. Продажи Ozon списываются автоматически только при совпадении артикула с изделием каталога.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по артикулу или названию изделия...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.load_data)
        toolbar.addWidget(self.search, 1)
        add = QPushButton("+ Записать готовую партию")
        add.setObjectName("accentButton")
        add.clicked.connect(self.add_batch)
        toolbar.addWidget(add)
        movement = QPushButton("+ Движение / списание")
        movement.clicked.connect(self.add_movement)
        toolbar.addWidget(movement)
        layout.addLayout(toolbar)
        stock_title = QLabel("Остатки готовых изделий")
        stock_title.setObjectName("sectionTitle")
        layout.addWidget(stock_title)
        self.stock_table = QTableWidget(0, 8)
        self.stock_table.setHorizontalHeaderLabels(["Артикул", "Изделие", "Произведено", "Продано", "Возвраты", "Списано", "В резерве", "Доступно"])
        self.prepare_table(self.stock_table)
        layout.addWidget(self.stock_table, 1)
        history_title = QLabel("История производственных партий")
        history_title.setObjectName("sectionTitle")
        layout.addWidget(history_title)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["Дата", "Артикул", "Изделие", "Количество", "Комментарий"])
        self.prepare_table(self.history_table)
        layout.addWidget(self.history_table, 1)
        movement_title = QLabel("История движений склада")
        movement_title.setObjectName("sectionTitle")
        layout.addWidget(movement_title)
        self.movement_table = QTableWidget(0, 5)
        self.movement_table.setHorizontalHeaderLabels(["Дата", "Операция", "Артикул / изделие", "Количество", "Комментарий"])
        self.prepare_table(self.movement_table)
        layout.addWidget(self.movement_table, 1)
        bottom = QHBoxLayout()
        self.count_label = QLabel("Партий: 0")
        self.count_label.setObjectName("subtitle")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        remove = QPushButton("Удалить запись партии")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self.delete_batch)
        bottom.addWidget(remove)
        refresh = QPushButton("Обновить")
        refresh.clicked.connect(self.load_data)
        bottom.addWidget(refresh)
        layout.addLayout(bottom)

    @staticmethod
    def prepare_table(table):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def load_data(self, *_):
        pattern = f"%{self.search.text().strip()}%" if hasattr(self, "search") else "%"
        with get_connection() as connection:
            stock = connection.execute("""SELECT p.id, p.article, p.name,
                COALESCE((SELECT SUM(b.quantity) FROM production_batches b WHERE b.product_id=p.id),0) produced,
                COALESCE(SUM(CASE WHEN m.movement_type='sale' THEN m.quantity ELSE 0 END),0) sold,
                COALESCE(SUM(CASE WHEN m.movement_type='return' THEN m.quantity ELSE 0 END),0) returned,
                COALESCE(SUM(CASE WHEN m.movement_type='writeoff' THEN m.quantity ELSE 0 END),0) written_off,
                COALESCE(SUM(CASE WHEN m.movement_type='reserve' THEN m.quantity ELSE 0 END),0) -
                COALESCE(SUM(CASE WHEN m.movement_type='release' THEN m.quantity ELSE 0 END),0) reserved
                FROM products p LEFT JOIN stock_movements m ON m.product_id=p.id
                WHERE p.article LIKE ? OR p.name LIKE ? GROUP BY p.id ORDER BY p.name COLLATE NOCASE""", (pattern, pattern)).fetchall()
            batches = connection.execute("""SELECT b.id, b.production_date, p.article, p.name, b.quantity, b.notes FROM production_batches b JOIN products p ON p.id = b.product_id WHERE p.article LIKE ? OR p.name LIKE ? ORDER BY b.production_date DESC, b.id DESC""", (pattern, pattern)).fetchall()
            movements = connection.execute("""SELECT m.id, m.movement_date, m.movement_type, m.quantity, m.notes, p.article, p.name
                FROM stock_movements m JOIN products p ON p.id=m.product_id
                WHERE p.article LIKE ? OR p.name LIKE ? ORDER BY m.movement_date DESC, m.id DESC LIMIT 500""",
                (pattern, pattern)).fetchall()
        self.stock_table.setRowCount(len(stock))
        for row, item in enumerate(stock):
            produced, sold = float(item["produced"] or 0), float(item["sold"] or 0)
            returned, written_off = float(item["returned"] or 0), float(item["written_off"] or 0)
            reserved = max(0.0, float(item["reserved"] or 0))
            values = [item["article"], item["name"], self.format_qty(produced), self.format_qty(sold),
                      self.format_qty(returned), self.format_qty(written_off), self.format_qty(reserved),
                      self.format_qty(produced - sold + returned - written_off - reserved)]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, int(item["id"]))
                self.stock_table.setItem(row, col, cell)
        self.history_table.setRowCount(len(batches))
        for row, batch in enumerate(batches):
            values = [self.display_date(batch["production_date"]), batch["article"], batch["name"], self.format_qty(batch["quantity"]), batch["notes"] or ""]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, int(batch["id"]))
                self.history_table.setItem(row, col, cell)
        self.movement_table.setRowCount(len(movements))
        type_labels = {"sale": "Продажа", "return": "Возврат", "writeoff": "Списание",
                       "reserve": "Резерв", "release": "Снятие резерва"}
        for row, movement in enumerate(movements):
            values = [self.display_date(movement["movement_date"]),
                      type_labels.get(movement["movement_type"], movement["movement_type"]),
                      f"{movement['article']} | {movement['name']}",
                      self.format_qty(movement["quantity"]), movement["notes"] or ""]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, int(movement["id"]))
                self.movement_table.setItem(row, col, cell)
        self.count_label.setText(f"Партий: {len(batches)} | Движений: {len(movements)} | Изделий в каталоге: {len(stock)}")

    def add_batch(self):
        dialog = ProductionBatchDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        try:
            with get_connection() as connection:
                connection.execute("INSERT INTO production_batches (product_id, quantity, production_date, notes) VALUES (?, ?, ?, ?)", (data["product_id"], data["quantity"], data["production_date"], data["notes"]))
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось сохранить партию:\n{error}")
            return
        self.load_data()

    def add_movement(self):
        dialog = StockMovementDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        if data["product_id"] is None:
            QMessageBox.warning(self, "Нет изделий", "Сначала добавь изделие в каталоге.")
            return
        try:
            with get_connection() as connection:
                connection.execute("""INSERT INTO stock_movements
                    (product_id, movement_type, quantity, movement_date, source_type, notes)
                    VALUES (?, ?, ?, ?, 'manual', ?)""",
                    (data["product_id"], data["movement_type"], data["quantity"],
                     data["movement_date"], data["notes"]))
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Ошибка базы данных", f"Не удалось сохранить движение:\\n{error}")
            return
        self.load_data()

    def delete_batch(self):
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Запись не выбрана", "Выбери партию в истории.")
            return
        batch_id = self.history_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(self, "Удалить партию", "Удалить выбранную запись? Учтённый остаток уменьшится на её количество.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        with get_connection() as connection:
            connection.execute("DELETE FROM production_batches WHERE id = ?", (batch_id,))
        self.load_data()

    @staticmethod
    def format_qty(value):
        number = float(value or 0)
        return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def display_date(value):
        parsed = QDate.fromString(str(value or ""), "yyyy-MM-dd")
        return parsed.toString("dd.MM.yyyy") if parsed.isValid() else str(value or "")
