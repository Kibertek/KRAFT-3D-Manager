import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDoubleSpinBox, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QTabWidget, QTextEdit, QGroupBox, QFrame
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


def initialize_packaging_tables():
    """Добавляет структуру упаковки, используя components как общий склад."""
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
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(components)")}
        for name, definition in {
            "supplier": "TEXT DEFAULT ''",
            "quantity": "REAL DEFAULT 0",
            "min_quantity": "REAL DEFAULT 0",
            "notes": "TEXT DEFAULT ''",
            "size_category": "TEXT DEFAULT 'Средняя'",
        }.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE components ADD COLUMN {name} {definition}")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS packaging_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                label_type TEXT NOT NULL DEFAULT 'Наклейка',
                price REAL NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS packaging_kits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS packaging_kit_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kit_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                FOREIGN KEY(kit_id) REFERENCES packaging_kits(id) ON DELETE CASCADE
            )
        """)


class PackagingItemDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.item = dict(item) if item is not None else None
        self.setWindowTitle("Редактировать упаковку" if item else "Добавить упаковку")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Например, зип-пакет 10×15 см")
        self.size = QComboBox()
        self.size.addItems(["Малая", "Средняя", "Большая"])
        self.unit = QComboBox()
        self.unit.setEditable(True)
        self.unit.addItems(["шт.", "м", "см", "рулон", "упак."])
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 100000000)
        self.price.setDecimals(2)
        self.price.setSuffix(" ₽")
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 100000000)
        self.quantity.setDecimals(3)
        self.min_quantity = QDoubleSpinBox()
        self.min_quantity.setRange(0, 100000000)
        self.min_quantity.setDecimals(3)
        self.supplier = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(75)
        form.addRow("Название *", self.name)
        form.addRow("Физический размер", self.size)
        form.addRow("Единица измерения", self.unit)
        form.addRow("Цена за единицу", self.price)
        form.addRow("Начальный остаток", self.quantity)
        form.addRow("Минимальный остаток", self.min_quantity)
        form.addRow("Поставщик", self.supplier)
        form.addRow("Примечание", self.notes)
        layout.addLayout(form)
        note = QLabel("Для полноценной закупки с датой и историей используй раздел «Закупки».")
        note.setWordWrap(True)
        note.setStyleSheet("color: #ffad5c;")
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self.item:
            self.name.setText(self.item["name"] or "")
            self.size.setCurrentText(self.item["size_category"] or "Средняя")
            self.unit.setCurrentText(self.item["unit"] or "шт.")
            self.price.setValue(float(self.item["price"] or 0))
            self.quantity.setValue(float(self.item["quantity"] or 0))
            self.quantity.setEnabled(False)
            self.quantity.setToolTip("Остаток изменяется через раздел «Закупки», чтобы история склада оставалась согласованной.")
            self.min_quantity.setValue(float(self.item["min_quantity"] or 0))
            self.supplier.setText(self.item["supplier"] or "")
            self.notes.setPlainText(self.item["notes"] or "")
        else:
            self.size.setCurrentText("Средняя")

    def validate(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Не хватает названия", "Укажи название упаковочного материала.")
            return
        self.accept()

    def data(self):
        return {
            "name": self.name.text().strip(),
            "size_category": self.size.currentText(),
            "unit": self.unit.currentText().strip() or "шт.",
            "price": self.price.value(),
            "quantity": self.quantity.value(),
            "min_quantity": self.min_quantity.value(),
            "supplier": self.supplier.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class LabelDialog(QDialog):
    def __init__(self, parent=None, label=None):
        super().__init__(parent)
        self.label = dict(label) if label is not None else None
        self.setWindowTitle("Редактировать наклейку или этикетку" if label else "Добавить наклейку или этикетку")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.kind = QComboBox()
        self.kind.addItems(["Наклейка", "Этикетка"])
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 100000000)
        self.price.setDecimals(2)
        self.price.setSuffix(" ₽ за единицу")
        self.notes = QLineEdit()
        form.addRow("Название *", self.name)
        form.addRow("Тип", self.kind)
        form.addRow("Цена за единицу", self.price)
        form.addRow("Примечание", self.notes)
        layout.addLayout(form)
        info = QLabel("Справочник не ведёт остатки, закупки или списание. Цена используется в составе набора упаковки.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #ffad5c;")
        layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self.label:
            self.name.setText(self.label["name"])
            self.kind.setCurrentText(self.label["label_type"])
            self.price.setValue(float(self.label["price"] or 0))
            self.notes.setText(self.label["notes"] or "")

    def validate(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Не хватает названия", "Укажи название.")
            return
        self.accept()

    def data(self):
        return {"name": self.name.text().strip(), "label_type": self.kind.currentText(),
                "price": self.price.value(), "notes": self.notes.text().strip()}


class KitDialog(QDialog):
    def __init__(self, parent=None, kit=None):
        super().__init__(parent)
        self.kit = dict(kit) if kit is not None else None
        self.setWindowTitle("Редактировать набор упаковки" if kit else "Создать набор упаковки")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Например, Ozon FBS")
        self.description = QLineEdit()
        form.addRow("Название набора *", self.name)
        form.addRow("Описание", self.description)
        layout.addLayout(form)
        group = QGroupBox("Состав набора")
        group_layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.item_type = QComboBox()
        self.item_type.addItem("Складская упаковка", "component")
        self.item_type.addItem("Наклейка / этикетка", "label")
        self.item = QComboBox()
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.001, 1000000)
        self.quantity.setDecimals(3)
        self.quantity.setValue(1)
        self.add_item_button = QPushButton("Добавить в состав")
        row.addWidget(self.item_type)
        row.addWidget(self.item, 1)
        row.addWidget(self.quantity)
        group_layout.addLayout(row)
        group_layout.addWidget(self.add_item_button)
        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["Тип", "Позиция", "Кол-во", "Цена"])
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (0, 2, 3):
            self.items_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        group_layout.addWidget(self.items_table)
        remove = QPushButton("Убрать выбранную позицию")
        remove.clicked.connect(self.remove_item)
        group_layout.addWidget(remove)
        layout.addWidget(group)
        self._items = []
        self._catalog = {"component": [], "label": []}
        self.item_type.currentIndexChanged.connect(self.reload_choices)
        self.add_item_button.clicked.connect(self.add_item)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.load_catalog()
        if self.kit:
            self.name.setText(self.kit["name"])
            self.description.setText(self.kit["description"] or "")
            with get_connection() as con:
                existing = con.execute("SELECT * FROM packaging_kit_items WHERE kit_id = ? ORDER BY id", (self.kit["id"],)).fetchall()
            for item in existing:
                self._items.append({"item_type": item["item_type"], "item_id": item["item_id"], "quantity": float(item["quantity"])})
            self.render_items()

    def load_catalog(self):
        with get_connection() as con:
            self._catalog["component"] = [dict(r) for r in con.execute("""
                SELECT id, name, unit, price FROM components
                WHERE COALESCE(category, '') = 'Упаковка' ORDER BY name
            """).fetchall()]
            self._catalog["label"] = [dict(r) for r in con.execute(
                "SELECT id, name, 'шт.' AS unit, price FROM packaging_labels ORDER BY name"
            ).fetchall()]
        self.reload_choices()

    def reload_choices(self, *_):
        kind = self.item_type.currentData()
        self.item.clear()
        for entry in self._catalog.get(kind, []):
            self.item.addItem(f"{entry['name']} · {money(entry['price'])}/{entry['unit']}", entry["id"])

    def add_item(self):
        item_id = self.item.currentData()
        if item_id is None:
            QMessageBox.information(self, "Нет позиций", "Сначала добавь упаковку или наклейку в соответствующем справочнике.")
            return
        kind = self.item_type.currentData()
        self._items.append({"item_type": kind, "item_id": int(item_id), "quantity": self.quantity.value()})
        self.render_items()

    def render_items(self):
        self.items_table.setRowCount(len(self._items))
        catalog_map = {kind: {x["id"]: x for x in rows} for kind, rows in self._catalog.items()}
        for index, entry in enumerate(self._items):
            found = catalog_map.get(entry["item_type"], {}).get(entry["item_id"], {})
            vals = ["Складская упаковка" if entry["item_type"] == "component" else "Наклейка / этикетка",
                    found.get("name", "Позиция удалена"), number(entry["quantity"]), money(float(found.get("price") or 0) * entry["quantity"])]
            for col, value in enumerate(vals):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, index)
                self.items_table.setItem(index, col, cell)

    def remove_item(self):
        row = self.items_table.currentRow()
        if row < 0:
            return
        self._items.pop(row)
        self.render_items()

    def validate(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Не хватает названия", "Укажи название набора.")
            return
        if not self._items:
            QMessageBox.warning(self, "Пустой набор", "Добавь хотя бы одну позицию в состав набора.")
            return
        self.accept()

    def data(self):
        return {"name": self.name.text().strip(), "description": self.description.text().strip(), "items": list(self._items)}


class PackagingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_packaging_tables()
        self.setup_ui()
        self.load_stock()
        self.load_labels()
        self.load_kits()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        title = QLabel("Упаковка")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("Складская упаковка, справочник наклеек и этикеток, пользовательские наборы")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        stock_tab = QWidget()
        stock_layout = QVBoxLayout(stock_tab)
        toolbar = QHBoxLayout()
        self.stock_search = QLineEdit()
        self.stock_search.setPlaceholderText("Поиск упаковки...")
        self.stock_search.textChanged.connect(self.load_stock)
        toolbar.addWidget(self.stock_search, 1)
        add = QPushButton("+ Добавить упаковку")
        add.setObjectName("accentButton")
        add.clicked.connect(self.add_stock)
        toolbar.addWidget(add)
        stock_layout.addLayout(toolbar)
        self.stock_table = QTableWidget(0, 7)
        self.stock_table.setHorizontalHeaderLabels(["Название", "Размер", "Ед.", "Цена", "Остаток", "Мин. остаток", "Поставщик"])
        self.configure_table(self.stock_table)
        self.stock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            self.stock_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.stock_table.doubleClicked.connect(self.edit_stock)
        stock_layout.addWidget(self.stock_table, 1)
        stock_buttons = QHBoxLayout()
        stock_buttons.addWidget(QLabel("Закупки добавляй через раздел «Закупки», чтобы сохранялась история."))
        stock_buttons.addStretch()
        edit = QPushButton("Редактировать")
        edit.clicked.connect(self.edit_stock)
        stock_buttons.addWidget(edit)
        delete = QPushButton("Удалить")
        delete.setObjectName("dangerButton")
        delete.clicked.connect(self.delete_stock)
        stock_buttons.addWidget(delete)
        stock_layout.addLayout(stock_buttons)
        self.tabs.addTab(stock_tab, "Складская упаковка")

        labels_tab = QWidget()
        labels_layout = QVBoxLayout(labels_tab)
        label_toolbar = QHBoxLayout()
        label_toolbar.addWidget(QLabel("Без остатков и складских закупок. Цена указывается за одну штуку."))
        label_toolbar.addStretch()
        label_add = QPushButton("+ Добавить наклейку / этикетку")
        label_add.setObjectName("accentButton")
        label_add.clicked.connect(self.add_label)
        label_toolbar.addWidget(label_add)
        labels_layout.addLayout(label_toolbar)
        self.labels_table = QTableWidget(0, 4)
        self.labels_table.setHorizontalHeaderLabels(["Название", "Тип", "Цена за единицу", "Примечание"])
        self.configure_table(self.labels_table)
        self.labels_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.labels_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2):
            self.labels_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.labels_table.doubleClicked.connect(self.edit_label)
        labels_layout.addWidget(self.labels_table, 1)
        label_buttons = QHBoxLayout()
        label_edit = QPushButton("Редактировать")
        label_edit.clicked.connect(self.edit_label)
        label_buttons.addWidget(label_edit)
        label_delete = QPushButton("Удалить")
        label_delete.setObjectName("dangerButton")
        label_delete.clicked.connect(self.delete_label)
        label_buttons.addWidget(label_delete)
        label_buttons.addStretch()
        labels_layout.addLayout(label_buttons)
        self.tabs.addTab(labels_tab, "Наклейки и этикетки")

        kits_tab = QWidget()
        kits_layout = QVBoxLayout(kits_tab)
        kit_toolbar = QHBoxLayout()
        kit_toolbar.addWidget(QLabel("Состав набора и его стоимость рассчитываются из выбранных позиций."))
        kit_toolbar.addStretch()
        kit_add = QPushButton("+ Создать набор")
        kit_add.setObjectName("accentButton")
        kit_add.clicked.connect(self.add_kit)
        kit_toolbar.addWidget(kit_add)
        kits_layout.addLayout(kit_toolbar)
        self.kits_table = QTableWidget(0, 4)
        self.kits_table.setHorizontalHeaderLabels(["Название набора", "Описание", "Позиций", "Стоимость набора"])
        self.configure_table(self.kits_table)
        self.kits_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.kits_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3):
            self.kits_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.kits_table.doubleClicked.connect(self.edit_kit)
        kits_layout.addWidget(self.kits_table, 1)
        kit_buttons = QHBoxLayout()
        kit_edit = QPushButton("Редактировать состав")
        kit_edit.clicked.connect(self.edit_kit)
        kit_buttons.addWidget(kit_edit)
        kit_delete = QPushButton("Удалить набор")
        kit_delete.setObjectName("dangerButton")
        kit_delete.clicked.connect(self.delete_kit)
        kit_buttons.addWidget(kit_delete)
        kit_buttons.addStretch()
        kits_layout.addLayout(kit_buttons)
        self.tabs.addTab(kits_tab, "Типы упаковки / наборы")

    def configure_table(self, table):
        # Убираем системную светлую рамку Qt и задаём тёмное оформление явно.
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setLineWidth(0)
        table.setStyleSheet("""
            QTableWidget {
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
            QTableWidget::item {
                color: #eeeeee;
                padding: 5px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #75421e;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #303030;
                color: #ffffff;
                padding: 9px 6px;
                border: none;
                border-bottom: 1px solid #484848;
                font-weight: 600;
            }
            QTableCornerButton::section {
                background-color: #303030;
                border: none;
            }
        """)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

    def selected_id(self, table):
        row = table.currentRow()
        if row < 0 or table.item(row, 0) is None:
            return None
        return table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def load_stock(self, *_):
        search = self.stock_search.text().strip()
        with get_connection() as con:
            rows = con.execute("""
                SELECT id, name, COALESCE(size_category, 'Средняя') AS size_category,
                       COALESCE(unit, 'шт.') AS unit, COALESCE(price, 0) AS price,
                       COALESCE(quantity, 0) AS quantity, COALESCE(min_quantity, 0) AS min_quantity,
                       COALESCE(supplier, '') AS supplier
                FROM components
                WHERE COALESCE(category, '') = 'Упаковка'
                  AND name LIKE ?
                ORDER BY name COLLATE NOCASE
            """, (f"%{search}%",)).fetchall()
        self.stock_table.setRowCount(len(rows))
        for r, entry in enumerate(rows):
            values = [entry["name"], entry["size_category"], entry["unit"], money(entry["price"]),
                      number(entry["quantity"]), number(entry["min_quantity"]), entry["supplier"]]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, entry["id"])
                self.stock_table.setItem(r, col, cell)
            if float(entry["quantity"] or 0) <= float(entry["min_quantity"] or 0):
                for col in range(len(values)):
                    self.stock_table.item(r, col).setForeground(Qt.GlobalColor.yellow)

    def stock_record(self, item_id):
        with get_connection() as con:
            return con.execute("SELECT * FROM components WHERE id = ?", (item_id,)).fetchone()

    def add_stock(self):
        dialog = PackagingItemDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        with get_connection() as con:
            con.execute("""
                INSERT INTO components (name, category, unit, price, supplier, quantity, min_quantity, notes, size_category)
                VALUES (?, 'Упаковка', ?, ?, ?, ?, ?, ?, ?)
            """, (data["name"], data["unit"], data["price"], data["supplier"], data["quantity"],
                  data["min_quantity"], data["notes"], data["size_category"]))
        self.load_stock()

    def edit_stock(self, *_):
        item_id = self.selected_id(self.stock_table)
        if item_id is None:
            return
        item = self.stock_record(item_id)
        if item is None:
            return
        dialog = PackagingItemDialog(self, item)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        with get_connection() as con:
            con.execute("""
                UPDATE components SET name=?, unit=?, price=?, supplier=?,
                    min_quantity=?, notes=?, size_category=? WHERE id=? AND category='Упаковка'
            """, (data["name"], data["unit"], data["price"], data["supplier"],
                  data["min_quantity"], data["notes"], data["size_category"], item_id))
        self.load_stock()

    def delete_stock(self):
        item_id = self.selected_id(self.stock_table)
        if item_id is None:
            return
        with get_connection() as con:
            purchases = con.execute("SELECT COUNT(*) FROM purchases WHERE item_type='component' AND item_id=?", (item_id,)).fetchone()[0]
            kit_use = con.execute("SELECT COUNT(*) FROM packaging_kit_items WHERE item_type='component' AND item_id=?", (item_id,)).fetchone()[0]
        if purchases or kit_use:
            QMessageBox.warning(self, "Нельзя удалить позицию", "У этой упаковки есть история закупок или она используется в наборе. Сначала убери связи, чтобы сохранить историю.")
            return
        answer = QMessageBox.question(self, "Удаление упаковки", "Удалить выбранную складскую позицию?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        with get_connection() as con:
            con.execute("DELETE FROM components WHERE id=? AND category='Упаковка'", (item_id,))
        self.load_stock()

    def load_labels(self):
        with get_connection() as con:
            rows = con.execute("SELECT * FROM packaging_labels ORDER BY name COLLATE NOCASE").fetchall()
        self.labels_table.setRowCount(len(rows))
        for r, entry in enumerate(rows):
            for col, value in enumerate([entry["name"], entry["label_type"], money(entry["price"]), entry["notes"] or ""]):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, entry["id"])
                self.labels_table.setItem(r, col, cell)

    def label_record(self, label_id):
        with get_connection() as con:
            return con.execute("SELECT * FROM packaging_labels WHERE id=?", (label_id,)).fetchone()

    def add_label(self):
        dialog = LabelDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        d = dialog.data()
        with get_connection() as con:
            con.execute("INSERT INTO packaging_labels (name,label_type,price,notes) VALUES (?,?,?,?)",
                        (d["name"], d["label_type"], d["price"], d["notes"]))
        self.load_labels()
        self.load_kits()

    def edit_label(self, *_):
        label_id = self.selected_id(self.labels_table)
        if label_id is None:
            return
        label = self.label_record(label_id)
        if label is None:
            return
        dialog = LabelDialog(self, label)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        d = dialog.data()
        with get_connection() as con:
            con.execute("UPDATE packaging_labels SET name=?,label_type=?,price=?,notes=? WHERE id=?",
                        (d["name"], d["label_type"], d["price"], d["notes"], label_id))
        self.load_labels()
        self.load_kits()

    def delete_label(self):
        label_id = self.selected_id(self.labels_table)
        if label_id is None:
            return
        with get_connection() as con:
            used = con.execute("SELECT COUNT(*) FROM packaging_kit_items WHERE item_type='label' AND item_id=?", (label_id,)).fetchone()[0]
        if used:
            QMessageBox.warning(self, "Нельзя удалить", "Эта наклейка или этикетка используется в составе набора.")
            return
        answer = QMessageBox.question(self, "Удаление", "Удалить запись из справочника?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        with get_connection() as con:
            con.execute("DELETE FROM packaging_labels WHERE id=?", (label_id,))
        self.load_labels()

    def kit_record(self, kit_id):
        with get_connection() as con:
            return con.execute("SELECT * FROM packaging_kits WHERE id=?", (kit_id,)).fetchone()

    def add_kit(self):
        dialog = KitDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.save_kit(dialog.data())
        self.load_kits()

    def edit_kit(self, *_):
        kit_id = self.selected_id(self.kits_table)
        if kit_id is None:
            return
        kit = self.kit_record(kit_id)
        if kit is None:
            return
        dialog = KitDialog(self, kit)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.save_kit(dialog.data(), kit_id)
        self.load_kits()

    def save_kit(self, data, kit_id=None):
        with get_connection() as con:
            if kit_id is None:
                cur = con.execute("INSERT INTO packaging_kits (name,description) VALUES (?,?)", (data["name"], data["description"]))
                kit_id = cur.lastrowid
            else:
                con.execute("UPDATE packaging_kits SET name=?,description=? WHERE id=?", (data["name"], data["description"], kit_id))
                con.execute("DELETE FROM packaging_kit_items WHERE kit_id=?", (kit_id,))
            con.executemany("INSERT INTO packaging_kit_items (kit_id,item_type,item_id,quantity) VALUES (?,?,?,?)",
                            [(kit_id, x["item_type"], x["item_id"], x["quantity"]) for x in data["items"]])

    def load_kits(self):
        with get_connection() as con:
            kits = con.execute("SELECT * FROM packaging_kits ORDER BY name COLLATE NOCASE").fetchall()
            components = {r["id"]: dict(r) for r in con.execute("SELECT id,name,price,unit FROM components").fetchall()}
            labels = {r["id"]: dict(r) for r in con.execute("SELECT id,name,price FROM packaging_labels").fetchall()}
            self.kits_table.setRowCount(len(kits))
            for r, kit in enumerate(kits):
                items = con.execute("SELECT * FROM packaging_kit_items WHERE kit_id=?", (kit["id"],)).fetchall()
                total = 0.0
                for item in items:
                    source = components if item["item_type"] == "component" else labels
                    entry = source.get(item["item_id"])
                    if entry:
                        total += float(entry.get("price") or 0) * float(item["quantity"] or 0)
                values = [kit["name"], kit["description"] or "", str(len(items)), money(total)]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setData(Qt.ItemDataRole.UserRole, kit["id"])
                    self.kits_table.setItem(r, col, cell)

    def delete_kit(self):
        kit_id = self.selected_id(self.kits_table)
        if kit_id is None:
            return
        answer = QMessageBox.question(self, "Удаление набора", "Удалить выбранный набор упаковки?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        with get_connection() as con:
            con.execute("DELETE FROM packaging_kit_items WHERE kit_id=?", (kit_id,))
            con.execute("DELETE FROM packaging_kits WHERE id=?", (kit_id,))
        self.load_kits()
