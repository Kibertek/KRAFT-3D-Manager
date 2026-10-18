
import sys
import re
import shutil
import sqlite3
from pathlib import Path

from calculator_module import CalculatorPage
from components_module import ComponentsPage
from materials_module import MaterialsPage
from purchases_module import PurchasesPage
from packaging_module import PackagingPage

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QFileDialog
)


# ============================================================
# ПАПКИ И БАЗА ДАННЫХ
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS_DIR = BASE_DIR / "products"
REPORTS_DIR = BASE_DIR / "reports"
BACKUPS_DIR = BASE_DIR / "backups"
DATABASE_FILE = DATA_DIR / "kraft3d.db"


def create_directories():
    for folder in (DATA_DIR, PRODUCTS_DIR, REPORTS_DIR, BACKUPS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'Без категории',
                status TEXT DEFAULT 'Активно',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                folder_path TEXT
            )
        """)

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(products)"
            ).fetchall()
        }

        if "folder_path" not in columns:
            connection.execute(
                "ALTER TABLE products ADD COLUMN folder_path TEXT"
            )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS product_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        """)

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
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                unit TEXT DEFAULT 'шт.',
                price REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                power REAL DEFAULT 0,
                purchase_price REAL DEFAULT 0,
                resource_hours REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ============================================================
# ПАПКА КОНКРЕТНОГО ИЗДЕЛИЯ
# ============================================================

def safe_folder_name(value):
    value = re.sub(r'[<>:"/\\|?*]', "_", value).strip(" .")
    return value or "product"


def ensure_product_folder(product_id):
    with get_connection() as connection:
        product = connection.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if product is None:
            raise ValueError("Изделие не найдено в базе данных.")

        saved_path = product["folder_path"]

        if saved_path:
            folder = BASE_DIR / saved_path
        else:
            folder = PRODUCTS_DIR / safe_folder_name(product["article"])

            if folder.exists():
                folder = PRODUCTS_DIR / (
                    f"{safe_folder_name(product['article'])}_{product_id}"
                )

            relative_path = folder.relative_to(BASE_DIR).as_posix()

            connection.execute(
                "UPDATE products SET folder_path = ? WHERE id = ?",
                (relative_path, product_id)
            )

    folder.mkdir(parents=True, exist_ok=True)

    for name in (
        "photos", "source", "slicer",
        "gcode", "documents", "other"
    ):
        (folder / name).mkdir(exist_ok=True)

    return folder


def get_file_category(file_path):
    extension = Path(file_path).suffix.lower()

    if extension in {
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"
    }:
        return "Фото", "photos"

    if extension in {".gcode", ".gco"}:
        return "G-code", "gcode"

    if extension in {".3mf", ".f3d", ".f3z", ".orca", ".idea"}:
        return "Проект слайсера", "slicer"

    if extension in {".stl", ".obj", ".step", ".stp", ".amf", ".ply"}:
        return "3D-модель", "source"

    if extension in {".pdf", ".txt", ".doc", ".docx", ".xlsx", ".csv"}:
        return "Документ", "documents"

    return "Другой файл", "other"


def unique_destination(folder, filename):
    destination = folder / filename

    if not destination.exists():
        return destination

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    number = 2

    while True:
        destination = folder / f"{stem}_{number}{suffix}"

        if not destination.exists():
            return destination

        number += 1


# ============================================================
# ФОРМА ИЗДЕЛИЯ
# ============================================================

class ProductDialog(QDialog):

    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product

        self.setWindowTitle(
            "Редактирование изделия" if product else "Новое изделие"
        )
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.article_input = QLineEdit()
        self.article_input.setPlaceholderText("Например, K3D-001")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название изделия")

        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems([
            "Брелоки и сувениры",
            "Предметы для дома",
            "Органайзеры",
            "Подарки",
            "Детали и комплектующие",
            "Прочее",
        ])

        self.status_input = QComboBox()
        self.status_input.addItems([
            "Активно",
            "Черновик",
            "Снято с производства",
        ])

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Описание и примечания"
        )
        self.description_input.setMaximumHeight(120)

        form.addRow("Артикул *", self.article_input)
        form.addRow("Название *", self.name_input)
        form.addRow("Категория", self.category_input)
        form.addRow("Статус", self.status_input)
        form.addRow("Описание", self.description_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if product:
            self.article_input.setText(product["article"])
            self.name_input.setText(product["name"])
            self.category_input.setCurrentText(
                product["category"] or "Без категории"
            )
            self.status_input.setCurrentText(
                product["status"] or "Активно"
            )
            self.description_input.setPlainText(
                product["description"] or ""
            )
        else:
            self.category_input.setCurrentText("Брелоки и сувениры")

    def validate_and_accept(self):
        if not self.article_input.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажи артикул.")
            self.article_input.setFocus()
            return

        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажи название.")
            self.name_input.setFocus()
            return

        self.accept()

    def get_data(self):
        return {
            "article": self.article_input.text().strip(),
            "name": self.name_input.text().strip(),
            "category": (
                self.category_input.currentText().strip()
                or "Без категории"
            ),
            "status": self.status_input.currentText(),
            "description": self.description_input.toPlainText().strip(),
        }


# ============================================================
# ОКНО ФАЙЛОВ И ФОТОГРАФИЙ
# ============================================================

class ProductFilesDialog(QDialog):

    def __init__(self, parent, product_id):
        super().__init__(parent)
        self.product_id = product_id
        self.folder = ensure_product_folder(product_id)

        with get_connection() as connection:
            self.product = connection.execute(
                "SELECT * FROM products WHERE id = ?",
                (product_id,)
            ).fetchone()

        if self.product is None:
            raise ValueError("Изделие не найдено в базе данных.")

        self.setWindowTitle(
            f"Файлы изделия: {self.product['article']}"
        )
        self.resize(850, 500)

        layout = QVBoxLayout(self)

        heading = QLabel(
            f"{self.product['name']}  |  {self.product['article']}"
        )
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        folder_label = QLabel(f"Папка: {self.folder}")
        folder_label.setWordWrap(True)
        folder_label.setObjectName("subtitle")
        layout.addWidget(folder_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "Тип", "Имя файла", "Путь", "Добавлен"
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
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )

        self.table.doubleClicked.connect(self.open_selected_file)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()

        add_button = QPushButton("+ Добавить файлы")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_files)
        buttons.addWidget(add_button)

        open_button = QPushButton("Открыть файл")
        open_button.clicked.connect(self.open_selected_file)
        buttons.addWidget(open_button)

        folder_button = QPushButton("Открыть папку")
        folder_button.clicked.connect(self.open_folder)
        buttons.addWidget(folder_button)

        remove_button = QPushButton("Удалить файл")
        remove_button.setObjectName("dangerButton")
        remove_button.clicked.connect(self.remove_file)
        buttons.addWidget(remove_button)

        layout.addLayout(buttons)

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.load_files()

    def load_files(self):
        with get_connection() as connection:
            files = connection.execute("""
                SELECT * FROM product_files
                WHERE product_id = ?
                ORDER BY id DESC
            """, (self.product_id,)).fetchall()

        self.table.setRowCount(len(files))

        for row_index, file in enumerate(files):
            values = [
                file["file_type"],
                file["file_name"],
                file["file_path"],
                file["added_at"] or "",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, file["id"])
                self.table.setItem(row_index, column, item)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Выбери фотографии или файлы изделия",
            str(Path.home()),
            "Все файлы (*.*)"
        )

        if not paths:
            return

        errors = []
        added_count = 0

        for source_name in paths:
            source = Path(source_name)

            try:
                file_type, subfolder = get_file_category(source)
                target_folder = self.folder / subfolder
                target_folder.mkdir(parents=True, exist_ok=True)

                destination = unique_destination(
                    target_folder, source.name
                )

                shutil.copy2(source, destination)

                relative_path = destination.relative_to(
                    BASE_DIR
                ).as_posix()

                with get_connection() as connection:
                    connection.execute("""
                        INSERT INTO product_files (
                            product_id, file_type, file_name, file_path
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        self.product_id,
                        file_type,
                        destination.name,
                        relative_path,
                    ))

                added_count += 1

            except Exception as error:
                errors.append(f"{source.name}: {error}")

        self.load_files()

        if errors:
            QMessageBox.warning(
                self,
                "Некоторые файлы не добавлены",
                "\n".join(errors[:10])
            )
        elif added_count:
            QMessageBox.information(
                self,
                "Файлы добавлены",
                f"Добавлено файлов: {added_count}"
            )

    def selected_file(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if item is None:
            return None

        file_id = item.data(Qt.ItemDataRole.UserRole)

        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM product_files WHERE id = ?",
                (file_id,)
            ).fetchone()

    def open_selected_file(self, *args):
        file = self.selected_file()

        if file is None:
            QMessageBox.information(
                self,
                "Файл не выбран",
                "Сначала выбери файл в таблице."
            )
            return

        path = BASE_DIR / file["file_path"]

        if not path.is_file():
            QMessageBox.warning(
                self,
                "Файл не найден",
                f"Файл не найден по пути:\n{path}"
            )
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_folder(self):
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.folder))
        )

    def remove_file(self):
        file = self.selected_file()

        if file is None:
            QMessageBox.information(
                self,
                "Файл не выбран",
                "Сначала выбери файл."
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление файла",
            f"Удалить файл «{file['file_name']}» "
            "из программы и папки изделия?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        path = BASE_DIR / file["file_path"]

        try:
            if path.is_file():
                path.unlink()

            with get_connection() as connection:
                connection.execute(
                    "DELETE FROM product_files WHERE id = ?",
                    (file["id"],)
                )

            self.load_files()

        except Exception as error:
            QMessageBox.critical(
                self, "Ошибка удаления", str(error)
            )


# ============================================================
# КАТАЛОГ ИЗДЕЛИЙ
# ============================================================

class ProductsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__()
        self.setup_ui()
        self.load_products()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(16)

        title = QLabel("Каталог изделий")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Изделия, артикулы, фотографии и файлы производства"
        )
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Поиск по артикулу, названию или категории..."
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.load_products)
        toolbar.addWidget(self.search_input, 1)

        add_button = QPushButton("+ Добавить изделие")
        add_button.setObjectName("accentButton")
        add_button.clicked.connect(self.add_product)
        toolbar.addWidget(add_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Артикул", "Название", "Категория",
            "Статус", "Дата создания"
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
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )

        self.table.doubleClicked.connect(self.edit_product)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()

        self.count_label = QLabel("Изделий: 0")
        self.count_label.setObjectName("subtitle")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_product)
        bottom.addWidget(edit_button)

        files_button = QPushButton("Файлы и фото")
        files_button.setObjectName("accentButton")
        files_button.clicked.connect(self.manage_files)
        bottom.addWidget(files_button)

        folder_button = QPushButton("Папка изделия")
        folder_button.clicked.connect(self.open_product_folder)
        bottom.addWidget(folder_button)

        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_product)
        bottom.addWidget(delete_button)

        layout.addLayout(bottom)

    def load_products(self, *args):
        search = self.search_input.text().strip()

        with get_connection() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute("""
                    SELECT * FROM products
                    WHERE article LIKE ?
                       OR name LIKE ?
                       OR category LIKE ?
                    ORDER BY id DESC
                """, (pattern, pattern, pattern)).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM products ORDER BY id DESC"
                ).fetchall()

        self.table.setRowCount(len(rows))

        for row_index, product in enumerate(rows):
            values = [
                product["article"],
                product["name"],
                product["category"] or "",
                product["status"] or "",
                product["created_at"] or "",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    product["id"]
                )
                self.table.setItem(row_index, column, item)

        self.count_label.setText(f"Изделий: {len(rows)}")

    def selected_product_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def add_product(self):
        dialog = ProductDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        try:
            with get_connection() as connection:
                cursor = connection.execute("""
                    INSERT INTO products (
                        article, name, description, category, status
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    data["article"],
                    data["name"],
                    data["description"],
                    data["category"],
                    data["status"],
                ))

                product_id = cursor.lastrowid

            ensure_product_folder(product_id)
            self.load_products()

        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Артикул уже существует",
                "Укажи уникальный артикул для нового изделия."
            )
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            self.load_products()

    def edit_product(self, *args):
        product_id = self.selected_product_id()

        if product_id is None:
            QMessageBox.information(
                self,
                "Изделие не выбрано",
                "Выбери изделие в таблице."
            )
            return

        with get_connection() as connection:
            product = connection.execute(
                "SELECT * FROM products WHERE id = ?",
                (product_id,)
            ).fetchone()

        if product is None:
            self.load_products()
            return

        dialog = ProductDialog(self, product)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        try:
            with get_connection() as connection:
                connection.execute("""
                    UPDATE products
                    SET article = ?, name = ?, description = ?,
                        category = ?, status = ?
                    WHERE id = ?
                """, (
                    data["article"],
                    data["name"],
                    data["description"],
                    data["category"],
                    data["status"],
                    product_id,
                ))

            self.load_products()

        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Артикул уже существует",
                "Этот артикул уже принадлежит другому изделию."
            )
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))

    def manage_files(self):
        product_id = self.selected_product_id()

        if product_id is None:
            QMessageBox.information(
                self,
                "Изделие не выбрано",
                "Выбери изделие в таблице."
            )
            return

        try:
            dialog = ProductFilesDialog(self, product_id)
            dialog.exec()
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))

    def open_product_folder(self):
        product_id = self.selected_product_id()

        if product_id is None:
            QMessageBox.information(
                self,
                "Изделие не выбрано",
                "Выбери изделие в таблице."
            )
            return

        try:
            folder = ensure_product_folder(product_id)
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(folder))
            )
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))

    def delete_product(self):
        product_id = self.selected_product_id()

        if product_id is None:
            QMessageBox.information(
                self,
                "Изделие не выбрано",
                "Выбери изделие в таблице."
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление изделия",
            "Удалить изделие из каталога?\n"
            "Файлы в папке изделия останутся на диске.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        with get_connection() as connection:
            connection.execute(
                "DELETE FROM product_files WHERE product_id = ?",
                (product_id,)
            )
            connection.execute(
                "DELETE FROM products WHERE id = ?",
                (product_id,)
            )

        self.load_products()


# ============================================================
# ОСТАЛЬНЫЕ РАЗДЕЛЫ
# ============================================================

class PlaceholderPage(QWidget):

    def __init__(self, title_text, description):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 35, 40, 35)

        title = QLabel(title_text)
        title.setObjectName("pageTitle")

        text = QLabel(description)
        text.setWordWrap(True)

        layout.addWidget(title)
        layout.addSpacing(18)
        layout.addWidget(text)
        layout.addStretch()


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KRAFT 3D Manager")
        self.setMinimumSize(1100, 700)
        self.create_interface()

    def create_interface(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 22, 15, 18)
        sidebar_layout.setSpacing(6)

        logo = QLabel("KRAFT 3D")
        logo.setObjectName("logo")

        logo_subtitle = QLabel("MANAGER")
        logo_subtitle.setObjectName("logoSubtitle")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(logo_subtitle)
        sidebar_layout.addSpacing(25)

        self.pages = QStackedWidget()

        definitions = [
            ("Главная", PlaceholderPage(
                "Главная", "Рабочая панель KRAFT 3D Manager."
            )),
            ("Изделия", ProductsPage()),
            ("Материалы", MaterialsPage()),
            ("Комплектующие", ComponentsPage()),
            ("Упаковка", PackagingPage()),
            ("Закупки", PurchasesPage()),
            ("Принтеры", PlaceholderPage(
                "Принтеры",
                "Оборудование, мощность, стоимость и ресурс."
            )),
            ("Калькулятор", CalculatorPage()),
            ("Отчёты", PlaceholderPage(
                "Отчёты", "Экспорт данных в Excel."
            )),
            ("Настройки", PlaceholderPage(
                "Настройки",
                "Параметры программы и резервное копирование."
            )),
        ]

        self.menu_buttons = []

        for _, page in definitions:
            self.pages.addWidget(page)

        for index, (name, _) in enumerate(definitions):
            button = QPushButton(name)
            button.setObjectName("menuButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, i=index: self.change_page(i)
            )
            sidebar_layout.addWidget(button)
            self.menu_buttons.append(button)

        sidebar_layout.addStretch()

        version = QLabel("KRAFT 3D Manager\nv0.4.0")
        version.setObjectName("version")
        sidebar_layout.addWidget(version)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.pages)

        self.change_page(0)

    # ИСПРАВЛЕНИЕ: метод теперь находится внутри MainWindow.
    def change_page(self, index):
        self.pages.setCurrentIndex(index)

        page = self.pages.widget(index)

        # Обновляем справочники при переходе на соответствующие страницы.
        if isinstance(page, ProductsPage):
            page.load_products()
        elif isinstance(page, PackagingPage):
            page.load_stock()
            page.load_labels()
            page.load_kits()
        elif isinstance(page, CalculatorPage):
            page.load_reference_data()
            page.recalculate()


# ============================================================
# СТИЛИ
# ============================================================

STYLE = """
QMainWindow {
    background-color: #181818;
}

QWidget {
    color: #eeeeee;
    font-family: "Segoe UI";
    font-size: 14px;
}

QDialog {
    background-color: #202020;
    color: #eeeeee;
}

QMessageBox {
    background-color: #202020;
    color: #eeeeee;
}

QMessageBox QLabel {
    color: #eeeeee;
    background-color: transparent;
}

#sidebar {
    background-color: #202020;
    border-right: 1px solid #303030;
}

#logo {
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
}

#logoSubtitle {
    color: #ff7a00;
    font-size: 12px;
    font-weight: 700;
}

#menuButton {
    background-color: transparent;
    color: #bdbdbd;
    border: none;
    border-radius: 8px;
    padding: 12px 15px;
    text-align: left;
}

#menuButton:hover {
    background-color: #303030;
    color: #ffffff;
}

#pageTitle {
    color: #ffffff;
    font-size: 26px;
    font-weight: 700;
}

#subtitle {
    color: #ff9a3d;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #252525;
    color: #eeeeee;
    border: 1px solid #414141;
    border-radius: 6px;
    padding: 8px;
    selection-background-color: #75421e;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #ff7a00;
}

QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {
    color: #888888;
    background-color: #202020;
}

QComboBox QAbstractItemView {
    background-color: #252525;
    color: #eeeeee;
    selection-background-color: #75421e;
    selection-color: #ffffff;
    border: 1px solid #414141;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 5px;
}

QPushButton {
    background-color: #303030;
    color: #eeeeee;
    border: 1px solid #414141;
    border-radius: 6px;
    padding: 9px 12px;
}

QPushButton:hover {
    background-color: #414141;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #252525;
}

QPushButton:disabled {
    color: #777777;
    background-color: #252525;
}

QPushButton#accentButton {
    background-color: #ff7a00;
    color: #ffffff;
    border: none;
    font-weight: 600;
}

QPushButton#accentButton:hover {
    background-color: #e86f00;
}

QPushButton#dangerButton {
    color: #ff8585;
}

QPushButton#dangerButton:hover {
    background-color: #492727;
    color: #ffaaaa;
}

QTableWidget {
    background-color: #202020;
    alternate-background-color: #262626;
    color: #eeeeee;
    gridline-color: #383838;
    border: 1px solid #383838;
    border-radius: 6px;
    selection-background-color: #75421e;
    selection-color: #ffffff;
}

QTableWidget::item {
    color: #eeeeee;
    padding: 5px;
}

QTableWidget::item:selected {
    background-color: #75421e;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #303030;
    color: #eeeeee;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #484848;
    font-weight: 600;
}

QLabel {
    color: #dddddd;
    background-color: transparent;
}

QCheckBox, QRadioButton {
    color: #eeeeee;
    background-color: transparent;
}

QToolTip {
    background-color: #303030;
    color: #ffffff;
    border: 1px solid #555555;
    padding: 5px;
}

#version {
    color: #888888;
    font-size: 11px;
}
"""


# ============================================================
# ЗАПУСК
# ============================================================

def main():
    create_directories()
    initialize_database()

    app = QApplication(sys.argv)
    app.setApplicationName("KRAFT 3D Manager")
    app.setApplicationVersion("0.4.0")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
